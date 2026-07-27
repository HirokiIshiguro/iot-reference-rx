import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


SCRIPT = Path(__file__).resolve().parents[2] / "build_rx671_fwup_v2_rsu.py"
SPEC = importlib.util.spec_from_file_location("build_rx671_fwup_v2_rsu", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def _s3_record(address: int, data: bytes) -> str:
    body = address.to_bytes(4, "big") + data
    count = len(body) + 1
    checksum = (~(count + sum(body))) & 0xFF
    return "S3" + bytes([count]).hex().upper() + body.hex().upper() + f"{checksum:02X}"


def _private_key_pem(curve: ec.EllipticCurve = ec.SECP256R1()) -> bytes:
    key = ec.generate_private_key(curve)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


class BuildTests(unittest.TestCase):
    def _write_valid_mot(self, directory: Path) -> Path:
        mot = directory / "app.mot"
        mot.write_text(
            "\n".join(
                (
                    _s3_record(builder.APPLICATION_START, b"\x10\x20\x30\x40"),
                    _s3_record(builder.RESET_VECTOR_ADDRESS, b"\x00\x03\xF0\xFF"),
                    "S705FFF0030008",
                )
            )
            + "\n",
            encoding="ascii",
        )
        return mot

    def _write_key(self, directory: Path, pem: bytes | None = None) -> Path:
        key = directory / "signer.pem"
        key.write_bytes(pem if pem is not None else _private_key_pem())
        return key

    def test_builds_fixed_rx671_image_and_raw_p256_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = self._write_valid_mot(directory)
            key_path = self._write_key(directory)

            image = builder.build_from_files(mot, key_path)

            self.assertEqual(builder.FWUP_AREA_SIZE, len(image))
            self.assertEqual(b"Renesas", image[0:7])
            self.assertEqual(builder.IMAGE_FLAG_TESTING, image[7])
            self.assertEqual(
                builder.SIGNATURE_TYPE,
                image[8 : 8 + len(builder.SIGNATURE_TYPE)],
            )
            self.assertEqual(
                b"\x00" * (32 - len(builder.SIGNATURE_TYPE)),
                image[8 + len(builder.SIGNATURE_TYPE) : 40],
            )
            self.assertEqual(64, struct.unpack_from("<I", image, 0x28)[0])
            self.assertEqual(0, struct.unpack_from("<I", image, 0x12C)[0])
            self.assertEqual(0xFFFFFFFF, struct.unpack_from("<I", image, 0x130)[0])
            self.assertEqual(0xFFFFFFFF, struct.unpack_from("<I", image, 0x134)[0])

            descriptor = image[
                builder.RSU_HEADER_SIZE : builder.RSU_HEADER_SIZE
                + builder.RSU_DESCRIPTOR_SIZE
            ]
            self.assertEqual(1, struct.unpack_from("<I", descriptor, 0)[0])
            self.assertEqual(
                builder.APPLICATION_START,
                struct.unpack_from("<I", descriptor, 4)[0],
            )
            self.assertEqual(
                builder.APPLICATION_SIZE,
                struct.unpack_from("<I", descriptor, 8)[0],
            )
            self.assertEqual(
                b"\xFF" * (builder.RSU_DESCRIPTOR_SIZE - 12),
                descriptor[12:],
            )
            self.assertEqual(
                b"\x10\x20\x30\x40",
                image[builder.APPLICATION_START - builder.FWUP_AREA_START :
                      builder.APPLICATION_START - builder.FWUP_AREA_START + 4],
            )
            self.assertEqual(
                b"\x00\x03\xF0\xFF",
                image[builder.RESET_VECTOR_ADDRESS - builder.FWUP_AREA_START :
                      builder.RESET_VECTOR_ADDRESS - builder.FWUP_AREA_START + 4],
            )

            private_key = serialization.load_pem_private_key(
                key_path.read_bytes(), password=None
            )
            raw_signature = image[0x2C : 0x2C + 64]
            r = int.from_bytes(raw_signature[:32], "big")
            s = int.from_bytes(raw_signature[32:], "big")
            der_signature = utils.encode_dss_signature(r, s)
            signed_data = image[builder.RSU_HEADER_SIZE :]
            private_key.public_key().verify(
                der_signature,
                signed_data,
                ec.ECDSA(hashes.SHA256()),
            )

            tampered = bytearray(signed_data)
            tampered[-1] ^= 1
            with self.assertRaises(Exception):
                private_key.public_key().verify(
                    der_signature,
                    bytes(tampered),
                    ec.ECDSA(hashes.SHA256()),
                )

    def test_rejects_data_below_application_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = directory / "outside.mot"
            mot.write_text(
                _s3_record(builder.APPLICATION_START - 1, b"\x00") + "\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "outside RX671 application range"):
                builder.build_from_files(mot, self._write_key(directory))

    def test_omits_known_rx671_option_setting_memory_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = self._write_valid_mot(directory)
            original = mot.read_text(encoding="ascii")
            mot.write_text(
                _s3_record(
                    builder.OPTION_SETTING_MEMORY_START,
                    b"\x8F" + b"\xFF" * 15,
                )
                + "\n"
                + original,
                encoding="ascii",
            )
            image = builder.build_from_files(mot, self._write_key(directory))
            self.assertEqual(builder.FWUP_AREA_SIZE, len(image))
            self.assertNotIn(b"\x8F" + b"\xFF" * 15, image[: builder.RSU_HEADER_SIZE])

    def test_rejects_unknown_non_application_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = self._write_valid_mot(directory)
            mot.write_text(
                _s3_record(0x00100000, b"\x00")
                + "\n"
                + mot.read_text(encoding="ascii"),
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "outside RX671 application range"):
                builder.build_from_files(mot, self._write_key(directory))

    def test_rejects_record_crossing_bootloader_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = directory / "crossing.mot"
            mot.write_text(
                _s3_record(builder.APPLICATION_END - 1, b"\x01\x02\x03") + "\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "outside RX671 application range"):
                builder.build_from_files(mot, self._write_key(directory))

    def test_rejects_bad_srecord_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = directory / "bad-checksum.mot"
            valid = _s3_record(builder.APPLICATION_START, b"\x01")
            mot.write_text(valid[:-2] + "00\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "checksum"):
                builder.build_from_files(mot, self._write_key(directory))

    def test_rejects_missing_reset_vector(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = directory / "no-reset.mot"
            mot.write_text(
                _s3_record(builder.APPLICATION_START, b"\x01") + "\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "reset vector"):
                builder.build_from_files(mot, self._write_key(directory))

    def test_rejects_non_p256_private_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = self._write_valid_mot(directory)
            key = self._write_key(directory, _private_key_pem(ec.SECP384R1()))
            with self.assertRaisesRegex(ValueError, "P-256"):
                builder.build_from_files(mot, key)

    def test_rejects_malformed_private_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            mot = self._write_valid_mot(directory)
            key = self._write_key(directory, b"not a private key")
            with self.assertRaisesRegex(ValueError, "private key"):
                builder.build_from_files(mot, key)


if __name__ == "__main__":
    unittest.main()

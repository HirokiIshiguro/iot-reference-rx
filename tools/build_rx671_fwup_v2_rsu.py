#!/usr/bin/env python3
"""Build the legacy contiguous signed RSU used by the RX671 bootloader.

The historical command/module filename is retained for existing CI and remote
staging callers.  The full RSU format is the original sequence/start/end/reset/
hardware-ID descriptor, not the r_fwup multi-segment format.  The whole area
after the 0x200-byte header is signed, including the 0x100-byte descriptor.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


FWUP_AREA_START = 0xFFF00000
FWUP_AREA_SIZE = 0x000C0000
FWUP_AREA_END = FWUP_AREA_START + FWUP_AREA_SIZE - 1

RSU_HEADER_SIZE = 0x200
RSU_DESCRIPTOR_SIZE = 0x100
APPLICATION_START = FWUP_AREA_START + RSU_HEADER_SIZE + RSU_DESCRIPTOR_SIZE
APPLICATION_END = FWUP_AREA_END
APPLICATION_SIZE = APPLICATION_END - APPLICATION_START + 1
RESET_VECTOR_ADDRESS = APPLICATION_END - 3
# CC-RX emits the RX671 option-setting memory records in a load module. They
# are programmed with the base image/debugger, not by the dual-bank FWUP
# payload, so the RSU converter recognizes and deliberately omits this exact
# device range. Any other record outside the application remains fail-closed.
OPTION_SETTING_MEMORY_START = 0xFE7F5D00
OPTION_SETTING_MEMORY_END = 0xFE7F5D80

MAGIC_CODE = b"Renesas"
IMAGE_FLAG_TESTING = 0xFE
SIGNATURE_TYPE = b"sig-sha256-ecdsa"
RAW_P256_SIGNATURE_SIZE = 64
HARDWARE_ID = 9

_SIGNATURE_TYPE_OFFSET = 0x08
_SIGNATURE_SIZE_OFFSET = 0x28
_SIGNATURE_OFFSET = 0x2C
_SIGNATURE_FIELD_SIZE = 0x100
_DATA_FLASH_FLAG_OFFSET = 0x12C
_DATA_FLASH_START_OFFSET = 0x130
_DATA_FLASH_END_OFFSET = 0x134

_SREC_ADDRESS_BYTES = {
    "S0": 2,
    "S1": 2,
    "S2": 3,
    "S3": 4,
    "S5": 2,
    "S6": 3,
    "S7": 4,
    "S8": 3,
    "S9": 2,
}
_SREC_DATA_TYPES = {"S1", "S2", "S3"}


def _decode_srecord(line: str, line_no: int) -> tuple[str, int, bytes]:
    record_type = line[:2]
    if record_type not in _SREC_ADDRESS_BYTES:
        raise ValueError(
            f"unsupported S-record type on line {line_no}: {record_type or '<empty>'}"
        )
    if len(line) < 4 or len(line) % 2:
        raise ValueError(f"malformed S-record length on line {line_no}")

    try:
        encoded = bytes.fromhex(line[2:])
    except ValueError as exc:
        raise ValueError(f"non-hex S-record data on line {line_no}") from exc

    byte_count = encoded[0]
    if len(encoded) != byte_count + 1:
        raise ValueError(
            f"S-record byte count mismatch on line {line_no}: "
            f"declared={byte_count}, actual={len(encoded) - 1}"
        )
    if sum(encoded) & 0xFF != 0xFF:
        raise ValueError(f"S-record checksum mismatch on line {line_no}")

    address_bytes = _SREC_ADDRESS_BYTES[record_type]
    if byte_count < address_bytes + 1:
        raise ValueError(f"S-record is too short on line {line_no}")
    address = int.from_bytes(encoded[1 : 1 + address_bytes], "big")
    data = encoded[1 + address_bytes : -1]
    return record_type, address, data


def parse_application_mot(mot_path: Path) -> bytes:
    """Parse an application MOT and return the full, padded RX671 payload."""

    payload = bytearray(b"\xFF" * APPLICATION_SIZE)
    populated = bytearray(APPLICATION_SIZE)
    data_bytes = 0

    try:
        handle = mot_path.open("r", encoding="ascii", errors="strict")
    except OSError as exc:
        raise ValueError(f"cannot read input MOT: {mot_path}") from exc

    try:
        with handle:
            for line_no, raw_line in enumerate(handle, 1):
                line = raw_line.strip()
                if not line:
                    continue
                record_type, address, data = _decode_srecord(line, line_no)
                if record_type not in _SREC_DATA_TYPES:
                    continue
                if not data:
                    raise ValueError(f"empty data S-record on line {line_no}")

                end_exclusive = address + len(data)
                if (
                    address < APPLICATION_START
                    or end_exclusive > APPLICATION_END + 1
                ):
                    if (
                        OPTION_SETTING_MEMORY_START <= address
                        and end_exclusive <= OPTION_SETTING_MEMORY_END
                    ):
                        continue
                    raise ValueError(
                        f"S-record data outside RX671 application range on line {line_no}: "
                        f"0x{address:08X}-0x{end_exclusive - 1:08X}; "
                        f"allowed=0x{APPLICATION_START:08X}-0x{APPLICATION_END:08X}"
                    )

                offset = address - APPLICATION_START
                for index, value in enumerate(data):
                    target = offset + index
                    if populated[target] and payload[target] != value:
                        raise ValueError(
                            f"conflicting overlapping S-record data at "
                            f"0x{address + index:08X} on line {line_no}"
                        )
                    if not populated[target]:
                        data_bytes += 1
                    populated[target] = 1
                    payload[target] = value
    except UnicodeError as exc:
        raise ValueError(f"input MOT is not ASCII: {mot_path}") from exc

    if data_bytes == 0:
        raise ValueError("input MOT contains no application data")

    reset_offset = RESET_VECTOR_ADDRESS - APPLICATION_START
    reset_populated = populated[reset_offset : reset_offset + 4]
    reset_vector = payload[reset_offset : reset_offset + 4]
    if reset_populated != b"\x01\x01\x01\x01" or reset_vector == b"\xFF" * 4:
        raise ValueError(
            f"RX671 reset vector at 0x{RESET_VECTOR_ADDRESS:08X} is missing or blank"
        )

    return bytes(payload)


def load_p256_private_key(key_path: Path) -> ec.EllipticCurvePrivateKey:
    try:
        encoded = key_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read private key: {key_path}") from exc

    try:
        private_key = serialization.load_pem_private_key(encoded, password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise ValueError(f"invalid unencrypted PEM private key: {key_path}") from exc

    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise ValueError("private key must be an ECDSA P-256 private key")
    if not isinstance(private_key.curve, ec.SECP256R1):
        raise ValueError(
            f"private key must use ECDSA P-256, got {private_key.curve.name}"
        )
    return private_key


def legacy_descriptor(application_start: int, application_end: int,
                      sequence: int = 1, hardware_id: int = HARDWARE_ID) -> bytes:
    """Serialize the original five-word RSU descriptor, independent of MCU."""
    if (type(sequence) is not int or not 1 <= sequence <= 0xFFFFFFFF or
            not 0 <= application_start <= application_end <= 0xFFFFFFFF or
            not 0 <= hardware_id <= 0xFFFFFFFF):
        raise ValueError("invalid legacy RSU sequence/address/hardware ID")
    descriptor = bytearray(RSU_DESCRIPTOR_SIZE)
    struct.pack_into("<IIIII", descriptor, 0, sequence, application_start,
                     application_end, application_end - 3, hardware_id)
    return bytes(descriptor)


def validate_legacy_descriptor(descriptor: bytes, application_start: int,
                               application_end: int, *, sequence: int | None = None) -> int:
    """Reject a segmented descriptor even if its ECDSA signature is valid."""
    if len(descriptor) != RSU_DESCRIPTOR_SIZE:
        raise ValueError("legacy RSU descriptor size mismatch")
    actual_sequence, start, end, reset, hardware_id = struct.unpack_from("<IIIII", descriptor)
    if (not 1 <= actual_sequence <= 0xFFFFFFFF or
            (sequence is not None and actual_sequence != sequence) or
            (start, end, reset, hardware_id) !=
            (application_start, application_end, application_end - 3, HARDWARE_ID)):
        raise ValueError("legacy RSU descriptor layout mismatch")
    return actual_sequence


def build_descriptor(sequence: int = 1) -> bytes:
    return legacy_descriptor(APPLICATION_START, APPLICATION_END, sequence)


def _sign_raw_p256(
    signed_data: bytes, private_key: ec.EllipticCurvePrivateKey
) -> bytes:
    der_signature = private_key.sign(signed_data, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_signature)
    try:
        raw_signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    except OverflowError as exc:
        raise ValueError("ECDSA signature does not fit the raw P-256 format") from exc

    try:
        private_key.public_key().verify(
            utils.encode_dss_signature(r, s),
            signed_data,
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise RuntimeError("ECDSA signature self-verification failed") from exc

    if len(raw_signature) != RAW_P256_SIGNATURE_SIZE:
        raise RuntimeError("unexpected raw P-256 signature size")
    return raw_signature


def build_header(signature: bytes) -> bytes:
    if len(signature) != RAW_P256_SIGNATURE_SIZE:
        raise ValueError(
            f"raw P-256 signature must be {RAW_P256_SIGNATURE_SIZE} bytes"
        )

    header = bytearray(b"\xFF" * RSU_HEADER_SIZE)
    header[0 : len(MAGIC_CODE)] = MAGIC_CODE
    header[7] = IMAGE_FLAG_TESTING
    header[_SIGNATURE_TYPE_OFFSET : _SIGNATURE_TYPE_OFFSET + 32] = b"\x00" * 32
    header[
        _SIGNATURE_TYPE_OFFSET :
        _SIGNATURE_TYPE_OFFSET + len(SIGNATURE_TYPE)
    ] = SIGNATURE_TYPE
    struct.pack_into(
        "<I", header, _SIGNATURE_SIZE_OFFSET, RAW_P256_SIGNATURE_SIZE
    )
    header[
        _SIGNATURE_OFFSET : _SIGNATURE_OFFSET + _SIGNATURE_FIELD_SIZE
    ] = b"\x00" * _SIGNATURE_FIELD_SIZE
    header[_SIGNATURE_OFFSET : _SIGNATURE_OFFSET + len(signature)] = signature

    # RX671 Data Flash is wholly owned by LittleFS/KVS and must never be part
    # of an OTA image.
    struct.pack_into("<I", header, _DATA_FLASH_FLAG_OFFSET, 0)
    struct.pack_into("<I", header, _DATA_FLASH_START_OFFSET, 0xFFFFFFFF)
    struct.pack_into("<I", header, _DATA_FLASH_END_OFFSET, 0xFFFFFFFF)
    return bytes(header)


def build_image(
    payload: bytes, private_key: ec.EllipticCurvePrivateKey, sequence: int = 1
) -> bytes:
    if len(payload) != APPLICATION_SIZE:
        raise ValueError(
            f"RX671 application payload must be {APPLICATION_SIZE} bytes, "
            f"got {len(payload)}"
        )

    descriptor = build_descriptor(sequence)
    signed_data = descriptor + payload
    signature = _sign_raw_p256(signed_data, private_key)
    image = build_header(signature) + signed_data
    if len(image) != FWUP_AREA_SIZE:
        raise RuntimeError(
            f"RX671 legacy RSU image size mismatch: expected={FWUP_AREA_SIZE}, "
            f"actual={len(image)}"
        )
    return image


def build_from_files(mot_path: Path, key_path: Path) -> bytes:
    payload = parse_application_mot(Path(mot_path))
    private_key = load_p256_private_key(Path(key_path))
    return build_image(payload, private_key)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mot", required=True, type=Path, help="Input RX671 application MOT"
    )
    parser.add_argument(
        "--key",
        required=True,
        type=Path,
        help="Unencrypted ECDSA P-256 private key in PEM format",
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Output signed legacy contiguous RSU"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        image = build_from_files(args.mot, args.key)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(image)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(f"Generated RX671 legacy contiguous RSU: {args.output}")
    print(
        f"  size={len(image)} bytes, application="
        f"0x{APPLICATION_START:08X}-0x{APPLICATION_END:08X}, "
        "format=legacy-full-rsu, sequence=1, dataflash=disabled"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

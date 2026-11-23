"""Exercise public signer provisioning over a mock serial command/response port."""
import contextlib
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from tools import bg96_bootloader_integration as boot

with mock.patch.dict(sys.modules, {"bg96_bootloader_integration": boot}):
    from tools import bg96_ota_prepare as prepare


ROOT = Path(__file__).resolve().parents[3]


def certificate(curve=None):
    # An ephemeral signing handle creates only a public certificate fixture.
    key = ec.generate_private_key(curve or ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "BG96 public signer fixture")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
            .not_valid_after(datetime(2030, 1, 1, tzinfo=timezone.utc))
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM)


class FakeSerial:
    def __init__(self, fail_key=None, commit_response=b"Configuration save success\r\n"):
        self.command = bytearray()
        self.pending = bytearray()
        self.commands = []
        self.fail_key = fail_key
        self.commit_response = commit_response
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.pending)

    def reset_input_buffer(self):
        self.pending.clear()

    def write(self, data):
        if data == b"\r\n":
            command = self.command.decode("ascii")
            self.commands.append(command)
            self.command.clear()
            if self.fail_key and command.startswith("conf set " + self.fail_key + " "):
                self.pending.extend(b"Error\r\n")
            elif command == "conf commit":
                self.pending.extend(self.commit_response)
            else:
                self.pending.extend(b"OK\r\n")
        else:
            self.command.extend(data)
        return len(data)

    def read(self, size):
        result = bytes(self.pending[:size])
        del self.pending[:size]
        return result

    def flush(self):
        pass

    def close(self):
        self.closed = True


class Bg96OtaPrepareTests(unittest.TestCase):
    def setUp(self):
        self.allowed = ROOT.parent.resolve()
        self.temporary = tempfile.TemporaryDirectory(prefix="bg96-public-", dir=self.allowed)
        self.folder = Path(self.temporary.name).resolve()
        self.assertTrue(self.folder.is_relative_to(self.allowed))
        self.addCleanup(self.cleanup)
        self.path = self.folder / "signer.crt.pem"
        self.pem = certificate()
        self.path.write_bytes(self.pem)
        self.args = SimpleNamespace(code_signer_cert=self.path, uart_port="MOCK", baud=921600,
                                    provision_cli_timeout=1, provision_char_delay=0,
                                    provision_line_delay=0)

    def cleanup(self):
        self.assertEqual(self.folder, Path(self.temporary.name).resolve())
        self.assertTrue(self.folder.is_relative_to(self.allowed))
        self.temporary.cleanup()

    def execute(self, port):
        clock = iter(range(1000))
        output = io.StringIO()
        with mock.patch.object(prepare, "parse_args", return_value=self.args), \
                mock.patch.object(prepare.serial, "Serial", return_value=port), \
                mock.patch.object(prepare, "run_rfp"), mock.patch.object(prepare, "enter_cli_mode"), \
                mock.patch.object(boot.time, "time", side_effect=lambda: next(clock)), \
                mock.patch.object(boot.time, "sleep"), mock.patch.object(boot, "write_serial_text"), \
                contextlib.redirect_stdout(output):
            return prepare.main()

    def test_same_certificate_spki_is_saved_before_checked_commit(self):
        port = FakeSerial()
        self.assertEqual(self.execute(port), 0)
        self.assertEqual(len(port.commands), 3)
        self.assertTrue(port.commands[0].startswith("conf set codesigncert "))
        self.assertTrue(port.commands[1].startswith("conf set codesignpubkey "))
        self.assertEqual(port.commands[2], "conf commit")
        cert = x509.load_pem_x509_certificate(port.commands[0].split(" ", 3)[3].encode())
        public = serialization.load_pem_public_key(port.commands[1].split(" ", 3)[3].encode())
        encode = lambda key: key.public_bytes(serialization.Encoding.DER,
                                              serialization.PublicFormat.SubjectPublicKeyInfo)
        self.assertEqual(encode(cert.public_key()), encode(public))
        self.assertTrue(port.closed)

    def test_failed_certificate_or_public_key_write_never_commits(self):
        for key in ("codesigncert", "codesignpubkey"):
            with self.subTest(key=key):
                port = FakeSerial(fail_key=key)
                with self.assertRaisesRegex(RuntimeError, "CLI command failed"):
                    self.execute(port)
                self.assertNotIn("conf commit", port.commands)
                self.assertTrue(port.closed)

    def test_commit_still_requires_configuration_save_ack(self):
        port = FakeSerial(commit_response=b"OK\r\n")
        with self.assertRaisesRegex(RuntimeError, "did not report success: conf commit"):
            self.execute(port)
        self.assertTrue(port.closed)

    def test_non_p256_certificate_is_rejected_before_opening_port(self):
        self.path.write_bytes(certificate(ec.SECP384R1()))
        with mock.patch.object(prepare, "parse_args", return_value=self.args), \
                mock.patch.object(prepare.serial, "Serial") as serial, \
                mock.patch.object(prepare, "run_rfp") as rfp:
            with self.assertRaisesRegex(RuntimeError, "ECDSA P-256"):
                prepare.main()
        serial.assert_not_called()
        rfp.assert_not_called()

    def test_private_header_and_appended_object_are_rejected_without_body_read(self):
        for prefix, limit in ((b"", len(b"-----BEGIN PRIVATE KEY-----\n")),
                              (self.pem, len(self.pem) + 1)):
            with self.subTest(appended=bool(prefix)):
                self.path.write_bytes(prefix + b"-----BEGIN PRIVATE KEY-----\nUNREAD_FIXTURE_BODY\n")
                positions = []
                original_open = Path.open

                class Guard:
                    def __init__(self, stream):
                        self.stream = stream

                    def __enter__(self):
                        return self

                    def __exit__(self, *_args):
                        self.stream.close()

                    def readline(self, size):
                        result = self.stream.readline(size)
                        positions.append(self.stream.tell())
                        if self.stream.tell() > limit:
                            raise AssertionError("private body read")
                        return result

                    def read(self, size):
                        result = self.stream.read(size)
                        positions.append(self.stream.tell())
                        if self.stream.tell() > limit:
                            raise AssertionError("private body read")
                        return result

                def opened(path, *args, **kwargs):
                    stream = original_open(path, *args, **kwargs)
                    return Guard(stream) if path == self.path else stream

                with mock.patch.object(Path, "open", opened), \
                        mock.patch.object(prepare, "parse_args", return_value=self.args), \
                        mock.patch.object(prepare.serial, "Serial") as serial:
                    with self.assertRaisesRegex(RuntimeError, "exactly one public certificate"):
                        prepare.main()
                serial.assert_not_called()
                self.assertLessEqual(max(positions), limit)


if __name__ == "__main__":
    unittest.main()

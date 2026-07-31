from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "tools"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


import sys

sys.path.insert(0, str(TOOLS))
host = load("rx671_ota_host", TOOLS / "rx671_ota_host.py")
provision = load("provision_rx671_ota", TOOLS / "provision_rx671_ota.py")
ota_test = load("test_rx671_ota", TOOLS / "test_rx671_ota.py")


class FakeSerial:
    def __init__(self, responses: bytes = b"\r\nOK.\r\n\r\n>"):
        self.responses = bytearray(responses)
        self.writes: list[bytes] = []
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.responses)

    def read(self, size):
        if not self.responses:
            return b""
        result = bytes(self.responses[:size])
        del self.responses[:size]
        return result

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def close(self):
        self.closed = True


class RfpContractTests(unittest.TestCase):
    def test_program_preserves_data_flash(self):
        command = host.RfpConfig().program_command(Path("/tmp/boot.mot"), leave_reset=True)
        self.assertIn("-p", command)
        self.assertIn("-v", command)
        self.assertNotIn("-reset", command)
        self.assertNotIn("-run", command)
        self.assertNotIn("-erase-chip", command)
        self.assertEqual("e2l:OBE110024", command[command.index("-t") + 1])

    def test_cli_echo_containing_ng_is_not_a_false_error(self):
        serial = FakeSerial(
            b"conf set key BASE64NGVALUE\r\n\r\nOK.\r\n\r\n>"
        )
        response = host.send_ascii_command(
            serial,
            "conf set key BASE64NGVALUE",
            timeout=1,
            char_delay=0,
        )
        self.assertIn(b"\r\nOK.\r\n\r\n>", response)

    def test_cli_echo_line_starting_ok_is_not_a_false_success(self):
        serial = FakeSerial(b"conf set key HEADER\nOKBASE64VALUE\nTRAILER\r\n")
        with self.assertRaises(TimeoutError):
            host.send_ascii_command(
                serial,
                "conf set key HEADER\nOKBASE64VALUE\nTRAILER",
                timeout=0.01,
                char_delay=0,
            )

    def test_cli_command_must_leave_space_for_target_nul_terminator(self):
        accepted = FakeSerial()
        host.send_ascii_command(
            accepted,
            "A" * (host.CLI_INPUT_BUFFER_BYTES - 1),
            timeout=1,
            char_delay=0,
        )
        self.assertEqual(
            host.CLI_INPUT_BUFFER_BYTES + 1,
            len(b"".join(accepted.writes)),
        )

        rejected = FakeSerial()
        with self.assertRaisesRegex(ValueError, "too long"):
            host.send_ascii_command(
                rejected,
                "S" * host.CLI_INPUT_BUFFER_BYTES,
                timeout=1,
                char_delay=0,
            )
        self.assertEqual([], rejected.writes)

    def test_rfp_timeout_does_not_disclose_command_or_auth_id(self):
        secret = "DO_NOT_DISCLOSE_AUTH_ID"

        def timeout_runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        with self.assertRaises(TimeoutError) as raised:
            host.run_checked(
                ["rfp-cli", "-auth", "id", secret],
                label="RFP operation",
                timeout=0.25,
                runner=timeout_runner,
            )
        message = str(raised.exception)
        self.assertEqual("RFP operation timed out after 0.25 seconds", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("rfp-cli", message)

    def test_rfp_failure_redacts_auth_id_from_tool_output(self):
        secret = "DO_NOT_DISCLOSE_AUTH_ID"

        def failed_runner(_command, **_kwargs):
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=f"RFP rejected -auth id {secret}",
            )

        with self.assertRaises(RuntimeError) as raised:
            host.run_checked(
                ["rfp-cli", "-auth", "id", secret],
                label="RFP operation",
                runner=failed_runner,
            )
        message = str(raised.exception)
        self.assertNotIn(secret, message)
        self.assertIn("<redacted-auth-id>", message)

    def test_sensitive_expected_token_is_not_disclosed_on_timeout(self):
        serial = FakeSerial(b"")
        with self.assertRaises(TimeoutError) as raised:
            host.read_until(
                serial,
                success_tokens=(b"DO_NOT_DISCLOSE",),
                timeout=0.01,
            )
        self.assertNotIn("DO_NOT_DISCLOSE", str(raised.exception))

    def test_cleanup_rejects_escape_and_deletes_regular_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item = root / "runtime" / "plain.mot"
            item.parent.mkdir()
            item.write_bytes(b"secret")
            self.assertEqual(["runtime/plain.mot"], host.cleanup_plaintext([item], root))
            self.assertFalse(item.exists())
            with self.assertRaises(ValueError):
                host.cleanup_plaintext([root.parent / "outside"], root)

    def test_timestamp_log_preserves_text_across_read_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "uart.log"
            log = host.TimestampLog(path)
            chunks = ("partial", " line\r\nnext", " line\n")
            for chunk in chunks:
                log.write(chunk)

            with path.open("r", encoding="utf-8", newline="") as handle:
                captured = handle.read()
            without_prefixes = re.sub(
                r"\[[^\]]+\]\[\+[^\]]+\] ",
                "",
                captured,
            )
            self.assertEqual("".join(chunks), without_prefixes)
            self.assertIn("partial line\r\n", captured)
            self.assertIn("next line\n", captured)


class ProvisioningContractTests(unittest.TestCase):
    def test_enter_cli_terminates_command_with_crlf(self):
        serial = FakeSerial()
        with mock.patch.object(
            provision,
            "read_until",
            side_effect=[TimeoutError(), b"Going to FreeRTOS-CLI"],
        ) as read_until:
            provision.enter_cli(serial, timeout=1, char_delay=0)
        self.assertEqual(b"CLI\r\n", b"".join(serial.writes))
        second_wait = read_until.call_args_list[1]
        self.assertIn(b"\r\n>", second_wait.kwargs["success_tokens"])
        self.assertNotIn(b"\r\n> ", second_wait.kwargs["success_tokens"])

    def test_pem_payload_is_sent_but_not_returned(self):
        with tempfile.TemporaryDirectory() as temporary:
            pem = Path(temporary) / "key.pem"
            pem.write_text(
                "-----BEGIN PRIVATE KEY-----\nSENSITIVE\n-----END PRIVATE KEY-----\n",
                encoding="ascii",
            )
            serial = FakeSerial()
            provision._set_pem(serial, "key", pem, char_delay=0, timeout=1)
            payload = b"".join(serial.writes)
            self.assertIn(b"conf set key -----BEGIN PRIVATE KEY-----", payload)
            self.assertIn(b"SENSITIVE", payload)

    def test_provision_programs_both_images_without_chip_erase(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {}
            for name in (
                "provisioner.mot",
                "bootloader.mot",
                "device.crt",
                "device.key",
                "signer.crt",
                "signer.pub",
            ):
                path = root / name
                path.write_text("-----BEGIN TEST-----\nX\n-----END TEST-----\n", encoding="ascii")
                files[name] = path
            args = argparse.Namespace(
                artifact_dir=root / "artifacts",
                rfp_cli="rfp-cli",
                rfp_device="RX671",
                rfp_tool="e2l:OBE110024",
                rfp_interface="fine",
                rfp_speed="500K",
                rfp_auth_id="F" * 32,
                rfp_timeout=123,
                provisioner_mot=files["provisioner.mot"],
                bootloader_mot=files["bootloader.mot"],
                port="/dev/test",
                baud=921600,
                boot_timeout=1,
                char_delay=0,
                command_timeout=1,
                commit_timeout=1,
                endpoint="example.iot",
                thing_name="thing",
                certificate=files["device.crt"],
                private_key=files["device.key"],
                codesigner_certificate=files["signer.crt"],
                codesigner_public_key=files["signer.pub"],
            )
            serial = FakeSerial()
            commands = []

            def capture(command, **_kwargs):
                commands.append(command)
                return mock.Mock(returncode=0)

            with mock.patch.object(
                provision, "run_checked", side_effect=capture
            ) as run_command, mock.patch.object(
                provision, "open_serial", return_value=serial
            ), mock.patch.object(provision, "enter_cli"), mock.patch.object(
                provision, "send_ascii_command", return_value=b"OK"
            ) as send_command:
                summary = provision.provision(args)
            self.assertTrue(summary["success"])
            self.assertEqual(3, len(commands))
            self.assertTrue(all("-erase-chip" not in command for command in commands))
            self.assertTrue(
                all(
                    call.kwargs["timeout"] == 123
                    for call in run_command.call_args_list
                )
            )
            get_commands = [
                call.args[1]
                for call in send_command.call_args_list
                if call.args[1].startswith("conf get ")
            ]
            self.assertEqual(
                ["conf get endpoint", "conf get thingname"],
                get_commands,
            )
            self.assertFalse(summary["pem_readback_performed"])
            self.assertEqual(
                "delegated_to_bootloader_tls_and_ota_signature",
                summary["pem_verification"],
            )
            format_call = next(
                call
                for call in send_command.call_args_list
                if call.args[1] == "format"
            )
            self.assertEqual(
                (b"Format OK !",),
                format_call.kwargs["success_tokens"],
            )


class OtaTransactionContractTests(unittest.TestCase):
    def test_requires_exact_raw_rsu_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rsu = root / "bad.rsu"
            rsu.write_bytes(b"x")
            args = argparse.Namespace(
                raw_log=root / "raw.log",
                baseline_rsu=rsu,
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            with self.assertRaisesRegex(ValueError, "exactly 0xC0000"):
                transaction.run()

    def test_bootloader_fail_close_marker_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            with self.assertRaisesRegex(RuntimeError, "fail-close"):
                transaction._consume(b"Loading user code signer public key from LittleFS: not found; refusing to boot.\r\n")

    def test_uses_existing_ota_analyzer_for_tls_and_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            for line in (
                "Application version 0.1.0\r\n",
                "TLS handshake successful: version TLSv1.2\r\n",
                "Received OTA Job.\r\n",
                "Starting The Download.\r\n",
                "Received file block\r\n",
                "Close file event Received\r\n",
                "Activate Image event Received\r\n",
                "Application version 0.1.1\r\n",
                "TLS handshake successful: version TLSv1.2\r\n",
                "New image has higher version than current image, accepted!\r\n",
                "Accepted and committed final image.\r\n",
            ):
                transaction._consume(line.encode("ascii"))
            self.assertTrue(transaction.ota.has_marker("image_committed"))
            self.assertIn("TLSv1.2", transaction.ota.tls_versions_seen)


if __name__ == "__main__":
    unittest.main()

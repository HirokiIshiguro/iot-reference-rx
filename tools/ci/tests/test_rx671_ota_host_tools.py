from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import re
import subprocess
import tempfile
import threading
import time
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
        self.input_reset_count = 0

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
        self.input_reset_count += 1

    def reset_output_buffer(self):
        pass

    def close(self):
        self.closed = True


class ThreadedFakeSerial:
    def __init__(
        self,
        *,
        timeout: float = 0.01,
        receive_capacity: int | None = None,
    ):
        self.timeout = timeout
        self.receive_capacity = receive_capacity
        self._condition = threading.Condition()
        self._responses = bytearray()
        self._failure = None
        self.writes = []
        self.closed = False
        self.input_reset_count = 0
        self.output_reset_count = 0
        self.dropped_bytes = 0

    @property
    def in_waiting(self):
        with self._condition:
            return len(self._responses)

    def feed(self, payload: bytes):
        with self._condition:
            accepted = payload
            if self.receive_capacity is not None:
                available = max(self.receive_capacity - len(self._responses), 0)
                accepted = payload[:available]
                self.dropped_bytes += len(payload) - len(accepted)
            self._responses.extend(accepted)
            self._condition.notify_all()

    def fail(self, error: BaseException):
        with self._condition:
            self._failure = error
            self._condition.notify_all()

    def read(self, size):
        deadline = time.monotonic() + self.timeout
        with self._condition:
            while not self._responses and self._failure is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return b""
                self._condition.wait(remaining)
            if self._failure is not None:
                error = self._failure
                self._failure = None
                raise error
            result = bytes(self._responses[:size])
            del self._responses[:size]
            return result

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        with self._condition:
            self._responses.clear()
            self.input_reset_count += 1

    def reset_output_buffer(self):
        self.output_reset_count += 1

    def close(self):
        self.closed = True


class GatedEmptyReadSerial(ThreadedFakeSerial):
    """Return one decided-empty read after the test releases its gate."""

    def __init__(self):
        super().__init__(timeout=0.001)
        self.empty_read_ready = threading.Event()
        self.release_empty_read = threading.Event()

    def read(self, size):
        deadline = time.monotonic() + self.timeout
        with self._condition:
            while not self._responses and self._failure is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            if self._failure is not None:
                error = self._failure
                self._failure = None
                raise error
            if self._responses:
                result = bytes(self._responses[:size])
                del self._responses[:size]
                return result

        self.empty_read_ready.set()
        if not self.release_empty_read.wait(2.0):
            raise TimeoutError("test did not release the gated empty read")
        return b""


class BufferedSerialReaderTests(unittest.TestCase):
    @staticmethod
    def _wait_for(predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        raise AssertionError("timed out waiting for serial reader state")

    def test_reader_keeps_192_block_burst_while_consumer_is_stalled(self):
        serial = ThreadedFakeSerial(receive_capacity=2048)
        reader = host.BufferedSerialReader(serial)
        payload = b"".join(
            (
                f"{block:03d} Downloaded block {block} of 192. "
                f"{'x' * 64}\r\n"
            ).encode("ascii")
            for block in range(192)
        ) + b"partial\x00tail"
        reader.start()

        def produce():
            for offset in range(0, len(payload), 128):
                serial.feed(payload[offset : offset + 128])
                time.sleep(0.002)

        producer = threading.Thread(target=produce)
        producer.start()
        # Model the synchronous analyzer/logger pause seen in job #64216.  The
        # consumer does not call read while the dedicated reader keeps draining.
        time.sleep(2.2)
        producer.join()
        self._wait_for(lambda: reader.stats()["reader_bytes"] == len(payload))
        self.assertGreater(len(payload), 12 * 1024)
        self.assertEqual(len(payload), reader.in_waiting)
        self.assertEqual(len(payload), reader.stats()["max_buffered_bytes"])

        captured = bytearray()
        while reader.in_waiting:
            captured.extend(reader.read(reader.in_waiting))
        reader.stop_after_quiet(quiet_seconds=0.02)
        reader.close()

        self.assertEqual(payload, bytes(captured))
        self.assertEqual(0, serial.dropped_bytes)
        self.assertEqual(192, captured.count(b"Downloaded block "))
        stats = reader.stats()
        self.assertEqual(len(payload), stats["reader_bytes"])
        self.assertEqual(len(payload), stats["consumer_bytes"])
        self.assertGreater(stats["max_buffered_bytes"], 0)
        self.assertFalse(stats["buffer_overflowed"])
        self.assertTrue(stats["all_reader_bytes_accounted"])
        self.assertTrue(stats["reader_thread_stopped"])
        self.assertIsNotNone(stats["last_capture_wall_utc"])
        self.assertIsNotNone(stats["last_capture_monotonic_seconds"])

    def test_quiet_shutdown_keeps_tail_arriving_after_success_marker(self):
        serial = ThreadedFakeSerial()
        reader = host.BufferedSerialReader(serial)
        reader.start()
        serial.feed(b"OTA Completed successfully!\r\n")
        self._wait_for(lambda: reader.stats()["reader_bytes"] > 0)

        def late_tail():
            time.sleep(0.05)
            serial.feed(b"late UART tail\r\n")

        producer = threading.Thread(target=late_tail)
        producer.start()
        reader.stop_after_quiet(quiet_seconds=0.1)
        producer.join()

        captured = reader.read(reader.in_waiting)
        reader.close()
        self.assertIn(b"OTA Completed successfully!", captured)
        self.assertIn(b"late UART tail", captured)
        self.assertTrue(reader.stats()["all_reader_bytes_accounted"])

    def test_stop_finally_drains_bytes_arriving_after_last_thread_read(self):
        serial = GatedEmptyReadSerial()
        reader = host.BufferedSerialReader(serial)
        reader.start()
        self.assertTrue(serial.empty_read_ready.wait(1.0))

        stop_error = []

        def stop_reader():
            try:
                reader.stop()
            except Exception as exc:
                stop_error.append(exc)

        stopper = threading.Thread(target=stop_reader)
        stopper.start()
        self._wait_for(reader._stop.is_set)
        tail = b"pre-cutoff physical tail\r\n"
        serial.feed(tail)
        serial.release_empty_read.set()
        stopper.join(2.0)

        self.assertFalse(stopper.is_alive())
        self.assertEqual([], stop_error)
        self.assertEqual(tail, reader.read(reader.in_waiting))
        reader.close()
        stats = reader.stats()
        self.assertEqual(len(tail), stats["physical_pending_at_cutoff"])
        self.assertEqual(len(tail), stats["physical_final_drain_bytes"])
        self.assertEqual(len(tail), stats["reader_bytes"])
        self.assertEqual(len(tail), stats["consumer_bytes"])
        self.assertEqual(0, stats["buffered_bytes"])
        self.assertTrue(stats["all_reader_bytes_accounted"])
        self.assertIsNotNone(stats["capture_cutoff_wall_utc"])

    def test_input_reset_discards_kernel_and_host_buffers_atomically(self):
        serial = ThreadedFakeSerial()
        reader = host.BufferedSerialReader(serial)
        reader.start()
        serial.feed(b"before-reset")
        self._wait_for(lambda: reader.stats()["reader_bytes"] == 12)

        reader.reset_input_buffer()
        serial.feed(b"after-reset")
        self._wait_for(lambda: reader.in_waiting == 11)
        self.assertEqual(b"after-reset", reader.read(11))
        reader.close()

        stats = reader.stats()
        self.assertEqual(1, stats["input_resets"])
        self.assertEqual(12, stats["discarded_buffered_bytes"])
        self.assertEqual(1, serial.input_reset_count)

    def test_reader_failure_is_fail_closed_and_closes_serial(self):
        serial = ThreadedFakeSerial()
        reader = host.BufferedSerialReader(serial)
        reader.start()
        serial.fail(OSError("simulated FTDI failure"))
        self._wait_for(lambda: reader.stats()["reader_failed"])

        with self.assertRaisesRegex(RuntimeError, "UART reader failed") as raised:
            reader.close()
        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertTrue(serial.closed)

    def test_buffer_overflow_is_explicit_failure_not_silent_drop(self):
        serial = ThreadedFakeSerial()
        reader = host.BufferedSerialReader(serial, max_buffer_bytes=8)
        reader.start()
        serial.feed(b"0123456789")
        self._wait_for(lambda: reader.stats()["reader_failed"])

        with self.assertRaisesRegex(RuntimeError, "UART reader failed") as raised:
            reader.close()
        self.assertIsInstance(raised.exception.__cause__, BufferError)
        stats = reader.stats()
        self.assertTrue(stats["buffer_overflowed"])
        self.assertGreater(stats["overflow_bytes"], 0)
        self.assertTrue(stats["all_reader_bytes_accounted"])

    def test_failure_path_preserves_primary_transaction_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rsu = root / "baseline.rsu"
            rsu.write_bytes(b"\x00" * ota_test.RSU_SIZE)
            args = argparse.Namespace(
                raw_log=root / "raw.log",
                baseline_rsu=rsu,
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                rfp_cli="rfp-cli",
                rfp_device="RX671",
                rfp_tool="e2l:test",
                rfp_interface="fine",
                rfp_speed="500K",
                rfp_auth_id="unit-test-auth-id",
                port="fake",
                baud=ota_test.DEFAULT_BAUD,
                boot_timeout=0.01,
                transfer_timeout=0.01,
                install_timeout=0.01,
                application_timeout=0.01,
                ota_timeout=0.01,
                startup_reset_retries=0,
                chunk_size=4096,
                inter_chunk_delay=0.0,
                min_capacity_heap_bytes=16384,
                min_capacity_network_buffers=4,
                expected_whd_buffer_count=8,
            )
            serial = ThreadedFakeSerial()
            transaction = ota_test.Rx671OtaTransaction(args)
            with mock.patch.object(
                ota_test,
                "open_serial",
                return_value=serial,
            ), mock.patch.object(
                ota_test,
                "run_checked",
                side_effect=RuntimeError("primary RFP failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "primary RFP failure"):
                    transaction.run()

            self.assertTrue(serial.closed)
            self.assertIsNotNone(transaction.uart_capture)
            self.assertTrue(transaction.uart_capture["reader_thread_stopped"])

    def test_success_path_stops_continuous_uart_then_drains_reader_queue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rsu = root / "baseline.rsu"
            rsu.write_bytes(b"\x00" * ota_test.RSU_SIZE)
            args = argparse.Namespace(
                raw_log=root / "raw.log",
                baseline_rsu=rsu,
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.3",
                rfp_cli="rfp-cli",
                rfp_device="RX671",
                rfp_tool="e2l:test",
                rfp_interface="fine",
                rfp_speed="500K",
                rfp_auth_id="unit-test-auth-id",
                port="fake",
                baud=ota_test.DEFAULT_BAUD,
                boot_timeout=0.01,
                transfer_timeout=0.01,
                install_timeout=0.01,
                application_timeout=0.01,
                ota_timeout=0.01,
                startup_reset_retries=0,
                chunk_size=4096,
                inter_chunk_delay=0.0,
                min_capacity_heap_bytes=16384,
                min_capacity_network_buffers=4,
                expected_whd_buffer_count=8,
            )
            serial = ThreadedFakeSerial()
            transaction = ota_test.Rx671OtaTransaction(args)
            transaction.boot_hits = {
                name: 1 for name in transaction.boot_hits
            }
            producer_stop = threading.Event()
            producer = None

            def successful_body(serial_port, _rfp):
                nonlocal producer

                def emit_continuously():
                    while not producer_stop.is_set():
                        serial.feed(b"alive tick after success\r\n")
                        time.sleep(0.001)

                producer = threading.Thread(target=emit_continuously)
                producer.start()
                self._wait_for(
                    lambda: serial_port.stats()["reader_bytes"] > 0
                )

            with mock.patch.object(
                ota_test,
                "open_serial",
                return_value=serial,
            ), mock.patch.object(
                ota_test,
                "run_checked",
            ), mock.patch.object(
                transaction,
                "wait_for",
            ), mock.patch.object(
                transaction,
                "stream_baseline_rsu",
                return_value=(ota_test.RSU_SIZE, "0" * 64),
            ), mock.patch.object(
                transaction,
                "wait_for_application_ready",
                side_effect=successful_body,
            ), mock.patch.object(
                transaction,
                "_runtime_success_ready",
                return_value=True,
            ), mock.patch.object(
                transaction,
                "_baseline_tls_before_activate",
                return_value=True,
            ), mock.patch.object(
                transaction,
                "_candidate_tls_after_activate",
                return_value=True,
            ), mock.patch.object(
                transaction,
                "_capacity_proof",
                return_value={"success": True},
            ), mock.patch.object(
                transaction.ota,
                "is_success",
                return_value=True,
            ), mock.patch.object(
                transaction.ota,
                "has_marker",
                return_value=True,
            ):
                started = time.monotonic()
                try:
                    summary = transaction.run()
                finally:
                    producer_stop.set()
                    if producer is not None:
                        producer.join(2.0)

            self.assertTrue(summary["success"])
            self.assertLess(time.monotonic() - started, 1.0)
            self.assertTrue(serial.closed)
            capture = transaction.uart_capture
            self.assertTrue(capture["reader_thread_stopped"])
            self.assertFalse(capture["reader_failed"])
            self.assertEqual(0, capture["buffered_bytes"])
            self.assertEqual(capture["reader_bytes"], capture["consumer_bytes"])
            self.assertTrue(capture["all_reader_bytes_accounted"])
            self.assertIsNotNone(capture["capture_cutoff_wall_utc"])


class RfpContractTests(unittest.TestCase):
    def test_program_preserves_data_flash(self):
        command = host.RfpConfig().program_command(Path("/tmp/boot.mot"), leave_reset=True)
        self.assertIn("-p", command)
        self.assertIn("-v", command)
        self.assertNotIn("-reset", command)
        self.assertNotIn("-run", command)
        self.assertNotIn("-erase-chip", command)
        self.assertEqual("e2l:OBE110024", command[command.index("-t") + 1])

    def test_install_area_erase_uses_exact_ranges_and_preserves_boundaries(self):
        command = host.RfpConfig().erase_ota_install_areas_command()
        self.assertIn("-erase", command)
        self.assertEqual(
            ["FFE00000,FFEBFFFF", "FFF00000,FFFBFFFF"],
            [
                command[index + 1]
                for index, token in enumerate(command)
                if token == "-range"
            ],
        )
        self.assertNotIn("-erase-chip", command)
        self.assertNotIn("-run", command)
        self.assertNotIn("FFEC0000,FFEFFFFF", command)
        self.assertNotIn("FFFC0000,FFFFFFFF", command)

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

    def test_mutable_ascii_command_is_sent_without_string_conversion(self):
        command = bytearray(b"conf sethex wifipass 0011")
        serial = FakeSerial()
        host.send_ascii_bytes_command(
            serial,
            command,
            timeout=1,
            char_delay=0,
        )
        self.assertEqual(bytes(command) + b"\r\n", b"".join(serial.writes))

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
    def test_wifi_environment_validation_uses_utf8_octet_limits(self):
        ssid, passphrase = provision._wifi_credentials_from_environment(
            "SSID",
            "PASS",
            {"SSID": "あ" * 10, "PASS": "password"},
        )
        self.assertEqual(30, len(ssid))
        self.assertEqual(8, len(passphrase))
        with self.assertRaisesRegex(ValueError, "1..32"):
            provision._wifi_credentials_from_environment(
                "SSID",
                "PASS",
                {"SSID": "あ" * 11, "PASS": "password"},
            )
        with self.assertRaisesRegex(ValueError, "8..63"):
            provision._wifi_credentials_from_environment(
                "SSID",
                "PASS",
                {"SSID": "ssid", "PASS": "short"},
            )

    def test_invalid_wifi_bytearrays_are_zeroized_before_error(self):
        zeroized = []

        def capture(value):
            zeroized.append(bytes(value))
            for index in range(len(value)):
                value[index] = 0

        with mock.patch.object(provision, "_zeroize", side_effect=capture):
            with self.assertRaisesRegex(ValueError, "1..32"):
                provision._wifi_credentials_from_environment(
                    "SSID",
                    "PASS",
                    {"SSID": "x" * 33, "PASS": "password"},
                )
        self.assertEqual([b"x" * 33, b"password"], zeroized)

    def test_wifi_hex_command_buffers_are_zeroized_after_send(self):
        command_references = []

        def capture(_serial, command, **_kwargs):
            command_references.append(command)
            return b"OK"

        with mock.patch.dict(
            provision.os.environ,
            {"SSID": "access-point", "PASS": "secret-passphrase"},
        ), mock.patch.object(
            provision,
            "send_ascii_bytes_command",
            side_effect=capture,
        ):
            provision._set_wifi_credentials(
                object(),
                ssid_variable="SSID",
                passphrase_variable="PASS",
                char_delay=0,
                timeout=1,
            )

        self.assertEqual(2, len(command_references))
        self.assertTrue(all(not any(command) for command in command_references))
        self.assertNotIn(".hex()", inspect.getsource(provision._set_wifi_credentials))

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

    def test_provision_erases_only_install_areas_between_images(self):
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
                wifi_ssid_env="TEST_WIFI_SSID",
                wifi_passphrase_env="TEST_WIFI_PASSPHRASE",
            )
            serial = FakeSerial()
            commands = []
            wifi_commands = []
            wifi_ssid = "test-access-point"
            wifi_passphrase = "do-not-log-this-passphrase"

            def capture(command, **_kwargs):
                commands.append(command)
                return mock.Mock(returncode=0)

            def capture_wifi(_serial, command, **_kwargs):
                wifi_commands.append(bytes(command))
                return b"OK"

            with mock.patch.dict(
                provision.os.environ,
                {
                    "TEST_WIFI_SSID": wifi_ssid,
                    "TEST_WIFI_PASSPHRASE": wifi_passphrase,
                },
            ), mock.patch.object(
                provision, "run_checked", side_effect=capture
            ) as run_command, mock.patch.object(
                provision, "open_serial", return_value=serial
            ), mock.patch.object(provision, "enter_cli"), mock.patch.object(
                provision, "send_ascii_command", return_value=b"OK"
            ) as send_command, mock.patch.object(
                provision,
                "send_ascii_bytes_command",
                side_effect=capture_wifi,
            ):
                summary = provision.provision(args)
            self.assertTrue(summary["success"])
            self.assertEqual(4, len(commands))
            self.assertTrue(all("-erase-chip" not in command for command in commands))
            self.assertIn("-p", commands[0])
            self.assertIn("-run", commands[1])
            self.assertEqual(
                ["FFE00000,FFEBFFFF", "FFF00000,FFFBFFFF"],
                [
                    commands[2][index + 1]
                    for index, token in enumerate(commands[2])
                    if token == "-range"
                ],
            )
            self.assertIn("-erase", commands[2])
            self.assertIn("-p", commands[3])
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
            self.assertIn(
                b"conf sethex wifissid " + wifi_ssid.encode("utf-8").hex().encode(),
                wifi_commands,
            )
            self.assertIn(
                b"conf sethex wifipass "
                + wifi_passphrase.encode("utf-8").hex().encode(),
                wifi_commands,
            )
            self.assertFalse(
                any(wifi_passphrase.encode() in command for command in wifi_commands)
            )
            self.assertFalse(
                any(
                    call.args[1] == "conf get wifipass"
                    for call in send_command.call_args_list
                )
            )
            self.assertFalse(summary["pem_readback_performed"])
            self.assertFalse(summary["wifi_passphrase_readback_performed"])
            self.assertEqual(
                "environment_to_sci6_to_littlefs",
                summary["wifi_credentials_source"],
            )
            self.assertEqual(
                "delegated_to_bootloader_tls_and_ota_signature",
                summary["pem_verification"],
            )
            self.assertTrue(summary["ota_install_areas_erased_after_provisioning"])
            self.assertTrue(summary["data_flash_preserved_during_rfp_operations"])
            self.assertEqual(
                ["0xFFE00000-0xFFEBFFFF", "0xFFF00000-0xFFFBFFFF"],
                summary["ota_install_area_erase_ranges"],
            )
            self.assertIn(
                "ota_install_areas_erased_after_provisioning",
                summary["completed_steps"],
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
    def test_capacity_cli_defaults_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rsu = root / "baseline.rsu"
            rsu.write_bytes(b"x")
            args = ota_test.parse_args(
                [
                    "--baseline-rsu",
                    str(rsu),
                    "--raw-log",
                    str(root / "raw.log"),
                    "--summary-json",
                    str(root / "summary.json"),
                    "--junit-output",
                    str(root / "junit.xml"),
                ]
            )
            self.assertEqual(16384, args.min_capacity_heap_bytes)
            self.assertEqual(4, args.min_capacity_network_buffers)
            self.assertEqual(8, args.expected_whd_buffer_count)
            self.assertEqual(2, args.startup_reset_retries)

    def test_startup_retry_resets_whole_mcu_and_then_accepts_application(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                application_timeout=0.1,
                startup_reset_retries=2,
            )
            serial = FakeSerial(
                b"RX671 OTA startup retry: WHD bring-up failed\r\n"
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            rfp = host.RfpConfig(auth_id="unit-test-auth-id")

            def release_after_reset(*_args, **_kwargs):
                serial.responses.extend(
                    b"RX671 OTA startup ready: WHD and DHCP lease verified\r\n"
                )

            with mock.patch.object(
                ota_test, "run_checked", side_effect=release_after_reset
            ) as reset:
                transaction.wait_for_application_ready(serial, rfp)

            self.assertEqual(1, reset.call_count)
            self.assertEqual(1, serial.input_reset_count)
            self.assertEqual(
                [
                    {
                        "reset_number": 1,
                        "reason": "whd_bringup_failed",
                        "phase": "baseline_startup",
                    }
                ],
                transaction.startup_reset_events,
            )

    def test_startup_retry_is_bounded_and_fails_after_exhaustion(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                application_timeout=0.1,
                startup_reset_retries=2,
            )
            retry_marker = b"RX671 OTA startup retry: DHCP lease not acquired\r\n"
            serial = FakeSerial(retry_marker)
            transaction = ota_test.Rx671OtaTransaction(args)

            def repeat_failure(*_args, **_kwargs):
                serial.responses.extend(retry_marker)

            with mock.patch.object(
                ota_test, "run_checked", side_effect=repeat_failure
            ) as reset:
                with self.assertRaisesRegex(RuntimeError, "retries exhausted"):
                    transaction.wait_for_application_ready(
                        serial, host.RfpConfig(auth_id="unit-test-auth-id")
                    )

            self.assertEqual(2, reset.call_count)
            self.assertEqual(2, serial.input_reset_count)
            self.assertEqual(2, len(transaction.startup_reset_events))

    def test_candidate_startup_retry_uses_the_same_global_reset_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                application_timeout=0.1,
                startup_reset_retries=2,
            )
            serial = FakeSerial(b"")
            transaction = ota_test.Rx671OtaTransaction(args)
            transaction._consume(
                b"RX671 OTA startup retry: WHD bring-up failed\r\n"
            )

            with mock.patch.object(ota_test, "run_checked") as reset:
                reason = transaction._startup_retry_reason()
                transaction._perform_startup_reset(
                    serial,
                    host.RfpConfig(auth_id="unit-test-auth-id"),
                    reason=reason,
                    phase="ota_observation",
                )

            self.assertEqual(1, reset.call_count)
            self.assertEqual("ota_observation", transaction.startup_reset_events[0]["phase"])
            self.assertEqual("", transaction.text)

    def test_application_version_alone_is_not_startup_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                application_timeout=0.01,
                startup_reset_retries=2,
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            serial = FakeSerial(b"Application version 0.1.0\r\n")

            with self.assertRaisesRegex(TimeoutError, "startup ready"):
                transaction.wait_for_application_ready(
                    serial, host.RfpConfig(auth_id="unit-test-auth-id")
                )

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

    def test_baseline_stream_waits_for_each_flash_block_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rsu = root / "baseline.rsu"
            payload = bytes(range(256)) * 256
            self.assertEqual(2 * ota_test.BOOTLOADER_FLASH_BLOCK_SIZE, len(payload))
            rsu.write_bytes(payload)
            args = argparse.Namespace(
                raw_log=root / "raw.log",
                baseline_rsu=rsu,
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                transfer_timeout=1.0,
                chunk_size=4096,
                inter_chunk_delay=0.0,
            )
            serial = FakeSerial(b"")
            transaction = ota_test.Rx671OtaTransaction(args)
            acknowledged = []

            def acknowledge(_serial, marker, timeout):
                expected_sent = (
                    len(acknowledged) + 1
                ) * ota_test.BOOTLOADER_FLASH_BLOCK_SIZE
                self.assertEqual(expected_sent, sum(map(len, serial.writes)))
                self.assertGreater(timeout, 0)
                acknowledged.append(marker)

            with mock.patch.object(
                transaction, "wait_for", side_effect=acknowledge
            ):
                sent, digest = transaction.stream_baseline_rsu(serial)

            self.assertEqual(len(payload), sent)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
            self.assertEqual(["(32/64KB).", "(64/64KB)."], acknowledged)
            self.assertTrue(all(len(chunk) <= 4096 for chunk in serial.writes))

    def test_baseline_stream_does_not_send_next_block_without_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rsu = root / "baseline.rsu"
            rsu.write_bytes(b"x" * (2 * ota_test.BOOTLOADER_FLASH_BLOCK_SIZE))
            args = argparse.Namespace(
                raw_log=root / "raw.log",
                baseline_rsu=rsu,
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                transfer_timeout=1.0,
                chunk_size=4096,
                inter_chunk_delay=0.0,
            )
            serial = FakeSerial(b"")
            transaction = ota_test.Rx671OtaTransaction(args)

            with mock.patch.object(
                transaction,
                "wait_for",
                side_effect=TimeoutError("progress missing"),
            ):
                with self.assertRaisesRegex(TimeoutError, "progress missing"):
                    transaction.stream_baseline_rsu(serial)

            self.assertEqual(
                ota_test.BOOTLOADER_FLASH_BLOCK_SIZE,
                sum(map(len, serial.writes)),
            )

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
                transaction._consume(
                    b"Loading user code signer public key from LittleFS: "
                    b"not found; refusing to boot.\r\n"
                )

    def test_runtime_fatal_marker_raises_without_waiting_for_ota_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            with self.assertRaisesRegex(RuntimeError, "fail-close"):
                transaction._consume(
                    b"RX671 OTA fatal: FreeRTOS malloc failed\r\n"
                )

    def test_littlefs_debug_can_split_key_found_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            transaction._consume(
                b"Loading user code signer public key from LittleFS: "
                b"lfs.c:4558:debug: Found older minor version\r\n"
                b"found.\r\n"
            )
            self.assertEqual(1, transaction.boot_hits["key_load_started"])
            self.assertEqual(1, transaction.boot_hits["key_found"])

    def test_acceptance_and_success_report_do_not_require_optional_pal_commit_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                min_capacity_heap_bytes=16384,
                min_capacity_network_buffers=4,
                expected_whd_buffer_count=8,
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            for line in (
                "Application version 0.1.0\r\n",
                "TLS handshake successful: version TLSv1.2\r\n",
                "Received OTA Job.\r\n",
                "Starting The Download.\r\n",
                "Downloaded block 191 of 192.\r\n",
                "Close file event Received\r\n",
                "Activate Image event Received\r\n",
                "Application version 0.1.1\r\n",
                "TLS handshake successful: version TLSv1.2\r\n",
                "[RX671_OTA_CAPACITY] minheap=25576 minnbuf=15 whdmax=1 "
                "tempfail=0 permfail=0 waitloop=0\r\n",
                "New image has higher version than current image, accepted!\r\n",
                "---OTA Completed successfully!---\r\n",
            ):
                transaction._consume(line.encode("ascii"))

            self.assertTrue(transaction.ota.is_success())
            self.assertTrue(transaction._runtime_success_ready())
            self.assertTrue(transaction.ota.has_marker("image_accepted"))
            self.assertTrue(transaction.ota.has_marker("ota_completed"))
            self.assertFalse(transaction.ota.has_marker("image_committed"))
            self.assertIn("TLSv1.2", transaction.ota.tls_versions_seen)

    def test_tls13_is_accepted_for_both_ota_boots(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.3",
                min_capacity_heap_bytes=16384,
                min_capacity_network_buffers=4,
                expected_whd_buffer_count=8,
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            for line in (
                "Application version 0.1.0\r\n",
                "TLS handshake successful: version TLSv1.3\r\n",
                "Received OTA Job.\r\n",
                "Starting The Download.\r\n",
                "Downloaded block 191 of 192.\r\n",
                "Close file event Received\r\n",
                "Activate Image event Received\r\n",
                "Application version 0.1.1\r\n",
                "TLS handshake successful: version TLSv1.3\r\n",
                "[RX671_OTA_CAPACITY] minheap=25576 minnbuf=15 whdmax=1 "
                "tempfail=0 permfail=0 waitloop=0\r\n",
                "New image has higher version than current image, accepted!\r\n",
                "---OTA Completed successfully!---\r\n",
            ):
                transaction._consume(line.encode("ascii"))

            self.assertTrue(transaction.ota.is_success())
            self.assertTrue(transaction._runtime_success_ready())
            self.assertTrue(transaction._baseline_tls_before_activate())
            self.assertTrue(transaction._candidate_tls_after_activate())
            self.assertEqual(["TLSv1.3"], transaction.ota.tls_versions_seen)

    def test_marker_loss_uses_ordered_candidate_as_phase_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.3",
                min_capacity_heap_bytes=16384,
                min_capacity_network_buffers=4,
                expected_whd_buffer_count=8,
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            for line in (
                "Application version 0.1.0\r\n",
                "TLS handshake successful: version TLSv1.3\r\n",
                "Received OTA Job.\r\n",
                "Starting The Download.\r\n",
                "Downloaded block 191 of 192.\r\n",
                "Application version 0.1.1\r\n",
                "TLS handshake successful: version TLSv1.3\r\n",
                "[RX671_OTA_CAPACITY] minheap=22424 minnbuf=13 whdmax=1 "
                "tempfail=0 permfail=0 waitloop=0\r\n",
                "New image has higher version than current image, accepted!\r\n",
                "---OTA Completed successfully!---\r\n",
            ):
                transaction._consume(line.encode("ascii"))

            self.assertEqual(
                "ordered_candidate_acceptance_and_completion",
                transaction.ota.success_proof(),
            )
            self.assertFalse(transaction.ota.has_marker("close_file"))
            self.assertFalse(transaction.ota.has_marker("activate_image"))
            self.assertFalse(transaction.ota.has_marker("software_reset"))
            self.assertEqual(
                transaction.ota.version_events[1]["line_number"],
                transaction._ota_phase_anchor_line(),
            )
            self.assertTrue(transaction._baseline_tls_before_activate())
            self.assertTrue(transaction._candidate_tls_after_activate())
            self.assertTrue(transaction._capacity_proof()["success"])
            self.assertTrue(transaction._runtime_success_ready())

    def test_marker_loss_phase_anchor_remains_fail_closed(self):
        base_lines = (
            "Application version 0.1.0\r\n",
            "TLS handshake successful: version TLSv1.3\r\n",
            "Received OTA Job.\r\n",
            "Starting The Download.\r\n",
            "Downloaded block 191 of 192.\r\n",
            "Application version 0.1.1\r\n",
            "TLS handshake successful: version TLSv1.3\r\n",
            "[RX671_OTA_CAPACITY] minheap=22424 minnbuf=13 whdmax=1 "
            "tempfail=0 permfail=0 waitloop=0\r\n",
            "New image has higher version than current image, accepted!\r\n",
            "---OTA Completed successfully!---\r\n",
        )
        rejected_variants = {
            "missing baseline TLS": base_lines[:1] + base_lines[2:],
            "missing candidate TLS": base_lines[:6] + base_lines[7:],
            "wrong candidate TLS": (
                base_lines[:6]
                + ("TLS handshake successful: version TLSv1.2\r\n",)
                + base_lines[7:]
            ),
            "capacity before candidate": (
                base_lines[:5]
                + (base_lines[7],)
                + base_lines[5:7]
                + base_lines[8:]
            ),
            "missing capacity": base_lines[:7] + base_lines[8:],
            "capacity below threshold": (
                base_lines[:7]
                + (
                    "[RX671_OTA_CAPACITY] minheap=16383 minnbuf=3 whdmax=8 "
                    "tempfail=1 permfail=1 waitloop=1\r\n",
                )
                + base_lines[8:]
            ),
            "missing acceptance": base_lines[:8] + base_lines[9:],
        }

        for case, lines in rejected_variants.items():
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as temporary:
                    args = argparse.Namespace(
                        raw_log=Path(temporary) / "raw.log",
                        baseline_version="0.1.0",
                        candidate_version="0.1.1",
                        require_tls_version="TLSv1.3",
                        min_capacity_heap_bytes=16384,
                        min_capacity_network_buffers=4,
                        expected_whd_buffer_count=8,
                    )
                    transaction = ota_test.Rx671OtaTransaction(args)
                    for line in lines:
                        transaction._consume(line.encode("ascii"))
                    self.assertFalse(transaction._runtime_success_ready())

    def test_tls13_candidate_handshake_cannot_replace_baseline_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.3",
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            transaction._consume(
                b"Application version 0.1.0\r\n"
                b"Activate Image event Received\r\n"
                b"Application version 0.1.1\r\n"
                b"TLS handshake successful: version TLSv1.3\r\n"
            )
            self.assertFalse(transaction._baseline_tls_before_activate())
            self.assertTrue(transaction._candidate_tls_after_activate())

    def test_requires_capacity_headroom_after_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                min_capacity_heap_bytes=16384,
                min_capacity_network_buffers=4,
                expected_whd_buffer_count=8,
            )
            transaction = ota_test.Rx671OtaTransaction(args)
            transaction._consume(b"Activate Image event Received\r\n")
            transaction._consume(
                b"[RX671_OTA_CAPACITY] minheap=16384 minnbuf=4 whdmax=7 "
                b"tempfail=0 permfail=0 waitloop=0\r\n"
            )
            proof = transaction._capacity_proof()
            self.assertTrue(proof["success"])
            self.assertEqual(16384, proof["metrics"]["min_heap_bytes"])
            self.assertEqual(8, proof["thresholds"]["whd_buffer_count"])

    def test_rejects_missing_or_exhausted_capacity_headroom(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(
                raw_log=Path(temporary) / "raw.log",
                baseline_version="0.1.0",
                candidate_version="0.1.1",
                require_tls_version="TLSv1.2",
                min_capacity_heap_bytes=16384,
                min_capacity_network_buffers=4,
                expected_whd_buffer_count=8,
            )
            missing = ota_test.Rx671OtaTransaction(args)
            missing._consume(b"Activate Image event Received\r\n")
            self.assertFalse(missing._capacity_proof()["success"])

            exhausted = ota_test.Rx671OtaTransaction(args)
            exhausted._consume(b"Activate Image event Received\r\n")
            exhausted._consume(
                b"[RX671_OTA_CAPACITY] minheap=0 minnbuf=0 whdmax=8 "
                b"tempfail=1 permfail=1 waitloop=1\r\n"
            )
            proof = exhausted._capacity_proof()
            self.assertFalse(proof["success"])
            self.assertFalse(proof["checks"]["minimum_heap_met"])
            self.assertFalse(proof["checks"]["minimum_network_buffers_met"])
            self.assertFalse(proof["checks"]["whd_pool_not_exhausted"])
            self.assertFalse(proof["checks"]["whd_temporary_failures_zero"])
            self.assertFalse(proof["checks"]["whd_permanent_failures_zero"])
            self.assertFalse(proof["checks"]["whd_wait_loops_zero"])


if __name__ == "__main__":
    unittest.main()

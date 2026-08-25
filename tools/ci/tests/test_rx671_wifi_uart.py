import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import patch

from tools.ci.test_rx671_wifi_uart import (
    IOCTL_MISMATCH_MARKER,
    MQTT_MARKERS,
    NETWORK_MARKERS,
    SmokeResult,
    evaluate_log,
    monitor_uart,
    required_markers,
    retryable_pre_network_failure,
    write_junit,
)


class EvaluateLogTests(unittest.TestCase):
    def test_network_markers_pass(self):
        text = "\r\n".join(NETWORK_MARKERS)
        missing, failures = evaluate_log(text, "network")
        self.assertEqual([], missing)
        self.assertEqual([], failures)

    def test_mqtt_requires_network_and_mqtt_markers(self):
        text = "\n".join(NETWORK_MARKERS + MQTT_MARKERS)
        missing, failures = evaluate_log(text, "mqtt")
        self.assertEqual([], missing)
        self.assertEqual([], failures)

    def test_mqtt_tls13_requires_negotiated_version_marker(self):
        text = "\n".join(NETWORK_MARKERS + MQTT_MARKERS)
        missing, failures = evaluate_log(text, "mqtt", "TLSv1.3")
        self.assertEqual(["AWS TLS version=TLSv1.3"], missing)
        self.assertEqual([], failures)

        missing, failures = evaluate_log(
            text + "\nAWS TLS version=TLSv1.3", "mqtt", "TLSv1.3"
        )
        self.assertEqual([], missing)
        self.assertEqual([], failures)

    def test_tls_version_requirement_rejects_network_mode(self):
        with self.assertRaises(ValueError):
            required_markers("network", "TLSv1.3")

    def test_nonzero_join_is_reported(self):
        missing, failures = evaluate_log("whd_wifi_join=00000005\r\n", "network")
        self.assertTrue(missing)
        self.assertEqual(["whd_wifi_join failed: 00000005"], failures)

    def test_nonzero_wifi_on_is_reported(self):
        missing, failures = evaluate_log("whd_wifi_on=060E0000\r\n", "network")
        self.assertTrue(missing)
        self.assertEqual(["whd_wifi_on failed: 060E0000"], failures)

    def test_f2_ioctl_mismatch_before_network_is_retryable(self):
        text = IOCTL_MISMATCH_MARKER + "\nwhd_wifi_on=060E0000"
        _, failures = evaluate_log(text, "network")
        self.assertTrue(retryable_pre_network_failure(text, failures))

    def test_f2_retry_is_fail_closed_without_causal_evidence(self):
        _, failures = evaluate_log("whd_wifi_on=060E0000", "network")
        self.assertFalse(
            retryable_pre_network_failure("whd_wifi_on=060E0000", failures)
        )

        text = "\n".join(
            (IOCTL_MISMATCH_MARKER, NETWORK_MARKERS[0], "whd_wifi_on=060E0000")
        )
        _, failures = evaluate_log(text, "network")
        self.assertFalse(retryable_pre_network_failure(text, failures))

    def test_nonzero_mqtt_status_is_reported(self):
        text = "\n".join(NETWORK_MARKERS + ("AWS MQTT smoke: network ready", "AWS TLS=0", "AWS MQTT=7"))
        missing, failures = evaluate_log(text, "mqtt")
        self.assertIn("AWS MQTT=0", missing)
        self.assertEqual(["AWS MQTT failed: 7"], failures)

    def test_required_markers_reject_unknown_mode(self):
        with self.assertRaises(ValueError):
            required_markers("unknown")


class JunitTests(unittest.TestCase):
    def test_failure_junit_contains_message_and_log(self):
        result = SmokeResult(False, "missing network", "uart output", 1.25)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.xml"
            write_junit(path, result, "network", "/dev/ttyUSB0", 921600)
            root = ET.parse(path).getroot()

        self.assertEqual("1", root.attrib["failures"])
        self.assertEqual("missing network", root.find("./testcase/failure").attrib["message"])
        self.assertEqual("uart output", root.findtext("./testcase/system-out"))

    def test_junit_records_bounded_recovery(self):
        result = SmokeResult(
            True,
            "all network milestones observed after 1 recovery reset",
            "uart output",
            1.25,
            attempts=2,
            recovery_reasons=("f2-ioctl-id-mismatch-before-network",),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.xml"
            write_junit(path, result, "network", "/dev/ttyUSB0", 921600)
            root = ET.parse(path).getroot()

        properties = {
            item.attrib["name"]: item.attrib["value"]
            for item in root.findall("./properties/property")
        }
        self.assertEqual("2", properties["startup_attempts"])
        self.assertEqual(
            "f2-ioctl-id-mismatch-before-network", properties["recovery_reasons"]
        )

    def test_junit_escapes_xml_1_0_invalid_characters(self):
        result = SmokeResult(
            False,
            "missing\x00network\ud800",
            "\x00\nuart\x01 output\udfff",
            1.25,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.xml"
            write_junit(path, result, "network", "/dev/tty\x08USB0", 921600)
            raw_xml = path.read_bytes()
            root = ET.parse(path).getroot()

        self.assertNotIn(b"\x00", raw_xml)
        self.assertEqual(
            "missing\\x00network\\uD800",
            root.find("./testcase/failure").attrib["message"],
        )
        self.assertEqual(
            "\\x00\nuart\\x01 output\\uDFFF",
            root.findtext("./testcase/system-out"),
        )
        properties = {
            item.attrib["name"]: item.attrib["value"]
            for item in root.findall("./properties/property")
        }
        self.assertEqual("/dev/tty\\x08USB0", properties["port"])


class MonitorTests(unittest.TestCase):
    def test_monitor_performs_one_whole_device_recovery(self):
        class FakeSerial:
            def __init__(self):
                self.attempt = -1
                self.sent = False

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def reset_input_buffer(self):
                self.attempt += 1
                self.sent = False

            def read(self, _size):
                if self.sent:
                    return b""
                self.sent = True
                if self.attempt == 0:
                    return (
                        IOCTL_MISMATCH_MARKER + "\nwhd_wifi_on=060E0000\n"
                    ).encode()
                return ("\n".join(NETWORK_MARKERS) + "\n").encode()

        fake_uart = FakeSerial()
        fake_serial_module = SimpleNamespace(
            Serial=lambda *_args, **_kwargs: fake_uart
        )
        reset_result = CompletedProcess("reset", 0, "reset ok\n", "")

        with patch.dict("sys.modules", {"serial": fake_serial_module}), patch(
            "tools.ci.test_rx671_wifi_uart.run_reset_command",
            return_value=reset_result,
        ) as reset_command:
            result = monitor_uart(
                port="COM1",
                baud=921600,
                timeout_seconds=0.1,
                mode="network",
                require_tls_version="",
                reset_command="reset",
                reset_timeout_seconds=1.0,
                startup_retries=1,
            )

        self.assertTrue(result.passed, result.message + "\n" + result.log)
        self.assertEqual(2, result.attempts)
        self.assertEqual(
            ("f2-ioctl-id-mismatch-before-network",), result.recovery_reasons
        )
        self.assertEqual(2, reset_command.call_count)


if __name__ == "__main__":
    unittest.main()

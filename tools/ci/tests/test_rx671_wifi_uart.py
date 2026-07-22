import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.ci.test_rx671_wifi_uart import (
    MQTT_MARKERS,
    NETWORK_MARKERS,
    SmokeResult,
    evaluate_log,
    required_markers,
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


if __name__ == "__main__":
    unittest.main()

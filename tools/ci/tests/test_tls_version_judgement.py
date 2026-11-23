"""Every observing tool passes only when it saw at least one TLS handshake and all of them used the required version.

For each tool: (a) only lines of the required version pass, (b) a line of another version fails,
(c) no version line fails.
"""
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # the tools import each other by module name
import bg96_bootloader_integration as bg96  # noqa: E402
import bg96_ota_monitor  # noqa: E402
import test_fleet_rx72n  # noqa: E402
import test_mqtt_rx72n  # noqa: E402
from tools.ci.test_rx671_wifi_uart import NETWORK_MARKERS, MQTT_MARKERS, evaluate_log
from tools.test_ota import OtaLogAnalyzer

LINE = "[MQTT] [INFO] (Network connection 1) TLS handshake successful: version {}"
VERSIONS = ("TLSv1.2", "TLSv1.3")


def other(version: str) -> str:
    return "TLSv1.3" if version == "TLSv1.2" else "TLSv1.2"


class Mqtt72nTests(unittest.TestCase):
    def test_judgement(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                judge = test_mqtt_rx72n.tls_requirement_ok
                self.assertTrue(judge(version, [version, version]))
                self.assertFalse(judge(version, [version, other(version)]))
                self.assertFalse(judge(version, [other(version)]))
                self.assertFalse(judge(version, []))


class FakePort:
    def __init__(self, chunks):
        self.chunks = [chunk.encode() for chunk in chunks]
        self.in_waiting = 0

    def read(self, _size):
        return self.chunks.pop(0) if self.chunks else b""


class Rx65nMqttTests(unittest.TestCase):
    def run_tool(self, version, handshakes):
        chunks = ["Start PubSub Demo Task\n"] + [LINE.format(v) + "\n" for v in handshakes] + \
                 ["Successfully sent QoS\n", "Successfully subscribed to topic\n"]
        with mock.patch.object(bg96, "write_serial_text"), mock.patch("sys.stdout", new_callable=io.StringIO):
            bg96.verify_app_mqtt(FakePort(chunks), 5, 5, True, version)

    def test_judgement(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.run_tool(version, [version])
                with self.assertRaises(RuntimeError):
                    self.run_tool(version, [other(version), version])    # the last line alone used to decide
                with self.assertRaises(RuntimeError):
                    self.run_tool(version, [version, other(version)])
                with self.assertRaises(RuntimeError):
                    self.run_tool(version, [])


class Rx671WifiTests(unittest.TestCase):
    def test_software_mqtt_mode(self):
        base = "\n".join(NETWORK_MARKERS + MQTT_MARKERS)
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(evaluate_log(base + f"\nAWS TLS version={version}", "mqtt", version), ([], []))
                missing, failures = evaluate_log(base + f"\nAWS TLS version={other(version)}", "mqtt", version)
                self.assertTrue(missing and failures)
                self.assertEqual(evaluate_log(base, "mqtt", version)[0], [f"AWS TLS version={version}"])

    def test_agent_mode(self):
        base = "\n".join(NETWORK_MARKERS + ("Successfully connected to MQTT broker.",
                                            "Request Job Document event Received"))
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(evaluate_log(base + "\n" + LINE.format(version), "mqtt-agent", version), ([], []))
                mixed = base + "\n" + LINE.format(version) + "\n" + LINE.format(other(version))
                self.assertTrue(evaluate_log(mixed, "mqtt-agent", version)[1])
                self.assertTrue(evaluate_log(base, "mqtt-agent", version)[0])


class FleetTests(unittest.TestCase):
    def test_judgement(self):
        judge = test_fleet_rx72n.tls_requirement_ok
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertTrue(judge(version, [version]))
                self.assertFalse(judge(version, [version, other(version)]))
                self.assertFalse(judge(version, []))
                self.assertFalse(judge(version, [version], 1, 2))   # RX671: claim and provisioned connections


class OtaTests(unittest.TestCase):
    def analyzer(self, version, handshakes):
        analyzer = OtaLogAnalyzer(expected_version="0.9.3", require_tls_version=version)
        for line in [LINE.format(v) for v in handshakes]:
            analyzer.consume_line(line, elapsed=1.0)
        return analyzer

    def test_judgement(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertTrue(self.analyzer(version, [version, version]).tls_requirement_ok())
                self.assertFalse(self.analyzer(version, [version, other(version)]).tls_requirement_ok())
                self.assertFalse(self.analyzer(version, []).tls_requirement_ok())

    def test_rx65n_monitor_judgement(self):
        def summary(*versions):
            return {"attempt": 1, "tls_versions_seen": list(versions)}
        for version in VERSIONS:
            with self.subTest(version=version):
                ok = bg96_ota_monitor.aggregate_summaries([summary(version)], "0.9.3", version)
                self.assertTrue(ok["tls_version_ok"])
                mixed = bg96_ota_monitor.aggregate_summaries([summary(version), summary(other(version))],
                                                             "0.9.3", version)
                self.assertFalse(mixed["tls_version_ok"])
                none = bg96_ota_monitor.aggregate_summaries([summary()], "0.9.3", version)
                self.assertFalse(none["tls_version_ok"])


if __name__ == "__main__":
    unittest.main()

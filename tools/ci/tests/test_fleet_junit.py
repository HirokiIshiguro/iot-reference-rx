from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools import test_fleet_rx72n


class FleetJunitTests(unittest.TestCase):
    def test_success_report(self) -> None:
        summary = {
            "success": True,
            "results": {"registered": True},
            "errors": [],
            "thing_name": "rx671-fleet-test",
            "certificate_id": "certificate-id",
            "require_tls_version": "",
            "tls_version_ok": True,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "junit.xml"
            test_fleet_rx72n.write_junit(output, "RX671 software Fleet", summary)
            root = ET.parse(output).getroot()

        self.assertEqual(root.attrib["failures"], "0")
        self.assertIsNone(root.find("testcase/failure"))

    def test_failure_report_lists_missing_markers(self) -> None:
        summary = {
            "success": False,
            "results": {"registered": False, "reconnected": True},
            "errors": ["RegisterThing rejected"],
            "tls_version_ok": True,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "junit.xml"
            test_fleet_rx72n.write_junit(output, "RX671 software Fleet", summary)
            root = ET.parse(output).getroot()

        failure = root.find("testcase/failure")
        self.assertEqual(root.attrib["failures"], "1")
        self.assertIsNotNone(failure)
        self.assertIn("registered", failure.text)
        self.assertIn("RegisterThing rejected", failure.text)


if __name__ == "__main__":
    unittest.main()

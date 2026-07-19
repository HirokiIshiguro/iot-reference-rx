import unittest

from tools.test_ota import OtaLogAnalyzer


class OtaLogAnalyzerTests(unittest.TestCase):
    def make_analyzer(self, events, expected_version="0.9.3"):
        analyzer = OtaLogAnalyzer(expected_version=expected_version)
        for line_number, line in enumerate(events, start=1):
            # Deliberately reuse one timestamp.  UART reads can contain multiple
            # lines, so proof ordering must use line order instead of timestamps.
            analyzer.consume_line(line, elapsed=1.0)
        return analyzer

    def alternate_events(self):
        return [
            "Application version 0.9.2",
            "Received OTA Job.",
            "Starting The Download.",
            "Downloaded block 1 of 1.",
            "software reset after install area erase...",
            "Application version 0.9.3",
            "---OTA Completed successfully!---",
        ]

    def test_existing_strict_marker_proof_remains_valid(self):
        analyzer = self.make_analyzer(
            [
                "Application version 0.9.2",
                "Received OTA Job.",
                "Starting The Download.",
                "Downloaded block 1 of 1.",
                "Close file event Received",
                "Activate Image event Received",
                "Application version 0.9.3",
                "New image has higher version than current image, accepted!",
            ]
        )

        self.assertTrue(analyzer.is_success())
        self.assertEqual(analyzer.success_proof(), "strict_markers")

    def test_accepts_ordered_post_reboot_completion_proof(self):
        analyzer = self.make_analyzer(self.alternate_events())

        self.assertTrue(analyzer.is_success())
        self.assertEqual(
            analyzer.success_proof(),
            "post_reboot_version_and_completion",
        )
        self.assertTrue(analyzer.has_marker("software_reset"))

    def test_alternate_proof_rejects_missing_reset(self):
        events = self.alternate_events()
        events.remove("software reset after install area erase...")

        self.assertFalse(self.make_analyzer(events).is_success())

    def test_alternate_proof_rejects_unchanged_baseline_version(self):
        events = self.alternate_events()
        events[0] = "Application version 0.9.3"

        self.assertFalse(self.make_analyzer(events).is_success())

    def test_alternate_proof_rejects_wrong_completion_order(self):
        events = self.alternate_events()
        completed = events.pop()
        events.insert(4, completed)

        self.assertFalse(self.make_analyzer(events).is_success())

    def test_alternate_proof_rejects_classified_fatal_error(self):
        events = self.alternate_events()
        events.append("OTA is failed!")

        self.assertFalse(self.make_analyzer(events).is_success())


if __name__ == "__main__":
    unittest.main()

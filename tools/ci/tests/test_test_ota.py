import unittest

from tools.test_ota import OtaLogAnalyzer


class OtaLogAnalyzerTests(unittest.TestCase):
    def make_analyzer(
        self,
        events,
        expected_version="0.9.3",
        require_tls_version=None,
    ):
        analyzer = OtaLogAnalyzer(
            expected_version=expected_version,
            require_tls_version=require_tls_version,
        )
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

    def marker_loss_events(self):
        return [
            "Application version 0.9.2",
            "Received OTA Job.",
            "Starting The Download.",
            "Downloaded block 1 of 1.",
            "Application version 0.9.3",
            "New image has higher version than current image, accepted!",
            "---OTA Completed successfully!---",
        ]

    def early_banner_capture_gap_events(self):
        return [
            "Application version 0.9.2",
            "TLS handshake successful: version TLSv1.2",
            "Downloaded block 0 of 112.",
            "Close file event Received",
            "Activate Image event Received",
            "software reset after install area erase...",
            "Application version 0.9.3",
            "TLS handshake successful: version TLSv1.2",
            "New image has higher version than current image, accepted!",
            "---OTA Completed successfully!---",
        ]

    def rx671_interleaved_banner_events(self):
        return [
            "RX secure boot program",
            "Application version 0.1.0",
            "RX secure boot program",
            "Received OTA Job.",
            "RX secure boot program",
            "Starting The Downloaalive tick=8",
            "d.",
            "Downloaded block 0 of 192.",
            "Close file event Received",
            "Activate Image event Received",
            "OTA image is in selfcheck mode.",
            "RX secure boot program",
            "Application version 0.1.1",
            "TLS handshake successful: version TLSv1.3",
            "New image has higher version than current image, accepted!",
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

    def test_accepts_ordered_candidate_proof_when_transition_markers_are_lost(self):
        analyzer = self.make_analyzer(self.marker_loss_events())

        self.assertTrue(analyzer.is_success())
        self.assertEqual(
            analyzer.success_proof(),
            "ordered_candidate_acceptance_and_completion",
        )
        self.assertFalse(analyzer.has_marker("close_file"))
        self.assertFalse(analyzer.has_marker("activate_image"))
        self.assertFalse(analyzer.has_marker("software_reset"))

    def test_ordered_candidate_proof_remains_fail_closed(self):
        base_events = self.marker_loss_events()
        rejected_variants = {
            "missing baseline": base_events[1:],
            "candidate before download": [
                base_events[0],
                base_events[1],
                base_events[4],
                base_events[2],
                base_events[3],
                base_events[5],
                base_events[6],
            ],
            "missing acceptance": [
                event for event in base_events if "accepted!" not in event
            ],
            "completion before acceptance": [
                *base_events[:5],
                base_events[6],
                base_events[5],
            ],
            "generic completion only": [
                base_events[0],
                base_events[6],
            ],
            "classified fatal error": [
                *base_events,
                "OTA is failed!",
            ],
        }

        for case, events in rejected_variants.items():
            with self.subTest(case=case):
                self.assertFalse(self.make_analyzer(events).is_success())

        with self.subTest(case="wrong expected candidate"):
            self.assertFalse(
                self.make_analyzer(
                    base_events,
                    expected_version="0.9.4",
                ).is_success()
            )

    def test_accepts_ordered_lifecycle_when_early_banners_are_lost(self):
        analyzer = self.make_analyzer(
            self.early_banner_capture_gap_events(),
            require_tls_version="TLSv1.2",
        )

        self.assertTrue(analyzer.is_success())
        self.assertEqual(
            analyzer.success_proof(),
            "ordered_post_download_lifecycle",
        )
        summary = analyzer.build_summary(
            total_bytes=1024,
            elapsed=10.0,
            success=analyzer.is_success(),
        )
        self.assertEqual(summary["classification"], "success")
        self.assertEqual(
            summary["required_markers_missing"],
            ["job_received", "download_started"],
        )
        self.assertEqual(
            summary["strict_markers_missing"],
            ["job_received", "download_started"],
        )

    def test_ordered_post_download_lifecycle_remains_fail_closed(self):
        base_events = self.early_banner_capture_gap_events()
        rejected_variants = {
            "missing baseline": base_events[1:],
            "missing block": [
                event for event in base_events if "Downloaded block" not in event
            ],
            "missing close": [
                event for event in base_events if "Close file" not in event
            ],
            "missing activate": [
                event for event in base_events if "Activate Image" not in event
            ],
            "missing reset": [
                event for event in base_events if "software reset" not in event
            ],
            "quoted reset": [
                event.replace(
                    "software reset after install area erase...",
                    "quoted: software reset after install area erase...",
                )
                for event in base_events
            ],
            "missing candidate": [
                event for event in base_events if "version 0.9.3" not in event
            ],
            "missing acceptance": [
                event for event in base_events if "accepted!" not in event
            ],
            "missing completion": [
                event for event in base_events if "OTA Completed" not in event
            ],
            "candidate before reset": [
                *base_events[:5],
                base_events[6],
                base_events[5],
                *base_events[7:],
            ],
            "completion before acceptance": [
                *base_events[:8],
                base_events[9],
                base_events[8],
            ],
            "classified fatal error": [
                *base_events,
                "OTA is failed!",
            ],
            "late job banner": [
                *base_events,
                "Received OTA Job.",
            ],
            "late download banner": [
                *base_events,
                "Starting The Download.",
            ],
            "reversed captured early banners": [
                *base_events[:2],
                "Starting The Download.",
                "Received OTA Job.",
                *base_events[2:],
            ],
            "generic completion only": [
                base_events[0],
                base_events[9],
            ],
        }

        for case, events in rejected_variants.items():
            with self.subTest(case=case):
                self.assertFalse(
                    self.make_analyzer(
                        events,
                        require_tls_version="TLSv1.2",
                    ).is_success()
                )

        with self.subTest(case="wrong expected candidate"):
            self.assertFalse(
                self.make_analyzer(
                    base_events,
                    expected_version="0.9.4",
                    require_tls_version="TLSv1.2",
                ).is_success()
            )

        with self.subTest(case="TLS mismatch"):
            tls_mismatch_events = [
                event.replace("TLSv1.2", "TLSv1.3")
                if event == base_events[7]
                else event
                for event in base_events
            ]
            self.assertFalse(
                self.make_analyzer(
                    tls_mismatch_events,
                    require_tls_version="TLSv1.2",
                ).is_success()
            )

    def test_accepts_rx671_secure_boot_boundary_after_interleaved_banner(self):
        analyzer = self.make_analyzer(
            self.rx671_interleaved_banner_events(),
            expected_version="0.1.1",
            require_tls_version="TLSv1.3",
        )

        self.assertTrue(analyzer.is_success())
        self.assertEqual(
            analyzer.success_proof(),
            "ordered_post_download_lifecycle",
        )
        self.assertFalse(analyzer.has_marker("download_started"))
        self.assertEqual(analyzer.marker_state["rx_secure_boot"]["hits"], 4)
        chain = analyzer.ordered_post_download_lifecycle_chain()
        self.assertEqual(
            chain["reboot_boundary"]["marker_id"],
            "rx_secure_boot",
        )
        self.assertEqual(chain["reboot_boundary"]["line_number"], 12)

        summary = analyzer.build_summary(
            total_bytes=4096,
            elapsed=100.0,
            success=analyzer.is_success(),
        )
        self.assertEqual(summary["required_markers_missing"], ["download_started"])
        self.assertEqual(summary["strict_markers_missing"], ["download_started"])
        self.assertEqual(
            summary["reboot_boundary"],
            {
                "marker_id": "rx_secure_boot",
                "line_number": 12,
                "seen_at": 1.0,
            },
        )

    def test_rx671_secure_boot_boundary_remains_fail_closed(self):
        base_events = self.rx671_interleaved_banner_events()
        post_boot_index = 11
        candidate_index = 12
        rejected_variants = {
            "pre-activate banners only": [
                *base_events[:post_boot_index],
                *base_events[post_boot_index + 1 :],
            ],
            "candidate before reboot boundary": [
                *base_events[:post_boot_index],
                base_events[candidate_index],
                base_events[post_boot_index],
                *base_events[candidate_index + 1 :],
            ],
            "missing baseline": [
                event for event in base_events if "version 0.1.0" not in event
            ],
            "missing block": [
                event for event in base_events if "Downloaded block" not in event
            ],
            "missing close": [
                event for event in base_events if "Close file" not in event
            ],
            "missing activate": [
                event for event in base_events if "Activate Image" not in event
            ],
            "missing candidate": [
                event for event in base_events if "version 0.1.1" not in event
            ],
            "missing acceptance": [
                event for event in base_events if "accepted!" not in event
            ],
            "missing completion": [
                event for event in base_events if "OTA Completed" not in event
            ],
            "partial post-activate banner": [
                *base_events[:post_boot_index],
                "prefix RX secure boot program suffix",
                *base_events[post_boot_index + 1 :],
            ],
            "late exact download banner": [
                *base_events,
                "Starting The Download.",
            ],
            "classified fatal error": [
                *base_events,
                "OTA is failed!",
            ],
        }

        for case, events in rejected_variants.items():
            with self.subTest(case=case):
                analyzer = self.make_analyzer(
                    events,
                    expected_version="0.1.1",
                    require_tls_version="TLSv1.3",
                )
                self.assertFalse(analyzer.is_success())

        with self.subTest(case="wrong expected candidate"):
            self.assertFalse(
                self.make_analyzer(
                    base_events,
                    expected_version="0.1.2",
                    require_tls_version="TLSv1.3",
                ).is_success()
            )

        with self.subTest(case="TLS mismatch"):
            events = [
                event.replace("TLSv1.3", "TLSv1.2")
                for event in base_events
            ]
            self.assertFalse(
                self.make_analyzer(
                    events,
                    expected_version="0.1.1",
                    require_tls_version="TLSv1.3",
                ).is_success()
            )

    def test_first_post_activate_boundary_is_selected_deterministically(self):
        events = self.rx671_interleaved_banner_events()
        activate_index = events.index("Activate Image event Received")
        events.insert(
            activate_index + 1,
            "software reset after install area erase...",
        )
        analyzer = self.make_analyzer(
            events,
            expected_version="0.1.1",
            require_tls_version="TLSv1.3",
        )

        self.assertTrue(analyzer.is_success())
        boundary = analyzer.ordered_post_download_lifecycle_chain()[
            "reboot_boundary"
        ]
        self.assertEqual(boundary["marker_id"], "software_reset")
        self.assertEqual(boundary["line_number"], 11)
        self.assertEqual(
            analyzer.marker_events["rx_secure_boot"][-1]["line_number"],
            13,
        )

    def test_rx671_secure_boot_marker_requires_an_exact_line(self):
        analyzer = self.make_analyzer(
            [
                "prefix RX secure boot program",
                "RX secure boot program suffix",
                "quoted: RX secure boot program",
            ],
            expected_version="0.1.1",
        )

        self.assertFalse(analyzer.has_marker("rx_secure_boot"))

    def test_rx671_secure_boot_boundary_advances_timeout_classification(self):
        analyzer = self.make_analyzer(
            [
                "Application version 0.1.0",
                "Downloaded block 0 of 192.",
                "Close file event Received",
                "Activate Image event Received",
                "RX secure boot program",
            ],
            expected_version="0.1.1",
            require_tls_version="TLSv1.3",
        )

        self.assertFalse(analyzer.is_success())
        self.assertTrue(analyzer.observed_reboot_into_new_image())
        self.assertEqual(
            analyzer.classify_timeout(total_bytes=1024),
            "acceptance_not_observed",
        )

    def test_late_evidence_is_not_classified_as_waiting_for_job(self):
        events = self.early_banner_capture_gap_events()
        events = [
            *events[:5],
            events[6],
            events[5],
            *events[7:],
        ]
        analyzer = self.make_analyzer(
            events,
            require_tls_version="TLSv1.2",
        )

        self.assertFalse(analyzer.is_success())
        self.assertEqual(
            analyzer.classify_timeout(total_bytes=1024),
            "incomplete_ordered_lifecycle_proof",
        )

    def test_strict_proof_requires_ordered_markers_and_candidate(self):
        strict_events = [
            "Application version 0.9.2",
            "Received OTA Job.",
            "Starting The Download.",
            "Downloaded block 1 of 1.",
            "Close file event Received",
            "Activate Image event Received",
            "Application version 0.9.3",
            "New image has higher version than current image, accepted!",
        ]
        rejected_variants = {
            "block before job": [
                strict_events[0],
                strict_events[3],
                strict_events[1],
                strict_events[2],
                *strict_events[4:],
            ],
            "acceptance before candidate": [
                *strict_events[:6],
                strict_events[7],
                strict_events[6],
            ],
            "expected version only before job": [
                "Application version 0.9.3",
                *strict_events[1:6],
                strict_events[7],
            ],
        }

        for case, events in rejected_variants.items():
            with self.subTest(case=case):
                self.assertFalse(self.make_analyzer(events).is_success())

    def test_post_reboot_proof_requires_ordered_download_markers(self):
        events = self.alternate_events()
        reordered = [
            events[0],
            events[3],
            events[2],
            events[1],
            *events[4:],
        ]

        self.assertFalse(self.make_analyzer(reordered).is_success())


if __name__ == "__main__":
    unittest.main()

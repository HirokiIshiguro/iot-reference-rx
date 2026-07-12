import subprocess
import sys
import types
import unittest
from argparse import Namespace
from unittest import mock

from tools.ci.monitor_multi_tls import (
    MultiTlsEvidence,
    monitor_uart,
    parse_marker,
    run_reset_command,
)


def marker(event, **fields):
    suffix = " ".join(f"{key}={value}" for key, value in fields.items())
    return f"[MULTI_TLS] {event}" + (f" {suffix}" if suffix else "")


def feed_happy_path(
    evidence,
    *,
    duplicate_tls_context=False,
    outage_traffic=True,
    session1_down_at=None,
    include_generation=True,
    reconnect_generation=2,
    reconnect_both_at=36.0,
    complete_at=68.0,
    test_complete_fields=None,
):
    tls2 = "0x200" if duplicate_tls_context else "0x201"
    generation_1 = {"connection_generation": 1} if include_generation else {}
    generation_2 = (
        {"connection_generation": reconnect_generation} if include_generation else {}
    )
    events = [
        (0.0, marker("TEST_START", generation=1)),
        (0.0, marker("SESSION_UP", session=1, client_id="thing-mtls-1", network_ctx="0x100", tls_ctx="0x200", socket=1, **generation_1)),
        (1.0, marker("SESSION_UP", session=2, client_id="thing-mtls-2", network_ctx="0x101", tls_ctx=tls2, socket=2, **generation_1)),
        (2.0, marker("BOTH_UP")),
        (3.0, marker("HEARTBEAT_TX", session=1, seq=1)),
        (3.1, marker("HEARTBEAT_RX", session=1, seq=1)),
        (4.0, marker("HEARTBEAT_TX", session=2, seq=1)),
        (4.1, marker("HEARTBEAT_RX", session=2, seq=1)),
        (33.0, marker("SESSION_DOWN", session=2, reason="ci_reconnect")),
    ]
    if outage_traffic:
        events.extend(
            [
                (34.0, marker("HEARTBEAT_TX", session=1, seq=2)),
                (34.1, marker("HEARTBEAT_RX", session=1, seq=2)),
            ]
        )
    events.extend(
        [
            (35.0, marker("SESSION_UP", session=2, client_id="thing-mtls-2", network_ctx="0x101", tls_ctx=tls2, socket=3, **generation_2)),
            (reconnect_both_at, marker("BOTH_UP")),
            (37.0, marker("HEARTBEAT_TX", session=1, seq=3)),
            (37.1, marker("HEARTBEAT_RX", session=1, seq=3)),
            (38.0, marker("HEARTBEAT_TX", session=2, seq=2)),
            (38.1, marker("HEARTBEAT_RX", session=2, seq=2)),
            (complete_at, marker("TEST_COMPLETE", **(test_complete_fields or {}))),
        ]
    )
    if session1_down_at is not None:
        events.append(
            (
                session1_down_at,
                marker("SESSION_DOWN", session=1, reason="unexpected"),
            )
        )
    # Preserve firmware marker order when two events share the same rounded
    # UART timestamp.  Sorting the full tuple would put BOTH_UP before
    # SESSION_UP lexicographically and create an impossible protocol order.
    for elapsed, line in sorted(events, key=lambda item: item[0]):
        evidence.consume_line(line, elapsed)


class ParseMarkerTests(unittest.TestCase):
    def test_parses_aliases_and_quoted_value(self):
        parsed = parse_marker(
            '[MULTI_TLS] SESSION_UP s=1 cid="thing hash 1" '
            "net=0x10 tls=0x20 sock=4 gen=3"
        )
        self.assertEqual(
            parsed,
            (
                "SESSION_UP",
                {
                    "session": "1",
                    "client_id": "thing hash 1",
                    "network_ctx": "0x10",
                    "tls_ctx": "0x20",
                    "socket": "4",
                    "connection_generation": "3",
                },
            ),
        )

    def test_ignores_unrelated_uart_line(self):
        self.assertIsNone(parse_marker("A clean MQTT connection is established."))


class MultiTlsEvidenceTests(unittest.TestCase):
    def test_accepts_complete_independent_reconnect_timeline(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        feed_happy_path(evidence)

        summary = evidence.build_summary()

        self.assertTrue(summary["success"])
        self.assertEqual(summary["result"], "PASS")
        self.assertEqual(summary["timeline"]["initial_overlap_seconds"], 31.0)
        self.assertEqual(summary["timeline"]["post_reconnect_overlap_seconds"], 32.0)
        self.assertEqual(summary["heartbeat_evidence"]["session_1_outage_matching_sequences"], ["2"])
        self.assertEqual(len(summary["identity_checks"]), 2)
        self.assertEqual(summary["timeline"]["session_2_initial_connection_generation"], 1)
        self.assertEqual(summary["timeline"]["session_2_reconnect_connection_generation"], 2)

    def test_ignores_stale_marker_before_test_start(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        evidence.consume_line(marker("HEARTBEAT_RX", session=1, seq=99), 0.0)
        feed_happy_path(evidence)

        summary = evidence.build_summary()

        self.assertTrue(summary["success"])
        self.assertNotIn(
            "99",
            [event["seq"] for event in summary["sessions"]["1"]["heartbeat_rx"]],
        )

    def test_accepts_reconnect_and_both_up_at_same_rounded_timestamp(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        feed_happy_path(evidence, reconnect_both_at=35.0)

        summary = evidence.build_summary()

        self.assertTrue(summary["success"])
        self.assertEqual(summary["timeline"]["second_both_up_seconds"], 35.0)
        self.assertEqual(summary["timeline"]["post_reconnect_overlap_seconds"], 33.0)

    def test_requires_nonzero_tsip_hybrid_wait_evidence_when_requested(self):
        evidence = MultiTlsEvidence(
            min_overlap_seconds=30,
            max_duration_seconds=90,
            require_tsip_wait=True,
        )
        feed_happy_path(
            evidence,
            test_complete_fields={
                "tsip_wait_mode": "hybrid_tick",
                "tsip_wait_calls": 4096,
                "tsip_wait_delays": 16,
            },
        )

        summary = evidence.build_summary()

        self.assertTrue(summary["success"])
        self.assertTrue(summary["checks"]["tsip_wait_hook_exercised"])
        self.assertEqual(summary["tsip_wait_evidence"]["delays"], 16)

    def test_rejects_missing_tsip_wait_evidence_when_requested(self):
        evidence = MultiTlsEvidence(
            min_overlap_seconds=30,
            max_duration_seconds=90,
            require_tsip_wait=True,
        )
        feed_happy_path(evidence)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertIn("tsip_wait_hook_exercised", summary["failures"])

    def test_rejects_shared_tls_context(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        feed_happy_path(evidence, duplicate_tls_context=True)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertFalse(summary["checks"]["initial_identities_distinct"])
        self.assertFalse(summary["checks"]["post_reconnect_identities_distinct"])

    def test_rejects_reconnect_without_session_1_traffic_during_outage(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        feed_happy_path(evidence, outage_traffic=False)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertIn("session_1_tx_rx_during_session_2_outage", summary["failures"])

    def test_rejects_short_post_reconnect_overlap(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        feed_happy_path(evidence, complete_at=50.0)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertIn("post_reconnect_overlap_long_enough", summary["failures"])

    def test_rejects_completion_after_duration_bound(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=60)
        feed_happy_path(evidence, complete_at=68.0)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertIn("duration_within_bound", summary["failures"])

    def test_rejects_session_1_disconnect(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=0, max_duration_seconds=90)
        feed_happy_path(evidence, session1_down_at=50.0)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertIn("session_1_stayed_up", summary["failures"])

    def test_rejects_missing_connection_generation(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        feed_happy_path(evidence, include_generation=False)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertIn("session_2_connection_generation_increased", summary["failures"])
        self.assertTrue(
            any("missing connection_generation" in error for error in summary["protocol_errors"])
        )

    def test_rejects_non_increasing_connection_generation(self):
        evidence = MultiTlsEvidence(min_overlap_seconds=30, max_duration_seconds=90)
        feed_happy_path(evidence, reconnect_generation=1)

        summary = evidence.build_summary()

        self.assertFalse(summary["success"])
        self.assertIn("session_2_connection_generation_increased", summary["failures"])


class ResetCommandTests(unittest.TestCase):
    @mock.patch("tools.ci.monitor_multi_tls.subprocess.run")
    def test_success_uses_shell_capture_and_timeout(self, run):
        run.return_value = subprocess.CompletedProcess(
            args="reset-target", returncode=0, stdout="reset ok\n", stderr=""
        )

        result = run_reset_command("reset-target", 12.5)

        self.assertTrue(result["success"])
        self.assertEqual(result["return_code"], 0)
        run.assert_called_once_with(
            "reset-target",
            shell=True,
            capture_output=True,
            text=True,
            timeout=12.5,
        )

    @mock.patch("tools.ci.monitor_multi_tls.subprocess.run")
    def test_timeout_is_a_structured_failure(self, run):
        run.side_effect = subprocess.TimeoutExpired(
            cmd="reset-target",
            timeout=3,
            output="partial stdout",
            stderr="partial stderr",
        )

        result = run_reset_command("reset-target", 3)

        self.assertFalse(result["success"])
        self.assertEqual(result["failure"], "reset_command_timeout")
        self.assertEqual(result["stdout"], "partial stdout")
        self.assertEqual(result["stderr"], "partial stderr")

    @mock.patch("tools.ci.monitor_multi_tls.subprocess.run")
    def test_nonzero_exit_is_a_structured_failure(self, run):
        run.return_value = subprocess.CompletedProcess(
            args="reset-target", returncode=7, stdout="", stderr="rfp failed"
        )

        result = run_reset_command("reset-target", 10)

        self.assertFalse(result["success"])
        self.assertEqual(result["failure"], "reset_command_nonzero_exit")
        self.assertEqual(result["return_code"], 7)

    @mock.patch("tools.ci.monitor_multi_tls.subprocess.run")
    def test_process_launch_error_is_a_structured_failure(self, run):
        run.side_effect = OSError("reset executable unavailable")

        result = run_reset_command("reset-target", 10)

        self.assertFalse(result["success"])
        self.assertEqual(result["failure"], "reset_command_error")
        self.assertIn("unavailable", result["stderr"])

    def test_uart_is_open_before_reset_and_reset_failure_closes_it(self):
        order = []

        class FakePort:
            def __init__(self):
                self.in_waiting = 0
                order.append("open")

            def reset_input_buffer(self):
                order.append("drain")

            def close(self):
                order.append("close")

        fake_serial = types.SimpleNamespace(Serial=lambda **_kwargs: FakePort())
        reset_failure = {
            "requested": True,
            "success": False,
            "failure": "reset_command_nonzero_exit",
            "return_code": 7,
            "timeout_seconds": 10,
            "duration_seconds": 0.1,
            "stdout": "",
            "stderr": "rfp failed",
        }

        def reset_after_open(_command, _timeout):
            self.assertEqual(order, ["open", "drain"])
            order.append("reset")
            return reset_failure

        args = Namespace(
            uart_port="FAKE",
            baud=921600,
            timeout=30.0,
            min_overlap_seconds=1.0,
            reset_cmd="reset-target",
            reset_timeout=10.0,
            raw_log=None,
        )
        with mock.patch.dict(sys.modules, {"serial": fake_serial}):
            with mock.patch(
                "tools.ci.monitor_multi_tls.run_reset_command",
                side_effect=reset_after_open,
            ):
                summary = monitor_uart(args)

        self.assertEqual(order, ["open", "drain", "reset", "close"])
        self.assertFalse(summary["success"])
        self.assertFalse(summary["checks"]["reset_command_succeeded"])
        self.assertIn("reset_command_nonzero_exit", summary["failures"])


if __name__ == "__main__":
    unittest.main()

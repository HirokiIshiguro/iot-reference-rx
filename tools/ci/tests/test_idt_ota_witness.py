import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools.idt.ota_witness import UartWitness, analyze_ota_witness
from tools.idt.targets import get_target, target_fingerprint

A, B, C = "a" * 32, "b" * 32, "c" * 32
TARGET = get_target("rx72n-ethernet")
TARGET_SHA256 = target_fingerprint(TARGET)


def marker(image, version):
    return f"[IDT_BOOT] image={image} version={version}\r\n".encode()


def build(image, version):
    return {"image_id": image, "ota_version": version, "payload_sha256": "1" * 64,
            "source_sha": "2" * 40, "source_tree_dirty": False,
            "target_id": TARGET["id"], "target_sha256": TARGET_SHA256}


class OtaWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def capture(self, **kwargs):
        capture = UartWitness(self.root / "private", **kwargs)
        self.addCleanup(capture.finish)
        return capture

    def test_fragmented_bytes_are_preserved_but_only_exact_boot_frames_export(self):
        capture = self.capture()
        raw = b"DO_NOT_EXPORT_PRIVATE_MATERIAL\nMQTT echoed: " + marker(C, "9.9.9") + marker(A, "1.9.1")
        for byte in raw:
            capture.feed(bytes([byte]))
        result = capture.finish()
        self.assertTrue(result["complete"])
        self.assertEqual(raw, (capture.directory / "uart.bin").read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result["raw_sha256"])
        self.assertEqual([A], [e["image_id"] for e in result["events"]])
        self.assertNotIn("PRIVATE_MATERIAL", (capture.directory / "events.jsonl").read_text())
        self.assertNotIn("PRIVATE_MATERIAL", json.dumps(result))

    def test_public_destination_is_rejected(self):
        with self.assertRaises(ValueError):
            UartWitness(self.root / "artifacts/raw", public_output=self.root / "artifacts")

    def test_parse_problems_are_observations_and_io_failures_invalidate_capture(self):
        capture = self.capture()
        capture.feed(b"[IDT_BOOT] broken frame\n")
        capture.feed(marker(A, "1.9.1")[:-2])
        result = capture.finish()
        self.assertTrue(result["complete"])
        self.assertTrue(result["truncated_marker"])
        self.assertEqual(1, result["invalid_marker_count"])
        for mode in ("io", "capacity"):
            with self.subTest(mode=mode):
                capture = UartWitness(self.root / mode, max_bytes=1 if mode == "capacity" else 100)
                if mode == "io":
                    capture._raw = Mock(wraps=capture._raw)
                    capture._raw.write.side_effect = OSError("synthetic disk failure")
                with self.assertRaises(OSError):
                    capture.feed(b"data\n")
                self.assertFalse(capture.finish()["complete"])

    def analyze(self, events, ledger=None, complete=True):
        return analyze_ota_witness(events, ledger or [build(B, "1.9.2"), build(A, "1.9.1")],
                                   "OTAE2EGreaterVersion", complete,
                                   initial_image_id=A, candidate_image_id=B,
                                   target_id=TARGET["id"], target_sha256=TARGET_SHA256)

    def event(self, image, version):
        return {"event": "boot", "image_id": image, "version": version}

    def test_candidate_build_order_does_not_replace_observed_boot_order(self):
        events = [self.event(C, "0.9.1"), self.event(A, "1.9.1"), self.event(A, "1.9.1"),
                  self.event(B, "1.9.2")]
        result = self.analyze(events)
        self.assertTrue(result["verified"])
        self.assertEqual([C], result["pre_run_image_ids"])
        self.assertEqual("1" * 64, result["observed_images"][-1]["payload_sha256"])

    def test_missing_reversed_rolled_back_wrong_or_unknown_boot_fails(self):
        initial, candidate = self.event(A, "1.9.1"), self.event(B, "1.9.2")
        for events in ([initial], [candidate, initial], [initial, candidate, initial],
                       [initial, self.event(B, "1.9.1")], [initial, self.event(C, "1.9.2"), candidate]):
            with self.subTest(events=events):
                self.assertFalse(self.analyze(events)["verified"])
        self.assertFalse(self.analyze([initial, candidate], complete=False)["verified"])
        wrong_source = dict(build(B, "1.9.2"), source_sha="3" * 40)
        self.assertFalse(self.analyze([initial, candidate], [build(A, "1.9.1"), wrong_source])["verified"])

    def test_observations_do_not_claim_unrequested_cases_passed(self):
        result = analyze_ota_witness([self.event(A, "1.9.1")], [build(A, "1.9.1")], "OTAE2ESameVersion",
                                     target_id=TARGET["id"], target_sha256=TARGET_SHA256)
        self.assertFalse(result["verified"])
        self.assertFalse(result["required"])
        self.assertEqual("observed_only", result["verdict"])

    def test_other_target_initial_or_candidate_is_rejected_despite_identical_source(self):
        events = [self.event(A, "1.9.1"), self.event(B, "1.9.2")]
        for wrong_id in (A, B):
            for other_name in ("rx65n-bg96", "rx671-wifi"):
                ledger = [build(A, "1.9.1"), build(B, "1.9.2")]
                other = get_target(other_name)
                next(item for item in ledger if item["image_id"] == wrong_id).update(
                    target_id=other_name, target_sha256=target_fingerprint(other))
                with self.subTest(image=wrong_id, target=other_name):
                    result = self.analyze(events, ledger)
                    self.assertFalse(result["verified"])
                    self.assertEqual("not_verified", result["verdict"])
                    self.assertIn("Build target provenance does not match the selected target", result["reasons"])

    def test_missing_or_changed_build_fingerprint_and_missing_selected_identity_fail_closed(self):
        events = [self.event(A, "1.9.1"), self.event(B, "1.9.2")]
        for missing in ("target_id", "target_sha256"):
            ledger = [build(A, "1.9.1"), build(B, "1.9.2")]
            ledger[0].pop(missing)
            with self.subTest(missing=missing):
                self.assertFalse(self.analyze(events, ledger)["verified"])
        stale = dict(build(B, "1.9.2"), target_sha256="f" * 64)
        self.assertFalse(self.analyze(events, [build(A, "1.9.1"), stale])["verified"])
        with self.assertRaises(TypeError):
            analyze_ota_witness(events, [build(A, "1.9.1"), build(B, "1.9.2")])
        for target_id, fingerprint in ((None, TARGET_SHA256), ("", TARGET_SHA256),
                                       (TARGET["id"], None), (TARGET["id"], "")):
            result = analyze_ota_witness(events, [build(A, "1.9.1"), build(B, "1.9.2")],
                                         "OTAE2EGreaterVersion", initial_image_id=A, candidate_image_id=B,
                                         target_id=target_id, target_sha256=fingerprint)
            self.assertFalse(result["verified"])
            self.assertIn("Selected target identity is missing or malformed", result["reasons"])

    def test_each_selected_target_can_verify_only_its_own_ledger(self):
        for name in ("rx72n-ethernet", "rx65n-bg96", "rx671-wifi"):
            target = get_target(name)
            fingerprint = target_fingerprint(target)
            ledger = [dict(build(A, "1.9.1"), target_id=name, target_sha256=fingerprint),
                      dict(build(B, "1.9.2"), target_id=name, target_sha256=fingerprint)]
            result = analyze_ota_witness([self.event(A, "1.9.1"), self.event(B, "1.9.2")], ledger,
                                         "OTAE2EGreaterVersion", initial_image_id=A, candidate_image_id=B,
                                         target_id=name, target_sha256=fingerprint)
            with self.subTest(target=name):
                self.assertTrue(result["verified"])
                self.assertEqual(name, result["observed_images"][-1]["target_id"])

    @unittest.skipUnless(sys.platform == "linux", "PTY draining is exercised on Linux/WSL")
    def test_bridge_drains_uart_after_native_consumer_stops(self):
        # A local child substitutes for SSH. No native IDT, RPi, AWS or hardware.
        directory = Path(__file__).resolve().parents[2] / "idt"
        with patch.object(sys, "path", [str(directory)] + sys.path):
            spec = importlib.util.spec_from_file_location("idt_bridge_test", directory / "run_transport.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        raw = b"x\n" * 131072 + marker(B, "1.9.2")
        child = ("import sys; print('IDT_UART_READY',file=sys.stderr,flush=True); "
                 "sys.stdout.buffer.write(b'x\\n'*131072+" + repr(marker(B, "1.9.2")) + "); "
                 "sys.stdout.buffer.flush(); sys.stdin.buffer.read()")
        popen = subprocess.Popen
        def local_child(_args, **kwargs):
            process = popen([sys.executable, "-c", child], **kwargs)
            wait = process.wait
            process.wait = lambda timeout=None: wait(timeout=min(timeout or 3, 3))
            return process
        with patch.object(module.subprocess, "Popen", side_effect=local_child):
            bridge = module.Bridge("0" * 32, self.root / "capture")
            self.assertTrue(bridge.ready.wait(3))
            bridge.close()
        result = bridge.capture.finish()
        self.assertTrue(result["complete"])
        self.assertEqual(len(raw), result["raw_bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result["raw_sha256"])
        self.assertEqual(B, result["events"][-1]["image_id"])

    @unittest.skipUnless(sys.platform == "linux", "PTY failure/draining is exercised on Linux/WSL")
    def test_bridge_capture_failure_drains_child_and_cannot_become_pass(self):
        directory = Path(__file__).resolve().parents[2] / "idt"
        with patch.object(sys, "path", [str(directory)] + sys.path):
            spec = importlib.util.spec_from_file_location("idt_bridge_capture_failure", directory / "run_transport.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        child = ("import sys; print('IDT_UART_READY',file=sys.stderr,flush=True); "
                 "sys.stdout.buffer.write(b'x'*262144); sys.stdout.buffer.flush(); sys.stdin.buffer.read()")
        popen = subprocess.Popen
        capture = UartWitness

        def local_child(_args, **kwargs):
            return popen([sys.executable, "-c", child], **kwargs)

        with patch.object(module.subprocess, "Popen", side_effect=local_child), \
                patch.object(module, "UartWitness", side_effect=lambda path: capture(path, max_bytes=16)):
            bridge = module.Bridge("0" * 32, self.root / "failed-capture")
            self.assertTrue(bridge.ready.wait(3))
            self.assertTrue(bridge.failed.wait(3))
            with self.assertRaisesRegex(RuntimeError, "private UART capture failed"):
                bridge.close()
        self.assertEqual(0, bridge.remote.returncode)
        self.assertFalse(bridge.threads[1].is_alive())
        result = json.loads((bridge.capture.directory.parent / "uart-capture.json").read_text())
        self.assertFalse(result["complete"])


if __name__ == "__main__":
    unittest.main()

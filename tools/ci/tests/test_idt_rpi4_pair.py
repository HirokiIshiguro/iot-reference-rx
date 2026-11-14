from __future__ import annotations

import io
import json
import os
from pathlib import Path
import queue
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools.idt import rpi4_pair as pair
from tools.idt import rpi4_build_callback as callback
from tools.idt import rpi4_pair_agent as agent
from tools.idt import rpi4_windows_worker as worker_module
from tools.idt.targets import get_target, target_fingerprint


class PairProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in pair.OVERLAYS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"public baseline\n")
        (self.root / "product.c").write_bytes(b"public source\n")
        self.baseline = pair.snapshot(self.root)
        self.provenance = {"source_sha": "a" * 40, "target_id": pair.TARGET, "source_tree_dirty": False,
                           "submodule_shas": {"Test/Unity": "b" * 40}, "dependency_target_id": pair.TARGET}
        (self.root / pair.OVERLAYS[0]).write_bytes(b"synthetic modified execution\n")
        (self.root / pair.OVERLAYS[1]).write_bytes(b"synthetic modified parameters\n")

    def request(self):
        return pair.create_request(self.root, self.baseline, self.provenance, "b" * 32)

    def test_fixed_headers_round_trip_and_secret_not_in_errors(self):
        value = self.request()
        stream = io.BytesIO()
        pair.write_frame(stream, value)
        stream.seek(0)
        result = pair.read_frame(stream)
        files = pair.validate_request(result, "a" * 40)
        self.assertEqual(files[pair.OVERLAYS[0]], b"synthetic modified execution\n")
        self.assertEqual(files[pair.OVERLAYS[1]], b"synthetic modified parameters\n")

    def test_unexpected_change_add_delete_and_identity_are_rejected(self):
        source = self.root / "product.c"
        source.write_bytes(b"changed\n")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.request()
        source.write_bytes(b"public source\n")
        (self.root / "extra.c").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "file set"):
            self.request()
        (self.root / "extra.c").unlink()
        source.unlink()
        with self.assertRaisesRegex(ValueError, "file set"):
            self.request()

    def test_wrong_sha_tampered_content_unknown_file_and_response_id(self):
        request = self.request()
        with self.assertRaisesRegex(ValueError, "identity"):
            pair.validate_request(request, "c" * 40)
        tampered = json.loads(json.dumps(request))
        tampered["files"][pair.OVERLAYS[0]]["data"] = "eA=="
        with self.assertRaisesRegex(ValueError, "integrity"):
            pair.validate_request(tampered, "a" * 40)
        request["files"]["../escape"] = {"data": "", "sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "unexpected"):
            pair.validate_request(request, "a" * 40)
        result = pair.response("b" * 32, {name: b"dummy" for name in pair.OUTPUTS})
        with self.assertRaisesRegex(ValueError, "identity"):
            pair.validate_response(result, "c" * 32)

    def test_short_or_oversized_frame_fails(self):
        with self.assertRaises(EOFError):
            pair.read_frame(io.BytesIO(b"\x00\x00"))
        with self.assertRaisesRegex(ValueError, "length"):
            pair.read_frame(io.BytesIO((pair.MAX_FRAME_BYTES + 1).to_bytes(4, "big")))

    def test_partial_stream_writes_are_completed(self):
        class PartialWriter(io.BytesIO):
            def write(self, data):
                return super().write(data[:3])
        stream = PartialWriter()
        pair.write_frame(stream, {"kind": "shutdown"})
        stream.seek(0)
        self.assertEqual(pair.read_frame(stream), {"kind": "shutdown"})

    def test_mock_callback_receives_only_matching_build_outputs(self):
        target = get_target(pair.TARGET)
        app, boot = b"dummy application", b"dummy bootloader"
        client, worker = socket.socketpair()
        with client, worker:

            def mock_builder():
                with worker.makefile("rwb", buffering=0) as stream:
                    request = pair.read_frame(stream)
                    overlay = pair.validate_request(request, "a" * 40)
                    manifest = {"target_id": pair.TARGET, "target_sha256": target_fingerprint(target),
                                "source_sha": "a" * 40, "source_tree_dirty": False,
                                "mode": "idt-transport-only", "submodule_shas": self.provenance["submodule_shas"],
                                "dependency_target_id": pair.TARGET,
                                "execution_config_sha256": pair.sha256(overlay[pair.OVERLAYS[0]]),
                                "parameter_config_sha256": pair.sha256(overlay[pair.OVERLAYS[1]]),
                                "outputs": {"mot": {"sha256": pair.sha256(app)},
                                            "bootloader": {"sha256": pair.sha256(boot)}}}
                    pair.write_frame(stream, pair.response(request["request_id"], {
                        "rx72n_idt_transport.mot": app, "bootloader.mot": boot,
                        "build_manifest.json": json.dumps(manifest).encode()}))

            thread = threading.Thread(target=mock_builder)
            thread.start()
            with client.makefile("rwb", buffering=0) as stream:
                output = callback.build(self.root, self.baseline, self.provenance, stream,
                                        prepare=False, package_output=False)
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertEqual((output / "rx72n_idt_transport.mot").read_bytes(), app)
        self.assertEqual((output / "bootloader.mot").read_bytes(), boot)
        self.assertTrue((output / "build_manifest.json").is_file())

    def test_worker_stream_returns_mock_result_then_shutdown(self):
        request = self.request()
        incoming = io.BytesIO()
        pair.write_frame(incoming, request)
        pair.write_frame(incoming, {"kind": "shutdown"})
        incoming.seek(0)
        outgoing = io.BytesIO()
        worker_module.serve(incoming, outgoing,
                            lambda value: pair.response(value["request_id"],
                                                        {name: b"dummy" for name in pair.OUTPUTS}))
        outgoing.seek(0)
        self.assertEqual(set(pair.validate_response(pair.read_frame(outgoing), "b" * 32)), set(pair.OUTPUTS))
        self.assertEqual(pair.read_frame(outgoing), {"kind": "shutdown_ack"})

    def test_idle_worker_blocks_in_stream_read(self):
        left, right = socket.socketpair()
        with left, right, left.makefile("rwb", buffering=0) as server, right.makefile("rwb", buffering=0) as client:
            thread = threading.Thread(target=worker_module.serve,
                                      args=(server, server, lambda _request: self.fail("unexpected build")))
            thread.start()
            cpu_start = time.process_time()
            time.sleep(0.25)
            used = time.process_time() - cpu_start
            self.assertTrue(thread.is_alive())
            pair.write_frame(client, {"kind": "shutdown"})
            self.assertEqual(pair.read_frame(client), {"kind": "shutdown_ack"})
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertLess(used, 0.1)

    def test_windows_worker_uses_private_copy_and_preserves_checkout(self):
        request = self.request()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            checkout, temporary, workspace = (parent / name for name in ("checkout", "temporary", "workspace"))
            checkout.mkdir()
            temporary.mkdir()
            workspace.mkdir()
            for name in pair.OVERLAYS:
                path = checkout / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"public baseline\n")
            (checkout / "product.c").write_bytes(b"public source\n")
            calls = []

            def fake_run(command, **_kwargs):
                calls.append(command)
                source = Path(command[command.index("-ProjectRoot") + 1])
                self.assertEqual((source / pair.OVERLAYS[1]).read_bytes(), b"synthetic modified parameters\n")
                output = source / "artifacts/idt/build_transport"
                output.mkdir(parents=True)
                for name in pair.OUTPUTS:
                    (output / name).write_bytes(b"public dummy")

            def git_output(command, **_kwargs):
                return "a" * 40 if "rev-parse" in command else b""

            with patch.dict(os.environ, {"CI_COMMIT_SHA": "a" * 40}), \
                 patch.object(worker_module.subprocess, "check_output", side_effect=git_output), \
                 patch.object(worker_module, "restrict_runtime"), \
                 patch.object(worker_module, "verify_dependency_provenance") as verify:
                result = worker_module.build_request(request, checkout, temporary, workspace,
                                                     parent / "lease.ps1", run=fake_run)
            self.assertEqual(len(calls), 1)
            verify.assert_called_once()
            self.assertEqual(pair.validate_response(result, "b" * 32)["bootloader.mot"], b"public dummy")
            self.assertEqual(pair.snapshot(checkout), self.baseline)
            self.assertEqual(list(temporary.iterdir()), [])
            self.assertEqual(list(workspace.iterdir()), [])

            def failed_run(_command, **_kwargs):
                raise RuntimeError("synthetic build interruption")

            with patch.dict(os.environ, {"CI_COMMIT_SHA": "a" * 40}), \
                 patch.object(worker_module.subprocess, "check_output", side_effect=git_output), \
                 patch.object(worker_module, "restrict_runtime"), \
                 patch.object(worker_module, "verify_dependency_provenance"):
                with self.assertRaisesRegex(RuntimeError, "synthetic"):
                    worker_module.build_request(request, checkout, temporary, workspace,
                                                parent / "lease.ps1", run=failed_run)
            self.assertEqual(len(list(temporary.iterdir())), 1)
            self.assertEqual(len(list(workspace.iterdir())), 1)

    @unittest.skipUnless(os.name != "nt", "Unix FIFO and socket required")
    def test_unix_rendezvous_mock_and_clean_shutdown(self):
        errors = queue.Queue()
        worker_end, agent_end = socket.socketpair()
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        with worker_end, agent_end, patch.object(Path, "home", return_value=Path(home.name)):
            agent.prepare("12345")

            def run_agent():
                try:
                    with agent_end.makefile("rwb", buffering=0) as stream:
                        agent.attach("12345", stream, stream)
                except BaseException as error:
                    errors.put(error)

            def run_worker():
                try:
                    with worker_end.makefile("rwb", buffering=0) as stream:
                        worker_module.serve(stream, stream,
                                            lambda value: pair.response(value["request_id"],
                                                                        {name: b"dummy" for name in pair.OUTPUTS}))
                except BaseException as error:
                    errors.put(error)

            server = threading.Thread(target=run_agent)
            worker = threading.Thread(target=run_worker)
            server.start()
            agent.wait_ready("12345", 5)
            worker.start()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(5)
                client.connect(str(agent.session_path("12345") / "build.sock"))
                with client.makefile("rwb", buffering=0) as stream:
                    pair.write_frame(stream, self.request())
                    self.assertEqual(set(pair.validate_response(pair.read_frame(stream), "b" * 32)), set(pair.OUTPUTS))
            agent.shutdown("12345", 5)
            server.join(timeout=5)
            worker.join(timeout=5)
            self.assertFalse(server.is_alive())
            self.assertFalse(worker.is_alive())
            self.assertTrue(errors.empty(), list(errors.queue))
            self.assertFalse((agent.session_path("12345") / "build.sock").exists())
            agent.cleanup("12345")
            self.assertFalse(agent.session_path("12345").exists())


if __name__ == "__main__":
    unittest.main()

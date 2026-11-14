"""Public paired pipeline and socket contract, without external services."""
import io
import json
import os
from pathlib import Path
import queue
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

from tools.idt import rpi4_dispatch as dispatch
from tools.idt import rpi4_build_callback as callback
from tools.idt import rpi4_pair as pair
from tools.idt import rpi4_pair_agent as agent
from tools.idt import rpi4_pair_broker as broker_module
from tools.idt import rpi4_public_controller as controller
from tools.idt import rpi4_windows_worker as worker
from tools.idt.targets import get_target, target_fingerprint

SHA = "a" * 40


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_args): self.close()


class PublicPairTests(unittest.TestCase):
    def test_only_reviewed_public_job_is_admitted(self):
        env = {"CI_PROJECT_ID": "38", "CI_RUNNER_ID": "28", "CI_COMMIT_REF_PROTECTED": "true",
               "CI_PIPELINE_SOURCE": "api", "CI_COMMIT_SHA": SHA, "CI_PIPELINE_ID": "123",
               "CI_COMMIT_BRANCH": "branch", "CI_JOB_ID": "17"}
        job = {"status": "running", "id": 17, "pipeline": {"id": 123, "ref": "branch"},
               "runner": {"id": 28}, "commit": {"id": SHA}, "tag_list": ["project38-idt-rpi4-protected"]}
        self.assertEqual(controller.verify_job(env, job, SHA), ("123", "branch"))
        for bad in ({**env, "CI_COMMIT_REF_PROTECTED": "false"}, {**env, "CI_DEBUG_TRACE": "+0001"},
                    {**env, "CI_RUNNER_ID": "26"}):
            with self.assertRaises(ValueError): controller.verify_job(bad, job, SHA)
        win = {"CI_PROJECT_ID": "38", "CI_RUNNER_ID": "29", "CI_PIPELINE_SOURCE": "pipeline",
               "CI_COMMIT_REF_PROTECTED": "true", "CI_COMMIT_SHA": SHA, "CI_PIPELINE_ID": "234",
               "CI_JOB_ID": "18", "IDT_PAIR_MODE": "public", "IDT_PAIR_PARENT_PIPELINE": "123",
               "IDT_PAIR_SESSION": "456", "IDT_PAIR_PARENT_SHA": SHA}
        win_job = {"status": "running", "id": 18, "pipeline": {"id": 234}, "runner": {"id": 29},
                   "commit": {"id": SHA}, "tag_list": ["project38-idt-windows-protected"]}
        self.assertEqual(worker.verify_worker_job(win, win_job, "svc-idt-rx", "public"), "456")
        with self.assertRaises(ValueError): worker.verify_worker_job(win, win_job, "another-user", "public")
        with self.assertRaises(ValueError): worker.verify_worker_job(win, win_job, "svc-idt-rx", "transport")
        native = {**win, "IDT_PAIR_MODE": "transport"}
        self.assertEqual(worker.verify_worker_job(native, win_job, "svc-idt-rx", "transport"), "456")

    def test_trigger_uses_form_token_and_rejects_wrong_revision(self):
        client = Mock()
        client.open.return_value = Response(json.dumps({"id": 42, "sha": SHA, "ref": "branch", "source": "pipeline"}).encode())
        self.assertEqual(dispatch.trigger_worker("dummy-secret", "branch", "123", SHA, "456", "public", 600, opener=client), 42)
        request = client.open.call_args.args[0]
        self.assertNotIn("dummy-secret", request.full_url)
        form = parse_qs(request.data.decode())
        self.assertEqual(form["token"], ["dummy-secret"])
        self.assertEqual(form["variables[IDT_PAIR_PARENT_PIPELINE]"], ["123"])
        self.assertEqual(form["variables[IDT_PAIR_SESSION]"], ["456"])
        self.assertEqual(form["variables[IDT_PAIR_BUILD_SECONDS]"], ["600"])
        self.assertEqual(form["variables[IDT_PAIR_PARENT_SHA]"], [SHA])
        client.open.return_value = Response(json.dumps({"id": 43, "sha": "b" * 40, "ref": "branch", "source": "pipeline"}).encode())
        with self.assertRaisesRegex(RuntimeError, "could not be confirmed"):
            dispatch.trigger_worker("dummy-secret", "branch", "123", SHA, "456", "public", 600, opener=client)
        self.assertEqual(client.open.call_count, 2)

    def test_worker_requires_matching_parent_sha_and_request(self):
        env = {"IDT_PAIR_PARENT_PIPELINE": "123", "IDT_PAIR_SESSION": "456", "IDT_PAIR_PARENT_SHA": SHA, "CI_COMMIT_SHA": SHA}
        self.assertEqual(worker.parent_pipeline(env), "456")
        for changed in ({**env, "IDT_PAIR_PARENT_PIPELINE": "../123"},
                        {**env, "IDT_PAIR_PARENT_SHA": "b" * 40},
                        {"IDT_PAIR_PARENT_PIPELINE": "123"}):
            with self.assertRaises(ValueError): worker.parent_pipeline(changed)
        build = Mock()
        request = {"kind": "public-build", "request_id": "b" * 32, "source_sha": SHA}
        self.assertEqual(worker.public_build(request, SHA, build)["kind"], "public-result")
        build.assert_called_once_with()
        with self.assertRaises(ValueError): worker.public_build({**request, "source_sha": "c" * 40}, SHA, build)
        build.assert_called_once_with()

    @unittest.skipUnless(sys.platform == "linux", "Unix FIFO and socket required")
    def test_public_request_runs_builder_and_cleans_up(self):
        errors = queue.Queue()
        agent_end, worker_end = socket.socketpair()
        with tempfile.TemporaryDirectory() as home, agent_end, worker_end, \
             patch.object(Path, "home", return_value=Path(home)):
            agent.prepare("123")
            build = Mock()
            def connect():
                try:
                    with agent_end.makefile("rwb", buffering=0) as stream:
                        agent.attach("123", stream, stream)
                except BaseException as error:
                    errors.put(error)
            def serve():
                try:
                    with worker_end.makefile("rwb", buffering=0) as stream:
                        worker.serve(stream, stream, lambda request: worker.public_build(request, SHA, build))
                except BaseException as error:
                    errors.put(error)
            agent_thread = threading.Thread(target=connect)
            worker_thread = threading.Thread(target=serve)
            agent_thread.start()
            agent.wait_ready("123", 5)
            worker_thread.start()
            controller.request_public_build("123", SHA, 5)
            agent.shutdown("123", 5)
            agent_thread.join(5)
            worker_thread.join(5)
            self.assertFalse(agent_thread.is_alive())
            self.assertFalse(worker_thread.is_alive())
            self.assertTrue(errors.empty(), list(errors.queue))
            build.assert_called_once_with()
            agent.cleanup("123")
            self.assertFalse(agent.session_path("123").exists())

    @unittest.skipUnless(sys.platform == "linux", "Unix FIFO and socket required")
    def test_broker_starts_worker_on_request_and_shuts_it_down(self):
        errors = queue.Queue()
        threads = []
        calls = []
        with tempfile.TemporaryDirectory() as home, patch.object(Path, "home", return_value=Path(home)):
            def trigger(_token, _ref, parent, sha, session, mode, _seconds):
                calls.append((parent, sha, session, mode))
                agent_end, worker_end = socket.socketpair()
                def attach():
                    try:
                        with agent_end, agent_end.makefile("rwb", buffering=0) as stream:
                            agent.attach(session, stream, stream)
                    except BaseException as error: errors.put(error)
                def serve():
                    try:
                        with worker_end, worker_end.makefile("rwb", buffering=0) as stream:
                            worker.serve(stream, stream, lambda request: worker.public_build(request, SHA, lambda: None))
                    except BaseException as error: errors.put(error)
                for target in (attach, serve):
                    thread = threading.Thread(target=target)
                    threads.append(thread)
                    thread.start()
                return 42
            with patch.object(broker_module, "trigger_worker", side_effect=trigger):
                broker = broker_module.Broker("token", "branch", "123", SHA, "public", build_seconds=5)
                broker.start()
                self.assertEqual(calls, [])
                controller.request_public_build("123", SHA, 10)
                broker.close()
            for thread in threads:
                thread.join(5)
                self.assertFalse(thread.is_alive())
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][:2], ("123", SHA))
            self.assertEqual(calls[0][3], "public")
            self.assertTrue(errors.empty(), list(errors.queue))
            self.assertFalse(agent.session_path("123").exists())
            self.assertFalse(agent.session_path(calls[0][2]).exists())

    @unittest.skipUnless(sys.platform == "linux", "Unix FIFO and socket required")
    def test_unconfirmed_trigger_is_not_retried_and_retains_sessions(self):
        with tempfile.TemporaryDirectory() as home, patch.object(Path, "home", return_value=Path(home)), \
             patch.object(broker_module, "trigger_worker", side_effect=RuntimeError("unknown outcome")) as trigger:
            broker = broker_module.Broker("token", "branch", "123", SHA, "public", build_seconds=5)
            broker.start()
            with self.assertRaises(ValueError): controller.request_public_build("123", SHA, 5)
            with self.assertRaisesRegex(RuntimeError, "retain"):
                broker.close()
            trigger.assert_called_once()
            self.assertTrue(agent.session_path("123").is_dir())
            self.assertEqual(len(list(agent.session_path("123").parent.iterdir())), 2)

    @unittest.skipUnless(sys.platform == "linux", "Unix FIFO and socket required")
    def test_native_callback_uses_on_demand_worker_and_verified_response(self):
        threads = []
        errors = queue.Queue()
        with tempfile.TemporaryDirectory() as folder, patch.object(Path, "home", return_value=Path(folder) / "home"):
            source = Path(folder) / "source"
            source.mkdir()
            for relative in pair.OVERLAYS:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"public baseline")
            (source / "product.c").write_bytes(b"public source")
            baseline = pair.snapshot(source)
            for relative in pair.OVERLAYS:
                (source / relative).write_bytes(b"synthetic idt input")
            provenance = {"source_sha": SHA, "target_id": pair.TARGET, "source_tree_dirty": False,
                          "submodule_shas": {"Test/Unity": "b" * 40}, "dependency_target_id": pair.TARGET}
            def fake_builder(request):
                overlays = pair.validate_request(request, SHA)
                app, boot = b"dummy application", b"dummy bootloader"
                manifest = {"target_id": pair.TARGET, "target_sha256": target_fingerprint(get_target(pair.TARGET)),
                            "source_sha": SHA, "source_tree_dirty": False, "mode": "idt-transport-only",
                            "submodule_shas": provenance["submodule_shas"], "dependency_target_id": pair.TARGET,
                            "execution_config_sha256": pair.sha256(overlays[pair.OVERLAYS[0]]),
                            "parameter_config_sha256": pair.sha256(overlays[pair.OVERLAYS[1]]),
                            "outputs": {"mot": {"sha256": pair.sha256(app)},
                                        "bootloader": {"sha256": pair.sha256(boot)}}}
                return pair.response(request["request_id"], {"rx72n_idt_transport.mot": app,
                                     "bootloader.mot": boot, "build_manifest.json": json.dumps(manifest).encode()})
            def trigger(_token, _ref, _parent, _sha, session, _mode, _seconds):
                agent_end, worker_end = socket.socketpair()
                def attach():
                    try:
                        with agent_end, agent_end.makefile("rwb", buffering=0) as stream:
                            agent.attach(session, stream, stream)
                    except BaseException as error: errors.put(error)
                def serve():
                    try:
                        with worker_end, worker_end.makefile("rwb", buffering=0) as stream:
                            worker.serve(stream, stream, fake_builder)
                    except BaseException as error: errors.put(error)
                for target in (attach, serve):
                    thread = threading.Thread(target=target)
                    threads.append(thread)
                    thread.start()
                return 42
            with patch.object(broker_module, "trigger_worker", side_effect=trigger):
                broker = broker_module.Broker("token", "branch", "123", SHA, "transport", build_seconds=5)
                broker.start()
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.settimeout(10)
                    connection.connect(str(agent.session_path("123") / "build.sock"))
                    with connection.makefile("rwb", buffering=0) as stream:
                        output = callback.build(source, baseline, provenance, stream, prepare=False, package_output=False)
                broker.close()
            self.assertEqual((output / "rx72n_idt_transport.mot").read_bytes(), b"dummy application")
            for thread in threads:
                thread.join(5)
                self.assertFalse(thread.is_alive())
            self.assertTrue(errors.empty(), list(errors.queue))


if __name__ == "__main__":
    unittest.main()

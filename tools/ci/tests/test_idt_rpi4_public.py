"""Public paired pipeline and socket contract, without external services."""
import io
import contextlib
import base64
import hashlib
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from urllib.parse import parse_qs

from tools.idt import rpi4_dispatch as dispatch
from tools.idt import rpi4_build_callback as callback
from tools.idt import rpi4_pair as pair
from tools.idt import rpi4_pair_agent as agent
from tools.idt import rpi4_pair_broker as broker_module
from tools.idt import rpi4_native_controller as native_controller
from tools.idt import rpi4_public_controller as controller
from tools.idt import rpi4_ssh_gate as ssh_gate
from tools.idt import rpi4_windows_worker as worker
from tools.idt.targets import get_target, target_fingerprint

SHA = "a" * 40


def running():
    return {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_args): self.close()


class PublicPairTests(unittest.TestCase):
    def test_public_failure_diagnostic_accepts_only_fixed_fields(self):
        marker = ('PUBLIC_BUILD_FAILURE stage=target-build type=IOException '
                  'source=build_rx72n_idt_transport.ps1 line=42')
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'build.log'
            log.write_text('secret fixture\n' + marker + '\n', encoding='utf-8')
            out = io.StringIO()
            with contextlib.redirect_stderr(out):
                worker.report_public_failure(log)
            self.assertEqual(out.getvalue(), marker + '\n')
            log.write_text(marker + ' secret fixture\n', encoding='utf-8')
            out = io.StringIO()
            with contextlib.redirect_stderr(out):
                worker.report_public_failure(log)
            self.assertEqual(out.getvalue(), '')

    def test_public_serve_reports_only_exception_type(self):
        def fail(_request):
            raise subprocess.CalledProcessError(1, ['secret fixture'])
        for public in (True, False):
            stream = io.BytesIO()
            pair.write_frame(stream, {'kind': 'fixture'})
            stream.seek(0)
            out = io.StringIO()
            with contextlib.redirect_stderr(out):
                with self.assertRaisesRegex(RuntimeError, 'paired Windows build failed'):
                    worker.serve(stream, stream, fail, report_public_errors=public)
            self.assertEqual(out.getvalue(), 'Public paired build error type: CalledProcessError\n' if public else '')

    def test_public_queue_budget_reserves_existing_build_and_cleanup_time(self):
        now = datetime(2026, 11, 15, tzinfo=timezone.utc)
        job = {'started_at': (now - timedelta(seconds=300)).isoformat()}
        self.assertEqual(controller.public_queue_budget({'CI_JOB_TIMEOUT': '7200'}, job, now=now), 2370)
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            controller.public_queue_budget({'CI_JOB_TIMEOUT': '7200', 'RUNNER_SCRIPT_TIMEOUT': '1h'}, job, now=now)

    def test_worker_uses_fixed_verified_host_key_and_exact_gate_command(self):
        blob = base64.b64decode(worker.PAIR_HOST_KEY.split()[2], validate=True)
        fingerprint = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')
        self.assertEqual(fingerprint, 'Cs4R7fkjzUKr8+yrKLE+e/dSl92IxX4e35DPkZuPn8U')
        command = worker.ssh_command('123', '/tmp/known_hosts')
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('IdentitiesOnly=yes', command)
        self.assertIn('UserKnownHostsFile=/tmp/known_hosts', command)
        self.assertIn(worker.PAIR_IDENTITY, command)
        self.assertIsNotNone(ssh_gate.COMMAND.fullmatch(command[-1]))
        with self.assertRaises(ValueError): worker.ssh_command('../123', '/tmp/known_hosts')

    def test_worker_removes_temporary_host_key_file_after_disconnect(self):
        observed = {}
        process = Mock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        def start(command, **_kwargs):
            argument = next(part for part in command if part.startswith('UserKnownHostsFile='))
            path = Path(argument.split('=', 1)[1])
            observed['path'] = path
            self.assertEqual(path.read_text(encoding='ascii').strip(), worker.PAIR_HOST_KEY)
            return process
        with patch.object(worker.subprocess, 'Popen', side_effect=start), patch.object(worker, 'serve'):
            worker.run_connection('123', lambda _request: None)
        self.assertFalse(observed['path'].exists())
        process.stdin.close.assert_called_once_with()

    @unittest.skipUnless(sys.platform == "linux", "native controller requires Linux")
    def test_native_controller_rejects_home_different_from_ssh_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            actual, configured = Path(folder) / 'actual', Path(folder) / 'configured'
            actual.mkdir(); configured.mkdir()
            account = SimpleNamespace(pw_name='gitlab-runner-idt-rx', pw_dir=str(actual))
            with patch('pwd.getpwuid', return_value=account), patch.object(native_controller.platform, 'machine', return_value='aarch64'), \
                 patch.dict(os.environ, {'CI_PROJECT_DIR': str(native_controller.ROOT)}), \
                 patch.object(native_controller.linux_oidc_job, 'read_reviewed_config', return_value=SimpleNamespace(home=str(configured))), \
                 patch.object(native_controller.linux_oidc_job, 'current_job_metadata', side_effect=AssertionError('must not query')):
                with self.assertRaisesRegex(ValueError, 'home differs'):
                    native_controller.main()

    def test_forced_command_accepts_only_exact_paired_attach(self):
        command = 'python3 -u "$HOME/.cache/idt-rx72n-pair/123/rpi4_pair_agent.py" attach 123'
        self.assertIsNotNone(ssh_gate.COMMAND.fullmatch(command))
        for bad in (command + '; id', command.replace('attach 123', 'attach 124'),
                    command.replace('/123/', '/../'), command + '\n', 'id'):
            self.assertIsNone(ssh_gate.COMMAND.fullmatch(bad))

    @unittest.skipUnless(sys.platform == "linux", "Unix file ownership required")
    def test_forced_command_checks_session_files(self):
        command = 'python3 -u "$HOME/.cache/idt-rx72n-pair/123/rpi4_pair_agent.py" attach 123'
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            parent = home / '.cache/idt-rx72n-pair'
            session = parent / '123'
            session.mkdir(parents=True, mode=0o700)
            parent.chmod(0o700)
            for name in ('rpi4_pair_agent.py', 'rpi4_pair.py'):
                path = session / name
                path.write_text('public fixture')
                path.chmod(0o600)
            path, identity = ssh_gate.checked_agent(command, home, os.getuid())
            self.assertEqual(path, session / 'rpi4_pair_agent.py')
            self.assertEqual(identity, '123')
            with patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='gitlab-runner-idt-rx', pw_dir=str(home))), \
                 patch.dict(os.environ, {'SSH_ORIGINAL_COMMAND': command}), patch.object(ssh_gate.os, 'execv') as execute:
                ssh_gate.main()
            execute.assert_called_once_with('/usr/bin/python3', ['python3', '-E', '-s', '-u', str(path), 'attach', '123'])
            (session / 'rpi4_pair.py').chmod(0o644)
            with self.assertRaises(ValueError): ssh_gate.checked_agent(command, home, os.getuid())

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

    @unittest.skipUnless(os.name == 'nt', 'Windows identity entry point')
    def test_public_entry_uses_windows_identity_api_without_decoding_whoami(self):
        env = {"CI_PROJECT_ID": "38", "CI_RUNNER_ID": "29", "CI_PIPELINE_SOURCE": "pipeline",
               "CI_COMMIT_REF_PROTECTED": "true", "CI_COMMIT_SHA": SHA, "CI_PIPELINE_ID": "234",
               "CI_JOB_ID": "18", "CI_JOB_TOKEN": "fixture", "IDT_PAIR_MODE": "public",
               "IDT_PAIR_PARENT_PIPELINE": "123", "IDT_PAIR_SESSION": "456", "IDT_PAIR_PARENT_SHA": SHA}
        job = {"status": "running", "id": 18, "pipeline": {"id": 234}, "runner": {"id": 29},
               "commit": {"id": SHA}, "tag_list": ["project38-idt-windows-protected"]}
        status = [b'']
        def command(args, **_kwargs):
            if 'rev-parse' in args: return SHA + '\n'
            if 'status' in args: return status[0]
            raise AssertionError('identity must not decode a whoami subprocess')
        with patch.dict(os.environ, env, clear=True), patch.object(worker, 'current_job_metadata', return_value=job), \
             patch.object(worker, 'current_windows_user', return_value='svc-idt-rx') as identity, \
             patch.object(worker.subprocess, 'check_output', side_effect=command), \
             patch.object(worker, 'run_connection') as connection:
            worker.main()
            identity.assert_called_once()
            connection.assert_called_once()
            self.assertNotIn('CI_JOB_TOKEN', os.environ)
            connection.reset_mock()
            status[0] = b'non-UTF8-fixture-\x82'
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, 'source differs'):
                    worker.main()
            connection.assert_not_called()

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

    def test_worker_status_checks_the_expected_job_and_revision(self):
        client = Mock()
        started = datetime.now(timezone.utc).isoformat()
        data = [{"name": "rpi4_public_windows_build", "status": "running", "started_at": started,
                 "commit": {"id": SHA}, "runner": {"id": 29}}]
        client.open.return_value = Response(json.dumps(data).encode())
        self.assertEqual(dispatch.worker_status("dummy-secret", 42, SHA, "public", opener=client),
                         {"status": "running", "started_at": started})
        request = client.open.call_args.args[0]
        self.assertNotIn("dummy-secret", request.full_url)
        self.assertEqual(request.get_header("Job-token"), "dummy-secret")
        data[0]["runner"]["id"] = 3
        client.open.return_value = Response(json.dumps(data).encode())
        with self.assertRaises(RuntimeError):
            dispatch.worker_status("dummy-secret", 42, SHA, "public", opener=client)

    @unittest.skipUnless(sys.platform == 'linux', 'Unix FIFO required')
    def test_queue_wait_is_separate_from_connection_wait(self):
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home)):
            agent.prepare('456')
            broker = broker_module.Broker('token', 'branch', '123', SHA, 'public', build_seconds=5, queue_seconds=5)
            start = time.monotonic()
            def status(*_args):
                return {'status': 'waiting_for_resource', 'started_at': None} if time.monotonic() - start < 1.2 else running()
            def ready():
                time.sleep(1.4)
                fd = os.open(agent.session_path('456') / 'ready', os.O_WRONLY | os.O_NONBLOCK)
                try: os.write(fd, b'R')
                finally: os.close(fd)
            thread = threading.Thread(target=ready)
            thread.start()
            with patch.object(broker_module, 'READY_SECONDS', 1), patch.object(broker_module, 'POLL_SECONDS', 0.05), \
                 patch.object(broker_module, 'worker_status', side_effect=status):
                broker.wait_ready('456', 42, 4)
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertGreaterEqual(time.monotonic() - start, 1.2)
            agent.cleanup('456')

    @unittest.skipUnless(sys.platform == 'linux', 'Unix FIFO required')
    def test_ready_does_not_wait_for_slow_job_status_request(self):
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home)):
            agent.prepare('456')
            broker = broker_module.Broker('token', 'branch', '123', SHA, 'public', build_seconds=5, queue_seconds=5)
            release = threading.Event()
            def slow_status(*_args):
                release.wait(5)
                return running()
            def ready():
                deadline = time.monotonic() + 3
                while True:
                    try:
                        fd = os.open(agent.session_path('456') / 'ready', os.O_WRONLY | os.O_NONBLOCK)
                        break
                    except OSError:
                        if time.monotonic() >= deadline: raise
                        time.sleep(0.01)
                try: os.write(fd, b'R')
                finally: os.close(fd)
            thread = threading.Thread(target=ready)
            thread.start()
            try:
                with patch.object(broker_module, 'worker_status', side_effect=slow_status):
                    start = time.monotonic()
                    broker.wait_ready('456', 42, 4)
                    self.assertLess(time.monotonic() - start, 1)
            finally:
                release.set()
                thread.join(3)
            self.assertFalse(thread.is_alive())
            agent.cleanup('456')

    @unittest.skipUnless(sys.platform == 'linux', 'Unix FIFO required')
    def test_failed_job_stops_waiting_and_closes_readiness_pipe(self):
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home)):
            agent.prepare('456')
            broker = broker_module.Broker('token', 'branch', '123', SHA, 'public', build_seconds=5, queue_seconds=5)
            with patch.object(broker_module, 'worker_status', return_value={'status': 'failed', 'started_at': None}) as status:
                with self.assertRaisesRegex(RuntimeError, 'ended before readiness'):
                    broker.wait_ready('456', 42, 4)
                status.assert_called_once()
            with self.assertRaises(OSError):
                os.open(agent.session_path('456') / 'ready', os.O_WRONLY | os.O_NONBLOCK)
            agent.cleanup('456')

    @unittest.skipUnless(sys.platform == 'linux', 'Unix FIFO required')
    def test_queue_deadline_closes_readiness_before_a_late_worker(self):
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home)):
            agent.prepare('456')
            broker = broker_module.Broker('token', 'branch', '123', SHA, 'public', build_seconds=5, queue_seconds=5)
            with patch.object(broker_module, 'worker_status', return_value={'status': 'waiting_for_resource', 'started_at': None}), \
                 patch.object(broker_module, 'POLL_SECONDS', 0.05):
                with self.assertRaisesRegex(RuntimeError, 'reviewed wait budget'):
                    broker.wait_ready('456', 42, 0.3)
            with self.assertRaises(OSError):
                os.open(agent.session_path('456') / 'ready', os.O_WRONLY | os.O_NONBLOCK)
            agent.cleanup('456')

    @unittest.skipUnless(sys.platform == 'linux', 'Unix FIFO required')
    def test_connection_deadline_begins_when_worker_is_running(self):
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home)):
            agent.prepare('456')
            broker = broker_module.Broker('token', 'branch', '123', SHA, 'public', build_seconds=5, queue_seconds=5)
            with patch.object(broker_module, 'worker_status', side_effect=lambda *_args: running()), \
                 patch.object(broker_module, 'READY_SECONDS', 0.3):
                start = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, 'reviewed wait budget'):
                    broker.wait_ready('456', 42, 4)
                self.assertLess(time.monotonic() - start, 2)
            with self.assertRaises(OSError):
                os.open(agent.session_path('456') / 'ready', os.O_WRONLY | os.O_NONBLOCK)
            agent.cleanup('456')

    @unittest.skipUnless(sys.platform == 'linux', 'Unix FIFO required')
    def test_connection_deadline_uses_actual_start_not_poll_time(self):
        with tempfile.TemporaryDirectory() as home, patch.object(Path, 'home', return_value=Path(home)):
            agent.prepare('456')
            broker = broker_module.Broker('token', 'branch', '123', SHA, 'public', build_seconds=5, queue_seconds=5)
            started = (datetime.now(timezone.utc) - timedelta(seconds=3)).isoformat()
            with patch.object(broker_module, 'worker_status', return_value={'status': 'running', 'started_at': started}), \
                 patch.object(broker_module, 'READY_SECONDS', 1):
                now = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, 'reviewed wait budget'):
                    broker.wait_ready('456', 42, 4)
                self.assertLess(time.monotonic() - now, 1)
            agent.cleanup('456')

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
            with patch.object(broker_module, "trigger_worker", side_effect=trigger), \
                 patch.object(broker_module, "worker_status", side_effect=lambda *_args: running()):
                broker = broker_module.Broker("token", "branch", "123", SHA, "public", build_seconds=5, queue_seconds=5)
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
            broker = broker_module.Broker("token", "branch", "123", SHA, "public", build_seconds=5, queue_seconds=5)
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
            with patch.object(broker_module, "trigger_worker", side_effect=trigger), \
                 patch.object(broker_module, "worker_status", side_effect=lambda *_args: running()):
                broker = broker_module.Broker("token", "branch", "123", SHA, "transport", build_seconds=5, queue_seconds=5)
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

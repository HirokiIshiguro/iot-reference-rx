"""Native console supervision uses host-only children, never WSL, AWS or hardware."""
from contextlib import redirect_stdout
import ast
import io
import queue
import threading
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.idt import run_idt


CREDENTIALS = SimpleNamespace(access_key="fixture-access", secret_key="fixture-secret", token="fixture-token")


class IdtProcessOutputTests(unittest.TestCase):
    def wait_for_reader_close(self, process):
        deadline = time.monotonic() + 5
        while not process.stdout.closed and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(process.stdout.closed, "Owned fixture output reader did not close")

    def mock_output(self, process, values):
        remaining = iter(values)
        def next_event(timeout):
            value = next(remaining)
            if isinstance(value, BaseException):
                raise value
            if value[0] == "eof":
                process.stdout.closed = True
                process.poll.return_value = 0
            return value
        events = Mock()
        events.get.side_effect = next_event
        return events, Mock()

    def observe_child(self, source):
        public, private = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            process = subprocess.Popen([sys.executable, "-u", "-c", source],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                with redirect_stdout(public):
                    code = run_idt.observe_hardware_runtime(process, runtime, {}, CREDENTIALS, private)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                self.wait_for_reader_close(process)
        return code, public.getvalue(), private.getvalue()

    def test_quiet_process_emits_status_and_exits_successfully(self):
        started = time.monotonic()
        code, public, private = self.observe_child("import time; time.sleep(3.2)")
        self.assertEqual(0, code)
        self.assertIn("IDT phase: native runtime active", public)
        self.assertEqual("", private)
        self.assertLess(time.monotonic() - started, 8)

    def test_nonzero_exit_and_unterminated_line_are_preserved(self):
        code, public, private = self.observe_child("import sys; sys.stdout.write('partial failure'); sys.exit(7)")
        self.assertEqual(7, code)
        self.assertEqual("partial failure", private)
        self.assertEqual("", public)

    def test_fragmented_chunks_do_not_repeat_lines_or_break_split_utf8(self):
        source = ("import os,time; os.write(1,b'Building source code\\n'); time.sleep(.15); "
                  "os.write(1,b'utf8 \\xe2'); time.sleep(.15); os.write(1,b'\\x82\\xac tail')")
        with patch.object(run_idt, "NATIVE_STATUS_SECONDS", .04):
            code, public, private = self.observe_child(source)
        self.assertEqual(0, code)
        self.assertEqual("Building source code\nutf8 \u20ac tail", private)
        self.assertEqual(1, public.count("IDT phase: Building source code"))
        self.assertNotIn("\ufffd", private)
        self.assertNotIn("utf8", public)

    def test_public_output_contains_only_whitelisted_phases_and_generic_status(self):
        source = ("import sys,time; print('fixture-access fixture-secret fixture-token private-value',flush=True); "
                  "time.sleep(.1); print('Flashing private-value',flush=True)")
        with patch.object(run_idt, "NATIVE_STATUS_SECONDS", .04):
            code, public, private = self.observe_child(source)
        self.assertEqual(0, code)
        self.assertIn("IDT phase: Flashing", public)
        self.assertNotIn("private-value", public)
        self.assertIn("private-value", private)
        for value in vars(CREDENTIALS).values():
            self.assertNotIn(value, public)
            self.assertNotIn(value, private)

    def test_secret_split_across_chunks_is_redacted_after_the_line_completes(self):
        source = ("import os,time; os.write(1,b'fixture-'); time.sleep(.15); "
                  "os.write(1,b'secret\\n')")
        with patch.object(run_idt, "NATIVE_STATUS_SECONDS", .04):
            code, public, private = self.observe_child(source)
        self.assertEqual(0, code)
        self.assertEqual("[REDACTED]\n", private)
        self.assertNotIn("fixture-", public)
        self.assertNotIn("secret", public)

    def test_complete_phase_and_private_lines_arrive_before_child_exit_without_communicate(self):
        public = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            release = runtime / "release-streaming-fixture"
            source = (
                "from pathlib import Path; import os,sys,time\n"
                "release=Path(sys.argv[1]);os.write(1,b'Building source code\\nfixture-secret\\n')\n"
                "deadline=time.monotonic()+3\n"
                "while not release.exists() and time.monotonic()<deadline:time.sleep(.01)\n"
            )
            process = subprocess.Popen([sys.executable, "-u", "-c", source, str(release)],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            observed_before_exit = []
            testcase = self

            class ProgressConsole(io.StringIO):
                def write(self, line):
                    written = super().write(line)
                    if line == "[REDACTED]\n":
                        testcase.assertIsNone(process.poll(), "Private progress was buffered until child exit")
                        testcase.assertIn("IDT phase: Building source code", public.getvalue())
                        observed_before_exit.append(True)
                        release.touch()
                    return written

            private = ProgressConsole()
            try:
                with patch.object(process, "communicate", side_effect=AssertionError("communicate must not own streaming stdout")) as snapshots, \
                        patch.object(run_idt, "stop_hardware_runtime", side_effect=RuntimeError("unexpected fixture cleanup")) as cleanup:
                    with redirect_stdout(public):
                        code = run_idt.observe_hardware_runtime(process, runtime, {}, CREDENTIALS, private)
                snapshots.assert_not_called()
                cleanup.assert_not_called()
                self.assertEqual(0, code)
                self.assertEqual([True], observed_before_exit)
                self.assertEqual("Building source code\n[REDACTED]\n", private.getvalue())
                self.assertTrue(process._idt_output_drain_complete)
            finally:
                release.touch()
                process.wait(timeout=5)
                self.wait_for_reader_close(process)

    def test_read_failure_retains_signers_even_if_the_pipe_was_closed(self):
        from tools.idt import ota_aws_signers
        process = Mock(stdout=SimpleNamespace(closed=True))
        process.poll.return_value = 0
        events = self.mock_output(process, [("error", None)])
        with patch.object(run_idt, "native_output_events", return_value=events), \
                patch.object(run_idt, "stop_hardware_runtime", side_effect=RuntimeError("reader cleanup failed")):
            with self.assertRaisesRegex(RuntimeError, "reader cleanup failed"):
                run_idt.observe_hardware_runtime(process, Path("fixture-runtime"), {}, CREDENTIALS, io.StringIO())
        self.assertFalse(process._idt_output_drain_complete)
        with patch.object(ota_aws_signers, "cleanup_aws_signers") as delete_signers:
            result = run_idt.cleanup_signers_after_runtime(process, Path("fixture-inputs"), object())
        self.assertEqual("cleanup_failed", result["state"])
        delete_signers.assert_not_called()

    def test_heartbeat_does_not_extend_the_existing_native_deadline(self):
        supervisor = Path(run_idt.__file__).with_name("run_transport.py")
        function = next(node for node in ast.parse(supervisor.read_text(encoding="utf-8")).body
                        if isinstance(node, ast.FunctionDef) and node.name == "wait_for_native")
        source = ("import os,time,sys\nfrom types import SimpleNamespace\n"
                  "raise_if_flash_failed = lambda path: None\n" + ast.unparse(function) + "\n"
                  "process=SimpleNamespace(poll=lambda:None)\n"
                  "bridge=SimpleNamespace(failed=SimpleNamespace(is_set=lambda:False),"
                  "remote=SimpleNamespace(poll=lambda:None))\n"
                  "try:\n wait_for_native(process,bridge,None,.15)\n"
                  "except RuntimeError as error:\n os.write(1,(str(error)+'\\n').encode());sys.exit(9)\n")
        with patch.object(run_idt, "NATIVE_STATUS_SECONDS", .04):
            code, public, private = self.observe_child(source)
        self.assertEqual(9, code)
        self.assertIn("IDT phase: native runtime active", public)
        self.assertEqual("IDT run exceeded its time budget\n", private)

    def test_signers_are_retained_until_both_native_exit_and_output_drain(self):
        from tools.idt import ota_aws_signers
        session, inputs = object(), Path("fixture-inputs")
        for running, output_closed in ((True, False), (False, False), (True, True), (False, True)):
            with self.subTest(running=running, output_closed=output_closed):
                process = Mock(stdout=SimpleNamespace(closed=output_closed))
                process.poll.return_value = None if running else 0
                with patch.object(ota_aws_signers, "cleanup_aws_signers", return_value={
                        "state": "deleted", "certificates": [{"deleted": True}]}) as cleanup:
                    result = run_idt.cleanup_signers_after_runtime(process, inputs, session)
                if not running and output_closed:
                    self.assertEqual({"state": "deleted", "certificates": 1,
                                      "certificates_deleted": 1}, result)
                    cleanup.assert_called_once_with(inputs, session)
                else:
                    self.assertEqual("cleanup_failed", result["state"])
                    cleanup.assert_not_called()

    def test_signers_created_before_native_start_can_be_cleaned(self):
        from tools.idt import ota_aws_signers
        with patch.object(ota_aws_signers, "cleanup_aws_signers", return_value={
                "state": "deleted", "certificates": []}) as cleanup:
            result = run_idt.cleanup_signers_after_runtime(None, Path("fixture-inputs"), object())
        self.assertEqual("deleted", result["state"])
        self.assertEqual(1, cleanup.call_count)

    def test_interrupt_uses_exact_owned_cleanup_once_and_drains_only_new_bytes(self):
        process = Mock(stdout=SimpleNamespace(closed=False))
        process.poll.return_value = None
        process.wait.return_value = 0
        output = self.mock_output(process, [("data", b"first\n"), KeyboardInterrupt(), ("data", b"last"), ("eof", None)])
        runtime, environment = Path("fixture-runtime"), {"fixture": "environment"}
        public, private = io.StringIO(), io.StringIO()
        def finish_owned(selected, selected_runtime, selected_env, credentials, *, drain):
            drain(time.monotonic() + 1)
        with patch.object(run_idt, "native_output_events", return_value=output), \
                patch.object(run_idt, "stop_hardware_runtime", side_effect=finish_owned) as cleanup:
            with redirect_stdout(public), self.assertRaises(KeyboardInterrupt):
                run_idt.observe_hardware_runtime(process, runtime, environment, CREDENTIALS, private)
        self.assertEqual((process, runtime, environment, CREDENTIALS), cleanup.call_args.args)
        self.assertEqual(1, cleanup.call_count)
        self.assertEqual("first\nlast", private.getvalue())
        self.assertTrue(process._idt_output_drain_complete)
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_cleanup_failure_is_terminal_and_not_retried(self):
        process = Mock(stdout=SimpleNamespace(closed=False))
        process.poll.return_value = None
        output = self.mock_output(process, [KeyboardInterrupt()])
        with patch.object(run_idt, "native_output_events", return_value=output), \
                patch.object(run_idt, "stop_hardware_runtime", side_effect=RuntimeError("owned cleanup failed")) as cleanup:
            with self.assertRaisesRegex(RuntimeError, "owned cleanup failed"):
                run_idt.observe_hardware_runtime(process, Path("fixture-runtime"), {}, CREDENTIALS, io.StringIO())
        self.assertEqual(1, cleanup.call_count)
        self.assertFalse(process._idt_output_drain_complete)
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_shared_reader_cleanup_honors_absolute_deadline_without_killing(self):
        process = Mock(stdout=SimpleNamespace(closed=False))
        process.poll.return_value = None
        waiting = queue.Queue()
        events = Mock()
        interrupted = False
        def next_event(timeout):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
            return waiting.get(timeout=timeout)
        events.get.side_effect = next_event
        def finish_owned(selected, selected_runtime, selected_env, credentials, *, drain):
            drain(time.monotonic() + .05)
        public = io.StringIO()
        started = time.monotonic()
        with patch.object(run_idt, "NATIVE_STATUS_SECONDS", .01), \
                patch.object(run_idt, "native_output_events", return_value=(events, Mock())), \
                patch.object(run_idt, "stop_hardware_runtime", side_effect=finish_owned) as cleanup:
            with redirect_stdout(public), self.assertRaisesRegex(RuntimeError, "Owned IDT cleanup did not finish"):
                run_idt.observe_hardware_runtime(process, Path("fixture-runtime"), {}, CREDENTIALS, io.StringIO())
        self.assertEqual(1, cleanup.call_count)
        self.assertLess(time.monotonic() - started, 1)
        self.assertIn("IDT phase: owned runtime cleanup active", public.getvalue())
        self.assertFalse(process._idt_output_drain_complete)
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_exited_parent_with_unclosed_output_uses_owned_cleanup_and_stays_failed(self):
        process = Mock(stdout=SimpleNamespace(closed=False))
        process.poll.return_value = 0
        process.wait.return_value = 0
        output = self.mock_output(process, [("data", b"tail"), queue.Empty(), ("data", b" after cleanup"), ("eof", None)])
        console = io.StringIO()
        runtime, environment = Path("fixture-runtime"), {"fixture": "environment"}
        def finish_owned(selected, selected_runtime, selected_env, credentials, *, drain):
            drain(time.monotonic() + 1)
        with patch.object(run_idt, "native_output_events", return_value=output), \
                patch.object(run_idt, "stop_hardware_runtime", side_effect=finish_owned) as cleanup:
            with self.assertRaisesRegex(RuntimeError, "without closing its output pipe"):
                run_idt.observe_hardware_runtime(process, runtime, environment, CREDENTIALS, console)
        self.assertEqual((process, runtime, environment, CREDENTIALS), cleanup.call_args.args)
        self.assertEqual(1, cleanup.call_count)
        self.assertEqual("tail after cleanup", console.getvalue())
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_exited_launcher_cleanup_failure_retains_signers(self):
        from tools.idt import ota_aws_signers
        process = Mock(stdout=SimpleNamespace(closed=False))
        process.poll.return_value = 0
        output = self.mock_output(process, [queue.Empty()])
        with patch.object(run_idt, "native_output_events", return_value=output), \
                patch.object(run_idt, "stop_hardware_runtime", side_effect=RuntimeError("owned cleanup failed")) as cleanup:
            with self.assertRaisesRegex(RuntimeError, "owned cleanup failed"):
                run_idt.observe_hardware_runtime(process, Path("fixture-runtime"), {}, CREDENTIALS, io.StringIO())
        cleanup.assert_called_once()
        with patch.object(ota_aws_signers, "cleanup_aws_signers") as delete_signers:
            result = run_idt.cleanup_signers_after_runtime(process, Path("fixture-inputs"), object())
        self.assertEqual("cleanup_failed", result["state"])
        delete_signers.assert_not_called()
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_real_grandchild_pipe_is_drained_after_owned_cleanup_but_is_not_success(self):
        public, private = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            release = runtime / "release-fixture-child"
            ready = runtime / "fixture-child-ready"
            child_source = (
                "from pathlib import Path; import os,sys,time\n"
                "release,ready=map(Path,sys.argv[1:]);ready.write_text(str(os.getpid()))\n"
                "deadline=time.monotonic()+5\n"
                "while not release.exists() and time.monotonic()<deadline:time.sleep(.01)\n"
                "os.write(1,b'fixture child drained\\n')\n"
            )
            launcher_source = (
                "import os,subprocess,sys\n"
                "subprocess.Popen([sys.executable,'-u','-c',sys.argv[1],*sys.argv[2:]],"
                "stdout=sys.stdout,stderr=sys.stderr)\nos._exit(0)\n"
            )
            process = subprocess.Popen(
                [sys.executable, "-u", "-c", launcher_source, child_source, str(release), str(ready)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                # Establish the exact reproduction: launcher exited, one known
                # fixture descendant still owns the inherited stdout handle.
                process.wait(timeout=5)
                deadline = time.monotonic() + 3
                while not ready.is_file() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.is_file(), "Fixture descendant did not start")
                fixture_child_pid = int(ready.read_text())
                self.assertGreater(fixture_child_pid, 0)

                def finish_owned_fixture(selected, selected_runtime, environment, credentials, *, drain):
                    self.assertIs(process, selected)
                    self.assertEqual(runtime, selected_runtime)
                    # Cooperative exit affects this unique fixture directory
                    # only; no PID enumeration, WSL or OS signaling is used.
                    timer = threading.Timer(.12, release.touch)
                    timer.start()
                    try:
                        drain(time.monotonic() + 3)
                    finally:
                        timer.cancel()
                        timer.join()

                with patch.object(run_idt, "NATIVE_STATUS_SECONDS", .04), \
                        patch.object(run_idt, "stop_hardware_runtime", side_effect=finish_owned_fixture) as cleanup:
                    with redirect_stdout(public), self.assertRaisesRegex(RuntimeError, "without closing its output pipe"):
                        run_idt.observe_hardware_runtime(process, runtime, {}, CREDENTIALS, private)
                cleanup.assert_called_once()
                self.assertEqual((process, runtime, {}, CREDENTIALS), cleanup.call_args.args)
                self.assertEqual(0, process.returncode)
                self.assertTrue(process.stdout.closed)
                self.assertEqual("fixture child drained\n", private.getvalue())
                self.assertNotIn("fixture child drained", public.getvalue())
                self.assertIn("IDT phase: owned runtime cleanup active", public.getvalue())
            finally:
                release.touch()
                process.wait(timeout=6)
                self.wait_for_reader_close(process)

    def test_owned_stop_passes_absolute_cleanup_budget_to_the_existing_reader(self):
        process = Mock()
        runtime, environment = Path("fixture-runtime"), {"fixture": "environment"}
        drain = Mock()
        with patch.object(run_idt, "HOST", {"wsl_distribution": "fixture-distro", "wsl_python": "fixture-python"}), \
                patch.object(run_idt, "wsl_path", side_effect=lambda path: str(path)), \
                patch.object(run_idt.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout='{"signaled": true}')) as signal_owned, \
                patch.object(run_idt.time, "monotonic", return_value=100):
            run_idt.stop_hardware_runtime(process, runtime, environment, CREDENTIALS, drain=drain)
        command = signal_owned.call_args.args[0]
        self.assertIn(str(runtime / "execution"), command)
        self.assertIn(str(run_idt.SOURCE), command)
        drain.assert_called_once_with(100 + run_idt.owned_runtime_cleanup_seconds(run_idt.NATIVE_CLEANUP_SECONDS))
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_owned_stop_signals_linux_selector_even_when_launcher_already_exited(self):
        process = Mock(stdout=SimpleNamespace(closed=False))
        process.poll.return_value = 0
        runtime, environment = Path("fixture-runtime"), {"fixture": "environment"}
        drain = Mock()
        with patch.object(run_idt, "HOST", {"wsl_distribution": "fixture-distro", "wsl_python": "fixture-python"}), \
                patch.object(run_idt, "wsl_path", side_effect=lambda path: str(path)), \
                patch.object(run_idt.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout='{"signaled": 1}')) as signal_owned:
            run_idt.stop_hardware_runtime(process, runtime, environment, CREDENTIALS, drain=drain)
        signal_owned.assert_called_once()
        command = signal_owned.call_args.args[0]
        self.assertIn(str(runtime / "execution"), command)
        self.assertIn(str(run_idt.SOURCE), command)
        drain.assert_called_once()
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_exhausted_owned_cleanup_budget_is_terminal(self):
        process = Mock()
        runtime = Path("fixture-runtime")
        drain = Mock(side_effect=RuntimeError("Owned IDT cleanup did not finish; inspect the private runtime before reuse"))
        with patch.object(run_idt, "HOST", {"wsl_distribution": "fixture-distro", "wsl_python": "fixture-python"}), \
                patch.object(run_idt, "wsl_path", side_effect=lambda path: str(path)), \
                patch.object(run_idt.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout='{"signaled": true}')):
            with self.assertRaisesRegex(RuntimeError, "cleanup did not finish"):
                run_idt.stop_hardware_runtime(process, runtime, {}, CREDENTIALS, drain=drain)
        drain.assert_called_once()
        process.communicate.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()

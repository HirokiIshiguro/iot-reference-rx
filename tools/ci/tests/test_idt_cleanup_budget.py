"""Exercise cleanup ordering and worst-case waits without boards or real waits."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import shlex
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from tools.idt import cleanup_budget as budget
from tools.idt.targets import get_target, target_fingerprint


def linux_module(name):
    directory = Path(__file__).resolve().parents[2] / "idt"
    with patch.object(sys, "path", [str(directory)] + sys.path):
        spec = importlib.util.spec_from_file_location("idt_cleanup_" + name, directory / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class CleanupBudgetTests(unittest.TestCase):
    def test_callback_budget_covers_every_phase_and_failed_transaction_reset(self):
        for name in ("rx72n-ethernet", "rx65n-bg96", "rx671-wifi"):
            with self.subTest(target=name):
                transaction = budget.flash_transaction_seconds(name)
                self.assertEqual(sum(budget.FLASH_TRANSACTION_PHASES[name].values()), transaction)
                self.assertGreaterEqual(budget.RFP_LOCK_WAIT_SECONDS,
                                        transaction + budget.FLASH_ABORT_RESET_SECONDS)
                self.assertGreater(budget.flash_remote_seconds(name),
                                   transaction + budget.FLASH_ABORT_RESET_SECONDS)
        self.assertGreater(budget.flash_transaction_seconds("rx671-wifi"),
                           budget.flash_transaction_seconds("rx72n-ethernet"))
        with self.assertRaises(ValueError):
            budget.flash_transaction_seconds("")

    def test_other_boards_wait_for_the_longest_shared_lock_transaction(self):
        longest = max(budget.flash_transaction_seconds(name) for name in budget.FLASH_TRANSACTION_PHASES)
        self.assertGreaterEqual(budget.BRIDGE_SHUTDOWN_SECONDS,
                                longest + budget.FLASH_ABORT_RESET_SECONDS +
                                budget.END_STATE_RESET_SECONDS + budget.END_STATE_QUIET_SECONDS +
                                budget.REMOTE_EXIT_MARGIN_SECONDS)

    def test_windows_wait_covers_native_shutdown_bridge_and_capture_drain(self):
        for native_timeout in (budget.NATIVE_CLEANUP_SECONDS, 600):
            with self.subTest(native_timeout=native_timeout):
                required = (native_timeout + budget.NATIVE_TERMINATE_SECONDS + budget.NATIVE_KILL_SECONDS +
                            budget.BRIDGE_SHUTDOWN_SECONDS + budget.REMOTE_TERMINATE_SECONDS + budget.REMOTE_KILL_SECONDS +
                            budget.CAPTURE_DRAIN_SECONDS + 3 * budget.BRIDGE_THREAD_JOIN_SECONDS)
                self.assertGreater(budget.owned_runtime_cleanup_seconds(native_timeout), required)
        self.assertEqual(480, budget.owned_runtime_cleanup_seconds(600) -
                         budget.owned_runtime_cleanup_seconds(120))
        for value in (0, -1, True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                budget.owned_runtime_cleanup_seconds(value)

    def test_windows_owned_stop_uses_shared_budget_and_preserves_live_runtime_on_timeout(self):
        from tools.idt import run_idt
        credentials = SimpleNamespace(access_key="synthetic-access", secret_key="synthetic-secret", token=None)
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            process = Mock()
            process.poll.return_value = None
            process.communicate.return_value = ("cleanup complete\n", None)
            host = {"wsl_distribution": "unit-test", "wsl_python": "python3"}
            with patch.dict(run_idt.HOST, host), patch.object(run_idt, "wsl_path", side_effect=str), \
                    patch.object(run_idt.subprocess, "run", return_value=Mock(returncode=0, stdout='{"signaled": 1}')):
                run_idt.stop_hardware_runtime(process, runtime, {}, credentials)
                process.communicate.assert_called_once_with(
                    timeout=budget.owned_runtime_cleanup_seconds(budget.NATIVE_CLEANUP_SECONDS))
                self.assertEqual("cleanup complete\n", (runtime / "console.log").read_text())
                process.communicate.side_effect = subprocess.TimeoutExpired("mock WSL", 1)
                with self.assertRaisesRegex(RuntimeError, "inspect the private runtime"):
                    run_idt.stop_hardware_runtime(process, runtime, {}, credentials)
            process.kill.assert_not_called()
            process.terminate.assert_not_called()


@unittest.skipUnless(sys.platform == "linux", "Remote bridge and PTY supervisor run on Linux/WSL")
class BridgeCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def bridge(self, module, remote):
        bridge = module.Bridge.__new__(module.Bridge)
        bridge.closing, bridge.forward_stopped = threading.Event(), threading.Event()
        bridge.closed, bridge.failed = threading.Event(), threading.Event()
        bridge.remote, bridge.failure_reason = remote, None
        bridge.master, bridge.slave = 123, 124
        bridge.threads = [Mock() for _ in range(3)]
        for thread in bridge.threads:
            thread.is_alive.return_value = False
        bridge.capture = Mock(directory=self.directory / "capture")
        bridge.capture.finish.return_value = {"complete": True, "events": []}
        remote.stdout, remote.stderr, remote.returncode = None, None, 0
        return bridge

    def test_remote_bootstrap_fits_windows_argv_and_loads_selected_manifest_without_checkout(self):
        module = linux_module("run_transport")
        original_read = Path.read_bytes
        # Execute the actual compressed module loader with a harmless bridge
        # body. This checks embedded imports without opening UART or SSH.
        bridge_source = ("from targets import get_target,target_fingerprint; "
                         "from cleanup_budget import BRIDGE_SHUTDOWN_SECONDS; "
                         "t=get_target(sys.argv[2]); "
                         "print(json.dumps({'id':t['id'],'fingerprint':target_fingerprint(t),"
                         "'budget':BRIDGE_SHUTDOWN_SECONDS}))").encode()

        def source(path):
            return bridge_source if path.name == "rpi_uart_bridge.py" else original_read(path)

        for name in ("rx72n-ethernet", "rx65n-bg96", "rx671-wifi"):
            target = get_target(name)
            command = module.bridge_command("0" * 32, target)
            self.assertLess(len(subprocess.list2cmdline([module.SSH, "-T", target["ssh_alias"], command])), 32767)
            with patch.object(module.Path, "read_bytes", side_effect=source, autospec=True):
                command = module.bridge_command("0" * 32, target)
            args = shlex.split(command)
            completed = subprocess.run([sys.executable, *args[1:]], cwd=self.directory,
                                       capture_output=True, text=True, timeout=5, check=True)
            result = json.loads(completed.stdout)
            with self.subTest(target=name):
                self.assertEqual(name, result["id"])
                self.assertEqual(target_fingerprint(target), result["fingerprint"])
                self.assertEqual(budget.BRIDGE_SHUTDOWN_SECONDS, result["budget"])

    def test_host_allows_full_callback_reset_and_quiet_check_before_capture_close(self):
        module = linux_module("run_transport")
        remote = Mock()
        bridge = self.bridge(module, remote)
        minimum = (budget.RFP_LOCK_WAIT_SECONDS + budget.END_STATE_RESET_SECONDS +
                   budget.END_STATE_QUIET_SECONDS)

        def wait(timeout):
            if timeout < minimum:
                raise subprocess.TimeoutExpired("mock remote bridge", timeout)
            self.assertTrue(bridge.closing.is_set())
            remote.stdin.close.assert_called_once()
            return 0

        remote.wait.side_effect = wait
        with patch.object(module.os, "close"):
            bridge.close()
        remote.wait.assert_called_once_with(timeout=budget.BRIDGE_SHUTDOWN_SECONDS)
        remote.terminate.assert_not_called()
        remote.kill.assert_not_called()
        bridge.threads[1].join.assert_any_call(timeout=budget.CAPTURE_DRAIN_SECONDS)
        bridge.capture.finish.assert_called_once()
        self.assertTrue((self.directory / "uart-capture.json").is_file())

    def test_expired_bridge_cleanup_cannot_pass_even_if_local_ssh_exits_zero(self):
        module = linux_module("run_transport")
        remote = Mock()
        bridge = self.bridge(module, remote)
        remote.wait.side_effect = [subprocess.TimeoutExpired("mock remote bridge", 1), 0]
        with patch.object(module.os, "close"), self.assertRaisesRegex(RuntimeError, "inspect the owned bench"):
            bridge.close()
        self.assertTrue(bridge.failed.is_set())
        remote.terminate.assert_called_once()
        bridge.capture.finish.assert_called_once()

    def test_native_signal_escalation_and_final_wait_are_bounded(self):
        module = linux_module("run_transport")
        process = Mock(pid=1234)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("mock native", 120),
                                    subprocess.TimeoutExpired("mock native", 10), 0]
        with patch.object(module.os, "killpg") as signal_group:
            module.stop_idt(process, 120)
        self.assertEqual([module.signal.SIGINT, module.signal.SIGTERM, module.signal.SIGKILL],
                         [call.args[1] for call in signal_group.call_args_list])
        self.assertEqual([120, budget.NATIVE_TERMINATE_SECONDS, budget.NATIVE_KILL_SECONDS],
                         [call.kwargs["timeout"] for call in process.wait.call_args_list])
        process.wait.side_effect = subprocess.TimeoutExpired("mock native", 1)
        with patch.object(module.os, "killpg"), self.assertRaisesRegex(RuntimeError, "did not stop"):
            module.stop_idt(process, 120)

    def test_remote_reset_waits_full_budget_but_quiet_does_not_establish_hold(self):
        module = linux_module("rpi_uart_bridge")
        clock = Mock()
        elapsed = [0.0]
        clock.monotonic.side_effect = lambda: elapsed[0]
        clock.sleep.side_effect = lambda _seconds: elapsed.__setitem__(0, elapsed[0] + 450)
        observer = Mock(in_waiting=0)

        def read(_amount):
            elapsed[0] += .25
            return b""

        observer.read.side_effect = read
        serial = Mock()
        serial.Serial.return_value.__enter__ = Mock(return_value=observer)
        serial.Serial.return_value.__exit__ = Mock(return_value=False)
        with patch.object(module, "time", clock), patch.object(module, "open_shared_lock", return_value=42), \
                patch.object(module.fcntl, "flock", side_effect=[BlockingIOError, BlockingIOError, BlockingIOError, None]), \
                patch.object(module, "run_guarded", return_value=Mock(returncode=0)) as reset, \
                patch.object(module.os, "close") as close, contextlib.redirect_stderr(io.StringIO()) as status:
            module.reset_and_observe_quiet(serial, get_target("rx65n-bg96"))
            self.assertGreater(elapsed[0], 900)
            self.assertLess(elapsed[0], budget.RFP_LOCK_WAIT_SECONDS)
            self.assertEqual(budget.END_STATE_RESET_SECONDS, reset.call_args.kwargs["timeout"])
            self.assertTrue(reset.call_args.kwargs["quiet"])
            self.assertIn("reset_requested=ok physical_hold=unverified quiet_1s=yes", status.getvalue())
            self.assertNotIn("reset_hold=ok", status.getvalue())
            self.assertIn("-reset", reset.call_args.args[0])
            self.assertNotIn("-run", reset.call_args.args[0])
            close.assert_called_once_with(42)

    def test_owner_is_released_after_verified_reset_but_retained_after_reset_failure(self):
        module = linux_module("rpi_uart_bridge")
        for reset_fails in (False, True):
            with self.subTest(reset_fails=reset_fails):
                target = dict(get_target("rx671-wifi"), id="unit-bridge-lifecycle",
                              rfp_lock=str(self.directory / "global-rfp.lock"),
                              owner_file=str(self.directory / ("owner-failed.json" if reset_fails else "owner-ok.json")))
                token = "0" * 32
                owner_path = Path(target["owner_file"])
                controller, client, serial, port = MagicMock(), MagicMock(), Mock(), Mock()
                controller.fileno.return_value = 11
                controller.accept.return_value = client, None
                client.__enter__.return_value = client
                client.recv.return_value = (json.dumps({"token": token, "target_id": target["id"],
                                                        "target_sha256": target_fingerprint(target),
                                                        "action": "mark-flashed"}) + "\n").encode()
                serial.Serial.return_value = port
                port.fileno.return_value = 12
                sequence = []

                def reset(_serial, _target):
                    state = json.loads(owner_path.read_text())
                    self.assertTrue(state["closing"])
                    self.assertTrue(state["touched"])
                    port.close.assert_called_once()
                    sequence.append("reset_and_quiet")
                    if reset_fails:
                        raise RuntimeError("synthetic reset failure")

                with patch.dict(sys.modules, {"serial": serial}), \
                        patch.object(sys, "argv", ["bridge", token, target["id"]]), \
                        patch.object(module, "get_target", return_value=target), \
                        patch.object(module.socket, "gethostname", return_value=target["hostname"]), \
                        patch.object(module.socket, "socket", return_value=controller), \
                        patch.object(module, "open_shared_lock", return_value=42), \
                        patch.object(module.fcntl, "flock"), patch.object(module.os, "chmod"), \
                        patch.object(module.os, "getpid", return_value=987654321), \
                        patch.object(module.os, "read", return_value=b""), \
                        patch.object(module.os, "close", side_effect=lambda _fd: sequence.append("unlock")), \
                        patch.object(module.select, "select", side_effect=[([11], [], []), ([0], [], [])]), \
                        patch.object(module.signal, "signal"), \
                        patch.object(module, "reset_and_observe_quiet", side_effect=reset), \
                        contextlib.redirect_stderr(io.StringIO()):
                    if reset_fails:
                        with self.assertRaisesRegex(RuntimeError, "synthetic reset failure"):
                            module.main()
                    else:
                        module.main()
                self.assertEqual(["reset_and_quiet", "unlock"], sequence)
                self.assertEqual(reset_fails, owner_path.exists())
                reply = json.loads(client.sendall.call_args.args[0])
                self.assertTrue(reply["ok"])
                self.assertEqual(target["id"], reply["target_id"])
                self.assertEqual(target_fingerprint(target), reply["target_sha256"])
                if reset_fails:
                    self.assertTrue(json.loads(owner_path.read_text())["closing"])

    def test_persistent_rfp_unsafe_sentinel_blocks_uart_before_any_bench_access(self):
        module = linux_module("rpi_uart_bridge")
        target = dict(get_target("rx671-wifi"), rfp_lock=str(self.directory / "unsafe-rfp.lock"))
        Path(target["rfp_lock"] + ".unsafe.json").write_text('{}')
        serial = Mock()
        with patch.dict(sys.modules, {"serial": serial}), \
                patch.object(sys, "argv", ["bridge", "0" * 32, target["id"]]), \
                patch.object(module, "get_target", return_value=target), \
                patch.object(module.socket, "gethostname", return_value=target["hostname"]), \
                patch.object(module.socket, "socket") as socket_open, \
                patch.object(module, "open_shared_lock") as lock:
            with self.assertRaisesRegex(RuntimeError, "unsafe sentinel requires manual recovery"):
                module.main()
        serial.Serial.assert_not_called()
        socket_open.assert_not_called()
        lock.assert_not_called()

    def test_unsafe_sentinel_created_while_waiting_blocks_final_reset(self):
        module = linux_module("rpi_uart_bridge")
        target = dict(get_target("rx65n-bg96"), rfp_lock=str(self.directory / "late-unsafe-rfp.lock"))

        def acquire(_fd, _operation):
            Path(target["rfp_lock"] + ".unsafe.json").write_text('{}')

        serial = Mock()
        with patch.object(module, "open_shared_lock", return_value=42), \
                patch.object(module.fcntl, "flock", side_effect=acquire), \
                patch.object(module.os, "close") as close, patch.object(module, "run_guarded") as reset:
            with self.assertRaisesRegex(RuntimeError, "unsafe sentinel requires manual recovery"):
                module.reset_and_observe_quiet(serial, target)
        reset.assert_not_called()
        serial.Serial.assert_not_called()
        close.assert_called_once_with(42)

if __name__ == "__main__":
    unittest.main()

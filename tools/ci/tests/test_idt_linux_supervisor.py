"""Exercise the Linux supervisor with synthetic callbacks, UART and IDT."""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if sys.platform == "linux":
    sys.path.insert(0, str(ROOT / "tools/idt"))
    import run_transport


@unittest.skipUnless(sys.platform == "linux", "PTY supervisor requires Linux")
class LinuxSupervisorTests(unittest.TestCase):
    def setUp(self):
        # The real supervisor ignores signals during its final cleanup. This
        # test invokes main() in-process, unlike the real standalone job.
        for number in (signal.SIGINT, signal.SIGTERM):
            previous = signal.getsignal(number)
            self.addCleanup(signal.signal, number, previous)

    def test_native_group_runs_mocked_callbacks_and_restores_vendor_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source, bundle, runtime = root / "source", root / "bundle", root / "execution"
            source.mkdir(); (source / "manifest.yml").write_text("version: 202604.00\n", encoding="utf-8")
            (bundle / "bin").mkdir(parents=True); (bundle / "configs").mkdir()
            (bundle / "bin/devicetester_linux_x86-64").write_bytes(b"offline")
            original = b'{"original": true}\n'
            (bundle / "configs/config.json").write_bytes(original)
            hook = root / "build-hook.sh"; hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8"); hook.chmod(0o700)
            userdata = root / "userdata.json"; userdata.write_text(json.dumps({"freeRTOSVersion": "202604.00"}))
            target = run_transport.get_target("rx72n-ethernet")
            device = root / "device.json"; device.write_text(json.dumps([{"sku": target["sku"], "devices": [{}]}]))
            fixture = ROOT / "tools/ci/tests/fixtures/idt/rx72n-transport-complete-pass-70574.xml"
            (root / "baseline.json").write_text('{"source": "synthetic"}', encoding="utf-8")
            (root / "private").write_text("synthetic", encoding="utf-8")
            (root / "provenance").write_text("{}", encoding="utf-8")
            paired = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            paired.bind(str(root / "build.sock"))
            self.addCleanup(paired.close)
            now = datetime.now(timezone.utc)
            env = {"CI": "true", "IDT_HOST_MODE": "linux-arm64", "IDT_TARGET": "rx72n-ethernet",
                   "IDT_SCOPE": "transport", "IDT_RUNTIME_DIR": str(runtime), "IDT_LINUX_BUILD_CALLBACK": str(hook),
                   "IDT_LINUX_SSH": "/usr/bin/ssh", "IDT_LINUX_SCP": "/usr/bin/scp",
                   "IDT_LINUX_RUNTIME_ROOT": str(root), "IDT_PAIR_BASELINE": str(root / "baseline.json"),
                   "IDT_PAIR_SOCKET": str(root / "build.sock"),
                   "IDT_PAIR_BUILD_SECONDS": "600", "IDT_PAIR_QUEUE_SECONDS": "3270", "QEMU_LD_PREFIX": "/reviewed/qemu/sysroot",
                   "IDT_PRIVATE_KEY_FILE": str(root / "private"), "IDT_PROVENANCE_FILE": str(root / "provenance"),
                   "AWS_ACCESS_KEY_ID": "fake-key", "AWS_SECRET_ACCESS_KEY": "fake-secret", "AWS_SESSION_TOKEN": "fake-token",
                   "RX_OIDC_EXPIRATION_UTC": (now + timedelta(hours=3)).isoformat(), "PATH": "/usr/bin:/bin",
                   "HOME": str(root), "RX_OIDC_ID_TOKEN": "must-not-reach-child"}
            argv = ["supervisor", "--idt-root", str(bundle), "--source-path", str(source), "--output", str(runtime),
                    "--userdata-template", str(userdata), "--device-template", str(device), "--region", "ap-northeast-1",
                    "--target", "rx72n-ethernet", "--group", "FullTransportInterfaceTLS"]
            observed = {}

            class Bridge:
                def __init__(self, _token, capture, selected):
                    self.capture = capture; self.ready = threading.Event(); self.ready.set()
                    self.failed = threading.Event(); self.forward_stopped = threading.Event()
                    self.remote = SimpleProcess(); self.device = "/dev/pts/synthetic"; self.ssh_failure = None
                    observed["target"] = selected["id"]
                def close(self):
                    (self.capture.parent / "uart-capture.json").write_text('{"complete": true}')
                    observed["bridge_closed"] = True

            class SimpleProcess:
                def __init__(self): self.returncode = 0; self.stdout = io.BytesIO(b"synthetic native output\n")
                def poll(self): return 0

            def popen(command, **kwargs):
                observed["command"] = command; observed["env"] = kwargs["env"]
                report = runtime / "results/FRQ_Report.xml"; report.parent.mkdir(exist_ok=True)
                shutil.copyfile(fixture, report)
                return SimpleProcess()

            with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", argv), \
                 patch.object(run_transport, "check_child_budget"), patch.object(run_transport, "check_native_timeouts"), \
                 patch.object(run_transport, "Bridge", Bridge), patch.object(run_transport.subprocess, "Popen", side_effect=popen), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = run_transport.main()
            self.assertEqual(code, 0)
            self.assertEqual(observed["target"], "rx72n-ethernet")
            self.assertTrue(observed["bridge_closed"])
            self.assertNotIn("RX_OIDC_ID_TOKEN", observed["env"])
            self.assertEqual(observed["env"]["IDT_PAIR_BASELINE"], str(root / "baseline.json"))
            self.assertEqual(observed["env"]["IDT_PAIR_SOCKET"], str(root / "build.sock"))
            self.assertEqual(observed["env"]["IDT_PAIR_BUILD_SECONDS"], "600")
            self.assertEqual(observed["env"]["IDT_PAIR_QUEUE_SECONDS"], "3270")
            self.assertEqual(observed["env"]["QEMU_LD_PREFIX"], "/reviewed/qemu/sysroot")
            self.assertEqual((bundle / "configs/config.json").read_bytes(), original)
            configured = json.loads((runtime / "userdata.json").read_text())
            self.assertEqual(configured["buildTool"]["command"], ["/bin/bash " + str(hook) + " {{testData.sourcePath}}"])
            self.assertEqual(json.loads((runtime / "transport-result.json").read_text())["verdict"], "SELECTED_GROUP_PASS")

            # An interruption must still stop the owned process, close the
            # mocked bridge and restore the vendor's original config.
            runtime = root / "interrupted"
            env["IDT_RUNTIME_DIR"] = str(runtime)
            argv[argv.index("--output") + 1] = str(runtime)
            observed.pop("bridge_closed")
            with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", argv), \
                 patch.object(run_transport, "check_child_budget"), patch.object(run_transport, "check_native_timeouts"), \
                 patch.object(run_transport, "Bridge", Bridge), patch.object(run_transport.subprocess, "Popen", side_effect=popen), \
                 patch.object(run_transport, "wait_for_native", side_effect=KeyboardInterrupt), \
                 patch.object(run_transport, "stop_idt") as stopped, contextlib.redirect_stdout(io.StringIO()):
                code = run_transport.main()
            self.assertEqual(code, 130)
            stopped.assert_called_once()
            self.assertTrue(observed["bridge_closed"])
            self.assertEqual((bundle / "configs/config.json").read_bytes(), original)
            self.assertEqual(json.loads((runtime / "transport-result.json").read_text())["verdict"], "INTERRUPTED")

    def test_native_without_fixed_session_fails_before_bridge(self):
        with patch.dict(os.environ, {"CI": "true", "IDT_HOST_MODE": "linux-arm64"}, clear=True), \
             patch.object(run_transport, "Bridge", side_effect=AssertionError("must not open device")):
            with self.assertRaisesRegex(RuntimeError, "fixed CI OIDC"):
                run_transport.main()


if __name__ == "__main__":
    unittest.main()

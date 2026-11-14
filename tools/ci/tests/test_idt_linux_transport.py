"""Synthetic Linux launch checks; never start IDT, SSH, AWS or a board."""
from pathlib import Path
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.idt import run_idt
from tools.idt.targets import get_target


class FakeKey:
    def private_bytes(self, *_args): return b"synthetic-private"
    def public_key(self): return self
    def public_bytes(self, *_args): return b"synthetic-public"


class LinuxTransportTests(unittest.TestCase):
    def test_linux_launch_uses_unchanged_bundle_and_reviewed_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            bundle = root / "bundle"
            binary = bundle / "bin/devicetester_linux_x86-64"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"offline")
            binary.chmod(0o700)
            runtime = root / "run"
            runtime.mkdir()
            environment = {"IDT_HOST_MODE": "linux-arm64", "IDT_LINUX_IDT_ROOT": str(bundle),
                           "IDT_LINUX_BUILD_CALLBACK": "/reviewed/build-hook", "IDT_LINUX_SSH": "/usr/bin/ssh",
                           "IDT_LINUX_SCP": "/usr/bin/scp", "CI": "true"}
            credentials = SimpleNamespace(access_key="dummy-key", secret_key="dummy-secret", token="dummy-token")
            observed = {}

            def popen(command, **kwargs):
                observed.update(command=command, environment=kwargs["env"])
                return object()

            def observe(_process, directory, _env, _credentials, _console):
                report = directory / "execution/results/FRQ_Report.xml"
                report.parent.mkdir(parents=True)
                report.write_text("<testsuites/>", encoding="utf-8")
                return 0

            with patch.dict(os.environ, environment, clear=True), \
                 patch.object(run_idt, "verify_install") as verified, \
                 patch.object(run_idt, "public_signer_bootstrap_environment", return_value={}), \
                 patch.object(run_idt, "manifest_version", return_value="offline"), \
                 patch("cryptography.hazmat.primitives.asymmetric.ec.generate_private_key", return_value=FakeKey()), \
                 patch.object(run_idt, "check_child_budget"), patch.object(run_idt.subprocess, "Popen", side_effect=popen), \
                 patch.object(run_idt, "observe_hardware_runtime", side_effect=observe):
                report, code = run_idt.transport_linux(runtime, "ap-northeast-1", credentials,
                                                       {"source_sha": "a" * 40}, get_target("rx72n-ethernet"))
            verified.assert_called_once_with(bundle, "linux")
            self.assertEqual(code, 0)
            self.assertTrue(report.is_file())
            self.assertIn("run_transport.py", " ".join(observed["command"]))
            self.assertNotIn("wsl.exe", " ".join(observed["command"]).lower())
            self.assertEqual(observed["environment"]["IDT_LINUX_BUILD_CALLBACK"], "/reviewed/build-hook")
            self.assertEqual(observed["environment"]["IDT_TARGET"], "rx72n-ethernet")
            self.assertNotIn("RX_OIDC_ID_TOKEN", observed["environment"])

    def test_budget_failure_precedes_native_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            binary = root / "bundle/bin/devicetester_linux_x86-64"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"offline")
            binary.chmod(0o700)
            runtime = root / "run"
            runtime.mkdir()
            env = {"IDT_HOST_MODE": "linux-arm64", "IDT_LINUX_IDT_ROOT": str(root / "bundle")}
            with patch.dict(os.environ, env, clear=True), patch.object(run_idt, "verify_install"), \
                 patch.object(run_idt, "public_signer_bootstrap_environment", return_value={}), \
                 patch.object(run_idt, "manifest_version", return_value="offline"), \
                 patch("cryptography.hazmat.primitives.asymmetric.ec.generate_private_key", return_value=FakeKey()), \
                 patch.object(run_idt, "check_child_budget", side_effect=RuntimeError("budget")), \
                 patch.object(run_idt.subprocess, "Popen", side_effect=AssertionError("must not start")):
                with self.assertRaisesRegex(RuntimeError, "budget"):
                    run_idt.transport_linux(runtime, "ap-northeast-1", SimpleNamespace(),
                                            {"source_sha": "a" * 40}, get_target("rx72n-ethernet"))

    def test_native_cancel_targets_existing_supervisor_without_wsl(self):
        calls = []
        def run(command, **_kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout='{"signaled": 1}')
        drained = []
        with patch.object(run_idt.subprocess, "run", side_effect=run):
            run_idt.stop_hardware_runtime(None, Path("/tmp/owned-run"), {"IDT_HOST_MODE": "linux-arm64"},
                                          None, drain=lambda deadline: drained.append(deadline))
        self.assertEqual(len(calls), 1)
        self.assertIn("stop_runtime.py", " ".join(calls[0]))
        self.assertNotIn("wsl.exe", " ".join(calls[0]).lower())
        self.assertEqual(len(drained), 1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.idt.host_profile import load_host_profile
from tools.idt.check_host import requirements


class IdtHostProfileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "profile.json"

    def profile(self, values, env=None):
        self.path.write_text(json.dumps({"schema_version": 1, **values}), encoding="utf-8")
        return load_host_profile(self.path, environ=env or {})

    def test_defaults_derive_windows_paths_and_keep_workspace_convention(self):
        profile = load_host_profile(environ={"WINDIR": "D:\\Windows", "ProgramFiles": "D:\\Programs"})
        self.assertEqual("D:\\Windows\\System32\\OpenSSH\\ssh.exe", profile["windows_ssh"])
        self.assertEqual("D:\\Programs\\PowerShell\\7\\pwsh.exe", profile["windows_powershell"])
        self.assertEqual("C:\\ai\\codex\\ws", profile["workspace_root"])

    def test_profile_controls_selected_distribution_and_tools_with_legacy_override(self):
        profile = self.profile({"wsl_distribution": "IDT-Ubuntu", "wsl_python": "/mnt/c/ai/codex/tools/venvs/linux/bin/python",
            "e2studio_cli": "D:\\Renesas\\e2studioc.exe"}, {"E2STUDIO_CLI": "D:\\CI\\e2studioc.exe"})
        self.assertEqual("IDT-Ubuntu", profile["wsl_distribution"])
        self.assertEqual("/mnt/c/ai/codex/tools/venvs/linux/bin/python", profile["wsl_python"])
        self.assertEqual("D:\\CI\\e2studioc.exe", profile["e2studio_cli"])
        selected = load_host_profile(environ={"RX72N_IDT_HOST_PROFILE": str(self.path)})
        self.assertEqual("D:\\Renesas\\e2studioc.exe", selected["e2studio_cli"])

    def test_profile_cannot_override_board_identity_or_embed_credential_keys(self):
        for key in ("uart", "board_hostname", "rfp_tool", "AWS_ACCESS_KEY_ID", "secret_key"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.profile({key: "unexpected"})

    def test_path_boundaries_reject_traversal_relative_and_whitespace_roots(self):
        for values in ({"workspace_root": "C:\\ai\\codex\\ws2"},
                       {"runtime_root": "C:\\ai\\codex\\..\\outside"},
                       {"install_root": "relative"},
                       {"runtime_root": "C:\\ai\\codex\\tmp\\space here"},
                       {"windows_powershell": "pwsh.exe"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.profile(values)

    def test_example_profile_is_loadable_and_dependency_pins_are_consistent(self):
        root = Path(__file__).resolve().parents[3]
        profile = load_host_profile(root / "tools/idt/host-profile.example.json", environ={})
        self.assertEqual("Ubuntu", profile["wsl_distribution"])
        windows = requirements("requirements-windows.txt")
        linux = requirements("requirements-wsl.txt")
        self.assertEqual(windows["boto3"], windows["botocore"])
        self.assertEqual(linux, {key: windows[key] for key in linux})

    def test_runtime_workspace_and_install_roots_cannot_enter_source_checkout(self):
        source = r"C:\ai\codex\ws\idt-source"
        with patch("tools.idt.host_profile._SOURCE_ROOT", source):
            for key in ("runtime_root", "workspace_root", "install_root"):
                for value in (source, source + r"\private", source.upper() + r"\private"):
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        self.profile({key: value})
            # The shared workspace parent and sibling directories stay valid;
            # only storage inside the actual source checkout is disallowed.
            profile = self.profile({"workspace_root": r"C:\ai\codex\ws",
                                    "runtime_root": source + "-runtime"})
            self.assertEqual(source + "-runtime", profile["runtime_root"])

    def test_checker_uses_the_passed_profile_instead_of_global_defaults(self):
        from tools.idt.check_host import check_host
        profile = self.profile({"wsl_distribution": "IDT-Custom", "wsl_python": "/opt/idt/bin/python"})
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            return 1, ""

        # Replace only the module's OS view; mutating global os.name would make
        # importlib/pathlib attempt WindowsPath construction on Linux CI.
        windows_view = SimpleNamespace(name="nt", environ=os.environ, getenv=os.getenv)
        with patch("tools.idt.check_host.os", windows_view), patch("tools.idt.check_host.command", side_effect=run), patch("tools.idt.check_host.Path.is_file", return_value=False):
            result = check_host(profile)
        wsl_probes = [args for args in calls if "--exec" in args]
        self.assertTrue(wsl_probes)
        self.assertTrue(all("IDT-Custom" in args for args in wsl_probes))
        self.assertTrue(all("/opt/idt/bin/python" in args for args in wsl_probes))
        self.assertEqual(profile, result["profile"])


if __name__ == "__main__":
    unittest.main()

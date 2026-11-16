"""Exercise Linux SSH/SCP routing without a network or a device."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/idt"))
import flash_transport as flash

SHA = "a" * 40


class LinuxFlashTests(unittest.TestCase):
    def test_native_scp_receives_linux_path_without_wsl_or_aws_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder).resolve() / "execution"
            source = runtime / "source" / "idt-generated"
            (source / "Test/include").mkdir(parents=True)
            (source / "Test/include/test_param_config.h").write_text("synthetic", encoding="utf-8")
            image = runtime / "synthetic.mot"
            image.write_text("test image", encoding="utf-8")
            commands = []

            def run(command, *, env, **kwargs):
                self.assertNotIn("AWS_ACCESS_KEY_ID", env)
                commands.append(command)

            def macro(_lines, name):
                return None, None, ("-----BEGIN CERTIFICATE-----" if name.endswith("CERTIFICATE")
                                    else "-----BEGIN PRIVATE KEY-----")

            env = {"IDT_HOST_MODE": "linux-arm64", "IDT_TARGET": "rx72n-ethernet", "IDT_SCOPE": "transport",
                   "IDT_RUNTIME_DIR": str(runtime), "IDT_BENCH_TOKEN": "a" * 32, "IDT_SOURCE_SHA": SHA,
                   "IDT_LINUX_SSH": "/usr/bin/ssh", "IDT_LINUX_SCP": "/usr/bin/scp",
                   "AWS_ACCESS_KEY_ID": "ambient-must-not-reach-ssh"}
            with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["flash", str(source)]), \
                 patch.object(flash, "validate_source", return_value=source), \
                 patch.object(flash, "validated_inputs", return_value=({"image.mot": image}, {"source_sha": SHA})), \
                 patch.object(flash, "macro", side_effect=macro), patch.object(flash.subprocess, "run", side_effect=run), \
                 patch.object(flash.subprocess, "check_output", side_effect=AssertionError("wslpath must not run")):
                flash.main()
            self.assertEqual(commands[0][0], "/usr/bin/ssh")
            copies = [cmd for cmd in commands if cmd[0] == "/usr/bin/scp"]
            self.assertEqual(len(copies), 2)  # image and generated manifest
            self.assertIn(str(image), copies[0])
            self.assertTrue(all(cmd[0] in {"/usr/bin/ssh", "/usr/bin/scp"} for cmd in commands))

    def test_native_rejects_other_target_before_ssh(self):
        env = {"IDT_HOST_MODE": "linux-arm64", "IDT_TARGET": "rx671-wifi", "IDT_BENCH_TOKEN": "a" * 32}
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", ["flash", "unused"]), \
             patch.object(flash.subprocess, "run", side_effect=AssertionError("must not reach SSH")):
            with self.assertRaisesRegex(RuntimeError, "restricted"):
                flash.main()


if __name__ == "__main__":
    unittest.main()

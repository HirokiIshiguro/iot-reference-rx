"""Run the shared CI initialization block without a device or programmer."""
import os
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest

from tools.ci.rx_ci_settings import PREFIXES
from tools.idt.targets import get_target

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Linux Bash fixture")
class RuntimeSettingsCiTests(unittest.TestCase):
    def invoke(self, target, hostname=None, overrides=None):
        text = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        block = text.split("\n.rx_ci_runtime_settings:\n", 1)[1].split("\n.rx72n_linux_hw_job:\n", 1)[0]
        block = block.split("\n  after_script:\n", 1)[0]
        body = textwrap.dedent(block.split("    - |\n", 1)[1])
        host = hostname or get_target(target)["hostname"]
        script = 'hostname() { printf "%s\\n" "$FIXTURE_HOST"; }\n' + body + '\nprintf "INIT_REACHED:%s\\n" "$' + PREFIXES[target] + 'UART_PORT"\n'
        env = {key: value for key, value in os.environ.items() if not key.startswith(("RX72N_", "RX65N_", "RX671_", "RX_CI_")) and key not in ("RFP_SPEED", "RFP_AUTH")}
        env.update(RX_CI_TARGET=target, RX_CI_ENV_PREFIX=PREFIXES[target], FIXTURE_HOST=host)
        env.update(overrides or {})
        return subprocess.run(["bash", "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)

    def test_all_targets_initialize_canonical_settings(self):
        for target in PREFIXES:
            with self.subTest(target=target):
                result = self.invoke(target)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "INIT_REACHED:" + get_target(target)["uart"])

    def test_wrong_physical_override_stops_before_following_step(self):
        result = self.invoke("rx72n-ethernet", overrides={"RX72N_UART_PORT": "/dev/wrong-device"})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("INIT_REACHED", result.stdout)
        self.assertNotIn("wrong-device", result.stderr)

    def test_wrong_host_stops_before_following_step(self):
        result = self.invoke("rx65n-bg96", hostname="wrong-runner")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("INIT_REACHED", result.stdout)


if __name__ == "__main__":
    unittest.main()

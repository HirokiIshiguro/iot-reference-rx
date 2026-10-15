"""Exercise the actual CI EXIT handler without touching hardware or credentials."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Linux Bash fixture")
class Rx671FleetFinishTests(unittest.TestCase):
    def run_handler(self, *, touched=True, test_status=0, park_status=0, preflight_status=0):
        ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        job = ci.split("\ntest_rx671_wifi_fleet:\n", 1)[1]
        functions = textwrap.dedent(job[job.index("      cleanup_runtime() {"):job.index("      trap finish_fleet EXIT")])
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            artifact = base / "artifacts"
            artifact.mkdir()
            if touched:
                (artifact / "fleet_flash_started.ok").touch()
            script = r'''
set -o pipefail
python3() {
  case "$1" in
    -c) echo preflight >> "$calls"; return "$preflight_status" ;;
    tools/install_normal_boot.py) echo restore >> "$calls"; return "$park_status" ;;
    tools/ci/cleanup_rx671_fleet_runtime.py) echo cleanup >> "$calls"; return 0 ;;
    *) echo "Unexpected fixture command" >&2; return 99 ;;
  esac
}
'''
            script += functions + '\ntrap finish_fleet EXIT\nexit "$test_status"\n'
            env = os.environ.copy()
            env.update({
                "artifact_dir": str(artifact), "normal_bundle": str(base / "normal"),
                "runtime_dir": str(base / "runtime"), "calls": str(base / "calls"),
                "CI_PIPELINE_ID": "123", "CI_JOB_ID": "456", "CI_COMMIT_SHA": "a" * 40,
                "test_status": str(test_status), "park_status": str(park_status),
                "preflight_status": str(preflight_status),
            })
            result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=10)
            calls = (base / "calls").read_text(encoding="utf-8").splitlines() if (base / "calls").exists() else []
            files = {path.name for path in artifact.iterdir()}
            return result.returncode, calls, files

    def test_success_restores_before_cleanup(self):
        status, calls, files = self.run_handler()
        self.assertEqual(status, 0)
        self.assertEqual(calls, ["preflight", "restore", "cleanup"])
        self.assertIn("parked.ok", files)

    def test_failed_observer_status_survives_successful_restore(self):
        status, calls, files = self.run_handler(test_status=7)
        self.assertEqual(status, 7)
        self.assertEqual(calls, ["preflight", "restore", "cleanup"])
        self.assertIn("parked.ok", files)

    def test_failed_restore_retains_private_runtime(self):
        status, calls, files = self.run_handler(park_status=7)
        self.assertEqual(status, 1)
        self.assertEqual(calls, ["preflight", "restore"])
        self.assertIn("park_failed", files)
        self.assertNotIn("parked.ok", files)

    def test_retained_owner_prevents_restore_and_cleanup(self):
        status, calls, files = self.run_handler(preflight_status=1)
        self.assertEqual(status, 1)
        self.assertEqual(calls, ["preflight"])
        self.assertIn("park_failed", files)

    def test_failure_before_hardware_only_cleans_private_runtime(self):
        status, calls, files = self.run_handler(touched=False, test_status=3)
        self.assertEqual(status, 3)
        self.assertEqual(calls, ["cleanup"])
        self.assertNotIn("parked.ok", files)


if __name__ == "__main__":
    unittest.main()

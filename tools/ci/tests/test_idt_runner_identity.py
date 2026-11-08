"""Check the read-only runner identity report without exposing identifiers."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
PWSH = shutil.which("pwsh")


@unittest.skipUnless(os.name == "nt" and PWSH, "Windows PowerShell identity is required")
class RunnerIdentityTests(unittest.TestCase):
    def report(self, *arguments):
        return subprocess.run([PWSH, "-NoProfile", "-File", str(ROOT / "tools/ci/report_runner_identity.ps1"),
                               *arguments], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=20, check=True)

    def test_current_job_reports_only_boolean_or_unknown(self):
        result = self.report()
        lines = result.stdout.splitlines()
        self.assertEqual(5, len(lines))
        self.assertRegex(lines[0], r"^job_sid_sha256=[0-9a-f]{64}$")
        for line in lines[1:]:
            self.assertRegex(line, r"^job_sid_matches_[a-z_]+=(true|false|unknown)$")
        self.assertNotRegex(result.stdout + result.stderr, r"S-1-\d+(?:-\d+)+")
        self.assertNotIn(os.environ.get("USERNAME", "\0"), result.stdout + result.stderr)

    def test_missing_inputs_are_unknown_without_raw_details(self):
        result = self.report("-ServiceName", "missing-service-for-test", "-VenvRoot", "Z:/missing",
                             "-WslVenvRoot", "Z:/missing")
        lines = result.stdout.splitlines()
        self.assertEqual(5, len(lines))
        self.assertRegex(lines[0], r"^job_sid_sha256=[0-9a-f]{64}$")
        self.assertTrue(all(line.endswith("=unknown") for line in lines[1:]))
        self.assertNotRegex(result.stdout + result.stderr, r"S-1-\d+(?:-\d+)+")


if __name__ == "__main__":
    unittest.main()

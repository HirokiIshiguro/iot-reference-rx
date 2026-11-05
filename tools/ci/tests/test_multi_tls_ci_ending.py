"""Execute the real job shell with fake tools; no UART/RFP/network access."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[3]
CI = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
BODY = CI.split("\ntest_rx72n_ether_multi_tls:\n", 1)[1].split("\ntest_rx72n_ether_ota:\n", 1)[0]
SCRIPT = textwrap.dedent(BODY.split("    - |\n", 1)[1].split("\n  artifacts:", 1)[0])
BASH = (str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
        if os.name == "nt" else shutil.which("bash"))


@unittest.skipUnless(BASH and Path(BASH).is_file(), "bash required")
class MultiTlsCiEndingTests(unittest.TestCase):
    def execute(self, monitor_status, ending_status, terminate=False):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            # Shell functions replace only external tools. Execute the full
            # checked-in job script, including PIPESTATUS and EXIT/TERM traps.
            stub = r'''set -e
CI_PROJECT_DIR="$PWD"
CI_COMMIT_SHA=public-fixture
RX72N_TLS_BACKEND=software
RX72N_RFP_CLI=unused
RX72N_RFP_TOOL=unused
RFP_SPEED=500K
RFP_AUTH=unused
RX72N_UART_PORT=unused
RX72N_UART_BAUD_RATE=921600
RX72N_MULTI_TLS_TEST_TIMEOUT=240
RX72N_MULTI_TLS_MIN_OVERLAP_SECONDS=30
exec 9> bench-lease
python() {
  if [ "$1" = tools/ci/monitor_multi_tls.py ]; then
    if [ "$TERMINATE" = 1 ]; then kill -TERM "$$"; fi
    return "$MONITOR_STATUS"
  fi
}
python3() {
  printf '%s\n' "$*" >> ending-calls
  printf 'held\n' >&9 || return 99
  printf '{"end_state":{"fresh_uart_quiet_1s":true}}\n'
  return "$ENDING_STATUS"
}
'''
            (path / "run.sh").write_text(stub + SCRIPT, encoding="utf-8", newline="\n")
            env = {**os.environ, "MONITOR_STATUS": str(monitor_status),
                   "ENDING_STATUS": str(ending_status), "TERMINATE": "1" if terminate else "0"}
            result = subprocess.run([BASH, "--noprofile", "--norc", "run.sh"],
                                    cwd=path, env=env, capture_output=True, text=True, timeout=15)
            calls = (path / "ending-calls").read_text().splitlines()
            self.assertEqual(1, len(calls))
            self.assertIn("--target rx72n-ethernet --source-sha public-fixture --reset-only", calls[0])
            self.assertEqual("held\n", (path / "bench-lease").read_text())
            failed = (path / "artifacts/test_rx72n_ether_multi_tls/end_state_failed").exists()
            return result.returncode, failed

    def test_success_and_failure_both_reset_without_hiding_test_failure(self):
        self.assertEqual((0, False), self.execute(0, 0))
        self.assertEqual((7, False), self.execute(7, 0))

    def test_ending_failure_cannot_pass_and_preserves_original_failure(self):
        self.assertEqual((1, True), self.execute(0, 9))
        self.assertEqual((7, True), self.execute(7, 9))

    def test_term_still_runs_ending_under_open_descriptor(self):
        self.assertEqual((143, False), self.execute(0, 0, terminate=True))

    def test_reset_bundle_is_an_artifact_dependency(self):
        needs = BODY.split("  rules:", 1)[0]
        self.assertRegex(needs, r"job: package_normal_boot_rx72n\s+artifacts: true")


if __name__ == "__main__":
    unittest.main()

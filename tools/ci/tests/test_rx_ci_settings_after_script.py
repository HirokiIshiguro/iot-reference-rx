"""Execute fresh-shell CI recovery with real settings and mocked device commands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from tools.idt.targets import get_target

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Linux Bash fixture")
class AfterScriptSettingsTests(unittest.TestCase):
    def recover(self, kind, *, invalid=False, wrong_host=False, touched=True):
        ci = (ROOT/".gitlab-ci.yml").read_text(encoding="utf-8")
        shared = ci.split("\n.rx_ci_runtime_settings:\n", 1)[1].split("\n.rx72n_linux_hw_job:\n", 1)[0]
        initializer = textwrap.dedent(shared.split("\n  after_script:\n    - |\n", 1)[1])
        name = "test_rx671_wifi_" + ("ota_atomic" if kind == "ota" else "fleet")
        job = ci.split("\n" + name + ":\n", 1)[1]
        recovery = job.split("\n  after_script:\n", 1)[1].split("\n  artifacts:\n", 1)[0]
        # Read the actual reference: do not inject initialization into a job
        # missing it, which would hide the original fresh-shell regression.
        prelude = initializer if "!reference [.rx_ci_runtime_settings, after_script]" in recovery else ""
        body = textwrap.dedent(recovery.split("    - |\n", 1)[1])
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            artifact = base/"artifacts"/name
            artifact.mkdir(parents=True)
            secret = base/".rx671-ota-secrets"
            secret.mkdir()
            (secret/"fixture").write_text("synthetic", encoding="utf-8")
            image = base/"artifacts/build_rx671_wifi/aws_wifi_rx671_ek.mot"
            image.parent.mkdir(parents=True)
            image.write_text("synthetic", encoding="utf-8")
            if touched:
                (artifact/"fleet_flash_started.ok").touch()
            rfp = base/"fixture-rfp"
            rfp.write_text('''#!/usr/bin/env bash
operation=unexpected
for argument; do
  case "$argument" in -erase-chip) operation=erase ;; -p) operation=program ;; esac
done
printf '%s\\n' "$operation" >> "$FIXTURE_CALLS"
[ "$operation" != unexpected ]
''', encoding="utf-8")
            rfp.chmod(0o700)
            mocks = r'''
hostname() { printf '%s\n' "$FIXTURE_HOST"; }
flock() {
  [ "$1" = -w ] && [[ "$2" =~ ^[0-9]+$ ]] || return 97
  echo lock >> "$FIXTURE_CALLS"
}
python3() {
  case "$1" in
    tools/ci/rx_ci_settings.py)
      local output
      output="$(command python3 "$@")" || return "$?"
      printf '%s\n' "$output"
      # Redirect only the lock file into this fixture after real validation;
      # keep every device/CLI/identity export produced by the real resolver.
      printf 'export RX671_WIFI_HARDWARE_LOCK_PATH=%q\n' "$FIXTURE_DIR/lock"
      ;;
    -c) echo ownership >> "$FIXTURE_CALLS" ;;
    tools/install_normal_boot.py) echo install >> "$FIXTURE_CALLS" ;;
    tools/ci/cleanup_rx671_fleet_runtime.py) echo cleanup >> "$FIXTURE_CALLS" ;;
    *) echo 'Unexpected fixture command' >&2; return 99 ;;
  esac
}
'''
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("RX671_", "RX_CI_"))}
            env.update(CI_PROJECT_DIR=str(base), CI_PIPELINE_ID="123", CI_JOB_ID="456", CI_COMMIT_SHA="a"*40,
                       RX_CI_TARGET="rx671-wifi", RX_CI_ENV_PREFIX="RX671_WIFI_",
                       RX671_WIFI_RFP_CLI="", RX671_WIFI_LINUX_RFP_CLI=str(rfp),
                       RX671_WIFI_HARDWARE_LOCK_PATH="", RX671_WIFI_HARDWARE_LOCK_TIMEOUT_SECONDS="",
                       FIXTURE_HOST="wrong-runner" if wrong_host else get_target("rx671-wifi")["hostname"],
                       FIXTURE_DIR=str(base), FIXTURE_CALLS=str(base/"calls"))
            if invalid:
                env["RX671_WIFI_RFP_TOOL"] = "wrong-tool"
            run = subprocess.run(["bash", "-c", "set -e\nset -o pipefail\n" + mocks + prelude + body],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
            calls = (base/"calls").read_text(encoding="utf-8").splitlines() if (base/"calls").exists() else []
            return run, calls, {p.name for p in artifact.iterdir()}, secret.exists()

    def test_ota_fresh_shell_resolves_before_erase_and_program(self):
        run, calls, files, secret = self.recover("ota")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(calls, ["lock", "ownership", "erase", "program"])
        self.assertIn("after_script_parked.ok", files)
        self.assertIn("after_script_cleanup.ok", files)
        self.assertFalse(secret)

    def test_ota_invalid_settings_still_remove_secrets_and_record_failed_park(self):
        run, calls, files, secret = self.recover("ota", invalid=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(calls, [])
        self.assertIn("after_script_park_failed", files)
        self.assertIn("after_script_cleanup.ok", files)
        self.assertFalse(secret)

    def test_ota_wrong_host_still_removes_secrets_without_device_commands(self):
        run, calls, files, secret = self.recover("ota", wrong_host=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(calls, [])
        self.assertIn("after_script_park_failed", files)
        self.assertFalse(secret)

    def test_fleet_fresh_shell_restores_then_cleans_private_runtime(self):
        run, calls, files, _ = self.recover("fleet")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(calls, ["lock", "ownership", "install", "cleanup"])
        self.assertIn("after_script_parked.ok", files)

    def test_fleet_invalid_settings_retain_touched_runtime_without_device_commands(self):
        _, calls, files, _ = self.recover("fleet", invalid=True)
        self.assertEqual(calls, [])
        self.assertIn("after_script_park_failed", files)
        self.assertNotIn("parked.ok", files)

    def test_fleet_untouched_runtime_can_be_cleaned_after_invalid_settings(self):
        _, calls, files, _ = self.recover("fleet", invalid=True, touched=False)
        self.assertEqual(calls, ["cleanup"])
        self.assertNotIn("after_script_park_failed", files)


if __name__ == "__main__":
    unittest.main()

"""Primary normal hardware jobs use signed bundles before existing provisioning."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[3]
CI = (ROOT/".gitlab-ci.yml").read_text(encoding="utf-8")
JOBS = {
    "test_rx72n_ether_mqtt": ("rx72n", "rx72n-ethernet"),
    "test_rx72n_ether_ota": ("rx72n", "rx72n-ethernet"),
    "test_rx65n_bg96_mqtt": ("rx65n", "rx65n-bg96"),
    "test_rx65n_bg96_ota": ("rx65n", "rx65n-bg96"),
    "test_rx671_wifi": ("rx671", "rx671-wifi"),
    "flash_rx671_wifi": ("rx671", "rx671-wifi"),
}


def job(name):
    start = re.search(r"(?m)^"+re.escape(name)+r":\n", CI)
    if start is None:
        raise AssertionError("Missing job: "+name)
    following = re.search(r"(?m)^[A-Za-z0-9_.-]+:\s*$", CI[start.end():])
    return CI[start.start():start.end()+following.start() if following else len(CI)]


def installation(body):
    match = re.search(r"(?m)^      python3 tools/install_normal_boot\.py \\\n.*?^      fi\n", body, re.S|re.M)
    if match is None:
        raise AssertionError("Missing guarded normal install command")
    return textwrap.dedent(match.group())


class NormalBootInstallCiTests(unittest.TestCase):
    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "Portable Bash fixture requires Linux")
    def test_installer_failure_status_stops_before_following_hardware_steps(self):
        for name,(suffix,target) in JOBS.items():
            with self.subTest(job=name), tempfile.TemporaryDirectory() as temporary:
                directory=Path(temporary)
                # The only executable command is this fixture function; no device
                # installer, Python module, programmer or credential tool runs.
                code='python3() { printf "%s\\n" "$@" > "$artifact_dir/arguments"; return 7; }\n'
                code+=installation(job(name))
                code+='touch "$artifact_dir/unreachable"\n'
                result=subprocess.run([shutil.which("bash"),"-c",code],capture_output=True,text=True,
                    env=dict(os.environ,artifact_dir=temporary,CI_PROJECT_DIR="/fixture source",CI_COMMIT_SHA="a"*40),timeout=5)
                self.assertEqual(result.returncode,7,result.stderr)
                self.assertFalse((directory/"unreachable").exists())
                arguments=(directory/"arguments").read_text().splitlines()
                self.assertEqual(arguments[arguments.index("--target")+1],target)
                self.assertEqual(arguments[arguments.index("--bundle")+1],"/fixture source/artifacts/normal_boot_"+suffix)


if __name__ == "__main__":
    unittest.main()

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
    def test_include_and_matching_bundle_artifact_dependencies(self):
        includes = CI.split("include:\n", 1)[1].split("\nstages:\n", 1)[0]
        self.assertEqual(includes.count("  - local: /tools/ci/normal_boot_jobs.yml\n"), 1)
        entries = []
        for entry in re.split(r"(?m)^  - ", includes):
            fields = {}
            for line in entry.splitlines():
                key, separator, value = line.strip().partition(":")
                if separator:
                    fields[key] = value.strip()
            entries.append(fields)
        remote = [entry for entry in entries if entry.get("project") == "oss/infra/hardware-config"]
        self.assertEqual(len(remote), 1)
        self.assertEqual(remote[0].get("file"), "/templates/windows_ccrx_host_lease.yml")
        self.assertRegex(remote[0].get("ref", ""), r"^[0-9a-f]{40}$")
        for name,(suffix,target) in JOBS.items():
            with self.subTest(job=name):
                body=job(name)
                self.assertRegex(body,r"(?m)^    - job: package_normal_boot_"+suffix+r"\n      artifacts: true$")
                command=installation(body)
                self.assertIn('--bundle "$CI_PROJECT_DIR/artifacts/normal_boot_'+suffix+'"',command)
                self.assertIn("--target "+target,command)
                self.assertIn('--source-sha "$CI_COMMIT_SHA"',command)
                self.assertIn('status="${PIPESTATUS[0]}"',command)
                self.assertEqual(body.count("tools/install_normal_boot.py"),1)
                self.assertNotIn("-erase-chip",body)
                self.assertNotIn("tools/test_uart_download_rx72n.py",body)
                self.assertNotIn("--action flash-bootloader",body)
                self.assertNotIn("--action download-rsu",body)
                self.assertNotIn('-p -v -reset -noquery "$mot"',body)

    def test_rx65_canonical_uart_fallback_keeps_explicit_overrides_and_selected_port_artifact(self):
        for name in ("test_rx65n_bg96_mqtt","test_rx65n_bg96_ota"):
            with self.subTest(job=name):
                body=job(name)
                self.assertIn('uart_port="${RX65N_BG96_UART_PORT:-${COMMAND_PORT:-}}"',body)
                self.assertIn('if [ -z "$uart_port" ]; then',body)
                self.assertIn("get_target('rx65n-bg96')['uart']",body)
                self.assertIn('> "$artifact_dir/selected_uart_port.txt"',body)
                self.assertNotIn("--selected-uart-out",body)
                self.assertNotIn("export RX65N_BG96_UART_PORT=",body)

    def test_existing_credentials_tsip_observers_and_resets_follow_installation(self):
        expected={
            "test_rx72n_ether_mqtt":("tools/provision_rx72n.py","tools/provision_tsip_over_uart.py","tools/test_mqtt_rx72n.py"),
            "test_rx72n_ether_ota":("tools/provision_rx72n.py","tools/provision_tsip_over_uart.py","tools/test_ota.py"),
            "test_rx65n_bg96_mqtt":("--action provision-mqtt","tools/provision_tsip_over_uart.py","--action reset-app","--action verify-mqtt"),
            "test_rx65n_bg96_ota":("--action provision-mqtt","tools/provision_tsip_over_uart.py","tools/bg96_ota_prepare.py","tools/bg96_ota_monitor.py"),
            "test_rx671_wifi":("reset_cmd=","tools/ci/test_rx671_wifi_uart.py"),
        }
        for name,steps in expected.items():
            with self.subTest(job=name):
                body=job(name)
                start=body.index("tools/install_normal_boot.py")
                for step in steps:
                    self.assertGreater(body.index(step,start),start)
        for name in ("test_rx72n_ether_mqtt","test_rx72n_ether_ota"):
            self.assertIn("--format",job(name))
            self.assertIn("--codesigner-cert",job(name))
            self.assertIn("--reset-after-open",job(name))

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

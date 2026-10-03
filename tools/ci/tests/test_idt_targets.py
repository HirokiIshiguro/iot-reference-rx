"""Target identity and runtime network boundaries; no cloud or board access."""
import importlib.util
import json
import ntpath
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.idt.targets import (get_target, target_fingerprint, device_template, target_ids,
                               hardware_end_state_status)
from tools.idt.prepare_target_network import network_values, prepare

ROOT = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = ROOT / "tools/idt/build_transport.sh"


class TargetIdentityTests(unittest.TestCase):
    def test_default_keeps_existing_rx72n_identity(self):
        with patch.dict(os.environ, {}, clear=True):
            target = get_target()
        self.assertEqual("rx72n-ethernet", target["id"])
        self.assertEqual("OBE110008", target["e2lite"])
        self.assertEqual("/tmp/e2lite-rfp-cli.lock.d/rx72n-device-01.lock", target["bench_lock"])

    def test_unknown_identity_cannot_fall_back_to_other_board(self):
        with self.assertRaises(ValueError):
            get_target("rx65n-ethernet")

    def test_only_none_uses_environment_or_default(self):
        with patch.dict(os.environ, {"IDT_TARGET": "rx671-wifi"}, clear=True):
            self.assertEqual("rx671-wifi", get_target(None)["id"])
            self.assertEqual("rx65n-bg96", get_target("rx65n-bg96")["id"])
            for value in ("", False, 0, [], " "):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    get_target(value)
        with patch.dict(os.environ, {"IDT_TARGET": ""}, clear=True), self.assertRaises(ValueError):
            get_target(None)

    def test_guard_identities_unique_and_fingerprints_include_programmer(self):
        identities = []
        for name in target_ids():
            target = get_target(name)
            identities.append((target["hostname"], target["uart"], target["e2lite"]))
            changed = dict(target, e2lite="OTHER")
            self.assertNotEqual(target_fingerprint(target), target_fingerprint(changed))
            reversed_order = dict(reversed(tuple(target.items())))
            self.assertEqual(target_fingerprint(target), target_fingerprint(reversed_order))
            self.assertEqual(target, get_target(name))
        self.assertEqual(len(set(identities)), 3)

    def test_native_features_describe_actual_connections(self):
        for name, wifi, cellular in (("rx72n-ethernet", "No", "No"),
                                      ("rx65n-bg96", "No", "Yes"),
                                      ("rx671-wifi", "Yes", "No")):
            pool = device_template(get_target(name), "ota-mqtt", "/private/public.hex")[0]
            features = {feature["name"]: feature["value"] for feature in pool["features"]}
            self.assertEqual(wifi, features["Wifi"])
            self.assertEqual(cellular, features["Cellular"])
            self.assertEqual("Onboard", features["KeyProvisioning"])
            self.assertEqual("No", pool["devices"][0]["secureElementConfig"]["preProvisioned"])

    def test_offline_plans_for_every_target_require_no_aws_or_control(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("AWS_", "IDT_", "RX671_EK_WIFI"))}
            for name in target_ids():
                dest = Path(folder) / name
                result = subprocess.run([sys.executable, str(ROOT / "tools/idt/run_idt.py"),
                                         "--target", name, "--scope", "transport", "--plan-only", "--output", str(dest)],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                plan = json.loads((dest / "plan.json").read_text())
                self.assertEqual("not_run", plan["status"])
                self.assertEqual(name, plan["target_id"])
                self.assertEqual("not-established", plan["qualification"])
                self.assertFalse((dest / "FRQ_Report.xml").exists())

    def test_existing_ci_end_state_requires_observations_without_claiming_pin_measurement(self):
        for name in target_ids():
            with self.subTest(target=name):
                target = get_target(name)
                status = hardware_end_state_status(target)
                self.assertTrue(status["supported"])
                self.assertEqual("reset_command_and_uart_quiet", status["status"])
                self.assertEqual("unverified", status["physical_reset_hold"])
                self.assertEqual(["reset_command_exit_zero", "fresh_uart_quiet_1s"],
                                 status["required_observations"])


class NetworkInputTests(unittest.TestCase):
    def test_established_board_inputs_only_and_values_not_printed(self):
        wifi = get_target("rx671-wifi")
        values = network_values(wifi, {"RX671_EK_WIFI_SSID": "unit-network", "RX671_EK_WIFI_PASSPHRASE": "test-only-pass"})
        self.assertEqual("unit-network", values["IDT_WIFI_SSID"])
        with self.assertRaises(RuntimeError):
            network_values(wifi, {"WIFI_SSID": "wrong-shared-name", "WIFI_PASSWORD": "test-only-pass"})
        cellular = network_values(get_target("rx65n-bg96"), {"AWS_IOT_CELLULAR_APN_CK_RX65N_01": "unit.invalid"})
        self.assertEqual("0", cellular["IDT_CELLULAR_APN_AUTH"])
        self.assertEqual("", cellular["IDT_CELLULAR_APN_USER"])

    def test_invalid_credentials_are_rejected_without_echoing_values(self):
        for env in ({"RX671_EK_WIFI_SSID": "unit", "RX671_EK_WIFI_PASSPHRASE": "short"},
                    {"RX671_EK_WIFI_SSID": "a" * 33, "RX671_EK_WIFI_PASSPHRASE": "test-only-pass"},
                    {"RX671_EK_WIFI_SSID": "unit\nnetwork", "RX671_EK_WIFI_PASSPHRASE": "test-only-pass"}):
            with self.assertRaises(ValueError):
                network_values(get_target("rx671-wifi"), env)
        with self.assertRaises(ValueError):
            network_values(get_target("rx65n-bg96"), {"AWS_IOT_CELLULAR_APN_CK_RX65N_01": "unit.invalid",
                           "AWS_IOT_CELLULAR_APN_AUTH_CK_RX65N_01": "99"})

    def test_original_checkout_refused_before_network_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, runtime = root / "original", root / "runtime"
            (original / "Test/include").mkdir(parents=True)
            (original / "Test/include/test_param_config.h").write_text("/* inert */")
            runtime.mkdir()
            with patch.dict(os.environ, {"IDT_RUNTIME_DIR": str(runtime), "IDT_SOURCE_PATH": str(original)}):
                with self.assertRaisesRegex(RuntimeError, "original checkout"):
                    prepare(str(original), get_target("rx671-wifi"))
            self.assertFalse((original / "Test/include/idt_network_config.h").exists())

    def test_hex_psk_exceeding_firmware_passphrase_bound_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "8–63 bytes"):
            network_values(get_target("rx671-wifi"),
                           {"RX671_EK_WIFI_SSID": "unit-network", "RX671_EK_WIFI_PASSPHRASE": "a" * 64})


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires POSIX bash")
class BuildPackagingArgumentTests(unittest.TestCase):
    def test_real_shell_expands_artifact_paths_for_every_target(self):
        # Execute the production shell; tool stubs only record argv. No key,
        # compiler, cloud service or device is accessed by this regression test.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source with spaces"
            source.mkdir()
            bin_dir = root / "bin"
            bin_dir.mkdir()
            capture = root / "arguments.jsonl"
            commands = {
                "wslpath": '#!/bin/sh\nprintf "%s\\n" "$2"\n',
                "pwsh": "#!/bin/sh\nexit 0\n",
                "linux-python": (
                    "#!/usr/bin/env python3\nimport pathlib,subprocess,sys\n"
                    "if pathlib.Path(sys.argv[1]).name == 'targets.py':\n"
                    f" sys.exit(subprocess.call([sys.executable, {str(ROOT / 'tools/idt/targets.py')!r}, *sys.argv[2:]]))\n"
                ),
                "windows-python": (
                    "#!/usr/bin/env python3\nimport json,os,sys\n"
                    "with open(os.environ['IDT_TEST_ARGUMENTS'], 'a') as output:\n"
                    " output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                ),
            }
            for name, text in commands.items():
                path = bin_dir / name
                path.write_text(text)
                path.chmod(0o700)
            env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                       IDT_LINUX_PYTHON=str(bin_dir / "linux-python"),
                       IDT_WINDOWS_PWSH=str(bin_dir / "pwsh"),
                       IDT_WINDOWS_PYTHON=str(bin_dir / "windows-python"),
                       IDT_RUNTIME_DIR=str(root / "run-test" / "execution"),
                       IDT_WORKSPACE_ROOT="C:/idt-test", IDT_E2STUDIO_CLI="C:/inert/e2studioc.exe",
                       IDT_PROVENANCE_FILE="C:/inert/provenance.json", IDT_SCOPE="pkcs11",
                       IDT_TEST_ARGUMENTS=str(capture))
            for target_id in target_ids():
                with self.subTest(target=target_id):
                    capture.unlink(missing_ok=True)
                    env['IDT_TARGET'] = target_id
                    completed = subprocess.run(['bash', str(BUILD_SCRIPT), str(source)], env=env,
                                               capture_output=True, text=True, timeout=15)
                    self.assertEqual(0, completed.returncode, completed.stderr)
                    calls = [json.loads(line) for line in capture.read_text().splitlines()]
                    target = get_target(target_id)
                    self.assertEqual(2, len(calls))
                    self.assertEqual(str(source / target['packager']), calls[0][0])
                    for flag, extension in (('--mot', 'mot'), ('--output', 'rsu')):
                        actual = calls[0][calls[0].index(flag) + 1]
                        expected = source / 'artifacts/idt/build_transport' / f"{target['artifact_basename']}.{extension}"
                        self.assertEqual(ntpath.normpath(str(expected)), ntpath.normpath(actual))
                    self.assertEqual(str(source / target['signing_key']), calls[0][calls[0].index('--key') + 1])


if __name__ == "__main__":
    unittest.main()

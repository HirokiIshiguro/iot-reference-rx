"""Target identity and runtime network boundaries; no cloud or board access."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.idt.targets import (get_target, target_fingerprint, device_template, target_ids,
                               hardware_end_state_status)
from tools.idt.prepare_target_network import network_values, prepare

ROOT = Path(__file__).resolve().parents[3]


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


if __name__ == "__main__":
    unittest.main()

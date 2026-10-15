"""Public runtime compatibility tests; no hardware, builds, credentials or network."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shlex
import unittest
from unittest.mock import patch

from tools.ci import rx_ci_settings as settings
from tools.idt.targets import get_target

TARGETS = {"rx72n-ethernet": "RX72N_", "rx65n-bg96": "RX65N_BG96_", "rx671-wifi": "RX671_WIFI_"}
SUFFIXES = {"UART_PORT", "UART_BAUD_RATE", "RFP_CLI", "RFP_TOOL", "RFP_DEVICE", "RFP_INTERFACE",
            "RFP_SPEED", "RFP_AUTH_ID", "RUNNER_HOSTNAME", "HARDWARE_LOCK_PATH",
            "HARDWARE_LOCK_TIMEOUT_SECONDS", "FLEET_TEST_TIMEOUT_SECONDS"}


class RxCiSettingsTests(unittest.TestCase):
    def test_actual_yaml_defaults_resolve_with_public_inventory_inputs(self):
        # Exercise source defaults as well as the resolver's built-in defaults.
        # These are public bench assignments, never live credential variables.
        names = {"rx72n-ethernet": ("E2L_SERIAL_ENVISION_KIT_RX72N_ECN1", "UART_PORT_ENVISION_KIT_RX72N_CN6_RPI1"),
                 "rx65n-bg96": ("E2L_SERIAL_CK_RX65N_RPI3", "UART_PORT_CK_RX65N_RPI3"),
                 "rx671-wifi": ("E2L_SERIAL_EK_RX671_E2OB_RPI1", "UART_PORT_EK_RX671_SCI6_RPI1")}
        inventory = {}
        keys = set()
        for target_id, (serial, uart) in names.items():
            target = get_target(target_id)
            inventory.update({serial: target["e2lite"], uart: target["uart"]})
            keys.update(settings.normalize(target_id, {}))
        text = (Path(__file__).resolve().parents[3]/".gitlab-ci.yml").read_text(encoding="utf-8")
        block = text.split("\nvariables:\n", 1)[1].split("\nworkflow:\n", 1)[0]
        inputs = {}
        for match in re.finditer(r'^  ([A-Z0-9_]+):\s*("[^\n]*")\s*$', block, re.M):
            key, value = match.groups()
            if key in keys:
                inputs[key] = json.loads(value)
        for _ in range(4):
            values = {**inventory, **inputs}
            inputs = {key: re.sub(r'\$\{([A-Z0-9_]+)\}', lambda m: values.get(m.group(1), m.group()), value)
                      for key, value in inputs.items()}
        for target_id, prefix in TARGETS.items():
            with self.subTest(target=target_id):
                result = settings.normalize(target_id, inputs)
                target = get_target(target_id)
                self.assertEqual(target["uart"], result[prefix+"UART_PORT"])
                self.assertEqual("e2l:"+target["e2lite"], result[prefix+"RFP_TOOL"])
                self.assertEqual(target["rfp_speed"], result[prefix+"RFP_SPEED"])
                self.assertEqual(target["bench_lock"], result[prefix+"HARDWARE_LOCK_PATH"])

    def test_defaults_bind_all_three_physical_targets_and_keep_legacy_exports(self):
        for target_id, prefix in TARGETS.items():
            with self.subTest(target=target_id):
                target = get_target(target_id)
                result = settings.normalize(target_id, {})
                expected = {"UART_PORT": target["uart"], "UART_BAUD_RATE": str(target["baud"]),
                            "RFP_CLI": "./tools/rfp_cli_locked.sh", "RFP_TOOL": "e2l:" + target["e2lite"],
                            "RFP_DEVICE": target["rfp_device"], "RFP_INTERFACE": "fine", "RFP_SPEED": target["rfp_speed"],
                            "RFP_AUTH_ID": "F" * 32, "RUNNER_HOSTNAME": target["hostname"],
                            "HARDWARE_LOCK_PATH": target["bench_lock"],
                            "HARDWARE_LOCK_TIMEOUT_SECONDS": "0" if target_id == "rx65n-bg96" else "3600",
                            "FLEET_TEST_TIMEOUT_SECONDS": "600" if target_id == "rx72n-ethernet" else "900"}
                self.assertEqual(SUFFIXES, set(expected))
                for suffix, value in expected.items():
                    self.assertEqual(value, result[prefix + suffix])
                self.assertEqual(result[prefix + "RFP_CLI"], result[prefix + "LINUX_RFP_CLI"])
        rx72n = settings.normalize("rx72n-ethernet", {})
        for old, new in (("RX72N_LINUX_UART_PORT", "RX72N_UART_PORT"),
                         ("RX72N_LINUX_UART_BAUD_RATE", "RX72N_UART_BAUD_RATE"),
                         ("RX72N_LINUX_RFP_TOOL", "RX72N_RFP_TOOL"),
                         ("RFP_SPEED", "RX72N_RFP_SPEED"), ("RFP_AUTH", "RX72N_RFP_AUTH_ID"),
                         ("RX72N_RPI1_HARDWARE_LOCK_PATH", "RX72N_HARDWARE_LOCK_PATH"),
                         ("RX72N_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS", "RX72N_HARDWARE_LOCK_TIMEOUT_SECONDS"),
                         ("RX72N_FLEET_TEST_TIMEOUT", "RX72N_FLEET_TEST_TIMEOUT_SECONDS")):
            self.assertEqual(rx72n[new], rx72n[old])
        rx671 = settings.normalize("rx671-wifi", {})
        self.assertEqual(rx671["RX671_WIFI_HARDWARE_LOCK_PATH"], rx671["RX671_RPI1_HARDWARE_LOCK_PATH"])
        self.assertEqual(rx671["RX671_WIFI_HARDWARE_LOCK_TIMEOUT_SECONDS"], rx671["RX671_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS"])

    def test_old_only_and_preferred_only_settings_export_both_spellings(self):
        for target_id, prefix in TARGETS.items():
            with self.subTest(target=target_id):
                custom = "/reviewed local/rfp-wrapper.sh"
                old = settings.normalize(target_id, {prefix + "LINUX_RFP_CLI": custom})
                new = settings.normalize(target_id, {prefix + "RFP_CLI": custom})
                self.assertEqual(old, new)
                self.assertEqual(custom, new[prefix + "RFP_CLI"])
                self.assertEqual(custom, new[prefix + "LINUX_RFP_CLI"])
                configured = settings.normalize(target_id, {prefix + "HARDWARE_LOCK_TIMEOUT_SECONDS": "42",
                                                            prefix + "FLEET_TEST_TIMEOUT_SECONDS": "1200"})
                self.assertEqual("42", configured[prefix + "HARDWARE_LOCK_TIMEOUT_SECONDS"])
                self.assertEqual("1200", configured[prefix + "FLEET_TEST_TIMEOUT_SECONDS"])
        old = settings.normalize("rx72n-ethernet", {"RX72N_FLEET_TEST_TIMEOUT": "1200",
                                                    "RX72N_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS": "42"})
        self.assertEqual("1200", old["RX72N_FLEET_TEST_TIMEOUT_SECONDS"])
        self.assertEqual("42", old["RX72N_HARDWARE_LOCK_TIMEOUT_SECONDS"])

    def test_preferred_can_replace_yaml_default_but_not_distinct_explicit_legacy_override(self):
        for target_id, prefix in TARGETS.items():
            with self.subTest(target=target_id):
                result = settings.normalize(target_id, {prefix + "RFP_CLI": "/new-wrapper",
                                                        prefix + "LINUX_RFP_CLI": "./tools/rfp_cli_locked.sh"})
                self.assertEqual("/new-wrapper", result[prefix + "LINUX_RFP_CLI"])
                result = settings.normalize(target_id, {prefix + "RFP_CLI": "/same-wrapper",
                                                        prefix + "LINUX_RFP_CLI": "/same-wrapper"})
                self.assertEqual("/same-wrapper", result[prefix + "RFP_CLI"])
                with self.assertRaisesRegex(ValueError, "Conflicting"):
                    settings.normalize(target_id, {prefix + "RFP_CLI": "/new-wrapper",
                                                   prefix + "LINUX_RFP_CLI": "/explicit-other-wrapper"})
        result = settings.normalize("rx72n-ethernet", {"RX72N_FLEET_TEST_TIMEOUT_SECONDS": "1200",
                                                      "RX72N_FLEET_TEST_TIMEOUT": "600"})
        self.assertEqual("1200", result["RX72N_FLEET_TEST_TIMEOUT"])
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            settings.normalize("rx72n-ethernet", {"RX72N_FLEET_TEST_TIMEOUT_SECONDS": "1200",
                                                 "RX72N_FLEET_TEST_TIMEOUT": "900"})

    def test_wrong_physical_identity_is_rejected_for_every_board_without_disclosing_values(self):
        sentinel = "SYNTHETIC-DO-NOT-DISCLOSE"
        physical = ("UART_PORT", "RFP_TOOL", "RFP_DEVICE", "RFP_INTERFACE", "RFP_SPEED", "RFP_AUTH_ID",
                    "RUNNER_HOSTNAME", "HARDWARE_LOCK_PATH", "UART_BAUD_RATE")
        for target_id, prefix in TARGETS.items():
            for suffix in physical:
                with self.subTest(target=target_id, suffix=suffix):
                    with self.assertRaises(ValueError) as failure:
                        settings.normalize(target_id, {prefix + suffix: sentinel})
                    self.assertNotIn(sentinel, str(failure.exception))
        for key in ("RX72N_LINUX_UART_PORT", "RX72N_LINUX_RFP_TOOL", "RFP_SPEED", "RFP_AUTH",
                    "RX72N_RPI1_HARDWARE_LOCK_PATH"):
            with self.subTest(legacy=key), self.assertRaises(ValueError) as failure:
                settings.normalize("rx72n-ethernet", {key: sentinel})
            self.assertNotIn(sentinel, str(failure.exception))

    def test_integer_policy_is_nonnegative_lock_and_positive_baud_and_fleet(self):
        for target_id, prefix in TARGETS.items():
            with self.subTest(target=target_id):
                self.assertEqual("0", settings.normalize(target_id, {prefix + "HARDWARE_LOCK_TIMEOUT_SECONDS": "0"})[
                    prefix + "HARDWARE_LOCK_TIMEOUT_SECONDS"])
                for suffix, values in (("HARDWARE_LOCK_TIMEOUT_SECONDS", ("-1", "1.5", "invalid")),
                                       ("FLEET_TEST_TIMEOUT_SECONDS", ("0", "-1", "invalid")),
                                       ("UART_BAUD_RATE", ("0", "115200", "invalid"))):
                    for value in values:
                        with self.subTest(suffix=suffix, value=value), self.assertRaises(ValueError):
                            settings.normalize(target_id, {prefix + suffix: value})
                value = settings.normalize(target_id, {prefix + "UART_BAUD_RATE": "0921600"})
                self.assertEqual("921600", value[prefix + "UART_BAUD_RATE"])

    def test_only_fixed_public_keys_are_read_and_credentials_and_runner_flags_are_not_exported(self):
        class PublicOnly:
            def get(self, key, default=""):
                if not any(key.startswith(prefix) for prefix in TARGETS.values()) and key not in ("RFP_SPEED", "RFP_AUTH", "RX671_RPI1_HARDWARE_LOCK_PATH", "RX671_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS"):
                    raise AssertionError("Unexpected environment read")
                if any(fragment in key for fragment in ("PRIVATE_KEY", "CERT_PEM", "PASSPHRASE", "RUNNER_TAG", "CLEANUP_RESOURCES")):
                    raise AssertionError("Non-runtime setting read")
                return default
        for target_id, prefix in TARGETS.items():
            result = settings.normalize(target_id, PublicOnly())
            expected = settings.normalize(target_id, {})
            self.assertEqual(expected, result)
            environment = {"SYNTHETIC_SECRET": "never-export", prefix + "RUNNER_TAG": "preserve-selection",
                           prefix + "FLEET_CLEANUP_RESOURCES": "false"}
            self.assertEqual(expected, settings.normalize(target_id, environment))
            self.assertNotIn("never-export", settings.shell_exports(result))

    def test_cli_shell_quoting_roundtrips_without_executing_arbitrary_input(self):
        path = "/synthetic tool's path/$(do-not-execute); `also-not-execute`"
        for target_id, prefix in TARGETS.items():
            with self.subTest(target=target_id):
                environment = {prefix + "RFP_CLI": path, "DO_NOT_EXPORT": "synthetic-secret"}
                stdout = io.StringIO()
                with patch.dict(os.environ, environment, clear=True), redirect_stdout(stdout):
                    self.assertEqual(0, settings.main(["--target", target_id]))
                parsed = {}
                for line in stdout.getvalue().splitlines():
                    words = shlex.split(line)
                    self.assertEqual("export", words[0])
                    self.assertEqual(2, len(words))
                    key, value = words[1].split("=", 1)
                    parsed[key] = value
                self.assertEqual(settings.normalize(target_id, environment), parsed)
                self.assertEqual(path, parsed[prefix + "RFP_CLI"])
                self.assertNotIn("synthetic-secret", stdout.getvalue())

    def test_empty_inputs_fall_back_and_errors_never_include_input_values(self):
        self.assertEqual(settings.normalize("rx72n-ethernet", {}),
                         settings.normalize("rx72n-ethernet", {"RX72N_UART_PORT": " ", "RX72N_LINUX_UART_PORT": ""}))
        sentinel = "SYNTHETIC-DO-NOT-DISCLOSE"
        with self.assertRaises(ValueError) as failure:
            settings.normalize(sentinel, {})
        self.assertNotIn(sentinel, str(failure.exception))
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"RX72N_UART_PORT": sentinel}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(1, settings.main(["--target", "rx72n-ethernet"]))
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("RX CI settings validation failed\n", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

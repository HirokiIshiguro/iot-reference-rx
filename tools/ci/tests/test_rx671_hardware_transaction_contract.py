from __future__ import annotations

import unittest
import re
from pathlib import Path

from tools.idt import cleanup_budget


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str | None = None) -> str:
    match = re.search(r"(?m)^" + re.escape(name) + r":\n", ci)
    if match is None:
        raise AssertionError("Missing CI job: " + name)
    following = re.search(r"(?m)^[A-Za-z0-9_.-]+:[ \t]*\n", ci[match.end():])
    end = match.end() + following.start() if following else len(ci)
    return ci[match.start():end]


class Rx671HardwareTransactionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

    def test_rpi1_jobs_hold_the_standalone_benchmark_lock(self) -> None:
        template = job_block(
            self.ci, ".rx671_wifi_linux_hw_job", ".aws_cli_windows_job"
        )

        self.assertIn(
            'RX671_RPI1_HARDWARE_LOCK_PATH: '
            '"/tmp/ek-rx671-rpi1-hardware.lock"',
            self.ci,
        )
        self.assertIn('exec 9>>"${RX671_RPI1_HARDWARE_LOCK_PATH}"', template)
        self.assertIn(
            'flock -w "${RX671_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS}" 9',
            template,
        )
        self.assertGreater(
            template.index("exec 9>"), template.index("python -m pip install")
        )

    def test_uart_observation_reflashes_inside_the_job_lock(self) -> None:
        job = job_block(self.ci, "test_rx671_wifi", "test_rx72n_ether_mqtt")

        ordered_tokens = (
            "Atomic RX671 signed normal install before UART observation",
            "tools/install_normal_boot.py",
            'initial_chip_erase.log',
            'if [ "$status" -ne 0 ]',
            "tools/ci/test_rx671_wifi_uart.py",
        )
        positions = [job.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))

    def test_normal_flash_uses_signed_bundle_and_preserves_command_failure(self) -> None:
        job = job_block(self.ci, "flash_rx671_wifi", "flash_rx72n_ether")
        install = job.index("tools/install_normal_boot.py")
        self.assertIn('--bundle "$CI_PROJECT_DIR/artifacts/normal_boot_rx671"', job)
        self.assertIn('--target rx671-wifi', job)
        self.assertIn('exit "$status"', job[install:])
        self.assertNotIn('-erase-chip', job)
        self.assertNotIn('-p -v -reset -noquery', job)

    def test_both_split_jobs_extend_the_locked_template(self) -> None:
        flash = job_block(self.ci, "flash_rx671_wifi", "flash_rx72n_ether")
        test = job_block(self.ci, "test_rx671_wifi", "test_rx72n_ether_mqtt")

        for job in (flash, test):
            self.assertIn("- .rx671_wifi_linux_hw_job", job)

    def test_nightly_matrix_templates_isolate_rx671_builds(self) -> None:
        non_rx671_templates = (
            job_block(
                self.ci,
                ".nightly_matrix_rx72n",
                ".nightly_matrix_rx65n_bg96",
            ),
            job_block(
                self.ci,
                ".nightly_matrix_rx65n_bg96",
                ".nightly_matrix_rx671_wifi",
            ),
            job_block(
                self.ci,
                ".nightly_matrix_rx72n_stabilizing",
                ".nightly_matrix_rx65n_bg96_stabilizing",
            ),
            job_block(
                self.ci,
                ".nightly_matrix_rx65n_bg96_stabilizing",
                ".nightly_matrix_rx671_wifi_stabilizing",
            ),
        )
        rx671_templates = (
            job_block(
                self.ci,
                ".nightly_matrix_rx671_wifi",
                ".nightly_matrix_stabilizing_trigger",
            ),
            job_block(
                self.ci,
                ".nightly_matrix_rx671_wifi_stabilizing",
                "matrix_rx671_wifi_network",
            ),
        )

        for template in non_rx671_templates:
            self.assertIn('RUN_RX671_WIFI_BUILD: "false"', template)
            self.assertIn('RUN_RX671_BOOTLOADER_BUILD: "false"', template)
        for template in rx671_templates:
            self.assertIn('RUN_RX671_WIFI_BUILD: "true"', template)
            self.assertIn('RUN_RX671_BOOTLOADER_BUILD: "true"', template)

    def test_nightly_routes_both_rx671_tls13_0rtt_variants(self) -> None:
        software_template = job_block(
            self.ci,
            ".matrix_rx671_software_lanbench",
            "matrix_rx671_wifi_software_lanbench",
        )
        software = job_block(
            self.ci,
            "matrix_rx671_wifi_software_tls13_resumption_0rtt",
            ".matrix_rx671_lanbench",
        )
        tsip = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_tls13_resumption_0rtt",
            "matrix_rx72n_ether_software_mqtt",
        )

        self.assertIn(
            'RX671_SOFTWARE_BENCHMARK_WIFI_SSID: "$RX671_EK_WIFI_SSID"',
            software_template,
        )
        self.assertIn(
            "RX671_SOFTWARE_BENCHMARK_WIFI_PASSPHRASE: "
            '"$RX671_EK_WIFI_PASSPHRASE"',
            software_template,
        )
        self.assertIn(
            "RX671_SOFTWARE_BENCHMARK_WIFI_PASSWORD: "
            '"$RX671_EK_WIFI_PASSWORD"',
            software_template,
        )
        self.assertIn("extends: .matrix_rx671_software_lanbench", software)
        self.assertIn('RX671_SOFTWARE_BENCHMARK_PROFILE: "tls13-0rtt"', software)
        self.assertIn("extends: .matrix_rx671_lanbench", tsip)
        self.assertIn('RX671_BENCHMARK_PROFILE: "tls13-0rtt"', tsip)

    def test_nightly_routes_rx671_fleet_as_stabilizing_with_cleanup_inputs(self) -> None:
        template = job_block(
            self.ci,
            ".nightly_matrix_rx671_wifi_stabilizing",
            "matrix_rx671_wifi_network",
        )
        fleet = job_block(
            self.ci,
            "matrix_rx671_wifi_fleet",
            ".matrix_rx671_software_lanbench",
        )

        self.assertIn("extends: .nightly_matrix_stabilizing_trigger", template)
        self.assertIn("resource_group: nightly-matrix-rx671-wifi", template)
        self.assertIn("extends: .nightly_matrix_rx671_wifi_stabilizing", fleet)
        self.assertIn('RX671_WIFI_TEST_SCOPE: "fleet"', fleet)
        self.assertIn('$NIGHTLY_MATRIX_INCLUDE_STABILIZING == "true"', fleet)
        self.assertIn("$AWS_DEFAULT_REGION", fleet)
        self.assertIn("$RX671_EK_FLEET_TEMPLATE_NAME", fleet)
        self.assertIn("$RX671_EK_FLEET_CLAIM_CERT_PEM", fleet)
        self.assertIn("$RX671_EK_FLEET_CLAIM_PRIVATE_KEY_PEM", fleet)

    def test_nightly_routes_both_software_ota_versions_as_stabilizing(self) -> None:
        tls12 = job_block(
            self.ci,
            "matrix_rx671_wifi_software_ota_tls12",
            "matrix_rx671_wifi_software_ota_tls13",
        )
        tls13 = job_block(
            self.ci,
            "matrix_rx671_wifi_software_ota_tls13",
            ".matrix_rx671_software_lanbench",
        )

        for job, tls_version in ((tls12, "TLSv1.2"), (tls13, "TLSv1.3")):
            with self.subTest(tls_version=tls_version):
                self.assertIn(
                    "extends: .nightly_matrix_rx671_wifi_stabilizing",
                    job,
                )
                self.assertIn('RX671_WIFI_TEST_SCOPE: "ota"', job)
                self.assertIn('RUN_RX671_OTA_TEST: "true"', job)
                self.assertIn(
                    f'RX671_OTA_REQUIRE_TLS_VERSION: "{tls_version}"',
                    job,
                )

    def test_nightly_routes_tsip_aws_mqtt_without_device_private_key(self) -> None:
        job = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_mqtt",
            "matrix_rx671_wifi_tsip_mqtt_tls13",
        )

        self.assertIn("extends: .matrix_rx671_lanbench", job)
        self.assertIn('RX671_BENCHMARK_PROFILE: "aws-mqtt"', job)
        self.assertIn('RUN_RX671_TSIP_AWS_MQTT_TEST: "false"', self.ci)
        self.assertIn('$RUN_RX671_TSIP_AWS_MQTT_TEST == "true"', job)
        self.assertNotIn("RX671_TSIP_AWS_IOT_", job)
        self.assertNotIn("RX671_EK_AWS_IOT_", job)
        self.assertNotIn("PRIVATE_KEY", job)

    def test_nightly_routes_tsip_aws_mqtt_tls13_without_device_private_key(self) -> None:
        job = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_mqtt_tls13",
            "matrix_rx671_wifi_tsip_fleet",
        )

        self.assertIn("extends: .matrix_rx671_lanbench", job)
        self.assertIn('RX671_BENCHMARK_PROFILE: "aws-mqtt-tls13"', job)
        self.assertIn('RUN_RX671_TSIP_AWS_MQTT_TLS13_TEST: "false"', self.ci)
        self.assertIn('$RUN_RX671_TSIP_AWS_MQTT_TLS13_TEST == "true"', job)
        self.assertNotIn("RX671_TSIP_AWS_IOT_", job)
        self.assertNotIn("RX671_EK_AWS_IOT_", job)
        self.assertNotIn("PRIVATE_KEY", job)

    def test_nightly_routes_tsip_fleet_as_stabilizing(self) -> None:
        job = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_fleet",
            "matrix_rx671_wifi_tsip_fleet_tls13",
        )

        self.assertIn("extends: .matrix_rx671_lanbench", job)
        self.assertIn('RX671_BENCHMARK_PROFILE: "aws-fleet"', job)
        self.assertIn('RUN_RX671_TSIP_FLEET_TEST: "false"', self.ci)
        self.assertIn('$RUN_RX671_TSIP_FLEET_TEST == "true"', job)
        self.assertIn('$NIGHTLY_MATRIX_INCLUDE_STABILIZING == "true"', job)
        self.assertIn('RX671_BENCHMARK_WIFI_SSID: "$RX671_EK_WIFI_SSID"', self.ci)
        self.assertNotIn("PRIVATE_KEY", job)

    def test_nightly_routes_tsip_fleet_tls13_as_stabilizing(self) -> None:
        job = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_fleet_tls13",
            "matrix_rx671_wifi_tsip_tls13_resumption_0rtt",
        )

        self.assertIn("extends: .matrix_rx671_lanbench", job)
        self.assertIn('RX671_BENCHMARK_PROFILE: "aws-fleet-tls13"', job)
        self.assertIn('RUN_RX671_TSIP_FLEET_TLS13_TEST: "false"', self.ci)
        self.assertIn('$RUN_RX671_TSIP_FLEET_TLS13_TEST == "true"', job)
        self.assertIn('$NIGHTLY_MATRIX_INCLUDE_STABILIZING == "true"', job)
        self.assertIn('RX671_BENCHMARK_WIFI_SSID: "$RX671_EK_WIFI_SSID"', self.ci)
        self.assertNotIn("PRIVATE_KEY", job)

    def test_nightly_routes_both_tsip_ota_versions_as_stabilizing(self) -> None:
        base = job_block(
            self.ci,
            ".matrix_rx671_tsip_child",
            ".matrix_rx671_lanbench",
        )
        lanbench = job_block(
            self.ci,
            ".matrix_rx671_lanbench",
            ".matrix_rx671_tsip_ota",
        )
        template = job_block(
            self.ci,
            ".matrix_rx671_tsip_ota",
            "matrix_rx671_wifi_tsip_ota_tls12",
        )
        tls12 = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_ota_tls12",
            "matrix_rx671_wifi_tsip_ota_tls13",
        )
        tls13 = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_ota_tls13",
            "matrix_rx671_wifi_lanbench_tcp",
        )

        self.assertIn("job: nightly_dependency_alignment", base)
        self.assertIn("artifacts: true", base)
        self.assertIn("resource_group: nightly-matrix-rx671-wifi", base)
        self.assertIn("extends: .matrix_rx671_tsip_child", lanbench)
        self.assertIn("extends: .matrix_rx671_tsip_child", template)
        self.assertIn('$NIGHTLY_MATRIX_INCLUDE_STABILIZING == "true"', template)
        self.assertIn(
            "project: oss/experiment/embedded/mcu/renesas/rx/example/"
            "ek-rx671/benchmark/tsip_mbedtls",
            base,
        )
        self.assertIn("branch: $RX671_BENCHMARK_PROJECT_REF", base)
        self.assertIn(
            'EXPECTED_BENCHMARK_COMMIT_SHA: '
            '"$RX671_BENCHMARK_RESOLVED_SHA"',
            base,
        )
        self.assertIn('RX671_BENCHMARK_RUN_HARDWARE: "false"', template)
        self.assertIn('RX671_TSIP_OTA_BUILD: "true"', template)
        self.assertIn('RX671_TSIP_OTA_RUN_HARDWARE: "true"', template)
        for unrelated in (
            "RX671_BENCHMARK_HOST",
            "RX671_BENCHMARK_WIFI_SSID",
            "RX671_BENCHMARK_WIFI_PASSPHRASE",
            "RX671_BENCHMARK_WIFI_PASSWORD",
            "RX671_TSIP_OTA_WIFI_",
        ):
            self.assertNotIn(unrelated, base + template)
        for job, tls_version in ((tls12, "TLSv1.2"), (tls13, "TLSv1.3")):
            with self.subTest(tls_version=tls_version):
                self.assertIn("extends: .matrix_rx671_tsip_ota", job)
                self.assertIn(
                    f'RX671_TSIP_OTA_REQUIRE_TLS_VERSION: "{tls_version}"',
                    job,
                )

    def test_fleet_installs_signed_protected_bundle_and_restores_normal(self) -> None:
        job = job_block(self.ci, "test_rx671_wifi_fleet", "cleanup_rx671_wifi_fleet")
        self.assertIn("package_normal_boot_rx671_fleet", job)
        self.assertIn("package_normal_boot_rx671", job)
        main = job.split("trap finish_fleet EXIT", 1)[1].split("  after_script:", 1)[0]
        positions = [main.index(token) for token in ("protected_normal_bundle.py unpack", "fleet_flash_started.ok", 'install_normal_boot.py --bundle "$runtime_dir/fleet-bundle"', "tools/test_fleet_rx72n.py")]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("-erase-chip", job)
        self.assertNotIn("aws_wifi_rx671_ek_fleet.mot.enc", job)
        self.assertIn('runtime_dir="/tmp/rx671-fleet-$CI_PIPELINE_ID-$CI_JOB_ID"', job)
        self.assertIn('exec 9>>"${RX671_RPI1_HARDWARE_LOCK_PATH}"', job)
        self.assertIn("raise_if_rfp_unsafe", job)
        self.assertIn("Retained owner; normal restore skipped", job)
        self.assertIn("cleanup_rx671_fleet_runtime.py", job)

    def test_fleet_reserves_time_for_bounded_normal_restore(self) -> None:
        job = job_block(self.ci, "test_rx671_wifi_fleet")
        main = int(re.search(r'RUNNER_SCRIPT_TIMEOUT: "(\d+)m"', job).group(1)) * 60
        recovery = int(re.search(r'RUNNER_AFTER_SCRIPT_TIMEOUT: "(\d+)m"', job).group(1)) * 60
        total = int(re.search(r'timeout: (\d+) hours', job).group(1)) * 3600
        # Main: existing one-hour bench wait, install, 900s observer, restore.
        transaction = cleanup_budget.flash_remote_seconds("rx671-wifi")
        self.assertGreaterEqual(main, 3600 + 2 * transaction + 900)
        # Recovery uses a short independent bench wait, then full restore.
        after = job.split("  after_script:\n", 1)[1]
        self.assertIn("flock -w 60 9", after)
        self.assertGreaterEqual(recovery, 60 + transaction + 30)
        self.assertGreater(total, main + recovery)


if __name__ == "__main__":
    unittest.main()

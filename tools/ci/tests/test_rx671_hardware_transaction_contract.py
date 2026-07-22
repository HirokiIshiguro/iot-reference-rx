from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


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
            'mot="$CI_PROJECT_DIR/artifacts/build_rx671_wifi/aws_wifi_rx671_ek.mot"',
            "Atomic RX671 reflash before UART observation",
            "-p -v -reset -noquery",
            "tools/ci/test_rx671_wifi_uart.py",
        )
        positions = [job.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))

    def test_both_split_jobs_extend_the_locked_template(self) -> None:
        flash = job_block(self.ci, "flash_rx671_wifi", "flash_rx72n_ether")
        test = job_block(self.ci, "test_rx671_wifi", "test_rx72n_ether_mqtt")

        for job in (flash, test):
            self.assertIn("- .rx671_wifi_linux_hw_job", job)

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

    def test_nightly_routes_tsip_aws_mqtt_without_device_private_key(self) -> None:
        job = job_block(
            self.ci,
            "matrix_rx671_wifi_tsip_mqtt",
            "matrix_rx671_wifi_tsip_tls13_resumption_0rtt",
        )

        self.assertIn("extends: .matrix_rx671_lanbench", job)
        self.assertIn('RX671_BENCHMARK_PROFILE: "aws-mqtt"', job)
        self.assertIn('RUN_RX671_TSIP_AWS_MQTT_TEST: "false"', self.ci)
        self.assertIn('$RUN_RX671_TSIP_AWS_MQTT_TEST == "true"', job)
        self.assertNotIn("RX671_TSIP_AWS_IOT_", job)
        self.assertNotIn("RX671_EK_AWS_IOT_", job)
        self.assertNotIn("PRIVATE_KEY", job)


if __name__ == "__main__":
    unittest.main()

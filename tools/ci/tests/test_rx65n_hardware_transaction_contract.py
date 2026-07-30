from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


class Rx65nHardwareTransactionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

    def test_mqtt_flash_provision_reset_and_verify_are_atomic(self) -> None:
        job = job_block(
            self.ci, "test_rx65n_bg96_mqtt", "test_rx65n_bg96_tls13_0rtt"
        )
        hardware_template = job_block(
            self.ci,
            ".rx65n_bg96_linux_hw_job",
            ".rx671_wifi_linux_hw_job",
        )

        self.assertIn("- .rx65n_bg96_linux_hw_job", job)
        self.assertIn(
            "resource_group: $RX65N_BG96_DEVICE_RESOURCE_GROUP",
            hardware_template,
        )
        self.assertIn("- job: build_rx65n_bg96", job)
        self.assertIn("- job: prepare_rx65n_bg96_mqtt_credentials", job)

        ordered_tokens = (
            "--action flash-bootloader",
            "--action download-rsu",
            "--action provision-mqtt",
            "tools/provision_tsip_over_uart.py",
            "--action reset-app",
            "--action verify-mqtt",
        )
        positions = [job.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))

    def test_atomic_job_is_mqtt_only_and_has_no_split_chain_needs(self) -> None:
        job = job_block(
            self.ci, "test_rx65n_bg96_mqtt", "test_rx65n_bg96_tls13_0rtt"
        )
        needs = job.split("\n  script:", maxsplit=1)[0]

        self.assertNotIn("- job: download_rx65n_bg96_app", needs)
        self.assertNotIn("- job: reset_rx65n_bg96_app", needs)
        mqtt_rules = job_block(
            self.ci,
            ".rx65n_bg96_mqtt_rules",
            ".rx65n_bg96_app_reset_rules",
        )
        self.assertIn(
            'RX65N_BG96_TEST_SCOPE == "mqtt"',
            mqtt_rules,
        )
        self.assertNotIn("full", mqtt_rules)

    def test_mqtt_credentials_are_prepared_without_device_dependency(self) -> None:
        job = job_block(
            self.ci,
            "prepare_rx65n_bg96_mqtt_credentials",
            "provision_rx65n_bg96_mqtt",
        )

        self.assertIn("needs: []", job)
        self.assertNotIn("download_rx65n_bg96_app", job)
        self.assertNotIn(".rx65n_bg96_linux_hw_job", job)

    def test_ota_uses_pipeline_owned_thing_and_one_hardware_observer(
        self,
    ) -> None:
        job = job_block(
            self.ci, "test_rx65n_bg96_ota", "cleanup_rx65n_bg96_ota"
        )
        needs = job.split("\n  script:", maxsplit=1)[0]

        self.assertIn("- .rx65n_bg96_linux_hw_job", job)
        self.assertIn("- job: build_rx65n_bg96", needs)
        self.assertIn("- job: prepare_rx65n_bg96_mqtt_credentials", needs)
        self.assertIn("- job: build_rx65n_bg96_ota", needs)
        self.assertNotIn("- job: download_rx65n_bg96_app", needs)

        ordered_tokens = (
            "--action flash-bootloader",
            "--action download-rsu",
            "--action provision-mqtt",
            "tools/provision_tsip_over_uart.py",
            "tools/bg96_ota_prepare.py",
            "tools/bg96_ota_monitor.py",
        )
        positions = [job.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("ota_job_meta.json", job)
        self.assertIn(
            "tools/manage_ephemeral_iot_thing.py verify-journal",
            job,
        )
        self.assertIn(
            "$RX65N_BG96_THING_NAME_PREFIX-$CI_PIPELINE_ID",
            job,
        )
        self.assertIn(
            'export RX65N_BG96_AWS_IOT_THING_NAME="$ota_thing_name"',
            job,
        )
        self.assertNotIn("tools/create_bg96_ota_update.py", job)
        self.assertNotIn("awscli", job)

        creator = job_block(
            self.ci, "create_rx65n_bg96_ota", "test_rx65n_bg96_ota"
        )
        cleanup = job_block(
            self.ci,
            "cleanup_rx65n_bg96_ota",
            "cleanup_rx65n_bg96_mqtt_credentials",
        )
        self.assertIn("- .aws_cli_windows_job", creator)
        self.assertIn("tools/manage_ephemeral_iot_thing.py create", creator)
        self.assertIn("tools/create_bg96_ota_update.py", creator)
        self.assertIn("$env:CI_PIPELINE_ID-$env:CI_JOB_ID", creator)
        self.assertLess(
            creator.index("tools/manage_ephemeral_iot_thing.py create"),
            creator.index("tools/create_bg96_ota_update.py"),
        )
        self.assertIn("creation_prepared.json", creator)
        self.assertIn("- create_rx65n_bg96_ota", cleanup)
        self.assertIn("- test_rx65n_bg96_ota", cleanup)
        self.assertIn("tools/manage_ephemeral_iot_thing.py cleanup", cleanup)
        self.assertLess(
            cleanup.index("tools/verify_ota_aws_state.py cleanup"),
            cleanup.index("tools/manage_ephemeral_iot_thing.py cleanup"),
        )

    def test_mqtt_is_excluded_from_split_hardware_rules(self) -> None:
        rule_blocks = (
            job_block(
                self.ci, ".rx65n_bg96_flash_rules", ".rx671_wifi_hardware_rules"
            ),
            job_block(
                self.ci, ".rx65n_bg96_download_rules", ".rx65n_bg96_app_rules"
            ),
            job_block(
                self.ci, ".rx65n_bg96_app_rules", ".rx65n_bg96_provision_rules"
            ),
            job_block(
                self.ci,
                ".rx65n_bg96_provision_rules",
                ".rx65n_bg96_mqtt_rules",
            ),
            job_block(
                self.ci,
                ".rx65n_bg96_app_reset_rules",
                ".rx65n_bg96_tls13_0rtt_rules",
            ),
        )

        for block in rule_blocks:
            self.assertNotIn("mqtt", block)

    def test_software_tsip_and_tls_version_boundaries_are_preserved(self) -> None:
        job = job_block(
            self.ci, "test_rx65n_bg96_mqtt", "test_rx65n_bg96_tls13_0rtt"
        )

        self.assertIn(
            'if [ "${RX65N_BG96_TLS_BACKEND}" = "tsip" ]; then', job
        )
        self.assertIn("bg96_provision_args+=(--skip-private-key)", job)
        self.assertIn("--no-reset-after-provision", job)
        self.assertIn("--target rx65n", job)
        self.assertIn('RX65N_BG96_REQUIRE_TLS_VERSION:-', job)
        self.assertIn("--require-tls-version", job)


if __name__ == "__main__":
    unittest.main()

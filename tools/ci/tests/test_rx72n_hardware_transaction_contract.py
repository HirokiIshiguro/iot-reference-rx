from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


class Rx72nHardwareTransactionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        cls.rfp_wrapper = (ROOT / "tools" / "rfp_cli_locked.sh").read_text(
            encoding="utf-8"
        )

    def test_rpi1_jobs_hold_the_cross_project_lock(self) -> None:
        template = job_block(
            self.ci, ".rx72n_linux_hw_job", ".rx65n_bg96_linux_hw_job"
        )

        self.assertIn(
            'RX72N_RPI1_HARDWARE_LOCK_PATH: '
            '"/tmp/e2lite-rfp-cli.lock.d/rx72n-device-01.lock"',
            self.ci,
        )
        self.assertIn('exec 9>>"${RX72N_RPI1_HARDWARE_LOCK_PATH}"', template)
        self.assertIn(
            'flock -w "${RX72N_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS}" 9',
            template,
        )
        self.assertGreater(
            template.index("exec 9>"), template.index("python -m pip install")
        )

    def test_rfp_wrapper_uses_a_distinct_per_call_lock(self) -> None:
        self.assertIn(
            "RX72N_RFP_CLI_LOCK_DIR:-/tmp/rx72n-e2lite-rfp-cli.lock.d",
            self.rfp_wrapper,
        )
        self.assertIn('LOCK_FILE="${LOCK_DIR}/rfp-cli.lock"', self.rfp_wrapper)
        self.assertNotIn("RFP_CLI_LOCK_HELD", self.rfp_wrapper)
        self.assertNotIn("/tmp/e2lite-rfp-cli.lock.d", self.rfp_wrapper)

    def test_default_branch_does_not_consume_rx72n_hardware(self) -> None:
        workflow = self.ci.split("workflow:\n", maxsplit=1)[1].split(
            "\n.nightly_matrix_trigger:", maxsplit=1
        )[0]
        default_branch = workflow.split(
            "- if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'", maxsplit=1
        )[1].split("\n    - if:", maxsplit=1)[0]

        self.assertIn('RX72N_TEST_SCOPE: "build"', default_branch)
        self.assertNotIn('RX72N_TEST_SCOPE: "mqtt"', default_branch)

    def test_merge_request_hardware_scopes_are_preserved(self) -> None:
        workflow = self.ci.split("workflow:\n", maxsplit=1)[1].split(
            "\n.nightly_matrix_trigger:", maxsplit=1
        )[0]
        merge_request_rules = workflow.split(
            "- if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'"
        )[1:]
        rx671_rule = next(
            rule
            for rule in merge_request_rules
            if 'PIPELINE_PROFILE: "mr-rx671"' in rule
        )
        rx671_bootloader_rule = next(
            rule
            for rule in merge_request_rules
            if 'PIPELINE_PROFILE: "mr-rx671-bootloader"' in rule
        )
        generic_rule = next(
            rule for rule in merge_request_rules if 'PIPELINE_PROFILE: "mr"' in rule
        )

        self.assertIn('RX72N_TEST_SCOPE: "build"', rx671_rule)
        self.assertIn('RX671_WIFI_TEST_SCOPE: "network"', rx671_rule)
        self.assertIn('RX72N_TEST_SCOPE: "build"', rx671_bootloader_rule)
        self.assertIn('RX671_WIFI_TEST_SCOPE: "build"', rx671_bootloader_rule)
        self.assertIn("Projects/boot_loader_rx671_ek/**/*", rx671_bootloader_rule)
        self.assertIn('RX72N_TEST_SCOPE: "mqtt"', generic_rule)
        self.assertIn('RX671_WIFI_TEST_SCOPE: "build"', generic_rule)

    def test_mqtt_baseline_flash_provision_and_test_are_atomic(self) -> None:
        job = job_block(
            self.ci, "test_rx72n_ether_mqtt", "test_rx72n_ether_multi_tls"
        )

        self.assertIn("extends: .rx72n_linux_hw_job", job)
        self.assertNotIn("- flash_rx72n_ether", job)
        self.assertNotIn("- provision_rx72n_ether_mqtt", job)

        ordered_tokens = (
            "-erase-chip",
            "tools/test_uart_download_rx72n.py",
            "tools/provision_rx72n.py",
            "tools/test_mqtt_rx72n.py",
        )
        positions = [job.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))

    def test_ota_uses_pipeline_owned_thing_and_atomic_hardware_observer(
        self,
    ) -> None:
        job = job_block(
            self.ci, "test_rx72n_ether_ota", "cleanup_rx72n_ether_ota"
        )

        self.assertIn("extends: .rx72n_linux_hw_job", job)
        self.assertIn("- job: build_rx72n_ether", job)
        self.assertIn("- job: build_rx72n_ether_ota", job)
        self.assertIn("- job: create_rx72n_ether_ota", job)
        self.assertIn("--no-reset-after", job)

        ordered_tokens = (
            "-erase-chip",
            "tools/test_uart_download_rx72n.py",
            "tools/provision_rx72n.py",
            "tools/provision_tsip_over_uart.py",
            "tools/test_ota.py",
        )
        positions = [job.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('ota_job_meta.json', job)
        self.assertIn('--thing-name "$ota_thing_name"', job)
        self.assertNotIn("tools/create_ota_update.py", job)
        self.assertNotIn("awscli", job)

        creator = job_block(
            self.ci, "create_rx72n_ether_ota", "test_rx72n_ether_ota"
        )
        cleanup = job_block(
            self.ci, "cleanup_rx72n_ether_ota", "build_rx72n_ether_fleet"
        )
        self.assertIn("extends: .aws_cli_windows_job", creator)
        self.assertIn("tools/manage_ephemeral_iot_thing.py create", creator)
        self.assertIn("tools/create_ota_update.py", creator)
        self.assertIn("$env:CI_PIPELINE_ID-$env:CI_JOB_ID", creator)
        self.assertLess(
            creator.index("tools/manage_ephemeral_iot_thing.py create"),
            creator.index("tools/create_ota_update.py"),
        )
        self.assertIn("creation_prepared.json", creator)
        self.assertIn("- create_rx72n_ether_ota", cleanup)
        self.assertIn("- test_rx72n_ether_ota", cleanup)
        self.assertIn("tools/manage_ephemeral_iot_thing.py cleanup", cleanup)
        self.assertLess(
            cleanup.index("tools/verify_ota_aws_state.py cleanup"),
            cleanup.index("tools/manage_ephemeral_iot_thing.py cleanup"),
        )

    def test_legacy_split_jobs_are_limited_to_0rtt(self) -> None:
        flash = job_block(self.ci, "flash_rx72n_ether", "flash_rx65n_bg96")
        provision = job_block(
            self.ci, "provision_rx72n_ether_mqtt", "provision_rx72n_ether_fleet"
        )

        for job in (flash, provision):
            self.assertIn('RX72N_TEST_SCOPE == "tls13_0rtt"', job)
            self.assertNotIn("/^(mqtt|ota|full|tls13_0rtt)$/", job)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CI_PATH = REPO_ROOT / ".gitlab-ci.yml"
README_PATH = REPO_ROOT / "Projects" / "aws_wifi_rx671_ek" / "README.md"
LAYOUT_PATH = (
    REPO_ROOT
    / "Projects"
    / "aws_wifi_rx671_ek"
    / "e2studio_ccrx"
    / "OTA_FLASH_LAYOUT.md"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


class Rx671OtaArtifactCiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = read(CI_PATH)
        cls.readme = read(README_PATH)
        cls.layout = read(LAYOUT_PATH)

    def test_ota_workspace_and_opt_in_switch_have_safe_defaults(self) -> None:
        self.assertIn(
            'E2STUDIO_WORKSPACE_RX671_OTA: '
            '"C:/ai/codex/ws/iot-reference-rx-rx671-ota-2026-04-2"',
            self.ci,
        )
        self.assertIn('RUN_RX671_OTA_ARTIFACT_BUILD: "false"', self.ci)

    def test_ota_mr_rule_precedes_general_rx671_network_rule(self) -> None:
        workflow = self.ci.split("workflow:", 1)[1].split(
            "\ninclude:", 1
        )[0]
        ota_profile = 'PIPELINE_PROFILE: "mr-rx671-ota-artifacts"'
        general_profile = 'PIPELINE_PROFILE: "mr-rx671"'
        self.assertIn(ota_profile, workflow)
        self.assertLess(workflow.index(ota_profile), workflow.index(general_profile))

        ota_rule = workflow[
            workflow.rfind(
                "- if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'",
                0,
                workflow.index(ota_profile),
            ) : workflow.index(ota_profile) + len(ota_profile)
        ]
        for ota_path in (
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/OTA_FLASH_LAYOUT.md",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "ota-layout-contract.json",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/application_code/ota_image_identity.c",
            "tools/build_rx671_ota_images.py",
            "tools/build_rx671_fwup_v2_rsu.py",
            "tools/ci/analyze_rx671_ota_layout.py",
        ):
            self.assertIn(ota_path, ota_rule)
        for general_rx671_path in (
            "Projects/aws_wifi_rx671_ek/README.md",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/frtos_config/demo_config.h",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/frtos_config/r_fwup_config.h",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/sdio_host.c",
            "tools/build_headless_rx671_wifi.ps1",
        ):
            self.assertNotIn(general_rx671_path, ota_rule)
        self.assertNotIn("- .gitlab-ci.yml", ota_rule)

        ota_variables = workflow[
            workflow.index(ota_profile) : workflow.find(
                "\n    - if:", workflow.index(ota_profile)
            )
        ]
        self.assertIn('RUN_RX671_OTA_ARTIFACT_BUILD: "true"', ota_variables)
        self.assertIn('RUN_RX671_WIFI_BUILD: "false"', ota_variables)
        self.assertIn('RX671_WIFI_TEST_SCOPE: "build"', ota_variables)
        self.assertIn('RX671_WIFI_SKIP_HW_TESTS: "true"', ota_variables)

    def test_package_job_is_build_only_and_needs_bootloader_artifacts(self) -> None:
        start = self.ci.index("package_rx671_ota_artifacts:")
        body_start = self.ci.index("\n", start) + 1
        next_job = re.search(
            r"(?m)^[a-zA-Z0-9_.-]+:\s*$", self.ci[body_start:]
        )
        self.assertIsNotNone(next_job)
        assert next_job is not None
        job = self.ci[start : body_start + next_job.start()]

        self.assertIn("stage: package", job)
        self.assertIn('RUN_RX671_OTA_ARTIFACT_BUILD == "true"', job)
        self.assertRegex(
            job,
            r"needs:\s*\n"
            r"\s+- job: build_rx671_bootloader\s*\n"
            r"\s+artifacts: true",
        )
        self.assertIn("python -m pip install --user cryptography", job)
        for test_module in (
            "tools.ci.tests.test_analyze_rx671_ota_layout",
            "tools.ci.tests.test_build_rx671_fwup_v2_rsu",
            "tools.ci.tests.test_build_rx671_ota_images",
            "tools.ci.tests.test_rx671_ota_build_profile_contract",
            "tools.ci.tests.test_rx671_ota_artifact_ci_contract",
            "tools.ci.tests.test_rx671_bootloader_contract",
        ):
            self.assertIn(test_module, job)

        self.assertIn("tools/build_rx671_ota_images.py", job)
        self.assertRegex(job, r"--baseline-version 0\.1\.0\s+`")
        self.assertRegex(job, r"--candidate-version 0\.1\.1\s+`")
        self.assertRegex(job, r'--e2studio "\$env:E2STUDIO_CLI"\s+`')
        self.assertIn(
            '--workspace-root "$env:E2STUDIO_WORKSPACE_RX671_OTA"',
            job,
        )
        self.assertIn("- build/rx671-ota/", job)

        for hardware_action in (
            "rfp-cli",
            "test_rx671_wifi_uart.py",
            "load_rx671_wifi_jlink.ps1",
            "RX671_EK_WIFI_SSID",
            "RX671_EK_AWS_IOT_ENDPOINT",
        ):
            self.assertNotIn(hardware_action, job)

    def test_user_docs_define_temporary_profile_and_scope_boundary(self) -> None:
        combined = self.readme + "\n" + self.layout
        for marker in (
            "bank.single",
            "bank.dual",
            "0x000C0000",
            "0xFFF00300",
            "PFRAM2",
            "RPFRAM2",
            "0.1.0",
            "0.1.1",
            "build/rx671-ota",
        ):
            self.assertIn(marker, combined)

        self.assertRegex(
            combined,
            r"(?is)byte.for.byte|byte-for-byte|バイト単位|バイト列",
        )
        self.assertRegex(
            combined,
            r"(?is)does not prove AWS OTA hardware success|"
            r"AWS OTAの実機成功を証明しない",
        )
        self.assertRegex(
            combined,
            r"(?is)does not change the AWS.*table|"
            r"AWS IoT Core 接続テスト結果.*[〇○].*更新しない",
        )


if __name__ == "__main__":
    unittest.main()

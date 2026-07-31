from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CI_PATH = REPO_ROOT / ".gitlab-ci.yml"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
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
        cls.gitignore = read(GITIGNORE_PATH)

    def test_ota_workspace_and_opt_in_switch_have_safe_defaults(self) -> None:
        self.assertIn(
            'E2STUDIO_WORKSPACE_RX671_OTA: '
            '"C:/ai/codex/ws/iot-reference-rx-rx671-ota-2026-04-2"',
            self.ci,
        )
        self.assertIn('RUN_RX671_OTA_ARTIFACT_BUILD: "false"', self.ci)

    def test_yaml_only_mr_runs_lightweight_ota_contracts(self) -> None:
        start = self.ci.index("rx671_ota_ci_contract:")
        end = self.ci.index("\nnightly_dependency_alignment:", start)
        job = self.ci[start:end]
        self.assertIn("stage: dependency_check", job)
        self.assertIn('GIT_SUBMODULE_STRATEGY: "none"', job)
        self.assertIn("- .gitlab-ci.yml", job)
        for module in (
            "tools.ci.tests.test_plan_rx671_ota",
            "tools.ci.tests.test_rx671_ota_artifact_ci_contract",
            "tools.ci.tests.test_rx671_ota_hardware_ci_contract",
            "tools.ci.tests.test_rx671_ota_host_tools",
            "tools.ci.tests.test_verify_ota_aws_state",
        ):
            self.assertIn(module, job)

    def test_shared_rx671_changes_keep_network_and_ota_artifact_lanes(self) -> None:
        workflow = self.ci.split("workflow:", 1)[1].split(
            "\ninclude:", 1
        )[0]
        combined_profile = 'PIPELINE_PROFILE: "mr-rx671-ota-and-network"'
        ota_profile = 'PIPELINE_PROFILE: "mr-rx671-ota-artifacts"'
        general_profile = 'PIPELINE_PROFILE: "mr-rx671"'
        self.assertIn(combined_profile, workflow)
        self.assertIn(ota_profile, workflow)
        self.assertLess(
            workflow.index(combined_profile),
            workflow.index(ota_profile),
        )
        self.assertLess(workflow.index(ota_profile), workflow.index(general_profile))

        combined_rule = workflow[
            workflow.rfind(
                "- if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'",
                0,
                workflow.index(combined_profile),
            ) : workflow.index(combined_profile) + len(combined_profile)
        ]
        ota_rule = workflow[
            workflow.rfind(
                "- if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'",
                0,
                workflow.index(ota_profile),
            ) : workflow.index(ota_profile) + len(ota_profile)
        ]
        for shared_path in (
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/.cproject",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/aws_wifi_rx671_ek.c",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/application_code/ota_image_identity.c",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/frtos_config/demo_config.h",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/frtos_config/r_fwup_config.h",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/frtos_config/rm_littlefs_flash_config.h",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/sdio_host.c",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/whd_port/whd_port_resource.c",
            "tools/build_headless_rx671_wifi.ps1",
        ):
            self.assertIn(shared_path, combined_rule)
            self.assertNotIn(shared_path, ota_rule)

        combined_variables = workflow[
            workflow.index(combined_profile) : workflow.find(
                "\n    - if:", workflow.index(combined_profile)
            )
        ]
        for setting in (
            'RX671_WIFI_TEST_SCOPE: "network"',
            'RX671_WIFI_SKIP_HW_TESTS: "false"',
            'RUN_RX671_WIFI_BUILD: "true"',
            'RUN_RX671_BOOTLOADER_BUILD: "true"',
            'RUN_RX671_OTA_ARTIFACT_BUILD: "true"',
        ):
            self.assertIn(setting, combined_variables)

        for ota_path in (
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/OTA_FLASH_LAYOUT.md",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "ota-layout-contract.json",
            "tools/build_rx671_ota_images.py",
            "tools/build_rx671_fwup_v2_rsu.py",
            "tools/ci/analyze_rx671_ota_layout.py",
        ):
            self.assertIn(ota_path, ota_rule)
        for general_rx671_path in (
            "Projects/aws_wifi_rx671_ek/README.md",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/"
            "src/frtos_config/r_fwup_config.h",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/sdio_host.c",
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

    def test_package_job_has_formal_default_and_encrypted_runtime_opt_in(self) -> None:
        start = self.ci.index("package_rx671_ota_artifacts:")
        body_start = self.ci.index("\n", start) + 1
        next_job = re.search(
            r"(?m)^[a-zA-Z0-9_.-]+:\s*$", self.ci[body_start:]
        )
        self.assertIsNotNone(next_job)
        assert next_job is not None
        job = self.ci[start : body_start + next_job.start()]

        self.assertIn("stage: package", job)
        self.assertIn(
            'RUN_RX671_OTA_TEST == "true" && '
            '$RX671_WIFI_TEST_SCOPE == "ota"',
            job,
        )
        self.assertIn('RUN_RX671_OTA_ARTIFACT_BUILD == "true"', job)
        self.assertRegex(
            job,
            r"needs:\s*\n"
            r"\s+- job: preflight_rx671_wifi_ota\s*\n"
            r"\s+artifacts: false\s*\n"
            r"\s+optional: true\s*\n"
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
            "tools.ci.tests.test_verify_ota_aws_state",
            "tools.ci.tests.test_ota_aws_evidence_ci_contract",
            "tools.ci.tests.test_rx671_bootloader_contract",
        ):
            self.assertIn(test_module, job)

        self.assertIn("tools/build_rx671_ota_images.py", job)
        self.assertIn(
            '"--baseline-version", "$env:RX671_OTA_BASELINE_VERSION"',
            job,
        )
        self.assertIn(
            '"--candidate-version", "$env:RX671_OTA_CANDIDATE_VERSION"',
            job,
        )
        self.assertIn('"--e2studio", "$env:E2STUDIO_CLI"', job)
        self.assertIn(
            '"--workspace-root", "$env:E2STUDIO_WORKSPACE_RX671_OTA"',
            job,
        )
        self.assertIn('$env:RX671_WIFI_TEST_SCOPE -eq "ota"', job)
        self.assertIn('$otaBuildArgs += "--runtime-wifi-config"', job)
        self.assertIn("tools/ci/protect_secret_artifact.py", job)
        self.assertIn("rx671-ota-runtime.tar.enc", job)
        self.assertIn("--secret-env RX671_OTA_ARTIFACT_KEY", job)
        self.assertNotIn("RX671_OTA_ARTIFACT_SECRET", job)
        self.assertNotRegex(
            job,
            r"RX671_OTA_ARTIFACT_KEY\s*=\s*"
            r"\$env:RX671_EK_WIFI_PASSPHRASE",
        )
        self.assertIn(
            'Remove-Item -LiteralPath "$env:CI_PROJECT_DIR\\build\\rx671-ota" '
            "-Recurse -Force",
            job,
        )
        self.assertNotIn("RX671_OTA_PACKAGE_ARTIFACT_PATH", job)
        artifacts = job.split("\n  artifacts:", 1)[1]
        self.assertIn("- build/rx671-ota/", artifacts)
        self.assertIn("- build/rx671-ota-secure/", artifacts)
        self.assertIn("after_script:", job)
        for cleanup_marker in (
            "RX671 OTA stale plaintext pre-clean failed",
            "Projects\\aws_wifi_rx671_ek\\e2studio_ccrx\\HardwareDebug",
            "E2STUDIO_WORKSPACE_RX671_OTA",
            "build\\rx671-ota-runtime.tar",
            "RX671 OTA after_script cleanup postcondition failed",
        ):
            self.assertIn(cleanup_marker, job)

        for hardware_action in (
            "rfp-cli",
            "test_rx671_wifi_uart.py",
            "load_rx671_wifi_jlink.ps1",
            "RX671_EK_AWS_IOT_ENDPOINT",
        ):
            self.assertNotIn(hardware_action, job)

    def test_downloaded_ci_artifacts_do_not_dirty_formal_source_provenance(self) -> None:
        self.assertRegex(self.gitignore, r"(?m)^/artifacts/$")

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

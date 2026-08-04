from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CI_PATH = REPO_ROOT / ".gitlab-ci.yml"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
ROOT_README_PATH = REPO_ROOT / "README.md"
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
        cls.root_readme = read(ROOT_README_PATH)
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
            "tools.ci.tests.test_manage_rx671_ota_event_policy",
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
            "tools/manage_rx671_ota_event_policy.py",
            "tools/ci/tests/test_manage_rx671_ota_event_policy.py",
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

    def test_package_job_always_exports_formal_credential_free_firmware(self) -> None:
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
            "tools.ci.tests.test_manage_rx671_ota_event_policy",
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
        self.assertIn(
            '"--tls-version", "$env:RX671_OTA_REQUIRE_TLS_VERSION"',
            job,
        )
        self.assertIn('"--e2studio", "$env:E2STUDIO_CLI"', job)
        self.assertIn(
            '"--workspace-root", "$env:E2STUDIO_WORKSPACE_RX671_OTA"',
            job,
        )
        self.assertIn("$manifest.formal -ne $true", job)
        self.assertIn("$manifest.credentials_embedded -ne $false", job)
        self.assertIn("$manifest.dirty -ne $false", job)
        self.assertIn("$manifest.source_sha -ne $env:CI_COMMIT_SHA", job)
        self.assertIn(
            "$manifest.tls_version -ne $env:RX671_OTA_REQUIRE_TLS_VERSION",
            job,
        )
        self.assertIn(
            '$manifest.sdio_run_clock_div -ne "SDHI_DIV_8"', job
        )
        self.assertIn(
            '$manifest.wifi_credentials_source -ne '
            '"littlefs_kvs_runtime_provisioning"',
            job,
        )
        for forbidden in (
            "--runtime-wifi-config",
            "tools/ci/protect_secret_artifact.py",
            "rx671-ota-runtime.tar.enc",
            "RX671_OTA_ARTIFACT_KEY",
            "RX671_OTA_ARTIFACT_SECRET",
            "rx671-ota-secure",
        ):
            self.assertNotIn(forbidden, job)
        self.assertNotIn("RX671_OTA_PACKAGE_ARTIFACT_PATH", job)
        artifacts = job.split("\n  artifacts:", 1)[1]
        self.assertIn("- build/rx671-ota/", artifacts)
        self.assertNotIn("rx671-ota-secure", artifacts)
        self.assertIn("after_script:", job)
        for cleanup_marker in (
            "RX671 OTA stale build-state pre-clean failed",
            "Projects\\aws_wifi_rx671_ek\\e2studio_ccrx\\HardwareDebug",
            "E2STUDIO_WORKSPACE_RX671_OTA",
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
            "SDHI_DIV_2",
            "SDHI_DIV_8",
        ):
            self.assertIn(marker, combined)

        self.assertRegex(
            combined,
            r"(?is)byte.for.byte|byte-for-byte|バイト単位|バイト列",
        )
        self.assertRegex(
            combined,
            r"(?is)package job alone does not prove.*hardware OTA success|"
            r"package job単体は実機AWS OTA成功を証明しない",
        )
        self.assertRegex(
            combined,
            r"(?is)fixed-SHA focused hardware pipeline.*proves|"
            r"focused hardware pipeline.*実機AWS OTA",
        )
        self.assertIn("test_rx671_wifi_ota_atomic", combined)
        self.assertIn("cleanup_rx671_wifi_ota", combined)
        self.assertIn("LIBRARY_LOG_LEVEL=LOG_NONE", combined)
        self.assertIn("configPRINTF", combined)
        for boundary in (
            "0xFFE00000-0xFFEBFFFF",
            "0xFFF00000-0xFFFBFFFF",
            "0xFFEC0000-0xFFEFFFFF",
            "0xFFFC0000-0xFFFFFFFF",
        ):
            self.assertIn(boundary, combined)
        self.assertRegex(
            self.layout,
            r"(?is)-range.*-erase.*-erase-chip.*(?:not|preserve|使用しない)",
        )
        self.assertRegex(
            combined,
            r"(?is)key-load.*found\.|key load.*found\.|key-load開始.*found\.",
        )
        self.assertRegex(
            combined,
            r"(?is)32 KiB.*(?:progress|進捗).*(?:ACK|flow-control)|"
            r"(?:ACK|flow-control).*32 KiB",
        )
        self.assertIn("(768/768KB)", combined)
        self.assertIn("completed installing firmware", combined)
        self.assertRegex(
            self.layout,
            r"(?is)208 KiB.*32 KiB.*TLS 1\.2|"
            r"32 KiB.*208 KiB.*TLS 1\.2",
        )
        for stream_memory_contract in (
            "blocks/request",
            "OTA event data buffer",
            "192",
            "785,920 bytes",
            "pipeline #9580",
            "callback",
            "30,116 bytes",
            "0x00058A5B",
        ):
            self.assertIn(stream_memory_contract, self.layout)
        self.assertIn("AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_2=1", combined)
        self.assertIn("RX671 OTA fatal:", combined)
        for notification_contract in (
            "configTASK_NOTIFICATION_ARRAY_ENTRIES",
            "index 2",
            "index 3",
            "4要素",
            "Smart Configurator",
            "compile-time guard",
        ):
            self.assertIn(notification_contract, self.layout)
        self.assertRegex(
            self.layout,
            r"(?s)OTAだけの\s*一時profileではなく",
        )
        for event_policy_contract in (
            "$aws/events/job/<jobId>/cancellation_in_progress",
            "iot:Subscribe",
            "iot:Receive",
            "topicfilter/",
            "pipeline専用policy",
            "preflight journal",
            "480秒",
            "DeleteConflictException",
            "最大300秒",
        ):
            self.assertIn(event_policy_contract, self.layout)
        self.assertRegex(
            self.layout,
            r"(?s)`#` / `\*` wildcard.*追加しない",
        )
        self.assertRegex(
            self.layout,
            r"(?is)(?:ServerHello|最初の受信).*pvPortMalloc|"
            r"pvPortMalloc.*(?:ServerHello|最初の受信)",
        )
        self.assertRegex(
            combined,
            r"(?is)same source SHA.*hardware job.*cleanup job|"
            r"同一source SHA.*hardware.*cleanup",
        )
        self.assertRegex(
            self.readme,
            r"(?is)TSIP and TLS 1\.3\s+OTA remain\s+unverified",
        )
        self.assertRegex(
            self.layout,
            r"(?is)TSIP OTA.*software / TSIP TLS 1\.3 OTA.*証明範囲外.*`—`",
        )

        for csp_boundary in (
            "-erase-chip",
            "claim-free",
            ".rx671-ota-secrets",
            "証明しない",
        ):
            self.assertIn(csp_boundary, self.layout)

        published_docs = self.root_readme + "\n" + combined
        for fixed_evidence in (
            "d505b3fd",
            "pipeline #9584",
            "package #61361",
            "create #61362",
            "hardware #61363",
            "cleanup #61364",
            "192/192 block",
            "25,584 bytes",
            "minimum 16 network buffers",
            "WHD maximum use 1/8",
            "Job execution `SUCCEEDED`",
        ):
            self.assertIn(fixed_evidence, published_docs)

        for stale_false_success in (
            "pipeline #9562",
            "b61640f3",
            "#61197",
            "#61198",
            "#61199",
            "#61200",
        ):
            self.assertNotIn(stale_false_success, published_docs)

        self.assertIn("image_commit_observed=false", self.layout)
        self.assertIn("Accepted and committed final image.", combined)
        self.assertRegex(
            combined,
            r"(?is)(?:optional|任意).*Accepted and committed final image|"
            r"Accepted and committed final image.*(?:optional|任意)",
        )
        self.assertRegex(
            self.layout,
            r"(?is)image acceptance.*OTA成功通知.*AWS.*SUCCEEDED|"
            r"image acceptance.*AWS.*SUCCEEDED",
        )


if __name__ == "__main__":
    unittest.main()

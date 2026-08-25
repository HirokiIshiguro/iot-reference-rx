from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


def top_level_blocks(ci: str) -> dict[str, str]:
    headers = list(
        re.finditer(r"(?m)^(?P<name>[A-Za-z0-9_.-]+):[ \t]*$", ci)
    )
    return {
        match.group("name"): ci[
            match.start() : (
                headers[index + 1].start()
                if index + 1 < len(headers)
                else len(ci)
            )
        ]
        for index, match in enumerate(headers)
    }


class NightlyDependencyCiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        cls.config = json.loads(
            (ROOT / "tools/ci/nightly-dependency-targets.json").read_text(
                encoding="utf-8"
            )
        )

    def test_dependency_gate_mr_is_contract_only_and_hardware_free(self) -> None:
        workflow = self.ci.split(
            "\nnightly_dependency_contract:\n",
            maxsplit=1,
        )[0]
        profile = '        PIPELINE_PROFILE: "mr-dependency-gate"'
        profile_index = workflow.index(profile)
        rule_start = workflow.rfind(
            '    - if: \'$CI_PIPELINE_SOURCE == "merge_request_event"\'',
            0,
            profile_index,
        )
        rule_end = workflow.index("      when: always", profile_index)
        rule = workflow[rule_start:rule_end]
        broad_mr_index = workflow.index('        PIPELINE_PROFILE: "mr"')
        self.assertLess(profile_index, broad_mr_index)

        for path in (
            "tools/ci/check_nightly_dependency_alignment.py",
            "tools/ci/nightly-dependency-targets.json",
            "tools/ci/tests/fixtures/nightly_dependency_alignment_run5.json",
            "tools/ci/tests/test_nightly_dependency_alignment.py",
            "tools/ci/tests/test_nightly_dependency_ci_contract.py",
            "tools/ci/tests/test_verify_dependency_gate_mr_scope.py",
            "tools/ci/verify_dependency_gate_mr_scope.py",
        ):
            self.assertIn(f"        - {path}", rule)
        self.assertNotIn("        - .gitlab-ci.yml", rule)
        for setting in (
            'RUN_RX65N_BG96_BUILD: "false"',
            'RX65N_BG96_TEST_SCOPE: "build"',
            'RX65N_BG96_SKIP_HW_TESTS: "true"',
            'RUN_RX72N_BUILD: "false"',
            'RX72N_TEST_SCOPE: "build"',
            'RX72N_SKIP_HW_TESTS: "true"',
            'RUN_RX671_WIFI_BUILD: "false"',
            'RX671_WIFI_TEST_SCOPE: "build"',
            'RX671_WIFI_SKIP_HW_TESTS: "true"',
            'RUN_RX671_BOOTLOADER_BUILD: "false"',
        ):
            self.assertIn(setting, rule)

        contract = job_block(
            self.ci,
            "nightly_dependency_contract",
            "nightly_dependency_alignment",
        )
        self.assertIn("stage: dependency_check", contract)
        self.assertIn('$CI_PIPELINE_SOURCE == "merge_request_event"', contract)
        self.assertIn('$PIPELINE_PROFILE == "mr-dependency-gate"', contract)
        self.assertIn(
            "tools.ci.tests.test_nightly_dependency_alignment",
            contract,
        )
        self.assertIn(
            "tools.ci.tests.test_nightly_dependency_ci_contract",
            contract,
        )
        self.assertIn(
            "tools.ci.tests.test_verify_dependency_gate_mr_scope",
            contract,
        )
        self.assertIn(
            "python3 tools/ci/verify_dependency_gate_mr_scope.py",
            contract,
        )
        self.assertNotIn(
            "python3 tools/ci/check_nightly_dependency_alignment.py",
            contract,
        )
        self.assertNotIn("artifacts:", contract)

    def test_dependency_stage_precedes_every_nightly_bridge(self) -> None:
        stage_list = self.ci.split("variables:\n", maxsplit=1)[0]
        self.assertLess(
            stage_list.index("  - dependency_check"),
            stage_list.index("  - nightly_matrix"),
        )

        job = job_block(
            self.ci,
            "nightly_dependency_alignment",
            ".nightly_matrix_trigger",
        )
        self.assertIn("stage: dependency_check", job)
        self.assertIn('GIT_SUBMODULE_STRATEGY: "none"', job)
        self.assertIn(
            "tools.ci.tests.test_nightly_dependency_alignment",
            job,
        )
        self.assertIn(
            "tools.ci.tests.test_nightly_dependency_ci_contract",
            job,
        )
        self.assertIn("tools/ci/check_nightly_dependency_alignment.py", job)
        self.assertIn("artifacts/nightly_dependency_alignment.json", job)
        self.assertIn("artifacts/nightly_dependency_alignment.env", job)
        self.assertIn("dotenv: artifacts/nightly_dependency_alignment.env", job)
        self.assertIn('$PIPELINE_PROFILE == "nightly_matrix"', job)
        self.assertIn('$CI_PIPELINE_SOURCE == "schedule"', job)
        self.assertIn('$CI_PIPELINE_SOURCE == "api"', job)
        self.assertIn('$CI_PIPELINE_SOURCE == "web"', job)
        self.assertIn('$PIPELINE_PROFILE == "focused"', job)
        for focused_flag in (
            "RUN_RX671_TSIP_AWS_MQTT_TEST",
            "RUN_RX671_TSIP_AWS_MQTT_TLS13_TEST",
            "RUN_RX671_TSIP_FLEET_TEST",
            "RUN_RX671_TSIP_FLEET_TLS13_TEST",
        ):
            self.assertIn(f'${focused_flag} == "true"', job)
        self.assertNotIn("merge_request_event", job)

    def test_external_bridge_project_ref_and_resolved_sha_mapping_is_exact(
        self,
    ) -> None:
        configured = {
            (
                target["project"],
                target["ref_env"],
                target["resolved_ref_env"],
            )
            for target in self.config["targets"]
        }
        self.assertEqual(
            {
                (
                    "oss/experiment/embedded/mcu/renesas/rx/example/"
                    "ek-rx671/benchmark/mbedtls",
                    "RX671_SOFTWARE_BENCHMARK_PROJECT_REF",
                    "RX671_SOFTWARE_BENCHMARK_RESOLVED_SHA",
                ),
                (
                    "oss/experiment/embedded/mcu/renesas/rx/example/"
                    "ek-rx671/benchmark/tsip_mbedtls",
                    "RX671_BENCHMARK_PROJECT_REF",
                    "RX671_BENCHMARK_RESOLVED_SHA",
                ),
                (
                    "oss/experiment/embedded/mcu/renesas/rx/example/"
                    "rx72n_envision_kit/benchmark/tsip_mbedtls13",
                    "RX72N_TSIP_MBEDTLS13_PROJECT_REF",
                    "RX72N_TSIP_MBEDTLS13_RESOLVED_SHA",
                ),
            },
            configured,
        )

        actual: set[tuple[str, str, str]] = set()
        for name, block in top_level_blocks(self.ci).items():
            project_match = re.search(r"(?m)^    project: (\S+)$", block)
            if project_match is None:
                continue
            branch_match = re.search(
                r"(?m)^    branch: \$([A-Z][A-Z0-9_]*)$",
                block,
            )
            resolved_match = re.search(
                r'(?m)^    EXPECTED_BENCHMARK_COMMIT_SHA: '
                r'"\$([A-Z][A-Z0-9_]*)"$',
                block,
            )
            with self.subTest(job=name):
                self.assertIsNotNone(branch_match)
                self.assertIsNotNone(resolved_match)
                self.assertIn("job: nightly_dependency_alignment", block)
                self.assertIn("artifacts: true", block)
                self.assertIn('GIT_SUBMODULE_STRATEGY: "none"', block)
            if branch_match is not None and resolved_match is not None:
                actual.add(
                    (
                        project_match.group(1),
                        branch_match.group(1),
                        resolved_match.group(1),
                    )
                )
        self.assertEqual(configured, actual)

    def test_policy_covers_kernel_and_every_used_aws_library(self) -> None:
        rx671_dependencies = {
            "Middleware/FreeRTOS/FreeRTOS-Kernel",
            "Middleware/FreeRTOS/FreeRTOS-Plus-TCP",
            "Middleware/FreeRTOS/backoffAlgorithm",
            "Middleware/FreeRTOS/coreJSON",
            "Middleware/FreeRTOS/coreMQTT",
            "Middleware/FreeRTOS/coreMQTT-Agent",
            "Middleware/FreeRTOS/corePKCS11",
            "Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk",
            "Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk",
            "Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c",
        }
        expected_dependencies = {
            "rx671-software-mbedtls": rx671_dependencies,
            "rx671-tsip-mbedtls": rx671_dependencies,
            "rx72n-tsip-mbedtls13": {
                "Middleware/AWS/Device-Defender-for-AWS-IoT-embedded-sdk",
                "Middleware/AWS/Device-Shadow-for-AWS-IoT-embedded-sdk",
                "Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk",
                "Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk",
                "Middleware/AWS/SigV4-for-AWS-IoT-embedded-sdk",
                "Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c",
                "Middleware/FreeRTOS/FreeRTOS-Cellular-Interface",
                "Middleware/FreeRTOS/FreeRTOS-Kernel",
                "Middleware/FreeRTOS/FreeRTOS-Plus-TCP",
                "Middleware/FreeRTOS/backoffAlgorithm",
                "Middleware/FreeRTOS/coreHTTP",
                "Middleware/FreeRTOS/coreJSON",
                "Middleware/FreeRTOS/coreMQTT",
                "Middleware/FreeRTOS/coreMQTT-Agent",
                "Middleware/FreeRTOS/corePKCS11",
                "Middleware/FreeRTOS/coreSNTP",
            },
        }
        rx671_source_roots = {
            "Common",
            "Demos",
            "Middleware",
            "Projects/aws_wifi_rx671_ek",
            "Projects/boot_loader_rx671_ek",
        }
        rx671_source_files = {
            "tools/build_headless_rx671_bootloader.ps1",
            "tools/build_headless_rx671_wifi.ps1",
            "tools/build_rx671_fwup_v2_rsu.py",
            "tools/build_rx671_ota_images.py",
            "tools/load_rx671_wifi_jlink.ps1",
            "tools/manage_ephemeral_iot_thing.py",
            "tools/manage_rx671_ota_event_policy.py",
            "tools/plan_rx671_ota.py",
            "tools/provision_rx671_ota.py",
            "tools/provision_tsip_over_uart.py",
            "tools/rfp_cli_locked.sh",
            "tools/run_rx671_tcp_throughput_smoke.py",
            "tools/rx671_ota_host.py",
            "tools/test_rx671_ota.py",
            "tools/verify_ota_aws_state.py",
            "tools/ci/analyze_rx671_ota_layout.py",
            "tools/ci/check_rx671_bootloader_layout.py",
            "tools/ci/protect_secret_artifact.py",
            "tools/ci/test_rx671_bootloader_uart.py",
            "tools/ci/test_rx671_wifi_uart.py",
        }
        expected_source_roots = {
            "rx671-software-mbedtls": rx671_source_roots,
            "rx671-tsip-mbedtls": rx671_source_roots,
            "rx72n-tsip-mbedtls13": {
                "Common",
                "Demos",
                "Middleware",
                "Projects/aws_ether_rx72n_envision_kit",
                "Projects/aws_ether_rx72n_envision_kit_tsip",
                "Projects/boot_loader_rx72n_envision_kit",
            },
        }
        expected_source_files = {
            "rx671-software-mbedtls": rx671_source_files,
            "rx671-tsip-mbedtls": rx671_source_files,
            "rx72n-tsip-mbedtls13": {
                "tools/build_headless_rx72n_fleet.ps1",
                "tools/build_headless_rx72n_with_client_credentials.ps1",
                "tools/build_headless_rx72n.ps1",
                "tools/build_ota_candidate.py",
                "tools/cleanup_rx72n_fleet_resources.py",
                "tools/create_ota_update.py",
                "tools/generate_rx72n_rsu.ps1",
                "tools/manage_ephemeral_iot_thing.py",
                "tools/monitor_rx72n_boot.py",
                "tools/provision_rx72n.py",
                "tools/provision_tsip_over_uart.py",
                "tools/render_rx72n_client_credentials.py",
                "tools/rfp_cli_locked.sh",
                "tools/run_rx72n_local_baseline.ps1",
                "tools/test_fleet_rx72n.py",
                "tools/test_lanbench_tls13_0rtt_rx72n.py",
                "tools/test_mqtt_rx72n.py",
                "tools/test_ota.py",
                "tools/test_uart_download_rx72n.py",
                "tools/verify_ota_aws_state.py",
                "tools/fwup/rx72n_envision_kit_dual_bank.prm.csv",
                "tools/ci/check_rx72n_tsip_driver.py",
                "tools/ci/monitor_multi_tls.py",
                "tools/ci/protect_secret_artifact.py",
            },
        }
        self.assertEqual(
            set(expected_dependencies),
            {target["name"] for target in self.config["targets"]},
        )
        for target in self.config["targets"]:
            with self.subTest(target=target["name"]):
                self.assertEqual("parent_gitlinks", target["mode"])
                self.assertEqual(
                    "external/iot-reference-rx",
                    target["iot_reference_gitlink"],
                )
                self.assertEqual(
                    expected_source_roots[target["name"]],
                    set(target["source_roots"]),
                )
                self.assertEqual(
                    expected_source_files[target["name"]],
                    set(target["source_files"]),
                )
                self.assertEqual(
                    expected_dependencies[target["name"]],
                    set(target["dependencies"]),
                )
                self.assertEqual(
                    len(target["dependencies"]),
                    len(set(target["dependencies"])),
                )


if __name__ == "__main__":
    unittest.main()

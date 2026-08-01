from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CI = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")


def job(name: str) -> str:
    start = CI.index(f"\n{name}:\n") + 1
    body = CI.index("\n", start) + 1
    next_job = re.search(r"(?m)^[A-Za-z0-9_.-]+:\s*$", CI[body:])
    if next_job is None:
        return CI[start:]
    return CI[start : body + next_job.start()]


class Rx671OtaHardwareCiContractTests(unittest.TestCase):
    def test_ota_hardware_path_is_explicitly_opt_in(self) -> None:
        self.assertIn('RUN_RX671_OTA_TEST: "false"', CI)
        self.assertIn('RX671_OTA_BASELINE_VERSION: "0.1.0"', CI)
        self.assertIn('RX671_OTA_CANDIDATE_VERSION: "0.1.1"', CI)
        self.assertIn('RX671_OTA_REQUIRE_TLS_VERSION: "TLSv1.2"', CI)
        rules = job(".rx671_wifi_ota_rules")
        activation = (
            'RUN_RX671_OTA_TEST == "true" && '
            '$RX671_WIFI_TEST_SCOPE == "ota"'
        )
        self.assertIn(activation, rules)
        for hidden_gate in (
            "RUN_RX671_OTA_ARTIFACT_BUILD",
            "RUN_RX671_BOOTLOADER_BUILD",
            "RUN_RX671_WIFI_BUILD",
            "RX671_WIFI_SKIP_HW_TESTS",
            "RX671_OTA_S3_BUCKET",
            "RX671_EK_AWS_IOT_CERT_PEM",
        ):
            self.assertNotIn(hidden_gate, rules)

        for name in (
            "preflight_rx671_wifi_ota",
            "create_rx671_wifi_ota",
            "test_rx671_wifi_ota_atomic",
        ):
            self.assertIn("- .rx671_wifi_ota_rules", job(name))
        self.assertIn(
            activation,
            job(".rx671_wifi_ota_cleanup_rules"),
        )

    def test_preflight_hard_fails_missing_inputs_or_changed_proof_profile(
        self,
    ) -> None:
        preflight = job("preflight_rx671_wifi_ota")
        for required in (
            "AWS_DEFAULT_REGION",
            "RX671_OTA_S3_BUCKET",
            "RX671_OTA_SERVICE_ROLE_ARN",
            "RX671_OTA_BASE_THING_NAME",
            "RX671_EK_WIFI_SSID",
            "RX671_EK_WIFI_PASSPHRASE",
            "RX671_EK_AWS_IOT_CERT_PEM",
            "RX671_EK_AWS_IOT_PRIVATE_KEY_PEM",
            "RX671_EK_AWS_IOT_ENDPOINT",
            "AWS_IOT_ENDPOINT",
        ):
            self.assertIn(required, preflight)
        self.assertIn('$env:RX671_OTA_BASELINE_VERSION -ne "0.1.0"', preflight)
        self.assertIn('$env:RX671_OTA_CANDIDATE_VERSION -ne "0.1.1"', preflight)
        self.assertIn('$env:RX671_OTA_REQUIRE_TLS_VERSION -ne "TLSv1.2"', preflight)
        self.assertNotIn("RX671_OTA_ARTIFACT_KEY", preflight)
        self.assertIn("tools/plan_rx671_ota.py create", preflight)
        self.assertIn("--plan-job-id \"$env:CI_JOB_ID\"", preflight)
        self.assertIn("ephemeral_thing_plan.json", preflight)
        self.assertIn(
            "RX671_OTA_PLAN_JOB_ID=$env:CI_JOB_ID",
            preflight,
        )
        self.assertIn(
            "RX671_OTA_RESOLVED_SERVICE_ROLE_ARN=",
            preflight,
        )
        self.assertIn("^arn:aws:iam::\\d{12}:role/.+$", preflight)
        self.assertIn("^\\d{12}:role/.+$", preflight)
        self.assertIn('"arn:aws:iam::$configuredRoleArn"', preflight)
        self.assertIn(
            "dotenv: artifacts/preflight_rx671_wifi_ota/plan.env",
            preflight,
        )

    def test_ota_activation_forces_every_producer_needed_by_hardware(self) -> None:
        activation = (
            'RUN_RX671_OTA_TEST == "true" && '
            '$RX671_WIFI_TEST_SCOPE == "ota"'
        )
        for producer in (
            "build_rx671_wifi",
            "build_rx671_bootloader",
            "package_rx671_ota_artifacts",
        ):
            self.assertIn(activation, job(producer))

        package = job("package_rx671_ota_artifacts")
        self.assertIn("- job: preflight_rx671_wifi_ota", package)
        self.assertIn("- job: build_rx671_bootloader", package)
        creator = job("create_rx671_wifi_ota")
        self.assertIn("- job: preflight_rx671_wifi_ota", creator)
        self.assertIn("- job: package_rx671_ota_artifacts", creator)

    def test_ota_park_build_is_credential_free(self) -> None:
        build = job("build_rx671_wifi")
        self.assertIn("$otaParkBuild", build)
        self.assertIn("$buildArgs.SkipWifiConfig = $true", build)
        self.assertIn("$buildArgs.UseLocalJoinConfig = $true", build)
        self.assertLess(
            build.index("if ($otaParkBuild)"),
            build.index("$buildArgs.SkipWifiConfig = $true"),
        )

    def test_ota_bundle_is_direct_formal_and_credential_free(
        self,
    ) -> None:
        package = job("package_rx671_ota_artifacts")
        self.assertIn("$manifest.formal -ne $true", package)
        self.assertIn("$manifest.credentials_embedded -ne $false", package)
        self.assertIn("littlefs_kvs_runtime_provisioning", package)
        self.assertNotIn("RX671_EK_WIFI_PASSPHRASE", package)
        for forbidden in (
            "--runtime-wifi-config",
            "rx671-ota-runtime.tar.enc",
            "protect_secret_artifact.py",
            "RX671_OTA_ARTIFACT_KEY",
            "rx671-ota-secure",
        ):
            self.assertNotIn(forbidden, package)
        artifacts = package.split("\n  artifacts:", 1)[1]
        self.assertNotIn("RX671_OTA_PACKAGE_ARTIFACT_PATH", package)
        self.assertIn("- build/rx671-ota/", artifacts)
        self.assertNotIn("rx671-ota-secure", artifacts)

    def test_creator_uses_transfer_payload_and_pipeline_owned_alias(self) -> None:
        creator = job("create_rx671_wifi_ota")
        ordered = (
            "aws_wifi_rx671_ek.ota.bin",
            "aws_wifi_rx671_ek.ota-signature.der",
            "manage_ephemeral_iot_thing.py create",
            "tools/create_bg96_ota_update.py",
        )
        positions = [creator.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("--custom-signature-der", creator)
        self.assertIn("--code-signer-cert", creator)
        self.assertIn("--ota-update-id \"$otaUpdateId\"", creator)
        self.assertIn("--s3-key \"$otaS3Key\"", creator)
        self.assertIn("--plan-meta-json \"$aliasPlanJson\"", creator)
        self.assertIn(
            "--owner-job-id \"$env:RX671_OTA_PLAN_JOB_ID\"",
            creator,
        )
        self.assertIn(
            '--role-arn "$env:RX671_OTA_RESOLVED_SERVICE_ROLE_ARN"',
            creator,
        )
        self.assertNotIn(
            '--role-arn "$env:RX671_OTA_SERVICE_ROLE_ARN"',
            creator,
        )
        self.assertIn("tools/plan_rx671_ota.py verify", creator)
        self.assertIn(
            "--created-alias-meta-json \"$ephemeralMeta\"",
            creator,
        )
        self.assertNotIn("RX671_OTA_ARTIFACT_KEY", creator)
        self.assertNotIn("protect_secret_artifact.py", creator)
        self.assertIn(
            '$bundleRoot = Join-Path $env:CI_PROJECT_DIR "build\\rx671-ota"',
            creator,
        )
        self.assertNotIn("RX671_EK_WIFI_PASSPHRASE", creator)
        self.assertNotIn("$runtimeDir", creator)

    def test_one_locked_job_owns_provision_baseline_ota_and_park(self) -> None:
        hardware = job("test_rx671_wifi_ota_atomic")
        self.assertIn("- .rx671_wifi_linux_hw_job", hardware)
        for need in (
            "preflight_rx671_wifi_ota",
            "build_rx671_wifi",
            "package_rx671_ota_artifacts",
            "create_rx671_wifi_ota",
        ):
            self.assertIn(f"- job: {need}", hardware)
        ordered = (
            "Preflight erase and park",
            "tools/provision_rx671_ota.py",
            "tools/test_rx671_ota.py",
        )
        positions = [hardware.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        between_tools = hardware[
            hardware.index("tools/provision_rx671_ota.py") :
            hardware.index("tools/test_rx671_ota.py")
        ]
        self.assertNotIn("-erase-chip", between_tools)
        self.assertIn("trap park_board EXIT", hardware)
        self.assertIn("after_script:", hardware)
        self.assertIn("after_script_parked.ok", hardware)
        self.assertIn('rm -rf -- "$secret_dir"', hardware)
        self.assertIn('install -d -m 700 "$secret_dir"', hardware)
        self.assertIn("secret_cleanup_failed", hardware)
        self.assertIn("after_script_cleanup_failed", hardware)
        self.assertIn("--require-tls-version \"$RX671_OTA_REQUIRE_TLS_VERSION\"", hardware)
        self.assertIn("--baseline-version \"$RX671_OTA_BASELINE_VERSION\"", hardware)
        self.assertIn("--candidate-version \"$RX671_OTA_CANDIDATE_VERSION\"", hardware)
        self.assertIn("--wifi-ssid-env RX671_EK_WIFI_SSID", hardware)
        self.assertIn(
            "--wifi-passphrase-env RX671_EK_WIFI_PASSPHRASE",
            hardware,
        )
        self.assertIn('bundle_root="$CI_PROJECT_DIR/build/rx671-ota"', hardware)
        self.assertNotIn("RX671_OTA_ARTIFACT_KEY", hardware)
        self.assertNotIn("protect_secret_artifact.py", hardware)
        self.assertIn("tools/plan_rx671_ota.py verify", hardware)
        self.assertIn("ota_hardware_success.ok", hardware)
        self.assertNotIn(
            'export RX671_OTA_ARTIFACT_SECRET="$RX671_EK_WIFI_PASSPHRASE"',
            hardware,
        )

    def test_cleanup_takes_success_snapshot_before_deleting_every_owner(self) -> None:
        cleanup = job("cleanup_rx671_wifi_ota")
        ordered = (
            "verify_ota_aws_state.py snapshot",
            "verify_ota_aws_state.py cleanup",
            "manage_ephemeral_iot_thing.py cleanup",
        )
        positions = [cleanup.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("when: always", job(".rx671_wifi_ota_cleanup_rules"))
        self.assertIn("allow_failure: false", cleanup)
        self.assertNotIn("\n  needs:", cleanup)
        self.assertIn(
            "dependencies:\n    - preflight_rx671_wifi_ota",
            cleanup,
        )
        self.assertNotIn("create_rx671_wifi_ota", cleanup)
        self.assertNotIn("test_rx671_wifi_ota_atomic", cleanup)
        self.assertIn(
            "tools/plan_rx671_ota.py write-recovery-meta",
            cleanup,
        )
        self.assertIn("--recover-partial", cleanup)
        self.assertIn("--meta-json \"$aliasPlan\"", cleanup)
        self.assertIn(
            "$planJobId = [string]$planPayload.plan_job_id",
            cleanup,
        )
        self.assertNotIn("RX671_OTA_PLAN_JOB_ID", cleanup)
        self.assertIn("post_cleanup_state.json", cleanup)
        self.assertIn("ephemeral_thing_cleanup.json", cleanup)
        self.assertIn("$snapshotMissingPlannedOta = $false", cleanup)
        self.assertIn(
            "Partial OTA snapshot recovery could not find the planned OTA update",
            cleanup,
        )
        self.assertIn('$snapshotPayload.error.type -ceq "ValueError"', cleanup)
        self.assertIn(
            "$snapshotPayload.error.message -ceq $expectedMissingMessage",
            cleanup,
        )
        self.assertIn(
            "($snapshotStatus -ne 0 -and -not $snapshotMissingPlannedOta)",
            cleanup,
        )


if __name__ == "__main__":
    unittest.main()

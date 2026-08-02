from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import manage_rx671_ota_event_policy as manager


PROJECT_ID = "38"
PIPELINE_ID = "9576"
PLAN_JOB_ID = "61300"
REGION = "ap-northeast-1"
ACCOUNT_ID = "123456789012"
THING_NAME = f"rx671-ek-type1yn-01-ota-{PIPELINE_ID}-{PLAN_JOB_ID}"
OTA_UPDATE_ID = f"rx671-software-ota-{PIPELINE_ID}-{PLAN_JOB_ID}"
AWS_IOT_JOB_ID = f"AFR_OTA-{OTA_UPDATE_ID}"
POLICY_NAME = f"rx671-ota-event-{PIPELINE_ID}-{PLAN_JOB_ID}"
PRINCIPAL = f"arn:aws:iot:{REGION}:{ACCOUNT_ID}:cert/example"
POLICY_ARN = f"arn:aws:iot:{REGION}:{ACCOUNT_ID}:policy/{POLICY_NAME}"


def plan() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": PROJECT_ID,
        "pipeline_id": PIPELINE_ID,
        "plan_job_id": PLAN_JOB_ID,
        "region": REGION,
        "thing_name": THING_NAME,
        "ota_update_id": OTA_UPDATE_ID,
        "aws_iot_job_id": AWS_IOT_JOB_ID,
        "event_policy_name": POLICY_NAME,
    }


def alias_meta(*, ready: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "status": "ready" if ready else "planned",
        "region": REGION,
        "thing_name": THING_NAME,
        "principal": PRINCIPAL,
        "owner_project_id": PROJECT_ID,
        "owner_pipeline_id": PIPELINE_ID,
        "owner_job_id": PLAN_JOB_ID,
    }
    if ready:
        payload["verified"] = True
    return payload


def write_inputs(root: Path, *, ready: bool) -> SimpleNamespace:
    plan_path = root / "ota_plan.json"
    alias_path = root / "alias.json"
    plan_path.write_text(json.dumps(plan()), encoding="utf-8")
    alias_path.write_text(json.dumps(alias_meta(ready=ready)), encoding="utf-8")
    return SimpleNamespace(
        plan_json=plan_path,
        alias_meta_json=alias_path,
        meta_json=root / "event_policy_meta.json",
        output_json=root / "event_policy_cleanup.json",
    )


class FakeAws:
    def __init__(self) -> None:
        self.policy: dict[str, object] | None = None
        self.document: dict[str, object] | None = None
        self.tags: dict[str, str] = {}
        self.targets: list[str] = []
        self.calls: list[str] = []
        self.fail_once: str | None = None
        self.fail_error_code: str | None = None
        self.stale_target_reads = 0
        self.detached_target: str | None = None

    @staticmethod
    def result(
        returncode: int = 0, *, stdout: str = "", stderr: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["aws"], returncode=returncode, stdout=stdout, stderr=stderr
        )

    @staticmethod
    def argument(arguments: list[str], name: str) -> str:
        return arguments[arguments.index(name) + 1]

    def __call__(
        self,
        arguments: list[str],
        *,
        region: str,
        check: bool = True,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        self.assert_region(region)
        operation = " ".join(arguments[:2])
        self.calls.append(operation)
        if self.fail_once == operation:
            self.fail_once = None
            raise manager.AwsCommandError(
                operation, 1, self.fail_error_code
            )

        if operation == "iot get-policy":
            if self.policy is None:
                return (
                    self.result(
                        254,
                        stderr="ResourceNotFoundException",
                    ),
                    {},
                )
            return self.result(), dict(self.policy)
        if operation == "iot create-policy":
            self.document = json.loads(
                self.argument(arguments, "--policy-document")
            )
            tag_list = json.loads(self.argument(arguments, "--tags"))
            self.tags = {item["Key"]: item["Value"] for item in tag_list}
            self.policy = {
                "policyName": POLICY_NAME,
                "policyArn": POLICY_ARN,
                "defaultVersionId": "1",
            }
            return self.result(), dict(self.policy)
        if operation == "iot attach-policy":
            self.targets = [self.argument(arguments, "--target")]
            return self.result(), {}
        if operation == "iot get-policy-version":
            assert self.document is not None
            return self.result(), {
                "policyDocument": urllib.parse.quote(
                    json.dumps(self.document, separators=(",", ":"))
                )
            }
        if operation == "iot list-tags-for-resource":
            return self.result(), {
                "tags": [
                    {"Key": key, "Value": value}
                    for key, value in self.tags.items()
                ]
            }
        if operation == "iot list-policy-versions":
            return self.result(), {
                "policyVersions": [
                    {"versionId": "1", "isDefaultVersion": True}
                ]
            }
        if operation == "iot list-targets-for-policy":
            if self.stale_target_reads > 0 and self.detached_target:
                self.stale_target_reads -= 1
                return self.result(), {"targets": [self.detached_target]}
            return self.result(), {"targets": list(self.targets)}
        if operation == "iot list-attached-policies":
            policies = []
            if PRINCIPAL in self.targets:
                policies.append(
                    {"policyName": POLICY_NAME, "policyArn": POLICY_ARN}
                )
            policies.append(
                {"policyName": "normal-device-policy", "policyArn": "normal"}
            )
            return self.result(), {"policies": policies}
        if operation == "iot detach-policy":
            self.detached_target = self.argument(arguments, "--target")
            self.targets = []
            return self.result(), {}
        if operation == "iot delete-policy":
            if self.targets:
                raise AssertionError("test double refuses deletion while attached")
            self.policy = None
            self.document = None
            self.tags = {}
            return self.result(), {}
        raise AssertionError(f"unexpected AWS operation: {operation}")

    @staticmethod
    def assert_region(region: str) -> None:
        if region != REGION:
            raise AssertionError(f"unexpected region: {region}")

    def seed_owned_policy(self, *, attached: bool = True) -> None:
        context = manager.build_context(
            plan(), alias_meta(ready=True), require_alias_ready=True
        )
        self.policy = {
            "policyName": POLICY_NAME,
            "policyArn": POLICY_ARN,
            "defaultVersionId": "1",
        }
        self.document = context.policy_document
        self.tags = dict(context.owner_tags)
        self.targets = [PRINCIPAL] if attached else []


class Rx671OtaEventPolicyTests(unittest.TestCase):
    def test_document_grants_only_the_exact_cancellation_event(self) -> None:
        context = manager.build_context(
            plan(), alias_meta(ready=True), require_alias_ready=True
        )
        statements = context.policy_document["Statement"]
        self.assertEqual(2, len(statements))
        self.assertEqual(
            ["iot:Subscribe", "iot:Receive"],
            [statement["Action"] for statement in statements],
        )
        for statement in statements:
            resource = statement["Resource"]
            self.assertIn(
                f"$aws/events/job/{AWS_IOT_JOB_ID}/cancellation_in_progress",
                resource,
            )
            self.assertNotIn("*", resource)
            self.assertNotIn("#", resource)
        self.assertIn(":topicfilter/", statements[0]["Resource"])
        self.assertIn(":topic/", statements[1]["Resource"])
        self.assertNotIn("iot:Publish", manager.canonical_json(statements))

    def test_create_verifies_document_tags_and_attachment_then_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_args = write_inputs(root, ready=True)
            fake = FakeAws()
            with mock.patch.object(manager, "run_aws", side_effect=fake):
                self.assertEqual(0, manager.create_policy(create_args))
            journal = json.loads(
                create_args.meta_json.read_text(encoding="utf-8")
            )
            self.assertEqual("ready", journal["status"])
            self.assertTrue(journal["verified"])
            self.assertEqual(
                {
                    "safftiOwnerProjectId": PROJECT_ID,
                    "safftiOwnerPipelineId": PIPELINE_ID,
                    "safftiOwnerJobId": PLAN_JOB_ID,
                },
                fake.tags,
            )
            self.assertEqual([PRINCIPAL], fake.targets)

            cleanup_args = write_inputs(root, ready=False)
            with mock.patch.object(manager, "run_aws", side_effect=fake):
                self.assertEqual(0, manager.cleanup_policy(cleanup_args))
            cleanup = json.loads(
                cleanup_args.output_json.read_text(encoding="utf-8")
            )
            self.assertEqual("complete", cleanup["status"])
            self.assertTrue(cleanup["verification"]["event_policy_absent"])
            self.assertIsNone(fake.policy)
            self.assertLess(
                fake.calls.index("iot detach-policy"),
                fake.calls.index("iot delete-policy"),
            )

    def test_create_refuses_collision_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = write_inputs(Path(temporary), ready=True)
            fake = FakeAws()
            fake.seed_owned_policy()
            with (
                mock.patch.object(manager, "run_aws", side_effect=fake),
                self.assertRaisesRegex(RuntimeError, "refusing to adopt"),
            ):
                manager.create_policy(args)
            journal = json.loads(args.meta_json.read_text(encoding="utf-8"))
            self.assertEqual("collision", journal["status"])
            self.assertNotIn("iot detach-policy", fake.calls)
            self.assertNotIn("iot delete-policy", fake.calls)
            self.assertIsNotNone(fake.policy)

    def test_create_verification_failure_rolls_back_only_owned_policy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = write_inputs(Path(temporary), ready=True)
            fake = FakeAws()
            fake.fail_once = "iot list-attached-policies"
            with (
                mock.patch.object(manager, "run_aws", side_effect=fake),
                self.assertRaises(manager.AwsCommandError),
            ):
                manager.create_policy(args)
            journal = json.loads(args.meta_json.read_text(encoding="utf-8"))
            self.assertEqual("error", journal["status"])
            self.assertTrue(journal["rollback_complete"])
            self.assertEqual(
                ["detach-policy", "delete-policy"],
                journal["rollback_actions"],
            )
            self.assertIsNone(fake.policy)

    def test_cleanup_refuses_owner_tag_mismatch_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = write_inputs(Path(temporary), ready=False)
            fake = FakeAws()
            fake.seed_owned_policy()
            fake.tags["safftiOwnerPipelineId"] = "other"
            with (
                mock.patch.object(manager, "run_aws", side_effect=fake),
                self.assertRaisesRegex(RuntimeError, "owner tags mismatch"),
            ):
                manager.cleanup_policy(args)
            self.assertNotIn("iot detach-policy", fake.calls)
            self.assertNotIn("iot delete-policy", fake.calls)
            self.assertIsNotNone(fake.policy)

    def test_cleanup_refuses_an_unexpected_target_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = write_inputs(Path(temporary), ready=False)
            fake = FakeAws()
            fake.seed_owned_policy()
            fake.targets.append(
                f"arn:aws:iot:{REGION}:{ACCOUNT_ID}:cert/foreign"
            )
            with (
                mock.patch.object(manager, "run_aws", side_effect=fake),
                self.assertRaisesRegex(RuntimeError, "unexpected targets"),
            ):
                manager.cleanup_policy(args)
            self.assertNotIn("iot detach-policy", fake.calls)
            self.assertNotIn("iot delete-policy", fake.calls)
            self.assertIsNotNone(fake.policy)

    def test_cleanup_is_idempotent_when_policy_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = write_inputs(Path(temporary), ready=False)
            fake = FakeAws()
            with mock.patch.object(manager, "run_aws", side_effect=fake):
                self.assertEqual(0, manager.cleanup_policy(args))
            result = json.loads(
                args.output_json.read_text(encoding="utf-8")
            )
            self.assertEqual("complete", result["status"])
            self.assertEqual([], result["actions"])
            self.assertTrue(result["verification"]["event_policy_absent"])

    def test_cleanup_retries_only_detach_propagation_delete_conflict(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = write_inputs(Path(temporary), ready=False)
            fake = FakeAws()
            fake.seed_owned_policy()
            fake.fail_once = "iot delete-policy"
            fake.fail_error_code = "DeleteConflictException"
            with (
                mock.patch.object(manager, "run_aws", side_effect=fake),
                mock.patch.object(manager.time, "sleep") as sleep,
            ):
                self.assertEqual(0, manager.cleanup_policy(args))
            sleep.assert_called_once_with(
                manager.DELETE_RETRY_INTERVAL_SECONDS
            )
            self.assertEqual(2, fake.calls.count("iot delete-policy"))
            self.assertIsNone(fake.policy)

    def test_cleanup_waits_for_detach_target_visibility_to_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = write_inputs(Path(temporary), ready=False)
            fake = FakeAws()
            fake.seed_owned_policy()
            fake.stale_target_reads = 1
            with (
                mock.patch.object(manager, "run_aws", side_effect=fake),
                mock.patch.object(manager.time, "sleep") as sleep,
            ):
                self.assertEqual(0, manager.cleanup_policy(args))
            sleep.assert_called_once_with(
                manager.DELETE_RETRY_INTERVAL_SECONDS
            )
            self.assertIsNone(fake.policy)

    def test_aws_failure_does_not_echo_principal_account_or_token(self) -> None:
        leaked_token = "private-token-value"
        result = subprocess.CompletedProcess(
            args=["aws"],
            returncode=1,
            stdout="",
            stderr=(
                "AccessDeniedException for "
                f"{PRINCIPAL} account {ACCOUNT_ID} token {leaked_token}"
            ),
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(manager.subprocess, "run", return_value=result),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            self.assertRaises(manager.AwsCommandError) as caught,
        ):
            manager.run_aws(
                ["iot", "attach-policy", "--target", PRINCIPAL],
                region=REGION,
            )
        visible = stdout.getvalue() + stderr.getvalue() + str(caught.exception)
        self.assertIn("AccessDeniedException", visible)
        for forbidden in (PRINCIPAL, ACCOUNT_ID, leaked_token):
            self.assertNotIn(forbidden, visible)


if __name__ == "__main__":
    unittest.main()

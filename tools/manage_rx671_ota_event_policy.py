#!/usr/bin/env python3
"""Manage the pipeline-owned AWS IoT Jobs event policy for RX671 OTA.

The RX671 OTA demo subscribes to the AWS-managed per-job cancellation topic.
The normal device policy deliberately remains unchanged.  This helper creates
one tagged, short-lived policy for the exact planned AWS IoT Job, verifies its
document and certificate attachment, and removes it fail-closed during the
independent cleanup job.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POLICY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_+=,.@-]{1,128}$")
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CERTIFICATE_ARN_PATTERN = re.compile(
    r"^arn:(aws(?:-us-gov|-cn)?):iot:([^:]+):(\d{12}):cert/[^/]+$"
)
OWNER_TAG_KEYS = {
    "project": "safftiOwnerProjectId",
    "pipeline": "safftiOwnerPipelineId",
    "job": "safftiOwnerJobId",
}
DELETE_RETRY_ATTEMPTS = 61
DELETE_RETRY_INTERVAL_SECONDS = 5


class AwsCommandError(RuntimeError):
    """An AWS CLI operation failed without echoing resource identifiers."""

    def __init__(
        self,
        operation: str,
        returncode: int,
        error_code: str | None = None,
    ):
        suffix = f", code={error_code}" if error_code else ""
        super().__init__(
            f"AWS IoT operation {operation!r} failed "
            f"(exit={returncode}{suffix})"
        )
        self.operation = operation
        self.returncode = returncode
        self.error_code = error_code


@dataclass(frozen=True)
class PolicyContext:
    region: str
    partition: str
    account_id: str
    principal: str
    policy_name: str
    policy_arn: str
    aws_iot_job_id: str
    owner_tags: dict[str, str]
    policy_document: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def aws_command_prefix() -> list[str]:
    if os.environ.get("AWS_CLI_USE_PYTHON_MODULE") == "1":
        return [
            sys.executable,
            "-c",
            "import sys; from awscli.clidriver import main; sys.exit(main())",
        ]
    configured = os.environ.get("AWS_CLI_EXE")
    if configured:
        return [configured]
    for candidate in ("aws", "aws.cmd", "aws.exe"):
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]
    return ["aws"]


def run_aws(
    arguments: list[str],
    *,
    region: str,
    check: bool = True,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    operation = " ".join(arguments[:2])
    command = [
        *aws_command_prefix(),
        *arguments,
        "--region",
        region,
        "--output",
        "json",
    ]
    print(f"+ aws {operation}")
    result = subprocess.run(command, capture_output=True, text=True)
    if check and result.returncode != 0:
        error_match = re.search(
            r"\b([A-Za-z][A-Za-z0-9]+Exception)\b",
            result.stderr,
        )
        raise AwsCommandError(
            operation,
            result.returncode,
            error_match.group(1) if error_match else None,
        )
    payload: dict[str, Any] = {}
    if result.returncode == 0 and result.stdout.strip():
        parsed = json.loads(result.stdout)
        if not isinstance(parsed, dict):
            raise RuntimeError("AWS CLI output must be a JSON object")
        payload = parsed
    return result, payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return payload


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def owner_tags(plan: dict[str, Any]) -> dict[str, str]:
    values = {
        OWNER_TAG_KEYS["project"]: str(plan.get("project_id", "")),
        OWNER_TAG_KEYS["pipeline"]: str(plan.get("pipeline_id", "")),
        OWNER_TAG_KEYS["job"]: str(plan.get("plan_job_id", "")),
    }
    if any(not value.isdecimal() for value in values.values()):
        raise RuntimeError("OTA plan owner IDs must contain decimal digits only")
    return values


def build_policy_document(
    *, partition: str, region: str, account_id: str, job_id: str
) -> dict[str, Any]:
    topic = f"$aws/events/job/{job_id}/cancellation_in_progress"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iot:Subscribe",
                "Resource": (
                    f"arn:{partition}:iot:{region}:{account_id}:"
                    f"topicfilter/{topic}"
                ),
            },
            {
                "Effect": "Allow",
                "Action": "iot:Receive",
                "Resource": (
                    f"arn:{partition}:iot:{region}:{account_id}:topic/{topic}"
                ),
            },
        ],
    }


def build_context(
    plan: dict[str, Any],
    alias_meta: dict[str, Any],
    *,
    require_alias_ready: bool,
) -> PolicyContext:
    tags = owner_tags(plan)
    project_id = tags[OWNER_TAG_KEYS["project"]]
    pipeline_id = tags[OWNER_TAG_KEYS["pipeline"]]
    plan_job_id = tags[OWNER_TAG_KEYS["job"]]
    expected_ota_id = f"rx671-software-ota-{pipeline_id}-{plan_job_id}"
    expected_job_id = f"AFR_OTA-{expected_ota_id}"
    expected_policy_name = f"rx671-ota-event-{pipeline_id}-{plan_job_id}"
    if plan.get("ota_update_id") != expected_ota_id:
        raise RuntimeError("OTA plan update ID is not pipeline-owned")
    job_id = str(plan.get("aws_iot_job_id", ""))
    if job_id != expected_job_id or not JOB_ID_PATTERN.fullmatch(job_id):
        raise RuntimeError("OTA plan AWS IoT Job ID is invalid")
    policy_name = str(plan.get("event_policy_name", ""))
    if (
        policy_name != expected_policy_name
        or not POLICY_NAME_PATTERN.fullmatch(policy_name)
    ):
        raise RuntimeError("OTA plan event policy name is invalid")

    region = str(plan.get("region", ""))
    if not region or alias_meta.get("region") != region:
        raise RuntimeError("OTA plan and Thing journal region mismatch")
    expected_alias = {
        "owner_project_id": project_id,
        "owner_pipeline_id": pipeline_id,
        "owner_job_id": plan_job_id,
        "thing_name": plan.get("thing_name"),
    }
    mismatches = [
        key for key, value in expected_alias.items()
        if alias_meta.get(key) != value
    ]
    if mismatches:
        raise RuntimeError(
            "Thing journal does not match OTA ownership: "
            + ", ".join(mismatches)
        )
    if require_alias_ready and (
        alias_meta.get("status") != "ready"
        or alias_meta.get("verified") is not True
    ):
        raise RuntimeError("created Thing journal is not verified ready")

    principal = str(alias_meta.get("principal", ""))
    match = CERTIFICATE_ARN_PATTERN.fullmatch(principal)
    if match is None:
        raise RuntimeError("Thing journal principal is not a certificate ARN")
    partition, principal_region, account_id = match.groups()
    if principal_region != region:
        raise RuntimeError("certificate and OTA plan region mismatch")
    policy_arn = (
        f"arn:{partition}:iot:{region}:{account_id}:policy/{policy_name}"
    )
    document = build_policy_document(
        partition=partition,
        region=region,
        account_id=account_id,
        job_id=job_id,
    )
    return PolicyContext(
        region=region,
        partition=partition,
        account_id=account_id,
        principal=principal,
        policy_name=policy_name,
        policy_arn=policy_arn,
        aws_iot_job_id=job_id,
        owner_tags=tags,
        policy_document=document,
    )


def is_not_found(result: subprocess.CompletedProcess[str]) -> bool:
    combined = f"{result.stdout}\n{result.stderr}"
    return "ResourceNotFoundException" in combined


def get_policy(context: PolicyContext) -> dict[str, Any] | None:
    result, payload = run_aws(
        ["iot", "get-policy", "--policy-name", context.policy_name],
        region=context.region,
        check=False,
    )
    if result.returncode == 0:
        return payload
    if is_not_found(result):
        return None
    error_match = re.search(
        r"\b([A-Za-z][A-Za-z0-9]+Exception)\b",
        result.stderr,
    )
    raise AwsCommandError(
        "iot get-policy",
        result.returncode,
        error_match.group(1) if error_match else None,
    )


def decode_policy_document(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise RuntimeError("AWS IoT policy document is malformed")
    try:
        decoded = json.loads(urllib.parse.unquote(value))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError("AWS IoT policy document is malformed") from error
    if not isinstance(decoded, dict):
        raise RuntimeError("AWS IoT policy document is malformed")
    return decoded


def get_default_policy_document(
    context: PolicyContext,
    policy: dict[str, Any],
) -> dict[str, Any]:
    version_id = policy.get("defaultVersionId")
    if not isinstance(version_id, str) or not version_id:
        raise RuntimeError("AWS IoT policy has no default version")
    _, payload = run_aws(
        [
            "iot",
            "get-policy-version",
            "--policy-name",
            context.policy_name,
            "--policy-version-id",
            version_id,
        ],
        region=context.region,
    )
    return decode_policy_document(payload.get("policyDocument"))


def list_policy_versions(context: PolicyContext) -> list[dict[str, Any]]:
    _, payload = run_aws(
        ["iot", "list-policy-versions", "--policy-name", context.policy_name],
        region=context.region,
    )
    versions = payload.get("policyVersions", [])
    if not isinstance(versions, list) or not all(
        isinstance(item, dict) for item in versions
    ):
        raise RuntimeError("AWS IoT policy version list is malformed")
    return versions


def list_policy_targets(context: PolicyContext) -> list[str]:
    _, payload = run_aws(
        ["iot", "list-targets-for-policy", "--policy-name", context.policy_name],
        region=context.region,
    )
    targets = payload.get("targets", [])
    if not isinstance(targets, list) or not all(
        isinstance(item, str) for item in targets
    ):
        raise RuntimeError("AWS IoT policy target list is malformed")
    return targets


def list_attached_policy_names(context: PolicyContext) -> list[str]:
    _, payload = run_aws(
        ["iot", "list-attached-policies", "--target", context.principal],
        region=context.region,
    )
    policies = payload.get("policies", [])
    if not isinstance(policies, list):
        raise RuntimeError("AWS IoT attached policy list is malformed")
    names: list[str] = []
    for item in policies:
        if not isinstance(item, dict) or not isinstance(
            item.get("policyName"), str
        ):
            raise RuntimeError("AWS IoT attached policy entry is malformed")
        names.append(item["policyName"])
    return names


def list_policy_tags(context: PolicyContext) -> dict[str, str]:
    _, payload = run_aws(
        ["iot", "list-tags-for-resource", "--resource-arn", context.policy_arn],
        region=context.region,
    )
    tags = payload.get("tags", [])
    if not isinstance(tags, list):
        raise RuntimeError("AWS IoT policy tag list is malformed")
    normalized: dict[str, str] = {}
    for item in tags:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("Key"), str)
            or not isinstance(item.get("Value"), str)
        ):
            raise RuntimeError("AWS IoT policy tag is malformed")
        normalized[item["Key"]] = item["Value"]
    return normalized


def verify_owned_policy(
    context: PolicyContext,
    *,
    allow_detached: bool,
) -> dict[str, Any]:
    policy = get_policy(context)
    if policy is None:
        raise RuntimeError("pipeline-owned event policy is absent")
    if (
        policy.get("policyName") != context.policy_name
        or policy.get("policyArn") != context.policy_arn
    ):
        raise RuntimeError("live event policy identity mismatch")
    live_document = get_default_policy_document(context, policy)
    if canonical_json(live_document) != canonical_json(context.policy_document):
        raise RuntimeError("live event policy document mismatch")
    if list_policy_tags(context) != context.owner_tags:
        raise RuntimeError("live event policy owner tags mismatch")
    versions = list_policy_versions(context)
    if len(versions) != 1 or versions[0].get("isDefaultVersion") is not True:
        raise RuntimeError("live event policy has unexpected versions")
    targets = list_policy_targets(context)
    allowed_targets = [] if allow_detached else [context.principal]
    if targets not in ([context.principal], allowed_targets):
        raise RuntimeError("live event policy has unexpected targets")
    if not allow_detached and context.policy_name not in list_attached_policy_names(
        context
    ):
        raise RuntimeError("event policy is not attached to the expected certificate")
    return {
        "document_matches": True,
        "owner_tags_match": True,
        "single_default_version": True,
        "target_count": len(targets),
        "expected_target_attached": context.principal in targets,
    }


def base_journal(context: PolicyContext) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "planned",
        "created_at_utc": utc_now(),
        "region": context.region,
        "policy_name": context.policy_name,
        "aws_iot_job_id": context.aws_iot_job_id,
        "owner_tags": context.owner_tags,
        "policy_document_sha256": digest_text(
            canonical_json(context.policy_document)
        ),
        "target_sha256": digest_text(context.principal),
        "operations": [],
        "verified": False,
    }


def delete_owned_policy(
    context: PolicyContext,
    *,
    actions: list[str],
) -> None:
    policy = get_policy(context)
    if policy is None:
        return
    verification = verify_owned_policy(context, allow_detached=True)
    if verification["expected_target_attached"]:
        run_aws(
            [
                "iot",
                "detach-policy",
                "--policy-name",
                context.policy_name,
                "--target",
                context.principal,
            ],
            region=context.region,
        )
        actions.append("detach-policy")
    for attempt in range(DELETE_RETRY_ATTEMPTS):
        remaining = list_policy_targets(context)
        if not remaining:
            break
        if remaining != [context.principal]:
            raise RuntimeError("event policy gained an unexpected target")
        if attempt == DELETE_RETRY_ATTEMPTS - 1:
            raise RuntimeError("event policy still has a target after detach")
        print(
            "AWS IoT policy detach is still propagating; "
            "retrying target verification."
        )
        time.sleep(DELETE_RETRY_INTERVAL_SECONDS)
    for attempt in range(DELETE_RETRY_ATTEMPTS):
        try:
            run_aws(
                ["iot", "delete-policy", "--policy-name", context.policy_name],
                region=context.region,
            )
            break
        except AwsCommandError as error:
            if error.error_code == "ResourceNotFoundException":
                break
            if (
                error.error_code != "DeleteConflictException"
                or attempt == DELETE_RETRY_ATTEMPTS - 1
            ):
                raise
            print(
                "AWS IoT policy detach is still propagating; "
                "retrying delete-policy."
            )
            time.sleep(DELETE_RETRY_INTERVAL_SECONDS)
    actions.append("delete-policy")
    if get_policy(context) is not None:
        raise RuntimeError("event policy still exists after delete")


def create_policy(args: argparse.Namespace) -> int:
    plan = load_json(args.plan_json.resolve())
    alias_meta = load_json(args.alias_meta_json.resolve())
    context = build_context(plan, alias_meta, require_alias_ready=True)
    meta_path = args.meta_json.resolve()
    journal = base_journal(context)
    write_json(meta_path, journal)
    created_by_this_run = False
    try:
        if get_policy(context) is not None:
            journal["status"] = "collision"
            write_json(meta_path, journal)
            raise RuntimeError("refusing to adopt an existing event policy")

        _, created = run_aws(
            [
                "iot",
                "create-policy",
                "--policy-name",
                context.policy_name,
                "--policy-document",
                canonical_json(context.policy_document),
                "--tags",
                json.dumps(
                    [
                        {"Key": key, "Value": value}
                        for key, value in sorted(context.owner_tags.items())
                    ],
                    separators=(",", ":"),
                ),
            ],
            region=context.region,
        )
        created_by_this_run = True
        if (
            created.get("policyName") != context.policy_name
            or created.get("policyArn") != context.policy_arn
        ):
            raise RuntimeError("created event policy identity mismatch")
        journal["status"] = "created"
        journal["operations"].append("create-policy")
        write_json(meta_path, journal)

        run_aws(
            [
                "iot",
                "attach-policy",
                "--policy-name",
                context.policy_name,
                "--target",
                context.principal,
            ],
            region=context.region,
        )
        journal["status"] = "attached"
        journal["operations"].append("attach-policy")
        write_json(meta_path, journal)

        journal["verification"] = verify_owned_policy(
            context, allow_detached=False
        )
        journal["status"] = "ready"
        journal["verified"] = True
        journal["completed_at_utc"] = utc_now()
        write_json(meta_path, journal)
        print("RX671 OTA event policy is verified ready")
        return 0
    except Exception as error:
        rollback_actions: list[str] = []
        rollback_error: Exception | None = None
        if created_by_this_run:
            try:
                delete_owned_policy(context, actions=rollback_actions)
            except Exception as caught:
                rollback_error = caught
        if journal.get("status") != "collision":
            journal["status"] = "error"
        journal["error_type"] = type(error).__name__
        journal["rollback_actions"] = rollback_actions
        journal["rollback_complete"] = (
            created_by_this_run and rollback_error is None
        ) or not created_by_this_run
        if rollback_error is not None:
            journal["rollback_error_type"] = type(rollback_error).__name__
        write_json(meta_path, journal)
        if rollback_error is not None:
            raise RuntimeError(
                "event policy creation failed and rollback was incomplete"
            ) from error
        raise


def cleanup_policy(args: argparse.Namespace) -> int:
    plan = load_json(args.plan_json.resolve())
    alias_meta = load_json(args.alias_meta_json.resolve())
    context = build_context(plan, alias_meta, require_alias_ready=False)
    output_path = args.output_json.resolve()
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "validating",
        "started_at_utc": utc_now(),
        "policy_name": context.policy_name,
        "owner_tags": context.owner_tags,
        "actions": [],
        "errors": [],
        "verification": {},
    }
    write_json(output_path, result)
    try:
        if get_policy(context) is None:
            result["status"] = "complete"
            result["verification"] = {
                "event_policy_absent": True,
                "expected_target_detached": True,
            }
            result["completed_at_utc"] = utc_now()
            write_json(output_path, result)
            return 0
        delete_owned_policy(context, actions=result["actions"])
        attached_names = list_attached_policy_names(context)
        verification = {
            "event_policy_absent": get_policy(context) is None,
            "expected_target_detached": context.policy_name not in attached_names,
        }
        result["verification"] = verification
        if not all(verification.values()):
            raise RuntimeError("event policy cleanup verification failed")
        result["status"] = "complete"
        result["completed_at_utc"] = utc_now()
        write_json(output_path, result)
        return 0
    except Exception as error:
        result["status"] = "failed"
        result["errors"].append(type(error).__name__)
        write_json(output_path, result)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--plan-json", required=True, type=Path)
    create_parser.add_argument("--alias-meta-json", required=True, type=Path)
    create_parser.add_argument("--meta-json", required=True, type=Path)
    create_parser.set_defaults(func=create_policy)

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--plan-json", required=True, type=Path)
    cleanup_parser.add_argument("--alias-meta-json", required=True, type=Path)
    cleanup_parser.add_argument("--output-json", required=True, type=Path)
    cleanup_parser.set_defaults(func=cleanup_policy)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return args.func(args)
    except Exception as error:
        print(
            f"RX671 OTA event policy operation failed: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create and verify the deterministic RX671 software-OTA cleanup journal."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    from tools import manage_ephemeral_iot_thing as thing_manager
except ModuleNotFoundError:  # Direct execution: python tools/plan_rx671_ota.py
    import manage_ephemeral_iot_thing as thing_manager


COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
OTA_UPDATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SOURCE_FILE_NAME = "aws_wifi_rx671_ek.ota.bin"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def require_decimal(label: str, value: str) -> None:
    if not value.isdecimal():
        raise ValueError(f"{label} must contain decimal digits only")


def expected_identity(
    *,
    project_id: str,
    pipeline_id: str,
    plan_job_id: str,
    commit_sha: str,
    base_thing_name: str,
    region: str,
    bucket: str,
    baseline_version: str,
    candidate_version: str,
    tls_version: str,
) -> dict[str, Any]:
    for label, value in (
        ("project ID", project_id),
        ("pipeline ID", pipeline_id),
        ("plan job ID", plan_job_id),
    ):
        require_decimal(label, value)
    if not COMMIT_SHA_PATTERN.fullmatch(commit_sha):
        raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")
    if not region.strip() or not bucket.strip():
        raise ValueError("region and S3 bucket must not be empty")
    if not baseline_version.strip() or not candidate_version.strip():
        raise ValueError("baseline and candidate versions must not be empty")
    if not tls_version.strip():
        raise ValueError("TLS version must not be empty")

    thing_name = f"{base_thing_name}-ota-{pipeline_id}-{plan_job_id}"
    thing_manager.validate_ownership(
        base_thing_name,
        thing_name,
        project_id,
        pipeline_id,
        plan_job_id,
    )
    ota_update_id = f"rx671-software-ota-{pipeline_id}-{plan_job_id}"
    if not OTA_UPDATE_ID_PATTERN.fullmatch(ota_update_id):
        raise ValueError("derived OTA update ID is invalid")
    s3_key = (
        f"ota/{thing_name}/source/{ota_update_id}/{SOURCE_FILE_NAME}"
    )
    return {
        "schema_version": 1,
        "project_id": project_id,
        "pipeline_id": pipeline_id,
        "plan_job_id": plan_job_id,
        "commit_sha": commit_sha,
        "region": region,
        "base_thing_name": base_thing_name,
        "thing_name": thing_name,
        "ota_update_id": ota_update_id,
        "s3_bucket": bucket,
        "s3_key": s3_key,
        "code_signing_mode": "custom",
        "signed_prefix": None,
        "baseline_version": baseline_version,
        "candidate_version": candidate_version,
        "tls_version": tls_version,
    }


def validate_alias_plan(
    plan: dict[str, Any],
    alias_plan: dict[str, Any],
) -> None:
    expected = {
        "schema_version": plan["schema_version"],
        "region": plan["region"],
        "base_thing_name": plan["base_thing_name"],
        "thing_name": plan["thing_name"],
        "owner_project_id": plan["project_id"],
        "owner_pipeline_id": plan["pipeline_id"],
        "owner_job_id": plan["plan_job_id"],
        "owner_attributes": thing_manager.ownership_attributes(
            str(plan["project_id"]),
            str(plan["pipeline_id"]),
            str(plan["plan_job_id"]),
        ),
    }
    mismatches = [
        key for key, value in expected.items()
        if alias_plan.get(key) != value
    ]
    for required in (
        "base_thing_arn",
        "expected_thing_arn",
        "principal",
    ):
        if not alias_plan.get(required):
            mismatches.append(required)
    if mismatches:
        raise ValueError(
            "ephemeral Thing plan mismatch: "
            + ", ".join(sorted(set(mismatches)))
        )


def validate_created_meta(
    plan: dict[str, Any],
    alias_plan: dict[str, Any],
    ota_meta: dict[str, Any],
) -> None:
    expected = {
        "region": plan["region"],
        "thing_name": plan["thing_name"],
        "thing_arn": alias_plan["expected_thing_arn"],
        "ota_update_id": plan["ota_update_id"],
        "s3_bucket": plan["s3_bucket"],
        "s3_key": plan["s3_key"],
        "code_signing_mode": "custom",
        "signed_prefix": None,
        "file_version": plan["candidate_version"],
    }
    mismatches = [
        key for key, value in expected.items()
        if ota_meta.get(key) != value
    ]
    if mismatches:
        raise ValueError(
            "created OTA journal mismatch: " + ", ".join(mismatches)
        )


def build_expected_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return expected_identity(
        project_id=args.project_id,
        pipeline_id=args.pipeline_id,
        plan_job_id=args.plan_job_id,
        commit_sha=args.commit_sha,
        base_thing_name=args.base_thing_name,
        region=args.region,
        bucket=args.bucket,
        baseline_version=args.baseline_version,
        candidate_version=args.candidate_version,
        tls_version=args.tls_version,
    )


def verify_plan_files(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = build_expected_from_args(args)
    plan = load_json(args.plan_json.resolve())
    mismatches = [
        key for key, value in expected.items() if plan.get(key) != value
    ]
    if mismatches:
        raise ValueError(
            "RX671 OTA plan does not belong to this pipeline: "
            + ", ".join(mismatches)
        )
    alias_plan = load_json(args.alias_plan_json.resolve())
    validate_alias_plan(plan, alias_plan)
    if getattr(args, "created_alias_meta_json", None) is not None:
        validate_alias_plan(
            plan,
            load_json(args.created_alias_meta_json.resolve()),
        )
    if getattr(args, "ota_meta_json", None) is not None:
        validate_created_meta(
            plan,
            alias_plan,
            load_json(args.ota_meta_json.resolve()),
        )
    return plan, alias_plan


def create_plan(args: argparse.Namespace) -> int:
    plan = build_expected_from_args(args)
    alias_args = SimpleNamespace(
        base_thing_name=plan["base_thing_name"],
        thing_name=plan["thing_name"],
        region=plan["region"],
        owner_project_id=plan["project_id"],
        owner_pipeline_id=plan["pipeline_id"],
        owner_job_id=plan["plan_job_id"],
    )
    alias_plan = thing_manager.build_alias_plan(alias_args)
    alias_exists, _ = thing_manager.describe_thing(
        plan["thing_name"],
        plan["region"],
    )
    if alias_exists:
        raise RuntimeError(
            f"refusing to adopt an existing Thing: {plan['thing_name']}"
        )
    validate_alias_plan(plan, alias_plan)
    plan["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    thing_manager.write_json(args.plan_json.resolve(), plan)
    thing_manager.write_json(
        args.alias_plan_json.resolve(),
        alias_plan,
    )
    print(plan["thing_name"])
    return 0


def verify_plan(args: argparse.Namespace) -> int:
    plan, _ = verify_plan_files(args)
    print(plan["thing_name"])
    return 0


def write_recovery_meta(args: argparse.Namespace) -> int:
    plan, alias_plan = verify_plan_files(args)
    recovery = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": plan["region"],
        "thing_name": plan["thing_name"],
        "thing_arn": alias_plan["expected_thing_arn"],
        "ota_update_id": plan["ota_update_id"],
        # CREATE_REQUESTED deliberately forces discovery/deletion. It is safe
        # when the creator never submitted the ID because absence is accepted.
        "ota_update_status": "CREATE_REQUESTED",
        "aws_iot_job_id": None,
        "s3_bucket": plan["s3_bucket"],
        "s3_key": plan["s3_key"],
        "s3_version": None,
        "signed_prefix": None,
        "signing_profile": None,
        "signing_job_id": None,
        "code_signing_mode": "custom",
        "file_version": plan["candidate_version"],
        "recovered_from_preflight_plan": True,
    }
    thing_manager.write_json(args.output_json.resolve(), recovery)
    return 0


def add_identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--plan-job-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--base-thing-name", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--baseline-version", required=True)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--tls-version", required=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    add_identity_arguments(create_parser)
    create_parser.add_argument("--plan-json", required=True, type=Path)
    create_parser.add_argument(
        "--alias-plan-json",
        required=True,
        type=Path,
    )
    create_parser.set_defaults(func=create_plan)

    verify_parser = subparsers.add_parser("verify")
    add_identity_arguments(verify_parser)
    verify_parser.add_argument("--plan-json", required=True, type=Path)
    verify_parser.add_argument(
        "--alias-plan-json",
        required=True,
        type=Path,
    )
    verify_parser.add_argument("--created-alias-meta-json", type=Path)
    verify_parser.add_argument("--ota-meta-json", type=Path)
    verify_parser.set_defaults(func=verify_plan)

    recovery_parser = subparsers.add_parser("write-recovery-meta")
    add_identity_arguments(recovery_parser)
    recovery_parser.add_argument("--plan-json", required=True, type=Path)
    recovery_parser.add_argument(
        "--alias-plan-json",
        required=True,
        type=Path,
    )
    recovery_parser.add_argument(
        "--output-json",
        required=True,
        type=Path,
    )
    recovery_parser.set_defaults(func=write_recovery_meta)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Capture and clean up AWS resources created by one OTA acceptance run.

The metadata input is the ``ota_job_meta.json`` emitted by
``create_ota_update.py`` or ``create_bg96_ota_update.py``.  The ``snapshot``
command records only non-secret state and requires a successfully completed
AWS IoT Job and Job execution.  The ``cleanup`` command deletes the OTA update
and source S3 object, then fails unless the OTA update, generated IoT Job, and
the exact S3 object/version are all confirmed absent.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


JOB_TERMINAL_STATUSES = {"CANCELED", "COMPLETED"}
EXECUTION_TERMINAL_STATUSES = {
    "CANCELED",
    "FAILED",
    "REJECTED",
    "REMOVED",
    "SUCCEEDED",
    "TIMED_OUT",
}
NOT_FOUND_MARKERS = (
    "ResourceNotFoundException",
    "NotFoundException",
    "NoSuchKey",
    "NoSuchVersion",
    "(404)",
    "status code: 404",
)


class AwsCommandError(RuntimeError):
    """Raised when an AWS CLI call fails for a reason other than absence."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


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


def _is_not_found(stderr: str) -> bool:
    return any(marker in stderr for marker in NOT_FOUND_MARKERS)


def run_aws(
    args: list[str],
    region: str,
    *,
    absent_ok: bool = False,
) -> dict[str, Any] | None:
    command = [
        *aws_command_prefix(),
        *args,
        "--region",
        region,
        "--output",
        "json",
    ]
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        if absent_ok and _is_not_found(result.stderr):
            return None
        raise AwsCommandError(
            f"AWS CLI command failed with exit {result.returncode}: "
            f"{' '.join(command[: len(aws_command_prefix()) + len(args)])}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def load_meta(
    path: Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = ("region",)
    if require_complete:
        required += (
            "thing_name",
            "ota_update_id",
            "aws_iot_job_id",
            "s3_bucket",
            "s3_key",
        )
    missing = [name for name in required if not payload.get(name)]
    if missing:
        raise ValueError(
            "OTA metadata is incomplete; missing: " + ", ".join(sorted(missing))
        )
    if not require_complete:
        has_s3_bucket = bool(payload.get("s3_bucket"))
        has_s3_key = bool(payload.get("s3_key"))
        if has_s3_bucket != has_s3_key:
            raise ValueError(
                "OTA cleanup metadata must provide s3_bucket and s3_key together"
            )
        if payload.get("s3_version") and not (
            has_s3_bucket and has_s3_key
        ):
            raise ValueError(
                "OTA cleanup metadata s3_version requires "
                "s3_bucket and s3_key"
            )
        has_known_resource = any(
            (
                payload.get("ota_update_id"),
                payload.get("aws_iot_job_id"),
                has_s3_bucket and has_s3_key,
            )
        )
        if not has_known_resource:
            raise ValueError(
                "OTA cleanup metadata contains no known resource identifiers"
            )
    return payload


def public_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        key: meta.get(key)
        for key in (
            "region",
            "thing_name",
            "ota_update_id",
            "aws_iot_job_id",
            "s3_bucket",
            "s3_key",
            "s3_version",
            "file_version",
        )
    }


def s3_head_args(meta: dict[str, Any]) -> list[str]:
    args = [
        "s3api",
        "head-object",
        "--bucket",
        str(meta["s3_bucket"]),
        "--key",
        str(meta["s3_key"]),
    ]
    if meta.get("s3_version"):
        args.extend(["--version-id", str(meta["s3_version"])])
    return args


def list_exact_s3_key_versions(
    meta: dict[str, Any],
    region: str,
) -> list[dict[str, str]]:
    payload = run_aws(
        [
            "s3api",
            "list-object-versions",
            "--bucket",
            str(meta["s3_bucket"]),
            "--prefix",
            str(meta["s3_key"]),
        ],
        region,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("S3 version listing returned malformed output")

    exact_key = str(meta["s3_key"])
    entries: list[dict[str, str]] = []
    for collection, kind in (
        ("Versions", "version"),
        ("DeleteMarkers", "delete-marker"),
    ):
        values = payload.get(collection, [])
        if not isinstance(values, list):
            raise RuntimeError(
                f"S3 version listing field {collection} is malformed"
            )
        for value in values:
            if not isinstance(value, dict) or value.get("Key") != exact_key:
                continue
            version_id = value.get("VersionId")
            if not isinstance(version_id, str) or not version_id:
                raise RuntimeError(
                    "S3 version listing contains an exact-key entry "
                    "without VersionId"
                )
            entries.append(
                {
                    "kind": kind,
                    "key": exact_key,
                    "version_id": version_id,
                }
            )
    return entries


def wait_until_s3_key_fully_absent(
    meta: dict[str, Any],
    region: str,
    *,
    timeout: int,
    poll_interval: int,
) -> bool:
    deadline = time.time() + timeout
    while True:
        versions = list_exact_s3_key_versions(meta, region)
        current = run_aws(s3_head_args(meta), region, absent_ok=True)
        if not versions and current is None:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(poll_interval)


def cleanup_resources(meta: dict[str, Any]) -> list[str]:
    return [
        resource
        for resource, present in (
            ("ota_update", meta.get("ota_update_id")),
            ("aws_iot_job", meta.get("aws_iot_job_id")),
            (
                "s3_source_object",
                meta.get("s3_bucket") and meta.get("s3_key"),
            ),
        )
        if present
    ]


def metadata_identity_error(
    resource: str,
    message: str,
) -> dict[str, str]:
    return {
        "operation": "preflight_identity",
        "resource": resource,
        "error_type": "MetadataIdentityError",
        "message": message,
    }


def validate_cleanup_metadata_identity(
    meta: dict[str, Any],
) -> list[dict[str, str]]:
    has_s3_bucket = bool(meta.get("s3_bucket"))
    has_s3_key = bool(meta.get("s3_key"))
    if has_s3_bucket != has_s3_key:
        return [
            metadata_identity_error(
                "s3_source_object",
                "Metadata must provide s3_bucket and s3_key together",
            )
        ]
    if meta.get("s3_version") and not (has_s3_bucket and has_s3_key):
        return [
            metadata_identity_error(
                "s3_source_object",
                "Metadata s3_version requires s3_bucket and s3_key",
            )
        ]
    return []


def reconcile_live_ota_identity(
    meta: dict[str, Any],
    ota_payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Validate live OTA identity and safely enrich partial metadata."""
    errors: list[dict[str, str]] = []
    updates: dict[str, Any] = {}
    ota_info = ota_payload.get("otaUpdateInfo")
    if not isinstance(ota_info, dict):
        return [
            metadata_identity_error(
                "ota_update",
                "Live OTA response does not contain otaUpdateInfo",
            )
        ]

    live_ota_id = ota_info.get("otaUpdateId")
    if not live_ota_id:
        errors.append(
            metadata_identity_error(
                "ota_update",
                "Live OTA response does not contain otaUpdateId",
            )
        )
    elif live_ota_id != meta.get("ota_update_id"):
        errors.append(
            metadata_identity_error(
                "ota_update",
                (
                    f"Live OTA ID {live_ota_id} does not match metadata "
                    f"{meta.get('ota_update_id')}"
                ),
            )
        )

    live_job_id = ota_info.get("awsIotJobId")
    recorded_job_id = meta.get("aws_iot_job_id")
    if not live_job_id:
        errors.append(
            metadata_identity_error(
                "aws_iot_job",
                "Live OTA response does not contain awsIotJobId",
            )
        )
    elif recorded_job_id and recorded_job_id != live_job_id:
        errors.append(
            metadata_identity_error(
                "aws_iot_job",
                (
                    f"Live OTA reports AWS IoT Job {live_job_id}, but "
                    f"metadata records {recorded_job_id}"
                ),
            )
        )
    elif not recorded_job_id:
        updates["aws_iot_job_id"] = live_job_id

    live_job_arn = ota_info.get("awsIotJobArn")
    recorded_job_arn = meta.get("aws_iot_job_arn")
    if recorded_job_arn and live_job_arn != recorded_job_arn:
        errors.append(
            metadata_identity_error(
                "aws_iot_job",
                (
                    f"Live OTA reports AWS IoT Job ARN {live_job_arn}, but "
                    f"metadata records {recorded_job_arn}"
                ),
            )
        )
    elif not recorded_job_arn and live_job_arn:
        updates["aws_iot_job_arn"] = live_job_arn

    recorded_thing_arn = meta.get("thing_arn")
    live_targets = ota_info.get("targets")
    if recorded_thing_arn and (
        not isinstance(live_targets, list)
        or recorded_thing_arn not in live_targets
    ):
        errors.append(
            metadata_identity_error(
                "ota_update",
                (
                    f"Live OTA targets do not contain metadata thing ARN "
                    f"{recorded_thing_arn}"
                ),
            )
        )

    recorded_bucket = meta.get("s3_bucket")
    recorded_key = meta.get("s3_key")
    recorded_version = meta.get("s3_version")
    if bool(recorded_bucket) != bool(recorded_key):
        errors.append(
            metadata_identity_error(
                "s3_source_object",
                "Metadata must provide s3_bucket and s3_key together",
            )
        )
    elif recorded_version and not (recorded_bucket and recorded_key):
        errors.append(
            metadata_identity_error(
                "s3_source_object",
                "Metadata s3_version requires s3_bucket and s3_key",
            )
        )
    elif recorded_bucket and recorded_key:
        live_s3_files: list[dict[str, Any]] = []
        ota_files = ota_info.get("otaUpdateFiles")
        if isinstance(ota_files, list):
            for ota_file in ota_files:
                if not isinstance(ota_file, dict):
                    continue
                file_location = ota_file.get("fileLocation")
                if not isinstance(file_location, dict):
                    continue
                s3_location = file_location.get("s3Location")
                if not isinstance(s3_location, dict):
                    continue
                live_s3_files.append(
                    {
                        "bucket": s3_location.get("bucket"),
                        "key": s3_location.get("key"),
                        "version": s3_location.get("version"),
                        "file_version": ota_file.get("fileVersion"),
                    }
                )

        matching_files = [
            item
            for item in live_s3_files
            if item["bucket"] == recorded_bucket
            and item["key"] == recorded_key
        ]
        if len(live_s3_files) != 1 or len(matching_files) != 1:
            errors.append(
                metadata_identity_error(
                    "s3_source_object",
                    (
                        "Live OTA does not contain exactly one total S3 file "
                        f"matching {recorded_bucket}/{recorded_key}"
                    ),
                )
            )
        else:
            live_s3_file = matching_files[0]
            live_version = live_s3_file["version"]
            if recorded_version and live_version != recorded_version:
                errors.append(
                    metadata_identity_error(
                        "s3_source_object",
                        (
                            f"Live OTA reports S3 version {live_version}, but "
                            f"metadata records {recorded_version}"
                        ),
                    )
                )
            elif not recorded_version and live_version:
                updates["s3_version"] = live_version

            recorded_file_version = meta.get("file_version")
            live_file_version = live_s3_file["file_version"]
            if (
                recorded_file_version
                and live_file_version != recorded_file_version
            ):
                errors.append(
                    metadata_identity_error(
                        "s3_source_object",
                        (
                            f"Live OTA reports file version "
                            f"{live_file_version}, but metadata records "
                            f"{recorded_file_version}"
                        ),
                    )
                )

    if not errors:
        meta.update(updates)
    return errors


def blocked_cleanup_summary(
    meta: dict[str, Any],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "verified_at_utc": utc_now(),
        "metadata": public_meta(meta),
        "checked_resources": cleanup_resources(meta),
        "actions": [],
        "errors": errors,
        "absence": {
            "ota_update_absent": None,
            "aws_iot_job_absent": None,
            "s3_source_object_or_version_absent": None,
            "passed": False,
        },
    }


def snapshot_state(
    meta: dict[str, Any],
    *,
    wait_timeout: int = 0,
    poll_interval: int = 3,
) -> dict[str, Any]:
    region = str(meta["region"])
    ota_payload = run_aws(
        ["iot", "get-ota-update", "--ota-update-id", str(meta["ota_update_id"])],
        region,
    )
    thing_payload = run_aws(
        ["iot", "describe-thing", "--thing-name", str(meta["thing_name"])],
        region,
    )
    deadline = time.time() + wait_timeout
    while True:
        job_payload = run_aws(
            ["iot", "describe-job", "--job-id", str(meta["aws_iot_job_id"])],
            region,
        )
        execution_payload = run_aws(
            [
                "iot",
                "describe-job-execution",
                "--job-id",
                str(meta["aws_iot_job_id"]),
                "--thing-name",
                str(meta["thing_name"]),
            ],
            region,
        )
        job_status = (job_payload or {}).get("job", {}).get("status")
        execution_status = (execution_payload or {}).get("execution", {}).get(
            "status"
        )
        if (
            job_status in JOB_TERMINAL_STATUSES
            and execution_status in EXECUTION_TERMINAL_STATUSES
        ):
            break
        if time.time() >= deadline:
            break
        time.sleep(poll_interval)
    s3_payload = run_aws(s3_head_args(meta), region)

    ota_info = (ota_payload or {}).get("otaUpdateInfo", {})
    job = (job_payload or {}).get("job", {})
    execution = (execution_payload or {}).get("execution", {})
    thing = thing_payload or {}
    job_status = job.get("status")
    execution_status = execution.get("status")
    ota_status = ota_info.get("otaUpdateStatus")
    process_details = job.get("jobProcessDetails") or {}
    succeeded_things = process_details.get("numberOfSucceededThings")
    failed_count_keys = (
        "numberOfCanceledThings",
        "numberOfFailedThings",
        "numberOfRejectedThings",
        "numberOfRemovedThings",
        "numberOfTimedOutThings",
    )
    job_counts_successful = (
        isinstance(succeeded_things, int)
        and succeeded_things >= 1
        and all(process_details.get(key) == 0 for key in failed_count_keys)
    )
    acceptance = {
        "ota_create_complete": ota_status == "CREATE_COMPLETE",
        "ota_update_id_matches_metadata": (
            ota_info.get("otaUpdateId") == meta["ota_update_id"]
        ),
        "ota_job_id_matches_metadata": (
            ota_info.get("awsIotJobId") == meta["aws_iot_job_id"]
        ),
        "job_terminal": job_status in JOB_TERMINAL_STATUSES,
        "job_successful": job_status == "COMPLETED",
        "job_id_matches_metadata": (
            job.get("jobId") == meta["aws_iot_job_id"]
        ),
        "job_execution_counts_successful": job_counts_successful,
        "execution_terminal": execution_status in EXECUTION_TERMINAL_STATUSES,
        "execution_successful": execution_status == "SUCCEEDED",
        "execution_job_id_matches_metadata": (
            execution.get("jobId") == meta["aws_iot_job_id"]
        ),
        "execution_thing_matches_metadata": (
            execution.get("thingArn") == thing.get("thingArn")
            and thing.get("thingName") == meta["thing_name"]
        ),
        "source_object_present": s3_payload is not None,
    }
    acceptance["passed"] = all(acceptance.values())

    return {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "metadata": public_meta(meta),
        "ota_update": {
            "ota_update_id": ota_info.get("otaUpdateId"),
            "status": ota_status,
            "aws_iot_job_id": ota_info.get("awsIotJobId"),
        },
        "aws_iot_job": {
            "job_id": job.get("jobId"),
            "status": job_status,
            "completed_at": job.get("completedAt"),
            "job_process_details": process_details,
        },
        "aws_iot_thing": {
            "thing_name": thing.get("thingName"),
            "thing_arn": thing.get("thingArn"),
        },
        "aws_iot_job_execution": {
            key: execution.get(key)
            for key in (
                "jobId",
                "thingArn",
                "status",
                "statusDetails",
                "queuedAt",
                "startedAt",
                "lastUpdatedAt",
                "executionNumber",
                "versionNumber",
            )
        },
        "s3_source_object": {
            "exists": s3_payload is not None,
            "bucket": meta["s3_bucket"],
            "key": meta["s3_key"],
            "version_id": meta.get("s3_version"),
            "content_length": (s3_payload or {}).get("ContentLength"),
            "etag": (s3_payload or {}).get("ETag"),
            "last_modified": (s3_payload or {}).get("LastModified"),
        },
        "acceptance": acceptance,
    }


def wait_until_absent(
    args: list[str],
    region: str,
    *,
    timeout: int,
    poll_interval: int,
) -> bool:
    deadline = time.time() + timeout
    while True:
        if run_aws(args, region, absent_ok=True) is None:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(poll_interval)


def cleanup_state(
    meta: dict[str, Any],
    *,
    wait_timeout: int,
    poll_interval: int,
) -> dict[str, Any]:
    region = str(meta["region"])
    actions: list[dict[str, Any]] = []
    errors = validate_cleanup_metadata_identity(meta)
    if errors:
        return blocked_cleanup_summary(meta, errors)

    def attempt(operation: str, resource: str, callback):
        try:
            return True, callback()
        except Exception as exc:
            errors.append(
                {
                    "operation": operation,
                    "resource": resource,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return False, None

    if meta.get("ota_update_id"):
        discovery_ok, discovery_payload = attempt(
            "discover",
            "ota_update",
            lambda: run_aws(
                [
                    "iot",
                    "get-ota-update",
                    "--ota-update-id",
                    str(meta["ota_update_id"]),
                ],
                region,
                absent_ok=True,
            ),
        )
        if not discovery_ok:
            return blocked_cleanup_summary(meta, errors)
        if discovery_payload is not None:
            errors.extend(
                reconcile_live_ota_identity(meta, discovery_payload)
            )
        if errors:
            return blocked_cleanup_summary(meta, errors)

    ota_absent: bool | None = None
    if meta.get("ota_update_id"):
        ota_delete_ok, ota_delete = attempt(
            "delete",
            "ota_update",
            lambda: run_aws(
                [
                    "iot",
                    "delete-ota-update",
                    "--ota-update-id",
                    str(meta["ota_update_id"]),
                    "--delete-stream",
                    "--force-delete-aws-job",
                ],
                region,
                absent_ok=True,
            ),
        )
        actions.append(
            {
                "resource": "ota_update",
                "id": meta["ota_update_id"],
                "delete_succeeded": ota_delete_ok,
                "already_absent": ota_delete_ok and ota_delete is None,
            }
        )
        ota_check_ok, ota_absent_result = attempt(
            "verify_absent",
            "ota_update",
            lambda: wait_until_absent(
                [
                    "iot",
                    "get-ota-update",
                    "--ota-update-id",
                    str(meta["ota_update_id"]),
                ],
                region,
                timeout=wait_timeout,
                poll_interval=poll_interval,
            ),
        )
        ota_absent = bool(ota_absent_result) if ota_check_ok else False

    job_absent: bool | None = None
    if meta.get("aws_iot_job_id"):
        job_args = [
            "iot",
            "describe-job",
            "--job-id",
            str(meta["aws_iot_job_id"]),
        ]
        job_check_ok, job_absent_result = attempt(
            "verify_absent",
            "aws_iot_job",
            lambda: wait_until_absent(
                job_args,
                region,
                timeout=wait_timeout,
                poll_interval=poll_interval,
            ),
        )
        job_absent = bool(job_absent_result) if job_check_ok else False
        if not job_absent:
            delete_job_ok, delete_job = attempt(
                "delete",
                "aws_iot_job",
                lambda: run_aws(
                    [
                        "iot",
                        "delete-job",
                        "--job-id",
                        str(meta["aws_iot_job_id"]),
                        "--force",
                    ],
                    region,
                    absent_ok=True,
                ),
            )
            actions.append(
                {
                    "resource": "aws_iot_job",
                    "id": meta["aws_iot_job_id"],
                    "delete_succeeded": delete_job_ok,
                    "already_absent": delete_job_ok and delete_job is None,
                }
            )
            job_recheck_ok, job_absent_result = attempt(
                "verify_absent_after_delete",
                "aws_iot_job",
                lambda: wait_until_absent(
                    job_args,
                    region,
                    timeout=wait_timeout,
                    poll_interval=poll_interval,
                ),
            )
            job_absent = (
                bool(job_absent_result) if job_recheck_ok else False
            )

    s3_absent: bool | None = None
    if meta.get("s3_bucket") and meta.get("s3_key"):
        if meta.get("s3_version"):
            delete_object_args = [
                "s3api",
                "delete-object",
                "--bucket",
                str(meta["s3_bucket"]),
                "--key",
                str(meta["s3_key"]),
                "--version-id",
                str(meta["s3_version"]),
            ]
            s3_delete_ok, _ = attempt(
                "delete",
                "s3_source_object",
                lambda: run_aws(delete_object_args, region),
            )
            actions.append(
                {
                    "resource": "s3_source_object",
                    "bucket": meta["s3_bucket"],
                    "key": meta["s3_key"],
                    "version_id": meta["s3_version"],
                    "delete_succeeded": s3_delete_ok,
                }
            )
            s3_check_ok, s3_absent_result = attempt(
                "verify_absent",
                "s3_source_object",
                lambda: wait_until_absent(
                    s3_head_args(meta),
                    region,
                    timeout=wait_timeout,
                    poll_interval=poll_interval,
                ),
            )
            s3_absent = (
                bool(s3_absent_result) if s3_check_ok else False
            )
        else:
            versions_ok, versions = attempt(
                "discover_versions",
                "s3_source_object",
                lambda: list_exact_s3_key_versions(meta, region),
            )
            if versions_ok:
                if versions:
                    for version in versions:
                        delete_args = [
                            "s3api",
                            "delete-object",
                            "--bucket",
                            str(meta["s3_bucket"]),
                            "--key",
                            str(meta["s3_key"]),
                            "--version-id",
                            version["version_id"],
                        ]
                        deleted, _ = attempt(
                            "delete_version",
                            "s3_source_object",
                            lambda delete_args=delete_args: run_aws(
                                delete_args,
                                region,
                            ),
                        )
                        actions.append(
                            {
                                "resource": "s3_source_object",
                                "bucket": meta["s3_bucket"],
                                "key": meta["s3_key"],
                                "version_id": version["version_id"],
                                "version_kind": version["kind"],
                                "delete_succeeded": deleted,
                            }
                        )
                else:
                    head_ok, current = attempt(
                        "discover_current",
                        "s3_source_object",
                        lambda: run_aws(
                            s3_head_args(meta),
                            region,
                            absent_ok=True,
                        ),
                    )
                    if head_ok and current is not None:
                        delete_args = [
                            "s3api",
                            "delete-object",
                            "--bucket",
                            str(meta["s3_bucket"]),
                            "--key",
                            str(meta["s3_key"]),
                        ]
                        deleted, _ = attempt(
                            "delete",
                            "s3_source_object",
                            lambda: run_aws(delete_args, region),
                        )
                        actions.append(
                            {
                                "resource": "s3_source_object",
                                "bucket": meta["s3_bucket"],
                                "key": meta["s3_key"],
                                "version_id": None,
                                "delete_succeeded": deleted,
                            }
                        )

                s3_check_ok, s3_absent_result = attempt(
                    "verify_all_versions_absent",
                    "s3_source_object",
                    lambda: wait_until_s3_key_fully_absent(
                        meta,
                        region,
                        timeout=wait_timeout,
                        poll_interval=poll_interval,
                    ),
                )
                s3_absent = (
                    bool(s3_absent_result) if s3_check_ok else False
                )
            else:
                s3_absent = False

    absence = {
        "ota_update_absent": ota_absent,
        "aws_iot_job_absent": job_absent,
        "s3_source_object_or_version_absent": s3_absent,
    }
    checked_absence = [
        value for key, value in absence.items() if key != "passed" and value is not None
    ]
    absence["passed"] = (
        bool(checked_absence)
        and all(checked_absence)
        and not errors
    )
    return {
        "schema_version": 1,
        "verified_at_utc": utc_now(),
        "metadata": public_meta(meta),
        "checked_resources": cleanup_resources(meta),
        "actions": actions,
        "errors": errors,
        "absence": absence,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("snapshot", "cleanup"))
    parser.add_argument("--meta-json", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--wait-timeout", type=int, default=60)
    parser.add_argument("--poll-interval", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    meta: dict[str, Any] | None = None
    try:
        meta = load_meta(
            args.meta_json,
            require_complete=args.command == "snapshot",
        )
        if args.command == "snapshot":
            summary = snapshot_state(
                meta,
                wait_timeout=args.wait_timeout,
                poll_interval=args.poll_interval,
            )
            passed = bool(summary["acceptance"]["passed"])
        else:
            summary = cleanup_state(
                meta,
                wait_timeout=args.wait_timeout,
                poll_interval=args.poll_interval,
            )
            passed = bool(summary["absence"]["passed"])
    except Exception as exc:
        summary = {
            "schema_version": 1,
            "failed_at_utc": utc_now(),
            "command": args.command,
            "metadata": public_meta(meta) if meta is not None else None,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
        passed = False

    write_json(args.output_json, summary)
    if not passed:
        print(
            f"OTA AWS {args.command} verification failed; "
            f"see {args.output_json}",
            file=sys.stderr,
        )
        return 1
    print(f"OTA AWS {args.command} verification passed: {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

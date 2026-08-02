#!/usr/bin/env python3
"""Capture and clean up AWS resources created by one OTA acceptance run.

The metadata input is the ``ota_job_meta.json`` emitted by
``create_ota_update.py`` or ``create_bg96_ota_update.py``.  The ``snapshot``
command records only non-secret state and requires a successfully completed
AWS IoT Job and Job execution.  The ``cleanup`` command deletes the OTA update,
source S3 object, and any AWS Signer output, then fails unless the OTA update,
generated IoT Job, exact source object/version, and every object/version below
the pipeline-owned Signer prefix are all confirmed absent.
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
SIGNING_JOB_TERMINAL_STATUSES = {"Succeeded", "Failed"}
OTA_MUTATING_STATUSES = {
    "CREATE_PENDING",
    "CREATE_IN_PROGRESS",
    "DELETE_IN_PROGRESS",
}
OTA_KNOWN_STATUSES = OTA_MUTATING_STATUSES | {
    "CREATE_COMPLETE",
    "CREATE_FAILED",
    "DELETE_FAILED",
}
OTA_PRECREATE_STATUSES = {"UPLOAD_REQUESTED", "S3_UPLOADED"}
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
            "code_signing_mode",
        )
    missing = [name for name in required if not payload.get(name)]
    if missing:
        raise ValueError(
            "OTA metadata is incomplete; missing: " + ", ".join(sorted(missing))
        )
    code_signing_mode = payload.get("code_signing_mode")
    if code_signing_mode not in {"aws-signer", "custom"}:
        raise ValueError(
            "OTA metadata code_signing_mode must be aws-signer or custom"
        )
    if code_signing_mode == "aws-signer" and not payload.get(
        "signed_prefix"
    ):
        raise ValueError(
            "OTA metadata for aws-signer requires signed_prefix"
        )
    if code_signing_mode == "custom" and payload.get("signed_prefix"):
        raise ValueError(
            "OTA metadata for custom signing must not include signed_prefix"
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
        if payload.get("signed_prefix") and not (
            has_s3_bucket and payload.get("thing_name")
        ):
            raise ValueError(
                "OTA cleanup metadata signed_prefix requires "
                "s3_bucket and thing_name"
            )
        has_known_resource = any(
            (
                payload.get("ota_update_id"),
                payload.get("aws_iot_job_id"),
                has_s3_bucket and has_s3_key,
                payload.get("signed_prefix") and has_s3_bucket,
            )
        )
        if not has_known_resource:
            raise ValueError(
                "OTA cleanup metadata contains no known resource identifiers"
            )
    validate_source_key(payload)
    validate_signed_prefix(payload)
    return payload


def public_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        key: meta.get(key)
        for key in (
            "region",
            "thing_name",
            "thing_arn",
            "ota_update_id",
            "aws_iot_job_id",
            "s3_bucket",
            "s3_key",
            "s3_version",
            "signed_prefix",
            "code_signing_mode",
            "signing_job_id",
            "file_version",
        )
    }


def s3_head_args(
    meta: dict[str, Any],
    *,
    exact_version: bool = True,
) -> list[str]:
    args = [
        "s3api",
        "head-object",
        "--bucket",
        str(meta["s3_bucket"]),
        "--key",
        str(meta["s3_key"]),
    ]
    if exact_version and meta.get("s3_version"):
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


def validate_signed_prefix(meta: dict[str, Any]) -> str | None:
    """Return a safely scoped Signer prefix or fail before any mutation."""

    value = meta.get("signed_prefix")
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Metadata signed_prefix must be a string")
    bucket = meta.get("s3_bucket")
    thing_name = meta.get("thing_name")
    ota_update_id = meta.get("ota_update_id")
    if not bucket or not thing_name or not ota_update_id:
        raise ValueError(
            "Metadata signed_prefix requires s3_bucket, thing_name, and "
            "ota_update_id"
        )
    owner_root = f"ota/{thing_name}/signed/{ota_update_id}/"
    if (
        not value.startswith(owner_root)
        or not value.endswith("/")
    ):
        raise ValueError(
            "Metadata signed_prefix must stay below the OTA update "
            f"namespace {owner_root!r}"
        )
    return value


def validate_source_key(meta: dict[str, Any]) -> str | None:
    """Return a safely scoped source key or fail before any mutation."""

    value = meta.get("s3_key")
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Metadata s3_key must be a string")
    bucket = meta.get("s3_bucket")
    thing_name = meta.get("thing_name")
    ota_update_id = meta.get("ota_update_id")
    if not bucket or not thing_name or not ota_update_id:
        raise ValueError(
            "Metadata s3_key requires s3_bucket, thing_name, and "
            "ota_update_id"
        )
    owner_root = f"ota/{thing_name}/source/{ota_update_id}/"
    if (
        not value.startswith(owner_root)
        or value == owner_root
        or value.endswith("/")
    ):
        raise ValueError(
            "Metadata s3_key must be an object below the OTA update "
            f"namespace {owner_root!r}"
        )
    return value


def list_s3_prefix_versions(
    meta: dict[str, Any],
    region: str,
    prefix: str,
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    key_marker: str | None = None
    version_marker: str | None = None
    seen_markers: set[tuple[str, str]] = set()
    while True:
        arguments = [
            "s3api",
            "list-object-versions",
            "--bucket",
            str(meta["s3_bucket"]),
            "--prefix",
            prefix,
            "--no-paginate",
        ]
        if key_marker is not None:
            arguments.extend(["--key-marker", key_marker])
        if version_marker is not None:
            arguments.extend(["--version-id-marker", version_marker])
        payload = run_aws(arguments, region)
        if not isinstance(payload, dict):
            raise RuntimeError(
                "S3 prefix version listing returned malformed output"
            )

        for collection, kind in (
            ("Versions", "version"),
            ("DeleteMarkers", "delete-marker"),
        ):
            values = payload.get(collection, [])
            if not isinstance(values, list):
                raise RuntimeError(
                    f"S3 prefix version listing field {collection} is "
                    "malformed"
                )
            for value in values:
                if not isinstance(value, dict):
                    raise RuntimeError(
                        "S3 prefix version listing contains a malformed entry"
                    )
                key = value.get("Key")
                if not isinstance(key, str) or not key.startswith(prefix):
                    raise RuntimeError(
                        "S3 prefix version listing returned an out-of-prefix "
                        "entry"
                    )
                version_id = value.get("VersionId")
                if not isinstance(version_id, str) or not version_id:
                    raise RuntimeError(
                        "S3 prefix version listing contains an owned entry "
                        "without VersionId"
                    )
                entries.append(
                    {
                        "kind": kind,
                        "key": key,
                        "version_id": version_id,
                    }
                )

        if payload.get("IsTruncated") is not True:
            break
        next_key = payload.get("NextKeyMarker")
        next_version = payload.get("NextVersionIdMarker")
        if not isinstance(next_key, str) or not next_key:
            raise RuntimeError(
                "Truncated S3 version listing has no NextKeyMarker"
            )
        if next_version is not None and not isinstance(next_version, str):
            raise RuntimeError(
                "Truncated S3 version listing has malformed "
                "NextVersionIdMarker"
            )
        marker = (next_key, next_version or "")
        if marker in seen_markers:
            raise RuntimeError("S3 version listing pagination loop detected")
        seen_markers.add(marker)
        key_marker = next_key
        version_marker = next_version or None
    return entries


def list_current_s3_prefix_keys(
    meta: dict[str, Any],
    region: str,
    prefix: str,
) -> list[str]:
    keys: list[str] = []
    continuation_token: str | None = None
    seen_tokens: set[str] = set()
    while True:
        arguments = [
            "s3api",
            "list-objects-v2",
            "--bucket",
            str(meta["s3_bucket"]),
            "--prefix",
            prefix,
            "--no-paginate",
        ]
        if continuation_token is not None:
            arguments.extend(
                ["--continuation-token", continuation_token]
            )
        payload = run_aws(arguments, region)
        if not isinstance(payload, dict):
            raise RuntimeError("S3 prefix listing returned malformed output")

        values = payload.get("Contents", [])
        if not isinstance(values, list):
            raise RuntimeError("S3 prefix listing field Contents is malformed")
        for value in values:
            if not isinstance(value, dict):
                raise RuntimeError(
                    "S3 prefix listing contains a malformed entry"
                )
            key = value.get("Key")
            if not isinstance(key, str) or not key.startswith(prefix):
                raise RuntimeError(
                    "S3 prefix listing returned an out-of-prefix entry"
                )
            keys.append(key)

        if payload.get("IsTruncated") is not True:
            break
        next_token = payload.get("NextContinuationToken")
        if not isinstance(next_token, str) or not next_token:
            raise RuntimeError(
                "Truncated S3 prefix listing has no NextContinuationToken"
            )
        if next_token in seen_tokens:
            raise RuntimeError("S3 prefix listing pagination loop detected")
        seen_tokens.add(next_token)
        continuation_token = next_token
    return keys


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
        current = run_aws(
            s3_head_args(meta, exact_version=False),
            region,
            absent_ok=True,
        )
        if not versions and current is None:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(poll_interval)


def ota_resource_may_exist(meta: dict[str, Any]) -> bool:
    return bool(
        meta.get("ota_update_id")
        and meta.get("ota_update_status") not in OTA_PRECREATE_STATUSES
    )


def cleanup_resources(meta: dict[str, Any]) -> list[str]:
    return [
        resource
        for resource, present in (
            ("ota_update", ota_resource_may_exist(meta)),
            ("aws_iot_job", meta.get("aws_iot_job_id")),
            (
                "s3_source_object",
                meta.get("s3_bucket") and meta.get("s3_key"),
            ),
            (
                "s3_signer_output_prefix",
                meta.get("s3_bucket") and meta.get("signed_prefix"),
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


def ota_signing_job_id(ota_info: dict[str, Any]) -> str | None:
    signer_ids: set[str] = set()
    ota_files = ota_info.get("otaUpdateFiles")
    if not isinstance(ota_files, list):
        return None
    for ota_file in ota_files:
        if not isinstance(ota_file, dict):
            continue
        code_signing = ota_file.get("codeSigning")
        if not isinstance(code_signing, dict):
            continue
        signer_id = code_signing.get("awsSignerJobId")
        if isinstance(signer_id, str) and signer_id:
            signer_ids.add(signer_id)
    if len(signer_ids) > 1:
        raise ValueError(
            "Live OTA response contains multiple AWS Signer job IDs"
        )
    return next(iter(signer_ids), None)


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
    try:
        validate_source_key(meta)
    except ValueError as error:
        return [
            metadata_identity_error(
                "s3_source_object",
                str(error),
            )
        ]
    code_signing_mode = meta.get("code_signing_mode")
    if code_signing_mode not in {"aws-signer", "custom"}:
        return [
            metadata_identity_error(
                "s3_signer_output_prefix",
                "Metadata code_signing_mode must be aws-signer or custom",
            )
        ]
    if code_signing_mode == "aws-signer" and not meta.get(
        "signed_prefix"
    ):
        return [
            metadata_identity_error(
                "s3_signer_output_prefix",
                "AWS Signer metadata requires signed_prefix",
            )
        ]
    if code_signing_mode == "custom" and meta.get("signed_prefix"):
        return [
            metadata_identity_error(
                "s3_signer_output_prefix",
                "Custom signing metadata must not include signed_prefix",
            )
        ]
    try:
        validate_signed_prefix(meta)
    except ValueError as error:
        return [
            metadata_identity_error(
                "s3_signer_output_prefix",
                str(error),
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

    live_status = ota_info.get("otaUpdateStatus")
    if live_status not in OTA_KNOWN_STATUSES:
        errors.append(
            metadata_identity_error(
                "ota_update",
                (
                    "Live OTA response does not contain a recognized "
                    f"otaUpdateStatus: {live_status!r}"
                ),
            )
        )
    else:
        updates["ota_update_status"] = live_status

    live_job_id = ota_info.get("awsIotJobId")
    recorded_job_id = meta.get("aws_iot_job_id")
    if not live_job_id:
        if live_status != "CREATE_FAILED":
            errors.append(
                metadata_identity_error(
                    "aws_iot_job",
                    (
                        "Live OTA response does not contain awsIotJobId "
                        f"for status {live_status!r}"
                    ),
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
    if (
        recorded_job_arn
        and live_job_arn
        and live_job_arn != recorded_job_arn
    ):
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
    elif (
        recorded_job_arn
        and not live_job_arn
        and live_status != "CREATE_FAILED"
    ):
        errors.append(
            metadata_identity_error(
                "aws_iot_job",
                (
                    "Live OTA response does not contain awsIotJobArn "
                    f"for status {live_status!r}"
                ),
            )
        )

    try:
        live_signer_job_id = ota_signing_job_id(ota_info)
    except ValueError as error:
        errors.append(
            metadata_identity_error(
                "aws_signer_job",
                str(error),
            )
        )
        live_signer_job_id = None
    recorded_signer_job_id = meta.get("signing_job_id")
    if (
        recorded_signer_job_id
        and live_signer_job_id
        and recorded_signer_job_id != live_signer_job_id
    ):
        errors.append(
            metadata_identity_error(
                "aws_signer_job",
                (
                    f"Live OTA reports AWS Signer job "
                    f"{live_signer_job_id}, but metadata records "
                    f"{recorded_signer_job_id}"
                ),
            )
        )
    elif not recorded_signer_job_id and live_signer_job_id:
        updates["signing_job_id"] = live_signer_job_id
    if (
        meta.get("code_signing_mode") == "custom"
        and live_signer_job_id
    ):
        errors.append(
            metadata_identity_error(
                "aws_signer_job",
                "Custom signing OTA unexpectedly reports an AWS Signer job",
            )
        )

    recorded_thing_arn = meta.get("thing_arn")
    live_targets = ota_info.get("targets")
    if recorded_thing_arn:
        targets_missing_after_failed_create = (
            live_status == "CREATE_FAILED" and live_targets is None
        )
        if not targets_missing_after_failed_create and (
            not isinstance(live_targets, list)
            or live_targets != [recorded_thing_arn]
        ):
            errors.append(
                metadata_identity_error(
                    "ota_update",
                    (
                        "Live OTA targets are not exactly the metadata Thing "
                        f"ARN "
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
        files_missing_after_failed_create = (
            live_status == "CREATE_FAILED" and ota_files is None
        )
        exactly_one_ota_file = (
            isinstance(ota_files, list) and len(ota_files) == 1
        )
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

        if not files_missing_after_failed_create:
            matching_files = [
                item
                for item in live_s3_files
                if item["bucket"] == recorded_bucket
                and item["key"] == recorded_key
            ]
        else:
            matching_files = []
        if (
            not files_missing_after_failed_create
            and (
                not exactly_one_ota_file
                or len(live_s3_files) != 1
                or len(matching_files) != 1
            )
        ):
            errors.append(
                metadata_identity_error(
                    "s3_source_object",
                    (
                        "Live OTA does not contain exactly one total S3 file "
                        f"matching {recorded_bucket}/{recorded_key}"
                    ),
                )
            )
        elif not files_missing_after_failed_create:
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


def signing_job_identity_errors(
    meta: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    signer_id = meta.get("signing_job_id")
    prefix = validate_signed_prefix(meta)
    errors: list[dict[str, str]] = []
    if payload.get("jobId") != signer_id:
        errors.append(
            metadata_identity_error(
                "aws_signer_job",
                (
                    f"Signer response job ID {payload.get('jobId')} does not "
                    f"match metadata {signer_id}"
                ),
            )
        )

    source = payload.get("source")
    source_s3 = source.get("s3") if isinstance(source, dict) else None
    expected_source = (
        meta.get("s3_bucket"),
        meta.get("s3_key"),
        meta.get("s3_version"),
    )
    live_source = (
        source_s3.get("bucketName") if isinstance(source_s3, dict) else None,
        source_s3.get("key") if isinstance(source_s3, dict) else None,
        source_s3.get("version") if isinstance(source_s3, dict) else None,
    )
    if live_source[:2] != expected_source[:2] or (
        expected_source[2] and live_source[2] != expected_source[2]
    ):
        errors.append(
            metadata_identity_error(
                "aws_signer_job",
                "Signer source object does not match OTA metadata",
            )
        )

    status = payload.get("status")
    if status not in SIGNING_JOB_TERMINAL_STATUSES | {"InProgress"}:
        errors.append(
            metadata_identity_error(
                "aws_signer_job",
                f"Signer response has unexpected status {status}",
            )
        )
    if status == "Succeeded":
        signed_object = payload.get("signedObject")
        signed_s3 = (
            signed_object.get("s3")
            if isinstance(signed_object, dict)
            else None
        )
        signed_bucket = (
            signed_s3.get("bucketName")
            if isinstance(signed_s3, dict)
            else None
        )
        signed_key = (
            signed_s3.get("key")
            if isinstance(signed_s3, dict)
            else None
        )
        if (
            signed_bucket != meta.get("s3_bucket")
            or not isinstance(signed_key, str)
            or prefix is None
            or not signed_key.startswith(prefix)
        ):
            errors.append(
                metadata_identity_error(
                    "s3_signer_output_prefix",
                    "Signer output object is outside the pipeline prefix",
                )
            )
    return errors


def wait_for_signing_job_terminal(
    meta: dict[str, Any],
    region: str,
    *,
    timeout: int,
    poll_interval: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    while True:
        payload = run_aws(
            [
                "signer",
                "describe-signing-job",
                "--job-id",
                str(meta["signing_job_id"]),
            ],
            region,
        )
        if not isinstance(payload, dict):
            raise RuntimeError(
                "AWS Signer job lookup returned malformed output"
            )
        identity_errors = signing_job_identity_errors(meta, payload)
        if identity_errors:
            raise ValueError(
                "; ".join(error["message"] for error in identity_errors)
            )
        if payload.get("status") in SIGNING_JOB_TERMINAL_STATUSES:
            return payload
        if time.time() >= deadline:
            raise TimeoutError(
                "AWS Signer job did not reach a terminal state before cleanup"
            )
        time.sleep(poll_interval)


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
            "s3_signer_output_prefix_absent": None,
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
        "thing_arn_matches_metadata": (
            not meta.get("thing_arn")
            or thing.get("thingArn") == meta["thing_arn"]
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


def wait_for_ota_cleanup_discovery(
    meta: dict[str, Any],
    region: str,
    *,
    timeout: int,
    poll_interval: int,
) -> dict[str, Any] | None:
    """Wait until an OTA create/delete mutation is terminal before cleanup."""

    deadline: float | None = None
    while True:
        payload = run_aws(
            [
                "iot",
                "get-ota-update",
                "--ota-update-id",
                str(meta["ota_update_id"]),
            ],
            region,
            absent_ok=True,
        )
        if payload is None:
            return None
        ota_info = payload.get("otaUpdateInfo")
        status = (
            ota_info.get("otaUpdateStatus")
            if isinstance(ota_info, dict)
            else None
        )
        if status not in OTA_MUTATING_STATUSES:
            return payload
        if deadline is None:
            deadline = time.time() + timeout
        if time.time() >= deadline:
            raise TimeoutError(
                f"OTA update remained in mutating state {status!r} "
                "until the cleanup deadline"
            )
        time.sleep(poll_interval)


def recover_partial_snapshot_meta(
    meta: dict[str, Any],
    *,
    wait_timeout: int,
    poll_interval: int,
) -> None:
    """Recover a complete snapshot identity from fail-closed plan metadata."""

    required_before_discovery = (
        "region",
        "thing_name",
        "thing_arn",
        "ota_update_id",
        "s3_bucket",
        "s3_key",
        "code_signing_mode",
        "file_version",
    )
    missing = [
        key for key in required_before_discovery if not meta.get(key)
    ]
    if missing:
        raise ValueError(
            "Partial OTA snapshot metadata is incomplete; missing: "
            + ", ".join(sorted(missing))
        )

    metadata_errors = validate_cleanup_metadata_identity(meta)
    if metadata_errors:
        raise ValueError(
            "Partial OTA snapshot metadata identity is invalid: "
            + "; ".join(error["message"] for error in metadata_errors)
        )

    region = str(meta["region"])
    ota_payload = wait_for_ota_cleanup_discovery(
        meta,
        region,
        timeout=wait_timeout,
        poll_interval=poll_interval,
    )
    if ota_payload is None:
        raise ValueError(
            "Partial OTA snapshot recovery could not find the planned OTA "
            f"update {meta['ota_update_id']}"
        )

    identity_errors = reconcile_live_ota_identity(meta, ota_payload)
    if identity_errors:
        raise ValueError(
            "Partial OTA snapshot live identity does not match the plan: "
            + "; ".join(error["message"] for error in identity_errors)
        )

    required_after_discovery = (
        "ota_update_status",
        "aws_iot_job_id",
        "aws_iot_job_arn",
        "s3_version",
    )
    if meta.get("code_signing_mode") == "aws-signer":
        required_after_discovery += ("signing_job_id",)
    missing = [
        key for key in required_after_discovery if not meta.get(key)
    ]
    if missing:
        raise ValueError(
            "Live OTA response could not complete snapshot metadata; missing: "
            + ", ".join(sorted(missing))
        )
    if meta["ota_update_status"] != "CREATE_COMPLETE":
        raise ValueError(
            "Live OTA update is not ready for a successful snapshot: "
            f"{meta['ota_update_status']}"
        )

    job_id = str(meta["aws_iot_job_id"])
    job_arn = str(meta["aws_iot_job_arn"])
    if not job_arn.endswith(f":job/{job_id}"):
        raise ValueError(
            "Live AWS IoT Job ARN does not identify the recovered Job ID: "
            f"{job_arn} versus {job_id}"
        )


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

    ota_may_exist = ota_resource_may_exist(meta)
    ota_discovery_absent = False
    if ota_may_exist:
        discovery_ok, discovery_payload = attempt(
            "discover",
            "ota_update",
            lambda: wait_for_ota_cleanup_discovery(
                meta,
                region,
                timeout=wait_timeout,
                poll_interval=poll_interval,
            ),
        )
        if not discovery_ok:
            return blocked_cleanup_summary(meta, errors)
        if discovery_payload is not None:
            errors.extend(
                reconcile_live_ota_identity(meta, discovery_payload)
            )
        else:
            ota_discovery_absent = True
        if errors:
            return blocked_cleanup_summary(meta, errors)

    if (
        meta.get("code_signing_mode") == "aws-signer"
        and meta.get("signing_job_id")
    ):
        try:
            signer_payload = wait_for_signing_job_terminal(
                meta,
                region,
                timeout=wait_timeout,
                poll_interval=poll_interval,
            )
        except Exception as exc:
            errors.append(
                {
                    "operation": "verify_terminal",
                    "resource": "aws_signer_job",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return blocked_cleanup_summary(meta, errors)
        actions.append(
            {
                "resource": "aws_signer_job",
                "id": meta["signing_job_id"],
                "terminal_status": signer_payload["status"],
                "ownership_verified": True,
            }
        )
    unresolved_signer_submission = bool(
        meta.get("code_signing_mode") == "aws-signer"
        and not meta.get("signing_job_id")
        and meta.get("ota_update_status")
        not in {"UPLOAD_REQUESTED", "S3_UPLOADED"}
    )

    ota_absent: bool | None = None
    if ota_may_exist and ota_discovery_absent:
        ota_absent = True
    elif ota_may_exist:
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
        versions_ok, versions = attempt(
            "discover_versions",
            "s3_source_object",
            lambda: list_exact_s3_key_versions(meta, region),
        )
        if versions_ok:
            recorded_version = meta.get("s3_version")
            if recorded_version and not any(
                version["version_id"] == recorded_version
                for version in versions
            ):
                # Always attempt the journaled version even if an eventually
                # consistent listing has not returned it yet.
                versions.append(
                    {
                        "kind": "version",
                        "key": str(meta["s3_key"]),
                        "version_id": str(recorded_version),
                    }
                )

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

    signed_prefix_absent: bool | None = None
    signed_prefix = validate_signed_prefix(meta)
    if signed_prefix is not None:
        deadline = time.time() + wait_timeout
        post_deadline_deletion_passes = 0
        while True:
            versions_ok, signer_versions = attempt(
                "discover_versions",
                "s3_signer_output_prefix",
                lambda: list_s3_prefix_versions(
                    meta,
                    region,
                    signed_prefix,
                ),
            )
            current_ok, current_keys = attempt(
                "discover_current",
                "s3_signer_output_prefix",
                lambda: list_current_s3_prefix_keys(
                    meta,
                    region,
                    signed_prefix,
                ),
            )
            if not versions_ok or not current_ok:
                signed_prefix_absent = False
                break
            if not signer_versions and not current_keys:
                # A Signer job submitted immediately before a partial create
                # failure can publish its output after cleanup starts.  Keep
                # observing an empty prefix for the configured wait window
                # instead of accepting the first empty listing.
                if time.time() >= deadline:
                    signed_prefix_absent = True
                    break
                time.sleep(poll_interval)
                continue
            if post_deadline_deletion_passes >= 3:
                signed_prefix_absent = False
                break

            delete_failed = False
            versioned_keys = {
                version["key"] for version in signer_versions
            }
            for version in signer_versions:
                delete_args = [
                    "s3api",
                    "delete-object",
                    "--bucket",
                    str(meta["s3_bucket"]),
                    "--key",
                    version["key"],
                    "--version-id",
                    version["version_id"],
                ]
                deleted, _ = attempt(
                    "delete_version",
                    "s3_signer_output_prefix",
                    lambda delete_args=delete_args: run_aws(
                        delete_args,
                        region,
                    ),
                )
                actions.append(
                    {
                        "resource": "s3_signer_output_prefix",
                        "bucket": meta["s3_bucket"],
                        "prefix": signed_prefix,
                        "key": version["key"],
                        "version_id": version["version_id"],
                        "version_kind": version["kind"],
                        "delete_succeeded": deleted,
                    }
                )
                if not deleted:
                    delete_failed = True

            for key in current_keys:
                if key in versioned_keys:
                    continue
                delete_args = [
                    "s3api",
                    "delete-object",
                    "--bucket",
                    str(meta["s3_bucket"]),
                    "--key",
                    key,
                ]
                deleted, _ = attempt(
                    "delete",
                    "s3_signer_output_prefix",
                    lambda delete_args=delete_args: run_aws(
                        delete_args,
                        region,
                    ),
                )
                actions.append(
                    {
                        "resource": "s3_signer_output_prefix",
                        "bucket": meta["s3_bucket"],
                        "prefix": signed_prefix,
                        "key": key,
                        "version_id": None,
                        "delete_succeeded": deleted,
                    }
                )
                if not deleted:
                    delete_failed = True

            if delete_failed:
                signed_prefix_absent = False
                break
            if time.time() >= deadline:
                post_deadline_deletion_passes += 1
            else:
                time.sleep(poll_interval)

    absence = {
        "ota_update_absent": ota_absent,
        "aws_iot_job_absent": job_absent,
        "s3_source_object_or_version_absent": s3_absent,
        "s3_signer_output_prefix_absent": signed_prefix_absent,
    }
    if unresolved_signer_submission:
        errors.append(
            {
                "operation": "verify_terminal",
                "resource": "aws_signer_job",
                "error_type": "UnresolvedSignerSubmission",
                "message": (
                    "OTA creation may have submitted an AWS Signer job, but "
                    "no signing_job_id was journaled; terminal state cannot "
                    "be proven"
                ),
            }
        )
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
    parser.add_argument(
        "--recover-partial",
        action="store_true",
        help=(
            "snapshot only: recover missing live identity fields from the "
            "planned OTA update before taking the normal snapshot"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    meta: dict[str, Any] | None = None
    try:
        if args.recover_partial and args.command != "snapshot":
            raise ValueError("--recover-partial is only valid with snapshot")
        meta = load_meta(
            args.meta_json,
            require_complete=(
                args.command == "snapshot" and not args.recover_partial
            ),
        )
        if args.command == "snapshot":
            if args.recover_partial:
                recover_partial_snapshot_meta(
                    meta,
                    wait_timeout=args.wait_timeout,
                    poll_interval=args.poll_interval,
                )
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

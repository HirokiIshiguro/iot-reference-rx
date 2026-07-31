#!/usr/bin/env python3
"""
Create an AWS IoT OTA update for RX72N and save the resulting metadata.

This helper is used by the RX72N Envision Kit OTA CI path. It uploads a prepared
OTA candidate to S3, creates an OTA update that targets a single thing, waits
for the OTA update to reach a terminal create state, and writes JSON artifacts
for later inspection.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


TERMINAL_CREATE_STATES = {"CREATE_COMPLETE", "CREATE_FAILED", "DELETE_FAILED"}


def run_command(cmd, cwd=None):
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"command failed (exit={result.returncode}): {' '.join(cmd)}")
    return result


def aws_command_prefix():
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


def run_aws(args, region, cwd=None):
    return run_command([*aws_command_prefix(), *args, "--region", region, "--output", "json"], cwd=cwd)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # Preserve the original write/replace failure. A stale temporary
            # file is safer than hiding the failure that kept the old journal.
            pass


def write_meta(path, meta, **updates):
    meta.update({key: value for key, value in updates.items() if value is not None})
    write_json(path, meta)


def validate_signed_prefix(thing_name, ota_update_id, signed_prefix):
    owner_root = f"ota/{thing_name}/signed/{ota_update_id}/"
    if (
        not signed_prefix.startswith(owner_root)
        or not signed_prefix.endswith("/")
    ):
        raise ValueError(
            "signed prefix must stay below the OTA update "
            f"namespace {owner_root!r}"
        )


def validate_source_key(thing_name, ota_update_id, s3_key):
    owner_root = f"ota/{thing_name}/source/{ota_update_id}/"
    if (
        not s3_key.startswith(owner_root)
        or s3_key == owner_root
        or s3_key.endswith("/")
    ):
        raise ValueError(
            "source key must be an object below the OTA update "
            f"namespace {owner_root!r}"
        )


def expand_ota_path_template(value, thing_name, ota_update_id):
    return value.replace("{thing_name}", thing_name).replace(
        "{ota_update_id}",
        ota_update_id,
    )


def load_json(result):
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def ota_meta_updates(payload):
    info = payload.get("otaUpdateInfo", payload)
    signing_job_id = None
    ota_files = info.get("otaUpdateFiles")
    if isinstance(ota_files, list) and ota_files:
        code_signing = ota_files[0].get("codeSigning", {})
        if isinstance(code_signing, dict):
            signing_job_id = code_signing.get("awsSignerJobId")
    return {
        "ota_update_arn": info.get("otaUpdateArn"),
        "ota_update_status": info.get("otaUpdateStatus"),
        "aws_iot_job_id": info.get("awsIotJobId"),
        "aws_iot_job_arn": info.get("awsIotJobArn"),
        "signing_job_id": signing_job_id,
    }


def wait_for_ota_status(
    ota_update_id,
    region,
    timeout_seconds,
    poll_interval,
    *,
    meta_path=None,
    meta=None,
):
    deadline = time.time() + timeout_seconds
    last_payload = None
    while time.time() < deadline:
        result = run_aws(
            ["iot", "get-ota-update", "--ota-update-id", ota_update_id],
            region=region,
        )
        payload = load_json(result)
        last_payload = payload
        if meta_path is not None and meta is not None:
            write_meta(meta_path, meta, **ota_meta_updates(payload))
        status = payload["otaUpdateInfo"]["otaUpdateStatus"]
        print(f"OTA update status: {status}")
        if status in TERMINAL_CREATE_STATES:
            return payload
        time.sleep(poll_interval)
    raise RuntimeError(
        f"timeout waiting for OTA update {ota_update_id} to reach a terminal create state"
    )


def main():
    parser = argparse.ArgumentParser(description="Create AWS IoT OTA update and save metadata artifacts")
    parser.add_argument("--artifact-dir", required=True, help="Directory for JSON artifacts")
    parser.add_argument("--thing-name", required=True, help="AWS IoT thing name")
    parser.add_argument("--input-rsu", required=True, help="Path to OTA candidate .rsu")
    parser.add_argument("--file-version", required=True, help="Target OTA file version (e.g. 0.9.3)")
    parser.add_argument("--bucket", required=True, help="S3 bucket for OTA source image")
    parser.add_argument("--signing-profile", required=True, help="AWS Signer profile name")
    parser.add_argument("--role-arn", required=True, help="AWS IoT OTA service role ARN")
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument("--ota-id-prefix", default="ck-rx65n-ota", help="Prefix for generated OTA update IDs")
    parser.add_argument(
        "--s3-key",
        default=None,
        help=(
            "Optional S3 object key template below ota/<thing-name>/. "
            "Use {thing_name} and {ota_update_id} placeholders. "
            "Default: ota/<thing-name>/source/<ota-update-id>/<input file name>"
        ),
    )
    parser.add_argument(
        "--signed-prefix",
        default=None,
        help=(
            "Optional S3 prefix template for AWS Signer output below "
            "ota/<thing-name>/. Use {thing_name} and {ota_update_id} "
            "placeholders. Default: "
            "ota/<thing-name>/signed/<ota-update-id>/"
        ),
    )
    parser.add_argument("--wait-timeout", type=int, default=180, help="Timeout for CREATE_COMPLETE polling")
    parser.add_argument("--poll-interval", type=int, default=3, help="Polling interval in seconds")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    meta_path = artifact_dir / "ota_job_meta.json"

    input_rsu = Path(args.input_rsu).resolve()
    if not input_rsu.exists():
        raise SystemExit(f"input .rsu not found: {input_rsu}")

    thing_result = run_aws(
        ["iot", "describe-thing", "--thing-name", args.thing_name],
        region=args.region,
    )
    thing_info = load_json(thing_result)
    thing_arn = thing_info["thingArn"]

    ota_update_id = (
        f"{args.ota_id_prefix}-{int(time.time())}-{uuid.uuid4().hex[:12]}"
    )
    s3_key = expand_ota_path_template(
        args.s3_key
        or "ota/{thing_name}/source/{ota_update_id}/" + input_rsu.name,
        args.thing_name,
        ota_update_id,
    )
    validate_source_key(args.thing_name, ota_update_id, s3_key)
    signed_prefix = expand_ota_path_template(
        args.signed_prefix
        or "ota/{thing_name}/signed/{ota_update_id}/",
        args.thing_name,
        ota_update_id,
    )
    validate_signed_prefix(args.thing_name, ota_update_id, signed_prefix)
    meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": args.region,
        "thing_name": args.thing_name,
        "thing_arn": thing_arn,
        "ota_update_id": ota_update_id,
        "ota_update_status": "UPLOAD_REQUESTED",
        "s3_bucket": args.bucket,
        "s3_key": s3_key,
        "s3_version": None,
        # AWS Signer writes one or more versioned output objects below this
        # prefix. Journal it before the upload so the always-running cleanup
        # job can remove signer output even after a partial create failure.
        "signed_prefix": signed_prefix,
        "code_signing_mode": "aws-signer",
        "signing_profile": args.signing_profile,
        "file_version": args.file_version,
        "input_rsu": str(input_rsu),
    }
    # Journal every resource identifier before the first AWS mutation.  The
    # always-running cleanup job can therefore remove an upload even when this
    # creator exits before create-ota-update is submitted.
    write_json(meta_path, meta)

    put_result = run_aws(
        [
            "s3api",
            "put-object",
            "--bucket",
            args.bucket,
            "--key",
            s3_key,
            "--body",
            str(input_rsu),
        ],
        region=args.region,
    )
    put_payload = load_json(put_result)
    write_json(artifact_dir / "ota_s3_put_output.json", put_payload)

    file_location = {
        "s3Location": {
            "bucket": args.bucket,
            "key": s3_key,
        }
    }
    if "VersionId" in put_payload:
        file_location["s3Location"]["version"] = put_payload["VersionId"]

    write_meta(
        meta_path,
        meta,
        ota_update_status="S3_UPLOADED",
        s3_version=file_location["s3Location"].get("version"),
    )

    create_input = {
        "otaUpdateId": ota_update_id,
        "targets": [thing_arn],
        "protocols": ["MQTT"],
        "targetSelection": "SNAPSHOT",
        "files": [
            {
                "codeSigning": {
                    "startSigningJobParameter": {
                        "signingProfileName": args.signing_profile,
                        "destination": {
                            "s3Destination": {
                                "bucket": args.bucket,
                                "prefix": signed_prefix,
                            }
                        },
                    }
                },
                "fileVersion": args.file_version,
                "fileName": s3_key,
                "fileLocation": file_location,
                "fileType": 0,
            }
        ],
        "roleArn": args.role_arn,
    }
    write_json(artifact_dir / "create_ota_input.json", create_input)
    write_meta(meta_path, meta, ota_update_status="CREATE_REQUESTED")

    create_result = run_aws(
        [
            "iot",
            "create-ota-update",
            "--cli-input-json",
            f"file://{artifact_dir / 'create_ota_input.json'}",
        ],
        region=args.region,
    )
    create_payload = load_json(create_result)
    write_json(artifact_dir / "create_ota_output.json", create_payload)
    create_updates = ota_meta_updates(create_payload)
    if not create_updates.get("ota_update_status"):
        create_updates["ota_update_status"] = "CREATE_SUBMITTED"
    write_meta(meta_path, meta, **create_updates)

    final_payload = wait_for_ota_status(
        ota_update_id=ota_update_id,
        region=args.region,
        timeout_seconds=args.wait_timeout,
        poll_interval=args.poll_interval,
        meta_path=meta_path,
        meta=meta,
    )
    write_json(artifact_dir / "ota_update_status.json", final_payload)

    ota_info = final_payload["otaUpdateInfo"]
    signer_job_id = None
    if ota_info.get("otaUpdateFiles"):
        signer_job_id = ota_info["otaUpdateFiles"][0].get("codeSigning", {}).get("awsSignerJobId")
    if signer_job_id:
        signing_job_result = run_aws(
            ["signer", "describe-signing-job", "--job-id", signer_job_id],
            region=args.region,
        )
        write_json(artifact_dir / "signing_job.json", load_json(signing_job_result))

    write_meta(
        meta_path,
        meta,
        **ota_meta_updates(final_payload),
    )

    print("")
    print("OTA update creation complete")
    print(f"  ota_update_id: {ota_update_id}")
    print(f"  aws_iot_job_id: {meta['aws_iot_job_id']}")
    print(f"  status: {meta['ota_update_status']}")
    print(f"  s3_key: {s3_key}")
    print(f"  s3_version: {meta['s3_version'] or '(none)'}")

    if meta["ota_update_status"] != "CREATE_COMPLETE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

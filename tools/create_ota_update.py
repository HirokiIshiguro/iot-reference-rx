#!/usr/bin/env python3
"""
Create an AWS IoT OTA update for CK-RX65N and save the resulting metadata.

This helper is intended for Step 7-5 manual CI runs. It uploads a prepared
OTA candidate to S3, creates an OTA update that targets a single thing, waits
for the OTA update to reach a terminal create state, and writes JSON artifacts
for later inspection.
"""

import argparse
import json
import os
import subprocess
import sys
import time
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


def run_aws(args, region, cwd=None):
    return run_command(["aws", *args, "--region", region, "--output", "json"], cwd=cwd)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def load_json(result):
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def wait_for_ota_status(ota_update_id, region, timeout_seconds, poll_interval):
    deadline = time.time() + timeout_seconds
    last_payload = None
    while time.time() < deadline:
        result = run_aws(
            ["iot", "get-ota-update", "--ota-update-id", ota_update_id],
            region=region,
        )
        payload = load_json(result)
        last_payload = payload
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
        help="Optional S3 object key. Default: ota/<thing-name>/<input file name>",
    )
    parser.add_argument(
        "--signed-prefix",
        default=None,
        help="Optional S3 prefix for AWS Signer output. Default: ota/<thing-name>/signed/",
    )
    parser.add_argument("--wait-timeout", type=int, default=180, help="Timeout for CREATE_COMPLETE polling")
    parser.add_argument("--poll-interval", type=int, default=3, help="Polling interval in seconds")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    input_rsu = Path(args.input_rsu).resolve()
    if not input_rsu.exists():
        raise SystemExit(f"input .rsu not found: {input_rsu}")

    thing_result = run_aws(
        ["iot", "describe-thing", "--thing-name", args.thing_name],
        region=args.region,
    )
    thing_info = load_json(thing_result)
    thing_arn = thing_info["thingArn"]

    s3_key = args.s3_key or f"ota/{args.thing_name}/{input_rsu.name}"
    signed_prefix = args.signed_prefix or f"ota/{args.thing_name}/signed/"

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

    ota_update_id = f"{args.ota_id_prefix}-{int(time.time())}"
    file_location = {
        "s3Location": {
            "bucket": args.bucket,
            "key": s3_key,
        }
    }
    if "VersionId" in put_payload:
        file_location["s3Location"]["version"] = put_payload["VersionId"]

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

    final_payload = wait_for_ota_status(
        ota_update_id=ota_update_id,
        region=args.region,
        timeout_seconds=args.wait_timeout,
        poll_interval=args.poll_interval,
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

    meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": args.region,
        "thing_name": args.thing_name,
        "thing_arn": thing_arn,
        "ota_update_id": ota_update_id,
        "ota_update_arn": ota_info.get("otaUpdateArn"),
        "ota_update_status": ota_info.get("otaUpdateStatus"),
        "aws_iot_job_id": ota_info.get("awsIotJobId"),
        "aws_iot_job_arn": ota_info.get("awsIotJobArn"),
        "s3_bucket": args.bucket,
        "s3_key": s3_key,
        "s3_version": file_location["s3Location"].get("version"),
        "signing_profile": args.signing_profile,
        "signing_job_id": signer_job_id,
        "file_version": args.file_version,
        "input_rsu": str(input_rsu),
    }
    write_json(artifact_dir / "ota_job_meta.json", meta)

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

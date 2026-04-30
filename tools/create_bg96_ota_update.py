#!/usr/bin/env python3
"""Upload a BG96 OTA payload and create an AWS IoT OTA update."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TERMINAL_CREATE_STATES = {"CREATE_COMPLETE", "CREATE_FAILED", "DELETE_FAILED"}


def run(command: list[str]) -> dict:
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def aws(args: list[str], region: str) -> dict:
    return run(["aws", *args, "--region", region, "--output", "json"])


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_meta(path: Path, meta: dict, **updates: object) -> None:
    meta.update({key: value for key, value in updates.items() if value is not None})
    write_json(path, meta)


def wait_for_ota(ota_update_id: str, region: str, timeout: int, poll_interval: int) -> dict:
    deadline = time.time() + timeout
    last_payload: dict | None = None
    while time.time() < deadline:
        payload = aws(["iot", "get-ota-update", "--ota-update-id", ota_update_id], region)
        last_payload = payload
        status = payload["otaUpdateInfo"]["otaUpdateStatus"]
        print(f"OTA update status: {status}")
        if status in TERMINAL_CREATE_STATES:
            return payload
        time.sleep(poll_interval)
    raise RuntimeError(f"timeout waiting for OTA update {ota_update_id}; last={last_payload}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--thing-name", required=True)
    parser.add_argument("--target-arn", default=None)
    parser.add_argument("--input-payload", required=True, type=Path)
    parser.add_argument("--file-version", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--signing-profile", required=True)
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--ota-id-prefix", default="bg96-ota")
    parser.add_argument("--s3-key", default=None)
    parser.add_argument("--signed-prefix", default=None)
    parser.add_argument("--wait-timeout", type=int, default=180)
    parser.add_argument("--poll-interval", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_payload.is_file():
        raise SystemExit(f"OTA payload not found: {args.input_payload}")

    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    meta_path = artifact_dir / "ota_job_meta.json"
    payload = args.input_payload.resolve()

    if args.target_arn:
        thing_arn = args.target_arn
    else:
        thing_info = aws(["iot", "describe-thing", "--thing-name", args.thing_name], args.region)
        thing_arn = thing_info["thingArn"]

    s3_key = args.s3_key or f"ota/{args.thing_name}/{payload.name}"
    signed_prefix = args.signed_prefix or f"ota/{args.thing_name}/signed/"
    put_output = aws(
        [
            "s3api",
            "put-object",
            "--bucket",
            args.bucket,
            "--key",
            s3_key,
            "--body",
            str(payload),
        ],
        args.region,
    )
    write_json(artifact_dir / "ota_s3_put_output.json", put_output)

    ota_update_id = f"{args.ota_id_prefix}-{int(time.time())}"
    file_location: dict = {"s3Location": {"bucket": args.bucket, "key": s3_key}}
    if "VersionId" in put_output:
        file_location["s3Location"]["version"] = put_output["VersionId"]

    meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": args.region,
        "thing_name": args.thing_name,
        "thing_arn": thing_arn,
        "ota_update_id": ota_update_id,
        "ota_update_status": "CREATE_REQUESTED",
        "s3_bucket": args.bucket,
        "s3_key": s3_key,
        "s3_version": file_location["s3Location"].get("version"),
        "signing_profile": args.signing_profile,
        "file_version": args.file_version,
        "input_payload": str(payload),
    }
    write_json(meta_path, meta)

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

    create_output = aws(
        ["iot", "create-ota-update", "--cli-input-json", f"file://{artifact_dir / 'create_ota_input.json'}"],
        args.region,
    )
    write_json(artifact_dir / "create_ota_output.json", create_output)
    write_meta(meta_path, meta, ota_update_status="CREATE_SUBMITTED")

    final_output = wait_for_ota(ota_update_id, args.region, args.wait_timeout, args.poll_interval)
    write_json(artifact_dir / "ota_update_status.json", final_output)

    ota_info = final_output["otaUpdateInfo"]
    signer_job_id = None
    if ota_info.get("otaUpdateFiles"):
        signer_job_id = ota_info["otaUpdateFiles"][0].get("codeSigning", {}).get("awsSignerJobId")
    if signer_job_id:
        write_json(
            artifact_dir / "signing_job.json",
            aws(["signer", "describe-signing-job", "--job-id", signer_job_id], args.region),
        )

    write_meta(
        meta_path,
        meta,
        ota_update_arn=ota_info.get("otaUpdateArn"),
        ota_update_status=ota_info.get("otaUpdateStatus"),
        aws_iot_job_id=ota_info.get("awsIotJobId"),
        aws_iot_job_arn=ota_info.get("awsIotJobArn"),
        signing_job_id=signer_job_id,
    )

    print("OTA update creation complete")
    print(f"  ota_update_id: {ota_update_id}")
    print(f"  aws_iot_job_id: {meta['aws_iot_job_id']}")
    print(f"  status: {meta['ota_update_status']}")
    return 0 if meta["ota_update_status"] == "CREATE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

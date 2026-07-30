#!/usr/bin/env python3
"""Upload a BG96 OTA payload and create an AWS IoT OTA update."""

from __future__ import annotations

import argparse
import base64
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


def encode_custom_signature_for_cli(der_signature: bytes) -> str:
    """Return the double-base64 form needed for AWS CLI blob JSON input."""
    return base64.b64encode(base64.b64encode(der_signature)).decode("ascii")


def ota_meta_updates(payload: dict) -> dict[str, object]:
    info = payload.get("otaUpdateInfo", payload)
    return {
        "ota_update_arn": info.get("otaUpdateArn"),
        "ota_update_status": info.get("otaUpdateStatus"),
        "aws_iot_job_id": info.get("awsIotJobId"),
        "aws_iot_job_arn": info.get("awsIotJobArn"),
    }


def wait_for_ota(
    ota_update_id: str,
    region: str,
    timeout: int,
    poll_interval: int,
    *,
    meta_path: Path | None = None,
    meta: dict | None = None,
) -> dict:
    deadline = time.time() + timeout
    last_payload: dict | None = None
    while time.time() < deadline:
        payload = aws(["iot", "get-ota-update", "--ota-update-id", ota_update_id], region)
        last_payload = payload
        if meta_path is not None and meta is not None:
            write_meta(meta_path, meta, **ota_meta_updates(payload))
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
    parser.add_argument("--signing-profile", default=None)
    parser.add_argument("--custom-signature-der", type=Path, default=None)
    parser.add_argument("--code-signer-cert", type=Path, default=None)
    parser.add_argument("--certificate-name", default=None)
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
    if args.custom_signature_der is not None and not args.custom_signature_der.is_file():
        raise SystemExit(f"custom signature not found: {args.custom_signature_der}")
    if args.custom_signature_der is None and not args.signing_profile:
        raise SystemExit("--signing-profile is required when --custom-signature-der is not used")

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

    code_signing_mode = "custom" if args.custom_signature_der is not None else "aws-signer"
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
        "code_signing_mode": code_signing_mode,
        "custom_signature_der": str(args.custom_signature_der.resolve()) if args.custom_signature_der else None,
        "code_signer_cert": str(args.code_signer_cert.resolve()) if args.code_signer_cert else None,
        "file_version": args.file_version,
        "input_payload": str(payload),
    }
    write_json(meta_path, meta)

    if args.custom_signature_der is not None:
        certificate_name = args.certificate_name
        if certificate_name is None:
            certificate_name = args.code_signer_cert.name if args.code_signer_cert is not None else "bg96_ota_codesign_cert.pem"
        code_signing = {
            "customCodeSigning": {
                "signature": {
                    "inlineDocument": encode_custom_signature_for_cli(args.custom_signature_der.read_bytes()),
                },
                "certificateChain": {
                    "certificateName": certificate_name,
                },
                "hashAlgorithm": "SHA256",
                "signatureAlgorithm": "ECDSA",
            }
        }
    else:
        code_signing = {
            "startSigningJobParameter": {
                "signingProfileName": args.signing_profile,
                "destination": {
                    "s3Destination": {
                        "bucket": args.bucket,
                        "prefix": signed_prefix,
                    }
                },
            }
        }

    create_input = {
        "otaUpdateId": ota_update_id,
        "targets": [thing_arn],
        "protocols": ["MQTT"],
        "targetSelection": "SNAPSHOT",
        "files": [
            {
                "codeSigning": code_signing,
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
    create_updates = ota_meta_updates(create_output)
    if not create_updates.get("ota_update_status"):
        create_updates["ota_update_status"] = "CREATE_SUBMITTED"
    write_meta(meta_path, meta, **create_updates)

    final_output = wait_for_ota(
        ota_update_id,
        args.region,
        args.wait_timeout,
        args.poll_interval,
        meta_path=meta_path,
        meta=meta,
    )
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
        **ota_meta_updates(final_output),
        signing_job_id=signer_job_id,
    )

    print("OTA update creation complete")
    print(f"  ota_update_id: {ota_update_id}")
    print(f"  aws_iot_job_id: {meta['aws_iot_job_id']}")
    print(f"  status: {meta['ota_update_status']}")
    return 0 if meta["ota_update_status"] == "CREATE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

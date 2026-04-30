#!/usr/bin/env python3
"""Create temporary AWS IoT credentials for the CK-RX65N BG96 CI path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_aws(args: list[str], region: str, allow_failure: bool = False) -> dict:
    command = ["aws", *args, "--region", region, "--output", "json"]
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        if allow_failure:
            return {}
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def create_policy_if_missing(policy_name: str, policy_document: Path | None, region: str) -> None:
    result = run_aws(["iot", "get-policy", "--policy-name", policy_name], region, allow_failure=True)
    if result:
        return
    if policy_document is None:
        raise RuntimeError(f"IoT policy does not exist and no policy document was provided: {policy_name}")
    run_aws(
        [
            "iot",
            "create-policy",
            "--policy-name",
            policy_name,
            "--policy-document",
            f"file://{policy_document.resolve()}",
        ],
        region,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--thing-name", required=True)
    parser.add_argument("--policy-name", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--endpoint", default="")
    parser.add_argument("--policy-document", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    create_policy_if_missing(args.policy_name, args.policy_document, args.region)
    run_aws(["iot", "create-thing", "--thing-name", args.thing_name], args.region, allow_failure=True)

    cert = run_aws(["iot", "create-keys-and-certificate", "--set-as-active"], args.region)
    cert_arn = cert["certificateArn"]
    cert_id = cert["certificateId"]

    run_aws(["iot", "attach-policy", "--policy-name", args.policy_name, "--target", cert_arn], args.region)
    run_aws(["iot", "attach-thing-principal", "--thing-name", args.thing_name, "--principal", cert_arn], args.region)

    endpoint = args.endpoint.strip()
    if not endpoint:
        endpoint_payload = run_aws(["iot", "describe-endpoint", "--endpoint-type", "iot:Data-ATS"], args.region)
        endpoint = endpoint_payload["endpointAddress"]

    write_text(artifact_dir / "thing_name.txt", args.thing_name)
    write_text(artifact_dir / "endpoint.txt", endpoint)
    write_text(artifact_dir / "certificate.pem", cert["certificatePem"])
    write_text(artifact_dir / "private_key.pem", cert["keyPair"]["PrivateKey"])
    write_text(artifact_dir / "public_key.pem", cert["keyPair"]["PublicKey"])
    write_json(
        artifact_dir / "iot_credentials_meta.json",
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "thing_name": args.thing_name,
            "policy_name": args.policy_name,
            "region": args.region,
            "endpoint": endpoint,
            "certificate_id": cert_id,
            "certificate_arn": cert_arn,
        },
    )

    print("Temporary BG96 AWS IoT credentials created.")
    print(f"  thing_name: {args.thing_name}")
    print(f"  policy_name: {args.policy_name}")
    print(f"  certificate_id: {cert_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

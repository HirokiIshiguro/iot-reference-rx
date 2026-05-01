#!/usr/bin/env python3
"""Delete temporary AWS IoT credentials created for the CK-RX65N BG96 CI path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_aws(args: list[str], region: str, allow_failure: bool = True) -> dict:
    command = ["aws", *args, "--region", region, "--output", "json"]
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        if allow_failure:
            return {}
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta-json", required=True, type=Path)
    parser.add_argument("--region", default="")
    parser.add_argument("--output-json", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.meta_json.is_file():
        print(f"Temporary credential metadata not found; cleanup skipped: {args.meta_json}")
        write_json(args.output_json, {"skipped": True, "reason": "metadata_not_found"})
        return 0

    meta = json.loads(args.meta_json.read_text(encoding="utf-8"))
    region = args.region or meta["region"]
    thing_name = meta.get("thing_name")
    cert_arn = meta.get("certificate_arn")
    cert_id = meta.get("certificate_id")
    policy_name = meta.get("policy_name")
    cleanup = {"thing_name": thing_name, "certificate_id": cert_id, "actions": []}

    principals: list[str] = []
    if thing_name:
        principals.extend(
            run_aws(["iot", "list-thing-principals", "--thing-name", thing_name], region).get("principals", [])
        )
    if cert_arn and cert_arn not in principals:
        principals.append(cert_arn)

    for principal in principals:
        if thing_name:
            run_aws(["iot", "detach-thing-principal", "--thing-name", thing_name, "--principal", principal], region)
            cleanup["actions"].append({"action": "detach_thing_principal", "principal": principal})

        policies = run_aws(["iot", "list-principal-policies", "--principal", principal], region).get("policies", [])
        policy_names = {policy.get("policyName") for policy in policies if policy.get("policyName")}
        if policy_name:
            policy_names.add(policy_name)
        for name in sorted(policy_names):
            run_aws(["iot", "detach-policy", "--policy-name", name, "--target", principal], region)
            cleanup["actions"].append({"action": "detach_policy", "policy": name, "principal": principal})

    if cert_id:
        run_aws(["iot", "update-certificate", "--certificate-id", cert_id, "--new-status", "INACTIVE"], region)
        cleanup["actions"].append({"action": "update_certificate", "certificate_id": cert_id, "status": "INACTIVE"})
        run_aws(["iot", "delete-certificate", "--certificate-id", cert_id], region)
        cleanup["actions"].append({"action": "delete_certificate", "certificate_id": cert_id})

    if thing_name:
        run_aws(["iot", "delete-thing", "--thing-name", thing_name], region)
        cleanup["actions"].append({"action": "delete_thing", "thing_name": thing_name})

    write_json(args.output_json, cleanup)
    print("Temporary BG96 AWS IoT credentials cleanup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

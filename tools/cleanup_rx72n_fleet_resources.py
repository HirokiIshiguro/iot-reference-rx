#!/usr/bin/env python3
"""
Delete AWS IoT resources created by the RX72N Fleet Provisioning experiment.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_aws(args, region, allow_failure=False):
    command = ["aws", *args, "--region", region, "--output", "json"]
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(f"command failed: {' '.join(command)}")
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"stdout": result.stdout}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Cleanup RX72N Fleet Provisioning AWS IoT resources")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--policy-name", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    with open(args.summary_json, "r", encoding="utf-8") as handle:
        summary = json.load(handle)

    thing_name = summary.get("thing_name")
    certificate_id = summary.get("certificate_id")
    cleanup = {
        "thing_name": thing_name,
        "certificate_id": certificate_id,
        "actions": [],
    }

    if not thing_name and not certificate_id:
        print("No generated thing or certificate was recorded; nothing to cleanup.")
        write_json(Path(args.output_json), cleanup)
        return 0

    cert_arn = None
    if certificate_id:
        caller = run_aws(["sts", "get-caller-identity"], region=args.region)
        account_id = caller["Account"]
        cert_arn = f"arn:aws:iot:{args.region}:{account_id}:cert/{certificate_id}"
        cleanup["certificate_arn"] = cert_arn

    principals = []
    if thing_name:
        payload = run_aws(
            ["iot", "list-thing-principals", "--thing-name", thing_name],
            region=args.region,
            allow_failure=True,
        )
        principals = payload.get("principals", [])
        cleanup["thing_principals"] = principals

    if cert_arn and cert_arn not in principals:
        principals.append(cert_arn)

    for principal in principals:
        if thing_name:
            run_aws(
                ["iot", "detach-thing-principal", "--thing-name", thing_name, "--principal", principal],
                region=args.region,
                allow_failure=True,
            )
            cleanup["actions"].append({"action": "detach_thing_principal", "principal": principal})

        policies = run_aws(
            ["iot", "list-principal-policies", "--principal", principal],
            region=args.region,
            allow_failure=True,
        ).get("policies", [])

        seen_policy_names = {policy.get("policyName") for policy in policies if policy.get("policyName")}
        seen_policy_names.add(args.policy_name)
        for policy_name in sorted(seen_policy_names):
            run_aws(
                ["iot", "detach-policy", "--policy-name", policy_name, "--target", principal],
                region=args.region,
                allow_failure=True,
            )
            cleanup["actions"].append({"action": "detach_policy", "policy": policy_name, "principal": principal})

    if certificate_id:
        run_aws(
            ["iot", "update-certificate", "--certificate-id", certificate_id, "--new-status", "INACTIVE"],
            region=args.region,
            allow_failure=True,
        )
        cleanup["actions"].append({"action": "update_certificate", "status": "INACTIVE"})

        run_aws(
            ["iot", "delete-certificate", "--certificate-id", certificate_id],
            region=args.region,
            allow_failure=True,
        )
        cleanup["actions"].append({"action": "delete_certificate"})

    if thing_name:
        run_aws(
            ["iot", "delete-thing", "--thing-name", thing_name],
            region=args.region,
            allow_failure=True,
        )
        cleanup["actions"].append({"action": "delete_thing"})

    write_json(Path(args.output_json), cleanup)
    print("Fleet provisioning cleanup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

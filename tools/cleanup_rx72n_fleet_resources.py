#!/usr/bin/env python3
"""
Delete AWS IoT resources created by the hardware Fleet Provisioning experiments.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


AWS_ERROR_CODE_PATTERN = re.compile(r"An error occurred \(([^)]+)\)")


def _aws_error_code(stderr):
    match = AWS_ERROR_CODE_PATTERN.search(stderr or "")
    return match.group(1) if match else None


def run_aws(args, region, allow_failure=False, command_status=None, print_output=True):
    command = ["aws", *args, "--region", region, "--output", "json"]
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    error_code = _aws_error_code(result.stderr)
    if command_status is not None:
        command_status.update(
            {
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "aws_error_code": error_code,
            }
        )
    if print_output and result.stdout.strip():
        print(result.stdout.rstrip())
    if print_output and result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(f"command failed: {' '.join(command)}")
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"stdout": result.stdout}


def verify_absence(resource_type, resource_id, region):
    if resource_type == "thing":
        command = ["iot", "describe-thing", "--thing-name", resource_id]
    elif resource_type == "certificate":
        command = ["iot", "describe-certificate", "--certificate-id", resource_id]
    else:
        raise ValueError(f"unsupported resource type: {resource_type}")

    command_status = {}
    run_aws(
        command,
        region=region,
        allow_failure=True,
        command_status=command_status,
        print_output=False,
    )
    if command_status["success"]:
        state = "present"
    elif command_status["aws_error_code"] == "ResourceNotFoundException":
        state = "absent"
    else:
        state = "unknown"

    result = {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "state": state,
        "returncode": command_status["returncode"],
    }
    if command_status["aws_error_code"]:
        result["aws_error_code"] = command_status["aws_error_code"]
    print(f"Verification: {resource_type} {resource_id} is {state}.")
    return result


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Cleanup Fleet Provisioning AWS IoT resources")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--policy-name", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument(
        "--verify-absence",
        action="store_true",
        help="Verify that deleted things and certificates no longer exist",
    )
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
    if args.verify_absence:
        cleanup["verification"] = {
            "enabled": True,
            "delete_failures": [],
            "resources": [],
            "success": False,
        }

    if not thing_name and not certificate_id:
        print("No generated thing or certificate was recorded; nothing to cleanup.")
        if args.verify_absence:
            results = summary.get("results") or {}
            resource_creation_may_have_started = any(
                bool(results.get(name))
                for name in ("claim_mqtt", "certificate", "thing_name")
            )
            cleanup["verification"]["resource_creation_may_have_started"] = resource_creation_may_have_started
            cleanup["verification"]["success"] = not resource_creation_may_have_started
        write_json(Path(args.output_json), cleanup)
        if args.verify_absence and not cleanup["verification"]["success"]:
            print(
                "Fleet provisioning reached the claim session, but no generated resource identifier was recorded; absence cannot be proven.",
                file=sys.stderr,
            )
            return 1
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

    certificate_ids_to_delete = set()
    if certificate_id:
        certificate_ids_to_delete.add(certificate_id)

    for principal in principals:
        if ":cert/" in principal:
            certificate_ids_to_delete.add(principal.rsplit(":cert/", 1)[1])

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

    cleanup["certificate_ids_to_delete"] = sorted(certificate_ids_to_delete)
    for certificate_id_to_delete in sorted(certificate_ids_to_delete):
        run_aws(
            ["iot", "update-certificate", "--certificate-id", certificate_id_to_delete, "--new-status", "INACTIVE"],
            region=args.region,
            allow_failure=True,
        )
        cleanup["actions"].append({"action": "update_certificate", "certificate_id": certificate_id_to_delete, "status": "INACTIVE"})

        delete_status = {} if args.verify_absence else None
        run_aws(
            ["iot", "delete-certificate", "--certificate-id", certificate_id_to_delete],
            region=args.region,
            allow_failure=True,
            command_status=delete_status,
        )
        delete_action = {"action": "delete_certificate", "certificate_id": certificate_id_to_delete}
        if args.verify_absence:
            delete_succeeded = delete_status["success"] or (
                delete_status["aws_error_code"] == "ResourceNotFoundException"
            )
            delete_action["success"] = delete_succeeded
            delete_action["already_absent"] = (
                delete_status["aws_error_code"] == "ResourceNotFoundException"
            )
            if delete_status["aws_error_code"]:
                delete_action["aws_error_code"] = delete_status["aws_error_code"]
            if not delete_succeeded:
                cleanup["verification"]["delete_failures"].append(delete_action.copy())
        cleanup["actions"].append(delete_action)

    if thing_name:
        delete_status = {} if args.verify_absence else None
        run_aws(
            ["iot", "delete-thing", "--thing-name", thing_name],
            region=args.region,
            allow_failure=True,
            command_status=delete_status,
        )
        delete_action = {"action": "delete_thing"}
        if args.verify_absence:
            delete_succeeded = delete_status["success"] or (
                delete_status["aws_error_code"] == "ResourceNotFoundException"
            )
            delete_action["success"] = delete_succeeded
            delete_action["already_absent"] = (
                delete_status["aws_error_code"] == "ResourceNotFoundException"
            )
            if delete_status["aws_error_code"]:
                delete_action["aws_error_code"] = delete_status["aws_error_code"]
            if not delete_succeeded:
                cleanup["verification"]["delete_failures"].append(delete_action.copy())
        cleanup["actions"].append(delete_action)

    if args.verify_absence:
        verification = cleanup["verification"]
        for certificate_id_to_delete in sorted(certificate_ids_to_delete):
            verification["resources"].append(
                verify_absence("certificate", certificate_id_to_delete, args.region)
            )
        if thing_name:
            verification["resources"].append(verify_absence("thing", thing_name, args.region))
        verification["success"] = not verification["delete_failures"] and all(
            resource["state"] == "absent" for resource in verification["resources"]
        )

    write_json(Path(args.output_json), cleanup)
    if args.verify_absence and not cleanup["verification"]["success"]:
        print("Fleet provisioning cleanup verification failed.", file=sys.stderr)
        return 1
    print("Fleet provisioning cleanup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

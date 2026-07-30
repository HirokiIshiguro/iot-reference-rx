#!/usr/bin/env python3
"""Delete and verify temporary AWS IoT credentials created for BG96 CI."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


AWS_ERROR_CODE_PATTERN = re.compile(r"An error occurred \(([^)]+)\)")
NOT_FOUND_ERROR = "ResourceNotFoundException"


def aws_error_code(stderr: str) -> str | None:
    match = AWS_ERROR_CODE_PATTERN.search(stderr or "")
    return match.group(1) if match else None


def run_aws(args: list[str], region: str) -> dict:
    command = ["aws", *args, "--region", region, "--output", "json"]
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)

    payload = {}
    parse_error = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            parse_error = str(error)
    return {
        "args": args,
        "returncode": result.returncode,
        "aws_error_code": aws_error_code(result.stderr),
        "payload": payload,
        "parse_error": parse_error,
    }


def succeeded_or_absent(result: dict) -> bool:
    return (
        (result["returncode"] == 0 and result["parse_error"] is None)
        or result["aws_error_code"] == NOT_FOUND_ERROR
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta-json", required=True, type=Path)
    parser.add_argument("--region", default="")
    parser.add_argument("--expected-thing-name", default="")
    parser.add_argument("--expected-policy-name", default="")
    parser.add_argument("--output-json", required=True, type=Path)
    return parser.parse_args()


def record_failure(cleanup: dict, operation: str, result: dict) -> None:
    cleanup["errors"].append(
        {
            "operation": operation,
            "returncode": result["returncode"],
            "aws_error_code": result["aws_error_code"],
            "parse_error": result["parse_error"],
        }
    )


def run_discovery(cleanup: dict, operation: str, args: list[str], region: str) -> dict:
    result = run_aws(args, region)
    cleanup["discovery"].append(
        {
            "operation": operation,
            "success": succeeded_or_absent(result),
            "already_absent": result["aws_error_code"] == NOT_FOUND_ERROR,
            "returncode": result["returncode"],
            "aws_error_code": result["aws_error_code"],
            "parse_error": result["parse_error"],
        }
    )
    if not succeeded_or_absent(result):
        record_failure(cleanup, operation, result)
    return result["payload"]


def run_action(
    cleanup: dict,
    operation: str,
    args: list[str],
    region: str,
    **details,
) -> None:
    result = run_aws(args, region)
    action = {
        "action": operation,
        **details,
        "success": succeeded_or_absent(result),
        "already_absent": result["aws_error_code"] == NOT_FOUND_ERROR,
        "returncode": result["returncode"],
        "aws_error_code": result["aws_error_code"],
        "parse_error": result["parse_error"],
    }
    cleanup["actions"].append(action)
    if not action["success"]:
        record_failure(cleanup, operation, result)


def verify_absence(cleanup: dict, resource: str, resource_id: str, args: list[str], region: str) -> None:
    result = run_aws(args, region)
    if result["aws_error_code"] == NOT_FOUND_ERROR:
        state = "absent"
    elif result["returncode"] == 0:
        state = "present"
    else:
        state = "unknown"
    cleanup["verification"]["resources"].append(
        {
            "resource": resource,
            "id": resource_id,
            "state": state,
            "returncode": result["returncode"],
            "aws_error_code": result["aws_error_code"],
            "parse_error": result["parse_error"],
        }
    )
    if state != "absent":
        record_failure(cleanup, f"verify_{resource}_absence", result)


def main() -> int:
    args = parse_args()
    cleanup = {
        "schema_version": 1,
        "thing_name": None,
        "certificate_id": None,
        "discovery": [],
        "actions": [],
        "errors": [],
        "verification": {"resources": [], "passed": False},
    }
    if not args.meta_json.is_file():
        cleanup["errors"].append(
            {"operation": "load_metadata", "reason": "metadata_not_found"}
        )
        write_json(args.output_json, cleanup)
        print(f"Temporary credential metadata not found: {args.meta_json}", file=sys.stderr)
        return 1

    try:
        meta = json.loads(args.meta_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        cleanup["errors"].append(
            {"operation": "load_metadata", "reason": type(error).__name__}
        )
        write_json(args.output_json, cleanup)
        print(f"Temporary credential metadata is invalid: {error}", file=sys.stderr)
        return 1

    region = args.region or meta.get("region", "")
    thing_name = meta.get("thing_name")
    cert_arn = meta.get("certificate_arn")
    cert_id = meta.get("certificate_id")
    policy_name = meta.get("policy_name")
    cleanup.update(
        {
            "region": region,
            "thing_name": thing_name,
            "certificate_id": cert_id,
        }
    )
    required_values = {
        "region": region,
        "thing_name": thing_name,
        "certificate_id": cert_id,
        "certificate_arn": cert_arn,
        "policy_name": policy_name,
    }
    missing_values = sorted(name for name, value in required_values.items() if not value)
    validation_errors = []
    if missing_values:
        validation_errors.append(
            {
                "reason": "required_metadata_missing",
                "fields": missing_values,
            }
        )
    if args.expected_thing_name and thing_name != args.expected_thing_name:
        validation_errors.append(
            {
                "reason": "thing_name_mismatch",
                "expected": args.expected_thing_name,
                "actual": thing_name,
            }
        )
    if args.expected_policy_name and policy_name != args.expected_policy_name:
        validation_errors.append(
            {
                "reason": "policy_name_mismatch",
                "expected": args.expected_policy_name,
                "actual": policy_name,
            }
        )
    expected_cert_arn = (
        rf"^arn:[^:]+:iot:{re.escape(region)}:\d{{12}}:cert/{re.escape(cert_id)}$"
        if region and cert_id
        else None
    )
    if expected_cert_arn and cert_arn and not re.fullmatch(expected_cert_arn, cert_arn):
        validation_errors.append(
            {
                "reason": "certificate_arn_mismatch",
                "certificate_id": cert_id,
                "certificate_arn": cert_arn,
            }
        )
    if validation_errors:
        cleanup["errors"].append(
            {
                "operation": "validate_metadata",
                "validation_errors": validation_errors,
            }
        )
        write_json(args.output_json, cleanup)
        print("Temporary credential metadata failed identity validation.", file=sys.stderr)
        return 1

    # Complete every read-only discovery before mutation. The dynamic Thing and
    # certificate are pipeline-owned resources and must have exactly the
    # metadata-recorded relationship. An API error or an unexpected additional
    # principal/policy makes the ownership boundary ambiguous, so actions stay
    # empty and the cleanup fails closed.
    principals_payload = run_discovery(
        cleanup,
        "list_thing_principals",
        ["iot", "list-thing-principals", "--thing-name", thing_name],
        region,
    )
    principals = {
        principal
        for principal in principals_payload.get("principals", [])
        if principal
    }
    policies_payload = run_discovery(
        cleanup,
        "list_principal_policies",
        ["iot", "list-principal-policies", "--principal", cert_arn],
        region,
    )
    policy_names = {
        policy.get("policyName")
        for policy in policies_payload.get("policies", [])
        if policy.get("policyName")
    }
    unexpected_principals = sorted(principals - {cert_arn})
    unexpected_policies = sorted(policy_names - {policy_name})
    if unexpected_principals or unexpected_policies:
        cleanup["errors"].append(
            {
                "operation": "validate_discovered_ownership",
                "unexpected_principals": unexpected_principals,
                "unexpected_policies": unexpected_policies,
            }
        )
    if cleanup["errors"]:
        write_json(args.output_json, cleanup)
        print(
            "Temporary BG96 credential ownership discovery failed; no AWS mutation was performed.",
            file=sys.stderr,
        )
        return 1

    run_action(
        cleanup,
        "detach_thing_principal",
        [
            "iot",
            "detach-thing-principal",
            "--thing-name",
            thing_name,
            "--principal",
            cert_arn,
        ],
        region,
        principal=cert_arn,
    )
    run_action(
        cleanup,
        "detach_policy",
        ["iot", "detach-policy", "--policy-name", policy_name, "--target", cert_arn],
        region,
        policy=policy_name,
        principal=cert_arn,
    )

    if cert_id:
        run_action(
            cleanup,
            "update_certificate",
            ["iot", "update-certificate", "--certificate-id", cert_id, "--new-status", "INACTIVE"],
            region,
            certificate_id=cert_id,
            status="INACTIVE",
        )
        run_action(
            cleanup,
            "delete_certificate",
            ["iot", "delete-certificate", "--certificate-id", cert_id],
            region,
            certificate_id=cert_id,
        )

    if thing_name:
        run_action(
            cleanup,
            "delete_thing",
            ["iot", "delete-thing", "--thing-name", thing_name],
            region,
            thing_name=thing_name,
        )

    if cert_id:
        verify_absence(
            cleanup,
            "certificate",
            cert_id,
            ["iot", "describe-certificate", "--certificate-id", cert_id],
            region,
        )
    if thing_name:
        verify_absence(
            cleanup,
            "thing",
            thing_name,
            ["iot", "describe-thing", "--thing-name", thing_name],
            region,
        )

    cleanup["verification"]["passed"] = not cleanup["errors"] and all(
        item["state"] == "absent" for item in cleanup["verification"]["resources"]
    )
    write_json(args.output_json, cleanup)
    if not cleanup["verification"]["passed"]:
        print(
            f"Temporary BG96 AWS IoT credentials cleanup could not be verified: {args.output_json}",
            file=sys.stderr,
        )
        return 1
    print("Temporary BG96 AWS IoT credentials cleanup and absence verification complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

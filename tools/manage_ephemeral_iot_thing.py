#!/usr/bin/env python3
"""Create and clean up a pipeline-owned AWS IoT Thing alias.

The OTA hardware jobs use a short-lived Thing name so another pipeline using
the board's normal Thing name cannot consume the one-shot OTA Job.  The
certificate remains attached to the normal Thing throughout the transaction.
Only the additional, explicitly journaled attachment is removed by cleanup.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THING_NAME_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")


class AwsCommandError(RuntimeError):
    """An AWS CLI command failed."""

    def __init__(self, command: list[str], result: subprocess.CompletedProcess[str]):
        super().__init__(
            f"AWS command failed (exit={result.returncode}): {' '.join(command)}"
        )
        self.command = command
        self.result = result


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


def run_aws(
    arguments: list[str],
    *,
    region: str,
    check: bool = True,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    command = [
        *aws_command_prefix(),
        *arguments,
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
    if check and result.returncode != 0:
        raise AwsCommandError(command, result)

    payload: dict[str, Any] = {}
    if result.returncode == 0 and result.stdout.strip():
        parsed = json.loads(result.stdout)
        if not isinstance(parsed, dict):
            raise RuntimeError("AWS CLI output must be a JSON object")
        payload = parsed
    return result, payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return payload


def validate_names(base_thing_name: str, thing_name: str) -> None:
    for label, value in (
        ("base Thing name", base_thing_name),
        ("ephemeral Thing name", thing_name),
    ):
        if not THING_NAME_PATTERN.fullmatch(value):
            raise RuntimeError(f"{label} is invalid: {value!r}")
    if thing_name == base_thing_name:
        raise RuntimeError("ephemeral Thing name must differ from the base Thing")
    expected_prefix = f"{base_thing_name}-ota-"
    if not thing_name.startswith(expected_prefix):
        raise RuntimeError(
            f"ephemeral Thing name must start with {expected_prefix!r}"
        )


def validate_ownership(
    base_thing_name: str,
    thing_name: str,
    owner_pipeline_id: str,
    owner_job_id: str,
) -> None:
    validate_names(base_thing_name, thing_name)
    for label, value in (
        ("owner pipeline ID", owner_pipeline_id),
        ("owner job ID", owner_job_id),
    ):
        if not value.isdecimal():
            raise RuntimeError(f"{label} must contain decimal digits only")
    expected_name = (
        f"{base_thing_name}-ota-{owner_pipeline_id}-{owner_job_id}"
    )
    if thing_name != expected_name:
        raise RuntimeError(
            "ephemeral Thing name does not match its pipeline/job ownership: "
            f"expected {expected_name!r}"
        )


def is_not_found(result: subprocess.CompletedProcess[str]) -> bool:
    combined = f"{result.stdout}\n{result.stderr}"
    return "ResourceNotFoundException" in combined


def list_principals(thing_name: str, region: str) -> list[str]:
    _, payload = run_aws(
        ["iot", "list-thing-principals", "--thing-name", thing_name],
        region=region,
    )
    principals = payload.get("principals", [])
    if not isinstance(principals, list) or not all(
        isinstance(item, str) for item in principals
    ):
        raise RuntimeError("AWS IoT principal list is malformed")
    return principals


def describe_thing(
    thing_name: str, region: str
) -> tuple[bool, dict[str, Any]]:
    result, payload = run_aws(
        ["iot", "describe-thing", "--thing-name", thing_name],
        region=region,
        check=False,
    )
    if result.returncode == 0:
        return True, payload
    if is_not_found(result):
        return False, {}
    raise AwsCommandError(
        [
            *aws_command_prefix(),
            "iot",
            "describe-thing",
            "--thing-name",
            thing_name,
        ],
        result,
    )


def create_alias(args: argparse.Namespace) -> int:
    validate_ownership(
        args.base_thing_name,
        args.thing_name,
        args.owner_pipeline_id,
        args.owner_job_id,
    )
    meta_path = args.meta_json.resolve()

    base_exists, base_info = describe_thing(args.base_thing_name, args.region)
    if not base_exists:
        raise RuntimeError(f"base Thing does not exist: {args.base_thing_name}")
    principals = list_principals(args.base_thing_name, args.region)
    if len(principals) != 1:
        raise RuntimeError(
            f"base Thing must have exactly one principal; found {len(principals)}"
        )
    principal = principals[0]
    if ":cert/" not in principal:
        raise RuntimeError("base Thing principal is not an AWS IoT certificate ARN")

    meta: dict[str, Any] = {
        "schema_version": 1,
        "status": "planned",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": args.region,
        "base_thing_name": args.base_thing_name,
        "base_thing_arn": base_info.get("thingArn"),
        "thing_name": args.thing_name,
        "principal": principal,
        "owner_pipeline_id": args.owner_pipeline_id,
        "owner_job_id": args.owner_job_id,
        "operations": [],
    }
    write_json(meta_path, meta)

    try:
        alias_exists, _ = describe_thing(args.thing_name, args.region)
        if alias_exists:
            meta["status"] = "collision"
            write_json(meta_path, meta)
            raise RuntimeError(
                f"refusing to adopt an existing Thing: {args.thing_name}"
            )

        _, create_payload = run_aws(
            ["iot", "create-thing", "--thing-name", args.thing_name],
            region=args.region,
        )
        meta["status"] = "created"
        meta["thing_arn"] = create_payload.get("thingArn")
        meta["operations"].append("create-thing")
        write_json(meta_path, meta)

        run_aws(
            [
                "iot",
                "attach-thing-principal",
                "--thing-name",
                args.thing_name,
                "--principal",
                principal,
            ],
            region=args.region,
        )
        meta["status"] = "attached"
        meta["operations"].append("attach-thing-principal")
        write_json(meta_path, meta)

        alias_principals = list_principals(args.thing_name, args.region)
        if alias_principals != [principal]:
            raise RuntimeError(
                "ephemeral Thing principal verification failed: "
                f"{alias_principals!r}"
            )
        base_principals = list_principals(args.base_thing_name, args.region)
        if principal not in base_principals:
            raise RuntimeError("base Thing lost its certificate principal")

        meta["status"] = "ready"
        meta["verified"] = True
        write_json(meta_path, meta)
        print(args.thing_name)
        return 0
    except Exception as error:
        if meta.get("status") != "collision":
            meta["status"] = "error"
        meta["error"] = str(error)
        write_json(meta_path, meta)
        raise


def cleanup_alias(args: argparse.Namespace) -> int:
    meta = load_json(args.meta_json.resolve())
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "validating",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "actions": [],
        "errors": [],
        "verification": {},
    }
    output_path = args.output_json.resolve()
    write_json(output_path, result)

    try:
        required = (
            "region",
            "base_thing_name",
            "thing_name",
            "principal",
            "owner_pipeline_id",
            "owner_job_id",
        )
        missing = [name for name in required if not meta.get(name)]
        if missing:
            raise RuntimeError(
                "ephemeral Thing metadata is incomplete: " + ", ".join(missing)
            )

        region = str(meta["region"])
        base_thing_name = str(meta["base_thing_name"])
        thing_name = str(meta["thing_name"])
        principal = str(meta["principal"])
        owner_pipeline_id = str(meta["owner_pipeline_id"])
        owner_job_id = str(meta["owner_job_id"])
        validate_ownership(
            base_thing_name,
            thing_name,
            owner_pipeline_id,
            owner_job_id,
        )
        if principal.count(":cert/") != 1:
            raise RuntimeError("metadata principal is not a certificate ARN")

        base_exists, _ = describe_thing(base_thing_name, region)
        if not base_exists:
            raise RuntimeError("base Thing disappeared; refusing alias cleanup")
        base_principals = list_principals(base_thing_name, region)
        if principal not in base_principals:
            raise RuntimeError(
                "expected certificate is no longer attached to the base Thing"
            )

        alias_exists, _ = describe_thing(thing_name, region)
        if not alias_exists:
            result["status"] = "complete"
            result["verification"] = {
                "base_thing_exists": True,
                "base_principal_attached": True,
                "ephemeral_thing_absent": True,
            }
            write_json(output_path, result)
            return 0

        operations = meta.get("operations")
        if not isinstance(operations, list) or "create-thing" not in operations:
            raise RuntimeError(
                "metadata does not prove this pipeline created the "
                "ephemeral Thing; refusing mutation"
            )

        alias_principals = list_principals(thing_name, region)
        unexpected = [item for item in alias_principals if item != principal]
        if unexpected:
            raise RuntimeError(
                "ephemeral Thing has unexpected principals; refusing mutation: "
                + ", ".join(unexpected)
            )

        if principal in alias_principals:
            run_aws(
                [
                    "iot",
                    "detach-thing-principal",
                    "--thing-name",
                    thing_name,
                    "--principal",
                    principal,
                ],
                region=region,
            )
            result["actions"].append("detach-thing-principal")
            write_json(output_path, result)

        remaining = list_principals(thing_name, region)
        if remaining:
            raise RuntimeError(
                "ephemeral Thing still has principals after detach: "
                + ", ".join(remaining)
            )

        run_aws(
            ["iot", "delete-thing", "--thing-name", thing_name],
            region=region,
        )
        result["actions"].append("delete-thing")

        alias_exists, _ = describe_thing(thing_name, region)
        base_exists, _ = describe_thing(base_thing_name, region)
        base_principals = (
            list_principals(base_thing_name, region) if base_exists else []
        )
        verification = {
            "base_thing_exists": base_exists,
            "base_principal_attached": principal in base_principals,
            "ephemeral_thing_absent": not alias_exists,
        }
        result["verification"] = verification
        if not all(verification.values()):
            raise RuntimeError(
                "ephemeral Thing cleanup verification failed: "
                + json.dumps(verification, sort_keys=True)
            )

        result["status"] = "complete"
        result["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output_path, result)
        return 0
    except Exception as error:
        result["status"] = "failed"
        result["errors"].append(str(error))
        write_json(output_path, result)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--base-thing-name", required=True)
    create_parser.add_argument("--thing-name", required=True)
    create_parser.add_argument("--region", required=True)
    create_parser.add_argument("--owner-pipeline-id", required=True)
    create_parser.add_argument("--owner-job-id", required=True)
    create_parser.add_argument("--meta-json", required=True, type=Path)
    create_parser.set_defaults(func=create_alias)

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--meta-json", required=True, type=Path)
    cleanup_parser.add_argument("--output-json", required=True, type=Path)
    cleanup_parser.set_defaults(func=cleanup_alias)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

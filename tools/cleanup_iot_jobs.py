#!/usr/bin/env python3
"""Check for active AWS IoT Jobs, or explicitly use the legacy cancellation mode."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CHECK_STATUSES = ("QUEUED", "IN_PROGRESS")
CHECK_TIMEOUT_SECONDS = 30
CHECK_HEARTBEAT_SECONDS = 3


def run_command(cmd, *, allow_failure=False):
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0 and not allow_failure:
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


def run_aws(args, region, *, allow_failure=False):
    return run_command([*aws_command_prefix(), *args, "--region", region, "--output", "json"], allow_failure=allow_failure)


def load_json(result):
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def list_job_executions(thing_name, region, status):
    result = run_aws(
        [
            "iot",
            "list-job-executions-for-thing",
            "--thing-name",
            thing_name,
            "--status",
            status,
        ],
        region=region,
    )
    payload = load_json(result)
    return payload.get("executionSummaries", [])


def collect_active_jobs(thing_name, region, statuses, job_id_prefix):
    active = []
    for status in statuses:
        for item in list_job_executions(thing_name, region, status):
            job_id = item.get("jobId", "")
            summary = item.get("jobExecutionSummary", {})
            if job_id_prefix and not job_id.startswith(job_id_prefix):
                continue
            active.append(
                {
                    "job_id": job_id,
                    "status": summary.get("status", status),
                    "queued_at": summary.get("queuedAt"),
                    "started_at": summary.get("startedAt"),
                    "last_updated_at": summary.get("lastUpdatedAt"),
                }
            )
    return sorted(active, key=lambda item: item["job_id"])


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def checked_snapshot(thing_name, region, status, deadline):
    """One bounded, non-paginated list call; never publish the CLI's output."""
    command = [*aws_command_prefix(), "iot", "list-job-executions-for-thing",
               "--thing-name", thing_name, "--status", status,
               "--max-results", "250", "--no-paginate", "--region", region,
               "--output", "json", "--cli-connect-timeout", "10", "--cli-read-timeout", "20"]
    environment = dict(os.environ, AWS_MAX_ATTEMPTS="1", AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off")
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                               env=environment)
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("AWS list snapshot deadline exhausted")
            try:
                stdout, _stderr = process.communicate(timeout=min(CHECK_HEARTBEAT_SECONDS, remaining))
                break
            except subprocess.TimeoutExpired:
                print(json.dumps({"status": "lookup_waiting"}), flush=True)
        if process.returncode != 0 or len(stdout) > 2 * 1024 * 1024:
            raise ValueError("AWS list snapshot failed")
        payload = json.loads(stdout)
        if not isinstance(payload, dict) or not isinstance(payload.get("executionSummaries"), list):
            raise ValueError("Invalid AWS list snapshot")
        return payload
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=CHECK_HEARTBEAT_SECONDS)


def check_empty(thing_name, region, job_id_prefix, output_json):
    # Reserve the final heartbeat interval for stopping/reaping the owned CLI.
    deadline = time.monotonic() + CHECK_TIMEOUT_SECONDS - CHECK_HEARTBEAT_SECONDS
    counts = {status: None for status in CHECK_STATUSES}
    result = {"status": "lookup_failed", "active_count": None, "status_counts": counts,
              "snapshot_complete": False, "mutation_count": 0}
    code = 1
    try:
        for status in CHECK_STATUSES:
            payload = checked_snapshot(thing_name, region, status, deadline)
            matched = 0
            for item in payload["executionSummaries"]:
                if not isinstance(item, dict) or not isinstance(item.get("jobId"), str):
                    raise ValueError("Invalid AWS execution summary")
                summary = item.get("jobExecutionSummary")
                if not isinstance(summary, dict) or summary.get("status") != status:
                    raise ValueError("Unexpected AWS execution status")
                if item["jobId"].startswith(job_id_prefix):
                    matched += 1
            counts[status] = matched
            if payload.get("nextToken"):
                result["status"] = "incomplete_snapshot"
                break
        else:
            total = sum(counts.values())
            result.update(status="active" if total else "empty", active_count=total,
                          snapshot_complete=True)
            code = 1 if total else 0
    except KeyboardInterrupt:
        result["status"] = "interrupted"
        code = 130
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError):
        # Exceptions and AWS stderr can contain commands, identifiers or credentials.
        # Keep the failure terminal and publish only aggregate state.
        result["status"] = "lookup_failed"
    write_json(Path(output_json), result)
    print(json.dumps(result, sort_keys=True), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description="Cancel queued/in-progress AWS IoT Jobs for one thing")
    parser.add_argument("--thing-name", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--job-id-prefix", default="AFR_OTA-")
    parser.add_argument("--statuses", nargs="+", default=["QUEUED", "IN_PROGRESS"])
    parser.add_argument("--wait-timeout", type=int, default=30)
    parser.add_argument("--poll-interval", type=int, default=3)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check-empty", action="store_true",
                        help="Read one QUEUED/IN_PROGRESS snapshot and fail if matching jobs exist; never cancel")
    args = parser.parse_args()

    if args.check_empty:
        return check_empty(args.thing_name, args.region, args.job_id_prefix, args.output_json)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "thing_name": args.thing_name,
        "region": args.region,
        "job_id_prefix": args.job_id_prefix,
        "statuses": args.statuses,
        "dry_run": args.dry_run,
        "initial_active_jobs": [],
        "actions": [],
        "remaining_active_jobs": [],
    }

    active = collect_active_jobs(args.thing_name, args.region, args.statuses, args.job_id_prefix)
    summary["initial_active_jobs"] = active

    if not active:
        print("No active IoT Jobs matched cleanup criteria.")
        write_json(Path(args.output_json), summary)
        return 0

    for job in active:
        job_id = job["job_id"]
        action = {"action": "cancel-job-execution", "job_id": job_id, "input_status": job["status"]}
        summary["actions"].append(action)
        if args.dry_run:
            print(f"DRY-RUN: would cancel job execution {job_id} for {args.thing_name}")
            continue
        run_aws(
            [
                "iot",
                "cancel-job-execution",
                "--thing-name",
                args.thing_name,
                "--job-id",
                job_id,
                "--force",
            ],
            region=args.region,
        )

    deadline = time.time() + args.wait_timeout
    remaining = collect_active_jobs(args.thing_name, args.region, args.statuses, args.job_id_prefix)
    while remaining and time.time() < deadline:
        print(f"Waiting for {len(remaining)} job execution(s) to leave active states...")
        time.sleep(args.poll_interval)
        remaining = collect_active_jobs(args.thing_name, args.region, args.statuses, args.job_id_prefix)

    summary["remaining_active_jobs"] = remaining
    write_json(Path(args.output_json), summary)

    if remaining:
        print("Active IoT Jobs remain after cleanup:")
        for job in remaining:
            print(f"  - {job['job_id']} ({job['status']})")
        return 1

    print("IoT Jobs cleanup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

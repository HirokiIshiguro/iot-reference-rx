#!/usr/bin/env python3
"""Cancel active AWS IoT Jobs for a thing before hardware tests."""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


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


def run_aws(args, region, *, allow_failure=False):
    return run_command(["aws", *args, "--region", region, "--output", "json"], allow_failure=allow_failure)


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
    args = parser.parse_args()

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

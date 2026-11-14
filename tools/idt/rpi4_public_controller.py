#!/usr/bin/env python3
"""Public-only paired build probe; never starts IDT, AWS, or hardware."""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.idt import rpi4_pair as pair, rpi4_pair_agent as agent
from tools.idt.oidc_job import current_job_metadata
from tools.idt.rpi4_pair_broker import Broker


def verify_job(env, job, source_sha):
    pipeline = env.get("CI_PIPELINE_ID", "")
    ref = env.get("CI_COMMIT_BRANCH", "")
    if (env.get("CI_PROJECT_ID") != "38" or env.get("CI_RUNNER_ID") != "28"
            or env.get("CI_COMMIT_REF_PROTECTED") != "true" or env.get("CI_PIPELINE_SOURCE") not in ("web", "api")
            or env.get("CI_COMMIT_SHA") != source_sha or not re.fullmatch(r"[0-9a-f]{40}", source_sha)
            or not re.fullmatch(r"[0-9]{1,20}", pipeline) or not ref
            or re.fullmatch(r"(?i)(t|true|\+?0*1)", env.get("CI_DEBUG_TRACE", ""))
            or re.fullmatch(r"(?i)(t|true|\+?0*1)", env.get("CI_DEBUG_SERVICES", ""))):
        raise ValueError("unexpected public controller identity")
    try:
        if (job["status"] != "running" or str(job["id"]) != env["CI_JOB_ID"]
                or str(job["pipeline"]["id"]) != pipeline or job["pipeline"]["ref"] != ref
                or job["runner"]["id"] != 28 or job["commit"]["id"] != source_sha
                or "project38-idt-rpi4-protected" not in job["tag_list"]):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("public controller job metadata mismatch") from None
    return pipeline, ref


def request_public_build(pipeline, source_sha, seconds):
    request_id = secrets.token_hex(16)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(seconds)
        connection.connect(str(agent.session_path(pipeline) / "build.sock"))
        with connection.makefile("rwb", buffering=0) as stream:
            pair.write_frame(stream, {"kind": "public-build", "request_id": request_id, "source_sha": source_sha})
            response = pair.read_frame(stream)
    if response != {"kind": "public-result", "request_id": request_id, "source_sha": source_sha}:
        raise ValueError("public build response mismatch")


def run(env, job, source_sha):
    pipeline, ref = verify_job(env, job, source_sha)
    token = env.get("CI_JOB_TOKEN", "")
    broker = Broker(token, ref, pipeline, source_sha, "public", build_seconds=3900)
    broker.start()
    try:
        request_public_build(pipeline, source_sha, 4800)
    finally:
        broker.close()
    print("Public paired RX72N placeholder build completed", flush=True)


def main():
    if sys.platform != "linux":
        raise ValueError("Linux controller required")
    import pwd
    account = pwd.getpwuid(os.geteuid())
    if (account.pw_name != "gitlab-runner-idt-rx"
            or Path(os.environ.get("CI_PROJECT_DIR", "")).resolve() != ROOT):
        raise ValueError("unexpected Linux controller account")
    os.environ["HOME"] = account.pw_dir
    environment = dict(os.environ)
    job = current_job_metadata(environment.get("CI_JOB_TOKEN", ""))
    sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain=v1",
                                      "--untracked-files=all", "--ignore-submodules=none"], text=True)
    if status:
        raise ValueError("public controller source is not clean")
    run(environment, job, sha)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Public paired build failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None

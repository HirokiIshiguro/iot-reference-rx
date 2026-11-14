#!/usr/bin/env python3
"""Wire the fixed Linux IDT launcher to on-demand Windows builds.

The CI workflow and the Windows native worker remain disabled pending the
public-only paired build and a separate physical-run review.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.idt import linux_oidc_job
from tools.idt.initialize_linux_dependencies import git_environment, initialize
from tools.idt.rpi4_pair_broker import Broker


def main():
    if sys.platform != "linux" or platform.machine().lower() not in {"aarch64", "arm64"}:
        raise ValueError("dedicated Linux ARM64 runner required")
    import pwd
    account = pwd.getpwuid(os.geteuid())
    if (account.pw_name != linux_oidc_job.RUNNER_USER
            or Path(os.environ.get("CI_PROJECT_DIR", "")).resolve() != ROOT):
        raise ValueError("unexpected Linux controller identity")
    config = linux_oidc_job.read_reviewed_config()
    if Path(config.home).resolve(strict=True) != Path(account.pw_dir).resolve(strict=True):
        raise ValueError("reviewed home differs from the dedicated account")
    os.environ["HOME"] = config.home
    env = dict(os.environ)
    sha = subprocess.check_output([config.git, "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    job = linux_oidc_job.current_job_metadata(env.get("CI_JOB_TOKEN", ""))
    linux_oidc_job.verified_context(env, source_sha=sha, config=config, job=job)
    count = initialize(ROOT, config.git, git_environment(env, config))
    print("Pinned nested dependency roots initialized: " + str(count), flush=True)
    broker = Broker(env["CI_JOB_TOKEN"], config.ref, str(job["pipeline"]["id"]), sha,
                    "transport", build_seconds=config.pair_build_seconds,
                    queue_seconds=linux_oidc_job.NATIVE_SECONDS - config.pair_build_seconds
                    - linux_oidc_job.READY_SECONDS - linux_oidc_job.RESPONSE_SECONDS)
    broker.start()
    try:
        return linux_oidc_job.main()
    finally:
        broker.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("Paired native controller failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None

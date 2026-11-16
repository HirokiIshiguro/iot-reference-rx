#!/usr/bin/env python3
"""Check same-source public artifacts on RPi #4 without AWS or hardware."""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.idt.initialize_linux_dependencies import clean_status, git_environment, initialize
from tools.idt.oidc_job import current_job_metadata
from tools.idt.stage_public_assets import source_digest, stage_assets

RUNNER_USER = 'gitlab-runner-idt-rx'
RUNNER_TAG = 'project38-idt-rpi4-protected'


def verify_job(env, job, sha):
    ref = env.get('CI_COMMIT_BRANCH', '')
    if (env.get('CI_PROJECT_ID') != '38' or env.get('CI_RUNNER_ID') != '28'
            or env.get('CI_COMMIT_REF_PROTECTED') != 'true' or not ref
            or any(char in ref for char in '\r\n\0')
            or env.get('CI_PIPELINE_SOURCE') not in ('api', 'web')
            or env.get('IDT_PAIR_MODE') != 'transport-controller' or env.get('CI_COMMIT_SHA') != sha
            or not re.fullmatch(r'[0-9a-f]{40}', sha)):
        raise ValueError('unexpected snapshot job identity')
    try:
        if (job['status'] != 'running' or str(job['id']) != env['CI_JOB_ID']
                or str(job['pipeline']['id']) != env['CI_PIPELINE_ID']
                or job['pipeline']['ref'] != ref or job['runner']['id'] != 28
                or job['commit']['id'] != sha or RUNNER_TAG not in job['tag_list']):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError('unexpected snapshot job metadata') from None


def main():
    if sys.platform != 'linux' or platform.machine().lower() not in {'aarch64', 'arm64'}:
        raise ValueError('dedicated Linux ARM64 runner required')
    import pwd
    account = pwd.getpwuid(os.geteuid())
    if account.pw_name != RUNNER_USER or Path(os.environ.get('CI_PROJECT_DIR', '')).resolve(strict=True) != ROOT:
        raise ValueError('unexpected Linux snapshot account')
    for name in list(os.environ):
        if name.upper().startswith(('AWS_', 'RX_OIDC_')):
            os.environ.pop(name)
    os.environ['HOME'] = account.pw_dir
    env = dict(os.environ)
    git = '/usr/bin/git'
    fixed = SimpleNamespace(home=account.pw_dir, search_path='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
    git_env = git_environment(env, fixed)
    sha = subprocess.check_output([git, '-C', str(ROOT), 'rev-parse', 'HEAD'], env=git_env,
                                  text=True, encoding='ascii').strip()
    verify_job(env, current_job_metadata(env.get('CI_JOB_TOKEN', '')), sha)
    initialize(ROOT, git, git_env)
    status = clean_status(ROOT, git, git_env)
    if status:
        raise ValueError('snapshot checkout is not clean')
    private = Path(tempfile.mkdtemp(prefix='idt-snapshot-', dir=account.pw_dir))
    try:
        _, expected = stage_assets(ROOT, private, sha)
        actual = source_digest(ROOT)
        if not hmac.compare_digest(actual, expected):
            raise ValueError('Windows and RPi source snapshots differ')
        output = ROOT / 'artifacts/idt-snapshot-proof.json'
        with output.open('x', encoding='utf-8') as stream:
            json.dump({'schema_version': 1, 'source_sha': sha, 'snapshot_sha256': actual}, stream)
            stream.write('\n')
        print('Windows/RPi same-source public snapshot: PASS', flush=True)
    finally:
        shutil.rmtree(private)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Source snapshot verification failed: ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None

"""Dedicated RX72N Transport launcher for a reviewed Linux ARM64 runner.

No runner, account, budget or host paths have been approved for this entry
point yet. The parent integration must supply a reviewed configuration before
this module can contact STS or start IDT.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.aws.oidc_session import (ExpectedIdentity, IDT_SESSION_SECONDS, OidcError, REGION,
                                    TOKEN_ENV, child_environment, obtain_session)
from tools.idt.oidc_job import (Budget, MAX_JOB_SECONDS, NATIVE_SECONDS, PROJECT_PATH, current_job_metadata,
                                verified_job_environment)
from tools.idt.public_signer_provision import ENVIRONMENT_INPUTS as PUBLIC_SIGNER_INPUTS
from tools.idt.cleanup_budget import owned_runtime_cleanup_seconds

RUNNER_TAG = "project38-idt-rpi4-protected"
RUNNER_USER = "gitlab-runner-idt-rx"
CONFIG_DIRECTORY = "/etc/idt-rx"
CONFIG_NAME = "runtime.json"


@dataclass(frozen=True)
class LinuxConfig:
    account: str
    role_arn: str
    ref: str
    runner_id: int
    job_timeout_seconds: int
    budget: Budget
    runtime_root: str
    idt_root: str
    ssh: str
    scp: str
    git: str
    python: str
    home: str
    search_path: str
    pair_build_seconds: int
    qemu_sysroot: str

    def __post_init__(self):
        if (not re.fullmatch(r"[0-9]{12}", self.account)
                or not re.fullmatch(r"arn:aws:iam::" + self.account + r":role/saffti-oss-gitlab-oidc", self.role_arn)
                or not self.ref or any(c in self.ref for c in "\r\n\0")
                or not isinstance(self.runner_id, int) or isinstance(self.runner_id, bool) or self.runner_id <= 0
                or not isinstance(self.job_timeout_seconds, int) or isinstance(self.job_timeout_seconds, bool)
                or not 0 < self.job_timeout_seconds <= MAX_JOB_SECONDS or not isinstance(self.budget, Budget)
                or not isinstance(self.pair_build_seconds, int) or isinstance(self.pair_build_seconds, bool)
                or not 0 < self.pair_build_seconds <= NATIVE_SECONDS
                or self.budget.initial_required() + self.budget.margin_seconds > min(self.job_timeout_seconds, IDT_SESSION_SECONDS)):
            raise OidcError("invalid reviewed Linux IDT configuration")
        paths = (self.runtime_root, self.idt_root, self.ssh, self.scp,
                 self.git, self.python, self.home, self.qemu_sysroot, *self.search_path.split(":"))
        if any(not isinstance(path, str) or not path or not PurePosixPath(path).is_absolute()
               or any(c.isspace() or c == "\0" for c in path) for path in paths):
            raise OidcError("invalid reviewed Linux path")


def parse_config(document):
    """Interpret only the reviewed, nonsecret host settings."""
    fields = set(LinuxConfig.__dataclass_fields__) | {"schema_version"}
    budget_fields = set(Budget.__dataclass_fields__)
    if (not isinstance(document, dict) or set(document) != fields or type(document.get("schema_version")) is not int
            or document.get("schema_version") != 1
            or not isinstance(document.get("budget"), dict) or set(document["budget"]) != budget_fields):
        raise OidcError("invalid Linux host configuration")
    try:
        values = {key: value for key, value in document.items() if key != "schema_version"}
        values["budget"] = Budget(**values["budget"])
        return LinuxConfig(**values)
    except (TypeError, ValueError):
        raise OidcError("invalid Linux host configuration") from None


def validate_config_metadata(directory, file, runner_gid):
    if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0 or stat.S_IMODE(directory.st_mode) != 0o755
            or not stat.S_ISREG(file.st_mode) or file.st_uid != 0 or file.st_gid != runner_gid
            or stat.S_IMODE(file.st_mode) != 0o640):
        raise OidcError("Linux host configuration ownership or mode is invalid")


def read_reviewed_config():
    """Read the fixed root-owned path; pipeline variables cannot select it."""
    import grp
    directory = os.open(CONFIG_DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        file = os.open(CONFIG_NAME, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        try:
            validate_config_metadata(os.fstat(directory), os.fstat(file), grp.getgrnam(RUNNER_USER).gr_gid)
            with os.fdopen(file, "rb") as source:
                file = None
                data = source.read(16385)
        finally:
            if file is not None:
                os.close(file)
    finally:
        os.close(directory)
    if len(data) > 16384:
        raise OidcError("Linux host configuration is too large")
    try:
        return parse_config(json.loads(data))
    except (UnicodeError, ValueError):
        raise OidcError("invalid Linux host configuration") from None


def verified_context(env, *, source_sha, config, job):
    """Match the reviewed runner ID and target against the current job API."""
    if not isinstance(config, LinuxConfig):
        raise OidcError("unreviewed Linux IDT configuration")
    if (env.get("RUN_RX_IDT") != "true" or env.get("IDT_TARGET") != "rx72n-ethernet"
            or env.get("IDT_SCOPE") != "transport" or env.get("AWS_ROLE_ARN") != config.role_arn
            or any(not env.get(name) for name in PUBLIC_SIGNER_INPUTS.values())):
        raise OidcError("unexpected Linux IDT target or routing")
    try:
        runner_id = job["runner"]["id"]
        if (not isinstance(runner_id, int) or isinstance(runner_id, bool) or runner_id != config.runner_id
                or RUNNER_TAG not in job["tag_list"] or job["pipeline"]["ref"] != config.ref):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise OidcError("unexpected dedicated runner metadata") from None
    verified = verified_job_environment(env, config, source_sha, job)
    expected = ExpectedIdentity("38", PROJECT_PATH, config.account, config.role_arn, "branch", config.ref,
                                source_sha, ("web", "api", "schedule"), runner_id)
    return verified, expected


def prepare_child(env, *, source_sha, config, job, baseline_path, session_factory=None):
    """Obtain the fixed session after reviewed job and source admission."""
    verified, expected = verified_context(env, source_sha=source_sha, config=config, job=job)
    baseline = PurePosixPath(str(baseline_path))
    if not baseline.is_absolute() or any(c.isspace() for c in str(baseline)):
        raise OidcError("invalid private source baseline")
    factory = obtain_session if session_factory is None else session_factory
    session = factory(verified, expected, required_seconds=config.budget.initial_required(),
                      margin_seconds=config.budget.margin_seconds, duration_seconds=IDT_SESSION_SECONDS)
    allowed = {"CI", "CI_PIPELINE_ID", "CI_PROJECT_DIR", "IDT_TARGET", "IDT_SCOPE", "RUN_RX_IDT",
               *PUBLIC_SIGNER_INPUTS.values()}
    child = child_environment(verified, session, allow_names=allowed)
    child.update(PATH=config.search_path, HOME=config.home, IDT_HOST_MODE="linux-arm64",
                 QEMU_LD_PREFIX=config.qemu_sysroot,
                 IDT_LINUX_RUNTIME_ROOT=config.runtime_root, IDT_LINUX_IDT_ROOT=config.idt_root,
                 IDT_LINUX_BUILD_CALLBACK=str(ROOT / "tools/idt/rpi4_build_callback.py"), IDT_LINUX_SSH=config.ssh,
                 IDT_LINUX_SCP=config.scp, IDT_PAIR_BASELINE=str(baseline),
                 IDT_PAIR_SOCKET=str(Path(config.home) / ".cache/idt-rx72n-pair" / str(job["pipeline"]["id"]) / "build.sock"),
                 IDT_PAIR_BUILD_SECONDS=str(config.pair_build_seconds),
                 RX_OIDC_IDT_NATIVE_REQUIRED_SECONDS=str(config.budget.native_required()),
                 RX_OIDC_IDT_PREPARE_SECONDS=str(config.budget.native_prepare_seconds),
                 RX_OIDC_IDT_MARGIN_SECONDS=str(config.budget.margin_seconds))
    return child


def publish_reports(private_output, destination, *, require_all):
    """Publish only the existing redacted IDT reports after the source copy is made."""
    if destination.is_symlink() or destination.parent.is_symlink():
        raise OidcError("invalid report destination")
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ("FRQ_Report.xml", "metadata.json", "summary.json"):
        source = private_output / name
        target = destination / name
        if source.is_symlink() or target.is_symlink():
            raise OidcError("invalid private report")
        if source.is_file():
            shutil.copyfile(source, target)
            copied.append(name)
    if require_all and len(copied) != 3:
        raise OidcError("successful IDT run did not provide all reports")


def capture_baseline(source, path):
    """Use the paired worker's snapshot format without duplicating its code."""
    try:
        from tools.idt.rpi4_pair import snapshot
    except ImportError:
        raise OidcError("paired build integration is unavailable") from None
    path.write_text(json.dumps(snapshot(source), sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def cancel_linux_child(_signal, _frame):
    raise KeyboardInterrupt


def run_linux_child(command, environment):
    """Forward cancellation to the owned supervisor and wait for its cleanup."""
    process = subprocess.Popen(command, cwd=ROOT, env=environment, start_new_session=True)
    try:
        return process.wait()
    except BaseException:
        if process.poll() is None:
            try:
                process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=owned_runtime_cleanup_seconds())
            except subprocess.TimeoutExpired:
                # An unconfirmed stop must retain the private runtime.
                pass
        raise


def check_host_paths(config):
    for path in (config.git, config.python, config.ssh, config.scp):
        if not Path(path).is_file() or not os.access(path, os.X_OK):
            raise OidcError("reviewed Linux executable unavailable")
    callback = ROOT / "tools/idt/rpi4_build_callback.py"
    if not callback.is_file() or not os.access(callback, os.R_OK):
        raise OidcError("source build callback unavailable")
    for path in (config.runtime_root, config.idt_root, config.home, config.qemu_sysroot):
        if not Path(path).is_dir():
            raise OidcError("reviewed Linux directory unavailable")


def main():
    if sys.platform != "linux":
        raise OidcError("unexpected Linux runner identity")
    import pwd
    if (platform.machine().lower() not in {"aarch64", "arm64"}
            or pwd.getpwuid(os.geteuid()).pw_name != RUNNER_USER
            or Path(os.environ.get("CI_PROJECT_DIR", "")).resolve() != ROOT):
        raise OidcError("unexpected Linux runner identity")
    config = read_reviewed_config()
    check_host_paths(config)
    source_env = dict(os.environ)
    git_env = {"PATH": config.search_path, "HOME": config.home, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    source_sha = subprocess.check_output([config.git, "rev-parse", "HEAD"], cwd=ROOT, env=git_env,
                                         text=True, encoding="utf-8").strip()
    job = current_job_metadata(source_env.get("CI_JOB_TOKEN", ""))
    verified_context(source_env, source_sha=source_sha, config=config, job=job)
    status = subprocess.check_output([config.git, "status", "--porcelain=v1", "--untracked-files=all"],
                                     cwd=ROOT, env=git_env, text=True, encoding="utf-8")
    if status:
        raise OidcError("source checkout is not clean")
    # The paired build implementation is supplied by the Windows integration.
    # Capture the pristine checkout before IDT creates its injected source copy.
    runtime_root = Path(config.runtime_root).resolve(strict=True)
    if runtime_root == ROOT or ROOT in runtime_root.parents:
        raise OidcError("Linux runtime must be outside the source checkout")
    baseline_dir = Path(tempfile.mkdtemp(prefix="idt-baseline-", dir=runtime_root))
    launched = finished = False
    try:
        baseline_path = baseline_dir / "baseline.json"
        capture_baseline(ROOT, baseline_path)
        child = prepare_child(source_env, source_sha=source_sha, config=config, job=job,
                              baseline_path=baseline_path)
        source_env.pop(TOKEN_ENV, None)
        os.environ.pop(TOKEN_ENV, None)
        private_output = baseline_dir / "report"
        command = [config.python, str(ROOT / "tools/idt/run_idt.py"), "--target", "rx72n-ethernet",
                   "--scope", "transport", "--output", str(private_output), "--region", REGION]
        launched = True
        previous_term = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, cancel_linux_child)
        try:
            returncode = run_linux_child(command, child)
        finally:
            signal.signal(signal.SIGTERM, previous_term)
        publish_reports(private_output, ROOT / "artifacts/idt", require_all=returncode == 0)
        # A nonzero launcher exit does not prove its descendants are stopped.
        finished = returncode == 0
        return returncode
    finally:
        if finished or not launched:
            shutil.rmtree(baseline_dir)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("Linux IDT OIDC preflight failed", file=sys.stderr)
        sys.exit(1)

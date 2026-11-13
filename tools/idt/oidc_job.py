"""Run the IDT CI script with one verified, non-refreshing STS session.

No runtime budget has been approved yet, so the CI entry point fails closed.
This module is a Draft and does not authorize AWS or hardware execution.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import ntpath
from pathlib import PurePosixPath
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.aws.oidc_session import (ExpectedIdentity, IDT_SESSION_SECONDS, OidcError, TOKEN_ENV,
                                    REGION, child_environment, ensure_child_budget, obtain_session)
from tools.idt.cleanup_budget import NATIVE_CLEANUP_SECONDS, owned_runtime_cleanup_seconds
from tools.idt.host_profile import load_host_profile
from tools.idt.prepare_target_network import INPUTS as NETWORK_INPUTS
from tools.idt.public_signer_provision import ENVIRONMENT_INPUTS as PUBLIC_SIGNER_INPUTS

PROJECT_PATH = "oss/import/github/renesas/iot-reference-rx"
PILOT_REF = "202-idt-transport-rx72n-pilot"
NATIVE_SECONDS = 4500
MAX_JOB_SECONDS = 10800
SIGNER_CLEANUP_SECONDS = 60
# Populate only after measuring and reviewing every remaining bound. A zero or
# missing bootstrap/prepare/report/margin cannot establish a safe deadline.
REVIEWED_CONFIGS = {}
ENTRY_PYTHON = "C:/ai/codex/tools/venvs/rx72n-idt-windows/Scripts/python.exe"
_INPUTS = {
    "CI", "CI_PIPELINE_ID", "CI_PROJECT_DIR", "CI_RUNNER_DESCRIPTION", "PYTHONUTF8", "PROGRAMFILES",
    "PROGRAMFILES(X86)", "PROGRAMDATA", "APPDATA", "LOCALAPPDATA",
    "RX72N_IDT_SCOPE", "RUN_RX_IDT", "IDT_TARGET", "IDT_SCOPE",
    "RX72N_IDT_TEST_ID", "IDT_TEST_ID",
    *PUBLIC_SIGNER_INPUTS.values(),
    *(name for values in NETWORK_INPUTS.values() for name in values.values()),
}
IDT_WSL_INPUTS = {
    "CI", "IDT_RUNTIME_DIR", "IDT_PRIVATE_KEY_FILE", "IDT_PROVENANCE_FILE", "IDT_WINDOWS_PYTHON",
    "IDT_WINDOWS_PWSH", "IDT_SCOPE", "IDT_TARGET", "IDT_SOURCE_SHA", "IDT_E2STUDIO_CLI",
    "IDT_WORKSPACE_ROOT", "IDT_LINUX_PYTHON", "IDT_WINDOWS_SSH", "IDT_WINDOWS_SCP",
    "IDT_DIAGNOSTIC_ONLY", "IDT_OTA_SIGNING_KEY_FILE", "IDT_OTA_SIGNER_CERT_FILE",
    "RX_OIDC_IDT_NATIVE_REQUIRED_SECONDS", "RX_OIDC_IDT_PREPARE_SECONDS", "RX_OIDC_IDT_MARGIN_SECONDS",
    "RX_OIDC_IDT_WSL_PATH", "RX_OIDC_IDT_WSL_HOME",
    *PUBLIC_SIGNER_INPUTS.values(),
    *(name for values in NETWORK_INPUTS.values() for name in values.values()),
}


@dataclass(frozen=True)
class Budget:
    bootstrap_seconds: int
    native_prepare_seconds: int
    report_seconds: int
    margin_seconds: int

    def __post_init__(self):
        if any(not isinstance(n, int) or isinstance(n, bool) or n <= 0
               for n in (self.bootstrap_seconds, self.native_prepare_seconds,
                         self.report_seconds, self.margin_seconds)):
            raise OidcError("unreviewed IDT time budget")

    def native_required(self):
        return NATIVE_SECONDS + owned_runtime_cleanup_seconds(NATIVE_CLEANUP_SECONDS) + SIGNER_CLEANUP_SECONDS + self.report_seconds

    def initial_required(self):
        return self.bootstrap_seconds + self.native_prepare_seconds + self.native_required()


@dataclass(frozen=True)
class ReviewedConfig:
    account: str
    role_arn: str
    runner_id: int
    job_timeout_seconds: int
    windows_root: str
    user_profile: str
    temp_directory: str
    program_files: str
    program_files_x86: str
    program_data: str
    wsl_path: str
    wsl_home: str
    host_profile: str
    host_profile_sha256: str
    search_path: str
    git_executable: str
    budget: Budget

    def __post_init__(self):
        if (not isinstance(self.budget, Budget) or not isinstance(self.runner_id, int)
                or isinstance(self.runner_id, bool) or self.runner_id <= 0
                or not isinstance(self.job_timeout_seconds, int) or isinstance(self.job_timeout_seconds, bool)
                or not 1 <= self.job_timeout_seconds <= MAX_JOB_SECONDS
                or any(not isinstance(x, str) or not x or any(c in x for c in "\r\n\0")
                       for x in (self.account, self.role_arn, self.windows_root, self.user_profile, self.temp_directory,
                                 self.program_files, self.program_files_x86, self.program_data, self.wsl_path, self.wsl_home,
                                 self.host_profile, self.host_profile_sha256, self.search_path,
                                 self.git_executable))
                or not re.fullmatch(r"[0-9a-f]{64}", self.host_profile_sha256)
                or any(not ntpath.isabs(x) for x in (self.windows_root, self.user_profile, self.temp_directory,
                                                     self.program_files, self.program_files_x86, self.program_data,
                                                     self.host_profile, self.git_executable))
                or any(not ntpath.isabs(item) for item in self.search_path.split(";"))
                or not PurePosixPath(self.wsl_home).is_absolute()
                or any(not PurePosixPath(item).is_absolute() for item in self.wsl_path.split(":"))):
            raise OidcError("invalid reviewed IDT configuration")


def scope_from_env(env):
    scope = env.get("IDT_SCOPE") if env.get("RUN_RX_IDT") == "true" else env.get("RX72N_IDT_SCOPE")
    if scope not in {"preflight", "transport", "mqtt", "pkcs11", "ota-pal", "ota-mqtt"}:
        raise OidcError("invalid IDT scope")
    return scope


def prepare_child(env, *, source_sha, config, user_name, session_factory=None):
    """Authenticate once and prepare an isolated child; performs no process launch."""
    scope = scope_from_env(env)
    # Admission, profile creation evidence and independent recovery have not
    # been connected. Do not create signer resources or start native OTA.
    if scope in {"ota-mqtt", "ota-pal"}:
        raise OidcError("native OTA admission is not ready")
    if not isinstance(config, ReviewedConfig):
        raise OidcError("unreviewed IDT configuration")
    if not isinstance(user_name, str) or not user_name or any(c in user_name for c in "\r\n\0"):
        raise OidcError("IDT execution identity unavailable")
    if env.get("AWS_ROLE_ARN") != config.role_arn:
        raise OidcError("IDT routing differs from reviewed configuration")
    if (scope != "transport" or env.get("RUN_RX_IDT") != "true"
            or env.get("IDT_TARGET") != "rx72n-ethernet"
            or env.get("IDT_TEST_ID") or env.get("RX72N_IDT_TEST_ID")
            or env.get("CI_COMMIT_BRANCH") != PILOT_REF):
        raise OidcError("outside the reviewed Transport pilot")
    budget = config.budget
    expected = ExpectedIdentity("38", PROJECT_PATH, config.account, config.role_arn,
                                "branch", PILOT_REF, source_sha, ("api",), config.runner_id)
    if session_factory is None:
        session_factory = obtain_session
    session = session_factory(env, expected, required_seconds=budget.initial_required(),
                              margin_seconds=budget.margin_seconds, duration_seconds=IDT_SESSION_SECONDS)
    child = child_environment(env, session, allow_names=_INPUTS)
    for name in list(child):
        if name.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "USERPROFILE", "HOME", "TEMP", "TMP",
                            "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "APPDATA", "LOCALAPPDATA",
                            "COMSPEC", "PATHEXT", "SYSTEMDRIVE", "LANG", "LC_ALL", "TMPDIR", "WSLENV"}:
            child.pop(name)
    child["PATH"] = config.search_path
    child["SYSTEMROOT"] = config.windows_root
    child["WINDIR"] = config.windows_root
    child["USERPROFILE"] = config.user_profile
    child["HOME"] = config.user_profile
    child["USERNAME"] = user_name
    child["TEMP"] = config.temp_directory
    child["TMP"] = config.temp_directory
    child["PROGRAMFILES"] = config.program_files
    child["PROGRAMFILES(X86)"] = config.program_files_x86
    child["PROGRAMDATA"] = config.program_data
    child["APPDATA"] = ntpath.join(config.user_profile, "AppData", "Roaming")
    child["LOCALAPPDATA"] = ntpath.join(config.user_profile, "AppData", "Local")
    child["COMSPEC"] = ntpath.join(config.windows_root, "System32", "cmd.exe")
    child["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
    child["SYSTEMDRIVE"] = ntpath.splitdrive(config.windows_root)[0]
    child["WSLENV"] = ""
    child["RX72N_IDT_PYTHON"] = ENTRY_PYTHON
    child["RX72N_IDT_HOST_PROFILE"] = config.host_profile
    child["RX_IDT_REVIEWED_PROFILE_SHA256"] = config.host_profile_sha256
    child["RX_OIDC_IDT_NATIVE_REQUIRED_SECONDS"] = str(budget.native_required())
    child["RX_OIDC_IDT_PREPARE_SECONDS"] = str(budget.native_prepare_seconds)
    child["RX_OIDC_IDT_MARGIN_SECONDS"] = str(budget.margin_seconds)
    child["RX_OIDC_IDT_WSL_PATH"] = config.wsl_path
    child["RX_OIDC_IDT_WSL_HOME"] = config.wsl_home
    return child


def check_child_budget(env, *, before_run=False, now=None):
    """Recheck STS and job/script time; CI must never bypass this check."""
    if not env.get("RX_OIDC_EXPIRATION_UTC"):
        if env.get("CI", "").lower() == "true":
            raise OidcError("missing fixed OIDC session")
        return
    allowed_aws = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_CONFIG_FILE",
                   "AWS_SHARED_CREDENTIALS_FILE", "AWS_EC2_METADATA_DISABLED", "AWS_DEFAULT_REGION", "AWS_REGION"}
    allowed_aws.update(name for values in NETWORK_INPUTS.values() for name in values.values() if name.startswith("AWS_"))
    if (any(not env.get(name) for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"))
            or env.get("AWS_CONFIG_FILE") != os.devnull or env.get("AWS_SHARED_CREDENTIALS_FILE") != os.devnull
            or env.get("BOTO_CONFIG") != os.devnull or "BOTO_PATH" in env or env.get("AWS_EC2_METADATA_DISABLED") != "true"
            or env.get("AWS_REGION") != REGION or env.get("AWS_DEFAULT_REGION") != REGION
            or any(name.upper().startswith("AWS_") and name.upper() not in allowed_aws for name in env)
            or any(name.upper() in {TOKEN_ENV, "RX_IOT_OIDC_TOKEN", "RX_IOT_OIDC_WRONG_AUDIENCE_TOKEN",
                                    "CI_JOB_JWT", "CI_JOB_JWT_V2", "CI_JOB_TOKEN"} for name in env)):
        raise OidcError("fixed session environment is not isolated")
    try:
        native = int(env["RX_OIDC_IDT_NATIVE_REQUIRED_SECONDS"])
        prepare = int(env["RX_OIDC_IDT_PREPARE_SECONDS"])
        margin = int(env["RX_OIDC_IDT_MARGIN_SECONDS"])
    except (KeyError, ValueError, TypeError):
        raise OidcError("missing IDT budget") from None
    minimum = NATIVE_SECONDS + owned_runtime_cleanup_seconds(NATIVE_CLEANUP_SECONDS) + SIGNER_CLEANUP_SECONDS
    if native <= minimum or prepare <= 0 or margin <= 0:
        raise OidcError("invalid IDT budget")
    ensure_child_budget(env, native + (prepare if before_run else 0),
                        datetime.now(timezone.utc) if now is None else now, margin_seconds=margin)


def check_native_timeouts(env, native_seconds, cleanup_seconds):
    if env.get("RX_OIDC_EXPIRATION_UTC") and (
            native_seconds > NATIVE_SECONDS or cleanup_seconds > NATIVE_CLEANUP_SECONDS):
        raise OidcError("native timeouts exceed the checked OIDC budget")


def verify_host_profile(profile, expected_sha256):
    digest = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=True).encode("utf-8")).hexdigest()
    if digest != expected_sha256:
        raise OidcError("IDT host profile differs from reviewed configuration")


def current_job_metadata(job_token):
    """Read only this job from GitLab; never put its token in a URL or child."""
    if not isinstance(job_token, str) or not job_token:
        raise OidcError("current job token unavailable")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    request = urllib.request.Request("https://gitlab.saffti.jp/api/v4/job", headers={"JOB-TOKEN": job_token})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=15) as response:
            data = response.read(65537)
        if len(data) > 65536:
            raise ValueError
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except Exception:
        raise OidcError("current job metadata unavailable") from None


def verified_job_environment(env, config, source_sha, job):
    """Use GitLab's current-job start, not an overridable start timestamp."""
    try:
        started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        timeout = int(env["CI_JOB_TIMEOUT"])
        if (started.tzinfo is None or timeout <= 0 or job["status"] != "running"
                or str(job["id"]) != env["CI_JOB_ID"]
                or str(job["pipeline"]["id"]) != env["CI_PIPELINE_ID"]
                or job["runner"]["id"] != config.runner_id
                or job["commit"]["id"] != source_sha):
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        raise OidcError("current job metadata mismatch") from None
    verified = dict(env)
    verified["CI_JOB_STARTED_AT"] = started.astimezone(timezone.utc).isoformat()
    verified["CI_JOB_TIMEOUT"] = str(min(timeout, config.job_timeout_seconds, MAX_JOB_SECONDS))
    return verified


def current_windows_user():
    """Get the current account name from Windows, not a pipeline variable."""
    if os.name != "nt":
        raise OidcError("Windows identity is unavailable")
    import ctypes
    from ctypes import wintypes
    length = wintypes.DWORD(256)
    buffer = ctypes.create_unicode_buffer(length.value)
    if not ctypes.windll.advapi32.GetUserNameW(buffer, ctypes.byref(length)):
        raise OidcError("Windows identity is unavailable")
    return buffer.value


def load_reviewed_host(config):
    # Only host path defaults may affect profile resolution. Tool overrides
    # from pipeline variables are not forwarded to this check.
    profile_env = {"WINDIR": config.windows_root, "ProgramFiles": config.program_files}
    profile = load_host_profile(profile_path=config.host_profile, environ=profile_env)
    verify_host_profile(profile, config.host_profile_sha256)
    for path in (ENTRY_PYTHON, config.git_executable,
                 ntpath.join(config.windows_root, "System32", "wsl.exe"), profile["windows_powershell"],
                 profile["e2studio_cli"], profile["ccrx"], profile["windows_ssh"], profile["windows_scp"]):
        if not Path(path).is_file():
            raise OidcError("reviewed IDT executable is unavailable")
    if not Path(config.user_profile).is_dir() or not Path(config.temp_directory).is_dir():
        raise OidcError("reviewed IDT directory is unavailable")
    return profile


def verify_transport_aws():
    """Check the exact public SSM parameter and EC2 read before native IDT."""
    check_child_budget(os.environ, before_run=True)
    import boto3
    from botocore.config import Config
    from tools.aws.oidc_session import quiet_aws_logging

    cfg = Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1},
                 proxies={}, ignore_configured_endpoint_urls=True)
    parameter = "/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"
    with quiet_aws_logging():
        session = boto3.Session(region_name=REGION)
        reply = session.client("ssm", config=cfg).get_parameters(Names=[parameter])
        image = reply.get("Parameters", [])
        if (len(image) != 1 or image[0].get("Name") != parameter
                or not re.fullmatch(r"ami-[0-9a-f]+", image[0].get("Value", ""))):
            raise OidcError("unexpected Transport AMI parameter")
        session.client("ec2", config=cfg).describe_instances(
            Filters=[{"Name": "tag:Owner", "Values": ["IoTDeviceTester"]}], MaxResults=5)
    print("IDT Transport AWS read preflight passed", flush=True)


def main():
    # Account and runner settings come from the reviewed host file rather than
    # user-supplied GitLab pipeline variables.
    source_env = dict(os.environ)
    scope = scope_from_env(source_env)
    config = REVIEWED_CONFIGS.get(scope)
    if scope == "transport" and source_env.get("CI_COMMIT_BRANCH") == PILOT_REF:
        host_config = json.loads(Path("C:/ai/codex/tools/venvs/rx72n-idt-windows/transport-pilot-config.json").read_text(encoding="utf-8"))
        config = ReviewedConfig(**{**host_config, "budget": Budget(**host_config["budget"])})
    if not isinstance(config, ReviewedConfig):
        raise OidcError("unreviewed IDT configuration")
    if ntpath.normcase(ntpath.normpath(source_env.get("CI_PROJECT_DIR", ""))) != ntpath.normcase(ntpath.normpath(str(ROOT))):
        raise OidcError("unexpected checkout")
    user_name = current_windows_user()
    profile = load_reviewed_host(config)
    git_env = {"SYSTEMROOT": config.windows_root, "WINDIR": config.windows_root,
               "TEMP": config.temp_directory, "TMP": config.temp_directory}
    git_env.update(PATH=config.search_path, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT="0")
    source_sha = subprocess.check_output([config.git_executable, "rev-parse", "HEAD"], cwd=ROOT, env=git_env,
                                         text=True, encoding="utf-8").strip()
    source_env = verified_job_environment(source_env, config, source_sha,
                                          current_job_metadata(source_env.get("CI_JOB_TOKEN", "")))
    child = prepare_child(source_env, source_sha=source_sha, config=config, user_name=user_name)
    # JWT is never inherited by this script's child processes.
    source_env.pop(TOKEN_ENV, None)
    os.environ.pop(TOKEN_ENV, None)
    script = ROOT / "tools/idt/run_ci_job.ps1"
    return subprocess.run([profile["windows_powershell"], "-NoProfile", "-File", str(script)],
                          cwd=ROOT, env=child, check=False).returncode


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--check-before-run"]:
            check_child_budget(os.environ, before_run=True)
            sys.exit(0)
        if sys.argv[1:] == ["--verify-transport-aws"]:
            verify_transport_aws()
            sys.exit(0)
        if sys.argv[1:]:
            raise OidcError("invalid arguments")
        sys.exit(main())
    except Exception:
        print("IDT OIDC preflight failed", file=sys.stderr)
        sys.exit(1)

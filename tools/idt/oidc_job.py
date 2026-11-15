"""Fixed-session and job checks for the dedicated RX72N Linux Transport route.

The existing Windows/WSL IDT and OTA routes do not use this entry point.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.aws.oidc_session import OidcError, TOKEN_ENV, REGION, ensure_child_budget
from tools.idt.cleanup_budget import NATIVE_CLEANUP_SECONDS, owned_runtime_cleanup_seconds
from tools.idt.public_signer_provision import ENVIRONMENT_INPUTS as PUBLIC_SIGNER_INPUTS

PROJECT_PATH = "oss/import/github/renesas/iot-reference-rx"
NATIVE_SECONDS = 4500
MAX_JOB_SECONDS = 10800
SIGNER_CLEANUP_SECONDS = 60
IDT_LINUX_INPUTS = {
    "CI", "IDT_RUNTIME_DIR", "IDT_PRIVATE_KEY_FILE", "IDT_PROVENANCE_FILE",
    "IDT_SCOPE", "IDT_TARGET", "IDT_SOURCE_SHA", "IDT_LINUX_PYTHON",
    "RX_OIDC_IDT_NATIVE_REQUIRED_SECONDS", "RX_OIDC_IDT_PREPARE_SECONDS", "RX_OIDC_IDT_MARGIN_SECONDS",
    "IDT_HOST_MODE", "IDT_LINUX_IDT_ROOT", "IDT_LINUX_RUNTIME_ROOT", "IDT_LINUX_BUILD_CALLBACK",
    "IDT_LINUX_SSH", "IDT_LINUX_SCP", "IDT_PAIR_BASELINE", "IDT_PAIR_BUILD_SECONDS",
    "IDT_PAIR_QUEUE_SECONDS", "IDT_PAIR_SOCKET", "QEMU_LD_PREFIX", *PUBLIC_SIGNER_INPUTS.values(),
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

def check_child_budget(env, *, before_run=False, now=None):
    """Recheck STS and job/script time; CI must never bypass this check."""
    if not env.get("RX_OIDC_EXPIRATION_UTC"):
        if env.get("CI", "").lower() == "true":
            raise OidcError("missing fixed OIDC session")
        return
    allowed_aws = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_CONFIG_FILE",
                   "AWS_SHARED_CREDENTIALS_FILE", "AWS_EC2_METADATA_DISABLED", "AWS_DEFAULT_REGION", "AWS_REGION"}
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

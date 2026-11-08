"""Obtain a fixed OIDC session without consulting the runner's AWS credentials.

This module is not wired into the production jobs yet. Callers must supply
reviewed project/role settings and a budget covering every remaining operation.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import re

REGION = "ap-northeast-1"
ISSUER = "https://gitlab.saffti.jp"
AUDIENCE = "sts.amazonaws.com"
TOKEN_ENV = "RX_OIDC_ID_TOKEN"
IDT_SESSION_SECONDS = 10800
_TRUE = re.compile(r"(?:t|true|\+?0*1)", re.IGNORECASE)
_ROLE = re.compile(r"arn:aws:iam::([0-9]{12}):role/([A-Za-z0-9+=,.@_/-]+)\Z")


class OidcError(Exception):
    """Only a fixed error type is exposed; SDK errors can contain secrets."""


@dataclass(frozen=True)
class ExpectedIdentity:
    project_id: str
    project_path: str
    account: str
    role_arn: str
    ref_type: str
    ref: str
    sha: str
    pipeline_sources: tuple[str, ...]


@dataclass(frozen=True, repr=False)
class FixedSession:
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    session_token: str = field(repr=False)
    expiration: datetime
    token_deadline: datetime


def _timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise OidcError("invalid timestamp") from None


def _duration(value: str) -> int:
    """Accept integer Go-duration units; reject unknown forms rather than guess."""
    if not value:
        raise OidcError("empty script timeout")
    parts = re.findall(r"([0-9]+)(h|m|s)", value)
    if (not parts or "".join(number + unit for number, unit in parts) != value
            or [unit for _, unit in parts] != sorted({unit for _, unit in parts}, key="hms".index)):
        raise OidcError("unsupported script timeout")
    return sum(int(number) * {"h": 3600, "m": 60, "s": 1}[unit] for number, unit in parts)


def _claims(token: str) -> dict:
    """Read only bounded claims for preflight; STS validates the signature."""
    try:
        if not token or len(token) > 32768:
            raise ValueError
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        result = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise OidcError("invalid token") from None


def validate_context(env: dict[str, str], expected: ExpectedIdentity, token: str, now: datetime) -> str:
    """Reject unprotected or incorrectly targeted jobs before contacting STS."""
    role = _ROLE.fullmatch(expected.role_arn)
    if (now.tzinfo is None or not role or role.group(1) != expected.account or not re.fullmatch(r"[0-9]{12}", expected.account)
            or not re.fullmatch(r"[0-9]{1,10}", expected.project_id)
            or expected.ref_type not in {"branch", "tag"} or not expected.ref
            or not re.fullmatch(r"[0-9a-f]{40}", expected.sha)
            or env.get("CI_PROJECT_ID") != expected.project_id
            or env.get("CI_PROJECT_PATH") != expected.project_path
            or env.get("CI_COMMIT_SHA") != expected.sha
            or env.get("CI_PIPELINE_SOURCE") not in expected.pipeline_sources
            or env.get("CI_COMMIT_REF_PROTECTED") != "true"
            or not re.fullmatch(r"[0-9]{1,20}", env.get("CI_JOB_ID", ""))
            or any(_TRUE.fullmatch(env.get(k, "")) for k in ("CI_DEBUG_TRACE", "CI_DEBUG_SERVICES"))):
        raise OidcError("invalid execution context")
    branch, tag = env.get("CI_COMMIT_BRANCH", ""), env.get("CI_COMMIT_TAG", "")
    if bool(branch) == bool(tag):
        raise OidcError("ambiguous ref")
    ref_type, ref = ("branch", branch) if branch else ("tag", tag)
    if (ref_type, ref) != (expected.ref_type, expected.ref):
        raise OidcError("unexpected ref")
    claims = _claims(token)
    subject = f"project_path:{expected.project_path}:ref_type:{ref_type}:ref:{ref}"
    audience = claims.get("aud")
    if (claims.get("iss") != ISSUER or claims.get("sub") != subject
            or claims.get("project_id") != expected.project_id
            or claims.get("job_id") != env.get("CI_JOB_ID")
            or claims.get("pipeline_source") != env.get("CI_PIPELINE_SOURCE")
            or claims.get("ref_protected") != "true" or claims.get("ref_type") != ref_type
            or claims.get("ref") != ref or claims.get("sha") != expected.sha
            or audience != AUDIENCE or not isinstance(claims.get("exp"), int) or isinstance(claims.get("exp"), bool)
            or claims["exp"] <= int(now.timestamp()) + 30):
        raise OidcError("invalid token claims")
    return "gitlab" + expected.project_id + "-" + env["CI_JOB_ID"]


def ensure_budget(env: dict[str, str], expiration: datetime, required_seconds: int,
                  now: datetime, *, margin_seconds: int, token_deadline: datetime | None = None) -> None:
    """Check both the fixed STS expiry and conservative CI/script deadlines."""
    if (now.tzinfo is None or expiration.tzinfo is None or not isinstance(required_seconds, int)
            or isinstance(required_seconds, bool) or required_seconds <= 0
            or not isinstance(margin_seconds, int) or isinstance(margin_seconds, bool) or margin_seconds <= 0):
        raise OidcError("invalid budget")
    started = _timestamp(env.get("CI_JOB_STARTED_AT", ""))
    try:
        timeout = int(env.get("CI_JOB_TIMEOUT", ""))
    except (ValueError, TypeError):
        raise OidcError("missing job timeout") from None
    if timeout <= 0 or started > now + timedelta(seconds=margin_seconds):
        raise OidcError("invalid job deadline")
    deadlines = [expiration.astimezone(timezone.utc), started + timedelta(seconds=timeout)]
    if token_deadline is not None:
        if token_deadline.tzinfo is None:
            raise OidcError("invalid token deadline")
        # The signed token expiry is a conservative upper bound, not the
        # actual expiration of credentials already issued by STS.
        deadlines.append(token_deadline.astimezone(timezone.utc))
    if env.get("RUNNER_SCRIPT_TIMEOUT"):
        # Actual script start is at or after job start; this is conservative.
        deadlines.append(started + timedelta(seconds=_duration(env["RUNNER_SCRIPT_TIMEOUT"])))
    if min(deadlines) < now.astimezone(timezone.utc) + timedelta(seconds=required_seconds + margin_seconds):
        raise OidcError("insufficient remaining time")


def ensure_session_budget(env: dict[str, str], session: FixedSession, required_seconds: int,
                          now: datetime, *, margin_seconds: int) -> None:
    """Recheck a verified session without accidentally omitting either deadline."""
    if (not isinstance(session.expiration, datetime) or session.expiration.tzinfo is None
            or not isinstance(session.token_deadline, datetime) or session.token_deadline.tzinfo is None):
        raise OidcError("invalid session deadlines")
    ensure_budget(env, session.expiration, required_seconds, now,
                  margin_seconds=margin_seconds, token_deadline=session.token_deadline)


def ensure_child_budget(env: dict[str, str], required_seconds: int,
                        now: datetime, *, margin_seconds: int) -> None:
    """Recheck propagated deadlines, including in a sanitized WSL child."""
    try:
        expiration = _timestamp(env["RX_OIDC_EXPIRATION_UTC"])
        token_deadline = _timestamp(env["RX_OIDC_TOKEN_DEADLINE_UTC"])
    except KeyError:
        raise OidcError("missing child deadlines") from None
    ensure_budget(env, expiration, required_seconds, now,
                  margin_seconds=margin_seconds, token_deadline=token_deadline)


@contextmanager
def _without_ambient_aws():
    """Do not read ambient profiles or endpoints; call before starting threads."""
    saved = {k: v for k, v in os.environ.items()
             if k.upper().startswith("AWS_") or k.upper() in {"BOTO_CONFIG", "BOTO_PATH"}}
    try:
        for name in list(os.environ):
            if name.upper().startswith("AWS_") or name.upper() in {"BOTO_CONFIG", "BOTO_PATH"}:
                os.environ.pop(name)
        os.environ.update(AWS_CONFIG_FILE=os.devnull, AWS_SHARED_CREDENTIALS_FILE=os.devnull,
                          BOTO_CONFIG=os.devnull, AWS_EC2_METADATA_DISABLED="true")
        yield
    finally:
        for name in list(os.environ):
            if name.upper().startswith("AWS_") or name.upper() in {"BOTO_CONFIG", "BOTO_PATH"}:
                os.environ.pop(name)
        os.environ.update(saved)


@contextmanager
def quiet_aws_logging():
    """Suppress SDK diagnostics while handling tokens; use before starting threads."""
    previous = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        yield
    finally:
        logging.disable(previous)


def obtain_session(env: dict[str, str], expected: ExpectedIdentity, *, required_seconds: int,
                   margin_seconds: int, duration_seconds: int, now: datetime | None = None) -> FixedSession:
    """Exchange exactly one JWT, check caller identity and return frozen keys.

    The caller owns `env` and must remove the JWT before launching any child.
    This function does not log SDK errors, JWTs, credentials or caller ARNs.
    """
    real_clock = now is None
    now = datetime.now(timezone.utc) if real_clock else now
    if (not isinstance(duration_seconds, int) or isinstance(duration_seconds, bool)
            or not 900 <= duration_seconds <= IDT_SESSION_SECONDS):
        raise OidcError("invalid session duration")
    token = env.get(TOKEN_ENV, "")
    name = validate_context(env, expected, token, now)
    try:
        token_deadline = datetime.fromtimestamp(_claims(token)["exp"], tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise OidcError("invalid token deadline") from None
    # Fail before STS when the job budget is already insufficient.
    ensure_budget(env, now + timedelta(seconds=duration_seconds), required_seconds, now,
                  margin_seconds=margin_seconds, token_deadline=token_deadline)
    try:
        from botocore import UNSIGNED
        from botocore.config import Config
        from botocore.httpsession import DEFAULT_CA_BUNDLE
        import botocore.session
        common = dict(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1},
                      proxies={}, ignore_configured_endpoint_urls=True)
        with _without_ambient_aws(), quiet_aws_logging():
            sdk = botocore.session.Session()
            sdk.set_config_variable("config_file", os.devnull)
            sdk.set_config_variable("credentials_file", os.devnull)
            sts = sdk.create_client("sts", region_name=REGION,
                                    endpoint_url=f"https://sts.{REGION}.amazonaws.com",
                                    verify=DEFAULT_CA_BUNDLE,
                                    config=Config(signature_version=UNSIGNED, **common))
            result = sts.assume_role_with_web_identity(RoleArn=expected.role_arn, RoleSessionName=name,
                                                       WebIdentityToken=token, DurationSeconds=duration_seconds)
            subject = f"project_path:{expected.project_path}:ref_type:{expected.ref_type}:ref:{expected.ref}"
            if result.get("SubjectFromWebIdentityToken") != subject or result.get("Audience") != AUDIENCE:
                raise OidcError("STS token identity mismatch")
            cred = result["Credentials"]
            session = FixedSession(cred["AccessKeyId"], cred["SecretAccessKey"],
                                   cred["SessionToken"], cred["Expiration"], token_deadline)
            if any(not isinstance(value, str) or not value for value in
                   (session.access_key, session.secret_key, session.session_token)):
                raise OidcError("invalid temporary credentials")
            signed = sdk.create_client("sts", region_name=REGION,
                                       endpoint_url=f"https://sts.{REGION}.amazonaws.com",
                                       verify=DEFAULT_CA_BUNDLE,
                                       config=Config(**common), aws_access_key_id=session.access_key,
                                       aws_secret_access_key=session.secret_key,
                                       aws_session_token=session.session_token)
            identity = signed.get_caller_identity()
        role_name = expected.role_arn.rsplit("/", 1)[-1]
        if identity.get("Account") != expected.account or identity.get("Arn") != (
                f"arn:aws:sts::{expected.account}:assumed-role/{role_name}/{name}"):
            raise OidcError("caller identity mismatch")
        # Re-read the clock after the network call in production.
        checked_at = datetime.now(timezone.utc) if real_clock else now
        ensure_session_budget(env, session, required_seconds, checked_at, margin_seconds=margin_seconds)
        return session
    except OidcError:
        raise
    except Exception:
        raise OidcError("OIDC session unavailable") from None


_BASE_ENV = {"PATH", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "TEMP", "TMP", "TMPDIR",
             "HOME", "USERPROFILE", "PATHEXT", "COMSPEC", "LANG", "LC_ALL", "WSLENV",
             "CI_JOB_ID", "CI_JOB_STARTED_AT", "CI_JOB_TIMEOUT", "CI_PROJECT_ID", "CI_PROJECT_PATH",
             "CI_COMMIT_SHA", "CI_COMMIT_BRANCH", "CI_COMMIT_TAG", "CI_COMMIT_REF_PROTECTED",
             "CI_PIPELINE_SOURCE", "RUNNER_SCRIPT_TIMEOUT"}
_DEVICE_NETWORK_ENV = {"AWS_IOT_CELLULAR_APN_CK_RX65N_01", "AWS_IOT_CELLULAR_APN_USER_CK_RX65N_01",
                       "AWS_IOT_CELLULAR_APN_PASS_CK_RX65N_01", "AWS_IOT_CELLULAR_APN_AUTH_CK_RX65N_01"}


def child_environment(env: dict[str, str], session: FixedSession, *, allow_names=()) -> dict[str, str]:
    """Pass fixed STS keys and explicitly allowed non-AWS inputs, never the JWT."""
    if (not isinstance(session.expiration, datetime) or session.expiration.tzinfo is None
            or not isinstance(session.token_deadline, datetime) or session.token_deadline.tzinfo is None):
        raise OidcError("invalid session deadlines")
    secret_names = {TOKEN_ENV, "RX_IOT_OIDC_TOKEN", "RX_IOT_OIDC_WRONG_AUDIENCE_TOKEN",
                    "CI_JOB_JWT", "CI_JOB_JWT_V2"}
    allowed = _BASE_ENV | {name.upper() for name in allow_names}
    if allowed & secret_names or any(name.startswith("AWS_") and name not in _DEVICE_NETWORK_ENV for name in allowed):
        raise OidcError("credential inputs cannot be allowed")
    clean = {k: v for k, v in env.items() if k.upper() in allowed
             and k.upper() not in {"BOTO_CONFIG", "BOTO_PATH", *secret_names}}
    clean.update(AWS_ACCESS_KEY_ID=session.access_key, AWS_SECRET_ACCESS_KEY=session.secret_key,
                 AWS_SESSION_TOKEN=session.session_token, AWS_CONFIG_FILE=os.devnull,
                 AWS_SHARED_CREDENTIALS_FILE=os.devnull, BOTO_CONFIG=os.devnull,
                 AWS_EC2_METADATA_DISABLED="true", AWS_DEFAULT_REGION=REGION, AWS_REGION=REGION)
    clean["RX_OIDC_EXPIRATION_UTC"] = session.expiration.astimezone(timezone.utc).isoformat()
    clean["RX_OIDC_TOKEN_DEADLINE_UTC"] = session.token_deadline.astimezone(timezone.utc).isoformat()
    if "WSLENV" in clean:
        clean["WSLENV"] = ":".join(part for part in clean["WSLENV"].split(":")
                                   if part and not part.split("/", 1)[0].upper().startswith("AWS_")
                                   and part.split("/", 1)[0].upper() not in secret_names)
    return clean


def wsl_bridge_environment(env: dict[str, str], session: FixedSession, *, allow_names=()) -> dict[str, str]:
    """Prepare Windows->WSL propagation; Linux must sanitize before AWS use."""
    clean = child_environment(env, session, allow_names=allow_names)
    names = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
             "AWS_EC2_METADATA_DISABLED", "AWS_DEFAULT_REGION", "AWS_REGION", "RX_OIDC_EXPIRATION_UTC",
             "RX_OIDC_TOKEN_DEADLINE_UTC",
             "CI_JOB_STARTED_AT", "CI_JOB_TIMEOUT", "RUNNER_SCRIPT_TIMEOUT")
    explicit = tuple(name.upper() for name in allow_names if name.upper() in clean)
    names = tuple(dict.fromkeys(names + explicit))
    existing = [part for part in clean.get("WSLENV", "").split(":")
                if part and part.split("/", 1)[0].upper() not in names]
    clean["WSLENV"] = ":".join(existing + [name + "/u" for name in names if name in clean])
    return clean


def wsl_child_environment(env: dict[str, str], *, allow_names=()) -> dict[str, str]:
    """Rebuild a Linux child environment before it can resolve AWS credentials."""
    try:
        expiration = _timestamp(env["RX_OIDC_EXPIRATION_UTC"])
        token_deadline = _timestamp(env["RX_OIDC_TOKEN_DEADLINE_UTC"])
        values = [env[name] for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")]
        if any(not value for value in values):
            raise ValueError
    except (KeyError, ValueError):
        raise OidcError("missing WSL session") from None
    session = FixedSession(*values, expiration, token_deadline)
    clean = child_environment(env, session, allow_names=allow_names)
    # Windows NUL is not the Linux null device. Do not propagate host paths.
    clean.update(AWS_CONFIG_FILE="/dev/null", AWS_SHARED_CREDENTIALS_FILE="/dev/null", BOTO_CONFIG="/dev/null")
    return clean

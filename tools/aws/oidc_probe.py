"""Project-38 OIDC-only read probe; never run the firmware or credential flows."""
from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import sys

PROJECT = "oss/import/github/renesas/iot-reference-rx"
ROLE = "saffti-iot-reference-rx-oidc-probe"
REGION = "ap-northeast-1"


class ProbeFailure(Exception):
    """Do not carry SDK exception messages or request data across the log boundary."""


def configuration(environ, denied_ref=False):
    if any(re.fullmatch(r"(?:t|true|\+?0*1)", environ.get(key, ""), re.IGNORECASE)
           for key in ("CI_DEBUG_TRACE", "CI_DEBUG_SERVICES")):
        raise ProbeFailure()
    branch = environ.get("CI_COMMIT_BRANCH", "")
    if (environ.get("CI_PROJECT_ID") != "38" or environ.get("CI_PROJECT_PATH") != PROJECT
            or environ.get("CI_PIPELINE_SOURCE") not in ("api", "web")
            or environ.get("CI_COMMIT_TAG")
            or not re.fullmatch(r"[0-9]+", environ.get("CI_JOB_ID", ""))
            or (not denied_ref and branch != "main")
            or (not denied_ref and environ.get("CI_COMMIT_REF_PROTECTED") != "true")
            or (denied_ref and not re.fullmatch(r"(?:(?:codex|claude)/)?[0-9]+-aws-oidc-[a-z0-9-]+", branch))):
        raise ProbeFailure()
    account = environ.get("RX_IOT_OIDC_ACCOUNT_ID", "")
    role = environ.get("RX_IOT_OIDC_ROLE_ARN", "")
    if not re.fullmatch(r"[0-9]{12}", account) or role != f"arn:aws:iam::{account}:role/{ROLE}":
        raise ProbeFailure()
    return account, role, "gitlab38-" + environ["CI_JOB_ID"]


def isolated_session():
    """Remove every ambient AWS provider/configuration input before SDK creation."""
    for name in list(os.environ):
        if name.upper().startswith("AWS_") or name.upper() in ("BOTO_CONFIG", "BOTO_PATH"):
            os.environ.pop(name)
    # Never load runner profiles, credential_process, SSO, container or EC2 keys.
    os.environ.update(AWS_CONFIG_FILE=os.devnull, AWS_SHARED_CREDENTIALS_FILE=os.devnull,
                      BOTO_CONFIG=os.devnull, AWS_EC2_METADATA_DISABLED="true")
    import botocore.session
    session = botocore.session.Session()
    session.set_config_variable("config_file", os.devnull)
    session.set_config_variable("credentials_file", os.devnull)
    return session


def run_probe(session, account, role, name, token, wrong_audience, denied_ref=False):
    from botocore import UNSIGNED
    from botocore.config import Config
    from botocore.exceptions import ClientError
    from botocore.httpsession import DEFAULT_CA_BUNDLE
    common = dict(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1},
                  proxies={}, ignore_configured_endpoint_urls=True)
    # UNSIGNED prevents credential-provider resolution for the STS bootstrap.
    sts = session.create_client("sts", region_name=REGION,
                                endpoint_url=f"https://sts.{REGION}.amazonaws.com",
                                verify=DEFAULT_CA_BUNDLE,
                                config=Config(signature_version=UNSIGNED, **common))

    def assume(value):
        if not value or len(value) > 32768:
            raise ProbeFailure()
        return sts.assume_role_with_web_identity(RoleArn=role, RoleSessionName=name,
                                                 WebIdentityToken=value, DurationSeconds=900)

    def require_denied(value, error_code):
        try:
            assume(value)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == error_code:
                return
        raise ProbeFailure()

    target = hashlib.sha256((account + "|" + role).encode("ascii")).hexdigest()
    if denied_ref:
        require_denied(token, "AccessDenied")
        # AccessDenied alone does not identify which trust condition failed.
        return {"sts_access_denied": True, "configured_target_sha256": target}
    require_denied(wrong_audience, "InvalidIdentityToken")
    credentials = assume(token)["Credentials"]
    # All authenticated calls receive the returned STS keys explicitly. No
    # default credential chain, exported environment or child process is used.
    key_args = {"aws_access_key_id": credentials["AccessKeyId"],
                "aws_secret_access_key": credentials["SecretAccessKey"],
                "aws_session_token": credentials["SessionToken"]}
    signed_sts = session.create_client("sts", region_name=REGION,
                                       endpoint_url=f"https://sts.{REGION}.amazonaws.com",
                                       verify=DEFAULT_CA_BUNDLE,
                                       config=Config(**common), **key_args)
    identity = signed_sts.get_caller_identity()
    if (identity.get("Account") != account
            or identity.get("Arn") != f"arn:aws:sts::{account}:assumed-role/{ROLE}/{name}"):
        raise ProbeFailure()
    iot = session.create_client("iot", region_name=REGION,
                                endpoint_url=f"https://iot.{REGION}.amazonaws.com",
                                verify=DEFAULT_CA_BUNDLE,
                                config=Config(**common), **key_args)
    endpoint = iot.describe_endpoint(endpointType="iot:Data-ATS")
    if not re.fullmatch(r"[a-z0-9-]+-ats\.iot\.ap-northeast-1\.amazonaws\.com",
                        endpoint.get("endpointAddress", "")):
        raise ProbeFailure()
    return {"caller_is_expected_assumed_role": True, "wrong_audience_denied": True,
            "iot_endpoint_read": True, "configured_target_sha256": target}


def main():
    # Suppress SDK diagnostic handlers even when the host configured debug logs.
    logging.disable(logging.CRITICAL)
    try:
        if sys.argv[1:] not in ([], ["--expect-denied-ref"]):
            raise ProbeFailure()
        denied_ref = sys.argv[1:] == ["--expect-denied-ref"]
        account, role, name = configuration(os.environ, denied_ref)
        token = os.environ.pop("RX_IOT_OIDC_TOKEN", "")
        wrong = os.environ.pop("RX_IOT_OIDC_WRONG_AUDIENCE_TOKEN", "")
        result = run_probe(isolated_session(), account, role, name, token, wrong, denied_ref)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        # Neither SDK exceptions nor tokens/keys/PEMs enter stdout or stderr.
        print('{"oidc_probe_failed": true}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

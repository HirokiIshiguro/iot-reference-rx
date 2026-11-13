"""Run one job-local OIDC subject authorization check without AWS writes."""
import os
import re

import botocore.session
from botocore.config import Config
from botocore.exceptions import ClientError

from tools.aws.oidc_session import ExpectedIdentity, REGION, TOKEN_ENV, obtain_session, quiet_aws_logging

PROJECT = "oss/import/github/renesas/iot-reference-rx"
ALLOW = "202-oidc-rx72n-read-allow"
DENY = "202-oidc-rx72n-read-deny"


def main():
    env = dict(os.environ)
    os.environ.pop(TOKEN_ENV, None)
    branch = env.get("CI_COMMIT_BRANCH")
    if branch not in (ALLOW, DENY):
        raise ValueError("unexpected ref")
    role = env.get("AWS_ROLE_ARN", "")
    match = re.fullmatch(r"arn:aws:iam::([0-9]{12}):role/saffti-oss-gitlab-oidc", role)
    if not match:
        raise ValueError("unexpected role")
    account = match[1]
    expected = ExpectedIdentity("38", PROJECT, account, role, "branch", branch,
                                env["CI_COMMIT_SHA"], ("api",), 26)
    sts = obtain_session(env, expected, required_seconds=30, margin_seconds=15, duration_seconds=900)
    env.pop(TOKEN_ENV, None)
    config = Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1},
                    proxies={}, ignore_configured_endpoint_urls=True)
    sdk = botocore.session.Session()
    sdk.set_config_variable("config_file", os.devnull)
    sdk.set_config_variable("credentials_file", os.devnull)
    with quiet_aws_logging():
        iot = sdk.create_client("iot", region_name=REGION, endpoint_url=f"https://iot.{REGION}.amazonaws.com",
                                config=config, aws_access_key_id=sts.access_key, aws_secret_access_key=sts.secret_key,
                                aws_session_token=sts.session_token)
        try:
            result = iot.describe_thing(thingName="rx72n-02")
        except ClientError as error:
            if branch == DENY and error.response["Error"]["Code"] in ("AccessDeniedException", "UnauthorizedException"):
                print("oidc_caller_verified=true iot_describe_thing=denied_as_expected")
                return 0
            print("oidc_caller_verified=true iot_describe_thing=unexpected_error")
            return 1
    if branch == ALLOW and result.get("thingArn") == f"arn:aws:iot:{REGION}:{account}:thing/rx72n-02":
        print("oidc_caller_verified=true iot_describe_thing=allowed_as_expected")
        return 0
    print("oidc_caller_verified=true iot_describe_thing=unexpected_result")
    return 1


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        print("oidc_read_proof_failed_before_verified_result=true")
        code = 1
    raise SystemExit(code)

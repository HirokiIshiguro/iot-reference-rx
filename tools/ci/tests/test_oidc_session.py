"""Offline checks for OIDC-only session creation and the fixed-job budget."""
import base64
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
from unittest.mock import patch

import botocore.session

from tools.aws import oidc_session as oidc

NOW = datetime(2026, 11, 8, 3, 0, tzinfo=timezone.utc)
ACCOUNT = "123456789012"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/test-oidc-role"
SHA = "a" * 40
EXPECTED = oidc.ExpectedIdentity("38", "oss/example/project", ACCOUNT, ROLE,
                                 "branch", "main", SHA, ("push", "schedule"))
ACCESS = "ASIA" + "X" * 16
SECRET = "unit-secret-" + "x" * 30
SESSION = "unit-session-token"


def jwt(**changes):
    claims = {"iss": oidc.ISSUER, "aud": oidc.AUDIENCE,
              "sub": "project_path:oss/example/project:ref_type:branch:ref:main",
              "project_id": "38", "job_id": "17", "pipeline_source": "push",
              "ref_protected": "true", "ref_type": "branch", "ref": "main", "sha": SHA,
              "exp": int((NOW + timedelta(hours=3)).timestamp())}
    claims.update(changes)
    raw = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "header." + raw + ".signature"


def environment():
    return {"CI_PROJECT_ID": "38", "CI_PROJECT_PATH": "oss/example/project",
            "CI_COMMIT_REF_PROTECTED": "true", "CI_COMMIT_BRANCH": "main",
            "CI_COMMIT_SHA": SHA, "CI_PIPELINE_SOURCE": "push",
            "CI_JOB_ID": "17", "CI_JOB_STARTED_AT": NOW.isoformat(),
            "CI_JOB_TIMEOUT": "10800", oidc.TOKEN_ENV: jwt(),
            "AWS_PROFILE": "must-not-be-used", "AWS_ACCESS_KEY_ID": "old-key",
            "AWS_SECRET_ACCESS_KEY": "old-secret", "AWS_SESSION_TOKEN": "old-token",
            "AWS_ENDPOINT_URL": "https://invalid.example", "BOTO_PATH": "old-file",
            "WSLENV": "KEEP/u:RX_OIDC_ID_TOKEN/u:AWS_PROFILE/u:AWS_SESSION_TOKEN/u"}


class FakeSts:
    def __init__(self, *, account=ACCOUNT, role="test-oidc-role", expiration=None, fail=False, duration=10800,
                 subject="project_path:oss/example/project:ref_type:branch:ref:main", audience=oidc.AUDIENCE):
        self.account, self.role, self.fail = account, role, fail
        self.duration = duration
        self.subject, self.audience = subject, audience
        self.expiration = expiration or (NOW + timedelta(hours=3))
        self.assume_calls = 0

    def assume_role_with_web_identity(self, **kwargs):
        self.assume_calls += 1
        assert kwargs["DurationSeconds"] == self.duration
        assert kwargs["WebIdentityToken"] == jwt()
        assert os.environ.get("AWS_CONFIG_FILE") == os.devnull
        assert "AWS_PROFILE" not in os.environ
        if self.fail:
            raise RuntimeError("untrusted diagnostic containing " + SECRET)
        return {"Credentials": {"AccessKeyId": ACCESS, "SecretAccessKey": SECRET,
                                "SessionToken": SESSION, "Expiration": self.expiration},
                "SubjectFromWebIdentityToken": self.subject, "Audience": self.audience}

    def get_caller_identity(self):
        return {"Account": self.account,
                "Arn": f"arn:aws:sts::{self.account}:assumed-role/{self.role}/gitlab38-17"}


class FakeSdk:
    def __init__(self, fake):
        self.fake = fake
        self.clients = []

    def set_config_variable(self, name, value):
        assert value == os.devnull

    def create_client(self, service, **kwargs):
        assert service == "sts"
        assert kwargs["endpoint_url"] == "https://sts.ap-northeast-1.amazonaws.com"
        assert kwargs["config"].proxies == {}
        assert kwargs["verify"]
        self.clients.append(kwargs)
        return self.fake


class OidcSessionTests(unittest.TestCase):
    def issue(self, env=None, fake=None, required=6489, margin=60, duration=10800):
        env = environment() if env is None else env
        fake = FakeSts() if fake is None else fake
        sdk = FakeSdk(fake)
        with patch("botocore.session.Session", return_value=sdk):
            result = oidc.obtain_session(env, EXPECTED, required_seconds=required,
                                         margin_seconds=margin, duration_seconds=duration, now=NOW)
        return result, fake, sdk

    def test_one_oidc_exchange_and_explicit_caller_identity(self):
        with patch.dict(os.environ, {"AWS_PROFILE": "host-admin", "KEEP": "yes"}, clear=True):
            session, fake, sdk = self.issue()
            self.assertEqual(1, fake.assume_calls)
            self.assertEqual(2, len(sdk.clients))
            self.assertNotIn("aws_access_key_id", sdk.clients[0])
            self.assertEqual(ACCESS, sdk.clients[1]["aws_access_key_id"])
            self.assertEqual("host-admin", os.environ["AWS_PROFILE"])
            self.assertEqual("yes", os.environ["KEEP"])
            self.assertEqual(NOW + timedelta(hours=3), session.expiration)
            self.assertNotIn(SECRET, repr(session))

    def test_child_cli_sdk_and_wsl_receive_only_fixed_sts_credentials(self):
        session, _, _ = self.issue()
        env = oidc.child_environment(environment(), session, allow_names=("WSLENV",))
        self.assertEqual(ACCESS, env["AWS_ACCESS_KEY_ID"])
        self.assertEqual(SECRET, env["AWS_SECRET_ACCESS_KEY"])
        self.assertEqual(SESSION, env["AWS_SESSION_TOKEN"])
        self.assertEqual(os.devnull, env["AWS_SHARED_CREDENTIALS_FILE"])
        self.assertEqual("true", env["AWS_EC2_METADATA_DISABLED"])
        self.assertEqual("KEEP/u", env["WSLENV"])
        for key in (oidc.TOKEN_ENV, "AWS_PROFILE", "AWS_ENDPOINT_URL", "BOTO_PATH"):
            self.assertNotIn(key, env)
        with patch.dict(os.environ, env, clear=True):
            credentials = botocore.session.Session().get_credentials()
            self.assertEqual("env", credentials.method)
            frozen = credentials.get_frozen_credentials()
            self.assertEqual((ACCESS, SECRET, SESSION),
                             (frozen.access_key, frozen.secret_key, frozen.token))

    def test_context_and_jwt_rejections_happen_before_sts(self):
        examples = [("CI_PROJECT_ID", "221"), ("CI_PROJECT_PATH", "fork/project"),
                    ("CI_COMMIT_REF_PROTECTED", "false"), ("CI_COMMIT_BRANCH", "other"),
                           ("CI_DEBUG_TRACE", "+01"), ("CI_DEBUG_SERVICES", "true"),
                           ("CI_COMMIT_SHA", "b" * 40), ("CI_JOB_ID", "bad")]
        for key, value in examples:
            fake = FakeSts()
            with self.subTest(key=key), self.assertRaises(oidc.OidcError):
                self.issue({**environment(), key: value}, fake)
            self.assertEqual(0, fake.assume_calls)
        for token in ("", "bad", "a" * 32769, jwt(aud="wrong"), jwt(aud=[oidc.AUDIENCE]),
                      jwt(sub="project_path:other:ref_type:branch:ref:main"),
                      jwt(exp=int(NOW.timestamp()) + 10),
                      jwt(iss="https://invalid.example"), jwt(ref_protected="false"),
                      jwt(project_id="221"), jwt(job_id="18"), jwt(sha="b" * 40),
                      jwt(pipeline_source="api")):
            fake = FakeSts()
            with self.subTest(token=token[:3]), self.assertRaises(oidc.OidcError):
                self.issue({**environment(), oidc.TOKEN_ENV: token}, fake)
            self.assertEqual(0, fake.assume_calls)

    def test_only_explicit_tag_or_integration_ref_is_accepted(self):
        expected = oidc.ExpectedIdentity("38", "oss/example/project", ACCOUNT, ROLE,
                                         "tag", "release-1", SHA, ("push",))
        token = jwt(sub="project_path:oss/example/project:ref_type:tag:ref:release-1",
                    ref="release-1", ref_type="tag")
        env = {**environment(), "CI_COMMIT_BRANCH": "", "CI_COMMIT_TAG": "release-1"}
        self.assertEqual("gitlab38-17", oidc.validate_context(env, expected, token, NOW))
        with self.assertRaises(oidc.OidcError):
            oidc.validate_context({**env, "CI_COMMIT_TAG": "release-2"}, expected, token, NOW)
        with self.assertRaises(oidc.OidcError):
            oidc.validate_context({**environment(), "CI_PIPELINE_SOURCE": "merge_request_event"},
                                  EXPECTED, jwt(pipeline_source="merge_request_event"), NOW)

    def test_bad_identity_or_insufficient_sts_expiry_fails(self):
        for fake in (FakeSts(account="999999999999"), FakeSts(role="other"),
                     FakeSts(subject="wrong"), FakeSts(audience="wrong"),
                     FakeSts(expiration=NOW + timedelta(seconds=6489))):
            with self.subTest(fake=fake), self.assertRaises(oidc.OidcError):
                self.issue(fake=fake)

    def test_job_and_script_deadlines_are_checked_before_exchange(self):
        for extra in ({"CI_JOB_TIMEOUT": "6000"}, {"CI_JOB_TIMEOUT": ""},
                      {"RUNNER_SCRIPT_TIMEOUT": "1h30m"}, {"RUNNER_SCRIPT_TIMEOUT": "invalid"},
                      {"RUNNER_SCRIPT_TIMEOUT": "1h1h"}):
            fake = FakeSts()
            with self.subTest(extra=extra), self.assertRaises(oidc.OidcError):
                self.issue({**environment(), **extra}, fake)
            self.assertEqual(0, fake.assume_calls)
        self.issue({**environment(), "RUNNER_SCRIPT_TIMEOUT": "2h"})

    def test_short_token_deadline_is_conservative_even_when_job_timeout_is_long(self):
        token = jwt(exp=int((NOW + timedelta(seconds=6500)).timestamp()))
        fake = FakeSts()
        with self.assertRaises(oidc.OidcError):
            self.issue({**environment(), oidc.TOKEN_ENV: token}, fake=fake, required=6489, margin=60)
        self.assertEqual(0, fake.assume_calls)

    def test_sdk_errors_do_not_expose_credentials(self):
        with self.assertRaises(oidc.OidcError) as caught:
            self.issue(fake=FakeSts(fail=True))
        self.assertNotIn(SECRET, str(caught.exception))

    def test_short_jobs_can_use_shorter_sessions_and_invalid_durations_fail(self):
        short = FakeSts(duration=900, expiration=NOW + timedelta(seconds=900))
        self.issue(fake=short, required=600, margin=60, duration=900)
        self.assertEqual(1, short.assume_calls)
        for duration in (0, 899, 10801, True):
            fake = FakeSts()
            with self.subTest(duration=duration), self.assertRaises(oidc.OidcError):
                self.issue(fake=fake, required=600, duration=duration)
            self.assertEqual(0, fake.assume_calls)

    def test_wsl_bridge_requires_linux_environment_rebuild(self):
        session, _, _ = self.issue()
        bridge = oidc.wsl_bridge_environment(environment(), session)
        for name in ("AWS_ACCESS_KEY_ID/u", "AWS_SECRET_ACCESS_KEY/u", "AWS_SESSION_TOKEN/u"):
            self.assertIn(name, bridge["WSLENV"].split(":"))
        self.assertNotIn("RX_OIDC_ID_TOKEN/u", bridge["WSLENV"])
        # Model a WSL host with an unrelated ambient profile and AWS endpoint.
        linux = oidc.wsl_child_environment({**bridge, "AWS_PROFILE": "host-admin",
                                             "AWS_ENDPOINT_URL": "https://invalid.example"})
        self.assertEqual("/dev/null", linux["AWS_SHARED_CREDENTIALS_FILE"])
        self.assertEqual("/dev/null", linux["AWS_CONFIG_FILE"])
        self.assertEqual(SESSION, linux["AWS_SESSION_TOKEN"])
        self.assertNotIn("AWS_PROFILE", linux)
        self.assertNotIn("AWS_ENDPOINT_URL", linux)
        with self.assertRaises(oidc.OidcError):
            oidc.wsl_child_environment({**linux, "AWS_SESSION_TOKEN": ""})

    def test_device_apn_is_explicitly_allowed_without_allowing_aws_profile(self):
        session, _, _ = self.issue()
        source = {**environment(), "AWS_IOT_CELLULAR_APN_CK_RX65N_01": "test-apn"}
        name = "AWS_IOT_CELLULAR_APN_CK_RX65N_01"
        bridge = oidc.wsl_bridge_environment(source, session, allow_names=(name,))
        self.assertEqual("test-apn", bridge[name])
        self.assertIn(name + "/u", bridge["WSLENV"].split(":"))
        self.assertEqual("test-apn", oidc.wsl_child_environment(bridge, allow_names=(name,))[name])
        self.assertNotIn(name, oidc.child_environment(source, session))
        with self.assertRaises(oidc.OidcError):
            oidc.child_environment(source, session, allow_names=("AWS_PROFILE",))


if __name__ == "__main__":
    unittest.main()

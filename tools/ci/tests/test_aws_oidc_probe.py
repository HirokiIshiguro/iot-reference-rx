"""Offline security boundaries for the independent, read-only OIDC probe."""
import contextlib
import hashlib
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

from botocore import UNSIGNED
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from tools.aws import oidc_probe as probe

ACCOUNT = "123456789012"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{probe.ROLE}"
NAME = "gitlab38-321"
TOKEN = "fixture-jwt-never-print"
WRONG = "fixture-wrong-aud-never-print"
KEY = "ASIA" + "X" * 16
SECRET = "fixture-secret-" + "X" * 30
SESSION = "fixture-session-never-print"


def environment(branch="main"):
    return {"CI_PROJECT_ID": "38", "CI_PROJECT_PATH": probe.PROJECT,
            "CI_COMMIT_BRANCH": branch, "CI_COMMIT_REF_PROTECTED": "true",
            "CI_PIPELINE_SOURCE": "api", "CI_JOB_ID": "321",
            "RX_IOT_OIDC_ACCOUNT_ID": ACCOUNT, "RX_IOT_OIDC_ROLE_ARN": ROLE_ARN,
            "RX_IOT_OIDC_TOKEN": TOKEN, "RX_IOT_OIDC_WRONG_AUDIENCE_TOKEN": WRONG}


class ProbeTests(unittest.TestCase):
    def test_context_ref_account_and_role_are_checked_before_sdk(self):
        self.assertEqual((ACCOUNT, ROLE_ARN, NAME), probe.configuration(environment()))
        self.assertEqual((ACCOUNT, ROLE_ARN, NAME),
                         probe.configuration(environment("200-aws-oidc-probe"), True))
        self.assertEqual((ACCOUNT, ROLE_ARN, NAME),
                         probe.configuration(environment("codex/999-aws-oidc-check"), True))
        for key, value in (("CI_PROJECT_ID", "257"), ("CI_PROJECT_PATH", "fork/app"),
                           ("CI_COMMIT_BRANCH", "other"), ("CI_PIPELINE_SOURCE", "push"),
                           ("CI_COMMIT_REF_PROTECTED", "false"),
                           ("CI_COMMIT_TAG", "v1"), ("CI_JOB_ID", "invalid"),
                           ("RX_IOT_OIDC_ACCOUNT_ID", "999999999999"),
                           ("RX_IOT_OIDC_ROLE_ARN", ROLE_ARN + "-other")):
            with self.subTest(key=key), self.assertRaises(probe.ProbeFailure):
                probe.configuration({**environment(), key: value})
        with self.assertRaises(probe.ProbeFailure):
            probe.configuration(environment(), True)

    def test_debug_boolean_aliases_fail_before_sdk_or_token_use(self):
        for flag in ("CI_DEBUG_TRACE", "CI_DEBUG_SERVICES"):
            for value in ("1", "t", "T", "TRUE", "true", "True", "TrUe", "+1", "01", "+0001"):
                out = io.StringIO()
                with self.subTest(flag=flag, value=value), \
                        patch.dict(os.environ, {**environment(), flag:value}, clear=True), \
                        patch.object(sys, "argv", ["probe"]), \
                        patch.object(probe, "isolated_session") as factory, \
                        contextlib.redirect_stdout(out):
                    self.assertEqual(1, probe.main())
                    factory.assert_not_called()
                    self.assertEqual('{"oidc_probe_failed": true}\n', out.getvalue())

    def test_ambient_provider_inputs_are_removed_without_reading_files(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": KEY, "AWS_SECRET_ACCESS_KEY": SECRET,
                        "AWS_SESSION_TOKEN": SESSION, "AWS_PROFILE": "runner-admin",
                        "AWS_CONFIG_FILE": "forbidden-config", "AWS_SHARED_CREDENTIALS_FILE": "forbidden-keys",
                        "AWS_CONTAINER_CREDENTIALS_FULL_URI": "http://invalid.example",
                        "AWS_WEB_IDENTITY_TOKEN_FILE": "forbidden-token", "AWS_ROLE_ARN": ROLE_ARN,
                        "AWS_ENDPOINT_URL": "https://invalid.example", "AWS_CSM_ENABLED": "true",
                        "BOTO_PATH": "forbidden-boto-path", "KEEP": "ok"}, clear=True):
            session = probe.isolated_session()
            self.assertEqual(os.devnull, session.get_config_variable("config_file"))
            self.assertEqual(os.devnull, session.get_config_variable("credentials_file"))
            self.assertEqual({"AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE", "AWS_EC2_METADATA_DISABLED"},
                             {k for k in os.environ if k.startswith("AWS_")})
            self.assertEqual("ok", os.environ["KEEP"])
            self.assertNotIn("BOTO_PATH", os.environ)

    def exercise(self, *, account=ACCOUNT, identity_account=ACCOUNT, endpoint=None,
                 denied=False, wrong_error="InvalidIdentityToken", allow_wrong=False):
        with patch.dict(os.environ, {}, clear=True):
            session = probe.isolated_session()
            original = session.create_client
            calls, stubbers = [], []

            def client(service, **kwargs):
                self.assertEqual("ap-northeast-1", kwargs["region_name"])
                self.assertEqual(f"https://{service}.ap-northeast-1.amazonaws.com", kwargs["endpoint_url"])
                self.assertTrue(kwargs["config"].ignore_configured_endpoint_urls)
                self.assertEqual({}, kwargs["config"].proxies)
                from botocore.httpsession import DEFAULT_CA_BUNDLE
                self.assertEqual(DEFAULT_CA_BUNDLE, kwargs["verify"])
                calls.append((service, kwargs))
                result = original(service, **kwargs)
                stub = Stubber(result)
                assume_params = lambda token: dict(RoleArn=ROLE_ARN, RoleSessionName=NAME,
                                                    WebIdentityToken=token, DurationSeconds=900)
                response = {"Credentials": {"AccessKeyId": KEY, "SecretAccessKey": SECRET,
                            "SessionToken": SESSION, "Expiration": "2026-11-07T11:00:00Z"}}
                if service == "sts" and kwargs["config"].signature_version is UNSIGNED:
                    self.assertNotIn("aws_access_key_id", kwargs)
                    if denied:
                        stub.add_client_error("assume_role_with_web_identity", "AccessDenied",
                                              expected_params=assume_params(TOKEN))
                    else:
                        if allow_wrong:
                            stub.add_response("assume_role_with_web_identity", response, assume_params(WRONG))
                        else:
                            stub.add_client_error("assume_role_with_web_identity", wrong_error,
                                                  expected_params=assume_params(WRONG))
                            if wrong_error == "InvalidIdentityToken":
                                stub.add_response("assume_role_with_web_identity", response, assume_params(TOKEN))
                else:
                    self.assertEqual(KEY, kwargs["aws_access_key_id"])
                    self.assertEqual(SECRET, kwargs["aws_secret_access_key"])
                    self.assertEqual(SESSION, kwargs["aws_session_token"])
                    if service == "sts":
                        stub.add_response("get_caller_identity", {"Account": identity_account,
                            "Arn": f"arn:aws:sts::{identity_account}:assumed-role/{probe.ROLE}/{NAME}",
                            "UserId": "fixture"}, {})
                    elif service == "iot":
                        stub.add_response("describe_endpoint", {"endpointAddress": endpoint or
                            "fixture-ats.iot.ap-northeast-1.amazonaws.com"}, {"endpointType": "iot:Data-ATS"})
                    else:
                        self.fail("unexpected AWS service")
                stub.activate(); stubbers.append(stub)
                return result

            # A real botocore client must not ask for the ambient provider chain.
            with patch.object(session, "get_credentials", side_effect=AssertionError("ambient provider used")), \
                    patch.object(session, "create_client", side_effect=client):
                result = probe.run_probe(session, account, ROLE_ARN, NAME, TOKEN, WRONG, denied)
            for stub in stubbers:
                stub.assert_no_pending_responses()
                stub.deactivate()
            return result, calls

    def test_unsigned_bootstrap_and_only_explicit_sts_keys_for_reads(self):
        result, calls = self.exercise()
        self.assertTrue(all(result.values()))
        self.assertEqual(["sts", "sts", "iot"], [c[0] for c in calls])
        for secret in (TOKEN, WRONG, KEY, SECRET, SESSION):
            self.assertNotIn(secret, json.dumps(result))

    def test_untrusted_ref_requires_sts_denial_and_never_calls_iot(self):
        result, calls = self.exercise(denied=True)
        self.assertEqual({"sts_access_denied": True, "configured_target_sha256":
                          hashlib.sha256((ACCOUNT + "|" + ROLE_ARN).encode()).hexdigest()}, result)
        self.assertEqual(1, len(calls))

    def test_wrong_audience_must_be_rejected_for_the_expected_reason(self):
        for args in ({"allow_wrong": True}, {"wrong_error": "AccessDenied"}):
            with self.subTest(args=args), self.assertRaises(probe.ProbeFailure):
                self.exercise(**args)

    def test_wrong_account_and_unexpected_endpoint_fail_closed(self):
        for args in ({"identity_account": "999999999999"}, {"endpoint": "attacker.example"}):
            with self.subTest(args=args), self.assertRaises(probe.ProbeFailure):
                self.exercise(**args)

    def test_missing_token_never_reaches_sts(self):
        from unittest.mock import Mock
        with patch.dict(os.environ, {}, clear=True):
            session = probe.isolated_session()
            with patch.object(session, "create_client", return_value=Mock()) as factory:
                with self.assertRaises(probe.ProbeFailure):
                    probe.run_probe(session, ACCOUNT, ROLE_ARN, NAME, "", "")
                factory.return_value.assume_role_with_web_identity.assert_not_called()

    def test_main_logs_no_exception_data_or_credential_material(self):
        error = ClientError({"Error": {"Code": "fixture", "Message": TOKEN + SECRET + SESSION}}, "AssumeRoleWithWebIdentity")
        for failure in (error, ValueError(TOKEN), TimeoutError(SECRET)):
            out, err = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, environment(), clear=True), patch.object(sys, "argv", ["probe"]), \
                    patch.object(probe, "isolated_session", side_effect=failure), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(1, probe.main())
                self.assertNotIn("RX_IOT_OIDC_TOKEN", os.environ)
            self.assertEqual('{"oidc_probe_failed": true}\n', out.getvalue())
            self.assertEqual("", err.getvalue())


if __name__ == "__main__":
    unittest.main()

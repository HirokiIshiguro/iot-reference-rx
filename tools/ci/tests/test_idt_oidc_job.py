"""Offline IDT CI credential isolation and remaining-time checks."""
from datetime import datetime, timedelta, timezone
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import botocore.session

from tools.aws.oidc_session import FixedSession, OidcError
from tools.idt import oidc_job
from tools.idt import run_idt
from tools.idt.targets import get_target
from tools.aws.oidc_session import wsl_child_environment

NOW = datetime(2026, 11, 8, 3, tzinfo=timezone.utc)
ACCESS = "ASIA" + "X" * 16
SECRET = "synthetic-secret-only"
TOKEN = "synthetic-session-only"
SHA = "a" * 40


def environment():
    return {"CI": "true", "CI_PROJECT_ID": "38", "CI_PROJECT_PATH": oidc_job.PROJECT_PATH,
            "CI_COMMIT_REF_PROTECTED": "true", "CI_COMMIT_BRANCH": "main", "CI_COMMIT_SHA": SHA,
            "CI_PIPELINE_SOURCE": "schedule", "CI_JOB_ID": "17", "CI_JOB_STARTED_AT": NOW.isoformat(),
            "CI_JOB_TIMEOUT": "10800", "CI_RUNNER_ID": "3", "CI_PIPELINE_ID": "18", "CI_PROJECT_DIR": str(oidc_job.ROOT),
            "CI_JOB_TOKEN": "synthetic-job-token",
            "RUN_RX_IDT": "true", "IDT_SCOPE": "transport", "IDT_TARGET": "rx65n-bg96",
            "RX_OIDC_ACCOUNT_ID": "123456789012", "RX_OIDC_ROLE_ARN_IDT_TRANSPORT": "arn:aws:iam::123456789012:role/test",
            "RX_OIDC_ID_TOKEN": "synthetic-jwt", "AWS_PROFILE": "host-profile",
            "AWS_ENDPOINT_URL": "https://invalid.example", "AWS_ACCESS_KEY_ID": "host-old-key",
            "AWS_IOT_CELLULAR_APN_CK_RX65N_01": "synthetic-apn", "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "WSLENV": "RX_OIDC_ID_TOKEN/u:AWS_PROFILE/u"}


class IdtOidcJobTests(unittest.TestCase):
    def setUp(self):
        self.budget = oidc_job.Budget(120, 90, 30, 60)
        profile = {"windows_powershell": "pwsh"}
        profile_hash = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"),
                                                 ensure_ascii=True).encode()).hexdigest()
        self.config = oidc_job.ReviewedConfig("123456789012", "arn:aws:iam::123456789012:role/test", 3, 10800,
                                              os.environ.get("SYSTEMROOT", "C:/Windows"),
                                              os.environ.get("USERPROFILE", "C:/trusted/user"),
                                              os.environ.get("TEMP", "C:/trusted/temp"),
                                              os.environ.get("PROGRAMFILES", "C:/Program Files"),
                                              os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"),
                                              os.environ.get("PROGRAMDATA", "C:/ProgramData"),
                                              "/usr/bin:/bin", "/home/reviewed",
                                              "C:/trusted/profile.json", profile_hash, os.environ.get("PATH", ""),
                                              "C:/trusted/git.exe", self.budget)
        self.session = FixedSession(ACCESS, SECRET, TOKEN, NOW + timedelta(hours=3))
        self.calls = []

    def issue(self, env, expected, **kwargs):
        self.calls.append((expected, kwargs))
        return self.session

    def test_all_ci_consumers_receive_only_verified_fixed_session(self):
        child = oidc_job.prepare_child(environment(), source_sha=SHA, config=self.config, user_name="synthetic-runner", session_factory=self.issue)
        expected, kwargs = self.calls[0]
        self.assertEqual((expected.project_id, expected.project_path, expected.ref, expected.sha),
                         ("38", oidc_job.PROJECT_PATH, "main", SHA))
        self.assertEqual(10800, kwargs["duration_seconds"])
        self.assertGreater(kwargs["required_seconds"], 6489)
        self.assertEqual((ACCESS, SECRET, TOKEN), tuple(child[k] for k in
                         ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")))
        for name in ("RX_OIDC_ID_TOKEN", "CI_JOB_TOKEN", "AWS_PROFILE", "AWS_ENDPOINT_URL"):
            self.assertNotIn(name, child)
        self.assertEqual("synthetic-apn", child["AWS_IOT_CELLULAR_APN_CK_RX65N_01"])
        self.assertEqual("synthetic-runner", child["USERNAME"])
        with patch.dict(os.environ, child, clear=True):
            credentials = botocore.session.Session().get_credentials()
            self.assertEqual("env", credentials.method)
            frozen = credentials.get_frozen_credentials()
            self.assertEqual((ACCESS, SECRET, TOKEN), (frozen.access_key, frozen.secret_key, frozen.token))
        oidc_job.check_child_budget(child, before_run=True, now=NOW)
        with self.assertRaises(OidcError):
            oidc_job.check_child_budget(child, now=NOW + timedelta(seconds=5000))

    def test_missing_budget_invalid_scope_and_ota_fail_before_exchange(self):
        for env, config in ((environment(), None),
                            ({**environment(), "IDT_SCOPE": "unknown"}, self.config),
                            ({**environment(), "IDT_SCOPE": "ota-mqtt"}, self.config),
                            ({**environment(), "IDT_SCOPE": "ota-pal"}, self.config)):
            with self.subTest(scope=env["IDT_SCOPE"]), self.assertRaises(OidcError):
                oidc_job.prepare_child(env, source_sha=SHA, config=config, user_name="synthetic-runner", session_factory=self.issue)
        self.assertFalse(self.calls)
        with self.assertRaises(OidcError):
            oidc_job.Budget(0, 90, 30, 60)

    def test_ci_cannot_bypass_deadline_with_missing_or_small_fields(self):
        with self.assertRaises(OidcError):
            oidc_job.check_child_budget({"CI": "true"}, now=NOW)
        child = oidc_job.prepare_child(environment(), source_sha=SHA, config=self.config, user_name="synthetic-runner", session_factory=self.issue)
        for update in ({"RX_OIDC_IDT_NATIVE_REQUIRED_SECONDS": "1"},
                       {"RX_OIDC_IDT_MARGIN_SECONDS": "0"},
                       {"CI_JOB_TIMEOUT": ""}, {"AWS_SESSION_TOKEN": ""},
                       {"AWS_PROFILE": "host-profile"}, {"AWS_ENDPOINT_URL": "https://invalid.example"},
                       {"BOTO_PATH": "host-config"}, {"RX_OIDC_ID_TOKEN": "synthetic-jwt"},
                       {"CI_JOB_TOKEN": "synthetic-job-token"}):
            with self.subTest(update=update), self.assertRaises(OidcError):
                oidc_job.check_child_budget({**child, **update}, now=NOW)
        oidc_job.check_native_timeouts(child, 4500, 120)
        for native, cleanup in ((4501, 120), (4500, 121)):
            with self.subTest(native=native, cleanup=cleanup), self.assertRaises(OidcError):
                oidc_job.check_native_timeouts(child, native, cleanup)

    def test_pipeline_overrides_cannot_choose_role_or_executable(self):
        bad_role = {**environment(), "RX_OIDC_ACCOUNT_ID": "999999999999",
                    "RX_OIDC_ROLE_ARN_IDT_TRANSPORT": "arn:aws:iam::999999999999:role/other"}
        with self.assertRaises(OidcError):
            oidc_job.prepare_child(bad_role, source_sha=SHA, config=self.config, user_name="synthetic-runner", session_factory=self.issue)
        self.assertEqual([], self.calls)
        env = {**environment(), "RX72N_IDT_PYTHON": "C:/untrusted/python.exe",
               "RX72N_IDT_HOST_PROFILE": "C:/untrusted/profile.json",
               "RX72N_IDT_POWERSHELL": "C:/untrusted/pwsh.exe", "PATH": "C:/untrusted",
               "SYSTEMROOT": "C:/untrusted", "WINDIR": "C:/untrusted",
               "COMSPEC": "C:/untrusted/cmd.exe", "WSLENV": "PATH/l:HOME/p"}
        child = oidc_job.prepare_child(env, source_sha=SHA, config=self.config, user_name="synthetic-runner", session_factory=self.issue)
        expected, _ = self.calls[0]
        self.assertEqual(self.config.account, expected.account)
        self.assertEqual(self.config.role_arn, expected.role_arn)
        self.assertEqual(oidc_job.ENTRY_PYTHON, child["RX72N_IDT_PYTHON"])
        self.assertEqual(self.config.host_profile, child["RX72N_IDT_HOST_PROFILE"])
        self.assertEqual(self.config.search_path, child["PATH"])
        self.assertEqual(self.config.windows_root, child["WINDIR"])
        self.assertEqual("", child["WSLENV"])
        self.assertNotIn("untrusted", child["COMSPEC"].lower())
        self.assertEqual(self.config.wsl_path, child["RX_OIDC_IDT_WSL_PATH"])
        self.assertNotIn("RX72N_IDT_POWERSHELL", child)
        self.assertEqual("17", child["CI_JOB_ID"])

    def test_real_idt_bridge_passes_only_fixed_session_and_required_inputs(self):
        child = oidc_job.prepare_child(environment(), source_sha=SHA, config=self.config, user_name="synthetic-runner", session_factory=self.issue)
        credentials = SimpleNamespace(access_key=ACCESS, secret_key=SECRET, token=TOKEN)
        inherited = {"IDT_TARGET": "rx65n-bg96", "IDT_RUNTIME_DIR": "/private/run",
                     "AWS_ACCESS_KEY_ID": ACCESS, "AWS_SECRET_ACCESS_KEY": SECRET,
                     "AWS_SESSION_TOKEN": TOKEN,
                     "AWS_IOT_CELLULAR_APN_CK_RX65N_01": "synthetic-apn"}
        bridge = run_idt.idt_wsl_environment({**child, "AWS_PROFILE": "host-profile", "WSLENV": "PATH/l:HOME/p",
                                              "AWS_ENDPOINT_URL": "https://invalid.example",
                                              "RX_OIDC_ID_TOKEN": "synthetic-jwt"}, inherited,
                                             credentials, get_target("rx65n-bg96"))
        for key in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "RX_OIDC_ID_TOKEN"):
            self.assertNotIn(key, bridge)
        self.assertNotIn("PATH/l", bridge["WSLENV"].split(":"))
        self.assertNotIn("HOME/p", bridge["WSLENV"].split(":"))
        for name in ("AWS_SESSION_TOKEN/u", "RX_OIDC_EXPIRATION_UTC/u", "IDT_RUNTIME_DIR/u",
                     "CI_JOB_STARTED_AT/u", "CI_JOB_TIMEOUT/u", "RX_OIDC_IDT_MARGIN_SECONDS/u",
                     "RX_OIDC_IDT_WSL_PATH/u", "RX_OIDC_IDT_WSL_HOME/u"):
            self.assertIn(name, bridge["WSLENV"].split(":"))
        linux = wsl_child_environment(bridge, allow_names=("IDT_TARGET", "IDT_RUNTIME_DIR", "CI",
                                      "RX_OIDC_IDT_NATIVE_REQUIRED_SECONDS", "RX_OIDC_IDT_PREPARE_SECONDS",
                                      "RX_OIDC_IDT_MARGIN_SECONDS", "AWS_IOT_CELLULAR_APN_CK_RX65N_01"))
        self.assertEqual(TOKEN, linux["AWS_SESSION_TOKEN"])
        self.assertEqual("synthetic-apn", linux["AWS_IOT_CELLULAR_APN_CK_RX65N_01"])
        with self.assertRaisesRegex(RuntimeError, "unreviewed IDT WSL input"):
            run_idt.idt_wsl_environment(child, {**inherited, "IDT_UNREVIEWED": "value"},
                                        credentials, get_target("rx65n-bg96"))

    def test_real_exchange_path_rejects_context_mismatch_and_ignores_later_jwt_expiry(self):
        now = datetime.now(timezone.utc)
        env = {**environment(), "CI_JOB_STARTED_AT": now.isoformat()}
        claims = {"iss": "https://gitlab.saffti.jp", "aud": "sts.amazonaws.com",
                  "sub": "project_path:" + oidc_job.PROJECT_PATH + ":ref_type:branch:ref:main",
                  "project_id": "38", "job_id": "17", "pipeline_source": "schedule",
                  "ref_protected": "true", "ref_type": "branch", "ref": "main", "sha": SHA,
                  "runner_id": 3,
                  "exp": int((now + timedelta(seconds=300)).timestamp())}
        calls = []

        class Sts:
            def assume_role_with_web_identity(self, **_kwargs):
                calls.append("exchange")
                return {"Credentials": {"AccessKeyId": ACCESS, "SecretAccessKey": SECRET,
                                        "SessionToken": TOKEN, "Expiration": now + timedelta(hours=3)},
                        "SubjectFromWebIdentityToken": claims["sub"], "Audience": "sts.amazonaws.com"}

            def get_caller_identity(self):
                return {"Account": "123456789012", "Arn": "arn:aws:sts::123456789012:assumed-role/test/gitlab38-17"}

        class Sdk:
            def set_config_variable(self, *_args):
                pass

            def create_client(self, *_args, **_kwargs):
                return Sts()

        def token(changed):
            payload = base64.urlsafe_b64encode(json.dumps({**claims, **changed}).encode()).decode().rstrip("=")
            return "header." + payload + ".signature"

        with patch("botocore.session.Session", return_value=Sdk()):
            for changed in ({"aud": "wrong"}, {"job_id": "18"}, {"runner_id": 4}, {"runner_id": 3.0},
                            {"runner_id": True}, {"sha": "b" * 40},
                            {"exp": int(now.timestamp()) - 1}):
                with self.subTest(changed=changed), self.assertRaises(OidcError):
                    oidc_job.prepare_child({**env, "RX_OIDC_ID_TOKEN": token(changed)},
                                           source_sha=SHA, config=self.config, user_name="synthetic-runner")
                self.assertEqual([], calls)
            child = oidc_job.prepare_child({**env, "RX_OIDC_ID_TOKEN": token({})}, source_sha=SHA, config=self.config, user_name="synthetic-runner")
        self.assertEqual(["exchange"], calls)
        self.assertNotIn("RX_OIDC_ID_TOKEN", child)
        oidc_job.check_child_budget(child, now=now + timedelta(seconds=600))

    def test_entrypoint_authenticates_before_starting_any_consumer(self):
        events = []

        def session(*args, **kwargs):
            events.append("authenticate")
            return self.issue(*args, **kwargs)

        def git(*_args, **kwargs):
            self.assertNotIn("RX_OIDC_ID_TOKEN", kwargs["env"])
            self.assertNotIn("AWS_ACCESS_KEY_ID", kwargs["env"])
            return SHA

        job = {"id": 17, "status": "running", "started_at": NOW.isoformat(),
               "pipeline": {"id": 18}, "runner": {"id": 3}, "commit": {"id": SHA}}

        def launch(*args, **kwargs):
            events.append("launch")
            self.assertNotIn("RX_OIDC_ID_TOKEN", kwargs["env"])
            self.assertNotIn("AWS_PROFILE", kwargs["env"])
            self.assertEqual(TOKEN, kwargs["env"]["AWS_SESSION_TOKEN"])
            return Mock(returncode=0)

        with patch.dict(os.environ, environment(), clear=True), \
                patch.dict(oidc_job.REVIEWED_CONFIGS, {"transport": self.config}), \
                patch.object(oidc_job.subprocess, "check_output", side_effect=git), \
                patch.object(oidc_job, "current_job_metadata", return_value=job), \
                patch.object(oidc_job, "obtain_session", side_effect=session), \
                patch.object(oidc_job, "current_windows_user", return_value="synthetic-runner"), \
                patch.object(oidc_job, "load_reviewed_host", return_value={"windows_powershell": "pwsh"}), \
                patch.object(oidc_job.subprocess, "run", side_effect=launch):
            self.assertEqual(0, oidc_job.main())
        self.assertEqual(["authenticate", "launch"], events)

    def test_exchange_failure_never_launches_consumer(self):
        job = {"id": 17, "status": "running", "started_at": NOW.isoformat(),
               "pipeline": {"id": 18}, "runner": {"id": 3}, "commit": {"id": SHA}}
        with patch.dict(os.environ, environment(), clear=True), \
                patch.dict(oidc_job.REVIEWED_CONFIGS, {"transport": self.config}), \
                patch.object(oidc_job, "current_windows_user", return_value="synthetic-runner"), \
                patch.object(oidc_job, "load_reviewed_host", return_value={"windows_powershell": "pwsh"}), \
                patch.object(oidc_job.subprocess, "check_output", return_value=SHA), \
                patch.object(oidc_job, "current_job_metadata", return_value=job), \
                patch.object(oidc_job, "obtain_session", side_effect=OidcError("insufficient")), \
                patch.object(oidc_job.subprocess, "run") as launch:
            with self.assertRaises(OidcError):
                oidc_job.main()
            launch.assert_not_called()

    def test_no_reviewed_configuration_never_calls_git_aws_or_child(self):
        with patch.dict(os.environ, environment(), clear=True), \
                patch.dict(oidc_job.REVIEWED_CONFIGS, {}, clear=True), \
                patch.object(oidc_job.subprocess, "check_output") as git, \
                patch.object(oidc_job, "obtain_session") as sts, \
                patch.object(oidc_job.subprocess, "run") as child:
            with self.assertRaises(OidcError):
                oidc_job.main()
            git.assert_not_called()
            sts.assert_not_called()
            child.assert_not_called()

    def test_job_api_start_and_reviewed_timeout_override_spoofed_values(self):
        job = {"id": 17, "status": "running", "started_at": NOW.isoformat(),
               "pipeline": {"id": 18}, "runner": {"id": 3}, "commit": {"id": SHA}}
        env = {**environment(), "CI_JOB_STARTED_AT": (NOW + timedelta(hours=1)).isoformat(),
               "CI_JOB_TIMEOUT": "999999"}
        verified = oidc_job.verified_job_environment(env, self.config, SHA, job)
        self.assertEqual(NOW.isoformat(), verified["CI_JOB_STARTED_AT"])
        self.assertEqual("10800", verified["CI_JOB_TIMEOUT"])
        for bad in ({**job, "runner": {"id": 4}}, {**job, "status": "canceled"},
                    {**job, "commit": {"id": "b" * 40}}, {**job, "pipeline": {"id": 19}}):
            with self.subTest(bad=bad), self.assertRaises(OidcError):
                oidc_job.verified_job_environment(env, self.config, SHA, bad)

    def test_current_job_api_uses_header_no_proxy_or_redirect_and_redacts_errors(self):
        payload = json.dumps({"id": 17}).encode()
        response = io.BytesIO(payload)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(oidc_job.urllib.request, "build_opener", return_value=opener) as build:
            self.assertEqual({"id": 17}, oidc_job.current_job_metadata("synthetic-job-token"))
        handlers = build.call_args.args
        self.assertEqual({}, handlers[0].proxies)
        self.assertIsNone(handlers[1].redirect_request(None, None, None, None, None, None))
        request = opener.open.call_args.args[0]
        self.assertEqual("https://gitlab.saffti.jp/api/v4/job", request.full_url)
        self.assertEqual("synthetic-job-token", request.get_header("Job-token"))
        with patch.object(oidc_job.urllib.request, "build_opener", side_effect=RuntimeError("synthetic-job-token")):
            with self.assertRaises(OidcError) as caught:
                oidc_job.current_job_metadata("synthetic-job-token")
            self.assertNotIn("synthetic-job-token", str(caught.exception))

    def test_actual_isolated_entrypoint_fails_without_reviewed_configuration(self):
        result = subprocess.run([sys.executable, "-I", str(oidc_job.ROOT / "tools/idt/oidc_job.py")],
                                env=environment(), capture_output=True, text=True, timeout=30)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("IDT OIDC preflight failed", result.stderr)
        for value in ("synthetic-jwt", "host-old-key"):
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_modified_host_profile_never_reaches_consumer(self):
        with patch.dict(os.environ, environment(), clear=True), \
                patch.dict(oidc_job.REVIEWED_CONFIGS, {"transport": self.config}), \
                patch.object(oidc_job.subprocess, "check_output") as git, \
                patch.object(oidc_job, "obtain_session") as sts, \
                patch.object(oidc_job, "current_windows_user", return_value="synthetic-runner"), \
                patch.object(oidc_job, "load_host_profile", return_value={"windows_powershell": "untrusted"}), \
                patch.object(oidc_job.subprocess, "run") as child:
            with self.assertRaisesRegex(OidcError, "host profile"):
                oidc_job.main()
            git.assert_not_called()
            sts.assert_not_called()
            child.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("awscli"), "AWS CLI module is not installed in this Python")
    def test_real_aws_cli_resolves_fixed_session_from_isolated_environment(self):
        child = oidc_job.prepare_child(environment(), source_sha=SHA, config=self.config, user_name="synthetic-runner", session_factory=self.issue)
        observed = {}

        class StsFixture(BaseHTTPRequestHandler):
            def do_POST(self):
                observed["auth"] = self.headers.get("Authorization", "")
                observed["token"] = self.headers.get("X-Amz-Security-Token", "")
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = (b'<GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">'
                        b'<GetCallerIdentityResult><Account>123456789012</Account>'
                        b'<Arn>arn:aws:sts::123456789012:assumed-role/test/unit</Arn>'
                        b'<UserId>unit</UserId></GetCallerIdentityResult>'
                        b'<ResponseMetadata><RequestId>unit</RequestId></ResponseMetadata></GetCallerIdentityResponse>')
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), StsFixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f"http://127.0.0.1:{server.server_port}"
            subprocess.run([sys.executable, "-I", "-m", "awscli", "--endpoint-url", endpoint, "sts", "get-caller-identity"],
                           env=child, capture_output=True, text=True, timeout=30, check=True)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertIn("Credential=" + ACCESS + "/", observed["auth"])
        self.assertEqual(TOKEN, observed["token"])


if __name__ == "__main__":
    unittest.main()

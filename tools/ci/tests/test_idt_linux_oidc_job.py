"""Offline coverage of the dedicated Linux runner and fixed-session boundary."""
import base64
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.aws.oidc_session import FixedSession, OidcError, validate_context
from tools.idt import linux_oidc_job as launcher
from tools.idt.oidc_job import Budget

SHA = "a" * 40
ACCOUNT = "000000000000"
ROLE = "arn:aws:iam::" + ACCOUNT + ":role/saffti-oss-gitlab-oidc"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def token(runner=28):
    claims = {"iss": "https://gitlab.saffti.jp", "sub": "project_path:" + launcher.PROJECT_PATH + ":ref_type:branch:ref:main",
              "aud": "sts.amazonaws.com", "project_id": "38", "job_id": "17", "pipeline_source": "api",
              "runner_id": runner, "ref_protected": "true", "ref_type": "branch", "ref": "main",
              "sha": SHA, "exp": int((NOW + timedelta(hours=1)).timestamp())}
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "e30." + encoded + ".signature"


def config():
    return launcher.LinuxConfig(ACCOUNT, ROLE, "main", 28, 10800, Budget(100, 100, 10, 10),
                                "/var/tmp/idt-runtime", "/opt/idt", "/opt/idt/build-hook",
                                "/usr/bin/ssh", "/usr/bin/scp", "/usr/bin/git", "/usr/bin/python3",
                                "/var/lib/gitlab-runner-idt-rx", "/usr/bin:/bin", 600)


def environment():
    return {"CI": "true", "CI_PROJECT_ID": "38", "CI_PROJECT_PATH": launcher.PROJECT_PATH,
            "CI_COMMIT_SHA": SHA, "CI_COMMIT_BRANCH": "main", "CI_COMMIT_REF_PROTECTED": "true",
            "CI_PIPELINE_SOURCE": "api", "CI_JOB_ID": "17", "CI_PIPELINE_ID": "19", "CI_RUNNER_ID": "28",
            "CI_JOB_TIMEOUT": "10800", "CI_JOB_TOKEN": "job-secret", "RX_OIDC_ID_TOKEN": token(),
            "RUN_RX_IDT": "true", "IDT_TARGET": "rx72n-ethernet", "IDT_SCOPE": "transport",
            "AWS_ROLE_ARN": ROLE, "AWS_ACCESS_KEY_ID": "ambient-key", "AWS_SECRET_ACCESS_KEY": "ambient-secret",
            "AWS_PROFILE": "ambient-profile", "UNREVIEWED_INPUT": "do-not-forward",
            **{name: "/var/tmp/bootstrap/" + name for name in launcher.PUBLIC_SIGNER_INPUTS.values()}}


def job(runner=28):
    return {"started_at": NOW.isoformat(), "status": "running", "id": 17,
            "pipeline": {"id": 19, "ref": "main"}, "runner": {"id": runner},
            "commit": {"id": SHA}, "tag_list": [launcher.RUNNER_TAG]}


def fake_session(env, expected, **kwargs):
    validate_context(env, expected, env["RX_OIDC_ID_TOKEN"], NOW)
    return FixedSession("temporary-key", "temporary-secret", "temporary-token", NOW + timedelta(hours=3))


class LinuxOidcJobTests(unittest.TestCase):
    def test_unreviewed_entry_stops_before_job_or_sts(self):
        with patch.object(launcher, "current_job_metadata", side_effect=AssertionError("must not contact GitLab")):
            with self.assertRaises(OidcError):
                launcher.main()

    def test_dedicated_job_uses_signed_runner_id_and_isolates_child(self):
        child = launcher.prepare_child(environment(), source_sha=SHA, config=config(), job=job(),
                                       baseline_path="/var/tmp/idt-runtime/baseline.json", session_factory=fake_session)
        self.assertEqual(child["IDT_HOST_MODE"], "linux-arm64")
        self.assertEqual(child["IDT_LINUX_BUILD_CALLBACK"], "/opt/idt/build-hook")
        self.assertEqual(child["IDT_PAIR_BASELINE"], "/var/tmp/idt-runtime/baseline.json")
        self.assertEqual(child["IDT_PAIR_SOCKET"].replace("\\", "/"), "/var/lib/gitlab-runner-idt-rx/.cache/idt-rx72n-pair/19/build.sock")
        self.assertEqual(child["IDT_PAIR_BUILD_SECONDS"], "600")
        self.assertEqual(child["AWS_ACCESS_KEY_ID"], "temporary-key")
        for name in ("RX_OIDC_ID_TOKEN", "CI_JOB_TOKEN", "AWS_ROLE_ARN", "AWS_PROFILE", "UNREVIEWED_INPUT"):
            self.assertNotIn(name, child)
        self.assertEqual(child["AWS_CONFIG_FILE"], __import__("os").devnull)

    def test_wrong_runner_claim_tag_ref_and_target_are_rejected(self):
        bad_env = environment(); bad_env["CI_RUNNER_ID"] = "29"
        with self.assertRaises(OidcError):
            launcher.prepare_child(bad_env, source_sha=SHA, config=config(), job=job(), baseline_path="/tmp/baseline", session_factory=fake_session)
        bad_env = environment(); bad_env["CI_RUNNER_ID"] = "29"; bad_env["RX_OIDC_ID_TOKEN"] = token(29)
        with self.assertRaises(OidcError):
            launcher.prepare_child(bad_env, source_sha=SHA, config=config(), job=job(29), baseline_path="/tmp/baseline", session_factory=fake_session)
        bad_job = job(); bad_job["tag_list"] = ["os-linux"]
        with self.assertRaises(OidcError):
            launcher.prepare_child(environment(), source_sha=SHA, config=config(), job=bad_job, baseline_path="/tmp/baseline", session_factory=fake_session)
        bad_job = job(); bad_job["pipeline"]["ref"] = "other"
        with self.assertRaises(OidcError):
            launcher.prepare_child(environment(), source_sha=SHA, config=config(), job=bad_job, baseline_path="/tmp/baseline", session_factory=fake_session)
        bad_env = environment(); bad_env["IDT_TARGET"] = "rx671-wifi"
        with self.assertRaises(OidcError):
            launcher.prepare_child(bad_env, source_sha=SHA, config=config(), job=job(), baseline_path="/tmp/baseline", session_factory=fake_session)
        bad_env = environment(); bad_env.pop(next(iter(launcher.PUBLIC_SIGNER_INPUTS.values())))
        with self.assertRaises(OidcError):
            launcher.prepare_child(bad_env, source_sha=SHA, config=config(), job=job(), baseline_path="/tmp/baseline", session_factory=fake_session)

    def test_no_budget_or_unreviewed_identity_cannot_start(self):
        with self.assertRaises(OidcError):
            launcher.prepare_child(environment(), source_sha=SHA, config=None, job=job(), baseline_path="/tmp/baseline", session_factory=fake_session)
        with self.assertRaises(OidcError):
            launcher.LinuxConfig(ACCOUNT, ROLE, "main", 28, 500, Budget(100, 100, 10, 10),
                                 "/tmp/runtime", "/opt/idt", "/opt/hook", "/usr/bin/ssh", "/usr/bin/scp",
                                 "/usr/bin/git", "/usr/bin/python3", "/tmp/home", "/usr/bin:/bin", 600)

    def test_fixed_host_config_rejects_wrong_owner_mode_and_extra_fields(self):
        document = {"schema_version": 1, **asdict(config())}
        self.assertEqual(launcher.parse_config(document), config())
        with self.assertRaises(OidcError):
            launcher.parse_config({**document, "extra": "unreviewed"})
        with self.assertRaises(OidcError):
            launcher.parse_config({**document, "schema_version": True})
        directory = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        file = SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_gid=123)
        launcher.validate_config_metadata(directory, file, 123)
        for bad in (SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_gid=123),
                    SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=1000, st_gid=123),
                    SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_gid=124)):
            with self.assertRaises(OidcError):
                launcher.validate_config_metadata(directory, bad, 123)

    def test_report_publication_excludes_private_runtime_and_requires_success_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            private, output = root / "private", root / "artifacts"
            private.mkdir()
            for name in ("FRQ_Report.xml", "metadata.json", "summary.json", "console.log", "transport-private.pem"):
                (private / name).write_text("synthetic", encoding="utf-8")
            launcher.publish_reports(private, output, require_all=True)
            self.assertEqual({p.name for p in output.iterdir()}, {"FRQ_Report.xml", "metadata.json", "summary.json"})
            (private / "FRQ_Report.xml").unlink()
            with self.assertRaises(OidcError):
                launcher.publish_reports(private, output, require_all=True)

    def test_baseline_reuses_paired_snapshot_and_missing_integration_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "baseline.json"
            snapshot = Mock(return_value={"file.c": "a" * 64})
            with patch.dict(sys.modules, {"tools.idt.rpi4_pair": SimpleNamespace(snapshot=snapshot)}):
                launcher.capture_baseline(Path(folder), path)
            snapshot.assert_called_once_with(Path(folder))
            self.assertEqual(json.loads(path.read_text()), {"file.c": "a" * 64})
            with patch.dict(sys.modules, {"tools.idt.rpi4_pair": None}):
                with self.assertRaisesRegex(OidcError, "paired build integration"):
                    launcher.capture_baseline(Path(folder), path)

    @unittest.skipUnless(sys.platform == "linux", "fixed config uses Linux openat")
    def test_host_config_reads_only_fixed_path_without_following_links(self):
        document = {"schema_version": 1, **asdict(config())}
        directory = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        file = SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_gid=123)
        with patch("grp.getgrnam", return_value=SimpleNamespace(gr_gid=123)), \
             patch.object(launcher.os, "open", side_effect=[11, 12]) as opened, \
             patch.object(launcher.os, "fstat", side_effect=[directory, file]), \
             patch.object(launcher.os, "fdopen", return_value=io.BytesIO(json.dumps(document).encode())), \
             patch.object(launcher.os, "close"):
            self.assertEqual(launcher.read_reviewed_config(), config())
        self.assertEqual(opened.call_args_list[0].args[0], "/etc/idt-rx")
        self.assertTrue(opened.call_args_list[0].args[1] & os.O_NOFOLLOW)
        self.assertEqual(opened.call_args_list[1].args[0], "runtime.json")
        self.assertEqual(opened.call_args_list[1].kwargs["dir_fd"], 11)
        self.assertTrue(opened.call_args_list[1].args[1] & os.O_NOFOLLOW)

    @unittest.skipUnless(sys.platform == "linux", "dedicated account is POSIX")
    def test_missing_host_config_stops_before_gitlab_or_aws(self):
        with patch.dict(os.environ, {"CI_PROJECT_DIR": str(launcher.ROOT)}, clear=True), \
             patch.object(launcher.platform, "machine", return_value="aarch64"), \
             patch("pwd.getpwuid", return_value=SimpleNamespace(pw_name=launcher.RUNNER_USER)), \
             patch.object(launcher, "read_reviewed_config", side_effect=FileNotFoundError), \
             patch.object(launcher, "current_job_metadata", side_effect=AssertionError("must not contact GitLab")):
            with self.assertRaises(FileNotFoundError):
                launcher.main()


if __name__ == "__main__":
    unittest.main()

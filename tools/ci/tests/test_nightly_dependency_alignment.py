from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "tools/ci/check_nightly_dependency_alignment.py"
SPEC = importlib.util.spec_from_file_location("dependency_alignment", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
alignment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alignment)


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    git(path, "init", "--quiet")
    git(path, "config", "user.name", "Codex Test")
    git(path, "config", "user.email", "codex-test@example.invalid")


def commit_all(path: Path, message: str = "files") -> str:
    git(path, "add", ".")
    git(path, "commit", "--quiet", "-m", message)
    return git(path, "rev-parse", "HEAD")


class GitlinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        init_repo(self.repo)
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        (self.repo / "Common").mkdir()
        (self.repo / "Common/source.c").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "README.md", "Common/source.c")
        git(self.repo, "commit", "--quiet", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def commit_gitlink(self, path: str, sha: str, message: str) -> str:
        git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{sha},{path}")
        git(self.repo, "commit", "--quiet", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def test_read_gitlink_accepts_mode_160000_and_sha40(self) -> None:
        ref = self.commit_gitlink("Middleware/AWS/lib", self.base, "link")
        self.assertEqual(
            self.base,
            alignment.read_gitlink(self.repo, ref, "Middleware/AWS/lib"),
        )

    def test_missing_and_non_gitlink_fail_closed(self) -> None:
        with self.assertRaisesRegex(alignment.AlignmentError, "missing gitlink"):
            alignment.read_gitlink(self.repo, self.base, "missing")
        with self.assertRaisesRegex(alignment.AlignmentError, "mode 160000"):
            alignment.read_gitlink(self.repo, self.base, "README.md")

    def test_gitlink_mismatch_is_reported(self) -> None:
        first = self.commit_gitlink("Middleware/AWS/lib", self.base, "first")
        second = self.commit_gitlink("Middleware/AWS/lib", first, "second")
        checks = alignment.compare_parent_gitlinks(
            self.repo,
            first,
            second,
            ["Middleware/AWS/lib"],
        )
        self.assertEqual("failed", checks[0]["status"])
        self.assertEqual(self.base, checks[0]["expected"])
        self.assertEqual(first, checks[0]["actual"])

    def test_source_tree_match_and_change_are_reported(self) -> None:
        self.assertEqual(
            git(self.repo, "rev-parse", f"{self.base}:Common"),
            alignment.read_source_tree(self.repo, self.base, "Common"),
        )
        (self.repo / "Common/source.c").write_text("changed\n", encoding="utf-8")
        changed = commit_all(self.repo, "source change")
        checks = alignment.compare_parent_source_trees(
            self.repo,
            changed,
            self.base,
            ["Common"],
        )
        self.assertEqual("failed", checks[0]["status"])
        self.assertEqual("source_tree", checks[0]["kind"])

    def test_missing_and_non_tree_source_roots_fail_closed(self) -> None:
        with self.assertRaisesRegex(alignment.AlignmentError, "missing source tree"):
            alignment.read_source_tree(self.repo, self.base, "missing")
        with self.assertRaisesRegex(alignment.AlignmentError, "mode 040000"):
            alignment.read_source_tree(self.repo, self.base, "README.md")


class ConfigurationAndCheckoutTests(unittest.TestCase):
    def test_invalid_config_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "targets": [
                            {
                                "name": "bad",
                                "repository": "https://user:secret@example.com/a.git",
                                "ref_env": "REF",
                                "default_ref": "main",
                                "mode": "parent_gitlinks",
                                "iot_reference_gitlink": "external/iot-reference-rx",
                                "dependencies": ["../escape"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(alignment.AlignmentError):
                alignment.load_config(config)

    def test_source_roots_are_required_and_must_be_safe(self) -> None:
        base_target = {
            "name": "benchmark",
            "project": "group/project",
            "repository": "https://example.com/group/project.git",
            "ref_env": "BENCHMARK_REF",
            "resolved_ref_env": "BENCHMARK_RESOLVED_SHA",
            "default_ref": "main",
            "mode": "parent_gitlinks",
            "iot_reference_gitlink": "external/iot-reference-rx",
            "dependencies": ["Middleware/FreeRTOS/FreeRTOS-Kernel"],
        }
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.json"
            config.write_text(
                json.dumps({"schema_version": 1, "targets": [base_target]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                alignment.AlignmentError,
                "source_roots must be non-empty",
            ):
                alignment.load_config(config)

            unsafe = dict(base_target)
            unsafe["source_roots"] = ["../Common"]
            config.write_text(
                json.dumps({"schema_version": 1, "targets": [unsafe]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                alignment.AlignmentError,
                "safe repository-relative path",
            ):
                alignment.load_config(config)

    def test_legacy_vendored_subset_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "targets": [
                            {
                                "name": "legacy",
                                "project": "group/project",
                                "repository": "https://example.com/group/project.git",
                                "ref_env": "REF",
                                "resolved_ref_env": "RESOLVED_SHA",
                                "default_ref": "main",
                                "mode": "vendored_subset",
                                "dependencies": ["Middleware/AWS/lib"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                alignment.AlignmentError,
                "unsupported mode",
            ):
                alignment.load_config(config)

    def test_gitlink_parser_rejects_abbreviated_sha(self) -> None:
        with self.assertRaisesRegex(alignment.AlignmentError, "mode 160000"):
            alignment.parse_gitlink_line(
                "160000 commit deadbeef\tMiddleware/AWS/lib",
                "Middleware/AWS/lib",
            )

    def test_git_errors_redact_url_userinfo_and_secret_values(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "CI_JOB_TOKEN": "token/with-special",
                "UNRELATED_VALUE": "public-value",
            },
            clear=False,
        ):
            redacted = alignment.redact_sensitive_text(
                "fatal: https://oauth2:token%2Fwith-special@gitlab.example/repo "
                "token/with-special public-value"
            )
        self.assertNotIn("oauth2:", redacted)
        self.assertNotIn("token%2Fwith-special", redacted)
        self.assertNotIn("token/with-special", redacted)
        self.assertIn("public-value", redacted)

    def test_resolved_commits_are_exported_as_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "resolved.env"
            alignment.write_dotenv(
                output,
                {
                    "targets": [
                        {
                            "name": "benchmark",
                            "resolved_ref_env": "BENCHMARK_RESOLVED_SHA",
                        }
                    ]
                },
                [{"name": "benchmark", "commit": "a" * 40}],
            )
            self.assertEqual(
                f"BENCHMARK_RESOLVED_SHA={'a' * 40}\n",
                output.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()

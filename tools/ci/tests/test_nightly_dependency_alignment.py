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


class VendoredSubsetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.parent = root / "parent"
        self.child = root / "child"
        self.parent_dependency = self.parent / "Middleware/AWS/lib"
        self.child_dependency = self.child / "Middleware/AWS/lib"
        init_repo(self.parent_dependency)
        init_repo(self.child)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def compare(self) -> dict:
        return alignment.compare_vendored_dependency(
            self.parent, self.child, "Middleware/AWS/lib"
        )

    def test_exact_subset_passes_and_parent_only_is_allowed(self) -> None:
        (self.parent_dependency / "a.c").write_bytes(b"same")
        (self.parent_dependency / "parent-only.md").write_bytes(b"docs")
        self.child_dependency.mkdir(parents=True)
        (self.child_dependency / "a.c").write_bytes(b"same")
        commit_all(self.parent_dependency)
        commit_all(self.child)
        result = self.compare()
        self.assertEqual("passed", result["status"])
        self.assertEqual(1, result["checked_files"])
        self.assertEqual(1, result["parent_only_files"])

    def test_modified_file_fails(self) -> None:
        (self.parent_dependency / "a.c").write_bytes(b"parent")
        self.child_dependency.mkdir(parents=True)
        (self.child_dependency / "a.c").write_bytes(b"child")
        commit_all(self.parent_dependency)
        commit_all(self.child)
        result = self.compare()
        self.assertEqual("failed", result["status"])
        self.assertEqual(["a.c"], result["modified"])

    def test_exact_blob_pair_can_be_allowed_as_a_documented_patch(self) -> None:
        (self.parent_dependency / "a.c").write_bytes(b"parent")
        self.child_dependency.mkdir(parents=True)
        (self.child_dependency / "a.c").write_bytes(b"child")
        commit_all(self.parent_dependency)
        commit_all(self.child)
        parent_blob = git(self.parent_dependency, "rev-parse", "HEAD:a.c")
        child_blob = git(
            self.child,
            "rev-parse",
            "HEAD:Middleware/AWS/lib/a.c",
        )
        patch = {
            "path": "Middleware/AWS/lib/a.c",
            "parent_blob": parent_blob,
            "child_blob": child_blob,
            "reason": "documented integration hook",
        }
        result = alignment.compare_vendored_dependency(
            self.parent,
            self.child,
            "Middleware/AWS/lib",
            allowed_patches=[patch],
        )
        self.assertEqual("passed", result["status"], result)
        self.assertEqual([patch], result["allowed_patches"])

    def test_allowed_patch_fails_when_either_blob_changes(self) -> None:
        (self.parent_dependency / "a.c").write_bytes(b"parent")
        self.child_dependency.mkdir(parents=True)
        (self.child_dependency / "a.c").write_bytes(b"unexpected")
        commit_all(self.parent_dependency)
        commit_all(self.child)
        result = alignment.compare_vendored_dependency(
            self.parent,
            self.child,
            "Middleware/AWS/lib",
            allowed_patches=[
                {
                    "path": "Middleware/AWS/lib/a.c",
                    "parent_blob": "0" * 40,
                    "child_blob": "1" * 40,
                    "reason": "stale allowlist",
                }
            ],
        )
        self.assertEqual("failed", result["status"])
        self.assertEqual(["a.c"], result["modified"])

    def test_child_extra_file_fails(self) -> None:
        (self.parent_dependency / "a.c").write_bytes(b"same")
        self.child_dependency.mkdir(parents=True)
        (self.child_dependency / "a.c").write_bytes(b"same")
        (self.child_dependency / "extra.c").write_bytes(b"extra")
        commit_all(self.parent_dependency)
        commit_all(self.child)
        result = self.compare()
        self.assertEqual("failed", result["status"])
        self.assertEqual(["extra.c"], result["missing_in_parent"])

    def test_missing_or_empty_child_dependency_fails(self) -> None:
        (self.parent_dependency / "a.c").write_bytes(b"same")
        (self.child / "README.md").write_text("child\n", encoding="utf-8")
        commit_all(self.parent_dependency)
        commit_all(self.child)
        with self.assertRaisesRegex(alignment.AlignmentError, "empty"):
            self.compare()

    def test_worktree_line_endings_do_not_change_committed_version(self) -> None:
        (self.parent_dependency / "a.c").write_bytes(b"one\ntwo\n")
        self.child_dependency.mkdir(parents=True)
        (self.child_dependency / "a.c").write_bytes(b"one\ntwo\n")
        commit_all(self.parent_dependency)
        commit_all(self.child)
        (self.child_dependency / "a.c").write_bytes(b"one\r\ntwo\r\n")
        self.assertEqual("passed", self.compare()["status"])

    def test_files_below_parent_nested_gitlink_are_ignored(self) -> None:
        nested = Path(self.temp.name) / "nested"
        init_repo(nested)
        (nested / "nested.c").write_text("nested\n", encoding="utf-8")
        nested_sha = commit_all(nested)
        (self.parent_dependency / "direct.c").write_text("same\n", encoding="utf-8")
        git(self.parent_dependency, "add", "direct.c")
        git(
            self.parent_dependency,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{nested_sha},source/dependency/nested",
        )
        git(self.parent_dependency, "commit", "--quiet", "-m", "nested gitlink")
        self.child_dependency.mkdir(parents=True)
        nested_copy = self.child_dependency / "source/dependency/nested"
        nested_copy.mkdir(parents=True)
        (nested_copy / "nested.c").write_text("nested\n", encoding="utf-8")
        (self.child_dependency / "direct.c").write_text("same\n", encoding="utf-8")
        commit_all(self.child)
        result = self.compare()
        self.assertEqual("passed", result["status"], result)
        self.assertEqual(
            ["source/dependency/nested"],
            result["ignored_parent_nested_gitlinks"],
        )
        self.assertEqual(1, result["ignored_child_files_below_nested_gitlinks"])


class GitlinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        init_repo(self.repo)
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
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
                                "mode": "vendored_subset",
                                "dependencies": ["../escape"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(alignment.AlignmentError):
                alignment.load_config(config)

    def test_parent_checkout_is_forced_to_recorded_pins(self) -> None:
        with mock.patch.object(alignment, "run_git") as run:
            alignment.initialize_parent_submodules(
                Path("repo"),
                ["Middleware/FreeRTOS/FreeRTOS-Kernel"],
            )
        update_args = run.call_args_list[1].args[0]
        self.assertIn("--force", update_args)
        self.assertIn("--depth", update_args)
        self.assertIn("1", update_args)

    def test_parent_checkout_retries_one_transient_failure(self) -> None:
        failure = alignment.AlignmentError("transient")
        with mock.patch.object(
            alignment,
            "run_git",
            side_effect=["", failure, "", ""],
        ) as run:
            alignment.initialize_parent_submodules(
                Path("repo"),
                ["Middleware/FreeRTOS/FreeRTOS-Kernel"],
            )
        self.assertEqual(4, run.call_count)

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

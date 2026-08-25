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
RUN5_FIXTURE_PATH = (
    ROOT
    / "tools/ci/tests/fixtures/nightly_dependency_alignment_run5.json"
)
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
        (self.repo / "tools").mkdir()
        (self.repo / "tools/helper.py").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "README.md", "Common/source.c", "tools/helper.py")
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

    def test_source_file_match_and_change_are_reported(self) -> None:
        self.assertEqual(
            git(self.repo, "rev-parse", f"{self.base}:tools/helper.py"),
            alignment.read_source_file(self.repo, self.base, "tools/helper.py"),
        )
        (self.repo / "tools/helper.py").write_text("changed\n", encoding="utf-8")
        changed = commit_all(self.repo, "tool change")
        checks = alignment.compare_parent_source_files(
            self.repo,
            changed,
            self.base,
            ["tools/helper.py"],
        )
        self.assertEqual("failed", checks[0]["status"])
        self.assertEqual("source_file", checks[0]["kind"])

    def test_missing_and_non_file_source_files_fail_closed(self) -> None:
        with self.assertRaisesRegex(alignment.AlignmentError, "missing source file"):
            alignment.read_source_file(self.repo, self.base, "missing.py")
        with self.assertRaisesRegex(alignment.AlignmentError, "regular source file"):
            alignment.read_source_file(self.repo, self.base, "Common")


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
            "source_files": ["tools/helper.py"],
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

    def test_source_files_are_required_and_must_be_safe(self) -> None:
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
            "source_roots": ["Common"],
        }
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.json"
            config.write_text(
                json.dumps({"schema_version": 1, "targets": [base_target]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                alignment.AlignmentError,
                "source_files must be non-empty",
            ):
                alignment.load_config(config)

            unsafe = dict(base_target)
            unsafe["source_files"] = ["../tools/helper.py"]
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


class Run5FixtureTests(unittest.TestCase):
    def test_run5_stale_pins_fail_on_target_specific_projects_and_tools(self) -> None:
        fixture = json.loads(RUN5_FIXTURE_PATH.read_text(encoding="utf-8"))
        config = alignment.load_config(
            ROOT / "tools/ci/nightly-dependency-targets.json"
        )
        targets = {target["name"]: target for target in config["targets"]}

        self.assertEqual(
            "06830f3820812cebe7451d198091b6da5c7c64e6",
            fixture["parent_sha"],
        )
        self.assertEqual(
            {
                "c8da31dd32c76eb878ecf6cdc153efcf8215e614",
                "96d269aa346322e5e46fff91ac5e05100c5edf02",
            },
            {item["child_parent_sha"] for item in fixture["stale_pins"]},
        )

        for stale_pin in fixture["stale_pins"]:
            target = targets[stale_pin["target"]]
            configured_paths = set(target["source_roots"]) | set(
                target["source_files"]
            )
            with self.subTest(target=stale_pin["target"]):
                self.assertTrue(stale_pin["differences"])
                for difference in stale_pin["differences"]:
                    self.assertIn(difference["path"], configured_paths)
                    check = alignment.make_source_check(
                        difference["path"],
                        difference["kind"],
                        difference["parent_object"],
                        difference["child_object"],
                    )
                    self.assertEqual("failed", check["status"])

    def test_evaluate_target_records_explicit_failed_paths(self) -> None:
        target = {
            "name": "benchmark",
            "mode": "parent_gitlinks",
            "repository": "https://example.com/group/project.git",
            "iot_reference_gitlink": "external/iot-reference-rx",
            "dependencies": ["Middleware/FreeRTOS/FreeRTOS-Kernel"],
            "source_roots": ["Projects/app"],
            "source_files": ["tools/helper.py"],
        }
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            alignment,
            "clone_target",
            return_value=(Path(temp), "main", "b" * 40),
        ), mock.patch.object(
            alignment,
            "read_gitlink",
            return_value="c" * 40,
        ), mock.patch.object(
            alignment,
            "run_git",
            return_value="",
        ), mock.patch.object(
            alignment,
            "compare_parent_gitlinks",
            return_value=[
                {"path": "Middleware/FreeRTOS/FreeRTOS-Kernel", "status": "passed"}
            ],
        ), mock.patch.object(
            alignment,
            "compare_parent_source_trees",
            return_value=[
                {"path": "Projects/app", "kind": "source_tree", "status": "failed"}
            ],
        ), mock.patch.object(
            alignment,
            "compare_parent_source_files",
            return_value=[
                {"path": "tools/helper.py", "kind": "source_file", "status": "failed"}
            ],
        ):
            result = alignment.evaluate_target(
                Path(temp), "a" * 40, target, Path(temp)
            )

        self.assertEqual("failed", result["status"])
        self.assertEqual(
            ["Projects/app", "tools/helper.py"],
            result["failed_paths"],
        )


if __name__ == "__main__":
    unittest.main()

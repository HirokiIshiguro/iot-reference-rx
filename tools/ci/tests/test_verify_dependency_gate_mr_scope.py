from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "tools/ci/verify_dependency_gate_mr_scope.py"
SPEC = importlib.util.spec_from_file_location("dependency_gate_scope", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)


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


class DependencyGateMrScopeTests(unittest.TestCase):
    BASE_CI = """stages:
  - nightly_matrix

workflow:
  rules:
    # Shared RX671 application/build inputs affect both the normal network image
    - when: always

matrix_job:
  stage: nightly_matrix
  trigger:
    branch: main
  variables:
    KEEP: "true"
  script:
    - echo bridge

other_job:
  script:
    - echo base
"""
    DEPENDENCY_CI = """stages:
  - dependency_check
  - nightly_matrix

workflow:
  rules:
    # Dependency-gate MRs validate checker-only changes.
    - when: always
    # Shared RX671 application/build inputs affect both the normal network image
    - when: always

nightly_dependency_contract:
  script:
    - echo contract

nightly_dependency_alignment:
  script:
    - echo live

matrix_job:
  stage: nightly_matrix
  needs:
    - job: nightly_dependency_alignment
      artifacts: true
  trigger:
    branch: $RX72N_TSIP_MBEDTLS13_PROJECT_REF
  variables:
    EXPECTED_BENCHMARK_COMMIT_SHA: "$RX72N_TSIP_MBEDTLS13_RESOLVED_SHA"
    KEEP: "true"
  script:
    - echo bridge

other_job:
  script:
    - echo base
"""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "--quiet")
        git(self.repo, "config", "user.name", "Codex Test")
        git(self.repo, "config", "user.email", "codex-test@example.invalid")
        for path in scope.ALLOWED_PATHS:
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("base\n", encoding="utf-8")
        (self.repo / ".gitlab-ci.yml").write_text(
            self.BASE_CI,
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "--quiet", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def commit_change(self, path: str) -> str:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("changed\n", encoding="utf-8")
        git(self.repo, "add", path)
        git(self.repo, "commit", "--quiet", "-m", "change")
        return git(self.repo, "rev-parse", "HEAD")

    def run_main(self, head: str, source_head: str = "") -> int:
        with (
            mock.patch.dict(
                scope.os.environ,
                {
                    "CI_MERGE_REQUEST_DIFF_BASE_SHA": self.base,
                    "CI_COMMIT_SHA": head,
                    "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": source_head,
                },
                clear=False,
            ),
            mock.patch.object(scope.subprocess, "run", wraps=subprocess.run),
        ):
            previous = Path.cwd()
            try:
                scope.os.chdir(self.repo)
                return scope.main()
            finally:
                scope.os.chdir(previous)

    def test_allowed_dependency_gate_change_passes(self) -> None:
        head = self.commit_change(
            "tools/ci/check_nightly_dependency_alignment.py"
        )
        self.assertEqual(0, self.run_main(head))

    def test_mixed_board_change_fails(self) -> None:
        self.commit_change("tools/ci/nightly-dependency-targets.json")
        head = self.commit_change("Projects/aws_wifi_rx671_ek/source.c")
        self.assertEqual(1, self.run_main(head))

    def test_invalid_sha_fails_closed(self) -> None:
        with mock.patch.dict(
            scope.os.environ,
            {
                "CI_MERGE_REQUEST_DIFF_BASE_SHA": "deadbeef",
                "CI_COMMIT_SHA": self.base,
            },
            clear=False,
        ):
            self.assertEqual(1, scope.main())

    def test_dependency_only_ci_regions_pass(self) -> None:
        (self.repo / ".gitlab-ci.yml").write_text(
            self.DEPENDENCY_CI,
            encoding="utf-8",
        )
        git(self.repo, "add", ".gitlab-ci.yml")
        git(self.repo, "commit", "--quiet", "-m", "dependency ci")
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(0, self.run_main(head))

    def test_real_ci_has_stable_dependency_workflow_boundaries(self) -> None:
        ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        self.assertIn(scope.DEPENDENCY_WORKFLOW_START, ci)
        self.assertIn(scope.DEPENDENCY_WORKFLOW_END, ci)
        stripped = scope.strip_dependency_ci_regions(ci)
        self.assertNotIn(scope.DEPENDENCY_WORKFLOW_START, stripped)
        self.assertIn(scope.DEPENDENCY_WORKFLOW_END, stripped)

    def test_dependency_bridge_submodule_strategy_override_passes(self) -> None:
        changed = self.DEPENDENCY_CI.replace(
            '    EXPECTED_BENCHMARK_COMMIT_SHA: '
            '"$RX72N_TSIP_MBEDTLS13_RESOLVED_SHA"',
            '    GIT_SUBMODULE_STRATEGY: "none"\n'
            '    EXPECTED_BENCHMARK_COMMIT_SHA: '
            '"$RX72N_TSIP_MBEDTLS13_RESOLVED_SHA"',
        )
        (self.repo / ".gitlab-ci.yml").write_text(changed, encoding="utf-8")
        git(self.repo, "add", ".gitlab-ci.yml")
        git(self.repo, "commit", "--quiet", "-m", "dependency bridge submodule")
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(0, self.run_main(head))

    def test_unrelated_change_in_ci_file_fails(self) -> None:
        changed = self.DEPENDENCY_CI.replace("echo base", "echo unrelated")
        (self.repo / ".gitlab-ci.yml").write_text(changed, encoding="utf-8")
        git(self.repo, "add", ".gitlab-ci.yml")
        git(self.repo, "commit", "--quiet", "-m", "mixed ci")
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(1, self.run_main(head))

    def test_unrelated_bridge_change_in_ci_file_fails(self) -> None:
        changed = self.DEPENDENCY_CI.replace("echo bridge", "echo changed")
        (self.repo / ".gitlab-ci.yml").write_text(changed, encoding="utf-8")
        git(self.repo, "add", ".gitlab-ci.yml")
        git(self.repo, "commit", "--quiet", "-m", "mixed bridge")
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(1, self.run_main(head))

    def test_merged_result_uses_source_sha_not_synthetic_merge(self) -> None:
        git(self.repo, "checkout", "--quiet", "-b", "source", self.base)
        source_head = self.commit_change(
            "tools/ci/check_nightly_dependency_alignment.py"
        )
        git(self.repo, "checkout", "--quiet", "-b", "target", self.base)
        target_head = self.commit_change("Projects/target-only.c")
        git(self.repo, "checkout", "--quiet", "-b", "merged", target_head)
        git(self.repo, "merge", "--quiet", "--no-ff", source_head, "-m", "merge")
        synthetic_merge = git(self.repo, "rev-parse", "HEAD")

        self.assertEqual(0, self.run_main(synthetic_merge, source_head))


if __name__ == "__main__":
    unittest.main()

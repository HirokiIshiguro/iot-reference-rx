#!/usr/bin/env python3
"""Reject mixed dependency-gate MRs whose board validation was disabled."""

from __future__ import annotations

import os
import re
import subprocess
import sys


SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_PATHS = {
    ".gitlab-ci.yml",
    "tools/ci/check_nightly_dependency_alignment.py",
    "tools/ci/nightly-dependency-targets.json",
    "tools/ci/tests/fixtures/nightly_dependency_alignment_run5.json",
    "tools/ci/tests/test_nightly_dependency_alignment.py",
    "tools/ci/tests/test_nightly_dependency_ci_contract.py",
    "tools/ci/tests/test_verify_dependency_gate_mr_scope.py",
    "tools/ci/verify_dependency_gate_mr_scope.py",
}
CI_PATH = ".gitlab-ci.yml"
DEPENDENCY_WORKFLOW_START = "    # Dependency-gate MRs validate"
DEPENDENCY_WORKFLOW_END = (
    "    # Shared RX671 application/build inputs affect both the normal network image"
)
DEPENDENCY_JOBS = (
    "nightly_dependency_contract",
    "nightly_dependency_alignment",
)
DEPENDENCY_NEEDS_BLOCK = (
    "  needs:\n"
    "    - job: nightly_dependency_alignment\n"
    "      artifacts: true\n"
)
DEPENDENCY_EXPECTED_SHA_RE = re.compile(
    r'(?m)^    EXPECTED_BENCHMARK_COMMIT_SHA: '
    r'"\$(?:RX671_SOFTWARE_BENCHMARK_RESOLVED_SHA|'
    r'RX671_BENCHMARK_RESOLVED_SHA|'
    r'RX72N_TSIP_MBEDTLS13_RESOLVED_SHA)"\r?\n'
)
DEPENDENCY_BRIDGE_SUBMODULE_STRATEGY_RE = re.compile(
    r'(?m)^    GIT_SUBMODULE_STRATEGY: "none"\r?\n'
    r'(?=    EXPECTED_BENCHMARK_COMMIT_SHA: '
    r'"\$(?:RX671_SOFTWARE_BENCHMARK_RESOLVED_SHA|'
    r'RX671_BENCHMARK_RESOLVED_SHA|'
    r'RX72N_TSIP_MBEDTLS13_RESOLVED_SHA)"\r?\n)'
)


def require_sha(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not SHA40_RE.fullmatch(normalized):
        raise RuntimeError(f"{label} must be a 40-character commit SHA")
    return normalized


def run_git(*args: str, capture: bool = True) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed with exit {completed.returncode}"
        )
    return completed.stdout or b""


def ensure_commit(commit: str) -> None:
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode == 0:
        return
    run_git("fetch", "--quiet", "--depth", "1", "origin", commit, capture=False)


def changed_paths(base_sha: str, head_sha: str) -> set[str]:
    ensure_commit(base_sha)
    ensure_commit(head_sha)
    raw = run_git(
        "diff",
        "--name-only",
        "-z",
        base_sha,
        head_sha,
        "--",
    )
    return {
        entry.decode("utf-8", errors="strict")
        for entry in raw.split(b"\0")
        if entry
    }


def read_blob(commit: str, path: str) -> str:
    raw = run_git("show", f"{commit}:{path}")
    return raw.decode("utf-8", errors="strict")


def remove_top_level_block(text: str, name: str) -> str:
    start_match = re.search(rf"(?m)^{re.escape(name)}:[ \t]*\r?$", text)
    if start_match is None:
        return text
    next_match = re.search(
        r"(?m)^[A-Za-z0-9_.-]+:[ \t]*\r?$",
        text[start_match.end() :],
    )
    end = (
        start_match.end() + next_match.start()
        if next_match is not None
        else len(text)
    )
    return text[: start_match.start()] + text[end:]


def strip_dependency_ci_regions(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(
        r"(?m)^(stages:\r?\n)  - dependency_check\r?\n",
        r"\1",
        text,
        count=1,
    )
    text = text.replace(DEPENDENCY_NEEDS_BLOCK, "")
    text = DEPENDENCY_BRIDGE_SUBMODULE_STRATEGY_RE.sub("", text)
    text = DEPENDENCY_EXPECTED_SHA_RE.sub("", text)
    text = text.replace(
        "    branch: $RX72N_TSIP_MBEDTLS13_PROJECT_REF\n",
        "    branch: main\n",
    )
    start = text.find(DEPENDENCY_WORKFLOW_START)
    if start >= 0:
        end = text.find(DEPENDENCY_WORKFLOW_END, start)
        if end < 0:
            raise RuntimeError("dependency workflow block has no end marker")
        text = text[:start] + text[end:]
    for job in DEPENDENCY_JOBS:
        text = remove_top_level_block(text, job)
    return text


def verify_ci_file_scope(base_sha: str, head_sha: str) -> None:
    base = strip_dependency_ci_regions(read_blob(base_sha, CI_PATH))
    head = strip_dependency_ci_regions(read_blob(head_sha, CI_PATH))
    if base != head:
        raise RuntimeError(
            ".gitlab-ci.yml also changes content outside the dependency "
            "workflow and dependency jobs"
        )


def main() -> int:
    try:
        base_sha = require_sha(
            os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", ""),
            "CI_MERGE_REQUEST_DIFF_BASE_SHA",
        )
        head_name = (
            "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA"
            if os.environ.get("CI_MERGE_REQUEST_SOURCE_BRANCH_SHA", "").strip()
            else "CI_COMMIT_SHA"
        )
        head_sha = require_sha(
            os.environ.get(head_name, ""),
            head_name,
        )
        changed = changed_paths(base_sha, head_sha)
        unexpected = sorted(changed - ALLOWED_PATHS)
        if not changed:
            raise RuntimeError("merge request contains no dependency-gate changes")
        if CI_PATH in changed:
            verify_ci_file_scope(base_sha, head_sha)
        if unexpected:
            print(
                "Dependency-gate MR also changes files that require the normal "
                "board validation lanes:",
                file=sys.stderr,
            )
            for path in unexpected:
                print(f"  {path}", file=sys.stderr)
            print(
                "Split dependency-gate changes into a dedicated merge request.",
                file=sys.stderr,
            )
            return 1
        print(
            f"Dependency-gate MR scope verified: {len(changed)} allowed file(s)."
        )
        return 0
    except (RuntimeError, OSError, UnicodeError) as exc:
        print(f"dependency-gate scope verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

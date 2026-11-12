#!/usr/bin/env python3
"""Reject runner-only MR profiles containing unrelated changes."""
import os
import sys

from tools.ci.verify_dependency_gate_mr_scope import (
    changed_paths, read_blob, remove_top_level_block, require_sha,
)

ALLOWED_PATHS = {
    ".gitlab-ci.yml",
    "tools/cleanup_iot_jobs.py",
    "tools/ci/tests/test_cleanup_iot_jobs.py",
    "tools/ci/tests/test_shared_flash_mr_workflow.py",
    "tools/ci/verify_ci_runner_mr_scope.py",
    "tools/ci/tests/test_ci_runner_mr_scope.py",
}
START = "    # BEGIN CI RUNNER MR WORKFLOW\n"
END = "    # END CI RUNNER MR WORKFLOW\n"


def strip_ci_regions(text):
    text = text.replace("\r\n", "\n")
    start = text.find(START)
    if start >= 0:
        end = text.find(END, start)
        if end < 0 or text.find(START, start + len(START)) >= 0 or text.find(END, end + len(END)) >= 0:
            raise RuntimeError("invalid runner workflow markers")
        text = text[:start] + text[end + len(END):]
    elif END in text:
        raise RuntimeError("invalid runner workflow markers")
    for job in ("ci_runner_mr_contract", "cleanup_rx72n_ether_ota_jobs"):
        text = remove_top_level_block(text, job)
    return text


def verify(base, head):
    changed = changed_paths(base, head)
    unexpected = sorted(changed - ALLOWED_PATHS)
    if not changed or unexpected:
        raise RuntimeError(f"empty or mixed runner MR; unexpected paths: {unexpected}")
    if ".gitlab-ci.yml" in changed:
        before = strip_ci_regions(read_blob(base, ".gitlab-ci.yml"))
        after = strip_ci_regions(read_blob(head, ".gitlab-ci.yml"))
        if before != after:
            raise RuntimeError("CI changes outside runner workflow and allowed jobs")


def main():
    try:
        base = require_sha(os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", ""), "CI_MERGE_REQUEST_DIFF_BASE_SHA")
        name = "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA" if os.environ.get("CI_MERGE_REQUEST_SOURCE_BRANCH_SHA", "").strip() else "CI_COMMIT_SHA"
        head = require_sha(os.environ.get(name, ""), name)
        verify(base, head)
        print("Runner MR scope verified")
        return 0
    except (RuntimeError, OSError, UnicodeError) as exc:
        print(f"runner MR scope verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

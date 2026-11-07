"""Reject mixed OIDC source changes before treating its reduced CI as valid."""
from __future__ import annotations

import os
import sys

from tools.ci.verify_dependency_gate_mr_scope import (
    changed_paths, read_blob, require_sha, run_git,
)

ALLOWED_PATHS = {
    ".gitlab-ci.yml", ".gitlab/ci/aws-oidc-probe.yml",
    "docs/aws-oidc-migration.md", "tools/aws/oidc_probe.py",
    "tools/aws/oidc-probe-trust.template.json", "tools/aws/oidc-probe-policy.json",
    "tools/ci/tests/test_aws_oidc_probe.py", "tools/ci/tests/test_aws_oidc_scope.py",
    "tools/ci/verify_aws_oidc_scope.py",
}
REGIONS = (
    ("  # OIDC include begin\n", "  # OIDC include end\n"),
    ("  # OIDC inputs begin\n", "  # OIDC inputs end\n"),
    ("    # OIDC workflows begin\n", "    # OIDC workflows end\n"),
)


def legacy_ci(text):
    text = text.replace("\r\n", "\n")
    for begin, end in REGIONS:
        if begin not in text and end not in text:
            continue
        if text.count(begin) != 1 or text.count(end) != 1:
            raise RuntimeError("OIDC CI region markers are ambiguous")
        start, stop = text.index(begin), text.index(end)
        if stop < start:
            raise RuntimeError("OIDC CI region markers are reversed")
        text = text[:start] + text[stop + len(end):]
    return text


def verify_scope(paths, base_ci, head_ci):
    if paths - ALLOWED_PATHS:
        raise RuntimeError("OIDC source validation cannot cover unrelated files")
    if legacy_ci(base_ci) != legacy_ci(head_ci):
        raise RuntimeError("OIDC source validation cannot cover changes to existing CI definitions")


def main():
    try:
        head = require_sha(run_git("rev-parse", "HEAD").decode(), "HEAD")
        if head != require_sha(os.environ.get("CI_COMMIT_SHA", ""), "CI_COMMIT_SHA"):
            raise RuntimeError("CI source differs from the checkout")
        if os.environ.get("CI_PIPELINE_SOURCE") == "merge_request_event":
            base = require_sha(os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", ""), "MR base")
        else:
            # Use the existing CI remote/authentication; never inspect credentials.
            # Fetch a commit, without moving any checked-out branch/worktree.
            if os.environ.get("CI_DEFAULT_BRANCH") != "main":
                raise RuntimeError("Unexpected default branch")
            run_git("fetch", "--quiet", "--depth", "1", "origin", "main", capture=False)
            base = require_sha(run_git("rev-parse", "FETCH_HEAD").decode(), "main")
        paths = changed_paths(base, head)
        verify_scope(paths, read_blob(base, ".gitlab-ci.yml"), read_blob(head, ".gitlab-ci.yml"))
        print(f"OIDC source scope verified: {len(paths)} allowed file(s), existing CI unchanged")
        return 0
    except (RuntimeError, OSError, UnicodeError):
        print("OIDC source scope verification failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

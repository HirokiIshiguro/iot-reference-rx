"""Fail closed for the three IDT documentation paths and their narrow CI lane."""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

try:
    from .verify_dependency_gate_mr_scope import ensure_commit, read_blob, remove_top_level_block, require_sha, run_git
except ImportError:
    from verify_dependency_gate_mr_scope import ensure_commit, read_blob, remove_top_level_block, require_sha, run_git


DOCS = {"README.md", "docs/idt-validation.md", "docs/ota-performance.md"}
BOOTSTRAP = {"tools/ci/check_idt_docs.py", "tools/ci/tests/test_idt_docs.py"}
BEGIN = "    # BEGIN IDT DOCS WORKFLOW\n"
END = "    # END IDT DOCS WORKFLOW\n"
DOC_BRANCH_RE = re.compile(r"^((codex|claude)/)?[0-9]+-(readme|docs)-")


def strip_docs_ci(text: str) -> str:
    text = text.replace("\r\n", "\n")
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise RuntimeError("IDT docs workflow markers are missing or duplicated")
        start, end = text.index(BEGIN), text.index(END)
        if end < start:
            raise RuntimeError("IDT docs workflow markers are out of order")
        text = text[:start] + text[end + len(END):]
    return remove_top_level_block(text, "idt_docs_check")


def verify_scope(changed: set[str], base_ci: str, head_ci: str) -> None:
    if not changed or changed - (DOCS | BOOTSTRAP | {".gitlab-ci.yml"}):
        raise RuntimeError("IDT docs lane requires a nonempty documentation-only MR; split mixed source changes")
    if ".gitlab-ci.yml" in changed and strip_docs_ci(base_ci) != strip_docs_ci(head_ci):
        raise RuntimeError("CI changes extend outside the IDT docs workflow/job")


def lint_document(path: Path) -> list[str]:
    errors = []
    fenced = False
    rows = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if raw.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        line = re.sub(r"`[^`]*`", "", raw)
        rows.append((number, line))
        for target in re.findall(r"\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", line):
            link = urlsplit(target.strip("<>"))
            if not link.scheme and not link.netloc and link.path:
                if not (path.parent / unquote(link.path)).exists():
                    errors.append(f"{path}:{number}: relative link target is missing: {link.path}")
    expected = None
    for index, (number, line) in enumerate(rows):
        if not line.strip().startswith("|"):
            expected = None
            continue
        cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
        if all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells):
            expected = len(cells)
            if index and len(re.split(r"(?<!\\)\|", rows[index - 1][1].strip().strip("|"))) != expected:
                errors.append(f"{path}:{number}: table header column count differs")
        elif expected is not None and len(cells) != expected:
            errors.append(f"{path}:{number}: table row column count differs")
    return errors


def main() -> int:
    try:
        if os.getenv("CI_PIPELINE_SOURCE") != "merge_request_event":
            raise RuntimeError("IDT docs lane is restricted to merge request pipelines")
        if not DOC_BRANCH_RE.match(os.getenv("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME", "")):
            raise RuntimeError("IDT docs lane requires an explicitly named docs/readme source branch")
        base = require_sha(os.getenv("CI_MERGE_REQUEST_DIFF_BASE_SHA", ""), "MR diff base")
        head = require_sha(os.getenv("CI_MERGE_REQUEST_SOURCE_BRANCH_SHA") or os.getenv("CI_COMMIT_SHA", ""), "MR source head")
        ensure_commit(base)
        ensure_commit(head)
        # A source-to-doc rename must still expose the removed source path.
        raw = run_git("diff", "--no-renames", "--name-only", "-z", base, head, "--")
        changed = {item.decode("utf-8") for item in raw.split(b"\0") if item}
        verify_scope(changed, read_blob(base, ".gitlab-ci.yml"), read_blob(head, ".gitlab-ci.yml"))
        errors = []
        for name in sorted(DOCS):
            path = Path(name)
            if path.is_file():
                errors.extend(lint_document(path))
        if errors:
            raise RuntimeError("\n".join(errors))
        print(f"IDT docs scope, relative links and tables verified ({len(changed)} changed paths)")
        return 0
    except (RuntimeError, OSError, UnicodeError, ValueError) as error:
        print("IDT docs verification failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

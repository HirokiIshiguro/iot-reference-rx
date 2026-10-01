from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.ci import check_idt_docs as docs


class IdtDocsTests(unittest.TestCase):
    BASE = "workflow:\n  rules:\n    - when: always\n\nnormal_build:\n  script: build\n"

    def test_docs_and_narrow_bootstrap_ci_are_allowed(self):
        changed = docs.DOCS | docs.BOOTSTRAP | {".gitlab-ci.yml"}
        head = self.BASE.replace("    - when: always\n", docs.BEGIN + "    - if: docs\n" + docs.END + "    - when: always\n")
        head = head.replace("\nnormal_build:", "\nidt_docs_check:\n  script: check\n\nnormal_build:")
        docs.verify_scope(changed, self.BASE, head)

    def test_mixed_code_other_docs_and_unrelated_ci_fail(self):
        for path in ("Projects/main.c", "docs/unrelated.md", "tools/test.py", ".gitmodules"):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                docs.verify_scope({"README.md", path}, self.BASE, self.BASE)
        with self.assertRaises(RuntimeError):
            docs.verify_scope({"README.md", ".gitlab-ci.yml"}, self.BASE, self.BASE.replace("script: build", "script: bypass"))
        with self.assertRaises(RuntimeError):
            docs.verify_scope(set(), self.BASE, self.BASE)

    def test_incomplete_or_repeated_region_markers_fail(self):
        for text in (self.BASE + docs.BEGIN, self.BASE + docs.BEGIN + docs.BEGIN + docs.END):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                docs.strip_docs_ci(text)

    def test_missing_relative_link_and_broken_table_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            path.write_text("[missing](absent.md)\n\n| A | B |\n|---|---|\n| one |\n", encoding="utf-8")
            errors = docs.lint_document(path)
            self.assertTrue(any("relative link" in error for error in errors))
            self.assertTrue(any("table row" in error for error in errors))
            (path.parent / "ok.md").write_text("ok", encoding="utf-8")
            path.write_text("[ok](ok.md#heading) [web](https://example.invalid/)\n| A | B |\n|---|---|\n| `x|y` | value |\n", encoding="utf-8")
            self.assertEqual([], docs.lint_document(path))

    def test_non_mr_cannot_use_docs_checker(self):
        with patch.dict(docs.os.environ, {"CI_PIPELINE_SOURCE": "api"}):
            self.assertEqual(1, docs.main())

    def test_mr_uses_source_sha_and_disables_rename_collapsing(self):
        base, source, merged = "a" * 40, "b" * 40, "c" * 40
        with patch.dict(docs.os.environ, {
            "CI_PIPELINE_SOURCE": "merge_request_event",
            "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "codex/160-readme-idt-performance",
            "CI_MERGE_REQUEST_DIFF_BASE_SHA": base,
            "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": source,
            "CI_COMMIT_SHA": merged,
        }), patch.object(docs, "ensure_commit"), patch.object(docs, "read_blob", return_value=self.BASE), patch.object(docs, "lint_document", return_value=[]), patch.object(docs, "run_git", return_value=b"README.md\0") as run:
            self.assertEqual(0, docs.main())
            run.assert_called_once_with("diff", "--no-renames", "--name-only", "-z", base, source, "--")
            run.return_value = b"README.md\0Projects/removed_source.c\0"
            self.assertEqual(1, docs.main())

    def test_only_explicit_docs_branch_names_match(self):
        for name in ("codex/160-readme-idt-performance", "claude/12-docs-links", "13-readme-update"):
            self.assertIsNotNone(docs.DOC_BRANCH_RE.match(name))
        for name in ("codex/161-idt-feature", "codex/161-feature-readme", "main", "codex/readme-update", ""):
            self.assertIsNone(docs.DOC_BRANCH_RE.match(name))

    def test_real_ci_changes_only_the_docs_regions(self):
        root = Path(__file__).resolve().parents[3]
        head = (root / ".gitlab-ci.yml").read_text(encoding="utf-8")
        self.assertIn(docs.BEGIN, head)
        self.assertIn('PIPELINE_PROFILE: "mr-idt-docs"', head)
        self.assertIn('$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME =~ /^((codex|claude)\\/)?[0-9]+-(readme|docs)-/', head)
        for name in ("RUN_RX72N_BUILD", "RUN_RX65N_BG96_BUILD", "RUN_RX671_WIFI_BUILD", "RUN_RX671_BOOTLOADER_BUILD"):
            lane = head.split(docs.BEGIN)[1].split(docs.END)[0]
            self.assertIn(f'{name}: "false"', lane)


if __name__ == "__main__":
    unittest.main()

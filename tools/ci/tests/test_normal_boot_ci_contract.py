"""Exercise the normal CI retained-owner stop before hardware mutations."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
CI = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
TEMPLATES = {
    ".rx72n_linux_hw_job": "rx72n-ethernet",
    ".rx65n_bg96_linux_hw_job": "rx65n-bg96",
    ".rx671_wifi_linux_hw_job": "rx671-wifi",
}


def job(name: str) -> str:
    match = re.search(r"(?m)^" + re.escape(name) + r":\n", CI)
    if match is None:
        raise AssertionError("Missing CI job: " + name)
    following = re.search(r"(?m)^[A-Za-z0-9_.-]+:\s*$", CI[match.end():])
    end = match.end() + following.start() if following else len(CI)
    return CI[match.start():end]


def owner_guard(template: str) -> str:
    lines = [line.strip() for line in job(template).splitlines()
             if "Retained hardware owner requires inspection" in line]
    if len(lines) != 1 or not lines[0].startswith('- python3 -c "') or not lines[0].endswith('"'):
        raise AssertionError("Expected one Python retained-owner guard")
    return lines[0][len('- python3 -c "'):-1]


class NormalBootCiContractTests(unittest.TestCase):
    def execute_guard(self, template: str, owner: Path):
        target = {"owner_file": str(owner)}
        with mock.patch("tools.idt.targets.get_target", return_value=target) as selected, \
             mock.patch("tools.idt.rfp_process.raise_if_rfp_unsafe") as unsafe:
            try:
                exec(compile(owner_guard(template), "<ci-owner-guard>", "exec"), {})
            finally:
                selected.assert_called_once_with(TEMPLATES[template])
                unsafe.assert_called_once_with(target)

    def test_clean_bench_without_owner_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            for template in TEMPLATES:
                with self.subTest(template=template):
                    self.execute_guard(template, Path(folder) / "absent-owner.json")

    def test_retained_owner_blocks_all_three_templates(self):
        with tempfile.TemporaryDirectory() as folder:
            owner = Path(folder) / "owner.json"
            owner.write_text("{}", encoding="utf-8")
            for template in TEMPLATES:
                with self.subTest(template=template):
                    with self.assertRaisesRegex(SystemExit, "Retained hardware owner"):
                        self.execute_guard(template, owner)

    def test_dangling_owner_symlink_also_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            owner = Path(folder) / "owner.json"
            try:
                owner.symlink_to(Path(folder) / "missing.json")
            except OSError as error:
                self.skipTest("Symlink creation unavailable: " + type(error).__name__)
            self.assertFalse(owner.exists())
            for template in TEMPLATES:
                with self.subTest(template=template):
                    with self.assertRaisesRegex(SystemExit, "Retained hardware owner"):
                        self.execute_guard(template, owner)

if __name__ == "__main__":
    unittest.main()

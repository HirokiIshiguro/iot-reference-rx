"""Shared Flash changes must win over narrower first-match MR workflow lanes."""
from __future__ import annotations

import fnmatch
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]


def mr_variables(ci: str, changed: set[str], branch: str = "codex/180-nested-interrupts") -> dict[str, str]:
    """Read only existing MR workflow rule forms, preserving first-match order."""
    workflow = re.split(r"(?m)^[A-Za-z0-9_.-]+:[ \t]*$",
                        ci.split("\nworkflow:\n", 1)[1], maxsplit=1)[0]
    for rule in re.split(r"(?m)(?=^    - if:)", workflow):
        condition = re.search(r"^    - if: '([^\n]+)'", rule, re.MULTILINE)
        if condition is None or '$CI_PIPELINE_SOURCE == "merge_request_event"' not in condition[1]:
            continue
        branch_pattern = re.search(r"\$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME =~ /(.+)/", condition[1])
        if branch_pattern and re.search(branch_pattern[1].replace(r"\/", "/"), branch) is None:
            continue
        changes = re.findall(r"^        - (\S+)\s*$", rule, re.MULTILINE)
        if changes and not any(
            fnmatch.fnmatchcase(path, pattern) or
            fnmatch.fnmatchcase(path, pattern.replace("/**/", "/"))
            for path in changed for pattern in changes
        ):
            continue
        return dict(re.findall(r'^        ([A-Z0-9_]+): "([^"\n]*)"', rule, re.MULTILINE))
    raise AssertionError("No matching MR workflow rule")


class SharedFlashMrWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

    def assert_three_board_coverage(self, selected: dict[str, str]) -> None:
        self.assertEqual(selected["PIPELINE_PROFILE"], "mr-shared-flash")
        for board, scope in (("RX65N_BG96", "mqtt"), ("RX72N", "mqtt"), ("RX671_WIFI", "mqtt")):
            self.assertEqual(selected[f"{board}_TEST_SCOPE"], scope)
            self.assertEqual(selected[f"{board}_SKIP_HW_TESTS"], "false")
        for flag in ("RUN_RX65N_BG96_BUILD", "RUN_RX72N_BUILD", "RUN_RX671_WIFI_BUILD",
                     "RUN_RX671_BOOTLOADER_BUILD", "RUN_RX671_OTA_ARTIFACT_BUILD"):
            self.assertEqual(selected[flag], "true")
        # Signed artifact coverage does not opt into OTA/Fleet/IDT/device smoke.
        for flag in ("RUN_RX671_OTA_TEST", "RUN_RX72N_OTA_TESTS", "RUN_RX72N_FLEET_TESTS",
                     "RUN_RX_IDT", "RUN_RX671_BOOTLOADER_SMOKE"):
            self.assertNotIn(flag, selected)

    def test_shared_flash_gitlink_selects_three_boards(self) -> None:
        self.assert_three_board_coverage(mr_variables(self.ci, {"Middleware/Renesas/r_flash_rx"}))

    def test_issue180_mixed_flash_and_ota_diff_inputs_do_not_fall_into_ota_only_lane(self) -> None:
        self.assert_three_board_coverage(mr_variables(self.ci, {
            ".gitlab-ci.yml", "Middleware/Renesas/r_flash_rx", "manifest.yml",
            "tools/build_rx671_ota_images.py", "tools/ci/analyze_rx671_ota_layout.py",
            "Projects/aws_wifi_rx671_ek/e2studio_ccrx/aws_wifi_rx671_ek.scfg",
            "tools/install_normal_boot.py",
        }))

    def test_dependency_gate_keeps_priority_and_narrow_rx671_lanes_remain(self) -> None:
        self.assertEqual(mr_variables(self.ci, {
            "tools/ci/check_nightly_dependency_alignment.py",
        })["PIPELINE_PROFILE"], "mr-dependency-gate")
        self.assertEqual(mr_variables(self.ci, {
            "tools/ci/check_nightly_dependency_alignment.py", "Middleware/Renesas/r_flash_rx",
        })["PIPELINE_PROFILE"], "mr-dependency-gate")
        for path, profile in (
            ("tools/build_rx671_ota_images.py", "mr-rx671-ota-artifacts"),
            ("Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/sdio_host.c", "mr-rx671-ota-and-network"),
            ("Projects/aws_wifi_rx671_ek/README.md", "mr-rx671"),
            ("Projects/aws_wifi_rx671_ek/e2studio_ccrx/aws_wifi_rx671_ek.scfg", "mr-rx671"),
            ("Projects/aws_wifi_rx671_ek/e2studio_ccrx/.project", "mr-rx671"),
            ("Projects/boot_loader_rx671_ek/README.md", "mr-rx671-bootloader"),
        ):
            with self.subTest(path=path):
                self.assertEqual(mr_variables(self.ci, {path})["PIPELINE_PROFILE"], profile)

    def test_other_driver_and_document_changes_do_not_enter_shared_flash_lane(self) -> None:
        for path in ("Middleware/Renesas/r_cellular", "README.md", "tools/install_normal_boot.py"):
            with self.subTest(path=path):
                self.assertEqual(mr_variables(self.ci, {path})["PIPELINE_PROFILE"], "mr")

    def test_selected_iot_job_precheck_is_read_only(self) -> None:
        # There is one tracked production caller; retain the explicit no-cancel mode.
        blocks = re.split(r"(?m)(?=^[A-Za-z0-9_.-]+:\s*$)", self.ci)
        callers = [b for b in blocks if re.search(r"python\s+tools[\\/]cleanup_iot_jobs\.py", b)]
        self.assertEqual(len(callers), 1)
        self.assertTrue(callers[0].startswith("cleanup_rx72n_ether_ota_jobs:"))
        self.assertIn("--check-empty", callers[0])
        self.assertNotIn("--force", callers[0])


if __name__ == "__main__":
    unittest.main()

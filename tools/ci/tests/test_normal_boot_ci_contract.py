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

    def test_owner_check_runs_after_the_bench_flock(self):
        for template in TEMPLATES:
            with self.subTest(template=template):
                body = job(template)
                self.assertLess(body.index("flock "), body.index("Retained hardware owner"))
                self.assertNotIn("assert ", owner_guard(template))
                self.assertIn("os.path.lexists", owner_guard(template))

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

    def test_linux_host_contracts_include_new_portable_checks(self):
        contract = job("idt_ci_contract")
        for name in ("test_rx72n_tsip_driver", "test_normal_boot",
                     "test_bg96_bootloader_download", "test_bg96_ota_prepare"):
            self.assertIn("tools.ci.tests." + name, contract)
        self.assertNotIn("tools.ci.tests.test_build_bg96_ota_candidate", contract)

    def test_candidate_wrapper_checks_run_on_windows_build_runner(self):
        build = job("build_rx65n_bg96")
        self.assertIn("- os-windows", build)
        self.assertIn("tools.ci.tests.test_build_bg96_ota_candidate", build)

    def test_bg96_persistent_keys_and_ota_loss_retries_are_checked_before_build(self):
        build = job("build_rx65n_bg96")
        self.assertIn("tools.ci.tests.test_idt_bg96_network", build)
        self.assertLess(build.index("tools.ci.tests.test_idt_bg96_network"),
                        build.index("RX65N BG96 host regression tests failed"))
        self.assertLess(build.index("RX65N BG96 host regression tests failed"),
                        build.index("python -m pip install"))
        self.assertIn("$LASTEXITCODE -ne 0", build)
        self.assertIn("tools.ci.tests.test_ota_request_retry", job("idt_ci_contract"))

    def test_bg96_tsip_lane_is_source_only_and_uses_the_shared_compiler_lease(self):
        lane = job("build_rx65n_tsip_common_core")
        for text in ("extends: build_rx65n_bg96", "resource_group: $WINDOWS_CCRX_BUILD_RESOURCE_GROUP",
                     '$CI_PIPELINE_SOURCE == "merge_request_event"', '$PIPELINE_PROFILE == "mr-idt-targets"',
                     'RX65N_BG96_TLS_BACKEND: "tsip"', 'RX65N_BG96_REQUIRE_TLS_VERSION: "TLSv1.2"',
                     'RX65N_BG96_TLS13_0RTT_ENABLE: "false"', 'RX65N_BG96_TEST_SCOPE: "build"'):
            self.assertIn(text, lane)
        self.assertNotIn("when: manual", lane)
        self.assertNotIn("install_normal_boot.py", lane)


if __name__ == "__main__":
    unittest.main()

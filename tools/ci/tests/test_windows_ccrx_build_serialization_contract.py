from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESOURCE_GROUP_VARIABLE = "$WINDOWS_CCRX_BUILD_RESOURCE_GROUP"
EXPECTED_CCRX_BUILD_JOBS = {
    "build_rx72n_ether",
    "build_rx65n_bg96",
    "build_rx671_wifi",
    "build_rx671_wifi_fleet",
    "build_rx671_bootloader",
    "package_rx671_ota_artifacts",
    "build_rx65n_bg96_fleet",
    "build_rx72n_ether_fleet",
    "build_rx65n_bg96_ota",
    "build_rx72n_ether_mqtt_candidate",
    "build_rx72n_ether_ota",
}


def top_level_job_blocks(ci: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^([A-Za-z0-9_.-]+):\s*$", ci))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(ci)
        blocks[match.group(1)] = ci[match.start():end]
    return blocks


class WindowsCcrxBuildSerializationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        cls.jobs = top_level_job_blocks(cls.ci)

    def test_all_e2studio_ccrx_build_jobs_are_covered(self) -> None:
        detected = {
            name
            for name, block in self.jobs.items()
            if "- ccrx" in block
            and re.search(
                r"(?:build_headless|--e2studio|-E2Studio|E2STUDIO_CLI)",
                block,
            )
        }

        self.assertEqual(EXPECTED_CCRX_BUILD_JOBS, detected)

    def test_all_e2studio_ccrx_build_jobs_share_one_resource_group(self) -> None:
        self.assertIn(
            'WINDOWS_CCRX_BUILD_RESOURCE_GROUP: '
            '"ishiguro-pc-ccrx-e2studio-build"',
            self.ci,
        )
        for name in sorted(EXPECTED_CCRX_BUILD_JOBS):
            with self.subTest(job=name):
                self.assertIn(
                    f"resource_group: {RESOURCE_GROUP_VARIABLE}",
                    self.jobs[name],
                )


if __name__ == "__main__":
    unittest.main()

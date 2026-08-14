from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
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
RX72N_CCRX_PROJECT_FILES = (
    "Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/.cproject",
    "Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx/.cproject",
    "Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/.cproject",
)


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

    def test_rx72n_ccrx_projects_use_bounded_parallelism(self) -> None:
        for relative_path in RX72N_CCRX_PROJECT_FILES:
            with self.subTest(project=relative_path):
                project_file = ROOT / relative_path
                root = ET.parse(project_file).getroot()
                builders = [
                    builder
                    for builder in root.iter("builder")
                    if builder.get("name") == "CCRX Builder"
                ]

                self.assertEqual(1, len(builders))
                self.assertEqual("true", builders[0].get("parallelBuildOn"))
                self.assertEqual("4", builders[0].get("parallelizationNumber"))


if __name__ == "__main__":
    unittest.main()

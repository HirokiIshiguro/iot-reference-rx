from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class WindowsCcrxBuildSerializationContractTests(unittest.TestCase):
    def test_ccrx_projects_use_automatic_parallelism(self) -> None:
        projects = sorted(ROOT.glob("Projects/*/e2studio_ccrx/.cproject"))
        self.assertTrue(projects)
        for project_file in projects:
            with self.subTest(project=project_file.relative_to(ROOT)):
                root = ET.parse(project_file).getroot()
                builders = [
                    builder
                    for builder in root.iter("builder")
                    if builder.get("name") == "CCRX Builder"
                ]

                self.assertEqual(1, len(builders))
                self.assertEqual("true", builders[0].get("parallelBuildOn"))
                self.assertEqual("optimal", builders[0].get("parallelizationNumber"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


class NightlyDependencyCiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        cls.config = json.loads(
            (ROOT / "tools/ci/nightly-dependency-targets.json").read_text(
                encoding="utf-8"
            )
        )

    def test_dependency_stage_precedes_every_nightly_bridge(self) -> None:
        stage_list = self.ci.split("variables:\n", maxsplit=1)[0]
        self.assertLess(
            stage_list.index("  - dependency_check"),
            stage_list.index("  - nightly_matrix"),
        )

        job = job_block(
            self.ci,
            "nightly_dependency_alignment",
            ".nightly_matrix_trigger",
        )
        self.assertIn("stage: dependency_check", job)
        self.assertIn('GIT_SUBMODULE_STRATEGY: "none"', job)
        self.assertIn(
            "tools.ci.tests.test_nightly_dependency_alignment",
            job,
        )
        self.assertIn(
            "tools.ci.tests.test_nightly_dependency_ci_contract",
            job,
        )
        self.assertIn("tools/ci/check_nightly_dependency_alignment.py", job)
        self.assertIn("artifacts/nightly_dependency_alignment.json", job)
        self.assertIn('$PIPELINE_PROFILE == "nightly_matrix"', job)

    def test_all_external_benchmark_refs_are_checked(self) -> None:
        configured_refs = {
            target["ref_env"] for target in self.config["targets"]
        }
        self.assertEqual(
            {
                "RX671_SOFTWARE_BENCHMARK_PROJECT_REF",
                "RX671_BENCHMARK_PROJECT_REF",
                "RX72N_TSIP_MBEDTLS13_PROJECT_REF",
            },
            configured_refs,
        )

        for ref_env in configured_refs:
            with self.subTest(ref_env=ref_env):
                self.assertIn(f"branch: ${ref_env}", self.ci)

    def test_policy_covers_kernel_and_every_used_aws_library(self) -> None:
        for target in self.config["targets"]:
            with self.subTest(target=target["name"]):
                dependencies = target["dependencies"]
                self.assertIn(
                    "Middleware/FreeRTOS/FreeRTOS-Kernel",
                    dependencies,
                )
                self.assertTrue(
                    any(path.startswith("Middleware/AWS/") for path in dependencies)
                )
                self.assertEqual(len(dependencies), len(set(dependencies)))


if __name__ == "__main__":
    unittest.main()

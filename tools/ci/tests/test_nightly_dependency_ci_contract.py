from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


def top_level_blocks(ci: str) -> dict[str, str]:
    headers = list(
        re.finditer(r"(?m)^(?P<name>[A-Za-z0-9_.-]+):[ \t]*$", ci)
    )
    return {
        match.group("name"): ci[
            match.start() : (
                headers[index + 1].start()
                if index + 1 < len(headers)
                else len(ci)
            )
        ]
        for index, match in enumerate(headers)
    }


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
        self.assertIn("artifacts/nightly_dependency_alignment.env", job)
        self.assertIn("dotenv: artifacts/nightly_dependency_alignment.env", job)
        self.assertIn('$PIPELINE_PROFILE == "nightly_matrix"', job)

    def test_external_bridge_project_ref_and_resolved_sha_mapping_is_exact(
        self,
    ) -> None:
        configured = {
            (
                target["project"],
                target["ref_env"],
                target["resolved_ref_env"],
            )
            for target in self.config["targets"]
        }
        self.assertEqual(
            {
                (
                    "oss/experiment/embedded/mcu/renesas/rx/example/"
                    "ek-rx671/benchmark/mbedtls",
                    "RX671_SOFTWARE_BENCHMARK_PROJECT_REF",
                    "RX671_SOFTWARE_BENCHMARK_RESOLVED_SHA",
                ),
                (
                    "oss/experiment/embedded/mcu/renesas/rx/example/"
                    "ek-rx671/benchmark/tsip_mbedtls",
                    "RX671_BENCHMARK_PROJECT_REF",
                    "RX671_BENCHMARK_RESOLVED_SHA",
                ),
                (
                    "oss/experiment/embedded/mcu/renesas/rx/example/"
                    "rx72n_envision_kit/benchmark/tsip_mbedtls13",
                    "RX72N_TSIP_MBEDTLS13_PROJECT_REF",
                    "RX72N_TSIP_MBEDTLS13_RESOLVED_SHA",
                ),
            },
            configured,
        )

        actual: set[tuple[str, str, str]] = set()
        for name, block in top_level_blocks(self.ci).items():
            project_match = re.search(r"(?m)^    project: (\S+)$", block)
            if project_match is None:
                continue
            branch_match = re.search(
                r"(?m)^    branch: \$([A-Z][A-Z0-9_]*)$",
                block,
            )
            resolved_match = re.search(
                r'(?m)^    EXPECTED_BENCHMARK_COMMIT_SHA: '
                r'"\$([A-Z][A-Z0-9_]*)"$',
                block,
            )
            with self.subTest(job=name):
                self.assertIsNotNone(branch_match)
                self.assertIsNotNone(resolved_match)
                self.assertIn("job: nightly_dependency_alignment", block)
                self.assertIn("artifacts: true", block)
            if branch_match is not None and resolved_match is not None:
                actual.add(
                    (
                        project_match.group(1),
                        branch_match.group(1),
                        resolved_match.group(1),
                    )
                )
        self.assertEqual(configured, actual)

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

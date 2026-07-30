from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str | None = None) -> str:
    block = ci.split(f"{name}:\n", maxsplit=1)[1]
    if next_name is not None:
        return block.split(f"\n{next_name}:\n", maxsplit=1)[0]
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if index and line and not line[0].isspace() and line.endswith(":"):
            return "\n".join(lines[:index])
    return block


class OtaAwsEvidenceCiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

    def test_rx65n_cleanup_is_fail_closed_and_preserves_evidence(self) -> None:
        job = job_block(
            self.ci,
            "cleanup_rx65n_bg96_ota",
            "cleanup_rx65n_bg96_mqtt_credentials",
        )
        self._assert_cleanup_contract(job, "cleanup_rx65n_bg96_ota")

    def test_rx72n_cleanup_is_fail_closed_and_preserves_evidence(self) -> None:
        job = job_block(self.ci, "cleanup_rx72n_ether_ota")
        self._assert_cleanup_contract(job, "cleanup_rx72n_ether_ota")

    def test_rx65n_static_mqtt_credentials_cleanup_is_explicit_noop(
        self,
    ) -> None:
        job = job_block(
            self.ci,
            "cleanup_rx65n_bg96_mqtt_credentials",
            "flash_rx72n_ether_fleet",
        )
        self.assertNotIn("allow_failure: true", job)
        self.assertIn("when: always", job)
        self.assertIn(
            '$mode -cnotin @("static", "static-tsip")',
            job,
        )
        self.assertIn(
            "Unknown BG96 credential mode '$mode'; refusing cleanup.",
            job,
        )
        self.assertIn(
            "Static BG96 credential mode '$mode' unexpectedly includes "
            "dynamic metadata; refusing cleanup.",
            job,
        )
        self.assertIn("credential_mode = $mode", job)
        self.assertIn('cleanup_action = "no-op"', job)
        self.assertIn("dynamic_metadata_present = $false", job)
        self.assertIn("passed = $true", job)
        self.assertIn(
            "Set-Content -LiteralPath $outPath -Encoding utf8 "
            "-ErrorAction Stop",
            job,
        )
        unknown_mode = job[
            job.index('if ($mode -cnotin @("static", "static-tsip"))'):
            job.index("if ($hasMeta)")
        ]
        self.assertIn("exit 1", unknown_mode)
        static_with_meta = job[
            job.index("if ($hasMeta)"):
            job.index("$summary = [ordered]@{")
        ]
        self.assertIn("exit 1", static_with_meta)
        self.assertLess(
            job.index('cleanup_action = "no-op"'),
            job.index("python tools/cleanup_bg96_iot_credentials.py"),
        )
        self.assertLess(
            job.index("exit 0"),
            job.index("python tools/cleanup_bg96_iot_credentials.py"),
        )

    def test_rx65n_dynamic_mqtt_credential_cleanup_is_fail_closed(
        self,
    ) -> None:
        job = job_block(
            self.ci,
            "cleanup_rx65n_bg96_mqtt_credentials",
            "flash_rx72n_ether_fleet",
        )
        self.assertNotIn("allow_failure: true", job)
        self.assertIn("$hasMode = Test-Path -LiteralPath $modePath", job)
        self.assertIn("$hasMeta = Test-Path -LiteralPath $metaPath", job)
        self.assertIn("if ($hasMode)", job)
        self.assertIn("if ($hasMeta)", job)
        self.assertIn("if (-not $hasMeta)", job)
        self.assertIn(
            "BG96 credential mode and dynamic metadata are both missing; "
            "cleanup cannot be verified.",
            job,
        )
        missing_both = job[
            job.index("if (-not $hasMeta)"):
            job.index("python tools/cleanup_bg96_iot_credentials.py")
        ]
        self.assertIn("exit 1", missing_both)

        self.assertIn(
            "python tools/cleanup_bg96_iot_credentials.py",
            job,
        )
        self.assertIn("$cleanupStatus = $LASTEXITCODE", job)
        self.assertIn("if ($cleanupStatus -ne 0)", job)
        self.assertIn("exit $cleanupStatus", job)

    def test_ota_creators_persist_partial_metadata_before_create(self) -> None:
        for relative_path in (
            "tools/create_bg96_ota_update.py",
            "tools/create_ota_update.py",
        ):
            with self.subTest(relative_path=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                upload = source.index('"put-object"')
                partial_meta = source.index("write_json(meta_path, meta)")
                create = source.index('"create-ota-update"')

                self.assertLess(upload, partial_meta)
                self.assertLess(partial_meta, create)
                self.assertIn(
                    "write_meta(meta_path, meta, **create_updates)",
                    source,
                )
                self.assertIn("meta_path=meta_path", source)

    def test_general_ci_changes_do_not_start_dependency_only_contract(self) -> None:
        contract = job_block(
            self.ci,
            "nightly_dependency_contract",
            "nightly_dependency_alignment",
        )
        rules = contract.split("  script:\n", maxsplit=1)[0]
        self.assertNotIn("        - .gitlab-ci.yml", rules)

    def _assert_cleanup_contract(self, job: str, artifact_name: str) -> None:
        self.assertNotIn("allow_failure: true", job)
        snapshot = "tools/verify_ota_aws_state.py snapshot"
        cleanup = "tools/verify_ota_aws_state.py cleanup"
        self.assertIn(snapshot, job)
        self.assertIn(cleanup, job)
        self.assertLess(job.index(snapshot), job.index(cleanup))
        self.assertIn("pre_cleanup_state.json", job)
        self.assertIn("post_cleanup_state.json", job)
        self.assertIn(f"artifacts/{artifact_name}/", job)
        self.assertIn('when: always', job)


if __name__ == "__main__":
    unittest.main()

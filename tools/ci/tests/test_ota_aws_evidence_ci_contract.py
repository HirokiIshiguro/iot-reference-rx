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

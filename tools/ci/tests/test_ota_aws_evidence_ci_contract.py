from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import create_bg96_ota_update
from tools import create_ota_update


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

                self.assertLess(partial_meta, upload)
                self.assertLess(partial_meta, create)
                self.assertLess(upload, create)
                self.assertIn('"ota_update_status": "UPLOAD_REQUESTED"', source)
                self.assertLess(
                    source.index('"signed_prefix":'),
                    partial_meta,
                )
                self.assertIn('ota_update_status="S3_UPLOADED"', source)
                self.assertIn("uuid.uuid4().hex[:12]", source)
                self.assertIn(
                    "write_meta(meta_path, meta, **create_updates)",
                    source,
                )
                self.assertIn("meta_path=meta_path", source)

    def test_ota_creators_reject_unowned_signer_prefix(self) -> None:
        for validator in (
            create_bg96_ota_update.validate_signed_prefix,
            create_ota_update.validate_signed_prefix,
        ):
            with self.subTest(validator=validator.__module__):
                validator(
                    "pipeline-thing",
                    "ota-id",
                    "ota/pipeline-thing/signed/ota-id/",
                )
                with self.assertRaisesRegex(ValueError, "OTA update"):
                    validator(
                        "pipeline-thing",
                        "ota-id",
                        "ota/other-thing/signed/ota-id/",
                    )
                with self.assertRaisesRegex(ValueError, "OTA update"):
                    validator(
                        "pipeline-thing",
                        "ota-id",
                        "ota/pipeline-thing/signed/other-ota/",
                    )
                with self.assertRaisesRegex(ValueError, "OTA update"):
                    validator(
                        "pipeline-thing",
                        "ota-id",
                        "ota/pipeline-thing/signed/ota-id",
                    )

    def test_ota_creators_reject_unowned_source_key(self) -> None:
        for creator in (
            create_bg96_ota_update,
            create_ota_update,
        ):
            with self.subTest(creator=creator.__name__):
                with self.assertRaisesRegex(ValueError, "source key"):
                    creator.validate_source_key(
                        "pipeline-thing",
                        "ota-id",
                        "ota/different-thing/source/candidate.rsu",
                    )
                with self.assertRaisesRegex(ValueError, "source key"):
                    creator.validate_source_key(
                        "pipeline-thing",
                        "ota-id",
                        "ota/pipeline-thing/source/other-ota/candidate.rsu",
                    )
                creator.validate_source_key(
                    "pipeline-thing",
                    "ota-id",
                    "ota/pipeline-thing/source/ota-id/candidate.rsu",
                )

    def test_ota_creator_path_templates_expand_generated_identity(
        self,
    ) -> None:
        for creator in (
            create_bg96_ota_update,
            create_ota_update,
        ):
            with self.subTest(creator=creator.__name__):
                self.assertEqual(
                    "ota/pipeline-thing/source/ota-id/candidate.rsu",
                    creator.expand_ota_path_template(
                        "ota/{thing_name}/source/{ota_update_id}/candidate.rsu",
                        "pipeline-thing",
                        "ota-id",
                    ),
                )

    def test_ota_creator_json_replacement_is_atomic(self) -> None:
        for creator in (
            create_bg96_ota_update,
            create_ota_update,
        ):
            with self.subTest(creator=creator.__name__):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "ota_job_meta.json"
                    path.write_text('{"state": "old"}\n', encoding="utf-8")
                    with (
                        patch.object(
                            creator.os,
                            "replace",
                            side_effect=OSError("simulated replace failure"),
                        ),
                        self.assertRaisesRegex(
                            OSError,
                            "simulated replace failure",
                        ),
                    ):
                        creator.write_json(path, {"state": "new"})

                    self.assertEqual(
                        {"state": "old"},
                        json.loads(path.read_text(encoding="utf-8")),
                    )
                    self.assertEqual(
                        [],
                        list(path.parent.glob(f".{path.name}.*.tmp")),
                    )
                    creator.write_json(path, {"state": "new"})
                    self.assertTrue(
                        path.read_text(encoding="utf-8").endswith("\n")
                    )
                    self.assertEqual(
                        {"state": "new"},
                        json.loads(path.read_text(encoding="utf-8")),
                    )
                    with (
                        patch.object(
                            creator.os,
                            "fsync",
                            side_effect=OSError("simulated fsync failure"),
                        ),
                        self.assertRaisesRegex(
                            OSError,
                            "simulated fsync failure",
                        ),
                    ):
                        creator.write_json(path, {"state": "not-committed"})
                    self.assertEqual(
                        {"state": "new"},
                        json.loads(path.read_text(encoding="utf-8")),
                    )
                    creator.write_meta(path, {"state": "new"}, step=1)
                    creator.write_meta(path, {"state": "new"}, step=2)
                    self.assertEqual(
                        {"state": "new", "step": 2},
                        json.loads(path.read_text(encoding="utf-8")),
                    )
                    self.assertEqual(
                        [],
                        list(path.parent.glob(f".{path.name}.*.tmp")),
                    )

    def test_ota_creators_journal_signer_id_during_status_poll(self) -> None:
        payload = {
            "otaUpdateInfo": {
                "otaUpdateFiles": [
                    {
                        "codeSigning": {
                            "awsSignerJobId": "signing-job",
                        }
                    }
                ]
            }
        }
        for creator in (
            create_bg96_ota_update,
            create_ota_update,
        ):
            with self.subTest(creator=creator.__name__):
                self.assertEqual(
                    "signing-job",
                    creator.ota_meta_updates(payload)["signing_job_id"],
                )

    def test_rx72_creator_writes_owned_prefix_before_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "candidate.rsu"
            payload.write_bytes(b"candidate")
            artifact_dir = root / "artifacts"
            journal_at_upload: dict = {}

            def fake_run(args, region, cwd=None):
                del region, cwd
                if args[:2] == ["iot", "describe-thing"]:
                    return SimpleNamespace(
                        stdout=json.dumps({"thingArn": "arn:thing"}),
                    )
                if args[:2] == ["s3api", "put-object"]:
                    journal_at_upload.update(
                        json.loads(
                            (artifact_dir / "ota_job_meta.json").read_text(
                                encoding="utf-8"
                            )
                        )
                    )
                    raise RuntimeError("stop after journal")
                self.fail(f"unexpected AWS call: {args}")

            argv = [
                "create_ota_update.py",
                "--artifact-dir",
                str(artifact_dir),
                "--thing-name",
                "pipeline-thing",
                "--input-rsu",
                str(payload),
                "--file-version",
                "2.06.0",
                "--bucket",
                "bucket",
                "--signing-profile",
                "profile",
                "--role-arn",
                "arn:role",
                "--region",
                "us-test-1",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(
                    create_ota_update,
                    "run_aws",
                    side_effect=fake_run,
                ),
                self.assertRaisesRegex(RuntimeError, "after journal"),
            ):
                create_ota_update.main()

        self.assertEqual("aws-signer", journal_at_upload["code_signing_mode"])
        self.assertTrue(
            journal_at_upload["signed_prefix"].startswith(
                "ota/pipeline-thing/signed/"
            )
        )
        self.assertIn(
            journal_at_upload["ota_update_id"],
            journal_at_upload["signed_prefix"],
        )
        self.assertIn(
            journal_at_upload["ota_update_id"],
            journal_at_upload["s3_key"],
        )

    def test_bg96_creator_writes_owned_prefix_before_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "candidate.rsu"
            payload.write_bytes(b"candidate")
            artifact_dir = root / "artifacts"
            journal_at_upload: dict = {}

            def fake_aws(args, region):
                del region
                if args[:2] == ["iot", "describe-thing"]:
                    return {"thingArn": "arn:thing"}
                if args[:2] == ["s3api", "put-object"]:
                    journal_at_upload.update(
                        json.loads(
                            (artifact_dir / "ota_job_meta.json").read_text(
                                encoding="utf-8"
                            )
                        )
                    )
                    raise RuntimeError("stop after journal")
                self.fail(f"unexpected AWS call: {args}")

            argv = [
                "create_bg96_ota_update.py",
                "--artifact-dir",
                str(artifact_dir),
                "--thing-name",
                "pipeline-thing",
                "--input-payload",
                str(payload),
                "--file-version",
                "2.06.0",
                "--bucket",
                "bucket",
                "--signing-profile",
                "profile",
                "--role-arn",
                "arn:role",
                "--region",
                "us-test-1",
                "--ota-update-id",
                "preplanned-ota-9402-60191",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(
                    create_bg96_ota_update,
                    "aws",
                    side_effect=fake_aws,
                ),
                self.assertRaisesRegex(RuntimeError, "after journal"),
            ):
                create_bg96_ota_update.main()

        self.assertEqual("aws-signer", journal_at_upload["code_signing_mode"])
        self.assertEqual(
            "preplanned-ota-9402-60191",
            journal_at_upload["ota_update_id"],
        )
        self.assertTrue(
            journal_at_upload["signed_prefix"].startswith(
                "ota/pipeline-thing/signed/"
            )
        )
        self.assertIn(
            journal_at_upload["ota_update_id"],
            journal_at_upload["signed_prefix"],
        )
        self.assertIn(
            journal_at_upload["ota_update_id"],
            journal_at_upload["s3_key"],
        )

    def test_rx72_creator_completes_with_signer_id_in_final_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "candidate.rsu"
            payload.write_bytes(b"candidate")
            artifact_dir = root / "artifacts"
            final_payload = {
                "otaUpdateInfo": {
                    "otaUpdateArn": "arn:ota",
                    "otaUpdateStatus": "CREATE_COMPLETE",
                    "awsIotJobId": "iot-job",
                    "awsIotJobArn": "arn:iot-job",
                    "otaUpdateFiles": [
                        {
                            "codeSigning": {
                                "awsSignerJobId": "signing-job",
                            }
                        }
                    ],
                }
            }

            def fake_run(args, region, cwd=None):
                del region, cwd
                if args[:2] == ["iot", "describe-thing"]:
                    payload_out = {"thingArn": "arn:thing"}
                elif args[:2] == ["s3api", "put-object"]:
                    payload_out = {"VersionId": "source-version"}
                elif args[:2] == ["iot", "create-ota-update"]:
                    payload_out = final_payload
                elif args[:2] == ["signer", "describe-signing-job"]:
                    payload_out = {"jobId": "signing-job", "status": "Succeeded"}
                else:
                    self.fail(f"unexpected AWS call: {args}")
                return SimpleNamespace(stdout=json.dumps(payload_out))

            argv = [
                "create_ota_update.py",
                "--artifact-dir",
                str(artifact_dir),
                "--thing-name",
                "pipeline-thing",
                "--input-rsu",
                str(payload),
                "--file-version",
                "2.06.0",
                "--bucket",
                "bucket",
                "--signing-profile",
                "profile",
                "--role-arn",
                "arn:role",
                "--region",
                "us-test-1",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(create_ota_update, "run_aws", side_effect=fake_run),
                patch.object(
                    create_ota_update,
                    "wait_for_ota_status",
                    return_value=final_payload,
                ),
            ):
                self.assertEqual(0, create_ota_update.main())

            meta = json.loads(
                (artifact_dir / "ota_job_meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual("signing-job", meta["signing_job_id"])
            self.assertEqual("CREATE_COMPLETE", meta["ota_update_status"])

    def test_bg96_creator_completes_with_signer_id_in_final_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "candidate.rsu"
            payload.write_bytes(b"candidate")
            artifact_dir = root / "artifacts"
            final_payload = {
                "otaUpdateInfo": {
                    "otaUpdateArn": "arn:ota",
                    "otaUpdateStatus": "CREATE_COMPLETE",
                    "awsIotJobId": "iot-job",
                    "awsIotJobArn": "arn:iot-job",
                    "otaUpdateFiles": [
                        {
                            "codeSigning": {
                                "awsSignerJobId": "signing-job",
                            }
                        }
                    ],
                }
            }

            def fake_aws(args, region):
                del region
                if args[:2] == ["iot", "describe-thing"]:
                    return {"thingArn": "arn:thing"}
                if args[:2] == ["s3api", "put-object"]:
                    return {"VersionId": "source-version"}
                if args[:2] == ["iot", "create-ota-update"]:
                    return final_payload
                if args[:2] == ["signer", "describe-signing-job"]:
                    return {"jobId": "signing-job", "status": "Succeeded"}
                self.fail(f"unexpected AWS call: {args}")

            argv = [
                "create_bg96_ota_update.py",
                "--artifact-dir",
                str(artifact_dir),
                "--thing-name",
                "pipeline-thing",
                "--input-payload",
                str(payload),
                "--file-version",
                "2.06.0",
                "--bucket",
                "bucket",
                "--signing-profile",
                "profile",
                "--role-arn",
                "arn:role",
                "--region",
                "us-test-1",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(create_bg96_ota_update, "aws", side_effect=fake_aws),
                patch.object(
                    create_bg96_ota_update,
                    "wait_for_ota",
                    return_value=final_payload,
                ),
            ):
                self.assertEqual(0, create_bg96_ota_update.main())

            meta = json.loads(
                (artifact_dir / "ota_job_meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual("signing-job", meta["signing_job_id"])
            self.assertEqual("CREATE_COMPLETE", meta["ota_update_status"])

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
        self.assertIn(
            "tools/manage_ephemeral_iot_thing.py cleanup",
            job,
        )
        self.assertLess(
            job.index(cleanup),
            job.index("tools/manage_ephemeral_iot_thing.py cleanup"),
        )
        self.assertIn(
            "independently attempting exact pipeline-owned Thing cleanup",
            job,
        )
        self.assertIn(f"artifacts/{artifact_name}/", job)
        self.assertIn('when: always', job)


if __name__ == "__main__":
    unittest.main()

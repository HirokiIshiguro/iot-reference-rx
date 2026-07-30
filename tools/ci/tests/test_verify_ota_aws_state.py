from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import verify_ota_aws_state as ota_state


META = {
    "region": "us-test-1",
    "thing_name": "test-thing",
    "ota_update_id": "ota-test",
    "aws_iot_job_id": "AFR_OTA-test",
    "s3_bucket": "test-bucket",
    "s3_key": "ota/test-thing/candidate.rsu",
    "s3_version": "test-version",
    "code_signing_mode": "custom",
    "file_version": "2.06.0",
}


def live_ota_payload(
    *,
    ota_id: str | None = META["ota_update_id"],
    job_id: str | None = META["aws_iot_job_id"],
    job_arn: str | None = None,
    targets: list[str] | None = None,
    bucket: str | None = META["s3_bucket"],
    key: str | None = META["s3_key"],
    version: str | None = META["s3_version"],
    file_version: str | None = META["file_version"],
    signer_job_id: str | None = None,
    include_s3_file: bool = True,
) -> dict:
    ota_info = {
        "otaUpdateId": ota_id,
        "awsIotJobId": job_id,
    }
    if job_arn is not None:
        ota_info["awsIotJobArn"] = job_arn
    if targets is not None:
        ota_info["targets"] = targets
    if include_s3_file:
        ota_file = {
            "fileVersion": file_version,
            "fileLocation": {
                "s3Location": {
                    "bucket": bucket,
                    "key": key,
                    "version": version,
                }
            },
        }
        if signer_job_id is not None:
            ota_file["codeSigning"] = {
                "awsSignerJobId": signer_job_id,
            }
        ota_info["otaUpdateFiles"] = [ota_file]
    return {"otaUpdateInfo": ota_info}


class VerifyOtaAwsStateTests(unittest.TestCase):
    def test_snapshot_requires_successful_terminal_job_and_execution(self) -> None:
        def fake_run(args, _region, *, absent_ok=False):
            self.assertFalse(absent_ok)
            if args[:2] == ["iot", "get-ota-update"]:
                return {
                    "otaUpdateInfo": {
                        "otaUpdateId": META["ota_update_id"],
                        "otaUpdateStatus": "CREATE_COMPLETE",
                        "awsIotJobId": META["aws_iot_job_id"],
                    }
                }
            if args[:2] == ["iot", "describe-job"]:
                return {
                    "job": {
                        "jobId": META["aws_iot_job_id"],
                        "status": "COMPLETED",
                        "jobProcessDetails": {
                            "numberOfSucceededThings": 1,
                            "numberOfCanceledThings": 0,
                            "numberOfFailedThings": 0,
                            "numberOfRejectedThings": 0,
                            "numberOfRemovedThings": 0,
                            "numberOfTimedOutThings": 0,
                        },
                    }
                }
            if args[:2] == ["iot", "describe-thing"]:
                return {
                    "thingName": META["thing_name"],
                    "thingArn": (
                        "arn:aws:iot:us-test-1:000000000000:"
                        f"thing/{META['thing_name']}"
                    ),
                }
            if args[:2] == ["iot", "describe-job-execution"]:
                return {
                    "execution": {
                        "jobId": META["aws_iot_job_id"],
                        "thingArn": (
                            "arn:aws:iot:us-test-1:000000000000:"
                            f"thing/{META['thing_name']}"
                        ),
                        "status": "SUCCEEDED",
                        "executionNumber": 1,
                    }
                }
            if args[:2] == ["s3api", "head-object"]:
                return {"ContentLength": 4096, "VersionId": META["s3_version"]}
            self.fail(f"unexpected AWS call: {args}")

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.snapshot_state(dict(META))

        self.assertTrue(summary["acceptance"]["passed"])
        self.assertEqual(summary["aws_iot_job"]["status"], "COMPLETED")
        self.assertEqual(
            summary["aws_iot_job_execution"]["status"],
            "SUCCEEDED",
        )
        self.assertNotIn("jobDocument", summary["aws_iot_job_execution"])

    def test_snapshot_rejects_terminal_failed_execution(self) -> None:
        def fake_run(args, _region, *, absent_ok=False):
            self.assertFalse(absent_ok)
            if args[:2] == ["iot", "get-ota-update"]:
                return {
                    "otaUpdateInfo": {
                        "otaUpdateId": META["ota_update_id"],
                        "otaUpdateStatus": "CREATE_COMPLETE",
                        "awsIotJobId": META["aws_iot_job_id"],
                    }
                }
            if args[:2] == ["iot", "describe-job"]:
                return {
                    "job": {
                        "jobId": META["aws_iot_job_id"],
                        "status": "COMPLETED",
                        "jobProcessDetails": {
                            "numberOfSucceededThings": 0,
                            "numberOfCanceledThings": 0,
                            "numberOfFailedThings": 1,
                            "numberOfRejectedThings": 0,
                            "numberOfRemovedThings": 0,
                            "numberOfTimedOutThings": 0,
                        },
                    }
                }
            if args[:2] == ["iot", "describe-thing"]:
                return {
                    "thingName": META["thing_name"],
                    "thingArn": "arn:aws:iot:us-test-1:000000000000:thing/test-thing",
                }
            if args[:2] == ["iot", "describe-job-execution"]:
                return {
                    "execution": {
                        "jobId": META["aws_iot_job_id"],
                        "thingArn": "arn:aws:iot:us-test-1:000000000000:thing/test-thing",
                        "status": "FAILED",
                    }
                }
            return {"ContentLength": 1}

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.snapshot_state(dict(META))

        self.assertTrue(summary["acceptance"]["execution_terminal"])
        self.assertFalse(summary["acceptance"]["execution_successful"])
        self.assertFalse(
            summary["acceptance"]["job_execution_counts_successful"]
        )
        self.assertFalse(summary["acceptance"]["passed"])

    def test_snapshot_rejects_completed_job_with_other_failed_target(self) -> None:
        thing_arn = (
            "arn:aws:iot:us-test-1:000000000000:"
            f"thing/{META['thing_name']}"
        )

        def fake_run(args, _region, *, absent_ok=False):
            self.assertFalse(absent_ok)
            if args[:2] == ["iot", "get-ota-update"]:
                return {
                    "otaUpdateInfo": {
                        "otaUpdateId": META["ota_update_id"],
                        "otaUpdateStatus": "CREATE_COMPLETE",
                        "awsIotJobId": META["aws_iot_job_id"],
                    }
                }
            if args[:2] == ["iot", "describe-job"]:
                return {
                    "job": {
                        "jobId": META["aws_iot_job_id"],
                        "status": "COMPLETED",
                        "jobProcessDetails": {
                            "numberOfSucceededThings": 1,
                            "numberOfCanceledThings": 0,
                            "numberOfFailedThings": 1,
                            "numberOfRejectedThings": 0,
                            "numberOfRemovedThings": 0,
                            "numberOfTimedOutThings": 0,
                        },
                    }
                }
            if args[:2] == ["iot", "describe-thing"]:
                return {
                    "thingName": META["thing_name"],
                    "thingArn": thing_arn,
                }
            if args[:2] == ["iot", "describe-job-execution"]:
                return {
                    "execution": {
                        "jobId": META["aws_iot_job_id"],
                        "thingArn": thing_arn,
                        "status": "SUCCEEDED",
                    }
                }
            return {"ContentLength": 1}

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.snapshot_state(dict(META))

        self.assertTrue(summary["acceptance"]["job_successful"])
        self.assertTrue(summary["acceptance"]["execution_successful"])
        self.assertFalse(
            summary["acceptance"]["job_execution_counts_successful"]
        )
        self.assertFalse(summary["acceptance"]["passed"])

    def test_snapshot_rejects_mixed_metadata_identity(self) -> None:
        thing_arn = (
            "arn:aws:iot:us-test-1:000000000000:"
            f"thing/{META['thing_name']}"
        )
        process_details = {
            "numberOfSucceededThings": 1,
            "numberOfCanceledThings": 0,
            "numberOfFailedThings": 0,
            "numberOfRejectedThings": 0,
            "numberOfRemovedThings": 0,
            "numberOfTimedOutThings": 0,
        }
        responses = [
            {
                "otaUpdateInfo": {
                    "otaUpdateId": "different-ota",
                    "otaUpdateStatus": "CREATE_COMPLETE",
                    "awsIotJobId": META["aws_iot_job_id"],
                }
            },
            {"thingName": META["thing_name"], "thingArn": thing_arn},
            {
                "job": {
                    "jobId": META["aws_iot_job_id"],
                    "status": "COMPLETED",
                    "jobProcessDetails": process_details,
                }
            },
            {
                "execution": {
                    "jobId": META["aws_iot_job_id"],
                    "thingArn": thing_arn,
                    "status": "SUCCEEDED",
                }
            },
            {"ContentLength": 1},
        ]

        with patch.object(ota_state, "run_aws", side_effect=responses):
            summary = ota_state.snapshot_state(dict(META))

        self.assertFalse(
            summary["acceptance"]["ota_update_id_matches_metadata"]
        )
        self.assertFalse(summary["acceptance"]["passed"])

    def test_cleanup_deletes_and_confirms_exact_version_absent(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args, _region, *, absent_ok=False):
            calls.append(args)
            if args[:2] in (
                ["iot", "get-ota-update"],
                ["iot", "describe-job"],
                ["s3api", "head-object"],
            ):
                self.assertTrue(absent_ok)
                return None
            return {}

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                dict(META),
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertTrue(summary["absence"]["passed"])
        delete_object = next(
            call for call in calls if call[:2] == ["s3api", "delete-object"]
        )
        head_object = next(
            call for call in calls if call[:2] == ["s3api", "head-object"]
        )
        for call in (delete_object, head_object):
            self.assertIn("--version-id", call)
            self.assertIn(META["s3_version"], call)

    def test_cleanup_fails_closed_when_s3_version_remains(self) -> None:
        def fake_run(args, _region, *, absent_ok=False):
            if args[:2] in (
                ["iot", "get-ota-update"],
                ["iot", "describe-job"],
            ):
                return None
            if args[:2] == ["s3api", "head-object"]:
                return {"VersionId": META["s3_version"]}
            return {}

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                dict(META),
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertFalse(
            summary["absence"]["s3_source_object_or_version_absent"]
        )
        self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_continues_after_one_delete_error(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args, _region, *, absent_ok=False):
            calls.append(args)
            if args[:2] == ["iot", "delete-ota-update"]:
                raise ota_state.AwsCommandError("denied")
            if args[:2] in (
                ["iot", "get-ota-update"],
                ["iot", "describe-job"],
                ["s3api", "head-object"],
            ):
                return None
            return {}

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                dict(META),
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertIn(
            ["s3api", "delete-object"],
            [call[:2] for call in calls],
        )
        self.assertTrue(summary["absence"]["ota_update_absent"])
        self.assertTrue(summary["absence"]["aws_iot_job_absent"])
        self.assertTrue(
            summary["absence"]["s3_source_object_or_version_absent"]
        )
        self.assertEqual(1, len(summary["errors"]))
        self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_accepts_s3_only_partial_metadata(self) -> None:
        partial = {
            "region": META["region"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
            "s3_version": META["s3_version"],
            "code_signing_mode": "custom",
        }
        calls: list[list[str]] = []

        def fake_run(args, _region, *, absent_ok=False):
            calls.append(args)
            if args[:2] == ["s3api", "head-object"]:
                self.assertTrue(absent_ok)
                return None
            return {}

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                partial,
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertTrue(summary["absence"]["passed"])
        self.assertIsNone(summary["absence"]["ota_update_absent"])
        self.assertIsNone(summary["absence"]["aws_iot_job_absent"])
        self.assertEqual(["s3_source_object"], summary["checked_resources"])
        self.assertNotIn(
            ["iot", "delete-ota-update"],
            [call[:2] for call in calls],
        )

    def test_cleanup_without_journaled_version_deletes_all_exact_versions(
        self,
    ) -> None:
        partial = {
            "region": META["region"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
            "code_signing_mode": "custom",
        }
        calls: list[list[str]] = []
        list_calls = 0

        def fake_run(args, _region, *, absent_ok=False):
            nonlocal list_calls
            calls.append(args)
            if args[:2] == ["s3api", "list-object-versions"]:
                list_calls += 1
                if list_calls == 1:
                    return {
                        "Versions": [
                            {
                                "Key": META["s3_key"],
                                "VersionId": "uploaded-version",
                            },
                            {
                                "Key": META["s3_key"] + ".other",
                                "VersionId": "not-owned",
                            },
                        ],
                        "DeleteMarkers": [
                            {
                                "Key": META["s3_key"],
                                "VersionId": "delete-marker",
                            }
                        ],
                    }
                return {}
            if args[:2] == ["s3api", "head-object"]:
                self.assertTrue(absent_ok)
                return None
            if args[:2] == ["s3api", "delete-object"]:
                return {}
            self.fail(f"unexpected AWS call: {args}")

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                partial,
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertTrue(summary["absence"]["passed"])
        deletes = [
            call
            for call in calls
            if call[:2] == ["s3api", "delete-object"]
        ]
        self.assertEqual(2, len(deletes))
        deleted_versions = {
            call[call.index("--version-id") + 1] for call in deletes
        }
        self.assertEqual(
            {"uploaded-version", "delete-marker"},
            deleted_versions,
        )
        self.assertNotIn("not-owned", deleted_versions)

    def test_cleanup_deletes_every_signer_prefix_version_and_marker(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        partial = {
            "region": META["region"],
            "thing_name": META["thing_name"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
            "signed_prefix": signed_prefix,
            "code_signing_mode": "aws-signer",
            "ota_update_status": "S3_UPLOADED",
        }
        calls: list[list[str]] = []
        signer_list_calls = 0

        def fake_run(args, _region, *, absent_ok=False):
            nonlocal signer_list_calls
            calls.append(args)
            if args[:2] == ["s3api", "list-object-versions"]:
                prefix = args[args.index("--prefix") + 1]
                if prefix == META["s3_key"]:
                    return {}
                self.assertEqual(signed_prefix, prefix)
                self.assertIn("--no-paginate", args)
                signer_list_calls += 1
                if signer_list_calls == 1:
                    signed_key = signed_prefix + "signing-job-id"
                    return {
                        "Versions": [
                            {
                                "Key": signed_key,
                                "VersionId": "signed-version-1",
                            },
                            {
                                "Key": signed_key,
                                "VersionId": "signed-version-2",
                            },
                        ],
                        "DeleteMarkers": [
                            {
                                "Key": signed_key,
                                "VersionId": "signed-delete-marker",
                            }
                        ],
                    }
                return {}
            if args[:2] == ["s3api", "list-objects-v2"]:
                self.assertEqual(
                    signed_prefix,
                    args[args.index("--prefix") + 1],
                )
                return {}
            if args[:2] == ["s3api", "head-object"]:
                self.assertTrue(absent_ok)
                return None
            if args[:2] == ["s3api", "delete-object"]:
                return {}
            self.fail(f"unexpected AWS call: {args}")

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                partial,
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertTrue(summary["absence"]["passed"])
        self.assertTrue(
            summary["absence"]["s3_signer_output_prefix_absent"]
        )
        deletes = [
            call
            for call in calls
            if call[:2] == ["s3api", "delete-object"]
        ]
        self.assertEqual(3, len(deletes))
        self.assertEqual(
            {
                "signed-version-1",
                "signed-version-2",
                "signed-delete-marker",
            },
            {
                call[call.index("--version-id") + 1]
                for call in deletes
            },
        )
        self.assertIn(
            "s3_signer_output_prefix",
            summary["checked_resources"],
        )

    def test_signer_prefix_version_listing_paginates_fail_closed(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        responses = [
            {
                "IsTruncated": True,
                "NextKeyMarker": signed_prefix + "job",
                "NextVersionIdMarker": "version-1",
                "Versions": [
                    {
                        "Key": signed_prefix + "job",
                        "VersionId": "version-1",
                    }
                ],
            },
            {
                "IsTruncated": False,
                "DeleteMarkers": [
                    {
                        "Key": signed_prefix + "job",
                        "VersionId": "delete-marker",
                    }
                ],
            },
        ]
        calls: list[list[str]] = []

        def fake_run(args, _region, *, absent_ok=False):
            self.assertFalse(absent_ok)
            calls.append(args)
            return responses.pop(0)

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            entries = ota_state.list_s3_prefix_versions(
                dict(META),
                META["region"],
                signed_prefix,
            )

        self.assertEqual(2, len(entries))
        self.assertEqual(2, len(calls))
        self.assertIn("--no-paginate", calls[0])
        self.assertIn("--key-marker", calls[1])
        self.assertIn("--version-id-marker", calls[1])

    def test_cleanup_blocks_unsafe_signer_prefix_before_aws_calls(
        self,
    ) -> None:
        unsafe = dict(META)
        unsafe["signed_prefix"] = "ota/different-thing/signed/"
        unsafe["code_signing_mode"] = "aws-signer"

        with patch.object(ota_state, "run_aws") as run_aws:
            summary = ota_state.cleanup_state(
                unsafe,
                wait_timeout=0,
                poll_interval=0,
            )

        run_aws.assert_not_called()
        self.assertEqual([], summary["actions"])
        self.assertTrue(summary["errors"])
        self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_rejects_aws_signer_metadata_without_prefix(
        self,
    ) -> None:
        missing = dict(META)
        missing["code_signing_mode"] = "aws-signer"

        with patch.object(ota_state, "run_aws") as run_aws:
            summary = ota_state.cleanup_state(
                missing,
                wait_timeout=0,
                poll_interval=0,
            )

        run_aws.assert_not_called()
        self.assertEqual([], summary["actions"])
        self.assertIn(
            "requires signed_prefix",
            summary["errors"][0]["message"],
        )
        self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_catches_signer_output_that_appears_late(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        partial = {
            "region": META["region"],
            "thing_name": META["thing_name"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
            "signed_prefix": signed_prefix,
            "code_signing_mode": "aws-signer",
            "ota_update_status": "CREATE_REQUESTED",
        }
        late_version = {
            "kind": "version",
            "key": signed_prefix + "late-signing-job",
            "version_id": "late-version",
        }

        with (
            patch.object(
                ota_state,
                "list_exact_s3_key_versions",
                return_value=[],
            ),
            patch.object(
                ota_state,
                "wait_until_s3_key_fully_absent",
                return_value=True,
            ),
            patch.object(
                ota_state,
                "list_s3_prefix_versions",
                side_effect=[[], [late_version], []],
            ),
            patch.object(
                ota_state,
                "list_current_s3_prefix_keys",
                side_effect=[[], [], []],
            ),
            patch.object(
                ota_state,
                "run_aws",
                side_effect=[None, {}],
            ) as run_aws,
            patch.object(
                ota_state.time,
                "time",
                side_effect=[0.0, 0.2, 0.5, 1.1],
            ),
            patch.object(ota_state.time, "sleep") as sleep,
        ):
            summary = ota_state.cleanup_state(
                partial,
                wait_timeout=1,
                poll_interval=0,
            )

        self.assertTrue(
            summary["absence"]["s3_signer_output_prefix_absent"]
        )
        self.assertFalse(summary["absence"]["passed"])
        self.assertEqual(
            "UnresolvedSignerSubmission",
            summary["errors"][0]["error_type"],
        )
        self.assertEqual(
            "late-version",
            summary["actions"][-1]["version_id"],
        )
        self.assertEqual(2, run_aws.call_count)
        self.assertEqual(2, sleep.call_count)

    def test_live_ota_enriches_signer_job_id_before_cleanup(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        partial = {
            **META,
            "code_signing_mode": "aws-signer",
            "signed_prefix": signed_prefix,
        }
        partial.pop("signing_job_id", None)

        errors = ota_state.reconcile_live_ota_identity(
            partial,
            live_ota_payload(signer_job_id="signing-job"),
        )

        self.assertEqual([], errors)
        self.assertEqual("signing-job", partial["signing_job_id"])

    def test_signer_job_waits_for_terminal_and_validates_owned_output(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        signer_meta = {
            **META,
            "code_signing_mode": "aws-signer",
            "signed_prefix": signed_prefix,
            "signing_job_id": "signing-job",
        }
        source = {
            "s3": {
                "bucketName": META["s3_bucket"],
                "key": META["s3_key"],
                "version": META["s3_version"],
            }
        }
        responses = [
            {
                "jobId": "signing-job",
                "status": "InProgress",
                "source": source,
            },
            {
                "jobId": "signing-job",
                "status": "Succeeded",
                "source": source,
                "signedObject": {
                    "s3": {
                        "bucketName": META["s3_bucket"],
                        "key": signed_prefix + "signing-job",
                    }
                },
            },
        ]

        with (
            patch.object(
                ota_state,
                "run_aws",
                side_effect=responses,
            ),
            patch.object(
                ota_state.time,
                "time",
                side_effect=[0.0, 0.5],
            ),
            patch.object(ota_state.time, "sleep") as sleep,
        ):
            result = ota_state.wait_for_signing_job_terminal(
                signer_meta,
                META["region"],
                timeout=1,
                poll_interval=0,
            )

        self.assertEqual("Succeeded", result["status"])
        sleep.assert_called_once_with(0)

    def test_signer_job_rejects_foreign_output_before_cleanup(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        signer_meta = {
            **META,
            "code_signing_mode": "aws-signer",
            "signed_prefix": signed_prefix,
            "signing_job_id": "signing-job",
        }
        response = {
            "jobId": "signing-job",
            "status": "Succeeded",
            "source": {
                "s3": {
                    "bucketName": META["s3_bucket"],
                    "key": META["s3_key"],
                    "version": META["s3_version"],
                }
            },
            "signedObject": {
                "s3": {
                    "bucketName": META["s3_bucket"],
                    "key": "ota/foreign-thing/signed/signing-job",
                }
            },
        }

        with patch.object(
            ota_state,
            "run_aws",
            return_value=response,
        ):
            with self.assertRaisesRegex(ValueError, "outside"):
                ota_state.wait_for_signing_job_terminal(
                    signer_meta,
                    META["region"],
                    timeout=0,
                    poll_interval=0,
                )

    def test_cleanup_waits_for_signer_before_destructive_calls(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        signer_meta = {
            "region": META["region"],
            "thing_name": META["thing_name"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
            "code_signing_mode": "aws-signer",
            "signed_prefix": signed_prefix,
            "signing_job_id": "signing-job",
        }
        events: list[str] = []

        def fake_signer_wait(*_args, **_kwargs):
            events.append("signer-terminal")
            return {"status": "Succeeded"}

        def fake_run(args, _region, *, absent_ok=False):
            if args[:2] == ["s3api", "head-object"]:
                self.assertTrue(absent_ok)
                events.append("source-read")
                return None
            if args[:2] == ["s3api", "delete-object"]:
                events.append("signer-delete")
                return {}
            self.fail(f"unexpected AWS call: {args}")

        signer_version = {
            "kind": "version",
            "key": signed_prefix + "signing-job",
            "version_id": "signer-version",
        }
        with (
            patch.object(
                ota_state,
                "wait_for_signing_job_terminal",
                side_effect=fake_signer_wait,
            ),
            patch.object(
                ota_state,
                "list_exact_s3_key_versions",
                return_value=[],
            ),
            patch.object(
                ota_state,
                "wait_until_s3_key_fully_absent",
                return_value=True,
            ),
            patch.object(
                ota_state,
                "list_s3_prefix_versions",
                side_effect=[[signer_version], []],
            ),
            patch.object(
                ota_state,
                "list_current_s3_prefix_keys",
                side_effect=[[], []],
            ),
            patch.object(ota_state, "run_aws", side_effect=fake_run),
        ):
            summary = ota_state.cleanup_state(
                signer_meta,
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertTrue(summary["absence"]["passed"])
        self.assertLess(
            events.index("signer-terminal"),
            events.index("signer-delete"),
        )

    def test_cleanup_signer_timeout_blocks_all_aws_mutation(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        signer_meta = {
            "region": META["region"],
            "thing_name": META["thing_name"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
            "code_signing_mode": "aws-signer",
            "signed_prefix": signed_prefix,
            "signing_job_id": "signing-job",
        }

        with (
            patch.object(
                ota_state,
                "wait_for_signing_job_terminal",
                side_effect=TimeoutError("still running"),
            ),
            patch.object(ota_state, "run_aws") as run_aws,
        ):
            summary = ota_state.cleanup_state(
                signer_meta,
                wait_timeout=0,
                poll_interval=0,
            )

        run_aws.assert_not_called()
        self.assertEqual([], summary["actions"])
        self.assertEqual(
            "aws_signer_job",
            summary["errors"][0]["resource"],
        )
        self.assertFalse(summary["absence"]["passed"])

    def test_signer_identity_guards_fail_closed(self) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        signer_meta = {
            **META,
            "code_signing_mode": "aws-signer",
            "signed_prefix": signed_prefix,
            "signing_job_id": "signing-job",
        }
        base = {
            "jobId": "signing-job",
            "status": "Succeeded",
            "source": {
                "s3": {
                    "bucketName": META["s3_bucket"],
                    "key": META["s3_key"],
                    "version": META["s3_version"],
                }
            },
            "signedObject": {
                "s3": {
                    "bucketName": META["s3_bucket"],
                    "key": signed_prefix + "signing-job",
                }
            },
        }
        cases = {
            "job id": {"jobId": "foreign-job"},
            "source bucket": {
                "source": {
                    "s3": {
                        "bucketName": "foreign-bucket",
                        "key": META["s3_key"],
                        "version": META["s3_version"],
                    }
                }
            },
            "source key": {
                "source": {
                    "s3": {
                        "bucketName": META["s3_bucket"],
                        "key": "ota/foreign/candidate.rsu",
                        "version": META["s3_version"],
                    }
                }
            },
            "source version": {
                "source": {
                    "s3": {
                        "bucketName": META["s3_bucket"],
                        "key": META["s3_key"],
                        "version": "foreign-version",
                    }
                }
            },
        }

        for label, override in cases.items():
            with self.subTest(label=label):
                payload = {**base, **override}
                self.assertTrue(
                    ota_state.signing_job_identity_errors(
                        signer_meta,
                        payload,
                    )
                )

    def test_current_signer_prefix_listing_paginates_fail_closed(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        responses = [
            {
                "IsTruncated": True,
                "NextContinuationToken": "next-page",
                "Contents": [{"Key": signed_prefix + "first"}],
            },
            {
                "IsTruncated": False,
                "Contents": [{"Key": signed_prefix + "second"}],
            },
        ]
        calls: list[list[str]] = []

        def fake_run(args, _region, *, absent_ok=False):
            self.assertFalse(absent_ok)
            calls.append(args)
            return responses.pop(0)

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            keys = ota_state.list_current_s3_prefix_keys(
                dict(META),
                META["region"],
                signed_prefix,
            )

        self.assertEqual(
            [signed_prefix + "first", signed_prefix + "second"],
            keys,
        )
        self.assertEqual(2, len(calls))
        self.assertIn("--no-paginate", calls[0])
        self.assertIn("--continuation-token", calls[1])

    def test_signer_prefix_listing_rejects_out_of_prefix_entry(
        self,
    ) -> None:
        signed_prefix = f"ota/{META['thing_name']}/signed/"
        response = {
            "Versions": [
                {
                    "Key": "ota/different-thing/signed/job",
                    "VersionId": "foreign-version",
                }
            ]
        }

        with patch.object(
            ota_state,
            "run_aws",
            return_value=response,
        ):
            with self.assertRaisesRegex(RuntimeError, "out-of-prefix"):
                ota_state.list_s3_prefix_versions(
                    dict(META),
                    META["region"],
                    signed_prefix,
                )

    def test_cleanup_discovers_job_id_from_partial_ota_metadata(self) -> None:
        partial = {
            "region": META["region"],
            "ota_update_id": META["ota_update_id"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
            "code_signing_mode": "custom",
        }
        get_calls = 0

        def fake_run(args, _region, *, absent_ok=False):
            nonlocal get_calls
            if args[:2] == ["iot", "get-ota-update"]:
                self.assertTrue(absent_ok)
                get_calls += 1
                if get_calls == 1:
                    return live_ota_payload()
                return None
            if args[:2] in (
                ["iot", "describe-job"],
                ["s3api", "head-object"],
            ):
                self.assertTrue(absent_ok)
                return None
            return {}

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                partial,
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertTrue(summary["absence"]["passed"])
        self.assertEqual(META["aws_iot_job_id"], partial["aws_iot_job_id"])
        self.assertEqual(META["s3_version"], partial["s3_version"])
        self.assertIn("aws_iot_job", summary["checked_resources"])
        self.assertTrue(summary["absence"]["aws_iot_job_absent"])

    def test_cleanup_blocks_identity_mismatch_before_any_mutation(self) -> None:
        cases = {
            "ota_update_id": {"ota_id": "different-ota"},
            "aws_iot_job_id": {"job_id": "different-job"},
            "s3_bucket": {"bucket": "different-bucket"},
            "s3_key": {"key": "different-key"},
            "s3_version": {"version": "different-version"},
            "file_version": {"file_version": "different-file-version"},
        }
        destructive_calls = {
            ("iot", "delete-ota-update"),
            ("iot", "delete-job"),
            ("s3api", "delete-object"),
        }

        for field, overrides in cases.items():
            with self.subTest(field=field):
                calls: list[list[str]] = []

                def fake_run(args, _region, *, absent_ok=False):
                    calls.append(args)
                    self.assertNotIn(tuple(args[:2]), destructive_calls)
                    self.assertEqual(["iot", "get-ota-update"], args[:2])
                    self.assertTrue(absent_ok)
                    return live_ota_payload(**overrides)

                with patch.object(
                    ota_state,
                    "run_aws",
                    side_effect=fake_run,
                ):
                    summary = ota_state.cleanup_state(
                        dict(META),
                        wait_timeout=0,
                        poll_interval=0,
                    )

                self.assertEqual(1, len(calls))
                self.assertEqual([], summary["actions"])
                self.assertTrue(summary["errors"])
                self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_blocks_job_arn_and_thing_target_mismatch(self) -> None:
        cases = {
            "aws_iot_job_arn": (
                {"aws_iot_job_arn": "arn:aws:iot:us-test-1:123:job/expected"},
                {
                    "job_arn": "arn:aws:iot:us-test-1:123:job/different",
                },
            ),
            "thing_arn": (
                {"thing_arn": "arn:aws:iot:us-test-1:123:thing/expected"},
                {
                    "targets": [
                        "arn:aws:iot:us-test-1:123:thing/different"
                    ],
                },
            ),
        }

        for field, (meta_overrides, live_overrides) in cases.items():
            with self.subTest(field=field):
                calls: list[list[str]] = []

                def fake_run(args, _region, *, absent_ok=False):
                    calls.append(args)
                    self.assertEqual(["iot", "get-ota-update"], args[:2])
                    self.assertTrue(absent_ok)
                    return live_ota_payload(**live_overrides)

                meta = dict(META)
                meta.update(meta_overrides)
                with patch.object(
                    ota_state,
                    "run_aws",
                    side_effect=fake_run,
                ):
                    summary = ota_state.cleanup_state(
                        meta,
                        wait_timeout=0,
                        poll_interval=0,
                    )

                self.assertEqual(1, len(calls))
                self.assertEqual([], summary["actions"])
                self.assertTrue(summary["errors"])
                self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_blocks_missing_live_identity_before_mutation(self) -> None:
        cases = {
            "missing_job": {"job_id": None},
            "missing_s3_file": {"include_s3_file": False},
        }
        destructive_calls = {
            ("iot", "delete-ota-update"),
            ("iot", "delete-job"),
            ("s3api", "delete-object"),
        }

        for field, overrides in cases.items():
            with self.subTest(field=field):
                calls: list[list[str]] = []

                def fake_run(args, _region, *, absent_ok=False):
                    calls.append(args)
                    self.assertNotIn(tuple(args[:2]), destructive_calls)
                    self.assertEqual(["iot", "get-ota-update"], args[:2])
                    self.assertTrue(absent_ok)
                    return live_ota_payload(**overrides)

                with patch.object(
                    ota_state,
                    "run_aws",
                    side_effect=fake_run,
                ):
                    summary = ota_state.cleanup_state(
                        dict(META),
                        wait_timeout=0,
                        poll_interval=0,
                    )

                self.assertEqual(1, len(calls))
                self.assertEqual([], summary["actions"])
                self.assertTrue(summary["errors"])
                self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_blocks_discovery_error_before_mutation(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args, _region, *, absent_ok=False):
            calls.append(args)
            self.assertEqual(["iot", "get-ota-update"], args[:2])
            self.assertTrue(absent_ok)
            raise ota_state.AwsCommandError("discovery denied")

        with patch.object(ota_state, "run_aws", side_effect=fake_run):
            summary = ota_state.cleanup_state(
                dict(META),
                wait_timeout=0,
                poll_interval=0,
            )

        self.assertEqual(1, len(calls))
        self.assertEqual([], summary["actions"])
        self.assertEqual(1, len(summary["errors"]))
        self.assertFalse(summary["absence"]["passed"])

    def test_cleanup_blocks_incomplete_metadata_before_aws_calls(self) -> None:
        incomplete = dict(META)
        incomplete.pop("s3_key")

        with patch.object(ota_state, "run_aws") as run_aws:
            summary = ota_state.cleanup_state(
                incomplete,
                wait_timeout=0,
                poll_interval=0,
            )

        run_aws.assert_not_called()
        self.assertEqual([], summary["actions"])
        self.assertEqual(1, len(summary["errors"]))
        self.assertFalse(summary["absence"]["passed"])

    def test_incomplete_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meta.json"
            path.write_text('{"region": "us-test-1"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "aws_iot_job_id"):
                ota_state.load_meta(path)

    def test_partial_cleanup_metadata_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meta.json"
            path.write_text(
                (
                    '{"region": "us-test-1", "s3_bucket": "bucket", '
                    '"s3_key": "key", '
                    '"code_signing_mode": "custom"}\n'
                ),
                encoding="utf-8",
            )
            loaded = ota_state.load_meta(path, require_complete=False)
            self.assertEqual("bucket", loaded["s3_bucket"])

    def test_partial_cleanup_metadata_rejects_half_s3_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meta.json"
            path.write_text(
                (
                    '{"region": "us-test-1", "s3_bucket": "bucket", '
                    '"code_signing_mode": "custom"}\n'
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "together"):
                ota_state.load_meta(path, require_complete=False)

    def test_partial_cleanup_metadata_rejects_s3_version_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meta.json"
            path.write_text(
                (
                    '{"region": "us-test-1", "ota_update_id": "ota-test", '
                    '"s3_version": "version", '
                    '"code_signing_mode": "custom"}\n'
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "s3_version requires"):
                ota_state.load_meta(path, require_complete=False)

    def test_partial_cleanup_metadata_rejects_unscoped_signed_prefix(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meta.json"
            path.write_text(
                (
                    '{"region": "us-test-1", "s3_bucket": "bucket", '
                    '"s3_key": "key", "signed_prefix": "ota/x/signed/", '
                    '"code_signing_mode": "aws-signer"}\n'
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "signed_prefix requires",
            ):
                ota_state.load_meta(path, require_complete=False)


if __name__ == "__main__":
    unittest.main()

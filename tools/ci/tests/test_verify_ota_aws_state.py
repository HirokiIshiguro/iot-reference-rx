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
        ota_info["otaUpdateFiles"] = [
            {
                "fileVersion": file_version,
                "fileLocation": {
                    "s3Location": {
                        "bucket": bucket,
                        "key": key,
                        "version": version,
                    }
                },
            }
        ]
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

    def test_cleanup_discovers_job_id_from_partial_ota_metadata(self) -> None:
        partial = {
            "region": META["region"],
            "ota_update_id": META["ota_update_id"],
            "s3_bucket": META["s3_bucket"],
            "s3_key": META["s3_key"],
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
                    '"s3_key": "key"}\n'
                ),
                encoding="utf-8",
            )
            loaded = ota_state.load_meta(path, require_complete=False)
            self.assertEqual("bucket", loaded["s3_bucket"])

    def test_partial_cleanup_metadata_rejects_half_s3_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meta.json"
            path.write_text(
                '{"region": "us-test-1", "s3_bucket": "bucket"}\n',
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
                    '"s3_version": "version"}\n'
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "s3_version requires"):
                ota_state.load_meta(path, require_complete=False)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import manage_ephemeral_iot_thing as thing_manager
from tools import plan_rx671_ota as planner


PROJECT_ID = "38"
PIPELINE_ID = "9402"
PLAN_JOB_ID = "60191"
COMMIT_SHA = "a" * 40
BASE_THING = "rx671-ek-type1yn-01"
THING_NAME = f"{BASE_THING}-ota-{PIPELINE_ID}-{PLAN_JOB_ID}"
OTA_UPDATE_ID = f"rx671-software-ota-{PIPELINE_ID}-{PLAN_JOB_ID}"
REGION = "ap-northeast-1"
BUCKET = "ota-bucket"
BASE_ARN = f"arn:aws:iot:{REGION}:123456789012:thing/{BASE_THING}"
THING_ARN = f"arn:aws:iot:{REGION}:123456789012:thing/{THING_NAME}"
PRINCIPAL = f"arn:aws:iot:{REGION}:123456789012:cert/example"


def identity_args(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        project_id=PROJECT_ID,
        pipeline_id=PIPELINE_ID,
        plan_job_id=PLAN_JOB_ID,
        commit_sha=COMMIT_SHA,
        base_thing_name=BASE_THING,
        region=REGION,
        bucket=BUCKET,
        baseline_version="0.1.0",
        candidate_version="0.1.1",
        tls_version="TLSv1.2",
        plan_json=root / "ota_plan.json",
        alias_plan_json=root / "ephemeral_thing_plan.json",
        ota_meta_json=None,
        output_json=root / "ota_recovery_meta.json",
    )


class Rx671OtaPlanTests(unittest.TestCase):
    def test_identity_is_deterministic_and_cleanup_owned(self) -> None:
        identity = planner.expected_identity(
            project_id=PROJECT_ID,
            pipeline_id=PIPELINE_ID,
            plan_job_id=PLAN_JOB_ID,
            commit_sha=COMMIT_SHA,
            base_thing_name=BASE_THING,
            region=REGION,
            bucket=BUCKET,
            baseline_version="0.1.0",
            candidate_version="0.1.1",
            tls_version="TLSv1.2",
        )
        self.assertEqual(THING_NAME, identity["thing_name"])
        self.assertEqual(OTA_UPDATE_ID, identity["ota_update_id"])
        self.assertEqual(
            (
                f"ota/{THING_NAME}/source/{OTA_UPDATE_ID}/"
                "aws_wifi_rx671_ek.ota.bin"
            ),
            identity["s3_key"],
        )

    def test_create_plan_records_alias_cleanup_identity_before_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = identity_args(root)
            alias_plan = {
                "schema_version": 1,
                "status": "planned",
                "region": REGION,
                "base_thing_name": BASE_THING,
                "base_thing_arn": BASE_ARN,
                "thing_name": THING_NAME,
                "expected_thing_arn": THING_ARN,
                "principal": PRINCIPAL,
                "owner_project_id": PROJECT_ID,
                "owner_pipeline_id": PIPELINE_ID,
                "owner_job_id": PLAN_JOB_ID,
                "owner_attributes": thing_manager.ownership_attributes(
                    PROJECT_ID,
                    PIPELINE_ID,
                    PLAN_JOB_ID,
                ),
                "operations": [],
            }
            with (
                mock.patch.object(
                    planner.thing_manager,
                    "build_alias_plan",
                    return_value=alias_plan,
                ),
                mock.patch.object(
                    planner.thing_manager,
                    "describe_thing",
                    return_value=(False, {}),
                ),
            ):
                self.assertEqual(0, planner.create_plan(args))

            plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
            written_alias = json.loads(
                args.alias_plan_json.read_text(encoding="utf-8")
            )
            self.assertEqual(THING_NAME, plan["thing_name"])
            self.assertEqual(alias_plan, written_alias)

    def test_recovery_meta_forces_idempotent_discovery_and_s3_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = identity_args(root)
            plan = planner.build_expected_from_args(args)
            alias_plan = {
                "schema_version": 1,
                "region": REGION,
                "base_thing_name": BASE_THING,
                "base_thing_arn": BASE_ARN,
                "thing_name": THING_NAME,
                "expected_thing_arn": THING_ARN,
                "principal": PRINCIPAL,
                "owner_project_id": PROJECT_ID,
                "owner_pipeline_id": PIPELINE_ID,
                "owner_job_id": PLAN_JOB_ID,
                "owner_attributes": thing_manager.ownership_attributes(
                    PROJECT_ID,
                    PIPELINE_ID,
                    PLAN_JOB_ID,
                ),
            }
            args.plan_json.write_text(json.dumps(plan), encoding="utf-8")
            args.alias_plan_json.write_text(
                json.dumps(alias_plan),
                encoding="utf-8",
            )

            self.assertEqual(0, planner.write_recovery_meta(args))
            recovery = json.loads(
                args.output_json.read_text(encoding="utf-8")
            )
            self.assertEqual("CREATE_REQUESTED", recovery["ota_update_status"])
            self.assertEqual(OTA_UPDATE_ID, recovery["ota_update_id"])
            self.assertEqual(THING_ARN, recovery["thing_arn"])
            self.assertEqual(plan["s3_key"], recovery["s3_key"])
            self.assertEqual("custom", recovery["code_signing_mode"])
            self.assertIsNone(recovery["signed_prefix"])

    def test_created_meta_must_target_the_planned_thing_arn(self) -> None:
        plan = planner.expected_identity(
            project_id=PROJECT_ID,
            pipeline_id=PIPELINE_ID,
            plan_job_id=PLAN_JOB_ID,
            commit_sha=COMMIT_SHA,
            base_thing_name=BASE_THING,
            region=REGION,
            bucket=BUCKET,
            baseline_version="0.1.0",
            candidate_version="0.1.1",
            tls_version="TLSv1.2",
        )
        alias_plan = {"expected_thing_arn": THING_ARN}
        ota_meta = {
            "region": REGION,
            "thing_name": THING_NAME,
            "thing_arn": THING_ARN,
            "ota_update_id": OTA_UPDATE_ID,
            "s3_bucket": BUCKET,
            "s3_key": plan["s3_key"],
            "code_signing_mode": "custom",
            "signed_prefix": None,
            "file_version": "0.1.1",
        }
        planner.validate_created_meta(plan, alias_plan, ota_meta)
        ota_meta["thing_arn"] = THING_ARN.replace(THING_NAME, "other")
        with self.assertRaisesRegex(ValueError, "thing_arn"):
            planner.validate_created_meta(plan, alias_plan, ota_meta)


if __name__ == "__main__":
    unittest.main()

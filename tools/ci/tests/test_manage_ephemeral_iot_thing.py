from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import manage_ephemeral_iot_thing as manager


REGION = "ap-northeast-1"
PROJECT_ID = "38"
BASE_THING = "rx72n-02"
ALIAS_THING = "rx72n-02-ota-9402-60191"
ALIAS_ARN = (
    "arn:aws:iot:ap-northeast-1:094025684215:"
    f"thing/{ALIAS_THING}"
)
OWNER_ATTRIBUTES = manager.ownership_attributes(
    PROJECT_ID,
    "9402",
    "60191",
)
PRINCIPAL = (
    "arn:aws:iot:ap-northeast-1:094025684215:"
    "cert/0123456789abcdef"
)
PRINCIPAL_OBJECT = {
    "principal": PRINCIPAL,
    "thingPrincipalType": "NON_EXCLUSIVE_THING",
}


class EphemeralIotThingTests(unittest.TestCase):
    def test_names_must_be_distinct_and_pipeline_scoped(self) -> None:
        manager.validate_names(BASE_THING, ALIAS_THING)
        manager.validate_ownership(
            BASE_THING,
            ALIAS_THING,
            PROJECT_ID,
            "9402",
            "60191",
        )

        with self.assertRaisesRegex(RuntimeError, "must differ"):
            manager.validate_names(BASE_THING, BASE_THING)
        with self.assertRaisesRegex(RuntimeError, "must start"):
            manager.validate_names(BASE_THING, "unowned-alias")
        with self.assertRaisesRegex(RuntimeError, "invalid"):
            manager.validate_names(BASE_THING, "rx72n-02/ota/invalid")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            manager.validate_ownership(
                BASE_THING,
                ALIAS_THING,
                PROJECT_ID,
                "9402",
                "99999",
            )
        with self.assertRaisesRegex(RuntimeError, "decimal digits"):
            manager.validate_ownership(
                BASE_THING,
                ALIAS_THING,
                PROJECT_ID,
                "pipeline",
                "60191",
            )

    def test_create_journals_alias_and_preserves_base_principal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            args = SimpleNamespace(
                base_thing_name=BASE_THING,
                thing_name=ALIAS_THING,
                region=REGION,
                owner_project_id=PROJECT_ID,
                owner_pipeline_id="9402",
                owner_job_id="60191",
                meta_json=meta_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (
                            True,
                            {
                                "thingArn": (
                                    "arn:aws:iot:ap-northeast-1:"
                                    "094025684215:thing/rx72n-02"
                                )
                            },
                        ),
                        (False, {}),
                        (
                            True,
                            {
                                "thingArn": ALIAS_ARN,
                                "attributes": OWNER_ATTRIBUTES,
                            },
                        ),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    side_effect=[
                        [PRINCIPAL_OBJECT],
                        [PRINCIPAL_OBJECT],
                        [PRINCIPAL_OBJECT],
                    ],
                ),
                mock.patch.object(
                    manager,
                    "run_aws",
                    side_effect=[
                        (
                            mock.Mock(returncode=0),
                            {"thingArn": ALIAS_ARN},
                        ),
                        (mock.Mock(returncode=0), {}),
                    ],
                ) as run_aws,
            ):
                self.assertEqual(manager.create_alias(args), 0)

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "ready")
            self.assertEqual(meta["principal"], PRINCIPAL)
            self.assertEqual(
                meta["operations"],
                ["create-thing", "attach-thing-principal"],
            )
            self.assertTrue(meta["verified"])
            self.assertEqual(meta["expected_thing_arn"], ALIAS_ARN)
            self.assertEqual(meta["owner_attributes"], OWNER_ATTRIBUTES)
            self.assertEqual(run_aws.call_count, 2)
            create_arguments = run_aws.call_args_list[0].args[0]
            self.assertIn("--attribute-payload", create_arguments)
            attribute_payload = json.loads(
                create_arguments[create_arguments.index("--attribute-payload") + 1]
            )
            self.assertEqual(
                attribute_payload,
                {"attributes": OWNER_ATTRIBUTES},
            )
            attach_arguments = run_aws.call_args_list[1].args[0]
            self.assertIn("--thing-principal-type", attach_arguments)
            self.assertIn("NON_EXCLUSIVE_THING", attach_arguments)

    def test_plan_journals_complete_cleanup_identity_without_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "planned-ephemeral.json"
            args = SimpleNamespace(
                base_thing_name=BASE_THING,
                thing_name=ALIAS_THING,
                region=REGION,
                owner_project_id=PROJECT_ID,
                owner_pipeline_id="9402",
                owner_job_id="60191",
                meta_json=meta_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (
                            True,
                            {
                                "thingArn": (
                                    "arn:aws:iot:ap-northeast-1:"
                                    "094025684215:thing/rx72n-02"
                                )
                            },
                        ),
                        (False, {}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    return_value=[PRINCIPAL_OBJECT],
                ),
                mock.patch.object(manager, "run_aws") as run_aws,
            ):
                self.assertEqual(manager.plan_alias(args), 0)

            self.assertEqual(run_aws.call_count, 0)
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "planned")
            self.assertEqual(meta["expected_thing_arn"], ALIAS_ARN)
            self.assertEqual(meta["principal"], PRINCIPAL)
            self.assertEqual(meta["owner_attributes"], OWNER_ATTRIBUTES)
            self.assertEqual(meta["operations"], [])

    def test_create_rejects_a_changed_preflight_plan_before_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "created-ephemeral.json"
            plan_path = Path(temporary) / "planned-ephemeral.json"
            self._write_meta(plan_path)
            planned = json.loads(plan_path.read_text(encoding="utf-8"))
            planned["principal"] = PRINCIPAL.replace("012345", "fedcba")
            plan_path.write_text(json.dumps(planned), encoding="utf-8")
            args = SimpleNamespace(
                base_thing_name=BASE_THING,
                thing_name=ALIAS_THING,
                region=REGION,
                owner_project_id=PROJECT_ID,
                owner_pipeline_id="9402",
                owner_job_id="60191",
                plan_meta_json=plan_path,
                meta_json=meta_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    return_value=(
                        True,
                        {
                            "thingArn": (
                                "arn:aws:iot:ap-northeast-1:"
                                "094025684215:thing/rx72n-02"
                            )
                        },
                    ),
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    return_value=[PRINCIPAL_OBJECT],
                ),
                mock.patch.object(manager, "run_aws") as run_aws,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "preflight journal",
                ):
                    manager.create_alias(args)

            self.assertEqual(run_aws.call_count, 0)

    def test_create_refuses_to_adopt_a_colliding_thing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            args = SimpleNamespace(
                base_thing_name=BASE_THING,
                thing_name=ALIAS_THING,
                region=REGION,
                owner_project_id=PROJECT_ID,
                owner_pipeline_id="9402",
                owner_job_id="60191",
                meta_json=meta_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (
                            True,
                            {
                                "thingArn": (
                                    "arn:aws:iot:ap-northeast-1:"
                                    "094025684215:thing/rx72n-02"
                                )
                            },
                        ),
                        (True, {"thingArn": "arn:collision"}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    return_value=[PRINCIPAL_OBJECT],
                ),
                mock.patch.object(manager, "run_aws") as run_aws,
            ):
                with self.assertRaisesRegex(RuntimeError, "refusing to adopt"):
                    manager.create_alias(args)

            self.assertEqual(run_aws.call_count, 0)
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "collision")

    def _write_meta(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "ready",
                    "verified": True,
                    "region": REGION,
                    "base_thing_name": BASE_THING,
                    "base_thing_arn": (
                        "arn:aws:iot:ap-northeast-1:"
                        "094025684215:thing/rx72n-02"
                    ),
                    "thing_name": ALIAS_THING,
                    "principal": PRINCIPAL,
                    "owner_project_id": PROJECT_ID,
                    "owner_pipeline_id": "9402",
                    "owner_job_id": "60191",
                    "owner_attributes": OWNER_ATTRIBUTES,
                    "expected_thing_arn": ALIAS_ARN,
                    "operations": [
                        "create-thing",
                        "attach-thing-principal",
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_local_journal_verification_binds_project_pipeline_and_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            self._write_meta(meta_path)
            args = SimpleNamespace(
                meta_json=meta_path,
                expected_thing_name=ALIAS_THING,
                owner_project_id=PROJECT_ID,
                owner_pipeline_id="9402",
            )
            self.assertEqual(manager.verify_journal(args), 0)

            args.owner_pipeline_id = "different"
            with self.assertRaisesRegex(RuntimeError, "pipeline ID mismatch"):
                manager.verify_journal(args)

    def test_cleanup_refuses_unowned_collision_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            output_path = Path(temporary) / "cleanup.json"
            self._write_meta(meta_path)
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            payload["status"] = "collision"
            payload["operations"] = []
            meta_path.write_text(json.dumps(payload), encoding="utf-8")
            args = SimpleNamespace(
                meta_json=meta_path,
                output_json=output_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (True, {"thingArn": "arn:base"}),
                        (
                            True,
                            {
                                "thingArn": ALIAS_ARN,
                                "attributes": {},
                            },
                        ),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    return_value=[PRINCIPAL_OBJECT],
                ),
                mock.patch.object(manager, "run_aws") as run_aws,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "live ephemeral Thing ownership does not match",
                ):
                    manager.cleanup_alias(args)

            self.assertEqual(run_aws.call_count, 0)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["actions"], [])

    def test_cleanup_recovers_atomically_owned_thing_without_operation_journal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            output_path = Path(temporary) / "cleanup.json"
            self._write_meta(meta_path)
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            payload["status"] = "planned"
            payload["operations"] = []
            meta_path.write_text(json.dumps(payload), encoding="utf-8")
            args = SimpleNamespace(
                meta_json=meta_path,
                output_json=output_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (True, {"thingArn": "arn:base"}),
                        (
                            True,
                            {
                                "thingArn": ALIAS_ARN,
                                "attributes": OWNER_ATTRIBUTES,
                            },
                        ),
                        (False, {}),
                        (True, {"thingArn": "arn:base"}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    side_effect=[
                        [PRINCIPAL_OBJECT],
                        [],
                        [],
                        [PRINCIPAL_OBJECT],
                    ],
                ),
                mock.patch.object(
                    manager,
                    "run_aws",
                    return_value=(mock.Mock(returncode=0), {}),
                ) as run_aws,
            ):
                self.assertEqual(manager.cleanup_alias(args), 0)

            self.assertEqual(run_aws.call_count, 1)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["actions"], ["delete-thing"])

    def test_cleanup_refuses_unexpected_principal_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            output_path = Path(temporary) / "cleanup.json"
            self._write_meta(meta_path)
            args = SimpleNamespace(
                meta_json=meta_path,
                output_json=output_path,
            )
            unexpected = PRINCIPAL.replace("012345", "fedcba")
            unexpected_object = {
                "principal": unexpected,
                "thingPrincipalType": "NON_EXCLUSIVE_THING",
            }
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (True, {"thingArn": "arn:base"}),
                        (
                            True,
                            {
                                "thingArn": ALIAS_ARN,
                                "attributes": OWNER_ATTRIBUTES,
                            },
                        ),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    side_effect=[
                        [PRINCIPAL_OBJECT],
                        [PRINCIPAL_OBJECT, unexpected_object],
                    ],
                ),
                mock.patch.object(manager, "run_aws") as run_aws,
            ):
                with self.assertRaisesRegex(RuntimeError, "unexpected principals"):
                    manager.cleanup_alias(args)

            self.assertEqual(run_aws.call_count, 0)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["actions"], [])

    def test_cleanup_detaches_only_alias_and_verifies_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            output_path = Path(temporary) / "cleanup.json"
            self._write_meta(meta_path)
            args = SimpleNamespace(
                meta_json=meta_path,
                output_json=output_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (True, {"thingArn": "arn:base"}),
                        (
                            True,
                            {
                                "thingArn": ALIAS_ARN,
                                "attributes": OWNER_ATTRIBUTES,
                            },
                        ),
                        (False, {}),
                        (True, {"thingArn": "arn:base"}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    side_effect=[
                        [PRINCIPAL_OBJECT],
                        [PRINCIPAL_OBJECT],
                        [],
                        [PRINCIPAL_OBJECT],
                    ],
                ),
                mock.patch.object(
                    manager,
                    "run_aws",
                    side_effect=[
                        (mock.Mock(returncode=0), {}),
                        (mock.Mock(returncode=0), {}),
                    ],
                ) as run_aws,
            ):
                self.assertEqual(manager.cleanup_alias(args), 0)

            self.assertEqual(run_aws.call_count, 2)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "complete")
            self.assertEqual(
                result["actions"],
                ["detach-thing-principal", "delete-thing"],
            )
            self.assertEqual(
                result["verification"],
                {
                    "base_thing_exists": True,
                    "base_principal_attached": True,
                    "ephemeral_thing_absent": True,
                },
            )

    def test_cleanup_is_idempotent_after_alias_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            output_path = Path(temporary) / "cleanup.json"
            self._write_meta(meta_path)
            args = SimpleNamespace(
                meta_json=meta_path,
                output_json=output_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (True, {"thingArn": "arn:base"}),
                        (False, {}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principal_objects",
                    return_value=[PRINCIPAL_OBJECT],
                ),
                mock.patch.object(manager, "run_aws") as run_aws,
            ):
                self.assertEqual(manager.cleanup_alias(args), 0)

            self.assertEqual(run_aws.call_count, 0)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["actions"], [])
            self.assertTrue(
                result["verification"]["ephemeral_thing_absent"]
            )


if __name__ == "__main__":
    unittest.main()

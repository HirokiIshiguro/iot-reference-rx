from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import manage_ephemeral_iot_thing as manager


REGION = "ap-northeast-1"
BASE_THING = "rx72n-02"
ALIAS_THING = "rx72n-02-ota-9402-60191"
PRINCIPAL = (
    "arn:aws:iot:ap-northeast-1:094025684215:"
    "cert/0123456789abcdef"
)


class EphemeralIotThingTests(unittest.TestCase):
    def test_names_must_be_distinct_and_pipeline_scoped(self) -> None:
        manager.validate_names(BASE_THING, ALIAS_THING)
        manager.validate_ownership(
            BASE_THING,
            ALIAS_THING,
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
                "9402",
                "99999",
            )
        with self.assertRaisesRegex(RuntimeError, "decimal digits"):
            manager.validate_ownership(
                BASE_THING,
                ALIAS_THING,
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
                owner_pipeline_id="9402",
                owner_job_id="60191",
                meta_json=meta_path,
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
                    "list_principals",
                    side_effect=[[PRINCIPAL], [PRINCIPAL], [PRINCIPAL]],
                ),
                mock.patch.object(
                    manager,
                    "run_aws",
                    side_effect=[
                        (
                            mock.Mock(returncode=0),
                            {"thingArn": "arn:ephemeral"},
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
            self.assertEqual(run_aws.call_count, 2)

    def test_create_refuses_to_adopt_a_colliding_thing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = Path(temporary) / "ephemeral.json"
            args = SimpleNamespace(
                base_thing_name=BASE_THING,
                thing_name=ALIAS_THING,
                region=REGION,
                owner_pipeline_id="9402",
                owner_job_id="60191",
                meta_json=meta_path,
            )
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (True, {"thingArn": "arn:base"}),
                        (True, {"thingArn": "arn:collision"}),
                    ],
                ),
                mock.patch.object(
                    manager, "list_principals", return_value=[PRINCIPAL]
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
                    "region": REGION,
                    "base_thing_name": BASE_THING,
                    "thing_name": ALIAS_THING,
                    "principal": PRINCIPAL,
                    "owner_pipeline_id": "9402",
                    "owner_job_id": "60191",
                    "operations": [
                        "create-thing",
                        "attach-thing-principal",
                    ],
                }
            ),
            encoding="utf-8",
        )

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
                        (True, {"thingArn": "arn:collision"}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principals",
                    return_value=[PRINCIPAL],
                ),
                mock.patch.object(manager, "run_aws") as run_aws,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "does not prove this pipeline created",
                ):
                    manager.cleanup_alias(args)

            self.assertEqual(run_aws.call_count, 0)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["actions"], [])

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
            with (
                mock.patch.object(
                    manager,
                    "describe_thing",
                    side_effect=[
                        (True, {"thingArn": "arn:base"}),
                        (True, {"thingArn": "arn:ephemeral"}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principals",
                    side_effect=[[PRINCIPAL], [PRINCIPAL, unexpected]],
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
                        (True, {"thingArn": "arn:ephemeral"}),
                        (False, {}),
                        (True, {"thingArn": "arn:base"}),
                    ],
                ),
                mock.patch.object(
                    manager,
                    "list_principals",
                    side_effect=[
                        [PRINCIPAL],
                        [PRINCIPAL],
                        [],
                        [PRINCIPAL],
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
                    manager, "list_principals", return_value=[PRINCIPAL]
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

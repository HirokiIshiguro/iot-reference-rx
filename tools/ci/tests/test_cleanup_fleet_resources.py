from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import cleanup_rx72n_fleet_resources as cleanup_fleet


class FakeAws:
    def __init__(
        self,
        *,
        certificate_state="absent",
        thing_state="absent",
        failing_deletes=(),
        delete_error_codes=None,
    ):
        self.certificate_state = certificate_state
        self.thing_state = thing_state
        self.failing_deletes = set(failing_deletes)
        self.delete_error_codes = dict(delete_error_codes or {})
        self.commands = []

    @staticmethod
    def _result(command, payload=None, *, returncode=0, error_code=None):
        stdout = json.dumps(payload or {}) if returncode == 0 else ""
        stderr = ""
        if error_code:
            stderr = f"An error occurred ({error_code}) when calling the test operation"
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    def __call__(self, command, *, capture_output, text):
        del capture_output, text
        region_index = command.index("--region")
        aws_args = command[1:region_index]
        self.commands.append(aws_args)

        if aws_args[:2] == ["sts", "get-caller-identity"]:
            return self._result(command, {"Account": "123456789012"})
        if aws_args[:2] == ["iot", "list-thing-principals"]:
            return self._result(command, {"principals": []})
        if aws_args[:2] == ["iot", "list-principal-policies"]:
            return self._result(command, {"policies": []})
        if aws_args[:2] in (["iot", "delete-certificate"], ["iot", "delete-thing"]):
            operation = aws_args[1]
            if operation in self.delete_error_codes:
                return self._result(
                    command,
                    returncode=254,
                    error_code=self.delete_error_codes[operation],
                )
            if operation in self.failing_deletes:
                return self._result(command, returncode=254, error_code="AccessDeniedException")
            return self._result(command)
        if aws_args[:2] == ["iot", "describe-certificate"]:
            return self._describe_result(command, self.certificate_state)
        if aws_args[:2] == ["iot", "describe-thing"]:
            return self._describe_result(command, self.thing_state)
        return self._result(command)

    def _describe_result(self, command, state):
        if state == "present":
            return self._result(command, {"status": "ACTIVE"})
        if state == "absent":
            return self._result(command, returncode=254, error_code="ResourceNotFoundException")
        return self._result(command, returncode=254, error_code="AccessDeniedException")


class CleanupFleetResourcesTests(unittest.TestCase):
    def _run_main(self, fake_aws, *, verify_absence, summary_payload=None):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            summary = root / "summary.json"
            output = root / "cleanup.json"
            summary.write_text(
                json.dumps(
                    summary_payload
                    or {"thing_name": "test-thing", "certificate_id": "test-certificate"}
                ),
                encoding="utf-8",
            )
            arguments = [
                "cleanup_rx72n_fleet_resources.py",
                "--summary-json",
                str(summary),
                "--region",
                "ap-northeast-1",
                "--policy-name",
                "test-policy",
                "--output-json",
                str(output),
            ]
            if verify_absence:
                arguments.append("--verify-absence")
            with mock.patch.object(sys, "argv", arguments), mock.patch.object(
                cleanup_fleet.subprocess, "run", side_effect=fake_aws
            ):
                return_code = cleanup_fleet.main()
            payload = json.loads(output.read_text(encoding="utf-8"))
        return return_code, payload

    def test_verify_absence_accepts_resource_not_found(self):
        return_code, payload = self._run_main(FakeAws(), verify_absence=True)

        self.assertEqual(return_code, 0)
        self.assertTrue(payload["verification"]["success"])
        self.assertEqual(
            [resource["state"] for resource in payload["verification"]["resources"]],
            ["absent", "absent"],
        )

    def test_verify_absence_rejects_present_resource(self):
        return_code, payload = self._run_main(
            FakeAws(certificate_state="present"), verify_absence=True
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["success"])
        self.assertIn("present", [item["state"] for item in payload["verification"]["resources"]])

    def test_verify_absence_rejects_unknown_resource_state(self):
        return_code, payload = self._run_main(FakeAws(thing_state="unknown"), verify_absence=True)

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["success"])
        self.assertIn("unknown", [item["state"] for item in payload["verification"]["resources"]])

    def test_verify_absence_rejects_delete_failure_even_if_resource_is_absent(self):
        return_code, payload = self._run_main(
            FakeAws(failing_deletes={"delete-certificate"}), verify_absence=True
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["success"])
        self.assertEqual(
            payload["verification"]["delete_failures"][0]["action"], "delete_certificate"
        )

    def test_verify_absence_is_idempotent_when_delete_reports_not_found(self):
        return_code, payload = self._run_main(
            FakeAws(
                delete_error_codes={
                    "delete-certificate": "ResourceNotFoundException",
                    "delete-thing": "ResourceNotFoundException",
                }
            ),
            verify_absence=True,
        )

        self.assertEqual(return_code, 0)
        self.assertTrue(payload["verification"]["success"])
        self.assertFalse(payload["verification"]["delete_failures"])
        delete_actions = [
            action for action in payload["actions"] if action["action"].startswith("delete_")
        ]
        self.assertTrue(all(action["already_absent"] for action in delete_actions))

    def test_flag_off_preserves_best_effort_success(self):
        fake_aws = FakeAws(failing_deletes={"delete-certificate", "delete-thing"})
        return_code, payload = self._run_main(fake_aws, verify_absence=False)

        self.assertEqual(return_code, 0)
        self.assertNotIn("verification", payload)
        self.assertFalse(any(command[1].startswith("describe-") for command in fake_aws.commands))

    def test_verify_absence_rejects_missing_identifiers_after_claim_session(self):
        return_code, payload = self._run_main(
            FakeAws(),
            verify_absence=True,
            summary_payload={
                "thing_name": None,
                "certificate_id": None,
                "results": {"claim_mqtt": True, "certificate": False, "thing_name": False},
            },
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["success"])
        self.assertTrue(payload["verification"]["resource_creation_may_have_started"])


if __name__ == "__main__":
    unittest.main()

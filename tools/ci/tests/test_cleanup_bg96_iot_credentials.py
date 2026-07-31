from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import cleanup_bg96_iot_credentials as cleanup_credentials


class FakeAws:
    def __init__(
        self,
        *,
        failing_operation: tuple[str, str] | None = None,
        certificate_state: str = "absent",
        thing_state: str = "absent",
        all_not_found: bool = False,
        invalid_json_operation: tuple[str, str] | None = None,
        principals: list[str] | None = None,
        policies: list[str] | None = None,
    ):
        self.failing_operation = failing_operation
        self.certificate_state = certificate_state
        self.thing_state = thing_state
        self.all_not_found = all_not_found
        self.invalid_json_operation = invalid_json_operation
        self.principals = principals
        self.policies = policies
        self.commands: list[list[str]] = []

    @staticmethod
    def result(command, payload=None, *, returncode=0, error_code=None):
        stdout = json.dumps(payload or {}) if returncode == 0 else ""
        stderr = (
            f"An error occurred ({error_code}) when calling the test operation"
            if error_code
            else ""
        )
        return subprocess.CompletedProcess(
            command, returncode, stdout=stdout, stderr=stderr
        )

    def __call__(self, command, *, capture_output, text):
        del capture_output, text
        region_index = command.index("--region")
        aws_args = command[1:region_index]
        self.commands.append(aws_args)
        operation = tuple(aws_args[:2])

        if self.invalid_json_operation == operation:
            return subprocess.CompletedProcess(
                command, 0, stdout="{not-json", stderr=""
            )
        if self.failing_operation == operation:
            return self.result(
                command, returncode=254, error_code="AccessDeniedException"
            )
        if self.all_not_found:
            return self.result(
                command, returncode=254, error_code="ResourceNotFoundException"
            )
        if operation == ("iot", "list-thing-principals"):
            return self.result(
                command,
                {
                    "principals": self.principals
                    if self.principals is not None
                    else [
                        "arn:aws:iot:ap-northeast-1:123456789012:cert/test-cert"
                    ],
                },
            )
        if operation == ("iot", "list-principal-policies"):
            names = self.policies if self.policies is not None else ["test-policy"]
            return self.result(
                command,
                {"policies": [{"policyName": name} for name in names]},
            )
        if operation == ("iot", "describe-certificate"):
            return self.describe(command, self.certificate_state)
        if operation == ("iot", "describe-thing"):
            return self.describe(command, self.thing_state)
        return self.result(command)

    def describe(self, command, state):
        if state == "absent":
            return self.result(
                command, returncode=254, error_code="ResourceNotFoundException"
            )
        if state == "present":
            return self.result(command, {"present": True})
        return self.result(command, returncode=254, error_code="AccessDeniedException")


class CleanupBg96IotCredentialsTests(unittest.TestCase):
    def run_main(
        self,
        fake_aws,
        *,
        metadata=None,
        create_metadata=True,
        expected_thing_name="",
        expected_policy_name="",
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            meta_path = root / "metadata.json"
            output_path = root / "cleanup.json"
            if create_metadata:
                meta_path.write_text(
                    json.dumps(
                        metadata
                        or {
                            "region": "ap-northeast-1",
                            "thing_name": "test-thing",
                            "certificate_id": "test-cert",
                            "certificate_arn": (
                                "arn:aws:iot:ap-northeast-1:"
                                "123456789012:cert/test-cert"
                            ),
                            "policy_name": "test-policy",
                        }
                    ),
                    encoding="utf-8",
                )
            arguments = [
                "cleanup_bg96_iot_credentials.py",
                "--meta-json",
                str(meta_path),
                "--output-json",
                str(output_path),
            ]
            if expected_thing_name:
                arguments.extend(["--expected-thing-name", expected_thing_name])
            if expected_policy_name:
                arguments.extend(["--expected-policy-name", expected_policy_name])
            with mock.patch.object(sys, "argv", arguments), mock.patch.object(
                cleanup_credentials.subprocess, "run", side_effect=fake_aws
            ):
                return_code = cleanup_credentials.main()
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        return return_code, payload

    def test_cleanup_succeeds_only_after_both_resources_are_absent(self):
        fake_aws = FakeAws()
        return_code, payload = self.run_main(fake_aws)

        self.assertEqual(return_code, 0)
        self.assertTrue(payload["verification"]["passed"])
        self.assertEqual(
            [resource["state"] for resource in payload["verification"]["resources"]],
            ["absent", "absent"],
        )

    def test_not_found_is_idempotent_success(self):
        return_code, payload = self.run_main(FakeAws(all_not_found=True))

        self.assertEqual(return_code, 0)
        self.assertTrue(payload["verification"]["passed"])
        self.assertTrue(
            all(action["already_absent"] for action in payload["actions"])
        )

    def test_non_not_found_failure_is_reported_and_cleanup_continues(self):
        fake_aws = FakeAws(failing_operation=("iot", "detach-policy"))
        return_code, payload = self.run_main(fake_aws)

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertEqual(payload["errors"][0]["aws_error_code"], "AccessDeniedException")
        self.assertIn(
            ["iot", "delete-thing", "--thing-name", "test-thing"],
            fake_aws.commands,
        )

    def test_present_resource_fails_absence_verification(self):
        return_code, payload = self.run_main(
            FakeAws(certificate_state="present")
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertIn(
            "present",
            [resource["state"] for resource in payload["verification"]["resources"]],
        )

    def test_unknown_resource_state_fails_absence_verification(self):
        return_code, payload = self.run_main(FakeAws(thing_state="unknown"))

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertIn(
            "unknown",
            [resource["state"] for resource in payload["verification"]["resources"]],
        )

    def test_invalid_aws_json_fails_closed(self):
        return_code, payload = self.run_main(
            FakeAws(invalid_json_operation=("iot", "list-thing-principals"))
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertTrue(payload["errors"][0]["parse_error"])
        self.assertEqual(payload["actions"], [])

    def test_discovery_api_error_performs_no_mutation(self):
        return_code, payload = self.run_main(
            FakeAws(failing_operation=("iot", "list-thing-principals"))
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertEqual(payload["actions"], [])

    def test_unexpected_principal_performs_no_mutation(self):
        return_code, payload = self.run_main(
            FakeAws(
                principals=[
                    "arn:aws:iot:ap-northeast-1:123456789012:cert/test-cert",
                    "arn:aws:iot:ap-northeast-1:123456789012:cert/not-owned",
                ]
            )
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertEqual(payload["actions"], [])

    def test_unexpected_policy_performs_no_mutation(self):
        return_code, payload = self.run_main(
            FakeAws(policies=["test-policy", "not-owned-policy"])
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertEqual(payload["actions"], [])

    def test_incomplete_metadata_fails_before_aws_actions(self):
        fake_aws = FakeAws()
        return_code, payload = self.run_main(
            fake_aws,
            metadata={
                "region": "ap-northeast-1",
                "thing_name": "test-thing",
                "certificate_id": "test-cert",
            },
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertEqual(fake_aws.commands, [])

    def test_expected_identity_mismatch_fails_before_aws_actions(self):
        fake_aws = FakeAws()
        return_code, payload = self.run_main(
            fake_aws,
            expected_thing_name="different-thing",
            expected_policy_name="test-policy",
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertEqual(fake_aws.commands, [])

    def test_missing_metadata_fails_closed(self):
        return_code, payload = self.run_main(
            FakeAws(), create_metadata=False
        )

        self.assertEqual(return_code, 1)
        self.assertFalse(payload["verification"]["passed"])
        self.assertEqual(payload["errors"][0]["reason"], "metadata_not_found")


if __name__ == "__main__":
    unittest.main()

"""Mock-only ownership/lifecycle tests; no AWS connection is made."""
import json
from unittest.mock import patch
try:
    from . import ota_aws_signers as module
    from .ota_support_tests import OtaSupportTests
except ImportError:
    import ota_aws_signers as module
    from ota_support_tests import OtaSupportTests


class ApiError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class Acm:
    def __init__(self):
        self.certificates = {}
        self.deleted = []
        self.fail_second = False
        self.in_use_once = False

    def import_certificate(self, **request):
        if self.fail_second and self.certificates:
            raise ApiError("AccessDeniedException")
        index = len(self.certificates) + 1
        arn = f"arn:aws:acm:ap-northeast-1:123456789012:certificate/00000000-0000-0000-0000-{index:012d}"
        self.certificates[arn] = {"Tags": request["Tags"]}
        return {"CertificateArn": arn}

    def list_tags_for_certificate(self, CertificateArn):
        if CertificateArn not in self.certificates:
            raise ApiError("ResourceNotFoundException")
        return self.certificates[CertificateArn]

    def delete_certificate(self, CertificateArn):
        if self.in_use_once:
            self.in_use_once = False
            raise ApiError("ResourceInUseException")
        self.certificates.pop(CertificateArn, None)
        self.deleted.append(CertificateArn)

    def describe_certificate(self, CertificateArn):
        if CertificateArn not in self.certificates:
            raise ApiError("ResourceNotFoundException")
        return {"Certificate": {"InUseBy": []}}


class Signer:
    def __init__(self):
        self.profiles = []
        self.canceled = []

    def list_signing_profiles(self, **_request):
        return {"profiles": self.profiles}

    def get_signing_profile(self, profileName):
        return next(item for item in self.profiles if item["profileName"] == profileName)

    def cancel_signing_profile(self, profileName):
        self.canceled.append(profileName)
        self.get_signing_profile(profileName)["status"] = "Canceled"


class AwsSignerTests(OtaSupportTests):
    def setUp(self):
        super().setUp()
        self.acm, self.signer = Acm(), Signer()
        mock = patch.object(module, "_clients", return_value=(self.acm, self.signer))
        mock.start()
        self.addCleanup(mock.stop)

    def prepare(self):
        return module.prepare_aws_signers(self.inputs, "ap-northeast-1", "unit-run", self.config)

    def test_native_config_and_owned_certificates_cleanup(self):
        native = self.prepare()["codeSigningConfiguration"]
        self.assertEqual(native["signingMethod"], "AWS")
        self.assertNotIn("signCommand", native)
        self.assertEqual(native["signerPlatform"], "AmazonFreeRTOS-Default")
        journal = module.cleanup_aws_signers(self.inputs)
        self.assertEqual(journal["state"], "cleaned")
        self.assertEqual(len(self.acm.deleted), 2)
        raw = (self.inputs / module.JOURNAL).read_text()
        self.assertNotIn("PRIVATE KEY", raw)
        self.assertNotIn("BEGIN CERTIFICATE", raw)

    def test_wrong_run_tag_prevents_deletion(self):
        self.prepare()
        arn = next(iter(self.acm.certificates))
        self.acm.certificates[arn]["Tags"] = [{"Key": "codex:run-id", "Value": "another-run"}]
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            module.cleanup_aws_signers(self.inputs)
        self.assertNotIn(arn, self.acm.deleted)
        self.assertEqual(self.signer.canceled, [])

    def test_in_use_cancels_only_profile_using_owned_certificate(self):
        self.prepare()
        arn = next(iter(self.acm.certificates))
        self.signer.profiles = [
            {"profileName": "owned", "status": "Active", "signingMaterial": {"certificateArn": arn}},
            {"profileName": "unrelated", "status": "Active", "signingMaterial": {"certificateArn": "other"}}]
        self.acm.in_use_once = True
        with patch.object(module.time, "sleep"):
            module.cleanup_aws_signers(self.inputs)
        self.assertEqual(self.signer.canceled, ["owned"])

    def test_partial_import_is_journaled_before_second_call_fails(self):
        self.acm.fail_second = True
        with self.assertRaisesRegex(RuntimeError, "AccessDeniedException"):
            self.prepare()
        journal = json.loads((self.inputs / module.JOURNAL).read_text())
        self.assertEqual(len(journal["certificates"]), 1)
        self.assertEqual(journal["certificates"][0]["role"], "trusted")
        self.assertEqual(journal["state"], "prepare_failed")

    def test_transient_windows_ready_rename_does_not_repeat_aws_import(self):
        replace = module.os.replace
        failed = []
        def sharing_violation_once(source, target):
            if json.loads(source.read_text())["state"] == "ready" and not failed:
                failed.append(True)
                error = PermissionError("test sharing violation")
                error.winerror = 32
                raise error
            return replace(source, target)
        with patch.object(module.os, "replace", side_effect=sharing_violation_once), \
                patch.object(module.time, "sleep") as sleep:
            self.prepare()
        self.assertEqual(len(self.acm.certificates), 2)
        self.assertEqual(json.loads((self.inputs / module.JOURNAL).read_text())["state"], "ready")
        sleep.assert_called_once_with(0.05)
        self.assertEqual(list(self.inputs.glob(module.JOURNAL + ".*.tmp")), [])

    def test_persistent_windows_rename_failure_is_bounded_and_preserves_journal(self):
        path = self.inputs / "rename-test.json"
        module._persist(path, {"state": "before"}, initial=True)
        error = PermissionError("test permanent access denial")
        error.winerror = 5
        with patch.object(module.os, "replace", side_effect=error) as replace, \
                patch.object(module.time, "sleep") as sleep:
            with self.assertRaises(PermissionError):
                module._persist(path, {"state": "after"})
        self.assertEqual(replace.call_count, 5)
        self.assertEqual(sleep.call_count, 4)
        self.assertEqual(json.loads(path.read_text())["state"], "before")
        temporary = list(self.inputs.glob("rename-test.json.*.tmp"))
        self.assertEqual(len(temporary), 1)
        self.assertEqual(json.loads(temporary[0].read_text())["state"], "after")

    def test_other_permission_errors_are_not_retried(self):
        path = self.inputs / "rename-test.json"
        module._persist(path, {"state": "before"}, initial=True)
        with patch.object(module.os, "replace", side_effect=PermissionError("test denial")) as replace, \
                patch.object(module.time, "sleep") as sleep:
            with self.assertRaises(PermissionError):
                module._persist(path, {"state": "after"})
        self.assertEqual(replace.call_count, 1)
        sleep.assert_not_called()


def load_tests(loader, _tests, _pattern):
    return loader.loadTestsFromTestCase(AwsSignerTests)


if __name__ == "__main__":
    import unittest
    unittest.main()

"""Mock-only ownership/lifecycle tests; no AWS connection is made."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
try:
    from . import ota_aws_signers as module
except ImportError:
    import ota_aws_signers as module

ORIGINAL_CLIENTS = module._clients


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


class AwsSignerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="idt-signer-unit-")
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {"CI": "false"})
        environment.start()
        self.addCleanup(environment.stop)
        self.inputs = Path(temporary.name)
        self.config = {"codeSigningConfiguration": {"signCommand": "test"}}
        now = datetime.now(timezone.utc)
        for cert_name, key_name in ((module.TRUSTED_CERT, module.SIGNING_KEY),
                                    (module.UNTRUSTED_CERT, module.UNTRUSTED_KEY)):
            key = ec.generate_private_key(ec.SECP256R1())
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "unit-test")])
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                    .public_key(key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=1))
                    .not_valid_after(now + timedelta(days=1)).sign(key, hashes.SHA256()))
            (self.inputs / cert_name).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            (self.inputs / key_name).write_bytes(key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
        self.acm, self.signer = Acm(), Signer()
        mock = patch.object(module, "_clients", return_value=(self.acm, self.signer))
        mock.start()
        self.addCleanup(mock.stop)

    def prepare(self):
        return module.prepare_aws_signers(self.inputs, "ap-northeast-1", "unit-run", self.config)

    def test_aws_clients_disable_automatic_mutation_retries(self):
        session = Mock()
        ORIGINAL_CLIENTS("ap-northeast-1", session)
        self.assertEqual(2, session.client.call_count)
        for call in session.client.call_args_list:
            self.assertEqual(1, call.kwargs["config"].retries["total_max_attempts"])

    def test_ci_or_oidc_native_ota_stops_before_import(self):
        for value in ({"CI": "true"}, {"RX_OIDC_EXPIRATION_UTC": "synthetic"}):
            with self.subTest(value=value), patch.dict(os.environ, value), self.assertRaisesRegex(RuntimeError, "not ready"):
                self.prepare()
            self.assertEqual({}, self.acm.certificates)

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

    def test_same_certificate_other_run_profile_is_never_canceled_or_deleted(self):
        self.prepare()
        arn = next(iter(self.acm.certificates))
        self.signer.profiles = [
            {"profileName": "other-run", "status": "Active", "signingMaterial": {"certificateArn": arn}},
            {"profileName": "unrelated", "status": "Active", "signingMaterial": {"certificateArn": "other"}}]
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            module.cleanup_aws_signers(self.inputs)
        self.assertEqual(self.signer.canceled, [])
        self.assertNotIn(arn, self.acm.deleted)
        self.assertIn(arn, self.acm.certificates)

    def test_in_use_without_profile_evidence_never_cancels(self):
        self.prepare()
        arn = next(iter(self.acm.certificates))
        self.acm.in_use_once = True
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            module.cleanup_aws_signers(self.inputs)
        self.assertNotIn(arn, self.acm.deleted)
        self.assertEqual(self.signer.canceled, [])

    def test_profile_scan_follows_pages_and_includes_canceled(self):
        self.prepare()
        arn = next(iter(self.acm.certificates))
        calls = []

        def pages(**request):
            calls.append(request)
            if "nextToken" not in request:
                return {"profiles": [], "nextToken": "page-2"}
            return {"profiles": [{"profileName": "other", "status": "Canceled",
                                   "signingMaterial": {"certificateArn": arn}}]}

        self.signer.list_signing_profiles = pages
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            module.cleanup_aws_signers(self.inputs)
        self.assertTrue(all(call["includeCanceled"] for call in calls))
        self.assertNotIn(arn, self.acm.deleted)
        self.assertEqual(self.signer.canceled, [])

    def test_profile_scan_failure_or_unknown_material_retains_certificate(self):
        for response in (ApiError("AccessDeniedException"), {"profiles": [{}]}, {}):
            with self.subTest(response=response):
                self.prepare()
                original = set(self.acm.certificates)
                with patch.object(self.signer, "list_signing_profiles",
                                  side_effect=response if isinstance(response, Exception) else None,
                                  return_value=response):
                    with self.assertRaisesRegex(RuntimeError, "incomplete"):
                        module.cleanup_aws_signers(self.inputs)
                self.assertEqual(original, set(self.acm.certificates))
                self.assertEqual(self.signer.canceled, [])
                (self.inputs / module.JOURNAL).unlink()
                self.acm.certificates.clear()

    def test_snapshot_is_complete_paginated_and_contains_only_identifiers(self):
        calls = []
        profile = {"profileName": "other", "arn": "arn:aws:signer:region:account:/signing-profiles/other",
                   "profileVersion": "a" * 10, "profileVersionArn": "version-arn", "status": "Canceled",
                   "signingMaterial": {"certificateArn": "not-saved"}, "tags": {"private": "not-saved"}}

        def pages(**request):
            calls.append(request)
            return {"profiles": [], "nextToken": "next"} if "nextToken" not in request else {"profiles": [profile]}

        self.signer.list_signing_profiles = pages
        snapshot = module.profile_snapshot(self.signer, module.time.monotonic() + 10)
        self.assertEqual([{"profileName": "other", "arn": profile["arn"], "profileVersion": "a" * 10,
                           "profileVersionArn": "version-arn", "status": "Canceled"}], snapshot)
        self.assertTrue(all(call["includeCanceled"] for call in calls))

    def test_snapshot_rejects_incomplete_or_repeated_pagination(self):
        for response in ({"profiles": [{}]}, {"profiles": [], "nextToken": "same"}, {}):
            with self.subTest(response=response), patch.object(self.signer, "list_signing_profiles", return_value=response):
                with self.assertRaises(RuntimeError):
                    module.profile_snapshot(self.signer, module.time.monotonic() + 10)

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
    unittest.main()

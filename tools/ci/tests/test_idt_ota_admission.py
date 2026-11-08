"""Offline admission races and original-run/recovery identity checks."""
from dataclasses import replace
import hashlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.idt import ota_admission
from tools.idt.ota_admission import AdmissionError, AdmissionStore, RunIdentity


class ApiError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class S3:
    def __init__(self):
        self.meta = SimpleNamespace(config=SimpleNamespace(retries={"total_max_attempts": 1}))
        self.versions = []
        self.enabled = True
        self.put_calls = []
        self.fail_read = False
        self.lose_put_response = False
        self.conflict = False
        self.history_hidden = False
        self.race_readback = False

    def get_bucket_versioning(self, **request):
        assert request["ExpectedBucketOwner"] == "123456789012"
        return {"Status": "Enabled" if self.enabled else "Suspended"}

    def list_object_versions(self, **_request):
        return {"Versions": self.versions[:1], "IsTruncated": False}

    def get_object(self, **request):
        if self.fail_read:
            raise ApiError("AccessDenied")
        candidates = [v for v in self.versions if v["VersionId"] == request.get("VersionId")] if request.get("VersionId") else self.versions[-1:]
        if not candidates or self.history_hidden:
            raise ApiError("NoSuchKey")
        version = candidates[-1]
        if request.get("VersionId") and self.race_readback:
            self.race_readback = False
            changed = dict(version)
            changed.update(VersionId="external", ETag='"external"')
            self.versions.append(changed)
        return {"Body": io.BytesIO(version["Body"]), "ETag": version["ETag"], "VersionId": version["VersionId"]}

    def put_object(self, **request):
        self.put_calls.append({k: v for k, v in request.items() if k != "Body"})
        current = self.versions[-1] if self.versions else None
        if (self.conflict or request.get("IfNoneMatch") == "*" and current
                or "IfMatch" in request and (not current or request["IfMatch"] != current["ETag"])):
            raise ApiError("PreconditionFailed")
        body = request["Body"]
        v = {"VersionId": str(len(self.versions) + 1), "ETag": '"' + hashlib.sha256(body).hexdigest() + '"', "Body": body}
        self.versions.append(v)
        if self.lose_put_response:
            raise ApiError("ConnectionClosed")
        return {"VersionId": v["VersionId"], "ETag": v["ETag"]}


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.s3 = S3()
        self.store = AdmissionStore(self.s3, "test-bucket", "private/idt", "123456789012",
                                    "123456789012", "ap-northeast-1")
        self.original = RunIdentity("123456789012", "ap-northeast-1", "38", "100", "101", "a" * 40, "run-1")
        self.recovery = replace(self.original, pipeline_id="200", job_id="201", source_sha="b" * 40, run_id="recovery-1")

    def test_active_and_unknown_block_next_run_until_verified_recovery(self):
        first, _, version = self.store.begin(self.original)
        self.assertEqual(self.s3.put_calls[-1]["IfNoneMatch"], "*")
        with self.assertRaises(AdmissionError):
            self.store.begin(replace(self.original, run_id="run-2"))
        unknown, _, version = self.store.mark_unknown(self.original, "host_loss", (first["request_id"], version))
        fence = (unknown["request_id"], version)
        with self.assertRaises(AdmissionError):
            self.store.begin(replace(self.original, run_id="run-2"))
        with self.assertRaises(AdmissionError):
            self.store.mark_cleaned(self.original, self.recovery, fence, native_stopped=False, ownership_verified=True)
        with self.assertRaises(AdmissionError):
            self.store.mark_cleaned(self.original, self.recovery, fence, native_stopped=True, ownership_verified=False)
        with patch.object(ota_admission, "EVIDENCE_VERIFICATION_READY", True):
            record, _, _ = self.store.mark_cleaned(self.original, self.recovery, fence,
                                                   native_stopped=True, ownership_verified=True)
        self.assertEqual(record["original"]["job_id"], "101")
        self.assertEqual(record["recovery_job"]["job_id"], "201")
        self.assertEqual(record["recovery_job"]["source_sha"], "b" * 40)
        self.store.begin(replace(self.original, run_id="run-2"))
        self.assertIn("IfMatch", self.s3.put_calls[-1])

    def test_wrong_original_or_recovery_scope_cannot_clean(self):
        first, _, version = self.store.begin(self.original)
        fence = (first["request_id"], version)
        for original, recovery in ((replace(self.original, job_id="999"), self.recovery),
                                   (self.original, replace(self.recovery, account="999999999999")),
                                   (self.original, replace(self.recovery, project_id="999")),
                                   (self.original, self.original)):
            with self.subTest(original=original), self.assertRaises(AdmissionError):
                self.store.mark_cleaned(original, recovery, fence, native_stopped=True, ownership_verified=True)
        self.assertEqual(len(self.s3.put_calls), 1)

    def test_conflict_or_lost_response_is_not_retried(self):
        for lose in (False, True):
            self.s3.conflict = not lose
            self.s3.lose_put_response = lose
            with self.assertRaisesRegex(AdmissionError, "outcome unknown"):
                self.store.begin(self.original)
            self.assertEqual(len(self.s3.put_calls), 1)
            self.s3.put_calls.clear()
        self.assertEqual(len(self.s3.versions), 1)
        with self.assertRaisesRegex(AdmissionError, "unresolved"):
            self.store.begin(self.original)
        record, _, version = self.store.inspect(self.original)
        self.assertEqual("ACTIVE", record["state"])
        self.assertEqual("1", version)
        with self.assertRaisesRegex(AdmissionError, "mismatch"):
            self.store.inspect(replace(self.original, job_id="999"))

    def test_deleted_current_with_history_and_denied_access_fail_closed(self):
        self.store.begin(self.original)
        self.s3.history_hidden = True
        with self.assertRaisesRegex(AdmissionError, "history"):
            self.store.begin(self.original)
        self.s3.history_hidden = False
        self.s3.fail_read = True
        with self.assertRaisesRegex(AdmissionError, "read failed"):
            self.store.begin(self.original)
        self.assertEqual(len(self.s3.put_calls), 1)

    def test_readback_rejects_concurrent_latest_version_change(self):
        self.s3.race_readback = True
        with self.assertRaisesRegex(AdmissionError, "outcome unknown"):
            self.store.begin(self.original)
        self.assertEqual(1, len(self.s3.put_calls))

    def test_versioning_disabled_and_malformed_record_fail_closed(self):
        self.s3.enabled = False
        with self.assertRaisesRegex(AdmissionError, "versioning"):
            self.store.begin(self.original)
        self.s3.enabled = True
        self.store.begin(self.original)
        self.s3.versions[-1]["Body"] = json.dumps({"state": "CLEANED"}).encode()
        with self.assertRaisesRegex(AdmissionError, "invalid"):
            self.store.begin(self.original)

    def test_client_with_automatic_retries_is_rejected(self):
        self.s3.meta.config.retries = {"total_max_attempts": 2}
        with self.assertRaisesRegex(AdmissionError, "disable SDK retries"):
            AdmissionStore(self.s3, "test-bucket", "private/idt", "123456789012",
                           "123456789012", "ap-northeast-1")

    def test_pre_native_profile_intent_uses_original_scope_and_cas(self):
        first, _, version = self.store.begin(self.original)
        fence = (first["request_id"], version)
        cert = "arn:aws:acm:ap-northeast-1:123456789012:certificate/00000000-0000-0000-0000-000000000001"
        arn = "arn:aws:signer:ap-northeast-1:123456789012:/signing-profiles/existing"
        profile = {"profileName": "existing", "arn": arn, "profileVersion": "a" * 10,
                   "profileVersionArn": arn + "/" + "a" * 10, "status": "Canceled"}
        record, _, version = self.store.record_profile_intent(self.original, [cert], [profile], fence)
        self.assertEqual([profile], record["profile_intent"]["before"])
        self.assertIn("IfMatch", self.s3.put_calls[-1])
        with self.assertRaises(AdmissionError):
            self.store.record_profile_intent(self.original, [cert], [profile], fence)
        with self.assertRaisesRegex(AdmissionError, "stale"):
            self.store.mark_unknown(self.original, "host_loss", fence)
        unknown, _, _ = self.store.mark_unknown(self.original, "host_loss", (record["request_id"], version))
        self.assertEqual(record["profile_intent"], unknown["profile_intent"])

    def test_bad_snapshot_or_certificate_scope_never_writes(self):
        first, _, version = self.store.begin(self.original)
        fence = (first["request_id"], version)
        cert = "arn:aws:acm:ap-northeast-1:123456789012:certificate/00000000-0000-0000-0000-000000000001"
        arn = "arn:aws:signer:ap-northeast-1:123456789012:/signing-profiles/existing"
        profile = {"profileName": "existing", "arn": arn, "profileVersion": "a" * 10,
                   "profileVersionArn": arn + "/" + "a" * 10, "status": "Active"}
        for certs, profiles in (([cert.replace("123456789012", "999999999999")], [profile]),
                                ([cert], [{**profile, "profileVersionArn": arn + "/wrong"}]),
                                ([cert], [profile, profile]), ([cert], [{**profile, "raw": "not allowed"}])):
            with self.subTest(certs=certs), self.assertRaises(AdmissionError):
                self.store.record_profile_intent(self.original, certs, profiles, fence)
        self.assertEqual(1, len(self.s3.put_calls))

    def test_normal_completion_is_separate_from_independent_recovery(self):
        first, _, version = self.store.begin(self.original)
        fence = (first["request_id"], version)
        with self.assertRaises(AdmissionError):
            self.store.complete_cleaned(self.original, self.recovery, fence,
                                        native_stopped=True, ownership_verified=True)
        with patch.object(ota_admission, "EVIDENCE_VERIFICATION_READY", True):
            result, _, _ = self.store.complete_cleaned(self.original, self.original, fence,
                                                       native_stopped=True, ownership_verified=True)
        self.assertEqual("101", result["completion_job"]["job_id"])

    def test_unconnected_evidence_verifier_cannot_clear_admission(self):
        first, _, version = self.store.begin(self.original)
        fence = (first["request_id"], version)
        with self.assertRaisesRegex(AdmissionError, "evidence is not connected"):
            self.store.mark_cleaned(self.original, self.recovery, fence,
                                    native_stopped=True, ownership_verified=True)
        with self.assertRaisesRegex(AdmissionError, "evidence is not connected"):
            self.store.complete_cleaned(self.original, self.original, fence,
                                        native_stopped=True, ownership_verified=True)
        self.assertEqual(1, len(self.s3.put_calls))


if __name__ == "__main__":
    unittest.main()

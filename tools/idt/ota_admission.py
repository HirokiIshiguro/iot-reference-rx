"""Versioned S3 admission checkpoint for serialized IDT OTA runs.

This is not connected to CI yet. Callers must independently authenticate the
current job and hold the reviewed resource group; this module does neither.
Conditional writes detect competing managed writers, not arbitrary S3 admin
operations. Bucket versioning and protection of history must be verified in
the deployment before use. Ambiguous AWS outcomes are never retried here.
"""
from dataclasses import asdict, dataclass
import json
import re
import uuid

EVIDENCE_VERIFICATION_READY = False


class AdmissionError(RuntimeError):
    """Admission cannot be established or its outcome is unknown."""


@dataclass(frozen=True)
class RunIdentity:
    account: str
    region: str
    project_id: str
    pipeline_id: str
    job_id: str
    source_sha: str
    run_id: str


def _valid_identity(identity):
    if not isinstance(identity, RunIdentity):
        return False
    if any(not isinstance(value, str) for value in asdict(identity).values()):
        return False
    return (bool(re.fullmatch(r"[0-9]{12}", identity.account))
            and bool(re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-[0-9]", identity.region))
            and all(bool(re.fullmatch(r"[0-9]{1,20}", value))
                    for value in (identity.project_id, identity.pipeline_id, identity.job_id))
            and bool(re.fullmatch(r"[0-9a-f]{40}", identity.source_sha))
            and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identity.run_id)))


def _code(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code")


class AdmissionStore:
    def __init__(self, s3, bucket, prefix, expected_bucket_owner, account, region):
        if (not all(isinstance(x, str) and x for x in (bucket, prefix, expected_bucket_owner, account, region))
                or not re.fullmatch(r"[0-9]{12}", expected_bucket_owner)
                or not re.fullmatch(r"[0-9]{12}", account)
                or not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-[0-9]", region)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]{0,255}", prefix)
                or any(part in ("", ".", "..") for part in prefix.split("/"))):
            raise AdmissionError("invalid admission location")
        config = getattr(getattr(s3, "meta", None), "config", None)
        retries = getattr(config, "retries", None)
        if not isinstance(retries, dict) or retries.get("total_max_attempts") != 1:
            raise AdmissionError("admission client must disable SDK retries")
        self.s3, self.bucket, self.owner = s3, bucket, expected_bucket_owner
        self.account, self.region = account, region
        self.key = f"{prefix}/{account}/{region}/admission.json"

    def _base(self):
        return {"Bucket": self.bucket, "ExpectedBucketOwner": self.owner}

    def _versioning(self):
        if self.s3.get_bucket_versioning(**self._base()).get("Status") != "Enabled":
            raise AdmissionError("journal bucket versioning is not enabled")

    def _read(self, *, version_id=None):
        request = {**self._base(), "Key": self.key}
        if version_id is not None:
            request["VersionId"] = version_id
        try:
            response = self.s3.get_object(**request)
        except Exception as error:
            if version_id is None and _code(error) in ("NoSuchKey", "404", "NotFound"):
                return None
            raise AdmissionError("admission read failed") from None
        body = response.get("Body")
        try:
            if body is None:
                raise ValueError
            payload = body.read(32769)
            if len(payload) > 32768:
                raise ValueError
            record = json.loads(payload)
        except (ValueError, TypeError, UnicodeError):
            raise AdmissionError("invalid admission record") from None
        finally:
            if body is not None:
                body.close()
        etag, version = response.get("ETag"), response.get("VersionId")
        if (not isinstance(record, dict) or record.get("schema") != 1
                or record.get("state") not in ("ACTIVE", "UNKNOWN", "CLEANED")
                or not isinstance(record.get("request_id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", record["request_id"])
                or not isinstance(record.get("original"), dict)
                or not isinstance(etag, str) or not etag
                or not isinstance(version, str) or not version or version == "null"):
            raise AdmissionError("invalid admission metadata")
        try:
            original = RunIdentity(**record["original"])
        except (TypeError, ValueError):
            raise AdmissionError("invalid original run") from None
        if not _valid_identity(original) or (original.account, original.region) != (self.account, self.region):
            raise AdmissionError("admission scope mismatch")
        allowed = {"schema", "state", "request_id", "original", "supersedes_version", "profile_intent", "reason",
                   "recovery_job", "completion_job"}
        previous = record.get("supersedes_version")
        if (set(record) - allowed or "supersedes_version" not in record
                or previous is not None and (not isinstance(previous, str) or not previous or previous == "null")
                or "profile_intent" in record and not isinstance(record["profile_intent"], dict)):
            raise AdmissionError("invalid admission contents")
        state = record["state"]
        if state == "ACTIVE" and "reason" in record:
            raise AdmissionError("invalid active outcome")
        if state == "UNKNOWN" and record.get("reason") not in {"host_loss", "ownership", "response", "external_change"}:
            raise AdmissionError("invalid unknown outcome")
        if "profile_intent" in record:
            intent = record["profile_intent"]
            if set(intent) != {"certificates", "before"}:
                raise AdmissionError("invalid profile intent")
            self._validate_profile_intent(intent["certificates"], intent["before"])
        if state != "CLEANED" and ("recovery_job" in record or "completion_job" in record):
            raise AdmissionError("invalid completion evidence")
        if state == "CLEANED":
            if ("recovery_job" in record) == ("completion_job" in record):
                raise AdmissionError("missing completion identity")
            try:
                actor = RunIdentity(**record.get("recovery_job", record.get("completion_job")))
            except (TypeError, ValueError):
                raise AdmissionError("invalid completion identity") from None
            if (not _valid_identity(actor) or (actor.account, actor.region, actor.project_id)
                    != (original.account, original.region, original.project_id)
                    or ("recovery_job" in record and actor.job_id == original.job_id)
                    or ("completion_job" in record and actor != original)):
                raise AdmissionError("completion identity mismatch")
        return record, etag, version

    def _assert_no_history(self):
        # One page is enough to establish nonempty history. IsTruncated also
        # fails closed, even if a malformed response omits entries.
        page = self.s3.list_object_versions(**self._base(), Prefix=self.key, MaxKeys=1)
        if page.get("IsTruncated") or page.get("Versions") or page.get("DeleteMarkers"):
            raise AdmissionError("missing current admission has history")

    def _write(self, record, condition):
        payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(payload) > 32768:
            raise AdmissionError("admission record too large")
        try:
            response = self.s3.put_object(**self._base(), Key=self.key, Body=payload,
                                          ContentType="application/json", **condition)
            version, etag = response.get("VersionId"), response.get("ETag")
            if not version or version == "null" or not etag:
                raise ValueError
            readback = self._read(version_id=version)
            latest = self._read()
            if readback is None or readback != (record, etag, version) or latest != readback:
                raise ValueError
        except Exception:
            # Includes conflicts, response loss and failed readback: the write
            # may have happened, so do not repeat it or claim success.
            raise AdmissionError("admission write outcome unknown") from None
        return record, etag, version

    def begin(self, original):
        """Start only after an absent, history-free record or CLEANED record."""
        if not _valid_identity(original) or (original.account, original.region) != (self.account, self.region):
            raise AdmissionError("invalid original run")
        try:
            self._versioning()
            current = self._read()
            if current is None:
                self._assert_no_history()
                condition = {"IfNoneMatch": "*"}
                previous_version = None
            else:
                record, etag, previous_version = current
                if record["state"] != "CLEANED":
                    raise AdmissionError("previous run remains unresolved")
                if record["original"] == asdict(original):
                    raise AdmissionError("run identity cannot be reused")
                condition = {"IfMatch": etag}
            new = {"schema": 1, "state": "ACTIVE", "request_id": uuid.uuid4().hex,
                   "original": asdict(original), "supersedes_version": previous_version}
            return self._write(new, condition)
        except AdmissionError:
            raise
        except Exception:
            raise AdmissionError("admission check failed") from None

    def inspect(self, original):
        """Read an exact original run after current-job authentication.

        The returned record can contain profile identifiers and belongs in a
        private runtime, never an unrestricted CI log or artifact.
        """
        if not _valid_identity(original) or (original.account, original.region) != (self.account, self.region):
            raise AdmissionError("invalid original run")
        try:
            self._versioning()
            current = self._read()
            if current is None or current[0]["original"] != asdict(original):
                raise AdmissionError("original run mismatch")
            return current
        except AdmissionError:
            raise
        except Exception:
            raise AdmissionError("admission inspection failed") from None

    @staticmethod
    def _fence(current, expected):
        if (not isinstance(expected, tuple) or len(expected) != 2
                or current[0]["request_id"] != expected[0] or current[2] != expected[1]):
            raise AdmissionError("stale admission generation")

    def mark_cleaned(self, original, recovery_job, expected, *, native_stopped, ownership_verified):
        """Finish an original run only after independently checked evidence.

        ``recovery_job`` identifies the *current* authenticated actor; it must
        not replace the original run's project/job/SHA. Boolean evidence is a
        caller precondition, not itself proof. This draft is not a recovery job.
        """
        if (not _valid_identity(original) or not _valid_identity(recovery_job)
                or (original.account, original.region) != (self.account, self.region)
                or (recovery_job.account, recovery_job.region) != (self.account, self.region)
                or original.project_id != recovery_job.project_id
                or original.job_id == recovery_job.job_id
                or native_stopped is not True or ownership_verified is not True):
            raise AdmissionError("recovery evidence incomplete")
        if not EVIDENCE_VERIFICATION_READY:
            raise AdmissionError("independent ownership evidence is not connected")
        try:
            self._versioning()
            current = self._read()
            if current is None or current[0]["state"] not in ("ACTIVE", "UNKNOWN"):
                raise AdmissionError("no unresolved original run")
            self._fence(current, expected)
            record, etag, _ = current
            if record["original"] != asdict(original):
                raise AdmissionError("original run mismatch")
            result = dict(record)
            result.update(state="CLEANED", request_id=uuid.uuid4().hex, recovery_job=asdict(recovery_job),
                          supersedes_version=current[2])
            return self._write(result, {"IfMatch": etag})
        except AdmissionError:
            raise
        except Exception:
            raise AdmissionError("recovery check failed") from None

    def complete_cleaned(self, original, current_job, expected, *, native_stopped, ownership_verified):
        """Complete a normal run using its own separately authenticated job."""
        if (not _valid_identity(original) or current_job != original
                or (original.account, original.region) != (self.account, self.region)
                or native_stopped is not True or ownership_verified is not True):
            raise AdmissionError("completion evidence incomplete")
        if not EVIDENCE_VERIFICATION_READY:
            raise AdmissionError("independent ownership evidence is not connected")
        try:
            self._versioning()
            current = self._read()
            if current is None or current[0]["state"] != "ACTIVE" or current[0]["original"] != asdict(original):
                raise AdmissionError("original run mismatch")
            self._fence(current, expected)
            record = dict(current[0])
            record.update(state="CLEANED", request_id=uuid.uuid4().hex, completion_job=asdict(current_job),
                          supersedes_version=current[2])
            return self._write(record, {"IfMatch": current[1]})
        except AdmissionError:
            raise
        except Exception:
            raise AdmissionError("completion check failed") from None

    def record_profile_intent(self, original, certificate_arns, snapshot, expected):
        """Record known certs and a complete pre-native identifier snapshot.

        Snapshot acquisition and managed-job serialization are caller
        prerequisites; this write alone cannot prove profile creation later.
        """
        if not _valid_identity(original) or (original.account, original.region) != (self.account, self.region):
            raise AdmissionError("invalid original run")
        self._validate_profile_intent(certificate_arns, snapshot)
        try:
            self._versioning()
            current = self._read()
            if (current is None or current[0]["state"] != "ACTIVE"
                    or current[0]["original"] != asdict(original) or "profile_intent" in current[0]):
                raise AdmissionError("original run or intent mismatch")
            self._fence(current, expected)
            record = dict(current[0])
            record.update(request_id=uuid.uuid4().hex,
                          supersedes_version=current[2],
                          profile_intent={"certificates": sorted(certificate_arns),
                                          "before": sorted(snapshot, key=lambda item: item["profileName"])})
            return self._write(record, {"IfMatch": current[1]})
        except AdmissionError:
            raise
        except Exception:
            raise AdmissionError("profile intent check failed") from None

    def _validate_profile_intent(self, certificate_arns, snapshot):
        cert_pattern = rf"arn:aws:acm:{re.escape(self.region)}:{self.account}:certificate/[0-9a-fA-F-]{{36}}"
        if (not isinstance(certificate_arns, list) or not certificate_arns
                or any(not isinstance(arn, str) or not re.fullmatch(cert_pattern, arn) for arn in certificate_arns)
                or len(set(certificate_arns)) != len(certificate_arns) or not isinstance(snapshot, list)):
            raise AdmissionError("invalid profile intent")
        seen = set()
        for profile in snapshot:
            fields = {"profileName", "arn", "profileVersion", "profileVersionArn", "status"}
            if not isinstance(profile, dict) or set(profile) != fields:
                raise AdmissionError("invalid profile snapshot")
            name, version = profile["profileName"], profile["profileVersion"]
            if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]{2,64}", name)
                    or not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9]{10}", version)
                    or not isinstance(profile["status"], str)
                    or profile["status"] not in {"Active", "Canceled", "Revoked"} or name in seen):
                raise AdmissionError("invalid profile snapshot")
            arn = f"arn:aws:signer:{self.region}:{self.account}:/signing-profiles/{name}"
            if profile["arn"] != arn or profile["profileVersionArn"] != arn + "/" + version:
                raise AdmissionError("profile snapshot scope mismatch")
            seen.add(name)

    def mark_unknown(self, original, reason, expected):
        """Record uncertainty without reopening admission or retrying a write."""
        if (not _valid_identity(original) or (original.account, original.region) != (self.account, self.region)
                or reason not in ("host_loss", "ownership", "response", "external_change")):
            raise AdmissionError("invalid unknown outcome")
        try:
            self._versioning()
            current = self._read()
            if current is None or current[0]["state"] != "ACTIVE" or current[0]["original"] != asdict(original):
                raise AdmissionError("original run mismatch")
            self._fence(current, expected)
            record = dict(current[0])
            record.update(state="UNKNOWN", request_id=uuid.uuid4().hex, reason=reason,
                          supersedes_version=current[2])
            return self._write(record, {"IfMatch": current[1]})
        except AdmissionError:
            raise
        except Exception:
            raise AdmissionError("unknown state check failed") from None

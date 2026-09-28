#!/usr/bin/env python3
"""Own temporary ACM certificates for native IDT AWS Signer execution.

Call prepare before IDT, and cleanup in a finally block only after IDT and its
native cleanup have stopped. This module never logs certificate/key contents.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

try:
    from .ota_support import SIGNING_KEY, TRUSTED_CERT, UNTRUSTED_CERT, UNTRUSTED_KEY, load_signer
except ImportError:
    from ota_support import SIGNING_KEY, TRUSTED_CERT, UNTRUSTED_CERT, UNTRUSTED_KEY, load_signer

JOURNAL = "ota-aws-signers.json"
PURPOSE = "rx72n-idt-ota"


def _code(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code", type(error).__name__)


def _persist(path, journal, *, initial=False):
    temporary = path if initial else path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(journal, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not initial:
        # Windows scanners/readers can briefly deny replacement of a recently
        # written file. Retry only this local rename, never the AWS import.
        # Permanent ACL errors remain failures; total backoff is at most 0.75s.
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as error:
                if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 4:
                    raise
                time.sleep(0.05 * (2 ** attempt))


def _clients(region, session):
    if session is None:
        import boto3
        session = boto3.Session(region_name=region)
    from botocore.config import Config
    config = Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 2})
    return (session.client("acm", region_name=region, config=config),
            session.client("signer", region_name=region, config=config))


def _valid_arn(arn, region):
    return bool(re.fullmatch(r"arn:aws(?:-cn|-us-gov)?:acm:" + re.escape(region) +
                            r":[0-9]{12}:certificate/[0-9a-fA-F-]{36}", arn))


def prepare_aws_signers(inputs, region, run_id, ota_config, session=None):
    """Import new tagged ACM certificates; return the native AWS OTA config.

    No existing ARN is passed to ImportCertificate. A partial failure leaves a
    journal for cleanup_aws_signers; caller's finally must invoke it even when
    this function raises. Runtime folder permissions remain caller-owned.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
        raise ValueError("invalid OTA signer run ID")
    inputs = Path(inputs).resolve(strict=True)
    journal_path = inputs / JOURNAL
    pairs = (("trusted", TRUSTED_CERT, SIGNING_KEY), ("untrusted", UNTRUSTED_CERT, UNTRUSTED_KEY))
    for _, cert, key in pairs:
        load_signer(inputs / key, inputs / cert)
    journal = {"schema_version": 1, "run_id": run_id, "region": region,
               "purpose": PURPOSE, "state": "preparing", "certificates": [],
               "canceled_profiles": [], "errors": []}
    _persist(journal_path, journal, initial=True)
    acm, _ = _clients(region, session)
    try:
        for role, certificate_name, key_name in pairs:
            journal["pending_import"] = role
            _persist(journal_path, journal)
            certificate = (inputs / certificate_name).read_bytes()
            response = acm.import_certificate(
                Certificate=certificate, PrivateKey=(inputs / key_name).read_bytes(),
                Tags=[{"Key": "codex:purpose", "Value": PURPOSE},
                      {"Key": "codex:run-id", "Value": run_id}])
            arn = response["CertificateArn"]
            if not _valid_arn(arn, region):
                raise RuntimeError("ACM returned an unexpected certificate ARN")
            journal["certificates"].append({"role": role, "arn": arn,
                                             "certificate_sha256": hashlib.sha256(certificate).hexdigest(),
                                             "deleted": False})
            journal.pop("pending_import", None)
            _persist(journal_path, journal)  # Persist ownership before any next AWS request.
        journal["state"] = "ready"
        _persist(journal_path, journal)
        arns = {item["role"]: item["arn"] for item in journal["certificates"]}
        result = deepcopy(ota_config)
        signing = result["codeSigningConfiguration"]
        signing.update(signingMethod="AWS", signerPlatform="AmazonFreeRTOS-Default",
                       signerCertificate=arns["trusted"], untrustedSignerCertificate=arns["untrusted"])
        signing.pop("signCommand", None)
        return result
    except Exception as error:
        journal["state"] = "prepare_failed"
        journal["errors"].append({"operation": "import", "code": _code(error)})
        _persist(journal_path, journal)
        raise RuntimeError("OTA ACM signer preparation failed: " + _code(error)) from None


def _assert_owned(acm, certificate, journal):
    arn = certificate["arn"]
    if not _valid_arn(arn, journal["region"]):
        raise RuntimeError("invalid owned ACM ARN in journal")
    response = acm.list_tags_for_certificate(CertificateArn=arn)
    tags = {item["Key"]: item["Value"] for item in response.get("Tags", [])}
    if tags.get("codex:purpose") != PURPOSE or tags.get("codex:run-id") != journal["run_id"]:
        raise RuntimeError("ACM ownership tags do not match this run")


def _cancel_owned_profiles(signer, arn, journal, deadline):
    token = None
    while True:
        if time.monotonic() >= deadline:
            raise RuntimeError("signing profile scan timed out")
        request = {"maxResults": 25}
        if token:
            request["nextToken"] = token
        page = signer.list_signing_profiles(**request)
        for profile in page.get("profiles", []):
            if profile.get("signingMaterial", {}).get("certificateArn") != arn:
                continue
            if profile.get("status") != "Active":
                continue
            name = profile["profileName"]
            # Re-read the exact material before canceling; never cancel by name prefix.
            current = signer.get_signing_profile(profileName=name)
            if current.get("signingMaterial", {}).get("certificateArn") != arn:
                raise RuntimeError("signing profile material changed during cleanup")
            if current.get("status") == "Active":
                signer.cancel_signing_profile(profileName=name)
                journal["canceled_profiles"].append(name)
        token = page.get("nextToken")
        if not token:
            return


def cleanup_aws_signers(inputs, session=None, timeout_seconds=60):
    """Delete only run-owned ACM certificates, after native IDT cleanup.

    Returns a credential-free journal on success. Uncertain ownership, in-use
    dependencies, timeouts, and access errors are recorded and fail closed.
    """
    path = Path(inputs).resolve(strict=True) / JOURNAL
    if not path.exists():
        return {"state": "not_created", "certificates": [], "errors": []}
    journal = json.loads(path.read_text(encoding="utf-8"))
    if journal.get("schema_version") != 1 or journal.get("purpose") != PURPOSE:
        raise RuntimeError("unrecognized OTA signer ownership journal")
    if timeout_seconds <= 0:
        raise ValueError("cleanup timeout must be positive")
    acm, signer = _clients(journal["region"], session)
    deadline = time.monotonic() + timeout_seconds
    errors = []
    for certificate in journal["certificates"]:
        if certificate.get("deleted"):
            continue
        arn = certificate["arn"]
        try:
            _assert_owned(acm, certificate, journal)
            canceled = False
            while True:
                if time.monotonic() >= deadline:
                    raise RuntimeError("ACM deletion confirmation timed out")
                try:
                    acm.delete_certificate(CertificateArn=arn)
                except Exception as error:
                    if _code(error) == "ResourceNotFoundException":
                        certificate["deleted"] = True
                        break
                    if _code(error) != "ResourceInUseException":
                        raise
                    if not canceled:
                        _cancel_owned_profiles(signer, arn, journal, deadline)
                        canceled = True
                        _persist(path, journal)
                try:
                    acm.describe_certificate(CertificateArn=arn)
                except Exception as error:
                    if _code(error) == "ResourceNotFoundException":
                        certificate["deleted"] = True
                        break
                    raise
                time.sleep(min(2, max(0, deadline - time.monotonic())))
        except Exception as error:
            if _code(error) == "ResourceNotFoundException":
                certificate["deleted"] = True
            else:
                errors.append({"operation": "cleanup", "arn": arn, "code": _code(error)})
        _persist(path, journal)
    if journal.get("pending_import"):
        errors.append({"operation": "import_recovery", "code": "UncertainImportOutcome",
                       "detail": "Inspect ACM run tags before considering cleanup complete."})
    journal["errors"].extend(errors)
    journal["state"] = "cleanup_failed" if errors else "cleaned"
    _persist(path, journal)
    if errors:
        raise RuntimeError("OTA signer cleanup incomplete; inspect the ownership journal")
    return journal

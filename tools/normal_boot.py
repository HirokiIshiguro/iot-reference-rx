"""Offline binding for normal signed applications and public boot trust.

This is a normal-application bundle, independent of native IDT input manifests.
It contains public signer material and firmware, never a signing private key.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

try:
    from .idt import public_signer_provision as trust
    from .idt import public_signer_material as material
    from .idt.targets import get_target, target_fingerprint
except ImportError:
    from idt import public_signer_provision as trust
    from idt import public_signer_material as material
    from idt.targets import get_target, target_fingerprint

PROFILE = "rx-normal-signed-install-v1"
FILES = frozenset(("normal_app.rsu", "bootloader.mot", "bootloader_bank1.mot",
    "public_signer_provisioner.mot", "public_signer_provisioner_manifest.json",
    "signer.crt.pem", "signer.pub.pem", "public_signer_bootloader_config.h", "public_signer_target.h"))

BENCHMARK_PROVENANCE_FIELDS = frozenset(("schema_version", "project_id", "pipeline_id", "job_id",
    "source_sha", "application_source_sha", "profile", "role", "application_sha256"))


def validate_benchmark_provenance(value, manifest):
    """Validate public build claims; CI source binding remains the caller's responsibility.

    The signed application hash binds these claims to this bundle. It does not
    prove which repository built the image; readers must also verify the exact
    producer job/source/profile against their immutable CI snapshot.
    """
    if type(value) is not dict or set(value) != BENCHMARK_PROVENANCE_FIELDS:
        raise RuntimeError("Unexpected benchmark provenance fields")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise RuntimeError("Unsupported benchmark provenance schema")
    if any(type(value[key]) is not int or value[key] <= 0
           for key in ("project_id", "pipeline_id", "job_id")):
        raise RuntimeError("Benchmark provenance requires positive CI identifiers")
    for key in ("source_sha", "application_source_sha"):
        if type(value[key]) is not str or not re.fullmatch(r"[0-9a-f]{40}", value[key]):
            raise RuntimeError("Benchmark provenance requires full source commits")
    if (type(value["profile"]) is not str or
            not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value["profile"]) or
            value["role"] not in ("benchmark", "normal-restore")):
        raise RuntimeError("Unsupported benchmark provenance profile or role")
    application_source = (value["source_sha"] if value["role"] == "benchmark"
                          else manifest["source_sha"])
    if value["application_source_sha"] != application_source:
        raise RuntimeError("Benchmark provenance application source/role mismatch")
    digest = value["application_sha256"]
    if (type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest) or
            digest != manifest["files"]["normal_app.rsu"]):
        raise RuntimeError("Benchmark provenance application hash mismatch")
    return dict(value)


def file_hash(path):
    return hashlib.sha256(trust._bytes(path)).hexdigest()


def signed_application(files, target):
    """Check actual CF-only bytes and signature; sequence is a normal-bundle field."""
    start, _ = trust.LAYOUTS[target["id"]]
    image = trust._bytes(files["normal_app.rsu"])
    if len(image) != 0xFFFC0000 - start:
        raise RuntimeError("Normal RSU size differs from the dual-bank Code Flash layout")
    if (image[:8] != b"Renesas\xfe" or image[8:40] != b"sig-sha256-ecdsa" + b"\0" * 16 or
            struct.unpack_from("<I", image, 0x28)[0] != 64 or
            struct.unpack_from("<III", image, 0x12C) != (0, 0xFFFFFFFF, 0xFFFFFFFF)):
        raise RuntimeError("Normal RSU signature or Code Flash-only policy mismatch")
    sequence = struct.unpack_from("<I", image, 0x200)[0]
    if not 1 <= sequence <= 0xFFFFFFFF:
        raise RuntimeError("Normal RSU sequence must be positive")
    try:
        trust._tools_module("build_rx671_fwup_v2_rsu").validate_legacy_descriptor(
            image[0x200:0x300], start + 0x300, 0xFFFBFFFF)
    except ValueError as error:
        raise RuntimeError("Normal RSU dual-bank descriptor mismatch") from error
    vector = int.from_bytes(image[0xFFFBFFFC-start:0xFFFC0000-start], "little")
    if not start + 0x300 <= vector <= 0xFFFBFFFF:
        raise RuntimeError("Normal RSU reset vector is outside its application")
    public = material.public_signer(files["signer.crt.pem"], files["signer.pub.pem"])
    material.verify_raw_p256(public, image[0x2C:0x6C], image[0x200:])
    return {"sequence": sequence, "reset_vector": f"0x{vector:08X}", "code_flash_only": True}


def validate(root, target, source_sha, *, expected_benchmark_provenance=None):
    root = Path(root)
    files = {name: root/name for name in FILES}
    manifest = json.loads(trust._bytes(root/"normal_install_manifest.json"))
    if (manifest.get("schema_version") != 1 or manifest.get("profile") != PROFILE or
            manifest.get("source_sha") != source_sha or manifest.get("target_id") != target["id"] or
            manifest.get("target_sha256") != target_fingerprint(target) or
            manifest.get("tls_backend") not in ("software", "tsip")):
        raise RuntimeError("Normal install source/target/backend/profile mismatch")
    if "benchmark_provenance" in manifest:
        actual_provenance = validate_benchmark_provenance(manifest["benchmark_provenance"], manifest)
        if (expected_benchmark_provenance is not None and
                actual_provenance != validate_benchmark_provenance(expected_benchmark_provenance, manifest)):
            raise RuntimeError("Normal install benchmark provenance differs from the expected producer")
    elif expected_benchmark_provenance is not None:
        raise RuntimeError("Normal install benchmark provenance is missing")
    # Parse public-only boundaries before hashing can read an unexpected PEM body.
    plan = trust.validate_boot_trust(files, target, source_sha)
    app = signed_application(files, target)
    if manifest.get("files") != {name: file_hash(path) for name, path in files.items()}:
        raise RuntimeError("Normal install input hash mismatch")
    if (manifest.get("application") != app or
            manifest.get("bootloader_policy_sha256") != trust.policy_hashes(files, target) or
            manifest.get("public_signer_spki_sha256") != plan["public_signer_spki_sha256"]):
        raise RuntimeError("Normal install claims differ from actual public firmware inputs")
    return manifest


def prepare(source, target_id, output, inputs, *, tls_backend="software", benchmark_provenance=None):
    try:
        from .idt.prepare_public_signer import _source_state, _unlinked
    except ImportError:
        from idt.prepare_public_signer import _source_state, _unlinked
    source = _unlinked(source).resolve(strict=True)
    source_sha = _source_state(source)
    target = get_target(target_id)
    if tls_backend not in ("software", "tsip"):
        raise RuntimeError("Unsupported normal application backend")
    output = _unlinked(output).resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Normal install output already exists; it will not be overwritten")
    if output.is_relative_to(source):
        raise RuntimeError("Normal install output must remain outside the source checkout")
    boot = source/target["bootloader_project"]
    inputs = {**inputs, "public_signer_bootloader_config.h": boot/"src/rx_bootloader_config.h",
              "public_signer_target.h": trust.chip_config(source, target)}
    if set(inputs) != FILES:
        raise RuntimeError("Unexpected normal install input set")
    # All validation happens before publishing a usable bundle.
    plan = trust.validate_boot_trust(inputs, target, source_sha)
    app = signed_application(inputs, target)
    manifest = {"schema_version": 1, "profile": PROFILE, "source_sha": source_sha,
                "target_id": target_id, "target_sha256": target_fingerprint(target),
                "tls_backend": tls_backend, "application": app,
                "public_signer_spki_sha256": plan["public_signer_spki_sha256"],
                "bootloader_policy_sha256": trust.policy_hashes(inputs, target),
                "files": {name: file_hash(path) for name, path in inputs.items()}}
    if benchmark_provenance is not None:
        manifest["benchmark_provenance"] = validate_benchmark_provenance(benchmark_provenance, manifest)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    manifest_path = output/"normal_install_manifest.json"
    try:
        for name, path in inputs.items():
            shutil.copyfile(trust._ordinary(path), output/name)
        if _source_state(source) != source_sha:
            raise RuntimeError("Normal install source changed during preparation")
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2)+"\n", encoding="utf-8")
        if benchmark_provenance is None:
            validate(output, target, source_sha)
        else:
            validate(output, target, source_sha,
                     expected_benchmark_provenance=manifest["benchmark_provenance"])
        if _source_state(source) != source_sha:
            raise RuntimeError("Normal install source changed during preparation")
    except BaseException:
        manifest_path.unlink(missing_ok=True)
        raise
    return manifest

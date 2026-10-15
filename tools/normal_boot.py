"""Offline binding for normal signed applications and public boot trust.

This is a normal-application bundle, independent of native IDT input manifests.
It contains public signer material and firmware, never a signing private key.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
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
    if target["id"] == "rx671-wifi":
        if image[0x200:0x300] != trust._tools_module("build_rx671_fwup_v2_rsu").build_descriptor():
            raise RuntimeError("Normal RX671 RSU descriptor mismatch")
    elif struct.unpack_from("<IIII", image, 0x204) != (start + 0x300, 0xFFFBFFFF, 0xFFFBFFFC, 9):
        raise RuntimeError("Normal RSU dual-bank descriptor mismatch")
    vector = int.from_bytes(image[0xFFFBFFFC-start:0xFFFC0000-start], "little")
    if not start + 0x300 <= vector <= 0xFFFBFFFF:
        raise RuntimeError("Normal RSU reset vector is outside its application")
    public = material.public_signer(files["signer.crt.pem"], files["signer.pub.pem"])
    material.verify_raw_p256(public, image[0x2C:0x6C], image[0x200:])
    return {"sequence": sequence, "reset_vector": f"0x{vector:08X}", "code_flash_only": True}


def validate(root, target, source_sha):
    root = Path(root)
    files = {name: root/name for name in FILES}
    manifest = json.loads(trust._bytes(root/"normal_install_manifest.json"))
    if (manifest.get("schema_version") != 1 or manifest.get("profile") != PROFILE or
            manifest.get("source_sha") != source_sha or manifest.get("target_id") != target["id"] or
            manifest.get("target_sha256") != target_fingerprint(target) or
            manifest.get("tls_backend") not in ("software", "tsip") or
            (target["id"] == "rx671-wifi" and manifest.get("tls_backend") != "software")):
        raise RuntimeError("Normal install source/target/backend/profile mismatch")
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


def prepare(source, target_id, output, inputs, *, tls_backend="software"):
    try:
        from .idt.prepare_public_signer import _source_state, _unlinked
    except ImportError:
        from idt.prepare_public_signer import _source_state, _unlinked
    source = _unlinked(source).resolve(strict=True)
    source_sha = _source_state(source)
    target = get_target(target_id)
    if tls_backend not in ("software", "tsip") or (target_id == "rx671-wifi" and tls_backend != "software"):
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
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    manifest_path = output/"normal_install_manifest.json"
    try:
        for name, path in inputs.items():
            shutil.copyfile(trust._ordinary(path), output/name)
        if _source_state(source) != source_sha:
            raise RuntimeError("Normal install source changed during preparation")
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2)+"\n", encoding="utf-8")
        validate(output, target, source_sha)
        if _source_state(source) != source_sha:
            raise RuntimeError("Normal install source changed during preparation")
    except BaseException:
        manifest_path.unlink(missing_ok=True)
        raise
    return manifest

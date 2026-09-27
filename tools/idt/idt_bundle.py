"""Verify IDT's immutable executables and test definitions against official ZIPs.

The manifest was derived from fresh signed-API downloads of IDT 4.9.0 /
FRQ_2.5.0. Mutable configuration, logs, results and certificates are excluded.
No cache is repaired or replaced here, including when an IDT process is active.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath


MANIFEST = Path(__file__).with_name("bundle-manifest.json")
STATIC_TREES = ("bin", "tests/FRQ_2.5.0")


def _read_manifest() -> dict:
    with MANIFEST.open(encoding="utf-8") as source:
        manifest = json.load(source)
    if (manifest.get("schema_version") != 1 or manifest.get("idt_version") != "4.9.0"
            or manifest.get("suite") != "FRQ_2.5.0"):
        raise RuntimeError("IDT bundle manifest does not match the supported version")
    return manifest


def _host(manifest: dict, host_os: str) -> dict:
    if host_os not in {"windows", "linux"}:
        raise ValueError("IDT bundle host_os must be windows or linux")
    return manifest["hosts"][host_os]


def verify_archive_digest(host_os: str, sha256: str) -> None:
    """Reject an unpinned ZIP before extracting it into an IDT installation."""
    expected = _host(_read_manifest(), host_os)["archive_sha256"]
    if not isinstance(sha256, str) or sha256.lower() != expected:
        raise RuntimeError("IDT archive SHA-256 does not match the pinned official bundle")


def verify_install(root: Path, host_os: str) -> None:
    """Reject missing, modified or extra files in the immutable IDT trees."""
    manifest = _read_manifest()
    host = _host(manifest, host_os)
    expected = {**manifest["common_files"], **host["files"]}
    root = Path(root).resolve()
    if not root.is_dir():
        raise RuntimeError("IDT installation directory is missing")
    actual = {
        path.relative_to(root).as_posix()
        for tree in STATIC_TREES
        for path in (root / tree).rglob("*")
        if path.is_file()
    }
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        raise RuntimeError(
            "IDT immutable file inventory differs from the official bundle"
            + f" (missing={len(missing)}, extra={len(extra)})"
        )
    for relative, expected_digest in expected.items():
        parts = PurePosixPath(relative)
        if parts.is_absolute() or ".." in parts.parts:
            raise RuntimeError("IDT bundle manifest contains an unsafe path")
        path = root / relative
        if root not in path.resolve().parents:
            raise RuntimeError("IDT static file resolves outside its installation")
        try:
            with path.open("rb") as stream:
                # The lightweight Linux CI runner predates Python 3.11's
                # hashlib.file_digest. Keep streaming without that newer API.
                digest_state = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest_state.update(chunk)
                digest = digest_state.hexdigest()
        except OSError:
            raise RuntimeError("IDT static file is unreadable: " + relative) from None
        if digest != expected_digest:
            raise RuntimeError("IDT static file SHA-256 mismatch: " + relative)

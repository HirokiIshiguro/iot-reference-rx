"""Host-only encrypted transport for the RX671 Fleet normal signed bundle.

Only public identity and output paths reach stdout. Firmware may contain claim
credentials: plaintext is kept in new private local directories, never artifacts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import normal_boot
from tools.ci import protect_secret_artifact as protection
from tools.idt.targets import get_target

PROFILE = "rx671-fleet-normal-bundle-v1"
FILES = normal_boot.FILES | {"normal_install_manifest.json"}
ARTIFACT_FILES = frozenset(("bundle.zip.enc", "manifest.json"))
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_CIPHER = MAX_TOTAL + 1024 * 1024


def _path(value):
    path = Path(value)
    if ".." in path.parts:
        raise ValueError("Parent traversal is not accepted")
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            metadata = item.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(metadata.st_mode) or
                getattr(metadata, "st_file_attributes", 0) & 0x400):
            raise ValueError("Linked paths are not accepted")
    return path


def _file(path, maximum):
    path = _path(path)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError("Only ordinary unlinked files are accepted")
    if metadata.st_size > maximum:
        raise ValueError("Input exceeds its size limit")
    return path


def _identity(target, source_sha, pipeline_id):
    if target != "rx671-wifi" or not isinstance(source_sha, str) or not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise ValueError("Expected rx671-wifi and an exact lowercase source SHA")
    if type(pipeline_id) is not int or pipeline_id <= 0:
        raise ValueError("Pipeline ID must be a positive integer")
    return {"schema_version": 1, "profile": PROFILE, "target_id": target,
            "source_sha": source_sha, "pipeline_id": pipeline_id,
            "context": f"{PROFILE}:{pipeline_id}:{source_sha}"}


def _paths(source, output, expected):
    source, output = _path(source), _path(output)
    if not source.is_dir() or {item.name for item in source.iterdir()} != expected:
        raise ValueError("Unexpected input directory member set")
    if output.exists():
        raise FileExistsError("Output already exists; it will not be overwritten")
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Input and output directories must be disjoint")
    if not output.parent.is_dir():
        raise ValueError("Output parent must already exist")
    return source, output


def _remove_owned(root, names):
    # No recursive deletion, and no deletion of input, siblings or unknown files.
    if _path(root) != root:
        raise RuntimeError("Owned directory path changed")
    for name in names:
        path = root / name
        if path.is_file() or path.is_symlink():
            path.unlink()
    root.rmdir()


@contextmanager
def _output(root, names):
    root.mkdir(mode=0o700, exist_ok=False)
    try:
        os.chmod(root, 0o700)
        yield root
    except BaseException:
        _remove_owned(root, names)
        raise


@contextmanager
def _workspace(parent):
    root = _path(tempfile.mkdtemp(prefix=".protected-normal-", dir=parent))
    stage = root / "bundle"
    try:
        os.chmod(root, 0o700)
        stage.mkdir(mode=0o700)
        yield root, stage
    finally:
        if stage.exists():
            _remove_owned(stage, FILES)
        _remove_owned(root, {"bundle.zip"})


def _write_private(path, payload):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    os.chmod(path, 0o600)


def _copy_bundle(source, stage):
    total = 0
    for name in sorted(FILES):
        with _file(source / name, MAX_FILE).open("rb") as stream:
            payload = stream.read(MAX_FILE + 1)
        total += len(payload)
        if len(payload) > MAX_FILE or total > MAX_TOTAL:
            raise ValueError("Bundle exceeds its size limit")
        _write_private(stage / name, payload)


def pack(bundle, output, target, source_sha, pipeline_id, secret_env):
    identity = _identity(target, source_sha, pipeline_id)
    bundle, output = _paths(bundle, output, FILES)
    if sum(_file(bundle / name, MAX_FILE).stat().st_size for name in FILES) > MAX_TOTAL:
        raise ValueError("Bundle exceeds its size limit")
    # Preserve normal_boot's public-PEM boundary checks before any bulk copying.
    normal_boot.validate(bundle, get_target(target), source_sha)
    with _workspace(bundle.parent) as (private, stage):
        _copy_bundle(bundle, stage)
        # Validate the exact snapshot to encrypt, retaining all existing normal
        # manifest, signer, PEM boundary and signature checks.
        normal_boot.validate(stage, get_target(target), source_sha)
        plaintext = private / "bundle.zip"
        with plaintext.open("xb") as stream:
            os.chmod(plaintext, 0o600)
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
                for name in sorted(FILES):
                    archive.write(stage / name, name)
        secret = protection._secret_from_environment(secret_env)
        try:
            with _output(output, ARTIFACT_FILES):
                digest = protection.encrypt(plaintext, output / "bundle.zip.enc", secret, identity["context"])
                manifest = {**identity, "ciphertext_sha256": digest}
                _write_private(output / "manifest.json", (json.dumps(manifest, sort_keys=True) + "\n").encode())
        finally:
            secret = b""
    return {**identity, "artifact": str(output), "ciphertext": str(output / "bundle.zip.enc"),
            "manifest": str(output / "manifest.json")}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest key")
        result[key] = value
    return result


def _manifest(artifact, identity):
    manifest = json.loads(_file(artifact / "manifest.json", 64 * 1024).read_bytes(), object_pairs_hook=_unique_object)
    fields = set(identity) | {"ciphertext_sha256"}
    if (not isinstance(manifest, dict) or set(manifest) != fields or
            type(manifest.get("schema_version")) is not int or
            type(manifest.get("pipeline_id")) is not int or
            any(manifest.get(key) != value for key, value in identity.items()) or
            not isinstance(manifest.get("ciphertext_sha256"), str) or
            not re.fullmatch(r"[a-f0-9]{64}", manifest["ciphertext_sha256"])):
        raise ValueError("Encrypted bundle identity/profile/context mismatch")
    ciphertext = _file(artifact / "bundle.zip.enc", MAX_CIPHER)
    if hashlib.sha256(ciphertext.read_bytes()).hexdigest() != manifest["ciphertext_sha256"]:
        raise ValueError("Encrypted bundle ciphertext hash mismatch")
    return ciphertext


def _members(archive):
    members = archive.infolist()
    if len(members) != len(FILES) or {item.filename for item in members} != FILES:
        raise ValueError("ZIP must contain exactly the ten flat expected files")
    total = 0
    for item in members:
        kind = stat.S_IFMT(item.external_attr >> 16)
        if (item.orig_filename != item.filename or item.is_dir() or
                kind not in (0, stat.S_IFREG) or item.flag_bits & 1 or
                item.file_size > MAX_FILE or item.file_size < 0):
            raise ValueError("ZIP members must be bounded regular files")
        total += item.file_size
    if total > MAX_TOTAL:
        raise ValueError("ZIP exceeds total size limit")
    return members


def unpack(artifact, output, target, source_sha, pipeline_id, secret_env):
    identity = _identity(target, source_sha, pipeline_id)
    artifact, output = _paths(artifact, output, ARTIFACT_FILES)
    ciphertext = _manifest(artifact, identity)
    with _workspace(output.parent) as (private, _stage):
        plaintext = private / "bundle.zip"
        secret = protection._secret_from_environment(secret_env)
        try:
            protection.decrypt(ciphertext, plaintext, secret, identity["context"])
        finally:
            secret = b""
        with zipfile.ZipFile(plaintext) as archive:
            members = _members(archive)  # Reject all names/types before extraction.
            with _output(output, FILES):
                for item in members:
                    with archive.open(item) as stream:
                        payload = stream.read(MAX_FILE + 1)
                    if len(payload) != item.file_size or len(payload) > MAX_FILE:
                        raise ValueError("ZIP member size mismatch")
                    _write_private(output / item.filename, payload)
                normal_boot.validate(output, get_target(target), source_sha)
    return {**identity, "bundle": str(output), "normal_manifest": str(output / "normal_install_manifest.json")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for operation in ("pack", "unpack"):
        command = commands.add_parser(operation)
        command.add_argument("--bundle" if operation == "pack" else "--artifact", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path)
        command.add_argument("--target", required=True, choices=("rx671-wifi",))
        command.add_argument("--source-sha", required=True)
        command.add_argument("--pipeline-id", required=True, type=int)
        command.add_argument("--secret-env", required=True)
    arguments = vars(parser.parse_args(argv))
    operation = arguments.pop("operation")
    try:
        result = (pack if operation == "pack" else unpack)(**arguments)
    except Exception:
        # Validation libraries may include payload fragments in exceptions.
        # Keep all firmware/credential material out of the command's output.
        print("Protected normal bundle operation failed", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

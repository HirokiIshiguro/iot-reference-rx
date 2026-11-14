"""Private RX72N Transport build messages for the RPi4/Windows pilot.

The caller supplies private, already authenticated streams. Payloads are never
logged. This module does not grant access, start AWS, or run any hardware.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

TARGET = "rx72n-ethernet"
OVERLAYS = ("Test/include/test_execution_config.h", "Test/include/test_param_config.h")
OUTPUTS = ("rx72n_idt_transport.mot", "bootloader.mot", "build_manifest.json")
MAX_FRAME_BYTES = 64 * 1024 * 1024
MAX_HEADER_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_frame(stream):
    def exact(count):
        chunks = []
        while count:
            part = stream.read(count)
            if not part:
                raise EOFError("private build stream closed")
            chunks.append(part)
            count -= len(part)
        return b"".join(chunks)

    size = struct.unpack("!I", exact(4))[0]
    if not 0 < size <= MAX_FRAME_BYTES:
        raise ValueError("invalid private build frame length")
    value = json.loads(exact(size))
    if not isinstance(value, dict):
        raise ValueError("private build frame must be an object")
    return value


def write_frame(stream, value):
    body = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if not 0 < len(body) <= MAX_FRAME_BYTES:
        raise ValueError("invalid private build frame length")
    data = memoryview(struct.pack("!I", len(body)) + body)
    while data:
        written = stream.write(data)
        if written is None or written <= 0:
            raise EOFError("private build stream could not be written")
        data = data[written:]
    stream.flush()


def _regular_file(root: Path, relative: str) -> Path:
    path = root.joinpath(*relative.split("/"))
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise ValueError("linked build source is not supported")
        if part == root:
            break
    if not path.is_file():
        raise ValueError("missing regular build source")
    return path


def snapshot(root: Path) -> dict[str, str]:
    """Hash source bytes, excluding Git metadata, without recording contents."""
    root = root.resolve(strict=True)
    files = {}
    for directory, subdirs, names in os.walk(root, followlinks=False):
        subdirs[:] = [name for name in subdirs if name not in (".git", "__pycache__")]
        base = Path(directory)
        for name in subdirs:
            _regular_directory = base / name
            info = _regular_directory.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                raise ValueError("linked build source directory is not supported")
        for name in names:
            if name == ".git" or name.endswith(".pyc"):
                continue
            path = base / name
            relative = path.relative_to(root).as_posix()
            files[relative] = sha256(_regular_file(root, relative).read_bytes())
    return files


def create_request(source: Path, baseline: dict[str, str], provenance: dict, request_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise ValueError("invalid build request identity")
    if not isinstance(provenance, dict) or not re.fullmatch(r"[0-9a-f]{40}", provenance.get("source_sha", "")):
        raise ValueError("invalid source provenance")
    if provenance.get("target_id") != TARGET or provenance.get("source_tree_dirty") is not False:
        raise ValueError("unexpected target or source state")
    current = snapshot(source)
    if set(current) != set(baseline):
        raise ValueError("native source file set changed")
    if any(current[name] != baseline[name] for name in current if name not in OVERLAYS):
        raise ValueError("native changed an unsupported source file")
    entries = {}
    for relative in OVERLAYS:
        data = _regular_file(source.resolve(strict=True), relative).read_bytes()
        if len(data) > MAX_HEADER_BYTES:
            raise ValueError("native test header exceeds build bound")
        entries[relative] = {"sha256": sha256(data), "data": base64.b64encode(data).decode("ascii")}
    augmented_provenance = dict(provenance, paired_source_files_sha256=baseline)
    return {"kind": "build", "request_id": request_id, "target": TARGET,
            "source_sha": provenance["source_sha"], "provenance": augmented_provenance, "files": entries}


def decode_files(entries, allowed, maximum):
    if not isinstance(entries, dict) or set(entries) != set(allowed):
        raise ValueError("unexpected private build files")
    result = {}
    for name in allowed:
        entry = entries[name]
        if not isinstance(entry, dict) or set(entry) != {"sha256", "data"}:
            raise ValueError("invalid private build file metadata")
        try:
            data = base64.b64decode(entry["data"], validate=True)
        except (ValueError, TypeError):
            raise ValueError("invalid private build file encoding") from None
        if len(data) > maximum or entry["sha256"] != sha256(data):
            raise ValueError("private build file integrity mismatch")
        result[name] = data
    return result


def validate_request(request: dict, source_sha: str):
    if set(request) != {"kind", "request_id", "target", "source_sha", "provenance", "files"}:
        raise ValueError("unexpected private build request")
    if (request["kind"] != "build" or request["target"] != TARGET or request["source_sha"] != source_sha
            or not re.fullmatch(r"[0-9a-f]{32}", request["request_id"])):
        raise ValueError("private build request identity mismatch")
    provenance = request["provenance"]
    if (not isinstance(provenance, dict) or provenance.get("source_sha") != source_sha
            or provenance.get("target_id") != TARGET or provenance.get("source_tree_dirty") is not False):
        raise ValueError("private build provenance mismatch")
    baseline = provenance.get("paired_source_files_sha256")
    if (not isinstance(baseline, dict) or not baseline or not set(OVERLAYS) <= set(baseline)
            or any(not isinstance(name, str) or not isinstance(digest, str)
                   or not re.fullmatch(r"[0-9a-f]{64}", digest) for name, digest in baseline.items())):
        raise ValueError("invalid source snapshot")
    return decode_files(request["files"], OVERLAYS, MAX_HEADER_BYTES)


def response(request_id: str, files: dict[str, bytes]):
    if not re.fullmatch(r"[0-9a-f]{32}", request_id) or set(files) != set(OUTPUTS):
        raise ValueError("unexpected build output")
    return {"kind": "result", "request_id": request_id,
            "files": {name: {"sha256": sha256(data), "data": base64.b64encode(data).decode("ascii")}
                      for name, data in files.items()}}


def validate_response(value: dict, request_id: str):
    if set(value) != {"kind", "request_id", "files"} or value["kind"] != "result" or value["request_id"] != request_id:
        raise ValueError("private build response identity mismatch")
    return decode_files(value["files"], OUTPUTS, MAX_OUTPUT_BYTES)

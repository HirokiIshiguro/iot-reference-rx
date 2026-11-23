"""Remove an owned Linux Fleet runtime after the caller establishes safety.

The caller owns hardware safety and restoration. This helper inspects only
filesystem ownership and public identity; it neither touches hardware nor reads
firmware, credentials, logs or lock state.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

RUNTIME_PARENT = Path("/tmp")


def _metadata(path):
    return path.lstat()


def _unlinked(path):
    metadata = _metadata(path)
    if (stat.S_ISLNK(metadata.st_mode) or
            getattr(metadata, "st_file_attributes", 0) & 0x400):
        raise ValueError("Linked runtime paths are not accepted")
    return metadata


def cleanup(runtime, pipeline_id, job_id, source_sha):
    if sys.platform != "linux":
        raise RuntimeError("Fleet runtime cleanup requires Linux")
    if (type(pipeline_id) is not int or pipeline_id <= 0 or
            type(job_id) is not int or job_id <= 0 or
            not isinstance(source_sha, str) or not re.fullmatch(r"[a-f0-9]{40}", source_sha)):
        raise ValueError("Expected positive pipeline/job IDs and an exact lowercase source SHA")
    root = Path(runtime)
    expected = RUNTIME_PARENT / f"rx671-fleet-{pipeline_id}-{job_id}"
    if not root.is_absolute() or ".." in root.parts or root != expected:
        raise ValueError("Runtime must match the exact pipeline/job /tmp path")
    for ancestor in root.parents:
        _unlinked(ancestor)
    result = {"runtime": str(root), "pipeline_id": pipeline_id, "job_id": job_id, "source_sha": source_sha}
    try:
        metadata = _unlinked(root)
    except FileNotFoundError:
        return {**result, "removed": False}
    effective_uid = os.geteuid()
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != effective_uid or
            stat.S_IMODE(metadata.st_mode) != 0o700):
        raise ValueError("Runtime must be an owned private directory with mode 0700")
    # Check every descendant before the deletion operation. Never follow links,
    # and read only the bounded public owner marker after its metadata passes.
    pending = [root]
    while pending:
        directory = pending.pop()
        for entry in directory.iterdir():
            item = _unlinked(entry)
            if item.st_uid != effective_uid:
                raise ValueError("Runtime contains an unexpected owner")
            if stat.S_ISDIR(item.st_mode):
                pending.append(entry)
            elif not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
                raise ValueError("Runtime contains a nonordinary or linked file")
    marker = root / ".owner"
    owner = _unlinked(marker)
    if not stat.S_ISREG(owner.st_mode) or owner.st_uid != effective_uid or owner.st_nlink != 1:
        raise ValueError("Invalid runtime owner marker")
    expected_marker = f"{pipeline_id}:{job_id}:{source_sha}\n".encode("ascii")
    with marker.open("rb") as stream:
        if stream.read(len(expected_marker) + 1) != expected_marker:
            raise ValueError("Runtime owner marker differs from the caller identity")
    # Recheck the absolute deletion boundary and original directory identity
    # immediately before rmtree. No caller-controlled broader path is removed.
    current = _unlinked(root)
    if (root.resolve(strict=True) != expected or root.parent != RUNTIME_PARENT or
            (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino)):
        raise ValueError("Runtime deletion boundary changed")
    shutil.rmtree(root)
    return {**result, "removed": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--pipeline-id", required=True, type=int)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--source-sha", required=True)
    try:
        result = cleanup(**vars(parser.parse_args(argv)))
    except Exception:
        print("Fleet runtime cleanup refused", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

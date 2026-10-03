#!/usr/bin/env python3
"""Capture and verify pinned dependencies copied into a private IDT runtime.

The source-copy provenance records every dependency file hash before IDT
rewrites test headers. Verification is read-only and precedes build preparation.
The reviewed WHD forward/reverse patch check remains a separate build gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

COMMON = (
    "Middleware/3rdparty/mbedtls", "Middleware/3rdparty/littlefs",
    "Middleware/FreeRTOS/FreeRTOS-Kernel", "Middleware/FreeRTOS/FreeRTOS-Plus-TCP",
    "Middleware/FreeRTOS/coreMQTT", "Middleware/FreeRTOS/coreMQTT-Agent",
    "Middleware/FreeRTOS/coreJSON", "Middleware/FreeRTOS/backoffAlgorithm",
    "Middleware/FreeRTOS/corePKCS11",
    "Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk",
    "Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk",
    "Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c",
)
TEST = ("Test/Unity", "Test/FreeRTOS-Libraries-Integration-Tests")
WIFI = (
    "Projects/aws_wifi_rx671_ek/external/wifi-host-driver",
    "Projects/aws_wifi_rx671_ek/external/TraceRecorderSource",
    "Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/firmware-wifi-host-driver",
    "Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/wifi-resources",
    "Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/cyw-fmac-nvram",
)
BOOT = {
    "rx72n-ethernet": "Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/src/rx_bootloader",
    "rx65n-bg96": "Projects/boot_loader_ck_rx65n/e2studio_ccrx/lib/rx_bootloader",
    "rx671-wifi": "Projects/boot_loader_rx671_ek/e2studio_ccrx/lib/rx_bootloader",
}
BOOT_RX671_SHA = "c31bac703e1406e7a94d398b7bcad108b5e8fdce"


def dependency_paths(target_id: str) -> tuple[str, ...]:
    if target_id not in BOOT:
        raise ValueError("Unknown IDT target")
    return TEST + ((BOOT[target_id],) if target_id == "rx65n-bg96" else
                   COMMON + (BOOT[target_id],) + (WIFI if target_id == "rx671-wifi" else ()))


def _is_linked_dependency(path: Path) -> bool:
    # Windows junctions are reparse points but are not symbolic links. Reading
    # lstat attributes works before Path.is_junction was added in Python 3.12.
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False  # The existing missing-dependency check rejects this path.
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _files(root: Path, target_id: str) -> dict[str, Path]:
    files = {}
    for relative in dependency_paths(target_id):
        directory = root / relative
        for ancestor in (directory, *directory.parents):
            if ancestor == root:
                break
            if _is_linked_dependency(ancestor):
                raise ValueError("Linked dependency path is unsupported: " + relative)
        if not directory.is_dir():
            raise ValueError("Missing IDT dependency: " + relative)
        members = {}
        # Do not follow links or junctions out of the selected dependency tree.
        for current, directories, names in os.walk(directory, followlinks=False):
            directories[:] = [name for name in directories if name not in (".git", "__pycache__")]
            for name in directories + [name for name in names if name != ".git"]:
                path = Path(current) / name
                if _is_linked_dependency(path):
                    raise ValueError("Linked dependency path is unsupported: " + path.relative_to(root).as_posix())
                if path.is_file():
                    members[path.relative_to(root).as_posix()] = path
        if not members:
            raise ValueError("Uninitialized IDT dependency: " + relative)
        files.update(members)
    return files


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(["git", "--no-optional-locks", "-c", "safe.directory=" + str(root), "-C", str(root), *arguments], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True).stdout.strip()


def capture_dependency_provenance(source: Path, target_id: str) -> dict:
    """Capture only from initialized Git dependencies matching source gitlinks."""
    source = Path(source).resolve(strict=True)
    if Path(_git(source, "rev-parse", "--show-toplevel")).resolve() != source:
        raise ValueError("Source Git root does not match the requested source tree")
    shas = {}
    for relative in dependency_paths(target_id):
        row = _git(source, "ls-tree", "HEAD", "--", relative).split()
        if len(row) != 4 or row[:2] != ["160000", "commit"] or row[3] != relative:
            raise ValueError("Missing source gitlink: " + relative)
        sha = row[2]
        dependency = source / relative
        if Path(_git(dependency, "rev-parse", "--show-toplevel")).resolve() != dependency.resolve():
            raise ValueError("Uninitialized dependency Git root: " + relative)
        if _git(dependency, "rev-parse", "HEAD") != sha:
            raise ValueError("Dependency does not match source gitlink: " + relative)
        if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", sha):
            raise ValueError("Missing/invalid verified dependency pin: " + relative)
        shas[relative] = sha.lower()
    if target_id == "rx671-wifi" and shas[BOOT[target_id]] != BOOT_RX671_SHA:
        raise ValueError("RX671 boot-loader pin differs from the reviewed production helper")
    return {"dependency_manifest_schema_version": 1, "dependency_target_id": target_id,
            "dependency_files_sha256": {
        relative: hashlib.sha256(path.read_bytes()).hexdigest()
        for relative, path in sorted(_files(source, target_id).items())
    }, "submodule_shas": shas}


def verify_dependency_provenance(source: Path, target_id: str, provenance: dict) -> int:
    source = Path(source).resolve(strict=True)
    if (provenance.get("dependency_manifest_schema_version") != 1 or
            provenance.get("dependency_target_id") != target_id):
        raise ValueError("Dependency source-copy manifest belongs to a different target or schema")
    expected = provenance.get("dependency_files_sha256")
    shas = provenance.get("submodule_shas")
    if not isinstance(expected, dict) or not isinstance(shas, dict):
        raise ValueError("Git-free IDT builds require captured dependency hashes and pins")
    if set(shas) != set(dependency_paths(target_id)):
        raise ValueError("Dependency pin list differs from the selected target")
    for relative in dependency_paths(target_id):
        if not isinstance(shas.get(relative), str) or not re.fullmatch(r"[a-f0-9]{40}", shas[relative]):
            raise ValueError("Missing/invalid dependency pin: " + relative)
    if target_id == "rx671-wifi" and shas[BOOT[target_id]] != BOOT_RX671_SHA:
        raise ValueError("RX671 boot-loader pin differs from the reviewed production helper")
    files = _files(source, target_id)
    for relative, path in files.items():
        digest = expected.get(relative)
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Unrecorded dependency file: " + relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Dependency file differs from captured source: " + relative)
    if set(expected) != set(files):
        raise ValueError("Dependency source-copy file list differs from captured source")
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "verify"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", choices=tuple(BOOT), required=True)
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    if args.action == "capture":
        captured = capture_dependency_provenance(args.source, args.target)
        if args.provenance is None:
            print(json.dumps(captured))
        else:
            provenance = json.loads(args.provenance.read_text(encoding="utf-8-sig"))
            provenance.update(captured)
            args.provenance.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    else:
        if args.provenance is None:
            parser.error("verify requires --provenance")
        provenance = json.loads(args.provenance.read_text(encoding="utf-8-sig"))
        count = verify_dependency_provenance(args.source, args.target, provenance)
        print(f"Verified {count} captured dependency files for {args.target}; no Git/network action.")


if __name__ == "__main__":
    main()

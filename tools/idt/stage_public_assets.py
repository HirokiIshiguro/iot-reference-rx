"""Stage a same-commit normal bundle outside the native source snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.idt import rpi4_pair
from tools.idt.public_signer_provision import ENVIRONMENT_INPUTS
from tools.normal_boot import FILES, validate as validate_normal_bundle
from tools.idt.targets import get_target

DIGEST_NAME = 'windows-source-sha256.txt'
ARTIFACT_NAMES = frozenset(FILES) | {'normal_install_manifest.json', DIGEST_NAME}
MAX_ASSET_BYTES = 64 * 1024 * 1024


def digest_snapshot(snapshot: dict[str, str]) -> str:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


def source_digest(source: Path) -> str:
    return digest_snapshot(rpi4_pair.snapshot(source))


def write_source_digest(source: Path, destination: Path) -> None:
    """Snapshot first; only then create the job-owned output inside artifacts."""
    source = source.resolve(strict=True)
    destination = Path(destination)
    expected = source / 'artifacts/idt-source/windows-source-sha256.txt'
    if destination != expected or destination.exists() or destination.is_symlink():
        raise ValueError('unexpected source digest destination')
    value = source_digest(source)
    destination.parent.mkdir(parents=True, exist_ok=False)
    with destination.open('x', encoding='ascii', newline='\n') as output:
        output.write(value + '\n')


def stage_assets(source: Path, private_root: Path, source_sha: str) -> tuple[dict[str, str], str]:
    """Copy only the expected public files, validate, then remove their checkout copies."""
    source = source.resolve(strict=True)
    private_root = private_root.resolve(strict=True)
    if private_root == source or source in private_root.parents:
        raise ValueError('public assets must be staged outside the source checkout')
    parent = source / 'artifacts'
    incoming = parent / 'normal_boot_rx72n'
    for path in (parent, incoming):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or path.is_symlink() or info.st_uid != os.geteuid():
            raise ValueError('unexpected public artifact directory')
    if {entry.name for entry in parent.iterdir()} != {'normal_boot_rx72n'}:
        raise ValueError('unexpected checkout artifacts')
    if {entry.name for entry in incoming.iterdir()} != ARTIFACT_NAMES:
        raise ValueError('unexpected public artifact set')
    staged = private_root / 'public-assets'
    staged.mkdir(mode=0o700, exist_ok=False)
    identities = {}
    for name in sorted(ARTIFACT_NAMES):
        origin = incoming / name
        descriptor = os.open(origin, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_nlink != 1 or not 0 < info.st_size <= MAX_ASSET_BYTES):
                raise ValueError('invalid public artifact')
            identities[name] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            target = staged / name
            with os.fdopen(descriptor, 'rb', closefd=False) as src, target.open('xb') as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
            target.chmod(0o600)
            after = os.fstat(descriptor)
            if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != identities[name]:
                raise ValueError('public artifact changed while staging')
        finally:
            os.close(descriptor)
    validate_normal_bundle(staged, get_target('rx72n-ethernet'), source_sha)
    expected_digest = (staged / DIGEST_NAME).read_text(encoding='ascii').strip()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_digest):
        raise ValueError('invalid Windows source digest')
    for name, expected in identities.items():
        path = incoming / name
        info = path.lstat()
        if path.is_symlink() or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != expected:
            raise ValueError('public artifact changed before checkout cleanup')
    for name in identities:
        (incoming / name).unlink()
    incoming.rmdir()
    return {variable: str(staged / name) for name, variable in ENVIRONMENT_INPUTS.items()}, expected_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-windows-snapshot', type=Path, required=True)
    args = parser.parse_args()
    write_source_digest(ROOT, args.write_windows_snapshot)


if __name__ == '__main__':
    main()

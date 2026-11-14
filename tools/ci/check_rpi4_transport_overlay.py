#!/usr/bin/env python3
"""Offline check of the Transport run-copy preparation; never launches IDT."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.idt.idt_bundle import _read_manifest, verify_install
from tools.idt.rpi4_sample_smoke import PACKAGES, digest
from tools.idt.rpi4_transport_overlay import FRQ_RELATIVE, TEST_RELATIVE, prepare, sha256


def main():
    if (os.environ.get('CI_PROJECT_ID') != '38' or os.environ.get('CI_PIPELINE_SOURCE') != 'api'
            or os.environ.get('CI_COMMIT_BRANCH') != '207-idt-rpi4-transport-prep'):
        raise RuntimeError('overlay check requires the dedicated project, API and ref')
    if os.uname().machine != 'aarch64':
        raise RuntimeError('overlay check requires ARM64')
    archive = Path(os.environ['IDT_RPI4_SAMPLE_ARCHIVE'])
    if not archive.is_absolute():
        raise RuntimeError('archive path must be absolute')
    archive_hash = sha256(archive)
    with tempfile.TemporaryDirectory(prefix='idt-rpi4-overlay-check-') as directory:
        root = Path(directory)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'LANG': 'C.UTF-8',
               'AWS_EC2_METADATA_DISABLED': 'true', 'AWS_CONFIG_FILE': '/dev/null',
               'AWS_SHARED_CREDENTIALS_FILE': '/dev/null'}
        subprocess.run(['apt-get', 'download', *PACKAGES], cwd=root, env=env, check=True, timeout=120)
        for name, expected in PACKAGES.items():
            packages = list(root.glob(name.split('=')[0] + '_*.deb'))
            if len(packages) != 1 or digest(packages[0]) != expected:
                raise RuntimeError('Ubuntu package hash mismatch')
            subprocess.run(['dpkg-deb', '-x', str(packages[0]), str(root / 'packages')], check=True)
        qemu = root / 'packages/usr/bin/qemu-x86_64-static'
        sysroot = root / 'packages/usr/x86_64-linux-gnu'
        run = prepare(archive, root, qemu, sysroot)
        idt = run / 'devicetester_freertos_linux'
        manifest = _read_manifest()
        expected = {**manifest['common_files'], **manifest['hosts']['linux']['files']}
        actual = {p.relative_to(idt).as_posix() for tree in ('bin', 'tests/FRQ_2.5.0')
                  for p in (idt / tree).rglob('*') if p.is_file()}
        if actual != set(expected):
            raise RuntimeError('unexpected immutable file inventory')
        for relative, original in expected.items():
            current = sha256(idt / relative)
            if (relative == TEST_RELATIVE.as_posix()) == (current == original):
                raise RuntimeError('unexpected immutable content difference')
        try:
            verify_install(idt, 'linux')
        except RuntimeError:
            pass  # The one intentional test.json edit must not claim original integrity.
        else:
            raise RuntimeError('modified run copy unexpectedly passed original manifest')
        metadata = json.loads((run / 'overlay-provenance.json').read_text())
        if (metadata['changed_file'] != TEST_RELATIVE.as_posix()
                or metadata['frq_sha256'] != expected[FRQ_RELATIVE.as_posix()]
                or metadata['qualification'] != 'not-established' or sha256(archive) != archive_hash):
            raise RuntimeError('overlay provenance mismatch')
        print('Verified original archive and exactly one temporary Transport test.json change.', flush=True)
        print('No IDT, FRQ, AWS or device process was started.', flush=True)


if __name__ == '__main__':
    main()

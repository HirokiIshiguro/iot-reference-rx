#!/usr/bin/env python3
"""Prepare, but do not execute, an RX72N IDT Transport run copy for ARM64."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

try:
    from .idt_bundle import verify_archive_digest, verify_install
except ImportError:
    from idt_bundle import verify_archive_digest, verify_install

QEMU_SHA256 = 'de72ec1143909f0f495a53c36d9215cb86e2952517aad87044c741a1088dc60f'
SYSROOT_SHA256 = {
    'lib/ld-linux-x86-64.so.2': 'cff2a563ca82b90beb5c43db38b84efe0c610a9a0e3394083882abcf8431fbae',
    'lib/libc.so.6': '7e262ac92a454f36664b9c95a8927ecc4fb0f0f007206c2613b1e9ce14e76906',
    'lib/libpthread.so.0': '6e60f40770ad79be6db5a9a57a3ebe097483553ffb9b5d82a6ca355e5e9a7ed3',
    'lib/libresolv.so.2': '450072ad411b89b0c00bfecdd2eb97b7269c0278018d4727790f07063a996905',
}
TEST_RELATIVE = Path('tests/FRQ_2.5.0/suite/transportInterfaceTLS/tls/test.json')
FRQ_RELATIVE = Path('tests/FRQ_2.5.0/frq_linux_x86-64')
EXPECTED_LINUX = {'cmd': './../../../frq_linux_x86-64',
                  'args': ['-test=FullTransportInterfaceTLS', '-testGroup=FullTransportInterfaceTLS']}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def prepare(archive: Path, parent: Path, qemu: Path, sysroot: Path) -> Path:
    """Return a private prepared directory. This function never launches IDT or FRQ.

    The caller owns the returned directory and must delete it after all child
    processes have stopped. QEMU and sysroot must remain unchanged for the run.
    """
    if any(not Path(path).is_absolute() for path in (archive, parent, qemu, sysroot)):
        raise ValueError('runtime paths must be absolute')
    archive = Path(archive).resolve(strict=True)
    parent = Path(parent).resolve(strict=True)
    qemu = Path(qemu).resolve(strict=True)
    sysroot = Path(sysroot).resolve(strict=True)
    if not parent.is_dir() or not qemu.is_file() or not os.access(qemu, os.X_OK) or not sysroot.is_dir():
        raise ValueError('reviewed runtime paths are unavailable')
    if sha256(qemu) != QEMU_SHA256:
        raise ValueError('QEMU executable hash mismatch')
    for relative, expected in SYSROOT_SHA256.items():
        resolved = (sysroot / relative).resolve(strict=True)
        if sysroot not in resolved.parents or sha256(resolved) != expected:
            raise ValueError('x86 sysroot hash mismatch')
    run = Path(tempfile.mkdtemp(prefix='idt-rpi4-transport-', dir=parent))
    try:
        copied_archive = run / 'official.zip'
        shutil.copyfile(archive, copied_archive)
        archive_hash = sha256(copied_archive)
        verify_archive_digest('linux', archive_hash)
        with zipfile.ZipFile(copied_archive) as source:
            for entry in source.infolist():
                destination = (run / entry.filename).resolve()
                if run not in destination.parents or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('unsafe bundle member')
            source.extractall(run)
        copied_archive.unlink()
        idt = run / 'devicetester_freertos_linux'
        verify_install(idt, 'linux')
        test_path, frq = idt / TEST_RELATIVE, idt / FRQ_RELATIVE
        before_bytes = test_path.read_bytes()
        before = json.loads(before_bytes)
        if before.get('id') != 'Full_Transport_Interface_TLS' or before.get('execution', {}).get('linux') != EXPECTED_LINUX:
            raise ValueError('unexpected Transport test definition')
        frq_hash = sha256(frq)
        # zipfile does not restore executable modes. Only the private copy is changed.
        frq.chmod(0o700)
        (idt / 'bin/devicetester_linux_x86-64').chmod(0o700)
        after = copy.deepcopy(before)
        after['execution']['linux'] = {'cmd': str(qemu),
                                       'args': ['-L', str(sysroot), str(frq), *EXPECTED_LINUX['args']]}
        test_path.write_text(json.dumps(after, indent=2) + '\n', encoding='utf-8')
        reread = json.loads(test_path.read_text(encoding='utf-8'))
        if reread != after or sha256(frq) != frq_hash:
            raise RuntimeError('overlay verification failed')
        # The original manifest no longer matches this run copy's test.json.
        provenance = {'schema_version': 1, 'target': 'rx72n-ethernet', 'archive_sha256': archive_hash,
                      'frq_sha256': frq_hash, 'qemu_sha256': QEMU_SHA256,
                      'test_before_sha256': hashlib.sha256(before_bytes).hexdigest(),
                      'test_after_sha256': sha256(test_path), 'changed_file': TEST_RELATIVE.as_posix(),
                      'qualification': 'not-established'}
        (run / 'overlay-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
        return run
    except BaseException:
        shutil.rmtree(run)
        raise

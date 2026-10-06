#!/usr/bin/env python3
"""Flash verified target images while the separate UART helper owns the board."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import stat
import sys
import time
from targets import get_target, target_fingerprint
from rfp_process import raise_if_rfp_unsafe, run_guarded
from cleanup_budget import (FLASH_ABORT_RESET_SECONDS, FLASH_CONTROL_SECONDS,
                            FLASH_DOWNLOAD_SECONDS, FLASH_LOCK_WAIT_SECONDS,
                            FLASH_RFP_COMMAND_SECONDS, RX671_SIGNER_PROVISION_SECONDS,
                            flash_transaction_seconds)

FLASH_INPUTS = frozenset(('bootloader.mot', 'bootloader_bank1.mot', 'idt_transport.rsu',
                          'test_uart_download_rx72n.py', 'rpi_flash.py', 'targets.py', 'targets.json',
                          'cleanup_budget.py', 'rfp_process.py'))


def validate_rx671_policy_binding(root, manifest):
    hashes = {name: hashlib.sha256((root / staged).read_bytes()).hexdigest()
              for name, staged in (('rx_bootloader_config.h', 'rx671_bootloader_config.h'),
                                   ('rx671.h', 'rx671_target.h'))}
    if manifest.get('bootloader_policy_sha256') != hashes:
        raise RuntimeError('RX671 bootloader policy differs from its effective build inputs')


def validate_flash_manifest(root, target, expected_sha256):
    manifest_path = root / 'flash_manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RuntimeError('Missing or symbolic link flash manifest')
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError('Flash manifest hash mismatch')
    manifest = json.loads(raw)
    if (manifest.get('schema_version') != 1 or manifest.get('target_id') != target['id'] or
            manifest.get('target_sha256') != target_fingerprint(target)):
        raise RuntimeError('Flash manifest target mismatch')
    files = manifest.get('files', {})
    expected = FLASH_INPUTS
    if target['id'] == 'rx671-wifi':
        from rx671_provision import RX671_INPUTS
        expected = expected | RX671_INPUTS
    if not isinstance(files, dict) or set(files) != expected:
        raise RuntimeError('Unexpected flash input set')
    for name, metadata in files.items():
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Missing or symbolic link flash input: ' + name)
        raw = path.read_bytes()
        if (not isinstance(metadata, dict) or len(raw) != metadata.get('size_bytes') or
                hashlib.sha256(raw).hexdigest() != metadata.get('sha256')):
            raise RuntimeError('Flash input hash mismatch: ' + name)
    if target['id'] == 'rx671-wifi':
        validate_rx671_policy_binding(root, manifest)
        from rx671_provision import validate_bundle
        plan = validate_bundle({name: root / name for name in expected}, target, manifest.get('source_sha'))
        if plan != manifest.get('rx671_provision_plan'):
            raise RuntimeError('RX671 provisioning plan does not match validated flash inputs')
    return manifest


def validate_owner(target, token, allow_closing=False):
    path = Path(target['owner_file'])
    if path.is_symlink():
        raise RuntimeError('Symbolic link owner file')
    owner = json.loads(path.read_text(encoding='utf-8'))
    expected = {'host': target['hostname'], 'uart': target['uart'], 'token': token,
                'target_id': target['id'], 'target_sha256': target_fingerprint(target)}
    if socket.gethostname() != target['hostname'] or any(owner.get(k) != v for k, v in expected.items()):
        raise RuntimeError('Board lock ownership mismatch')
    pid = owner.get('pid')
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise RuntimeError('Invalid board lock owner PID')
    expected_socket = '/tmp/codex-idt-155-control-' + target['id'] + '-' + str(pid) + '.sock'
    if owner.get('control_socket') != expected_socket:
        raise RuntimeError('Board control socket mismatch')
    if owner.get('closing') and not allow_closing:
        raise RuntimeError('Board owner is closing')
    os.kill(pid, 0)
    return owner


def control(target, token, action):
    deadline = time.monotonic() + FLASH_CONTROL_SECONDS
    owner = validate_owner(target, token)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        def remaining():
            seconds = deadline - time.monotonic()
            if seconds <= 0:
                raise RuntimeError('UART control time budget exhausted')
            client.settimeout(seconds)
        remaining()
        client.connect(owner['control_socket'])
        request = {'token': token, 'target_id': target['id'],
                   'target_sha256': target_fingerprint(target), 'action': action}
        remaining()
        client.sendall((json.dumps(request) + '\n').encode())
        raw = bytearray()
        while b'\n' not in raw and len(raw) <= 4096:
            remaining()
            chunk = client.recv(4097 - len(raw))
            if not chunk:
                break
            raw.extend(chunk)
        remaining()
        if len(raw) > 4096 or not raw.endswith(b'\n') or raw.count(b'\n') != 1:
            raise RuntimeError('Invalid bounded UART control response')
        answer = json.loads(raw)
        if (not answer.get('ok') or answer.get('action') != action or
                answer.get('target_id') != target['id'] or
                answer.get('target_sha256') != target_fingerprint(target)):
            raise RuntimeError('UART control rejected: ' + action)


def rfp_command(target):
    return ['sudo', '-n', '/usr/local/bin/rfp-cli', '-device', target['rfp_device'],
            '-tool', 'e2l:' + target['e2lite'], '-if', 'fine', '-speed', target['rfp_speed'],
            '-auth', 'id', 'F' * 32]


def download_command(root, target, reset_command):
    # These are bootloader markers, independent of network/application startup.
    success = 'swap bank' if target['id'] == 'rx65n-bg96' else 'jump to user program'
    ready_timeout = '180' if target['id'] == 'rx65n-bg96' else '90'
    command = [sys.executable, str(root / 'test_uart_download_rx72n.py'), '--rsu',
            str(root / 'idt_transport.rsu'), '--port', target['uart'], '--baud', str(target['baud']),
            '--timeout', '420', '--post-tx-wait', '120', '--wait-for-ready',
            '--ready-timeout', ready_timeout, '--ready-message', 'send "userprog.rsu" via UART.',
            '--reset-cmd', shlex.join(reset_command), '--success-message', success, '--strict-success']
    if target['id'] in ('rx65n-bg96', 'rx671-wifi'):
        # These receivers acknowledge each 32 KiB flash write. Continuous TX
        # overruns reception during flash programming; keep the existing
        # signature/end-state checks and wait for the real progress event.
        command += ['--ack-each-chunk', '--send-chunk-size', '32768',
                    '--ack-prefix', 'installing firmware...']
    return command


def open_rfp_lock(path):
    if path.parent.is_symlink():
        raise RuntimeError('Symbolic link RFP lock directory')
    try:
        path.parent.mkdir(mode=0o1777, parents=True)
        os.chmod(path.parent, 0o1777)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666)
    except FileExistsError:
        descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    else:
        os.fchmod(descriptor, 0o666)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RuntimeError('Nonregular RFP lock')
    return descriptor


def flash(root, target, token, manifest=None):
    if target['id'] == 'rx671-wifi':
        # Fail before opening a lock, UART, or programmer when callers omit
        # initial signer inputs. A locally written receipt cannot enable flash.
        if manifest is None:
            raise RuntimeError('RX671 initial public signer provisioning inputs are required')
        validate_rx671_policy_binding(root, manifest)
        from rx671_provision import RX671_INPUTS, validate_bundle
        plan = validate_bundle({name: root / name for name in FLASH_INPUTS | RX671_INPUTS},
                               target, manifest.get('source_sha'))
        if plan != manifest.get('rx671_provision_plan'):
            raise RuntimeError('RX671 initial signer plan mismatch')
    raise_if_rfp_unsafe(target)
    import fcntl
    descriptor = open_rfp_lock(Path(target['rfp_lock']))
    base = rfp_command(target)
    transaction_deadline = time.monotonic() + flash_transaction_seconds(target['id'])

    def call(arguments, timeout=FLASH_RFP_COMMAND_SECONDS):
        # Recheck after each potentially long command, including owner shutdown.
        validate_owner(target, token)
        remaining = transaction_deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Flash transaction timeout')
        result = run_guarded(arguments, target=target, timeout=min(timeout, remaining))
        validate_owner(target, token)
        return result

    try:
        # Hold the production global RFP lock over the entire callback, so the
        # bridge's final reset happens after every possible programming/run step.
        deadline = time.monotonic() + FLASH_LOCK_WAIT_SECONDS
        while True:
            validate_owner(target, token)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Global RFP lock timeout')
                time.sleep(0.1)
        validate_owner(target, token)
        raise_if_rfp_unsafe(target)
        control(target, token, 'pause')
        control(target, token, 'mark-flashed')
        try:
            download = download_command(root, target, [*base, '-sig', '-run', '-noquery'])
            if target['id'] == 'rx671-wifi':
                from rx671_provision import provision_and_install
                if transaction_deadline - time.monotonic() < RX671_SIGNER_PROVISION_SECONDS:
                    raise RuntimeError('Insufficient RX671 signer provisioning budget')
                provision_and_install(root, target, manifest['source_sha'], call, download,
                                      check_owner=lambda: validate_owner(target, token))
            else:
                call([*base, '-erase-chip', '-noquery'])
                call([*base, '-p', str(root / 'bootloader.mot'), '-v', '-noquery'])
                call([*base, '-p', str(root / 'bootloader_bank1.mot'), '-v', '-noquery'])
                call(download, timeout=FLASH_DOWNLOAD_SECONDS)
            call([*base, '-sig', '-reset', '-noquery'])
            control(target, token, 'resume')
            call([*base, '-sig', '-run', '-noquery'])
            print('IDT_FLASH_COMPLETE', flush=True)
        except BaseException:
            # The bridge retains its bench lock until this transaction releases
            # RFP, then performs the authoritative reset and quiet check.
            try:
                raise_if_rfp_unsafe(target)
                validate_owner(target, token, allow_closing=True)
                run_guarded([*base, '-sig', '-reset', '-noquery'], target=target,
                            timeout=FLASH_ABORT_RESET_SECONDS)
            except BaseException:
                print('IDT_FLASH_ABORT_RESET_FAILED', file=sys.stderr, flush=True)
            raise
    finally:
        os.close(descriptor)


def main():
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    p = argparse.ArgumentParser()
    for name in ('token', 'root', 'target', 'manifest_sha256'):
        p.add_argument(name)
    a = p.parse_args()
    raw_root=Path(a.root)
    if (not a.target or not re.fullmatch('[a-f0-9]{32}',a.token) or
            not re.fullmatch('[a-f0-9]{64}',a.manifest_sha256) or raw_root.is_symlink()):
        raise RuntimeError('Invalid flash token or symbolic link directory')
    root=raw_root.resolve(strict=True)
    if root.parent != Path('/tmp') or root.name != 'codex-idt-155-flash-'+a.token:
        raise RuntimeError('Unexpected flash directory')
    target = get_target(a.target)  # Explicit argument; remote IDT_TARGET cannot redirect hardware.
    manifest = validate_flash_manifest(root, target, a.manifest_sha256)
    validate_owner(target, a.token)
    flash(root, target, a.token, manifest)
if __name__=='__main__':main()

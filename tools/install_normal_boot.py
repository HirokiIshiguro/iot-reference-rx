"""Install a normal signed application under the CI shell's inherited bench lease.

The caller must hold canonical bench flock on FD 9 through subsequent credential
provisioning/tests. This entry owns the global programmer lock through public
trust preparation, signed install, reset, and a fresh one-second UART quiet test.
Reset-only mode validates the reference bundle and uses the same ownership and
end-state checks without replacing the application or boot trust on the board.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import socket
import stat
import sys
import tempfile
import time

try:
    from . import normal_boot
    from .idt import cleanup_budget as budget, public_signer_provision as trust, rfp_process
    from .idt.targets import get_target, target_ids
except ImportError:
    import normal_boot
    from idt import cleanup_budget as budget, public_signer_provision as trust, rfp_process
    from idt.targets import get_target, target_ids


RESET_ONLY_PROFILE = "rx-normal-reset-only-v1"


def check_bench_lease(target, descriptor=9, *, owner=None):
    if socket.gethostname() != target["hostname"]:
        raise RuntimeError("Normal install host differs from the reviewed board identity")
    path = Path(target["bench_lock"])
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise RuntimeError("Linked bench lock is not accepted")
    actual, expected = os.fstat(descriptor), path.stat()
    if not stat.S_ISREG(actual.st_mode) or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
        raise RuntimeError("Normal install requires the canonical inherited bench descriptor")
    # fdinfo reports locks attached to this open file description. Merely
    # observing another process's lock on the same inode would not prove ownership.
    info = Path(f"/proc/self/fdinfo/{descriptor}").read_text()
    locks = [line.split() for line in info.splitlines() if line.startswith("lock:")]
    if not any("FLOCK" in fields and "WRITE" in fields and "->" not in fields for fields in locks):
        raise RuntimeError("Inherited bench descriptor does not own an exclusive flock")
    if os.path.lexists(target["owner_file"]):
        if owner is None or json.loads(trust._bytes(Path(target["owner_file"]))) != owner:
            raise RuntimeError("A retained or different hardware owner blocks normal installation")
    elif owner is not None:
        raise RuntimeError("Normal install owner record disappeared during the transaction")
    rfp_process.raise_if_rfp_unsafe(target)


def check_devices(target):
    if not stat.S_ISCHR(os.stat(target["uart"]).st_mode):
        raise RuntimeError("Reviewed UART does not resolve to a character device")
    matches = []
    for node in Path("/sys/bus/usb/devices").iterdir():
        try:
            if ((node/"idVendor").read_text().strip() == "045b" and
                    (node/"idProduct").read_text().strip() == "82a0"):
                value = (node/"serial").read_text().strip()
                matches.append(value.removeprefix("E2L:").strip())
        except FileNotFoundError:
            continue
    if matches.count(target["e2lite"]) != 1:
        raise RuntimeError("Reviewed E2 Lite USB identity is missing or ambiguous")


def check_ci_identity(target, environ=None):
    """Reject a physical override rather than silently using another CI bench."""
    environment = os.environ if environ is None else environ
    prefixes = {"rx72n-ethernet": "RX72N_LINUX_", "rx65n-bg96": "RX65N_BG96_", "rx671-wifi": "RX671_WIFI_"}
    prefix = prefixes[target["id"]]
    expected = {prefix+"UART_PORT": target["uart"], prefix+"UART_BAUD_RATE": str(target["baud"]),
                prefix+"RFP_TOOL": "e2l:"+target["e2lite"]}
    if target["id"] == "rx72n-ethernet":
        expected.update({"RFP_SPEED":target["rfp_speed"], "RFP_AUTH":"F"*32})
    else:
        expected.update({prefix+"RFP_DEVICE":target["rfp_device"], prefix+"RFP_INTERFACE":"fine",
                         prefix+"RFP_SPEED":target["rfp_speed"], prefix+"RFP_AUTH_ID":"F"*32})
    if target["id"] == "rx65n-bg96" and not environment.get(prefix+"UART_PORT"):
        expected["COMMAND_PORT"] = target["uart"]
    if target["id"] == "rx671-wifi":
        expected[prefix+"E2OB_SERIAL"] = target["e2lite"]
    for name, value in expected.items():
        actual = environment.get(name)
        if actual and actual != value:
            raise RuntimeError("Normal install physical CI override differs from reviewed target: "+name)


def rfp_command(target):
    return ["sudo", "-n", "/usr/local/bin/rfp-cli", "-device", target["rfp_device"],
            "-tool", "e2l:"+target["e2lite"], "-if", "fine", "-speed", target["rfp_speed"],
            "-auth", "id", "F"*32]


def download_command(root, target):
    command = [sys.executable, str(Path(__file__).with_name("test_uart_download_rx72n.py")),
        "--rsu", str(root/"normal_app.rsu"), "--port", target["uart"], "--baud", str(target["baud"]),
        "--timeout", "420", "--post-tx-wait", "120", "--wait-for-ready", "--ready-timeout",
        "180" if target["id"] == "rx65n-bg96" else "90", "--ready-message", 'send "userprog.rsu" via UART.',
        "--reset-cmd", shlex.join([*rfp_command(target), "-sig", "-run", "-noquery"]),
        "--success-message", "jump to user program", "--success-timeout", "90", "--strict-success"]
    if target["id"] in ("rx65n-bg96", "rx671-wifi"):
        command += ["--ack-each-chunk", "--send-chunk-size", "32768", "--ack-prefix", "installing firmware..."]
    return command


def reset_and_quiet(target, call, check_owner):
    import serial
    check_owner()
    trust._checked_call(call, check_owner, [*rfp_command(target), "-sig", "-reset", "-noquery"],
                        budget.FLASH_ABORT_RESET_SECONDS)
    with serial.Serial(target["uart"], target["baud"], timeout=0.1, exclusive=True) as observer:
        observer.reset_input_buffer()
        deadline, count = time.monotonic()+budget.END_STATE_QUIET_SECONDS, 0
        while time.monotonic() < deadline:
            check_owner()
            count += len(observer.read(max(1, observer.in_waiting)))
    if count:
        raise RuntimeError("Normal install end-state failed: UART remained active after reset")
    return {"reset_command_exit_zero": True, "fresh_uart_quiet_1s": True, "physical_reset_hold": "unverified"}


def install(root, target, source_sha, reset_only=False):
    # All image/public signer validation precedes device or programmer access.
    manifest = normal_boot.validate(root, target, source_sha)
    check_ci_identity(target)
    import fcntl
    owner = None
    check_owner = lambda: check_bench_lease(target, owner=owner)
    check_owner()
    check_devices(target)
    event_directory = Path(tempfile.mkdtemp(prefix="rx-normal-boot-events-"))
    # The same production lock used by native IDT is held for this transaction.
    lock = Path(target["rfp_lock"])
    if lock.parent.is_symlink():
        raise RuntimeError("Linked global programmer lock directory")
    try:
        lock.parent.mkdir(mode=0o1777, parents=True)
        os.chmod(lock.parent, 0o1777)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666)
    except FileExistsError:
        descriptor = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
    else:
        os.fchmod(descriptor, 0o666)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RuntimeError("Nonregular global programmer lock")
    deadline = time.monotonic()+budget.flash_transaction_seconds(target["id"])
    # The native bridge creates this same canonical file with O_EXCL. A failed
    # end-state therefore blocks both normal and native-IDT reuse of the board.
    owner_path = Path(target["owner_file"])
    touched, owner_created, completed, end_state = False, False, False, None
    def call(command, timeout=budget.FLASH_RFP_COMMAND_SECONDS, *, cleanup=False):
        check_owner()
        remaining = budget.FLASH_ABORT_RESET_SECONDS if cleanup else deadline-time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Normal install transaction deadline exhausted")
        result = rfp_process.run_guarded(command, target=target, timeout=min(timeout, remaining))
        check_owner()
        return result
    try:
        lock_deadline = time.monotonic()+budget.FLASH_LOCK_WAIT_SECONDS
        while True:
            check_owner()
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= lock_deadline:
                    raise RuntimeError("Global programmer lock timeout")
                time.sleep(0.1)
        check_owner()
        owner_fd = os.open(owner_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        owner = {"profile": RESET_ONLY_PROFILE if reset_only else normal_boot.PROFILE,
                 "pid": os.getpid(), "token": secrets.token_hex(16), "target_id": target["id"]}
        owner["validated_bundle_source_sha" if reset_only else "source_sha"] = source_sha
        with os.fdopen(owner_fd, "w", encoding="utf-8") as stream:
            json.dump(owner, stream)
            stream.flush(); os.fsync(stream.fileno())
        owner_created = True
        touched = True
        if not reset_only:
            trust.provision_boot_trust(root, target, source_sha, call, check_owner, artifact_dir=event_directory)
            if normal_boot.validate(root, target, source_sha) != manifest:
                raise RuntimeError("Normal install bundle changed during boot-trust preparation")
            trust._checked_call(call, check_owner, download_command(root, target), budget.FLASH_DOWNLOAD_SECONDS)
            completed = True
    finally:
        try:
            if touched:
                end_state = reset_and_quiet(target, lambda command, timeout: call(command, timeout, cleanup=True), check_owner)
                if owner_created:
                    owner_path.unlink()
        finally:
            os.close(descriptor)
    if reset_only:
        return {"schema_version": 1, "profile": RESET_ONLY_PROFILE,
                "validated_bundle_source_sha": source_sha, "target_id": target["id"],
                "bundle_validation": "offline_reference_only",
                "current_image_signature": "not_reverified", "code_flash_written": False,
                "data_flash_written": False, "image_replaced": False, "end_state": end_state}
    return {"schema_version": 1, "profile": normal_boot.PROFILE, "source_sha": source_sha,
            "target_id": target["id"], "tls_backend": manifest["tls_backend"],
            "signed_install_and_bootloader_handoff": completed,
            "application_functional_test": "subsequent_normal_ci_provisioning_and_monitor",
            "event_directory": str(event_directory), "end_state": end_state}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--target", choices=target_ids(), required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--reset-only", action="store_true",
                        help="Preserve the installed image and trust; verify reset and fresh UART quiet only")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Normal hardware installation requires the reviewed Linux bench")
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    # Preserve the supplied path until ordinary-file validation has rejected
    # linked parent directories; resolving first would hide that information.
    receipt = install(args.bundle.absolute(), get_target(args.target), args.source_sha,
                      reset_only=args.reset_only)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

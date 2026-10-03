#!/usr/bin/env python3
"""Pinned-target raw UART bridge. SSH carries bytes; stderr carries status."""
import fcntl
import hmac
import json
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess
import sys
import time
from targets import get_target, target_fingerprint
from cleanup_budget import RFP_LOCK_WAIT_SECONDS, END_STATE_RESET_SECONDS, END_STATE_QUIET_SECONDS
from rfp_process import raise_if_rfp_unsafe, run_guarded


def open_shared_lock(path):
    """Use the production flock inode, including its shared-user permissions."""
    if path.parent.is_symlink():
        raise RuntimeError("refusing symbolic link lock directory")
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
        raise RuntimeError("refusing nonregular shared lock")
    return descriptor


def write_all(fd, data):
    while data:
        written = os.write(fd, data)
        if written <= 0:
            raise OSError("raw stream write failed")
        data = data[written:]


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def persist_owner(owner, owner_path, initial=False):
    target = owner_path if initial else Path(str(owner_path) + "." + str(os.getpid()) + ".tmp")
    if not initial:
        current = json.loads(owner_path.read_text(encoding="utf-8"))
        if any(current.get(key) != owner[key] for key in ("token", "target_id", "target_sha256")):
            raise RuntimeError("owner token changed while bench lock was held")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(owner, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if not initial:
        os.replace(target, owner_path)


def reset_and_observe_quiet(serial_module, target):
    raise_if_rfp_unsafe(target)
    descriptor = open_shared_lock(Path(target["rfp_lock"]))
    try:
        # Every supported callback's transaction and abort reset fit this bound.
        deadline = time.monotonic() + RFP_LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("end-state reset failed: global RFP lock timeout")
                time.sleep(0.1)
        # A callback may have persisted an unsafe sentinel while we waited.
        raise_if_rfp_unsafe(target)
        command = ["sudo", "-n", "/usr/local/bin/rfp-cli", "-d", target["rfp_device"],
                   "-t", "e2l:" + target["e2lite"], "-if", "fine", "-s", target["rfp_speed"],
                   "-auth", "id", "F" * 32, "-sig", "-reset", "-noquery"]
        completed = run_guarded(command, target=target, timeout=END_STATE_RESET_SECONDS, quiet=True)
        if completed.returncode != 0:
            raise RuntimeError("end-state reset failed: rfp-cli exit " + str(completed.returncode))
        with serial_module.Serial(target["uart"], target["baud"], timeout=0.1, exclusive=True) as observer:
            observer.reset_input_buffer()
            deadline = time.monotonic() + END_STATE_QUIET_SECONDS
            count = 0
            while time.monotonic() < deadline:
                count += len(observer.read(max(1, observer.in_waiting)))
        print("IDT_UART_END_STATE reset_requested=ok physical_hold=unverified quiet_1s=" +
              ("yes" if count == 0 else "no") + " bytes=" + str(count),
              file=sys.stderr, flush=True)
        if count:
            raise RuntimeError("end-state verification failed: UART remained active after reset request")
        # This is the existing CI operational end-state check. A quiet UART is
        # not a measurement of RESET pin voltage, so retain physical_hold=unverified.
    finally:
        os.close(descriptor)


def main():
    if len(sys.argv) != 3 or len(sys.argv[1]) != 32 or not sys.argv[2]:
        raise ValueError("a 32-character hexadecimal bench token and explicit target ID are required")
    token = sys.argv[1]
    if any(c not in "0123456789abcdef" for c in token):
        raise ValueError("invalid bench token")
    target = get_target(sys.argv[2])
    target_sha256 = target_fingerprint(target)
    owner_path = Path(target["owner_file"])
    if socket.gethostname() != target["hostname"]:
        raise RuntimeError("refusing UART access: unexpected RPi hostname")
    raise_if_rfp_unsafe(target)
    import serial
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    lock_fd = open_shared_lock(Path(target["bench_lock"]))
    port = None
    own_owner_file = False
    controller = None
    socket_path = Path("/tmp/codex-idt-155-control-" + target["id"] + "-" + str(os.getpid()) + ".sock")
    owner = {"pid": os.getpid(), "token": token, "host": target["hostname"], "uart": target["uart"],
             "target_id": target["id"], "target_sha256": target_sha256,
             "control_socket": str(socket_path), "touched": False, "paused": False, "closing": False}
    pending = bytearray()

    def open_uart():
        return serial.Serial(target["uart"], target["baud"], timeout=0, write_timeout=5, exclusive=True)

    def send_uart(data):
        remaining = memoryview(data)
        while remaining:
            written = port.write(remaining)
            if not written:
                raise OSError("UART write failed")
            remaining = remaining[written:]

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # An existing owner file needs inspection, even if the flock is free.
        persist_owner(owner, owner_path, initial=True)
        own_owner_file = True
        controller = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        controller.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        controller.listen(2)
        port = open_uart()
        print("IDT_UART_READY", file=sys.stderr, flush=True)
        while True:
            watched = [0, controller.fileno()] + ([port.fileno()] if port is not None else [])
            readable, _, _ = select.select(watched, [], [], 1)
            if controller.fileno() in readable:
                client, _ = controller.accept()
                with client:
                    client.settimeout(2)
                    reply = {"ok": False}
                    try:
                        line = bytearray()
                        while b"\n" not in line:
                            chunk = client.recv(1024)
                            if not chunk or len(line) + len(chunk) > 4096:
                                raise ValueError("one bounded JSON line is required")
                            line.extend(chunk)
                        request = json.loads(line.split(b"\n", 1)[0])
                        supplied_token = request.get("token", "")
                        if not isinstance(supplied_token, str) or not hmac.compare_digest(supplied_token, token):
                            raise ValueError("bench token mismatch")
                        if request.get("target_id") != target["id"] or request.get("target_sha256") != target_sha256:
                            raise ValueError("bench target mismatch")
                        action = request.get("action")
                        if action == "pause":
                            if port is not None:
                                port.close()
                                port = None
                            owner["paused"] = True
                            persist_owner(owner, owner_path)
                        elif action == "resume":
                            if port is None:
                                port = open_uart()
                            if pending:
                                send_uart(pending)
                                pending.clear()
                            owner["paused"] = False
                            persist_owner(owner, owner_path)
                        elif action == "mark-flashed":
                            # Mark before the first mutation so failures still trigger reset hold.
                            owner["touched"] = True
                            persist_owner(owner, owner_path)
                        else:
                            raise ValueError("unsupported bridge action")
                        reply.update(ok=True, action=action, paused=owner["paused"], touched=owner["touched"],
                                     target_id=target["id"], target_sha256=target_sha256)
                    except (ValueError, OSError, TypeError, AttributeError) as error:
                        reply["error"] = str(error)
                    client.sendall((json.dumps(reply) + "\n").encode("utf-8"))
            if 0 in readable:
                incoming = os.read(0, 65536)
                if not incoming:
                    break
                if port is None:
                    if len(pending) + len(incoming) > 65536:
                        raise RuntimeError("paused UART input exceeded its buffer")
                    pending.extend(incoming)
                else:
                    send_uart(incoming)
            if port is not None and port.fileno() in readable:
                incoming = os.read(port.fileno(), 65536)
                if incoming:
                    write_all(1, incoming)
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        reset_failed = False
        try:
            if own_owner_file:
                owner["closing"] = True
                persist_owner(owner, owner_path)
            if port is not None:
                port.close()
            if owner["touched"]:
                try:
                    reset_and_observe_quiet(serial, target)
                except BaseException:
                    reset_failed = True
                    raise
        except BaseException:
            reset_failed = True
            raise
        finally:
            try:
                if controller is not None:
                    controller.close()
                    socket_path.unlink(missing_ok=True)
                # A failed reset leaves a sentinel requiring bench inspection.
                if own_owner_file and not reset_failed:
                    try:
                        current = json.loads(owner_path.read_text(encoding="utf-8"))
                        if all(current.get(key) == owner[key] for key in ("token", "target_id", "target_sha256")):
                            owner_path.unlink()
                    except FileNotFoundError:
                        pass
            finally:
                os.close(lock_fd)  # Unlock only after the reset/quiet check and resource cleanup.


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print("IDT_UART_ERROR: " + str(error), file=sys.stderr, flush=True)
        sys.exit(1)

#!/usr/bin/env python3
"""RPi1-only raw UART bridge. SSH stdin/stdout carry bytes, stderr carries status."""
import fcntl
import hmac
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

EXPECTED_HOST = "ef-saffti-001-rpi-001"
UART = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A904CXV7-if00-port0"
BAUD = 921600
LOCK = Path("/tmp/e2lite-rfp-cli.lock.d/rx72n-device-01.lock")
OWNER = Path("/tmp/codex-idt-155-owner.json")
RFP_LOCK = Path("/tmp/rx72n-e2lite-rfp-cli.lock.d/rfp-cli.lock")


def write_all(fd, data):
    while data:
        written = os.write(fd, data)
        if written <= 0:
            raise OSError("raw stream write failed")
        data = data[written:]


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def persist_owner(owner, initial=False):
    target = OWNER if initial else Path(str(OWNER) + "." + str(os.getpid()) + ".tmp")
    if not initial:
        current = json.loads(OWNER.read_text(encoding="utf-8"))
        if current.get("token") != owner["token"]:
            raise RuntimeError("owner token changed while bench lock was held")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(owner, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if not initial:
        os.replace(target, OWNER)


def reset_hold_and_observe(serial_module):
    RFP_LOCK.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    descriptor = os.open(RFP_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("end-state reset failed: global RFP lock timeout")
                time.sleep(0.1)
        command = ["sudo", "-n", "/usr/local/bin/rfp-cli", "-d", "RX72x",
                   "-t", "e2l:OBE110008", "-if", "fine", "-s", "1500K",
                   "-auth", "id", "F" * 32, "-sig", "-reset", "-noquery"]
        completed = subprocess.run(command, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=60, check=False)
        if completed.returncode != 0:
            raise RuntimeError("end-state reset failed: rfp-cli exit " + str(completed.returncode))
        with serial_module.Serial(UART, BAUD, timeout=0.1, exclusive=True) as observer:
            observer.reset_input_buffer()
            deadline = time.monotonic() + 1.0
            count = 0
            while time.monotonic() < deadline:
                count += len(observer.read(max(1, observer.in_waiting)))
        print("IDT_UART_END_STATE reset_hold=ok quiet_1s=" +
              ("yes" if count == 0 else "no") + " bytes=" + str(count),
              file=sys.stderr, flush=True)
        if count:
            raise RuntimeError("end-state verification failed: UART remained active after reset hold")
    finally:
        os.close(descriptor)


def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 32:
        raise ValueError("one 32-character hexadecimal bench token is required")
    token = sys.argv[1]
    if any(c not in "0123456789abcdef" for c in token):
        raise ValueError("invalid bench token")
    if socket.gethostname() != EXPECTED_HOST:
        raise RuntimeError("refusing UART access: unexpected RPi hostname")
    import serial
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    LOCK.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    lock_fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    port = None
    own_owner_file = False
    controller = None
    socket_path = Path("/tmp/codex-idt-155-control-" + str(os.getpid()) + ".sock")
    owner = {"pid": os.getpid(), "token": token, "host": EXPECTED_HOST, "uart": UART,
             "control_socket": str(socket_path), "touched": False, "paused": False}
    pending = bytearray()

    def open_uart():
        return serial.Serial(UART, BAUD, timeout=0, write_timeout=5, exclusive=True)

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
        persist_owner(owner, initial=True)
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
                        action = request.get("action")
                        if action == "pause":
                            if port is not None:
                                port.close()
                                port = None
                            owner["paused"] = True
                            persist_owner(owner)
                        elif action == "resume":
                            if port is None:
                                port = open_uart()
                            if pending:
                                send_uart(pending)
                                pending.clear()
                            owner["paused"] = False
                            persist_owner(owner)
                        elif action == "mark-flashed":
                            # Mark before the first mutation so failures still trigger reset hold.
                            owner["touched"] = True
                            persist_owner(owner)
                        else:
                            raise ValueError("unsupported bridge action")
                        reply.update(ok=True, action=action, paused=owner["paused"], touched=owner["touched"])
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
        try:
            if port is not None:
                port.close()
            if owner["touched"]:
                reset_hold_and_observe(serial)
        finally:
            try:
                if controller is not None:
                    controller.close()
                    socket_path.unlink(missing_ok=True)
                if own_owner_file:
                    try:
                        current = json.loads(OWNER.read_text(encoding="utf-8"))
                        if current.get("token") == token:
                            OWNER.unlink()
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

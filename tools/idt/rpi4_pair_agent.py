#!/usr/bin/env python3
"""Per-pipeline local rendezvous; no daemon or private payload on disk."""
from __future__ import annotations

import argparse
import errno
import os
from pathlib import Path
import queue
import re
import shutil
import socket
import stat
import sys
import threading
import time

try:
    from .rpi4_pair import read_frame, write_frame
except ImportError:
    from rpi4_pair import read_frame, write_frame


def session_path(pipeline):
    if not re.fullmatch(r"[0-9]{1,20}", pipeline):
        raise ValueError("invalid pipeline identity")
    return Path.home() / ".cache" / "idt-rx72n-pair" / pipeline


def check_session(path):
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or path.is_symlink()):
        raise ValueError("paired session is not private to this user")


def prepare(pipeline):
    path = session_path(pipeline)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    check_session(path.parent)
    path.mkdir(mode=0o700, exist_ok=False)
    os.mkfifo(path / "ready", 0o600)
    for name in ("rpi4_pair.py", "rpi4_pair_agent.py"):
        destination = path / name
        shutil.copyfile(Path(__file__).with_name(name), destination)
        destination.chmod(0o600)


def wait_ready(pipeline, seconds):
    path = session_path(pipeline)
    check_session(path)
    result = queue.Queue(maxsize=1)

    def wait():
        try:
            with (path / "ready").open("rb", buffering=0) as fifo:
                result.put(fifo.read(1))
        except OSError:
            result.put(b"")

    threading.Thread(target=wait, daemon=True).start()
    try:
        if result.get(timeout=seconds) != b"R":
            raise RuntimeError("paired build worker failed readiness")
    except queue.Empty:
        raise RuntimeError("paired build worker did not become ready") from None


def attach(pipeline, input_stream, output_stream):
    path = session_path(pipeline)
    check_session(path)
    endpoint = path / "build.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(endpoint))
        endpoint.chmod(0o600)
        server.listen(1)
        server.settimeout(10800)
        try:
            deadline = time.monotonic() + 120
            while True:
                try:
                    descriptor = os.open(path / "ready", os.O_WRONLY | os.O_NONBLOCK)
                    break
                except OSError as error:
                    if error.errno != errno.ENXIO or time.monotonic() >= deadline:
                        raise RuntimeError("paired controller did not accept readiness") from None
                    time.sleep(0.1)
            with os.fdopen(descriptor, "wb", buffering=0) as fifo:
                fifo.write(b"R")
            while True:
                connection, _ = server.accept()
                with connection, connection.makefile("rwb", buffering=0) as client:
                    request = read_frame(client)
                    write_frame(output_stream, request)
                    result = read_frame(input_stream)
                    write_frame(client, result)
                if request == {"kind": "shutdown"}:
                    if result != {"kind": "shutdown_ack"}:
                        raise RuntimeError("paired worker did not acknowledge shutdown")
                    break
        finally:
            endpoint.unlink(missing_ok=True)


def shutdown(pipeline, seconds):
    path = session_path(pipeline)
    check_session(path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(seconds)
        connection.connect(str(path / "build.sock"))
        with connection.makefile("rwb", buffering=0) as stream:
            write_frame(stream, {"kind": "shutdown"})
            if read_frame(stream) != {"kind": "shutdown_ack"}:
                raise RuntimeError("paired worker did not acknowledge shutdown")


def cleanup(pipeline):
    path = session_path(pipeline)
    check_session(path)
    expected = {"ready", "rpi4_pair.py", "rpi4_pair_agent.py"}
    if {entry.name for entry in path.iterdir()} != expected:
        raise RuntimeError("paired session has active or unexpected files")
    for name in expected:
        entry = path / name
        if entry.is_symlink():
            raise RuntimeError("paired session contains a link")
        entry.unlink()
    path.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "attach", "wait-ready", "shutdown", "cleanup"))
    parser.add_argument("pipeline")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")
    if args.action == "prepare":
        prepare(args.pipeline)
    elif args.action == "attach":
        attach(args.pipeline, sys.stdin.buffer, sys.stdout.buffer)
    elif args.action == "wait-ready":
        wait_ready(args.pipeline, args.seconds)
    elif args.action == "shutdown":
        shutdown(args.pipeline, args.seconds)
    else:
        cleanup(args.pipeline)


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        print("Paired build agent failed: " + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(1) from None

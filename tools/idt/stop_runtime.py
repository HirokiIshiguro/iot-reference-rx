#!/usr/bin/env python3
"""Signal only the Linux IDT supervisor with this exact source/output pair."""
import argparse
import json
import os
from pathlib import Path
import signal


def is_owned(args, source, runtime):
    if len(args) < 4 or Path(args[1]).resolve() != source / "tools/idt/run_transport.py":
        return False
    for flag, value in (("--source-path", str(source)), ("--output", str(runtime))):
        if args.count(flag) != 1:
            return False
        index = args.index(flag)
        if index + 1 >= len(args) or Path(args[index + 1]).resolve() != Path(value):
            return False
    return True


def stop_owned(source, runtime):
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RuntimeError("The IDT WSL host must support pidfd signals")
    count = 0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal() or int(entry.name) == os.getpid():
            continue
        descriptor = None
        try:
            # Open a process handle before inspection; a recycled PID must
            # never redirect the signal to another process.
            descriptor = os.pidfd_open(int(entry.name))
            args = [part.decode("utf-8") for part in (entry / "cmdline").read_bytes().split(b"\0") if part]
            if is_owned(args, source, runtime):
                signal.pidfd_send_signal(descriptor, signal.SIGINT)
                count += 1
        except (ProcessLookupError, FileNotFoundError, PermissionError, UnicodeError):
            pass
        finally:
            if descriptor is not None:
                os.close(descriptor)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    options = parser.parse_args()
    print(json.dumps({"signaled": stop_owned(options.source.resolve(), options.runtime.resolve())}))

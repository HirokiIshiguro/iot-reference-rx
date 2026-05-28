#!/usr/bin/env python3
"""Monitor RX72N UART logs for LAN throughput benchmark results."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

import serial


SUCCESS_TOKEN = "[LANBENCH] PASS"
FAIL_TOKENS = (
    "[LANBENCH] FAIL",
    "TCP SINK connect failed",
    "TCP SOURCE connect failed",
    "TLS SINK connect failed",
    "TLS SOURCE connect failed",
    "TLS connect status=",
    "ERROR: stack overflow",
    "ERROR: Malloc failed",
    "payload failed",
    "command failed",
    "missing result",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--reset-cmd", help="External reset command to run after opening UART")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deadline = time.time() + args.timeout
    log_bytes = bytearray()

    with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=5.0) as ser:
        ser.reset_input_buffer()
        if args.reset_cmd:
            print(f"[LANBENCH-MONITOR] reset: {args.reset_cmd}", flush=True)
            reset = subprocess.run(
                args.reset_cmd,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if reset.stdout.strip():
                print(reset.stdout.strip(), flush=True)
            if reset.stderr.strip():
                print(reset.stderr.strip(), flush=True)
            if reset.returncode != 0:
                print(f"[LANBENCH-MONITOR] reset failed: {reset.returncode}")
                return 1

        while time.time() < deadline:
            chunk = ser.read(1024)
            if not chunk:
                continue

            log_bytes.extend(chunk)
            text = log_bytes.decode("utf-8", errors="replace")
            print(chunk.decode("utf-8", errors="replace"), end="", flush=True)

            for token in FAIL_TOKENS:
                if token in text:
                    args.log.parent.mkdir(parents=True, exist_ok=True)
                    args.log.write_bytes(bytes(log_bytes))
                    print(f"\n[LANBENCH-MONITOR] failure token observed: {token}")
                    return 1

            if SUCCESS_TOKEN in text:
                args.log.parent.mkdir(parents=True, exist_ok=True)
                args.log.write_bytes(bytes(log_bytes))
                print("\n[LANBENCH-MONITOR] PASS")
                return 0

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_bytes(bytes(log_bytes))
    print("\n[LANBENCH-MONITOR] timeout")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

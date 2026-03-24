#!/usr/bin/env python3
"""
Monitor RX72N UART ports while an external reset/flash command runs.

This helper is intended for local bring-up on Windows where one-shot boot
messages may be missed if the serial port is opened only after `rfp-cli`
returns. It opens the serial ports first, keeps them open while the external
command runs, and records any UART lines observed before and after the reset.
"""

import argparse
import subprocess
import sys
import threading
import time

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor RX72N UART ports during reset/flash")
    parser.add_argument(
        "--ports",
        nargs="+",
        default=["COM6", "COM7"],
        help="Ports to monitor (default: COM6 COM7)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=921600,
        help="Baud rate for all monitored ports (default: 921600)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Observation timeout in seconds after command starts (default: 20)",
    )
    parser.add_argument(
        "--pre-delay",
        type=float,
        default=0.5,
        help="Delay after ports open and before command starts (default: 0.5)",
    )
    parser.add_argument(
        "--command",
        required=True,
        help="External command to run while ports are open",
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        help="Optional expected substring; may be specified multiple times",
    )
    return parser.parse_args()


class PortMonitor:
    def __init__(self, port: str, baud: int):
        self.port_name = port
        self.baud = baud
        self.ser = None
        self.lines = []
        self.raw_bytes = 0
        self.error = None
        self._stop = threading.Event()
        self._thread = None
        self._buffer = b""

    def open(self):
        self.ser = serial.Serial(
            port=self.port_name,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        self.ser.reset_input_buffer()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        try:
            while not self._stop.is_set():
                chunk = self.ser.read(self.ser.in_waiting or 1)
                if not chunk:
                    continue
                self.raw_bytes += len(chunk)
                self._buffer += chunk
                while b"\n" in self._buffer:
                    line, self._buffer = self._buffer.split(b"\n", 1)
                    text = line.decode("ascii", errors="replace").strip("\r")
                    if text:
                        self.lines.append(text)
                        print(f"[UART:{self.port_name}] {text}")
        except Exception as exc:  # pragma: no cover - best effort diagnostics
            self.error = str(exc)

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self.ser and self.ser.is_open:
            self.ser.close()


def main():
    args = parse_args()
    monitors = []

    print("=" * 60)
    print("RX72N Boot Monitor")
    print("=" * 60)
    print(f"Ports:    {', '.join(args.ports)}")
    print(f"Baud:     {args.baud}")
    print(f"Timeout:  {args.timeout}s")
    print(f"Command:  {args.command}")
    if args.expect:
        print(f"Expect:   {args.expect}")
    print("=" * 60)

    try:
        for port in args.ports:
            mon = PortMonitor(port, args.baud)
            mon.open()
            monitors.append(mon)
            print(f"Opened {port}")

        if args.pre_delay > 0:
            time.sleep(args.pre_delay)

        print("Running external command...")
        start = time.time()
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", args.command],
            capture_output=True,
            text=True,
        )
        elapsed = time.time() - start
        print(f"Command exit: {result.returncode} ({elapsed:.1f}s)")
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                print(f"[CMD] {line}")
        if result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                print(f"[CMD:ERR] {line}")

        print(f"Observing UART for {args.timeout}s...")
        time.sleep(args.timeout)
    finally:
        for mon in monitors:
            mon.close()

    print("")
    print("=" * 60)
    print("Monitor Summary")
    success = False
    for mon in monitors:
        matched = []
        for token in args.expect:
            if any(token in line for line in mon.lines):
                matched.append(token)
        if args.expect and len(matched) == len(args.expect):
            success = True
        print(f"{mon.port_name}: raw_bytes={mon.raw_bytes}, lines={len(mon.lines)}, matched={matched}")
        if mon.error:
            print(f"  error: {mon.error}")
        for line in mon.lines[:20]:
            print(f"  > {line}")
    print("=" * 60)

    if args.expect and not success:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

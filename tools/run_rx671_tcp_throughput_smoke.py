#!/usr/bin/env python3
"""Run the EK-RX671 TCP throughput smoke test from a Windows host.

The target firmware connects to the host twice:

1. sink:   RX671 sends bytes to the host.
2. source: host sends bytes to the RX671.

This helper opens COM5 before releasing reset so boot and throughput logs are
not missed, starts the TCP peer, programs the MOT through rfp-cli, and captures
all serial output into a timestamped log.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import socket
import subprocess
import sys
import threading
import time

try:
    import serial
except ImportError as exc:  # pragma: no cover - host setup guard
    raise SystemExit("pyserial is required: python -m pip install pyserial") from exc


DEFAULT_RFP = (
    r"C:\Program Files (x86)\Renesas Electronics\Programming Tools"
    r"\Renesas Flash Programmer V3.22\rfp-cli.exe"
)


class SerialCapture:
    def __init__(self, port: str, baud: int, output: pathlib.Path) -> None:
        self._port = port
        self._baud = baud
        self._output = output
        self._stop = threading.Event()
        self.failed = threading.Event()
        self._thread = threading.Thread(target=self._run, name="serial-capture")
        self.lines: list[str] = []

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        self._output.parent.mkdir(parents=True, exist_ok=True)
        with serial.Serial(self._port, self._baud, timeout=0.1) as ser, self._output.open(
            "w", encoding="utf-8", errors="replace"
        ) as fp:
            fp.write(f"# serial {self._port} {self._baud} opened {_dt.datetime.now().isoformat()}\n")
            fp.flush()
            pending = bytearray()
            while not self._stop.is_set():
                chunk = ser.read(4096)
                if not chunk:
                    continue
                pending.extend(chunk)
                while b"\n" in pending:
                    raw, _, pending = pending.partition(b"\n")
                    line = raw.decode("utf-8", errors="replace").rstrip("\r")
                    self.lines.append(line)
                    if self._is_failure_line(line):
                        self.failed.set()
                    print(line, flush=True)
                    fp.write(line + "\n")
                    fp.flush()
            if pending:
                line = pending.decode("utf-8", errors="replace").rstrip("\r")
                self.lines.append(line)
                if self._is_failure_line(line):
                    self.failed.set()
                print(line, flush=True)
                fp.write(line + "\n")

    @staticmethod
    def _is_failure_line(line: str) -> bool:
        if "Could not turn on APSTA" in line:
            return True
        if "WHD bring-up failed" in line:
            return True
        if line.startswith("whd_wifi_on=") and not line.endswith("=00000000"):
            return True
        return False


class TcpPeer:
    def __init__(self, bind: str, port: int, sink_bytes: int, source_bytes: int, chunk: int) -> None:
        self._bind = bind
        self._port = port
        self._sink_bytes = sink_bytes
        self._source_bytes = source_bytes
        self._chunk = chunk
        self._ready = threading.Event()
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, name="tcp-peer", daemon=True)
        self.sink_bytes = 0
        self.source_bytes = 0
        self.error: BaseException | None = None

    def start(self) -> None:
        self._thread.start()
        if not self._ready.wait(timeout=10.0):
            raise TimeoutError("TCP peer did not start listening")

    def wait(self, timeout: float) -> None:
        self._done.wait(timeout=timeout)
        if self._thread.is_alive():
            raise TimeoutError("TCP peer timed out")
        if self.error is not None:
            raise self.error

    def _accept_one(self, server: socket.socket) -> socket.socket:
        conn, addr = server.accept()
        print(f"[HOST] accepted {addr[0]}:{addr[1]}", flush=True)
        conn.settimeout(10.0)
        return conn

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self._bind, self._port))
                server.listen(2)
                self._ready.set()
                print(f"[HOST] listening {self._bind}:{self._port}", flush=True)

                with self._accept_one(server) as conn:
                    start = time.monotonic()
                    while self.sink_bytes < self._sink_bytes:
                        data = conn.recv(65536)
                        if not data:
                            break
                        self.sink_bytes += len(data)
                elapsed = max(time.monotonic() - start, 0.001)
                print(
                    f"[HOST] sink bytes={self.sink_bytes} Mbps={self.sink_bytes * 8 / elapsed / 1_000_000:.3f}",
                    flush=True,
                )

                payload = bytes([0x5A]) * self._chunk
                remaining = self._source_bytes
                with self._accept_one(server) as conn:
                    start = time.monotonic()
                    while remaining > 0:
                        n = min(remaining, len(payload))
                        conn.sendall(payload[:n])
                        remaining -= n
                        self.source_bytes += n
                elapsed = max(time.monotonic() - start, 0.001)
                print(
                    f"[HOST] source bytes={self.source_bytes} Mbps={self.source_bytes * 8 / elapsed / 1_000_000:.3f}",
                    flush=True,
                )
        except BaseException as exc:  # pragma: no cover - diagnostic path
            self.error = exc
        finally:
            self._done.set()


def run_rfp(args: argparse.Namespace) -> None:
    cmd = [
        args.rfp_cli,
        "-d",
        "RX671",
        "-t",
        f"e2l:{args.e2_serial}",
        "-if",
        "fine",
        "-s",
        args.speed,
        "-auth",
        "id",
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        "-p",
        str(args.mot),
        "-v",
        "-run",
        "-noquery",
    ]
    print("[HOST] rfp-cli program+run", flush=True)
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mot", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, default=None)
    parser.add_argument("--rfp-cli", default=DEFAULT_RFP)
    parser.add_argument("--e2-serial", default="OBE110024")
    parser.add_argument("--speed", default="1500K")
    parser.add_argument("--serial-port", default="COM5")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--tcp-port", type=int, default=5004)
    parser.add_argument("--sink-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--source-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--source-chunk", type=int, default=5840)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output is None:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = pathlib.Path("logs") / f"rx671-tcp-throughput-{stamp}.log"

    tcp_peer = TcpPeer(args.bind, args.tcp_port, args.sink_bytes, args.source_bytes, args.source_chunk)
    serial_capture = SerialCapture(args.serial_port, args.baud, args.output)

    tcp_peer.start()
    serial_capture.start()
    try:
        time.sleep(0.3)
        run_rfp(args)
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if serial_capture.failed.is_set():
                raise RuntimeError("target reported Wi-Fi bring-up failure")
            try:
                tcp_peer.wait(0.5)
                break
            except TimeoutError:
                continue
        else:
            raise TimeoutError("TCP peer timed out")

        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if any("[TCPTHR] done" in line for line in serial_capture.lines):
                break
            time.sleep(0.2)
    finally:
        serial_capture.stop()

    print(f"[HOST] serial log: {args.output}", flush=True)
    print(f"[HOST] sink_bytes={tcp_peer.sink_bytes} source_bytes={tcp_peer.source_bytes}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

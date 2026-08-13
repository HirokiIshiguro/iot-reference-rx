#!/usr/bin/env python3
"""Shared host-side primitives for the EK-RX671 OTA hardware transaction.

The helpers in this module deliberately keep RFP programming, serial capture,
result artifacts, and deletion of short-lived plaintext artifacts explicit.
They do not know any credential values and never print command payloads.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence


DEFAULT_PORT = os.environ.get(
    "RX671_WIFI_UART_PORT",
    "/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DK0EOSDX-if00-port0",
)
DEFAULT_BAUD = 921600
DEFAULT_RFP_CLI = os.environ.get("RX671_WIFI_LINUX_RFP_CLI", "./tools/rfp_cli_locked.sh")
DEFAULT_RFP_TIMEOUT = 120.0
DEFAULT_UART_BUFFER_LIMIT = 16 * 1024 * 1024
RX671_TEMPORARY_INSTALL_START = 0xFFE00000
RX671_TEMPORARY_INSTALL_END = 0xFFEBFFFF
RX671_EXECUTE_INSTALL_START = 0xFFF00000
RX671_EXECUTE_INSTALL_END = 0xFFFBFFFF
CLI_INPUT_BUFFER_BYTES = 4096
CLI_PROMPT_TOKENS = (b"\r\n>", b"\n>")
CLI_SET_SUCCESS_TOKENS = (
    b"\r\nOK.\r\n\r\n>",
    b"\nOK.\r\n\r\n>",
)


@dataclass(frozen=True)
class RfpConfig:
    executable: str = DEFAULT_RFP_CLI
    device: str = "RX671"
    tool: str = "e2l:OBE110024"
    interface: str = "fine"
    speed: str = "500K"
    auth_id: str = "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"

    def common_command(self) -> list[str]:
        return [
            self.executable,
            "-d",
            self.device,
            "-t",
            self.tool,
            "-if",
            self.interface,
            "-s",
            self.speed,
            "-auth",
            "id",
            self.auth_id,
        ]

    def program_command(self, mot: Path, *, leave_reset: bool) -> list[str]:
        """Program only records present in *mot*; never issue chip erase."""
        command = self.common_command()
        command.extend(["-p", "-v"])
        # RFP -reset/-run both release the target.  Omitting both is the
        # established Linux-runner path for holding the MCU after programming.
        if not leave_reset:
            command.append("-run")
        command.extend(["-noquery", str(mot)])
        if "-erase-chip" in command:
            raise AssertionError("RX671 OTA programming must preserve Data Flash")
        return command

    def erase_ota_install_areas_command(self) -> list[str]:
        """Erase both RX671 OTA install areas while preserving both boot loaders."""
        command = self.common_command()
        command.extend(
            [
                "-range",
                f"{RX671_TEMPORARY_INSTALL_START:08X},"
                f"{RX671_TEMPORARY_INSTALL_END:08X}",
                "-range",
                f"{RX671_EXECUTE_INSTALL_START:08X},"
                f"{RX671_EXECUTE_INSTALL_END:08X}",
                "-erase",
                "-noquery",
            ]
        )
        if "-erase-chip" in command:
            raise AssertionError("RX671 OTA handoff must preserve non-install areas")
        return command

    def run_command(self) -> list[str]:
        command = self.common_command()
        command.extend(["-sig", "-run", "-noquery"])
        return command


class BufferedSerialReader:
    """Continuously drain a serial port into a bounded host-side buffer.

    RX671 OTA emits UART at 921600 bps.  The transaction consumer also formats
    timestamped logs and analyzes every line, so a filesystem or scheduler
    stall in that consumer must not stop the kernel tty buffer from being
    drained.  The generous buffer absorbs transient consumer stalls; reaching
    its limit is an explicit integrity failure rather than a silent drop.  Only
    this reader thread touches ``serial.read``; writes remain full-duplex and
    are delegated to the wrapped pyserial object.
    """

    def __init__(
        self,
        serial_port,
        *,
        stop_timeout: float = 5.0,
        max_buffer_bytes: int = DEFAULT_UART_BUFFER_LIMIT,
    ):
        if stop_timeout <= 0:
            raise ValueError("serial reader stop timeout must be positive")
        if max_buffer_bytes <= 0:
            raise ValueError("serial reader buffer limit must be positive")
        self._serial = serial_port
        self._stop_timeout = stop_timeout
        self._max_buffer_bytes = max_buffer_bytes
        self._condition = threading.Condition()
        self._io_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="rx671-uart-reader",
            daemon=True,
        )
        self._started = False
        self._closed = False
        self._chunks = deque()
        self._buffered_bytes = 0
        self._reader_error: Exception | None = None
        self._reader_bytes = 0
        self._reader_chunks = 0
        self._consumer_bytes = 0
        self._consumer_reads = 0
        self._max_buffered_bytes = 0
        self._input_resets = 0
        self._discarded_buffered_bytes = 0
        self._overflow_bytes = 0
        self._max_service_gap_seconds = 0.0
        self._last_capture_wall = None
        self._last_capture_elapsed_seconds = None
        self._capture_cutoff_wall = None
        self._capture_cutoff_elapsed_seconds = None
        self._physical_pending_at_cutoff = 0
        self._physical_final_drain_bytes = 0

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("cannot start a closed serial reader")
        if self._started:
            raise RuntimeError("serial reader already started")
        self._started = True
        self._thread.start()

    def _run(self) -> None:
        previous_service = time.monotonic()
        try:
            while not self._stop.is_set():
                service_started = time.monotonic()
                service_gap = service_started - previous_service
                previous_service = service_started
                with self._condition:
                    self._max_service_gap_seconds = max(
                        self._max_service_gap_seconds,
                        service_gap,
                    )
                # Keep the append inside the same lock as the physical read.
                # reset_input_buffer() can then atomically discard both the
                # kernel-side bytes and every pre-reset byte already read.
                with self._io_lock:
                    waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
                    chunk = self._serial.read(waiting or 1)
                    if chunk:
                        self._append_reader_chunk(
                            chunk,
                            capture_wall=datetime.now(timezone.utc).isoformat(),
                            capture_elapsed=time.monotonic(),
                        )
        except Exception as exc:  # propagate hardware/driver failures
            with self._condition:
                self._reader_error = exc
                self._condition.notify_all()

    def _raise_reader_error_locked(self) -> None:
        if self._reader_error is not None:
            raise RuntimeError("RX671 UART reader failed") from self._reader_error

    def _append_reader_chunk(
        self,
        chunk: bytes,
        *,
        capture_wall: str,
        capture_elapsed: float,
        physical_final_drain: bool = False,
    ) -> None:
        with self._condition:
            self._reader_bytes += len(chunk)
            self._reader_chunks += 1
            if physical_final_drain:
                self._physical_final_drain_bytes += len(chunk)
            if self._buffered_bytes + len(chunk) > self._max_buffer_bytes:
                self._overflow_bytes += len(chunk)
                raise BufferError(
                    "RX671 UART host buffer limit exceeded: "
                    f"{self._buffered_bytes + len(chunk)}/"
                    f"{self._max_buffer_bytes} bytes"
                )
            self._chunks.append(bytes(chunk))
            self._buffered_bytes += len(chunk)
            self._max_buffered_bytes = max(
                self._max_buffered_bytes,
                self._buffered_bytes,
            )
            self._last_capture_wall = capture_wall
            self._last_capture_elapsed_seconds = round(capture_elapsed, 6)
            self._condition.notify_all()

    @property
    def in_waiting(self) -> int:
        with self._condition:
            self._raise_reader_error_locked()
            return self._buffered_bytes

    def read(self, size: int = 1) -> bytes:
        if size <= 0:
            return b""
        timeout = getattr(self._serial, "timeout", 0.1)
        deadline = None if timeout is None else time.monotonic() + float(timeout)
        with self._condition:
            while not self._chunks:
                self._raise_reader_error_locked()
                if self._stop.is_set():
                    return b""
                if deadline is None:
                    self._condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return b""
                self._condition.wait(remaining)

            take = min(size, self._buffered_bytes)
            pieces = []
            remaining = take
            while remaining:
                head = self._chunks[0]
                if len(head) <= remaining:
                    pieces.append(self._chunks.popleft())
                    remaining -= len(head)
                else:
                    pieces.append(head[:remaining])
                    self._chunks[0] = head[remaining:]
                    remaining = 0
            chunk = b"".join(pieces)
            self._buffered_bytes -= len(chunk)
            self._consumer_bytes += len(chunk)
            self._consumer_reads += 1
            return chunk

    def write(self, payload: bytes) -> int:
        return self._serial.write(payload)

    def flush(self) -> None:
        self._serial.flush()

    def reset_input_buffer(self) -> None:
        # _run() also appends while holding _io_lock, so no pre-reset chunk can
        # be appended after this queue clear.
        with self._io_lock:
            self._serial.reset_input_buffer()
            with self._condition:
                self._raise_reader_error_locked()
                self._discarded_buffered_bytes += self._buffered_bytes
                self._chunks.clear()
                self._buffered_bytes = 0
                self._input_resets += 1

    def reset_output_buffer(self) -> None:
        self._serial.reset_output_buffer()

    def stats(self) -> dict:
        with self._condition:
            accounted_bytes = (
                self._consumer_bytes
                + self._discarded_buffered_bytes
                + self._buffered_bytes
                + self._overflow_bytes
            )
            return {
                "mode": "dedicated_reader_thread",
                "reader_thread_started": self._started,
                "reader_thread_stopped": self._started and not self._thread.is_alive(),
                "reader_failed": self._reader_error is not None,
                "buffer_limit_bytes": self._max_buffer_bytes,
                "buffer_overflowed": self._overflow_bytes > 0,
                "overflow_bytes": self._overflow_bytes,
                "reader_bytes": self._reader_bytes,
                "reader_chunks": self._reader_chunks,
                "consumer_bytes": self._consumer_bytes,
                "consumer_reads": self._consumer_reads,
                "max_buffered_bytes": self._max_buffered_bytes,
                "buffered_bytes": self._buffered_bytes,
                "input_resets": self._input_resets,
                "discarded_buffered_bytes": self._discarded_buffered_bytes,
                "accounted_reader_bytes": accounted_bytes,
                "all_reader_bytes_accounted": accounted_bytes == self._reader_bytes,
                "max_reader_service_gap_seconds": round(
                    self._max_service_gap_seconds,
                    6,
                ),
                "last_capture_wall_utc": self._last_capture_wall,
                "last_capture_monotonic_seconds": self._last_capture_elapsed_seconds,
                "capture_cutoff_wall_utc": self._capture_cutoff_wall,
                "capture_cutoff_monotonic_seconds": (
                    self._capture_cutoff_elapsed_seconds
                ),
                "physical_pending_at_cutoff": self._physical_pending_at_cutoff,
                "physical_final_drain_bytes": self._physical_final_drain_bytes,
            }

    def stop(self) -> None:
        if not self._started:
            return
        with self._condition:
            self._raise_reader_error_locked()
            if self._capture_cutoff_wall is not None:
                return
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        self._thread.join(self._stop_timeout)
        if self._thread.is_alive():
            raise RuntimeError("RX671 UART reader did not stop")

        # The thread can observe the stop event immediately after its last
        # physical read.  Bytes may reach the tty in that narrow interval.  A
        # single fixed-size snapshot defines the capture cutoff and prevents
        # those pre-cutoff bytes from being silently lost.  Do not loop until
        # quiet: the successful application intentionally logs continuously.
        try:
            with self._io_lock:
                cutoff_wall = datetime.now(timezone.utc).isoformat()
                cutoff_elapsed = time.monotonic()
                physical_waiting = int(
                    getattr(self._serial, "in_waiting", 0) or 0
                )
                if physical_waiting < 0:
                    raise IOError(
                        "RX671 UART reported a negative physical byte count"
                    )
                with self._condition:
                    self._capture_cutoff_wall = cutoff_wall
                    self._capture_cutoff_elapsed_seconds = round(
                        cutoff_elapsed,
                        6,
                    )
                    self._physical_pending_at_cutoff = physical_waiting
                final_chunk = (
                    self._serial.read(physical_waiting)
                    if physical_waiting
                    else b""
                )
                if final_chunk:
                    self._append_reader_chunk(
                        final_chunk,
                        capture_wall=cutoff_wall,
                        capture_elapsed=cutoff_elapsed,
                        physical_final_drain=True,
                    )
                if len(final_chunk) != physical_waiting:
                    raise IOError(
                        "RX671 UART final physical drain was short: "
                        f"{len(final_chunk)}/{physical_waiting} bytes"
                    )
        except Exception as exc:
            with self._condition:
                if self._reader_error is None:
                    self._reader_error = exc
                self._condition.notify_all()
        with self._condition:
            self._raise_reader_error_locked()

    def stop_after_quiet(self, quiet_seconds: float = 0.2) -> None:
        """Stop after the physical port and host buffer stay quiet.

        The OTA consumer can decide success immediately after a marker while a
        final UART chunk is still moving through USB.  Wait for a bounded quiet
        interval before stopping the only physical reader, then let the caller
        drain every queued byte.
        """
        if quiet_seconds <= 0:
            raise ValueError("serial reader quiet interval must be positive")
        stable_since = None
        previous_reader_bytes = None
        deadline = time.monotonic() + max(quiet_seconds * 10, 5.0)
        while time.monotonic() < deadline:
            with self._condition:
                self._raise_reader_error_locked()
                current_reader_bytes = self._reader_bytes
            with self._io_lock:
                physical_waiting = int(
                    getattr(self._serial, "in_waiting", 0) or 0
                )
            now = time.monotonic()
            if (
                physical_waiting == 0
                and current_reader_bytes == previous_reader_bytes
            ):
                if stable_since is None:
                    stable_since = now
                elif now - stable_since >= quiet_seconds:
                    self.stop()
                    return
            else:
                stable_since = None
            previous_reader_bytes = current_reader_bytes
            time.sleep(min(quiet_seconds / 4, 0.05))
        raise TimeoutError("RX671 UART reader did not become quiet before shutdown")

    def close(self) -> None:
        if self._closed:
            return
        stop_error = None
        try:
            self.stop()
        except Exception as exc:
            stop_error = exc
        finally:
            self._serial.close()
            self._closed = True
        if stop_error is not None:
            raise stop_error


class TimestampLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.path.write_text("", encoding="utf-8")
        self._at_line_start = True

    def write(self, payload: str) -> None:
        """Append text without creating line breaks at host read boundaries."""
        if not payload:
            return
        wall = datetime.now(timezone.utc).isoformat()
        elapsed = time.monotonic() - self.started
        prefix = f"[{wall}][+{elapsed:09.3f}s] "
        offset = 0
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            while offset < len(payload):
                if self._at_line_start:
                    handle.write(prefix)
                    self._at_line_start = False
                newline = payload.find("\n", offset)
                if newline < 0:
                    handle.write(payload[offset:])
                    break
                handle.write(payload[offset : newline + 1])
                self._at_line_start = True
                offset = newline + 1


def run_checked(
    command: Sequence[str],
    *,
    label: str,
    timeout: float = DEFAULT_RFP_TIMEOUT,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Run an argv command without echoing the argv (which contains auth data)."""
    if timeout <= 0:
        raise ValueError("command timeout must be positive")
    try:
        result = runner(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # TimeoutExpired includes the argv in its string representation.  Do
        # not chain or interpolate it because RFP argv contains the auth ID.
        raise TimeoutError(
            f"{label} timed out after {timeout:g} seconds"
        ) from None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        command_parts = list(command)
        try:
            auth_index = command_parts.index("-auth")
        except ValueError:
            auth_index = -1
        if (
            auth_index >= 0
            and len(command_parts) > auth_index + 2
            and command_parts[auth_index + 1] == "id"
            and command_parts[auth_index + 2]
        ):
            detail = detail.replace(
                command_parts[auth_index + 2],
                "<redacted-auth-id>",
            )
        raise RuntimeError(f"{label} failed with exit status {result.returncode}: {detail}")
    return result


def open_serial(port: str, baud: int):
    try:
        import serial
    except ImportError as exc:  # pragma: no cover - depends on runner image
        raise RuntimeError("pyserial is required") from exc
    return serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
        write_timeout=10,
        rtscts=False,
    )


def read_until(
    serial_port,
    *,
    success_tokens: Iterable[bytes],
    error_tokens: Iterable[bytes] = (),
    timeout: float,
    on_data: Callable[[bytes], None] | None = None,
) -> bytes:
    success = tuple(success_tokens)
    errors = tuple(error_tokens)
    collected = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waiting = getattr(serial_port, "in_waiting", 0)
        chunk = serial_port.read(waiting or 1)
        if chunk:
            collected.extend(chunk)
            if on_data is not None:
                on_data(chunk)
            snapshot = bytes(collected)
            if any(token in snapshot for token in errors):
                raise RuntimeError("target reported an error while waiting for a marker")
            if any(token in snapshot for token in success):
                return snapshot
        else:
            time.sleep(0.01)
    # Tokens can intentionally be credential values during a silent `conf get`
    # check, so never put their contents into an exception or CI log.
    raise TimeoutError(f"timed out waiting for {len(success)} target marker(s)")


def send_ascii_command(
    serial_port,
    command: str,
    *,
    timeout: float,
    char_delay: float,
    success_tokens: Iterable[bytes] = CLI_SET_SUCCESS_TOKENS,
) -> bytes:
    """Send a command character-by-character; callers must not log *command*."""
    try:
        encoded_command = command.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("CLI command must contain ASCII only") from None
    return send_ascii_bytes_command(
        serial_port,
        encoded_command,
        timeout=timeout,
        char_delay=char_delay,
        success_tokens=success_tokens,
    )


def send_ascii_bytes_command(
    serial_port,
    command: bytes | bytearray,
    *,
    timeout: float,
    char_delay: float,
    success_tokens: Iterable[bytes] = CLI_SET_SUCCESS_TOKENS,
) -> bytes:
    """Send mutable ASCII command bytes without logging or string conversion."""
    if any(byte > 0x7F for byte in command):
        raise ValueError("CLI command must contain ASCII only")
    if len(command) >= CLI_INPUT_BUFFER_BYTES:
        raise ValueError(
            "CLI command is too long for the target input buffer: "
            f"{len(command)}/{CLI_INPUT_BUFFER_BYTES} bytes"
        )
    serial_port.reset_input_buffer()
    for byte in command:
        serial_port.write(bytes((byte,)))
        if char_delay:
            time.sleep(char_delay)
    serial_port.write(b"\r\n")
    serial_port.flush()
    return read_until(
        serial_port,
        success_tokens=success_tokens,
        # Do not scan for a generic "NG": echoed PEM/base64 can contain it.
        error_tokens=(b"\r\nError", b"\nError", b"Error.", b"Format NG", b"\r\nNG\r\n"),
        timeout=timeout,
    )


def stream_file(
    serial_port,
    path: Path,
    *,
    chunk_size: int,
    inter_chunk_delay: float,
    timeout: float,
) -> tuple[int, str]:
    expected_size = path.stat().st_size
    sent = 0
    digest = hashlib.sha256()
    deadline = time.monotonic() + timeout
    with path.open("rb") as source:
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out after sending {sent}/{expected_size} bytes")
            written = serial_port.write(chunk)
            if written != len(chunk):
                raise IOError(f"short UART write: {written}/{len(chunk)} bytes")
            digest.update(chunk)
            sent += written
            if inter_chunk_delay:
                time.sleep(inter_chunk_delay)
    serial_port.flush()
    if sent != expected_size:
        raise IOError(f"RSU transfer size mismatch: {sent}/{expected_size}")
    return sent, digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_junit(path: Path, *, name: str, success: bool, message: str, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suite = ET.Element(
        "testsuite",
        name=name,
        tests="1",
        failures="0" if success else "1",
        time=f"{seconds:.3f}",
    )
    case = ET.SubElement(suite, "testcase", classname="rx671.ota", name=name, time=f"{seconds:.3f}")
    if not success:
        failure = ET.SubElement(case, "failure", message=message)
        failure.text = message
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def cleanup_plaintext(paths: Iterable[Path], allowed_root: Path) -> list[str]:
    """Delete regular files under an explicit root; refuse links and escapes."""
    root = allowed_root.resolve(strict=True)
    removed: list[str] = []
    for candidate in paths:
        path = candidate.absolute()
        if path.is_symlink():
            raise ValueError(f"refusing to delete symlink: {path}")
        resolved = path.resolve(strict=False)
        if resolved == root or root not in resolved.parents:
            raise ValueError(f"cleanup path is outside the allowed root: {path}")
        if resolved.exists():
            if not resolved.is_file():
                raise ValueError(f"cleanup path is not a regular file: {path}")
            resolved.unlink()
            removed.append(resolved.relative_to(root).as_posix())
    return removed

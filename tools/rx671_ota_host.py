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
import time
import xml.etree.ElementTree as ET
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

    def run_command(self) -> list[str]:
        command = self.common_command()
        command.extend(["-sig", "-run", "-noquery"])
        return command


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

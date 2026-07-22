#!/usr/bin/env python3
"""Flash the standalone EK-RX671 boot loader and verify its SCI6 banner."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path


BANNER_MARKER = "RX secure boot program"
KEY_MARKERS = {
    "found": "Loading user code signer public key from LittleFS: found.",
    "missing-fail-closed": (
        "Loading user code signer public key from LittleFS: "
        "not found; refusing to boot."
    ),
}
UNSAFE_FALLBACK_MARKER = "not found; using built-in key."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--program-timeout", type=float, default=180.0)
    parser.add_argument("--program-command", required=True)
    parser.add_argument(
        "--expected-key-state",
        choices=tuple(KEY_MARKERS),
        default="missing-fail-closed",
    )
    parser.add_argument("--output-log", required=True, type=Path)
    args = parser.parse_args()

    import serial

    captured = bytearray()
    program_text = ""
    result_message = ""
    passed = False
    try:
        with serial.Serial(args.port, args.baud, timeout=0.1, write_timeout=1.0) as uart:
            uart.reset_input_buffer()
            command = shlex.split(args.program_command)
            program = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=args.program_timeout,
                check=False,
            )
            program_text = (
                "# program command\n"
                + args.program_command
                + "\n# stdout\n"
                + program.stdout
                + "\n# stderr\n"
                + program.stderr
            )
            if program.returncode != 0:
                result_message = f"RFP programming failed with exit code {program.returncode}"
            else:
                deadline = time.monotonic() + args.timeout
                text = ""
                while time.monotonic() < deadline:
                    chunk = uart.read(4096)
                    if chunk:
                        captured.extend(chunk)
                        sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                        sys.stdout.flush()
                    text = captured.decode("utf-8", errors="replace")
                    if UNSAFE_FALLBACK_MARKER in text:
                        result_message = "unsafe built-in public-key fallback was observed"
                        break
                    markers = (BANNER_MARKER, KEY_MARKERS[args.expected_key_state])
                    if all(marker in text for marker in markers):
                        passed = True
                        result_message = (
                            "standalone boot-loader SCI6 markers observed; "
                            f"key_state={args.expected_key_state}"
                        )
                        break
                if not passed:
                    if not result_message:
                        markers = (BANNER_MARKER, KEY_MARKERS[args.expected_key_state])
                        missing = [marker for marker in markers if marker not in text]
                        result_message = "missing UART markers: " + ", ".join(missing)
    except Exception as exc:  # Hardware diagnostics belong in the artifact log.
        result_message = f"RX671 boot-loader smoke exception: {exc}"

    uart_text = captured.decode("utf-8", errors="replace")
    args.output_log.parent.mkdir(parents=True, exist_ok=True)
    args.output_log.write_text(
        program_text + "\n# UART\n" + uart_text + "\n# result\n" + result_message + "\n",
        encoding="utf-8",
    )
    print(result_message)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

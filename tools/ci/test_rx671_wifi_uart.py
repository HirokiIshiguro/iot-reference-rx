#!/usr/bin/env python3
"""Verify EK-RX671 Wi-Fi startup milestones over UART.

The UART is opened before the reset command is executed. This ordering is
required for EK-RX671 because the useful SCI6 startup messages begin
immediately after the E2OB releases reset.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


NETWORK_MARKERS = (
    "whd_wifi_join=00000000",
    "WHD bring-up done",
    "FreeRTOS+TCP network up",
)
MQTT_MARKERS = (
    "AWS MQTT smoke: network ready",
    "AWS TLS=0",
    "AWS MQTT=0",
)


@dataclass(frozen=True)
class SmokeResult:
    passed: bool
    message: str
    log: str
    duration_seconds: float


def required_markers(mode: str, require_tls_version: str = "") -> tuple[str, ...]:
    if mode == "network":
        if require_tls_version:
            raise ValueError("TLS version can only be required in mqtt mode")
        return NETWORK_MARKERS
    if mode == "mqtt":
        markers = NETWORK_MARKERS + MQTT_MARKERS
        if require_tls_version:
            if require_tls_version != "TLSv1.3":
                raise ValueError(f"unsupported TLS version: {require_tls_version}")
            markers += (f"AWS TLS version={require_tls_version}",)
        return markers
    raise ValueError(f"unsupported mode: {mode}")


def evaluate_log(
    text: str, mode: str, require_tls_version: str = ""
) -> tuple[list[str], list[str]]:
    markers = required_markers(mode, require_tls_version)
    missing = [marker for marker in markers if marker not in text]
    failures: list[str] = []

    join_match = re.search(r"whd_wifi_join=([0-9A-Fa-f]{8})", text)
    if join_match and join_match.group(1) != "00000000":
        failures.append(f"whd_wifi_join failed: {join_match.group(1)}")

    if mode == "mqtt":
        for label in ("AWS TLS", "AWS MQTT"):
            match = re.search(rf"{re.escape(label)}=(-?[0-9A-Fa-f]+)", text)
            if match and match.group(1) != "0":
                failures.append(f"{label} failed: {match.group(1)}")

    return missing, failures


def run_reset_command(command: str, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def monitor_uart(
    port: str,
    baud: int,
    timeout_seconds: float,
    mode: str,
    require_tls_version: str,
    reset_command: str,
    reset_timeout_seconds: float,
) -> SmokeResult:
    import serial

    start = time.monotonic()
    captured = bytearray()
    reset_details = ""

    try:
        with serial.Serial(
            port,
            baudrate=baud,
            timeout=0.1,
            write_timeout=1.0,
        ) as uart:
            uart.reset_input_buffer()
            print(f"Opened UART {port} at {baud} bps before reset", flush=True)

            reset = run_reset_command(reset_command, reset_timeout_seconds)
            reset_details = (
                "\n# reset command stdout\n"
                + reset.stdout
                + "\n# reset command stderr\n"
                + reset.stderr
            )
            if reset.stdout:
                print(reset.stdout, end="", flush=True)
            if reset.stderr:
                print(reset.stderr, end="", file=sys.stderr, flush=True)
            if reset.returncode != 0:
                duration = time.monotonic() - start
                return SmokeResult(
                    False,
                    f"reset command failed with exit code {reset.returncode}",
                    reset_details,
                    duration,
                )

            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                chunk = uart.read(4096)
                if chunk:
                    captured.extend(chunk)
                    sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                    sys.stdout.flush()

                text = captured.decode("utf-8", errors="replace")
                missing, failures = evaluate_log(text, mode, require_tls_version)
                if failures:
                    duration = time.monotonic() - start
                    return SmokeResult(
                        False,
                        "; ".join(failures),
                        text + reset_details,
                        duration,
                    )
                if not missing:
                    duration = time.monotonic() - start
                    return SmokeResult(
                        True,
                        f"all {mode} milestones observed",
                        text + reset_details,
                        duration,
                    )

            text = captured.decode("utf-8", errors="replace")
            missing, failures = evaluate_log(text, mode, require_tls_version)
            details = failures or ["missing: " + ", ".join(missing)]
            duration = time.monotonic() - start
            return SmokeResult(
                False,
                "; ".join(details),
                text + reset_details,
                duration,
            )
    except Exception as exc:
        duration = time.monotonic() - start
        text = captured.decode("utf-8", errors="replace") + reset_details
        return SmokeResult(False, f"UART smoke exception: {exc}", text, duration)


def write_junit(
    path: Path,
    result: SmokeResult,
    mode: str,
    port: str,
    baud: int,
    require_tls_version: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suite = ET.Element(
        "testsuite",
        {
            "name": "ek-rx671-wifi-uart",
            "tests": "1",
            "failures": "0" if result.passed else "1",
            "errors": "0",
            "time": f"{result.duration_seconds:.3f}",
        },
    )
    properties = ET.SubElement(suite, "properties")
    ET.SubElement(properties, "property", {"name": "mode", "value": mode})
    ET.SubElement(properties, "property", {"name": "port", "value": port})
    ET.SubElement(properties, "property", {"name": "baud", "value": str(baud)})
    ET.SubElement(
        properties,
        "property",
        {"name": "require_tls_version", "value": require_tls_version},
    )
    case = ET.SubElement(
        suite,
        "testcase",
        {
            "classname": "hardware.ek_rx671",
            "name": f"wifi_{mode}",
            "time": f"{result.duration_seconds:.3f}",
        },
    )
    if not result.passed:
        failure = ET.SubElement(case, "failure", {"message": result.message})
        failure.text = result.message
    system_out = ET.SubElement(case, "system-out")
    system_out.text = result.log
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--mode", choices=("network", "mqtt"), default="network")
    parser.add_argument(
        "--require-tls-version",
        choices=("TLSv1.3",),
        default="",
        help="Require the negotiated AWS IoT TLS version in mqtt mode.",
    )
    parser.add_argument("--reset-cmd", required=True)
    parser.add_argument("--reset-timeout", type=float, default=90.0)
    parser.add_argument("--output-log", type=Path, required=True)
    parser.add_argument("--junit-output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = monitor_uart(
        port=args.port,
        baud=args.baud,
        timeout_seconds=args.timeout,
        mode=args.mode,
        require_tls_version=args.require_tls_version,
        reset_command=args.reset_cmd,
        reset_timeout_seconds=args.reset_timeout,
    )

    args.output_log.parent.mkdir(parents=True, exist_ok=True)
    args.output_log.write_text(result.log, encoding="utf-8")
    write_junit(
        args.junit_output,
        result,
        args.mode,
        args.port,
        args.baud,
        args.require_tls_version,
    )

    status = "PASS" if result.passed else "FAIL"
    print(f"RX671 Wi-Fi UART smoke {status}: {result.message}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

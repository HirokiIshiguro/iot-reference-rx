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
IOCTL_MISMATCH_MARKER = "Received a response for a different IOCTL - retry"
F2_DIAG_RE = re.compile(
    r"f2retry=(\d+) f2rec=(\d+) f2fail=(\d+) f2abort=(\d+) "
    r"f2lost=(\d+) f2inject=(\d+)"
)


@dataclass(frozen=True)
class SmokeResult:
    passed: bool
    message: str
    log: str
    duration_seconds: float
    attempts: int = 1
    recovery_reasons: tuple[str, ...] = ()


def sanitize_xml_text(value: str) -> str:
    """Replace characters forbidden by XML 1.0 with visible escapes."""
    output: list[str] = []
    for character in value:
        codepoint = ord(character)
        if (
            codepoint in (0x09, 0x0A, 0x0D)
            or 0x20 <= codepoint <= 0xD7FF
            or 0xE000 <= codepoint <= 0xFFFD
            or 0x10000 <= codepoint <= 0x10FFFF
        ):
            output.append(character)
        elif codepoint <= 0xFF:
            output.append(f"\\x{codepoint:02X}")
        elif codepoint <= 0xFFFF:
            output.append(f"\\u{codepoint:04X}")
        else:
            output.append(f"\\U{codepoint:08X}")
    return "".join(output)


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
    text: str,
    mode: str,
    require_tls_version: str = "",
    require_f2_fault_injection: bool = False,
) -> tuple[list[str], list[str]]:
    markers = required_markers(mode, require_tls_version)
    missing = [marker for marker in markers if marker not in text]
    failures: list[str] = []

    join_match = re.search(r"whd_wifi_join=([0-9A-Fa-f]{8})", text)
    if join_match and join_match.group(1) != "00000000":
        failures.append(f"whd_wifi_join failed: {join_match.group(1)}")

    wifi_on_match = re.search(r"whd_wifi_on=([0-9A-Fa-f]{8})", text)
    if wifi_on_match and wifi_on_match.group(1) != "00000000":
        failures.append(f"whd_wifi_on failed: {wifi_on_match.group(1)}")

    if mode == "mqtt":
        for label in ("AWS TLS", "AWS MQTT"):
            match = re.search(rf"{re.escape(label)}=(-?[0-9A-Fa-f]+)", text)
            if match and match.group(1) != "0":
                failures.append(f"{label} failed: {match.group(1)}")

    if require_f2_fault_injection:
        diagnostics = [
            tuple(map(int, values)) for values in F2_DIAG_RE.findall(text)
        ]
        if not diagnostics:
            missing.append("F2 one-shot fault injection diagnostics")
        elif not any(
            retry >= 1
            and recovered >= 1
            and failed == 0
            and aborted == 0
            and lost == 0
            and injected == 1
            for retry, recovered, failed, aborted, lost, injected in diagnostics
        ):
            failures.append("F2 one-shot fault injection did not recover cleanly")

    return missing, failures


def retryable_pre_network_failure(text: str, failures: Sequence[str]) -> bool:
    """Return true only for the Run 5 F2/IOCTL mismatch before networking.

    A whole-device reset is the recovery boundary because Function 2 abort made
    the retried CMD53 look successful while the returned control frame carried
    stale IOCTL ID 0.  Never retry after WHD/network progress or for a generic
    timeout with no causal mismatch evidence.
    """
    if IOCTL_MISMATCH_MARKER not in text:
        return False
    if any(marker in text for marker in NETWORK_MARKERS):
        return False
    return any(item.startswith("whd_wifi_on failed:") for item in failures)


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
    startup_retries: int = 0,
    require_f2_fault_injection: bool = False,
) -> SmokeResult:
    import serial

    start = time.monotonic()
    captured = bytearray()
    attempt_logs: list[str] = []
    recovery_reasons: list[str] = []

    try:
        with serial.Serial(
            port,
            baudrate=baud,
            timeout=0.1,
            write_timeout=1.0,
        ) as uart:
            print(f"Opened UART {port} at {baud} bps before reset", flush=True)

            for attempt_index in range(startup_retries + 1):
                captured = bytearray()
                uart.reset_input_buffer()
                print(
                    f"RX671 startup attempt {attempt_index + 1}/{startup_retries + 1}",
                    flush=True,
                )

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
                    attempt_logs.append(reset_details)
                    return SmokeResult(
                        False,
                        f"reset command failed with exit code {reset.returncode}",
                        "".join(attempt_logs),
                        duration,
                        attempt_index + 1,
                        tuple(recovery_reasons),
                    )

                retry_requested = False
                deadline = time.monotonic() + timeout_seconds
                while time.monotonic() < deadline:
                    chunk = uart.read(4096)
                    if chunk:
                        captured.extend(chunk)
                        sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                        sys.stdout.flush()

                    text = captured.decode("utf-8", errors="replace")
                    missing, failures = evaluate_log(
                        text,
                        mode,
                        require_tls_version,
                        require_f2_fault_injection,
                    )
                    if failures:
                        attempt_log = (
                            f"\n# startup attempt {attempt_index + 1}\n"
                            + text
                            + reset_details
                        )
                        attempt_logs.append(attempt_log)
                        if (
                            attempt_index < startup_retries
                            and retryable_pre_network_failure(text, failures)
                        ):
                            reason = "f2-ioctl-id-mismatch-before-network"
                            recovery_reasons.append(reason)
                            print(
                                "Bounded RX671 pre-network recovery: " + reason,
                                flush=True,
                            )
                            retry_requested = True
                            break
                        duration = time.monotonic() - start
                        return SmokeResult(
                            False,
                            "; ".join(failures),
                            "".join(attempt_logs),
                            duration,
                            attempt_index + 1,
                            tuple(recovery_reasons),
                        )
                    if not missing:
                        attempt_logs.append(
                            f"\n# startup attempt {attempt_index + 1}\n"
                            + text
                            + reset_details
                        )
                        duration = time.monotonic() - start
                        message = f"all {mode} milestones observed"
                        if recovery_reasons:
                            message += f" after {len(recovery_reasons)} recovery reset"
                        return SmokeResult(
                            True,
                            message,
                            "".join(attempt_logs),
                            duration,
                            attempt_index + 1,
                            tuple(recovery_reasons),
                        )

                if retry_requested:
                    continue

                text = captured.decode("utf-8", errors="replace")
                missing, failures = evaluate_log(
                    text,
                    mode,
                    require_tls_version,
                    require_f2_fault_injection,
                )
                attempt_logs.append(
                    f"\n# startup attempt {attempt_index + 1}\n"
                    + text
                    + reset_details
                )
                details = failures or ["missing: " + ", ".join(missing)]
                duration = time.monotonic() - start
                return SmokeResult(
                    False,
                    "; ".join(details),
                    "".join(attempt_logs),
                    duration,
                    attempt_index + 1,
                    tuple(recovery_reasons),
                )
    except Exception as exc:
        duration = time.monotonic() - start
        text = "".join(attempt_logs) + captured.decode("utf-8", errors="replace")
        return SmokeResult(
            False,
            f"UART smoke exception: {exc}",
            text,
            duration,
            max(1, len(attempt_logs)),
            tuple(recovery_reasons),
        )


def write_junit(
    path: Path,
    result: SmokeResult,
    mode: str,
    port: str,
    baud: int,
    require_tls_version: str = "",
    require_f2_fault_injection: bool = False,
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
    ET.SubElement(
        properties,
        "property",
        {"name": "mode", "value": sanitize_xml_text(mode)},
    )
    ET.SubElement(
        properties,
        "property",
        {
            "name": "require_f2_fault_injection",
            "value": str(require_f2_fault_injection).lower(),
        },
    )
    ET.SubElement(
        properties,
        "property",
        {"name": "startup_attempts", "value": str(result.attempts)},
    )
    ET.SubElement(
        properties,
        "property",
        {
            "name": "recovery_reasons",
            "value": sanitize_xml_text(",".join(result.recovery_reasons)),
        },
    )
    ET.SubElement(
        properties,
        "property",
        {"name": "port", "value": sanitize_xml_text(port)},
    )
    ET.SubElement(properties, "property", {"name": "baud", "value": str(baud)})
    ET.SubElement(
        properties,
        "property",
        {
            "name": "require_tls_version",
            "value": sanitize_xml_text(require_tls_version),
        },
    )
    case = ET.SubElement(
        suite,
        "testcase",
        {
            "classname": "hardware.ek_rx671",
            "name": sanitize_xml_text(f"wifi_{mode}"),
            "time": f"{result.duration_seconds:.3f}",
        },
    )
    if not result.passed:
        safe_message = sanitize_xml_text(result.message)
        failure = ET.SubElement(case, "failure", {"message": safe_message})
        failure.text = safe_message
    system_out = ET.SubElement(case, "system-out")
    system_out.text = sanitize_xml_text(result.log)
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
    parser.add_argument(
        "--require-f2-fault-injection",
        action="store_true",
        help=(
            "Require one injected F2 byte-read failure and a clean non-abort "
            "recovery in the UART diagnostics."
        ),
    )
    parser.add_argument("--reset-cmd", required=True)
    parser.add_argument("--reset-timeout", type=float, default=90.0)
    parser.add_argument(
        "--startup-retries",
        type=int,
        choices=(0, 1),
        default=0,
        help=(
            "Allow one whole-device reset only for an explicit F2/IOCTL ID "
            "mismatch before network startup."
        ),
    )
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
        startup_retries=args.startup_retries,
        require_f2_fault_injection=args.require_f2_fault_injection,
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
        args.require_f2_fault_injection,
    )

    status = "PASS" if result.passed else "FAIL"
    print(f"RX671 Wi-Fi UART smoke {status}: {result.message}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
OTA observability and log classification helper for iot-reference-rx.

This script has two modes:
1. Live UART monitor mode for CK-RX65N hardware.
2. Offline log analysis mode for previously captured UART logs.

It records progress markers, classifies likely failure points, and can emit:
- raw UART log with wallclock and relative timestamps
- JSON summary for CI artifacts
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Force unbuffered stdout for CI environments.
if not sys.stdout.isatty():
    sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except Exception:
        pass

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None


RL78_G1C_VID_PID = "045B:8111"
VERSION_RE = re.compile(r"Application version (\d+)\.(\d+)\.(\d+)")
LOG_PREFIX_RE = re.compile(r"^(?:\[[^\]]+\])?\[\+([0-9]+(?:\.[0-9]+)?)s\]\s?(.*)$")


@dataclass(frozen=True)
class Marker:
    marker_id: str
    stage: str
    pattern: str
    required: bool
    capture_version: bool = False


@dataclass(frozen=True)
class ErrorPattern:
    error_id: str
    classification: str
    pattern: str
    stage: str


MARKERS = [
    Marker("bootloader", "boot", r"==== .*BootLoader", False),
    Marker("app_version", "boot", r"Application version \d+\.\d+\.\d+", False, True),
    Marker("ota_task_started", "boot", r"Start OTA Update Task", False),
    Marker("request_job_document", "waiting_for_job", r"Request Job Document event Received", False),
    Marker("waiting_for_job", "waiting_for_job", r"Waiting for OTA job", False),
    Marker("job_received", "job_received", r"Received OTA Job\.", True),
    Marker("request_file_block", "download_started", r"Request File Block event Received", False),
    Marker("download_started", "download_started", r"Starting The Download\.", True),
    Marker("file_block_received", "downloading", r"Received File Block event Received", False),
    Marker("block_downloaded", "downloading", r"Downloaded block \d+ of \d+\.", True),
    Marker("close_file", "close_file", r"Close file event Received", True),
    Marker("activate_image", "activate_image", r"Activate Image event Received", True),
    Marker("ota_completed", "activate_image", r"OTA Completed successfully!", False),
    Marker("software_reset", "reboot", r"software reset\.\.\.", False),
    Marker("selfcheck_mode", "self_test", r"OTA image is in selfcheck mode\.", False),
    Marker("image_state_testing", "self_test", r"Testing\.", False),
    Marker("image_self_test_passed", "self_test", r"Image self-test passed!", False),
    Marker(
        "image_accepted",
        "accepted",
        r"New image has higher version than current image, accepted!",
        True,
    ),
    Marker("image_committed", "accepted", r"Accepted and committed final image\.", False),
    Marker("buffer_area_erased", "accepted", r"Successful to erase the buffer area", False),
]

ERROR_PATTERNS = [
    ErrorPattern("semaphore_create_failed", "resource_init_failed", r"Failed to create semaphore!", "boot"),
    ErrorPattern("mqtt_not_connected", "mqtt_not_connected", r"MQTT not connected, exiting!", "boot"),
    ErrorPattern(
        "thing_name_missing",
        "missing_thing_name",
        r"Thing name is not stored in Data Flash\.|Failed to get thing name!",
        "boot",
    ),
    ErrorPattern("job_doc_fetch_failed", "job_document_error", r"Failed to get job document!", "waiting_for_job"),
    ErrorPattern(
        "job_doc_invalid",
        "job_document_error",
        r"Failed to parse the job document!|The job document cannot be parsed or corrupted!",
        "job_received",
    ),
    ErrorPattern(
        "create_file_failed",
        "create_file_failed",
        r"otaPal_CreateFileForRx: failed!|Unable to create the OTA file",
        "job_received",
    ),
    ErrorPattern(
        "block_decode_failed",
        "download_data_error",
        r"File block decoding error|File ID mismatched|File block size mismatched",
        "downloading",
    ),
    ErrorPattern(
        "flash_write_failed",
        "flash_write_failed",
        r"Flash erase: NG|ota_flash_write_function: NG|Error R_FWUP_EraseArea\(\)",
        "downloading",
    ),
    ErrorPattern(
        "codesign_missing",
        "missing_codesigncert",
        r"No certificate stored in DF!",
        "close_file",
    ),
    ErrorPattern(
        "codesign_load_failed",
        "codesigncert_load_failed",
        r"Failed to store the certificate in dynamic memory",
        "close_file",
    ),
    ErrorPattern(
        "signature_failed",
        "signature_verification_failed",
        r"Failed to decode the image signature to DER format\.|signature verification failed|R_FWUP_VerifyImage returns error|Error ECDSASignature extraction",
        "close_file",
    ),
    ErrorPattern(
        "close_file_failed",
        "close_file_failed",
        r"OTA job failed at OtaAgentEventCloseFile",
        "close_file",
    ),
    ErrorPattern(
        "commit_state_invalid",
        "commit_state_invalid",
        r"Not in commit pending so can not mark image valid",
        "self_test",
    ),
    ErrorPattern("image_rejected", "image_rejected", r"Rejected image\.", "self_test"),
    ErrorPattern("image_aborted", "image_aborted", r"Aborted image\.", "self_test"),
    ErrorPattern(
        "rollback",
        "activate_or_boot_failed",
        r"The new image cannot be booted, rollback to old image",
        "activate_image",
    ),
    ErrorPattern(
        "self_test_failed",
        "self_test_failed",
        r"New image cannot pass self-test|self-test is failed",
        "self_test",
    ),
    ErrorPattern("version_invalid", "version_invalid", r"The image version is invalid", "self_test"),
    ErrorPattern("ota_failed", "ota_job_marked_failed", r"OTA is failed!", "self_test"),
    ErrorPattern("bootloader_error", "bootloader_error", r"error occurred\. please reset your board\.", "reboot"),
]

STAGE_ORDER = {
    "boot": 1,
    "waiting_for_job": 2,
    "job_received": 3,
    "download_started": 4,
    "downloading": 5,
    "close_file": 6,
    "activate_image": 7,
    "reboot": 8,
    "self_test": 9,
    "accepted": 10,
}


def list_renesas_ports():
    if serial is None:
        return []
    ports = []
    for port_info in serial.tools.list_ports.comports():
        if RL78_G1C_VID_PID in port_info.hwid.upper():
            ports.append((port_info.device, port_info.description, port_info.hwid))
    return ports


def open_serial_port(port, baud):
    if serial is None:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        return None
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )
    except serial.SerialException as exc:
        print(f"ERROR: Cannot open {port}: {exc}")
        return None

    print(f"Serial port {port} opened @ {baud}bps")
    try:
        print(f"  DSR={ser.dsr}, CTS={ser.cts}, CD={ser.cd}, RI={ser.ri}")
    except (serial.SerialException, OSError):
        print("  (serial line status not available)")
    return ser


def wait_for_cli(ser, max_retries=10, interval=2.0):
    print(f"Waiting for CLI to become responsive (max {max_retries * interval:.0f}s)...")
    for attempt in range(max_retries):
        ser.reset_input_buffer()
        cmd = b"CLI\r\n" if attempt < 3 else b"\r\n"
        ser.write(cmd)
        time.sleep(0.5)
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
            print(f"  CLI responded on attempt {attempt + 1}: {data.strip()[:80]}")
            return True
        time.sleep(interval - 0.5)
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
            print(
                f"  Device output on attempt {attempt + 1} ({len(data)} bytes): "
                f"{data.strip()[:80]}"
            )
            return True
        print(f"  Attempt {attempt + 1}/{max_retries}: no response")
    print("  WARNING: CLI did not respond after all retries")
    return False


def reset_device_via_uart(ser):
    cli_ready = wait_for_cli(ser)
    if not cli_ready:
        print("Sending 'reset' anyway as last resort...")

    print("Sending UART 'reset' command...")
    ser.reset_input_buffer()
    for ch in "reset":
        ser.write(ch.encode("ascii"))
        time.sleep(0.002)
    ser.write(b"\r\n")
    time.sleep(2.0)
    if ser.in_waiting:
        resp = ser.read(ser.in_waiting).decode("ascii", errors="replace")
        print(f"  Reset response: {resp.strip()[:80]}")
    print("Waiting for device reboot (5s)...")
    time.sleep(5.0)
    return cli_ready


def reset_device_via_command(reset_cmd):
    print(f"Running reset command: {reset_cmd}")
    try:
        result = subprocess.run(
            reset_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("  ERROR: Reset command timed out (300s)")
        return False
    except Exception as exc:
        print(f"  ERROR: Reset command failed: {exc}")
        return False

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            if line.strip():
                print(f"  [reset-cmd] {line}")
    if result.stderr:
        progress_re = re.compile(r"^\d+%\s*\[")
        for line in result.stderr.strip().splitlines():
            stripped = line.strip()
            if stripped and not progress_re.match(stripped):
                print(f"  [reset-cmd stderr] {stripped}")

    if result.returncode != 0:
        print(f"  WARNING: Reset command exited with code {result.returncode}")
        return False

    print("  Reset command completed successfully")
    return True


class OtaLogAnalyzer:
    def __init__(self, expected_version=None):
        self.expected_version = expected_version
        self.marker_state = {
            marker.marker_id: {
                "stage": marker.stage,
                "required": marker.required,
                "hits": 0,
                "first_seen_at": None,
                "first_line": None,
            }
            for marker in MARKERS
        }
        self.error_state = {}
        self.versions_seen = []
        self.total_lines = 0
        self.last_progress_stage = None
        self.last_observed_at = 0.0

    def consume_line(self, line, elapsed):
        self.total_lines += 1
        stripped = line.rstrip("\r\n")
        self.last_observed_at = max(self.last_observed_at, elapsed)

        for marker in MARKERS:
            match = re.search(marker.pattern, stripped)
            if not match:
                continue
            state = self.marker_state[marker.marker_id]
            state["hits"] += 1
            if state["first_seen_at"] is None:
                state["first_seen_at"] = round(elapsed, 3)
                state["first_line"] = stripped
            if marker.capture_version:
                version_match = VERSION_RE.search(stripped)
                if version_match:
                    version = ".".join(version_match.groups())
                    if version not in self.versions_seen:
                        self.versions_seen.append(version)
            if self.last_progress_stage is None or STAGE_ORDER[marker.stage] >= STAGE_ORDER.get(self.last_progress_stage, 0):
                self.last_progress_stage = marker.stage

        for pattern in ERROR_PATTERNS:
            if not re.search(pattern.pattern, stripped):
                continue
            if pattern.error_id in self.error_state:
                continue
            self.error_state[pattern.error_id] = {
                "classification": pattern.classification,
                "stage": pattern.stage,
                "first_seen_at": round(elapsed, 3),
                "line": stripped,
            }

    def has_marker(self, marker_id):
        return self.marker_state[marker_id]["hits"] > 0

    def first_error(self):
        if not self.error_state:
            return None
        return min(self.error_state.values(), key=lambda item: item["first_seen_at"])

    def is_success(self):
        required_ok = all(
            state["hits"] > 0
            for state in self.marker_state.values()
            if state["required"]
        )
        if not required_ok or self.first_error() is not None:
            return False

        if self.expected_version:
            if self.expected_version not in self.versions_seen:
                return False
        elif len(self.versions_seen) < 2:
            return False

        return True

    def classify_timeout(self, total_bytes):
        if total_bytes == 0 or self.total_lines == 0:
            return "no_uart_output"
        if not self.has_marker("job_received"):
            return "waiting_for_ota_job"
        if not self.has_marker("block_downloaded"):
            return "download_not_started"
        if not self.has_marker("close_file"):
            return "download_incomplete"
        if not self.has_marker("activate_image"):
            return "close_or_signature_phase"
        if not self.has_marker("selfcheck_mode"):
            return "reboot_or_selfcheck_missing"
        if not self.has_marker("image_accepted"):
            return "acceptance_not_observed"
        if self.expected_version and self.expected_version not in self.versions_seen:
            return "expected_version_not_observed"
        if not self.expected_version and len(self.versions_seen) < 2:
            return "new_version_not_observed"
        return "timeout_after_unknown_stage"

    def build_summary(self, total_bytes, elapsed, success):
        error = self.first_error()
        if error is not None:
            classification = error["classification"]
        elif success:
            classification = "success"
        else:
            classification = self.classify_timeout(total_bytes)

        duration_seconds = round(max(elapsed, self.last_observed_at), 3)
        required_markers_missing = [
            marker.marker_id
            for marker in MARKERS
            if marker.required and self.marker_state[marker.marker_id]["hits"] == 0
        ]

        return {
            "success": success,
            "classification": classification,
            "last_progress_stage": self.last_progress_stage,
            "expected_version": self.expected_version,
            "versions_seen": self.versions_seen,
            "total_lines": self.total_lines,
            "total_bytes": total_bytes,
            "duration_seconds": duration_seconds,
            "last_observed_at": round(self.last_observed_at, 3),
            "required_markers_missing": required_markers_missing,
            "first_error": error,
            "markers": self.marker_state,
            "errors": self.error_state,
        }


def ensure_parent(path_str):
    if not path_str:
        return None
    path = Path(path_str)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_timestamped_log(log_file, elapsed, text, force_newline=False):
    if log_file is None:
        return
    if text == "":
        return
    now = datetime.now(timezone.utc).isoformat()
    if force_newline and not text.endswith(("\n", "\r")):
        text = text + "\n"
    with log_file.open("a", encoding="utf-8") as handle:
        prefix = f"[{now}][+{elapsed:07.3f}s] "
        handle.write(prefix + text)


def parse_logged_line(line):
    match = LOG_PREFIX_RE.match(line.rstrip("\r\n"))
    if not match:
        return 0.0, line
    return float(match.group(1)), match.group(2)


def analyze_log_file(path, expected_version=None):
    analyzer = OtaLogAnalyzer(expected_version=expected_version)
    total_bytes = 0
    elapsed = 0.0
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            total_bytes += len(line.encode("utf-8", errors="replace"))
            elapsed, payload = parse_logged_line(line)
            analyzer.consume_line(payload, elapsed)
    summary = analyzer.build_summary(
        total_bytes=total_bytes,
        elapsed=elapsed,
        success=analyzer.is_success(),
    )
    return analyzer, summary


def monitor_uart(port, baud, timeout, expected_version=None, reset_cmd=None, skip_reset=False, raw_log_path=None):
    analyzer = OtaLogAnalyzer(expected_version=expected_version)
    total_bytes = 0
    raw_log_file = ensure_parent(raw_log_path)

    if reset_cmd:
        if not reset_device_via_command(reset_cmd):
            print("WARNING: Reset command failed, continuing to monitor anyway...")
        print("Waiting 5s for USB-Serial bridge recovery...")
        time.sleep(5.0)

    ser = open_serial_port(port, baud)
    if ser is None:
        summary = analyzer.build_summary(total_bytes=0, elapsed=0.0, success=False)
        summary["classification"] = "cannot_open_uart"
        return summary

    if skip_reset:
        print("Skipping device reset")
    else:
        if reset_cmd:
            print("Device already booted after external reset command.")
            print("Sending UART 'reset' to reboot and capture full output...")
        cli_ready = reset_device_via_uart(ser)
        if not cli_ready and reset_cmd:
            print("Reopening serial port (recovery attempt)...")
            ser.close()
            time.sleep(2.0)
            ser = open_serial_port(port, baud)
            if ser is None:
                summary = analyzer.build_summary(total_bytes=0, elapsed=0.0, success=False)
                summary["classification"] = "cannot_reopen_uart"
                return summary
            reset_device_via_uart(ser)

    print(f"Monitoring OTA UART ({port} @ {baud}bps, timeout={timeout}s)")
    print("=" * 60)
    start = time.time()
    last_progress_print = start
    failure_detected_at = None
    partial_line = ""

    try:
        while time.time() - start < timeout:
            if ser.in_waiting:
                try:
                    data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
                except serial.SerialException:
                    print("ERROR: Serial port read failed")
                    break

                total_bytes += len(data)
                elapsed = time.time() - start
                full_text = partial_line + data
                lines = full_text.splitlines(True)
                if lines and not lines[-1].endswith(("\n", "\r")):
                    partial_line = lines.pop()
                else:
                    partial_line = ""

                for line in lines:
                    append_timestamped_log(raw_log_file, elapsed, line)
                    sys.stdout.write(f"[+{elapsed:07.3f}s] {line}")
                    analyzer.consume_line(line, elapsed)
                sys.stdout.flush()

                if failure_detected_at is None and analyzer.first_error() is not None:
                    failure_detected_at = time.time()
                    error = analyzer.first_error()
                    print(
                        f"\n>>> [ERROR DETECTED] {error['classification']} "
                        f"at +{error['first_seen_at']:.3f}s <<<"
                    )

                if analyzer.is_success():
                    print("\nAll required OTA markers found.")
                    time.sleep(2.0)
                    break

                if failure_detected_at is not None and (time.time() - failure_detected_at) >= 3.0:
                    break
            else:
                now = time.time()
                if now - last_progress_print >= 15:
                    elapsed = now - start
                    print(
                        f"  [WAITING] {elapsed:.0f}s elapsed, "
                        f"{total_bytes} bytes received, "
                        f"last_stage={analyzer.last_progress_stage}"
                    )
                    last_progress_print = now
            time.sleep(0.1)
    finally:
        ser.close()

    if partial_line:
        elapsed = time.time() - start
        append_timestamped_log(raw_log_file, elapsed, partial_line, force_newline=True)
        sys.stdout.write(f"[+{elapsed:07.3f}s] {partial_line}\n")
        analyzer.consume_line(partial_line, elapsed)
        sys.stdout.flush()

    elapsed = time.time() - start
    print("=" * 60)
    print(f"Monitoring completed in {elapsed:.1f}s")
    print(f"Total UART bytes received: {total_bytes}")

    return analyzer.build_summary(total_bytes=total_bytes, elapsed=elapsed, success=analyzer.is_success())


def write_summary(summary_path, summary):
    if not summary_path:
        return
    path = ensure_parent(summary_path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def print_summary(summary):
    print("\n--- OTA Summary ---")
    print(f"Success:        {summary['success']}")
    print(f"Classification: {summary['classification']}")
    print(f"Last stage:     {summary['last_progress_stage']}")
    print(f"Versions seen:  {', '.join(summary['versions_seen']) or '(none)'}")
    print(f"Total bytes:    {summary['total_bytes']}")
    print(f"Duration:       {summary['duration_seconds']}s")
    if summary["required_markers_missing"]:
        print(f"Missing req.:   {', '.join(summary['required_markers_missing'])}")

    print("\nMarkers:")
    for marker in MARKERS:
        state = summary["markers"][marker.marker_id]
        status = "HIT" if state["hits"] else "MISS"
        required = " required" if marker.required else ""
        print(f"  - {marker.marker_id}: {status}{required}")
        if state["first_seen_at"] is not None:
            print(f"    first_seen_at=+{state['first_seen_at']:.3f}s")

    if summary["errors"]:
        print("\nErrors:")
        for error_id, state in summary["errors"].items():
            print(
                f"  - {error_id}: {state['classification']} "
                f"(stage={state['stage']}, +{state['first_seen_at']:.3f}s)"
            )


def main():
    parser = argparse.ArgumentParser(description="Analyze or monitor OTA progress for CK-RX65N")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input-log", help="Analyze an existing UART log file")
    source_group.add_argument("--port", help="Serial port (for live UART monitor, e.g. COM6)")

    parser.add_argument("--baud", type=int, default=115200, help="Baud rate for live UART mode")
    parser.add_argument("--timeout", type=int, default=420, help="Total live monitoring timeout in seconds")
    parser.add_argument("--reset-cmd", default=None, help="External command to run before opening UART")
    parser.add_argument("--no-reset", action="store_true", help="Skip UART reset in live mode")
    parser.add_argument(
        "--expected-version",
        default=None,
        help="Expected post-OTA version (e.g. 0.9.3). If omitted, two distinct versions are required.",
    )
    parser.add_argument("--raw-log", default=None, help="Write timestamped UART log to this path")
    parser.add_argument("--summary-json", default=None, help="Write JSON summary to this path")
    args = parser.parse_args()

    print("=" * 60)
    print("iot-reference-rx OTA Observability Helper")
    print("=" * 60)
    if args.input_log:
        print(f"Mode:        offline analysis")
        print(f"Input log:   {args.input_log}")
    else:
        print(f"Mode:        live UART monitor")
        print(f"Port:        {args.port}")
        print(f"Baud:        {args.baud}")
        print(f"Timeout:     {args.timeout}s")
        if args.reset_cmd:
            print("Reset:       external command + UART 'reset'")
        elif args.no_reset:
            print("Reset:       disabled (--no-reset)")
        else:
            print("Reset:       UART 'reset' command")

        rl78_ports = list_renesas_ports()
        if rl78_ports:
            print("\nRenesas RL78/G1C ports detected:")
            for port, desc, hwid in rl78_ports:
                primary = " <-- primary" if port == args.port else ""
                print(f"  {port}: {desc}{primary}")
                print(f"       {hwid}")
        else:
            print("\nWARNING: No Renesas RL78/G1C ports detected!")

    print(f"Expected ver:{args.expected_version or '(auto detect)'}")
    print(f"Raw log:     {args.raw_log or '(disabled)'}")
    print(f"Summary:     {args.summary_json or '(disabled)'}")
    print("=" * 60)

    if args.port and serial is None:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        return 1

    if args.input_log:
        _, summary = analyze_log_file(args.input_log, expected_version=args.expected_version)
    else:
        summary = monitor_uart(
            port=args.port,
            baud=args.baud,
            timeout=args.timeout,
            expected_version=args.expected_version,
            reset_cmd=args.reset_cmd,
            skip_reset=args.no_reset,
            raw_log_path=args.raw_log,
        )

    write_summary(args.summary_json, summary)
    print_summary(summary)

    if summary["success"]:
        print("\nOTA OBSERVATION PASSED")
        return 0

    print("\nOTA OBSERVATION FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())

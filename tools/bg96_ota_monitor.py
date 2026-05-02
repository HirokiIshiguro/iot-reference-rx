#!/usr/bin/env python3
"""Monitor CK-RX65N BG96 OTA progress on UART."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import serial

from bg96_bootloader_integration import default_rfp_cli, run_rfp, write_serial_text


VERSION_RE = re.compile(r"Application version (\d+)\.(\d+)\.(\d+)")
MARKERS = {
    "ota_task_started": "Start OTA Update Task",
    "waiting_for_job": "Waiting for OTA job",
    "job_received": "Received OTA Job.",
    "download_started": "Starting The Download.",
    "block_downloaded": "Downloaded block",
    "close_file": "Close file event Received",
    "activate_image": "Activate Image event Received",
    "selfcheck_mode": "OTA image is in selfcheck mode.",
    "image_accepted": "New image has higher version than current image, accepted!",
}
REQUIRED = (
    "job_received",
    "download_started",
    "block_downloaded",
    "close_file",
    "activate_image",
    "image_accepted",
)
ERROR_PATTERNS = (
    "Cellular init failed",
    "Cellular Open Failed",
    "Failed to decode the image signature",
    "Failed to parse the job document",
    "Unable to create the OTA file",
    "OTA job failed",
    "No certificate stored in DF",
    "signature verification failed",
    "R_FWUP_VerifyImage returns error",
    "The image version is invalid",
    "OTA is failed",
    "rollback",
)
RETRYABLE_ERROR_PATTERNS = (
    "Cellular init failed",
    "Cellular Open Failed",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uart-port", required=True)
    parser.add_argument("--baud", type=int, default=int(os.environ.get("UART_BAUD_RATE", "921600")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("BG96_OTA_OBSERVE_TIMEOUT_SECONDS", "900")))
    parser.add_argument("--app-reset-retries", type=int, default=int(os.environ.get("BG96_OTA_APP_RESET_RETRIES", "2")))
    parser.add_argument(
        "--activate-reset-delay",
        type=float,
        default=float(os.environ.get("BG96_OTA_ACTIVATE_RESET_DELAY_SECONDS", "15")),
    )
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--raw-log", type=Path)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--rfp-cli", default=default_rfp_cli())
    parser.add_argument("--rfp-device", default=os.environ.get("RFP_DEVICE", "RX65x"))
    parser.add_argument("--rfp-tool", default=os.environ.get("BG96_BOOTLOADER_E2LITE_SERIAL", "OBE110020"))
    parser.add_argument("--rfp-interface", default=os.environ.get("RFP_INTERFACE", "fine"))
    parser.add_argument("--rfp-speed", default=os.environ.get("RFP_SPEED", "1500K"))
    parser.add_argument("--rfp-auth-id", default=os.environ.get("RFP_AUTH_ID", "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"))
    return parser.parse_args()


def log_raw(path: Path | None, elapsed: float, text: str) -> None:
    if path is None or not text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now(timezone.utc).isoformat()}][+{elapsed:07.3f}s] {text}")


def monitor_once(args: argparse.Namespace, port: serial.Serial, attempt: int) -> dict:
    detected: dict[str, dict] = {}
    versions: list[str] = []
    errors: list[str] = []
    partial = ""
    start = time.time()
    last_rx_time = start
    activate_reset_done = False
    total_bytes = 0

    port.reset_input_buffer()
    run_rfp(args, ["-sig", "-run"])
    print(f"[OTA] Monitoring {args.uart_port} for OTA version {args.expected_version} (attempt {attempt})")
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        now = time.time()
        if (
            not activate_reset_done
            and args.activate_reset_delay >= 0
            and any(marker in detected for marker in ("activate_image", "selfcheck_mode"))
            and now - last_rx_time >= args.activate_reset_delay
        ):
            elapsed = now - start
            message = (
                f"\n[OTA] activate/selfcheck reached; resetting app after "
                f"{args.activate_reset_delay:g}s quiet\n"
            )
            print(message, end="")
            log_raw(args.raw_log, elapsed, message)
            port.reset_input_buffer()
            run_rfp(args, ["-sig", "-run"])
            activate_reset_done = True
            last_rx_time = time.time()

        chunk = port.read(port.in_waiting or 1)
        if not chunk:
            time.sleep(0.05)
            continue

        last_rx_time = time.time()
        total_bytes += len(chunk)
        text = chunk.decode("utf-8", errors="replace")
        elapsed = time.time() - start
        write_serial_text(text)
        log_raw(args.raw_log, elapsed, text)

        content = partial + text
        lines = content.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            partial = lines.pop()
        else:
            partial = ""

        for line in lines:
            stripped = line.strip()
            for marker_id, marker in MARKERS.items():
                if marker in stripped and marker_id not in detected:
                    detected[marker_id] = {"seen_at": round(elapsed, 3), "line": stripped}
            match = VERSION_RE.search(stripped)
            if match:
                version = ".".join(match.groups())
                if version not in versions:
                    versions.append(version)
            for pattern in ERROR_PATTERNS:
                if pattern.lower() in stripped.lower():
                    errors.append(stripped)

        if (
            all(marker in detected for marker in REQUIRED)
            or "image_accepted" in detected
        ) and args.expected_version in versions:
            break
        if errors:
            break

    elapsed = time.time() - start
    success = all(marker in detected for marker in REQUIRED) and args.expected_version in versions and not errors
    return {
        "success": success,
        "attempt": attempt,
        "expected_version": args.expected_version,
        "versions_seen": versions,
        "detected_markers": detected,
        "missing_required": [marker for marker in REQUIRED if marker not in detected],
        "errors": errors,
        "total_bytes": total_bytes,
        "duration_seconds": round(elapsed, 3),
    }


def is_retryable_error(error: str) -> bool:
    return any(pattern.lower() in error.lower() for pattern in RETRYABLE_ERROR_PATTERNS)


def aggregate_summaries(summaries: list[dict], expected_version: str) -> dict:
    detected: dict[str, dict] = {}
    versions: list[str] = []
    errors: list[str] = []
    total_bytes = 0
    duration_seconds = 0.0

    for summary in summaries:
        attempt = summary["attempt"]
        total_bytes += summary.get("total_bytes", 0)
        duration_seconds += summary.get("duration_seconds", 0.0)
        for version in summary.get("versions_seen", []):
            if version not in versions:
                versions.append(version)
        for marker_id, marker in summary.get("detected_markers", {}).items():
            if marker_id not in detected:
                detected[marker_id] = dict(marker, attempt=attempt)
        errors.extend(summary.get("errors", []))

    blocking_errors = [error for error in errors if not is_retryable_error(error)]
    success = (
        all(marker in detected for marker in REQUIRED)
        and expected_version in versions
        and not blocking_errors
    )

    return {
        "success": success,
        "expected_version": expected_version,
        "versions_seen": versions,
        "detected_markers": detected,
        "missing_required": [marker for marker in REQUIRED if marker not in detected],
        "errors": errors,
        "blocking_errors": blocking_errors,
        "retryable_errors": [error for error in errors if is_retryable_error(error)],
        "total_bytes": total_bytes,
        "duration_seconds": round(duration_seconds, 3),
        "attempt_count": len(summaries),
        "attempts": summaries,
    }


def main() -> int:
    args = parse_args()
    summaries: list[dict] = []

    port = serial.Serial(
        port=args.uart_port,
        baudrate=args.baud,
        timeout=0.1,
        write_timeout=10,
        dsrdtr=False,
        rtscts=False,
    )
    try:
        for attempt in range(1, args.app_reset_retries + 2):
            summary = monitor_once(args, port, attempt)
            summaries.append(summary)
            if summary["success"]:
                break
            errors = [str(error) for error in summary["errors"]]
            if (
                attempt <= args.app_reset_retries
                and any("Cellular init failed" in error or "Cellular Open Failed" in error for error in errors)
            ):
                print(f"\n[OTA] app cellular init failed; resetting app and retrying ({attempt}/{args.app_reset_retries})")
                continue
            break
    finally:
        port.close()

    summary = aggregate_summaries(summaries, args.expected_version)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print("\n--- OTA Summary ---")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if summary["success"]:
        print("[PASS] app OTA update verified")
        return 0
    print("[FAIL] app OTA update was not verified")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

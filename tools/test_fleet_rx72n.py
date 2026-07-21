#!/usr/bin/env python3
"""Monitor UART logs and verify the Fleet Provisioning demo completes."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


DEFAULT_LOG_PORT = os.environ.get("RX72N_LOG_PORT", os.environ.get("UART_PORT", "COM7"))
DEFAULT_LOG_BAUD = int(os.environ.get("UART_BAUD_RATE", "921600"))
DEFAULT_TIMEOUT = 240
TLS_VERSION_RE = re.compile(r"TLS handshake successful: version\s+(\S+)")
WHD_WIFI_ON_RE = re.compile(r"(?:^|\s)whd_wifi_on=([0-9A-Fa-f]{8})(?:\s|$)")

MARKERS = [
    ("claim_mqtt", "Established connection with claim credentials."),
    ("certificate", "Received certificate with Id:"),
    ("thing_name", "Received AWS IoT Thing name:"),
    ("provisioned_mqtt", "Sucessfully established connection with provisioned credentials."),
    ("complete", "Demo completed successfully."),
]

ERROR_PATTERNS = [
    "Cellular init failed",
    "Cellular Open Failed",
    "Failed to establish MQTT session",
    "Failed to publish to fleet provisioning topic",
    "Failed to parse the CreateCertificatefromCsr API response",
    "Failed to parse the RegisterThing API response",
    "Failed to establish MQTT session with provisioned credentials",
    "All 3 demo iterations failed.",
    "Error:",
]

RETRYABLE_STARTUP_ERROR_PATTERNS = (
    "Cellular init failed",
    "Cellular Open Failed",
    "WHD startup failed:",
)


def whd_wifi_on_failed(line):
    """Return True only for an explicit non-zero WHD bring-up result."""
    match = WHD_WIFI_ON_RE.search(line)
    return bool(match and match.group(1).upper() != "00000000")


def retryable_startup_failure(errors, results, thing_name, certificate_id):
    """Allow a reset only before Fleet can have created an AWS resource."""
    resource_creation_may_have_started = (
        any(results.values()) or
        bool(thing_name) or
        bool(certificate_id)
    )
    if resource_creation_may_have_started:
        return False

    return any(
        pattern in error
        for error in errors
        for pattern in RETRYABLE_STARTUP_ERROR_PATTERNS
    )


def reset_device_via_command(reset_cmd):
    print(f"Running reset command: {reset_cmd}")
    try:
        result = subprocess.run(
            reset_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        print("  ERROR: Reset command timed out (180s)")
        return False

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            stripped = line.strip()
            if stripped:
                print(f"  [reset-cmd] {stripped}")

    if result.stderr:
        progress_re = re.compile(r"^\d+%\s*\[")
        for line in result.stderr.strip().splitlines():
            stripped = line.strip()
            if stripped and not progress_re.match(stripped):
                print(f"  [reset-cmd stderr] {stripped}")

    if result.returncode != 0:
        print(f"  ERROR: Reset command exited with code {result.returncode}")
        return False

    print("  Reset command completed successfully")
    return True


def monitor_uart(port, baud, timeout, reset_cmd, progress_callback=None):
    results = {name: False for name, _ in MARKERS}
    errors = []
    certificate_id = None
    thing_name = None
    tls_versions = []
    tls_events = []
    total_bytes = 0
    total_lines = 0
    buffer = ""
    fatal_startup_error = False

    ser = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.5,
    )
    print(f"Serial port {port} opened @ {baud}bps")

    try:
        ser.reset_input_buffer()
        if reset_cmd and not reset_device_via_command(reset_cmd):
            errors.append("reset command failed")

        start = time.time()
        last_status = 0

        while time.time() - start < timeout:
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                text = chunk.decode("ascii", errors="replace")
                total_bytes += len(chunk)
                buffer += text

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip("\r")
                    if not line:
                        continue

                    total_lines += 1
                    print(line)
                    progress_changed = False

                    for name, pattern in MARKERS:
                        if (not results[name]) and pattern in line:
                            results[name] = True
                            progress_changed = True
                            print(f"[MILESTONE] {name}: {line}")

                    if "Received certificate with Id:" in line:
                        certificate_id = line.split("Received certificate with Id:", 1)[1].strip()
                        progress_changed = True
                    if "Received AWS IoT Thing name:" in line:
                        thing_name = line.split("Received AWS IoT Thing name:", 1)[1].strip()
                        progress_changed = True

                    tls_match = TLS_VERSION_RE.search(line)
                    if tls_match:
                        tls_version = tls_match.group(1)
                        tls_events.append(
                            {
                                "version": tls_version,
                                "seen_at": round(time.time() - start, 3),
                                "line": line,
                            }
                        )
                        if tls_version not in tls_versions:
                            tls_versions.append(tls_version)
                        progress_changed = True
                        print(f"[MILESTONE] tls_version: {tls_version}")

                    if whd_wifi_on_failed(line):
                        error = f"WHD startup failed: {line}"
                        errors.append(error)
                        fatal_startup_error = True
                        progress_changed = True
                        print(f"[ERROR] {error}")

                    for pattern in ERROR_PATTERNS:
                        if pattern in line:
                            errors.append(line)
                            progress_changed = True
                            print(f"[ERROR] {line}")
                            if pattern in ("Cellular init failed", "Cellular Open Failed"):
                                fatal_startup_error = True

                    if progress_changed and progress_callback:
                        progress_callback(
                            {
                                "results": dict(results),
                                "errors": list(errors),
                                "total_bytes": total_bytes,
                                "total_lines": total_lines,
                                "thing_name": thing_name,
                                "certificate_id": certificate_id,
                                "tls_versions_seen": list(tls_versions),
                                "tls_events": list(tls_events),
                            }
                        )

                if all(results.values()):
                    break
                if fatal_startup_error:
                    break
            else:
                time.sleep(0.05)

            elapsed = time.time() - start
            if int(elapsed) // 30 > last_status:
                last_status = int(elapsed) // 30
                detected = sum(1 for ok in results.values() if ok)
                print(f"[STATUS] {elapsed:.0f}s elapsed: {detected}/{len(results)} markers, RX={total_bytes} bytes")
    finally:
        ser.close()
        print(f"Closed {port}")

    return results, errors, total_bytes, total_lines, thing_name, certificate_id, tls_versions, tls_events


def tls_requirement_ok(require_tls_version, tls_versions):
    require_tls_version = (require_tls_version or "").strip()
    if not require_tls_version:
        return True
    return bool(tls_versions) and all(version == require_tls_version for version in tls_versions)


def make_summary(
    *,
    success,
    results,
    errors,
    total_bytes,
    total_lines,
    thing_name,
    certificate_id,
    require_tls_version,
    tls_versions,
    tls_events,
    attempts,
    partial,
):
    return {
        "success": bool(success),
        "partial": bool(partial),
        "results": dict(results),
        "errors": list(errors),
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "thing_name": thing_name,
        "certificate_id": certificate_id,
        "require_tls_version": require_tls_version,
        "tls_versions_seen": list(tls_versions),
        "tls_version_ok": tls_requirement_ok(require_tls_version, tls_versions),
        "tls_events": list(tls_events),
        "attempts": list(attempts),
    }


def write_json_atomic(path, payload):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    os.replace(temporary_path, output_path)


def write_junit(path, label, summary):
    """Write one deterministic JUnit testcase for CI report rendering."""
    success = bool(summary.get("success"))
    errors = summary.get("errors") or []
    missing = [name for name, detected in (summary.get("results") or {}).items() if not detected]
    testsuite = ET.Element(
        "testsuite",
        {
            "name": "fleet-provisioning",
            "tests": "1",
            "failures": "0" if success else "1",
            "errors": "0",
        },
    )
    testcase = ET.SubElement(
        testsuite,
        "testcase",
        {"classname": "hardware.aws-iot", "name": label},
    )
    if not success:
        details = []
        if missing:
            details.append("missing markers: " + ", ".join(missing))
        if errors:
            details.append("errors: " + " | ".join(errors[:10]))
        ET.SubElement(
            testcase,
            "failure",
            {"message": "Fleet Provisioning verification failed"},
        ).text = "\n".join(details) or "Fleet Provisioning verification did not complete"

    properties = ET.SubElement(testsuite, "properties")
    for name in ("thing_name", "certificate_id", "require_tls_version", "tls_version_ok"):
        ET.SubElement(
            properties,
            "property",
            {"name": name, "value": str(summary.get(name, ""))},
        )

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(testsuite).write(output_path, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description="Verify Fleet Provisioning demo from log UART")
    parser.add_argument("--log-port", default=DEFAULT_LOG_PORT)
    parser.add_argument("--log-baud", type=int, default=DEFAULT_LOG_BAUD)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--reset-cmd", required=True)
    parser.add_argument("--label", default=os.environ.get("FLEET_TEST_LABEL", "RX72N"))
    parser.add_argument("--summary-json", help="Optional path to write fleet provisioning summary JSON")
    parser.add_argument("--junit-output", help="Optional path to write a JUnit XML report")
    parser.add_argument("--app-reset-retries", type=int, default=int(os.environ.get("FLEET_APP_RESET_RETRIES", "0")))
    parser.add_argument("--require-tls-version", default=os.environ.get("FLEET_REQUIRE_TLS_VERSION", ""))
    args = parser.parse_args()
    require_tls_version = args.require_tls_version.strip()

    print("=" * 60)
    print(f"{args.label} Fleet Provisioning Test")
    print("=" * 60)
    print(f"Log Port: {args.log_port}")
    print(f"Log Baud: {args.log_baud}")
    print(f"Timeout:  {args.timeout}s")
    print(f"Required TLS: {require_tls_version or '(not enforced)'}")
    print("=" * 60)

    attempts = []
    results = {name: False for name, _ in MARKERS}
    errors = []
    total_bytes = 0
    total_lines = 0
    thing_name = None
    certificate_id = None
    tls_versions = []
    tls_events = []
    last_progress_state = {
        "results": results,
        "errors": errors,
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "thing_name": thing_name,
        "certificate_id": certificate_id,
        "tls_versions_seen": tls_versions,
        "tls_events": tls_events,
    }

    def persist_partial(state=None):
        nonlocal last_progress_state
        if state is not None:
            last_progress_state = state
        current = last_progress_state
        if args.summary_json:
            write_json_atomic(
                args.summary_json,
                make_summary(
                    success=False,
                    results=current["results"],
                    errors=current["errors"],
                    total_bytes=current["total_bytes"],
                    total_lines=current["total_lines"],
                    thing_name=current["thing_name"],
                    certificate_id=current["certificate_id"],
                    require_tls_version=require_tls_version,
                    tls_versions=current["tls_versions_seen"],
                    tls_events=current["tls_events"],
                    attempts=attempts,
                    partial=True,
                ),
            )

    # Create the cleanup handoff before the board is reset. If the monitor is
    # interrupted later, every observed resource identifier is durably updated.
    persist_partial()
    for attempt in range(1, args.app_reset_retries + 2):
        if attempt > 1:
            print(f"[RETRY] restarting fleet test after pre-claim startup failure ({attempt}/{args.app_reset_retries + 1})")
        try:
            results, errors, total_bytes, total_lines, thing_name, certificate_id, tls_versions, tls_events = monitor_uart(
                args.log_port,
                args.log_baud,
                args.timeout,
                args.reset_cmd,
                progress_callback=persist_partial,
            )
        except Exception as exc:  # Keep cleanup evidence even when UART access fails.
            results = dict(last_progress_state["results"])
            errors = list(last_progress_state["errors"])
            errors.append(f"{type(exc).__name__}: {exc}")
            total_bytes = last_progress_state["total_bytes"]
            total_lines = last_progress_state["total_lines"]
            thing_name = last_progress_state["thing_name"]
            certificate_id = last_progress_state["certificate_id"]
            tls_versions = list(last_progress_state["tls_versions_seen"])
            tls_events = list(last_progress_state["tls_events"])
            persist_partial(
                {
                    "results": results,
                    "errors": errors,
                    "total_bytes": total_bytes,
                    "total_lines": total_lines,
                    "thing_name": thing_name,
                    "certificate_id": certificate_id,
                    "tls_versions_seen": tls_versions,
                    "tls_events": tls_events,
                }
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "results": dict(results),
                    "errors": list(errors),
                    "total_bytes": total_bytes,
                    "total_lines": total_lines,
                    "thing_name": thing_name,
                    "certificate_id": certificate_id,
                    "tls_versions_seen": list(tls_versions),
                    "tls_version_ok": tls_requirement_ok(require_tls_version, tls_versions),
                    "tls_events": list(tls_events),
                }
            )
            break
        tls_ok = tls_requirement_ok(require_tls_version, tls_versions)
        attempts.append(
            {
                "attempt": attempt,
                "results": dict(results),
                "errors": list(errors),
                "total_bytes": total_bytes,
                "total_lines": total_lines,
                "thing_name": thing_name,
                "certificate_id": certificate_id,
                "tls_versions_seen": list(tls_versions),
                "tls_version_ok": tls_ok,
                "tls_events": list(tls_events),
            }
        )
        if all(results.values()):
            break
        retryable = retryable_startup_failure(
            errors,
            results,
            thing_name,
            certificate_id,
        )
        if not retryable or attempt > args.app_reset_retries:
            break

    completed = all(results.values()) and tls_requirement_ok(require_tls_version, tls_versions)
    summary = make_summary(
        success=completed,
        results=results,
        errors=errors,
        total_bytes=total_bytes,
        total_lines=total_lines,
        thing_name=thing_name,
        certificate_id=certificate_id,
        require_tls_version=require_tls_version,
        tls_versions=tls_versions,
        tls_events=tls_events,
        attempts=attempts,
        partial=False,
    )
    if args.summary_json:
        write_json_atomic(args.summary_json, summary)
    if args.junit_output:
        write_junit(args.junit_output, args.label, summary)

    print()
    print("=" * 60)
    print(f"RX total: {total_bytes} bytes / {total_lines} lines")
    print(f"Thing name: {thing_name or '(not observed)'}")
    print(f"Certificate ID: {certificate_id or '(not observed)'}")
    print(f"TLS versions: {', '.join(tls_versions) or '(none)'}")
    if require_tls_version:
        status = "PASS" if tls_requirement_ok(require_tls_version, tls_versions) else "FAIL"
        print(f"[{status}] Required TLS version: {require_tls_version}")
    for name, _ in MARKERS:
        print(f"[{'PASS' if results[name] else 'FAIL'}] {name}")
    if errors:
        print("Non-fatal errors observed before completion:" if completed else "Errors:")
        for line in errors[:10]:
            print(f"  - {line}")
    print("=" * 60)

    if completed:
        print(f"[PASS] {args.label} Fleet Provisioning demo verified")
        return 0

    print(f"[FAIL] {args.label} Fleet Provisioning demo incomplete")
    return 1


if __name__ == "__main__":
    sys.exit(main())

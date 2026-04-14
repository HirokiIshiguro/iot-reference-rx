#!/usr/bin/env python3
"""
Monitor RX72N UART logs and verify the Fleet Provisioning demo completes.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


DEFAULT_LOG_PORT = os.environ.get("RX72N_LOG_PORT", os.environ.get("UART_PORT", "COM7"))
DEFAULT_LOG_BAUD = int(os.environ.get("UART_BAUD_RATE", "921600"))
DEFAULT_TIMEOUT = 240

MARKERS = [
    ("claim_mqtt", "Established connection with claim credentials."),
    ("certificate", "Received certificate with Id:"),
    ("thing_name", "Received AWS IoT Thing name:"),
    ("provisioned_mqtt", "Sucessfully established connection with provisioned credentials."),
    ("complete", "Demo completed successfully."),
]

ERROR_PATTERNS = [
    "Failed to establish MQTT session",
    "Failed to publish to fleet provisioning topic",
    "Failed to parse the CreateCertificatefromCsr API response",
    "Failed to parse the RegisterThing API response",
    "Failed to establish MQTT session with provisioned credentials",
    "All 3 demo iterations failed.",
    "Error:",
]


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
        progress_re = re.compile(r"^\\d+%\\s*\\[")
        for line in result.stderr.strip().splitlines():
            stripped = line.strip()
            if stripped and not progress_re.match(stripped):
                print(f"  [reset-cmd stderr] {stripped}")

    if result.returncode != 0:
        print(f"  ERROR: Reset command exited with code {result.returncode}")
        return False

    print("  Reset command completed successfully")
    return True


def monitor_uart(port, baud, timeout, reset_cmd):
    results = {name: False for name, _ in MARKERS}
    errors = []
    certificate_id = None
    thing_name = None
    total_bytes = 0
    total_lines = 0
    buffer = ""

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

                    for name, pattern in MARKERS:
                        if (not results[name]) and pattern in line:
                            results[name] = True
                            print(f"[MILESTONE] {name}: {line}")

                    if "Received certificate with Id:" in line:
                        certificate_id = line.split("Received certificate with Id:", 1)[1].strip()
                    if "Received AWS IoT Thing name:" in line:
                        thing_name = line.split("Received AWS IoT Thing name:", 1)[1].strip()

                    for pattern in ERROR_PATTERNS:
                        if pattern in line:
                            errors.append(line)
                            print(f"[ERROR] {line}")

                if all(results.values()):
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

    return results, errors, total_bytes, total_lines, thing_name, certificate_id


def main():
    parser = argparse.ArgumentParser(description="Verify RX72N Fleet Provisioning demo from log UART")
    parser.add_argument("--log-port", default=DEFAULT_LOG_PORT)
    parser.add_argument("--log-baud", type=int, default=DEFAULT_LOG_BAUD)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--reset-cmd", required=True)
    parser.add_argument("--summary-json", help="Optional path to write fleet provisioning summary JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("RX72N Fleet Provisioning Test")
    print("=" * 60)
    print(f"Log Port: {args.log_port}")
    print(f"Log Baud: {args.log_baud}")
    print(f"Timeout:  {args.timeout}s")
    print("=" * 60)

    results, errors, total_bytes, total_lines, thing_name, certificate_id = monitor_uart(
        args.log_port,
        args.log_baud,
        args.timeout,
        args.reset_cmd,
    )

    summary = {
        "results": results,
        "errors": errors,
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "thing_name": thing_name,
        "certificate_id": certificate_id,
    }
    if args.summary_json:
        with open(args.summary_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=True)
            handle.write("\n")

    print()
    print("=" * 60)
    print(f"RX total: {total_bytes} bytes / {total_lines} lines")
    print(f"Thing name: {thing_name or '(not observed)'}")
    print(f"Certificate ID: {certificate_id or '(not observed)'}")
    for name, _ in MARKERS:
        print(f"[{'PASS' if results[name] else 'FAIL'}] {name}")
    if errors:
        print("Errors:")
        for line in errors[:10]:
            print(f"  - {line}")
    print("=" * 60)

    if all(results.values()) and not errors:
        print("[PASS] RX72N Fleet Provisioning demo verified")
        return 0

    print("[FAIL] RX72N Fleet Provisioning demo incomplete")
    return 1


if __name__ == "__main__":
    sys.exit(main())

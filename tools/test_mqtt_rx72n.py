#!/usr/bin/env python3
"""
Monitor phase8b UART logs and verify that the MQTT demo reaches steady state.

The phase8b baseline uses a short-lived CLI window on the command UART, so the
recommended CI flow is:
1. Provision in a separate job with an external reset command.
2. Open the dedicated log UART (CN6 / SCI7).
3. Trigger a fresh reset with `rfp-cli ... -run -noquery`.
4. Monitor the full boot and MQTT demo output from the log UART only.
"""

import argparse
import os
import re
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, errors="backslashreplace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "test_scripts"))

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

from device_config_loader import load_device_config


DEFAULT_LOG_PORT = os.environ.get("RX72N_LOG_PORT", os.environ.get("UART_PORT", "COM7"))
DEFAULT_LOG_BAUD = int(os.environ.get("UART_BAUD_RATE", "921600"))
DEFAULT_TIMEOUT = 150

MARKERS = [
    {
        "name": "IP Address",
        "pattern": "IP Address:",
        "required": True,
    },
    {
        "name": "MQTT Receive",
        "pattern": "Incoming PUBLISH received on topic $aws/things/",
        "required": True,
    },
    {
        "name": "Topic Subscribe",
        "pattern": "Successfully subscribed to topic",
        "required": True,
    },
    {
        "name": "MQTT Publish",
        "pattern": "Successfully sent QoS",
        "required": True,
    },
]

INFO_MARKERS = [
    "Creating a TLS connection",
    "A clean MQTT connection is established.",
]

TLS13_RESUMPTION_NO_TICKET_MARKER = "TLS 1.3 resumption requested: no stored session ticket."
TLS13_RESUMPTION_REQUEST_MARKER = "TLS 1.3 resumption requested with stored session ticket"
TLS13_RESUMPTION_TICKET_MARKER = "TLS 1.3 resumption ticket stored"
TLS13_RESUMPTION_RECONNECT_MARKER = "TLS 1.3 resumption test: reconnecting MQTT broker"

PKCS11_SIGN_MARKERS = [
    "P11:ECDSA:SignInit>",
    "P11:ECDSA:Sign>",
    "P11:RSA:SWSignSHA256>",
    "PKCS11 sign trace:",
]

BOOT_MARKERS = [
    "BootLoader",
    "execute image",
    "send image",
    "jump to user program",
    "error occurred",
    "software reset",
    "activating image",
]

APP_START_MARKERS = [
    "FreeRTOS command server.",
    "Press CLI and enter to switch to CLI mode",
    "IP Address:",
    "Creating a TLS connection",
    "A clean MQTT connection is established.",
]

ERROR_PATTERNS = [
    "Failed to connect to MQTT broker",
    "Connection to the broker failed, all attempts exhausted",
    "Failed to subscribe to topic",
    "DHCP failed",
    "Network connection failed",
    "TLS connection failed",
    "DNS resolution failed",
    "error occurred. please reset your board",
]


def open_serial_port(port, baud):
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {port}: {e}")
        return None

    print(f"Serial port {port} opened @ {baud}bps")
    return ser


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
    except Exception as e:
        print(f"  ERROR: Reset command failed: {e}")
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
        print(f"  WARNING: Reset command exited with code {result.returncode}")
        return False

    print("  Reset command completed successfully")
    return True


def monitor_uart(port, baud, timeout, reset_cmd=None, app_startup_timeout=45.0, require_tls13_resumption=False):
    results = {marker["name"]: False for marker in MARKERS}
    infos = []
    errors = []
    tls_versions = []
    resumption = {
        "initial_no_ticket": False,
        "ticket_stored": False,
        "reconnect_requested": False,
        "resumption_requested": False,
        "second_handshake_seen": False,
        "sign_after_request": 0,
        "accepted_without_client_sign": False,
    }
    total_bytes = 0
    total_lines = 0
    boot_lines = []
    buffer = ""
    jump_to_app_time = None
    app_output_seen = False

    ser = open_serial_port(port, baud)
    if ser is None:
        return results, infos, errors, [], resumption, total_bytes, total_lines, boot_lines, app_output_seen

    try:
        ser.reset_input_buffer()

        if reset_cmd:
            print("Issuing external reset while keeping log UART open...")
            if not reset_device_via_command(reset_cmd):
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

                    for boot_marker in BOOT_MARKERS:
                        if boot_marker in line:
                            boot_lines.append(line)
                            if boot_marker == "jump to user program":
                                jump_to_app_time = time.time()
                            break

                    if any(marker in line for marker in APP_START_MARKERS):
                        app_output_seen = True

                    for marker in MARKERS:
                        if not results[marker["name"]] and marker["pattern"] in line:
                            results[marker["name"]] = True
                            print(f"[MILESTONE] {marker['name']}: {line}")

                    for info_marker in INFO_MARKERS:
                        if info_marker in line and line not in infos:
                            infos.append(line)
                            print(f"[INFO] {line}")

                    if TLS13_RESUMPTION_NO_TICKET_MARKER in line:
                        resumption["initial_no_ticket"] = True
                        print("[INFO] TLS 1.3 resumption: first full handshake has no stored ticket yet")

                    if TLS13_RESUMPTION_TICKET_MARKER in line:
                        resumption["ticket_stored"] = True
                        print(f"[INFO] TLS 1.3 resumption ticket: {line}")

                    if TLS13_RESUMPTION_RECONNECT_MARKER in line:
                        resumption["reconnect_requested"] = True
                        print("[INFO] TLS 1.3 resumption reconnect requested")

                    if TLS13_RESUMPTION_REQUEST_MARKER in line:
                        resumption["resumption_requested"] = True
                        resumption["sign_after_request"] = 0
                        resumption["second_handshake_seen"] = False
                        print(f"[INFO] TLS 1.3 resumption requested: {line}")

                    if resumption["resumption_requested"] and any(
                        sign_marker in line for sign_marker in PKCS11_SIGN_MARKERS
                    ):
                        resumption["sign_after_request"] += 1

                    tls_match = re.search(r"TLS handshake successful: version\s+(\S+)", line)
                    if tls_match:
                        tls_version = tls_match.group(1)
                        tls_versions.append(tls_version)
                        print(f"[INFO] TLS version: {tls_version}")

                        if resumption["resumption_requested"] and not resumption["second_handshake_seen"]:
                            resumption["second_handshake_seen"] = True
                            if "TLSv1.3" in tls_version and resumption["sign_after_request"] == 0:
                                resumption["accepted_without_client_sign"] = True
                                print(
                                    "[MILESTONE] TLS 1.3 resumption accepted "
                                    "without a second client certificate signature"
                                )

                    for error_pattern in ERROR_PATTERNS:
                        if error_pattern in line:
                            errors.append(line)
                            print(f"[ERROR] {line}")

                if all(results.values()) and (
                    not require_tls13_resumption or resumption["accepted_without_client_sign"]
                ):
                    break
            else:
                time.sleep(0.05)

            if (
                app_startup_timeout > 0
                and jump_to_app_time is not None
                and not app_output_seen
                and time.time() - jump_to_app_time >= app_startup_timeout
            ):
                diag = (
                    "Application output did not appear after bootloader "
                    f"'jump to user program' within {app_startup_timeout:.0f}s"
                )
                errors.append(diag)
                print(f"[ERROR] {diag}")
                break

            elapsed = time.time() - start
            if int(elapsed) // 30 > last_status:
                last_status = int(elapsed) // 30
                detected = sum(1 for ok in results.values() if ok)
                print(f"[STATUS] {elapsed:.0f}s elapsed: {detected}/{len(results)} markers, RX={total_bytes} bytes")
    finally:
        ser.close()
        print(f"Closed {port}")

    return results, infos, errors, tls_versions, resumption, total_bytes, total_lines, boot_lines, app_output_seen


def main():
    parser = argparse.ArgumentParser(
        description="Verify phase8b MQTT baseline from dedicated log UART"
    )
    parser.add_argument("--device-id", help="Device ID (loads config from device_config.json)")
    parser.add_argument("--log-port", default=DEFAULT_LOG_PORT,
                        help=f"Log serial port (default: {DEFAULT_LOG_PORT})")
    parser.add_argument("--log-baud", type=int, default=DEFAULT_LOG_BAUD,
                        help=f"Log baud rate (default: {DEFAULT_LOG_BAUD})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Overall timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--app-startup-timeout", type=float, default=45.0,
                        help="Seconds to wait for application UART output after bootloader jump (0 disables)")
    parser.add_argument("--reset-cmd",
                        help="External reset command to execute while the log port is open")
    parser.add_argument("--no-reset", action="store_true",
                        help="Skip reset and only monitor the current UART stream")
    parser.add_argument("--require-tls-version",
                        help="Require the logged TLS handshake version to contain this string")
    parser.add_argument("--require-tls13-resumption", action="store_true",
                        help="Require TLS 1.3 session ticket resumption on a second MQTT connection")
    args = parser.parse_args()

    if args.device_id:
        device = load_device_config(args.device_id)
        print(f"Loaded config for device: {args.device_id}")
        if args.log_port == DEFAULT_LOG_PORT:
            args.log_port = device.get("log_port") or os.environ.get("UART_PORT") or DEFAULT_LOG_PORT
        if args.log_baud == DEFAULT_LOG_BAUD:
            args.log_baud = int(device.get("log_baud") or os.environ.get("UART_BAUD_RATE") or DEFAULT_LOG_BAUD)

    if not args.no_reset and not args.reset_cmd:
        parser.error("--reset-cmd is required unless --no-reset is specified")

    print("=" * 60)
    print("phase8b MQTT Connectivity Test")
    print("=" * 60)
    print(f"Log Port:    {args.log_port}")
    print(f"Log Baud:    {args.log_baud}")
    print(f"Timeout:     {args.timeout}s")
    print(f"App Startup: {args.app_startup_timeout}s after bootloader jump")
    print(f"Reset Mode:  {'external reset command' if args.reset_cmd else 'monitor only'}")
    print("=" * 60)

    results, infos, errors, tls_versions, resumption, total_bytes, total_lines, boot_lines, app_output_seen = monitor_uart(
        args.log_port,
        args.log_baud,
        args.timeout,
        reset_cmd=None if args.no_reset else args.reset_cmd,
        app_startup_timeout=args.app_startup_timeout,
        require_tls13_resumption=args.require_tls13_resumption,
    )

    print()
    print("=" * 60)
    print(f"RX total: {total_bytes} bytes / {total_lines} lines")
    for marker in MARKERS:
        status = "PASS" if results[marker["name"]] else "FAIL"
        print(f"[{status}] {marker['name']}")
    if infos:
        print("Info markers:")
        for line in infos[:5]:
            print(f"  - {line}")
    if tls_versions:
        print("TLS versions:")
        for tls_version in tls_versions[:5]:
            print(f"  - {tls_version}")
    if args.require_tls13_resumption:
        print("TLS 1.3 resumption:")
        print(f"  - initial_no_ticket={resumption['initial_no_ticket']}")
        print(f"  - ticket_stored={resumption['ticket_stored']}")
        print(f"  - reconnect_requested={resumption['reconnect_requested']}")
        print(f"  - resumption_requested={resumption['resumption_requested']}")
        print(f"  - second_handshake_seen={resumption['second_handshake_seen']}")
        print(f"  - sign_after_request={resumption['sign_after_request']}")
        print(f"  - accepted_without_client_sign={resumption['accepted_without_client_sign']}")
    if errors:
        print("Errors:")
        for line in errors[:5]:
            print(f"  - {line}")
    if boot_lines:
        print("Boot markers:")
        for line in boot_lines[:5]:
            print(f"  - {line}")
    print("=" * 60)

    tls_ok = True
    if args.require_tls_version:
        tls_ok = any(args.require_tls_version in tls_version for tls_version in tls_versions)
        status = "PASS" if tls_ok else "FAIL"
        print(f"[{status}] Required TLS version: {args.require_tls_version}")

    resumption_ok = True
    if args.require_tls13_resumption:
        resumption_ok = resumption["accepted_without_client_sign"]
        status = "PASS" if resumption_ok else "FAIL"
        print(f"[{status}] TLS 1.3 session ticket resumption")

    if all(results.values()) and tls_ok and resumption_ok:
        print("[PASS] phase8b MQTT baseline verified")
        return 0

    print("[FAIL] phase8b MQTT baseline incomplete")
    if total_bytes == 0:
        print("[DIAG] No UART bytes were captured on the dedicated log port.")
    if (not app_output_seen) and any("jump to user program" in line for line in boot_lines):
        print("[DIAG] Bootloader jumped to the user program, but no application startup marker was captured.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

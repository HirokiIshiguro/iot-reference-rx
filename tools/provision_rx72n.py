#!/usr/bin/env python3
"""
Provision phase8b credentials to RX72N Envision Kit over the short-lived CLI.

This is the RX72N-specific variant of the iot-reference-rx provisioning flow.
The phase8b firmware exposes the FreeRTOS CLI for roughly 10 seconds after boot,
so CI sometimes needs to open the UART first and then reset the device to catch
the short-lived CLI window.
"""

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "provisioning"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "test_scripts"))

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

from provisioning.security import mask_sensitive_output
from device_config_loader import load_device_config, get_cert_env_var_name, get_key_env_var_name


# phase8b app の短時間 CLI は SCI7 / CN6 のログ UART と共用される。
DEFAULT_PORT = os.environ.get("RX72N_LOG_PORT", os.environ.get("UART_PORT", "COM7"))
DEFAULT_BAUD = int(os.environ.get("UART_BAUD_RATE", "921600"))
DEFAULT_CHAR_DELAY = 0.002
DEFAULT_LINE_DELAY = 0.5
DEFAULT_BOOT_WAIT = 3.0
DEFAULT_CLI_TIMEOUT = 15.0
DEFAULT_CLI_RETRY_INTERVAL = 1.0
DEFAULT_COMMIT_TIMEOUT = 15.0
DEFAULT_SHADOW_BAUD = int(os.environ.get("COMMAND_BAUD_RATE", "115200"))
CLI_READY_MARKERS = ("Going to FreeRTOS-CLI",)
CLI_INVITE_MARKERS = (
    "Press CLI and enter to switch to CLI mode",
    "FreeRTOS command server.",
)
BOOTLOADER_MARKERS = (
    "send image(*.rsu) via UART.",
    "send \"userprog.rsu\" via UART.",
    "error occurred. please reset your board.",
)


def send_chars(ser, text, char_delay):
    for ch in text:
        ser.write(ch.encode("ascii"))
        time.sleep(char_delay)


def send_command(ser, command, char_delay, line_delay, expect_ok=True, required_tokens=None):
    ser.reset_input_buffer()
    send_chars(ser, command, char_delay)
    ser.write(b"\r\n")
    time.sleep(line_delay)
    response = ser.read(ser.in_waiting or 1024).decode("ascii", errors="replace")

    if expect_ok and "Error" in response:
        print(f"  ERROR in response: {mask_sensitive_output(response.strip())}")
        return None

    if required_tokens and not any(token in response for token in required_tokens):
        print(f"  ERROR: expected one of {required_tokens}, got: {mask_sensitive_output(response.strip()) or 'No response'}")
        return None

    return response


def send_pem_command(ser, key_name, pem_path, char_delay, line_delay):
    with open(pem_path, "r", encoding="utf-8") as f:
        pem_content = f.read()

    pem_content = pem_content.replace("\r\n", "\n").replace("\r", "\n").strip()
    total_len = len(f"conf set {key_name} ") + len(pem_content)
    if total_len > 4090:
        print(f"  WARNING: Command length ({total_len}) near buffer limit (4096)")

    print(f"  Sending: conf set {key_name} <{pem_path}> ({len(pem_content)} bytes)")
    send_chars(ser, f"conf set {key_name} ", char_delay)
    send_chars(ser, pem_content, char_delay)
    ser.write(b"\r\n")
    time.sleep(line_delay)
    response = ser.read(ser.in_waiting or 1024).decode("ascii", errors="replace")

    if "OK" in response:
        print("  OK")
        return True
    if "Error" in response:
        print(f"  ERROR: {mask_sensitive_output(response.strip())}")
        return False

    print(f"  ERROR: unexpected response: {mask_sensitive_output(response.strip()) or 'No response'}")
    return False


def wait_for_response_tokens(ser, timeout, success_tokens, error_tokens=("Error",)):
    start = time.time()
    collected = ""

    while time.time() - start < timeout:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
            collected += data
            sys.stdout.write(mask_sensitive_output(data))
            sys.stdout.flush()

            if any(token in collected for token in error_tokens):
                return None

            if any(token in collected for token in success_tokens):
                return collected

        time.sleep(0.1)

    return None


def wait_for_boot(ser, timeout, shadow_ser=None, shadow_name="shadow", stop_tokens=None):
    print(f"Waiting for device boot ({timeout}s timeout)...")
    start = time.time()
    collected = ""
    shadow_collected = ""
    while time.time() - start < timeout:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
            collected += data
            sys.stdout.write(mask_sensitive_output(data))
            sys.stdout.flush()
            if stop_tokens and any(token in collected for token in stop_tokens):
                break
        shadow_collected = read_shadow_data(shadow_ser, shadow_name, shadow_collected)
        time.sleep(0.1)
    return collected, shadow_collected


def read_shadow_data(shadow_ser, shadow_name, collected):
    if not shadow_ser or not shadow_ser.in_waiting:
        return collected

    data = shadow_ser.read(shadow_ser.in_waiting).decode("ascii", errors="replace")
    collected += data
    sys.stdout.write(f"[{shadow_name}] {mask_sensitive_output(data)}")
    sys.stdout.flush()
    return collected


def run_reset_command(reset_cmd, description):
    print(description)
    result = subprocess.run(reset_cmd, shell=True)
    if result.returncode != 0:
        print(f"ERROR: reset command failed with exit code {result.returncode}")
        return False
    return True


def enter_cli_mode(ser, char_delay, line_delay, timeout, retry_interval, shadow_ser=None, shadow_name="shadow", initial_output=""):
    print("Entering CLI mode...")
    shadow_collected = ""
    shadow_bootloader_reported = False

    start = time.monotonic()
    collected = initial_output or ""

    if any(marker in collected for marker in CLI_READY_MARKERS):
        print("CLI prompt already detected")
        return True
    if any(marker in collected for marker in BOOTLOADER_MARKERS):
        print("ERROR: boot_loader responded on the log UART; phase8b app CLI is not active")
        return False

    next_retry = start
    attempt = 0
    while time.monotonic() - start < timeout:
        now = time.monotonic()
        if now >= next_retry:
            attempt += 1
            if attempt > 1:
                print(f"  Retrying CLI wake-up ({attempt})...")
            send_chars(ser, "CLI", char_delay)
            ser.write(b"\r\n")
            time.sleep(line_delay)
            next_retry = now + retry_interval
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
            collected += data
            sys.stdout.write(mask_sensitive_output(data))
            sys.stdout.flush()
            if any(marker in collected for marker in CLI_READY_MARKERS):
                print("\nCLI mode entered successfully")
                return True
            if any(marker in collected for marker in BOOTLOADER_MARKERS):
                print("\nERROR: boot_loader responded on the log UART; phase8b app CLI is not active")
                return False
        shadow_collected = read_shadow_data(shadow_ser, shadow_name, shadow_collected)
        if shadow_collected:
            if any(marker in shadow_collected for marker in CLI_READY_MARKERS):
                print(f"\nERROR: CLI markers were observed on {shadow_name} instead of the log UART")
                return False
            if (not shadow_bootloader_reported) and any(marker in shadow_collected for marker in BOOTLOADER_MARKERS):
                print(f"\nWARNING: boot_loader banner was observed on {shadow_name}")
                shadow_bootloader_reported = True
        time.sleep(0.1)

    print("\nERROR: CLI prompt not detected")
    return False


def resolve_device_args(args, parser):
    if args.device_id:
        device = load_device_config(args.device_id)
        print(f"Loaded config for device: {args.device_id}")

        if args.port == DEFAULT_PORT:
            args.port = device.get("log_port") or os.environ.get("UART_PORT") or DEFAULT_PORT
        if args.baud == DEFAULT_BAUD:
            args.baud = int(device.get("log_baud") or os.environ.get("UART_BAUD_RATE") or DEFAULT_BAUD)
        if not args.endpoint:
            args.endpoint = device["aws_endpoint"]
        if not args.thing_name:
            args.thing_name = device["thing_name"]
        if not args.cert:
            cert_var = get_cert_env_var_name(args.device_id)
            args.cert = os.environ.get(cert_var)
            if not args.cert:
                parser.error(f"Environment variable {cert_var} not set")
            print(f"Certificate path from ${cert_var}")
        if not args.key:
            key_var = get_key_env_var_name(args.device_id)
            args.key = os.environ.get(key_var)
            if not args.key:
                parser.error(f"Environment variable {key_var} not set")
            print(f"Private key path from ${key_var}")
        if not args.codesigner_cert and device.get("codesigner_cert"):
            repo_root = os.path.dirname(os.path.dirname(__file__))
            candidate = os.path.join(repo_root, device["codesigner_cert"])
            if os.path.isfile(candidate):
                args.codesigner_cert = candidate
                print(f"Code signer cert from device_config: {candidate}")

    if not args.endpoint:
        parser.error("--endpoint is required (or use --device-id)")
    if not args.thing_name:
        parser.error("--thing-name is required (or use --device-id)")
    if not args.cert:
        parser.error("--cert is required (or use --device-id)")
    if not args.key:
        parser.error("--key is required (or use --device-id)")

    for path, desc in ((args.cert, "Certificate"), (args.key, "Private key")):
        if not os.path.isfile(path):
            parser.error(f"{desc} file not found: {path}")
    if args.codesigner_cert and not os.path.isfile(args.codesigner_cert):
        parser.error(f"Code signer certificate file not found: {args.codesigner_cert}")


def provision(args):
    print("=" * 60)
    print("phase8b Device Provisioning")
    print("=" * 60)
    print(f"Port:       {args.port}")
    print(f"Baud:       {args.baud}")
    print(f"Thing Name: {args.thing_name}")
    print(f"Endpoint:   {args.endpoint}")
    print(f"Cert:       {args.cert}")
    print(f"Key:        {args.key}")
    if args.shadow_port:
        print(f"Shadow Port:{args.shadow_port} @ {args.shadow_baud}")
    if args.codesigner_cert:
        print(f"Code Sign:  {args.codesigner_cert}")
    if args.reset_cmd:
        print(f"Reset cmd:  {args.reset_cmd}")
    if args.reset_after_open:
        print("Reset mode: after opening serial")
    print("=" * 60)

    if args.reset_cmd and not args.reset_after_open:
        if not run_reset_command(args.reset_cmd, "Running external reset command before opening serial..."):
            return 1

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
        )
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {args.port}: {e}")
        return 1

    print(f"Serial port {args.port} opened")
    shadow_ser = None
    if args.shadow_port:
        try:
            shadow_ser = serial.Serial(
                port=args.shadow_port,
                baudrate=args.shadow_baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0,
            )
        except serial.SerialException as e:
            ser.close()
            print(f"ERROR: Cannot open shadow port {args.shadow_port}: {e}")
            return 1
        print(f"Shadow serial port {args.shadow_port} opened")

    try:
        if args.reset_cmd and args.reset_after_open:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            if shadow_ser:
                shadow_ser.reset_input_buffer()
                shadow_ser.reset_output_buffer()
            if not run_reset_command(args.reset_cmd, "Running external reset command after opening serial..."):
                return 1

        boot_output = ""
        if not args.skip_boot_wait:
            boot_output, _ = wait_for_boot(
                ser,
                args.boot_wait,
                shadow_ser=shadow_ser,
                shadow_name=args.shadow_name,
                stop_tokens=CLI_INVITE_MARKERS + CLI_READY_MARKERS,
            )

        if not enter_cli_mode(
            ser,
            args.char_delay,
            args.line_delay,
            args.cli_timeout,
            args.cli_retry_interval,
            shadow_ser=shadow_ser,
            shadow_name=args.shadow_name,
            initial_output=boot_output,
        ):
            print("ERROR: Failed to enter CLI mode")
            return 1

        if args.format:
            print("\n--- Format data flash ---")
            resp = send_command(ser, "format", args.char_delay, args.line_delay * 2,
                                required_tokens=("OK",))
            if resp and "OK" in str(resp):
                print("  Format OK")
            else:
                print(f"  Format response: {mask_sensitive_output(str(resp).strip()) if resp else 'No response'}")

        print(f"\n--- Set thing name: {args.thing_name} ---")
        if send_command(ser, f"conf set thingname {args.thing_name}",
                        args.char_delay, args.line_delay, required_tokens=("OK",)) is None:
            return 1

        print(f"\n--- Set endpoint: {args.endpoint} ---")
        if send_command(ser, f"conf set endpoint {args.endpoint}",
                        args.char_delay, args.line_delay, required_tokens=("OK",)) is None:
            return 1

        print("\n--- Set device certificate ---")
        if not send_pem_command(ser, "cert", args.cert, args.char_delay, args.line_delay):
            return 1

        print("\n--- Set private key ---")
        if not send_pem_command(ser, "key", args.key, args.char_delay, args.line_delay):
            return 1

        if args.codesigner_cert:
            print("\n--- Set code signing certificate ---")
            if not send_pem_command(ser, "codesigncert", args.codesigner_cert, args.char_delay, args.line_delay):
                return 1
        else:
            print("\nWARNING: No code signing certificate provided; OTA signature verification will fail")

        print("\n--- Commit to data flash ---")
        ser.reset_input_buffer()
        send_chars(ser, "conf commit", args.char_delay)
        ser.write(b"\r\n")
        time.sleep(args.line_delay)
        resp = wait_for_response_tokens(
            ser,
            args.commit_timeout,
            success_tokens=("Configuration save", "\r\n>", "\n>"),
        )
        if resp is None:
            return 1
        print(f"  {mask_sensitive_output(resp.strip()) if resp else 'No response'}")

        if not args.no_reset:
            print("\n--- Reset device ---")
            send_command(ser, "reset", args.char_delay, args.line_delay, expect_ok=False)
            print("  Reset command sent")
            if not args.quiet:
                print("\n--- Device boot output ---")
                wait_for_boot(ser, 5.0, shadow_ser=shadow_ser, shadow_name=args.shadow_name)
    finally:
        if shadow_ser:
            shadow_ser.close()
            print(f"Shadow serial port {args.shadow_port} closed")
        ser.close()
        print(f"\nSerial port {args.port} closed")

    print("\n" + "=" * 60)
    print("PROVISIONING COMPLETE")
    print("=" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Provision AWS IoT credentials to phase8b RX72N via UART CLI"
    )
    parser.add_argument("--device-id", help="Device ID (loads config from device_config.json)")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate (default: {DEFAULT_BAUD})")
    parser.add_argument("--thing-name", help="AWS IoT Thing name")
    parser.add_argument("--endpoint", help="AWS IoT MQTT endpoint URL")
    parser.add_argument("--cert", help="Path to device certificate PEM file")
    parser.add_argument("--key", help="Path to device private key PEM file")
    parser.add_argument("--codesigner-cert", help="Path to OTA code signing certificate PEM file")
    parser.add_argument("--char-delay", type=float, default=DEFAULT_CHAR_DELAY,
                        help=f"Delay between characters in seconds (default: {DEFAULT_CHAR_DELAY})")
    parser.add_argument("--line-delay", type=float, default=DEFAULT_LINE_DELAY,
                        help=f"Delay after each command in seconds (default: {DEFAULT_LINE_DELAY})")
    parser.add_argument("--boot-wait", type=float, default=DEFAULT_BOOT_WAIT,
                        help=f"Seconds to wait for boot messages (default: {DEFAULT_BOOT_WAIT})")
    parser.add_argument("--cli-timeout", type=float, default=DEFAULT_CLI_TIMEOUT,
                        help=f"Seconds to wait for CLI prompt (default: {DEFAULT_CLI_TIMEOUT})")
    parser.add_argument("--cli-retry-interval", type=float, default=DEFAULT_CLI_RETRY_INTERVAL,
                        help=f"Seconds between repeated CLI wake-up sends (default: {DEFAULT_CLI_RETRY_INTERVAL})")
    parser.add_argument("--commit-timeout", type=float, default=DEFAULT_COMMIT_TIMEOUT,
                        help=f"Seconds to wait for conf commit completion (default: {DEFAULT_COMMIT_TIMEOUT})")
    parser.add_argument("--reset-cmd", help="External reset/run command executed before or after opening UART")
    parser.add_argument("--reset-after-open", action="store_true",
                        help="Open UART first, then execute --reset-cmd to capture the short CLI window")
    parser.add_argument("--shadow-port", help="Optional secondary UART to monitor during boot/CLI capture")
    parser.add_argument("--shadow-baud", type=int, default=DEFAULT_SHADOW_BAUD,
                        help=f"Secondary UART baud rate (default: {DEFAULT_SHADOW_BAUD})")
    parser.add_argument("--shadow-name", default="shadow",
                        help="Label used when printing secondary UART output")
    parser.add_argument("--format", action="store_true", help="Format data flash before provisioning")
    parser.add_argument("--no-reset", action="store_true", help="Do not reset device after provisioning")
    parser.add_argument("--skip-boot-wait", action="store_true",
                        help="Skip waiting for boot messages (device already in CLI mode)")
    parser.add_argument("--quiet", action="store_true", help="Suppress boot output after reset")
    args = parser.parse_args()

    resolve_device_args(args, parser)
    return provision(args)


if __name__ == "__main__":
    sys.exit(main())

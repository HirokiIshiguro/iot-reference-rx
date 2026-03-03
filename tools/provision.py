#!/usr/bin/env python3
"""
UART provisioning script for iot-reference-rx (CK-RX65N).

Sends AWS IoT credentials to the device via the FreeRTOS CLI over serial.
The firmware must be flashed and the device must be reset before running
this script — the CLI window is available for ~10 seconds after boot.

Usage:
    python tools/provision.py \
        --port COM9 --baud 115200 \
        --thing-name ck-rx65n-01 \
        --endpoint xxxxx-ats.iot.ap-northeast-1.amazonaws.com \
        --cert certs/ck-rx65n-01-cert.pem \
        --key certs/ck-rx65n-01-privkey.pem

PEM file handling:
    The FreeRTOS CLI accumulates characters until \\r\\n.
    Bare \\n (without preceding \\r) is treated as a regular character.
    PEM content is sent with \\n line endings so the entire content
    becomes part of a single 'conf set' command line (max 4096 bytes).
    FreeRTOS_CLIGetParameter has special handling for spaces in PEM
    headers (BEGIN CERTIFICATE, etc.).

Dependencies:
    pip install pyserial
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


DEFAULT_CHAR_DELAY = 0.002   # 2ms between characters (safe for 115200bps)
DEFAULT_LINE_DELAY = 0.5     # 500ms after each command
DEFAULT_BOOT_WAIT = 3.0      # seconds to wait for boot messages
DEFAULT_CLI_TIMEOUT = 15.0   # seconds to wait for CLI prompt


def send_chars(ser, text, char_delay):
    """Send text character by character with delay."""
    for ch in text:
        ser.write(ch.encode('ascii'))
        time.sleep(char_delay)


def send_command(ser, command, char_delay, line_delay, expect_ok=True):
    """Send a CLI command and wait for response."""
    # Drain any pending input
    ser.reset_input_buffer()

    # Send command character by character
    send_chars(ser, command, char_delay)

    # Terminate with \r\n
    ser.write(b'\r\n')
    time.sleep(line_delay)

    # Read response
    response = ser.read(ser.in_waiting or 1024).decode('ascii', errors='replace')

    if expect_ok and 'Error' in response:
        print(f"  ERROR in response: {response.strip()}")
        return False

    return response


def send_pem_command(ser, key_name, pem_path, char_delay, line_delay):
    """Send a conf set command with PEM file content."""
    # Read PEM file and ensure Unix line endings
    with open(pem_path, 'r') as f:
        pem_content = f.read()

    # Strip \r to ensure only \n line endings
    # (bare \n is accumulated as regular char in FreeRTOS CLI buffer)
    pem_content = pem_content.replace('\r\n', '\n').replace('\r', '\n')
    pem_content = pem_content.strip()

    total_len = len(f'conf set {key_name} ') + len(pem_content)
    if total_len > 4090:  # cmdMAX_INPUT_SIZE = 4096, leave margin
        print(f"  WARNING: Command length ({total_len}) near buffer limit (4096)")

    print(f"  Sending: conf set {key_name} <{pem_path}> ({len(pem_content)} bytes)")

    # Send command prefix
    send_chars(ser, f'conf set {key_name} ', char_delay)

    # Send PEM content (with \n, not \r\n)
    send_chars(ser, pem_content, char_delay)

    # Terminate command with \r\n
    ser.write(b'\r\n')
    time.sleep(line_delay)

    # Read response
    response = ser.read(ser.in_waiting or 1024).decode('ascii', errors='replace')

    if 'OK' in response:
        print(f"  OK")
        return True
    elif 'Error' in response:
        print(f"  ERROR: {response.strip()}")
        return False
    else:
        print(f"  Response: {response.strip()}")
        return True  # Might be OK without explicit "OK" text


def wait_for_boot(ser, timeout):
    """Wait for device boot messages on UART."""
    print(f"Waiting for device boot ({timeout}s timeout)...")
    start = time.time()
    collected = ""
    while time.time() - start < timeout:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode('ascii', errors='replace')
            collected += data
            sys.stdout.write(data)
            sys.stdout.flush()
        time.sleep(0.1)
    return collected


def enter_cli_mode(ser, char_delay, line_delay, timeout):
    """Enter CLI mode by sending 'CLI' command within the boot window."""
    print("Entering CLI mode...")

    # Send CLI command
    ser.reset_input_buffer()
    send_chars(ser, 'CLI', char_delay)
    ser.write(b'\r\n')
    time.sleep(line_delay)

    # Check for CLI prompt
    start = time.time()
    collected = ""
    while time.time() - start < timeout:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting).decode('ascii', errors='replace')
            collected += data
            sys.stdout.write(data)
            sys.stdout.flush()
            if '>' in collected or 'CLI' in collected:
                print("\nCLI mode entered successfully")
                return True
        time.sleep(0.1)

    print(f"\nWARNING: CLI prompt not detected, continuing anyway...")
    return True  # Continue even if prompt not detected


def provision(args):
    """Run the full provisioning sequence."""
    print("=" * 60)
    print("iot-reference-rx Device Provisioning")
    print("=" * 60)
    print(f"Port:       {args.port}")
    print(f"Baud:       {args.baud}")
    print(f"Thing Name: {args.thing_name}")
    print(f"Endpoint:   {args.endpoint}")
    print(f"Cert:       {args.cert}")
    print(f"Key:        {args.key}")
    print("=" * 60)

    # Open serial port
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

    char_delay = args.char_delay
    line_delay = args.line_delay

    try:
        # Step 1: Wait for boot messages
        if not args.skip_boot_wait:
            wait_for_boot(ser, args.boot_wait)

        # Step 2: Enter CLI mode
        if not enter_cli_mode(ser, char_delay, line_delay, 5.0):
            print("ERROR: Failed to enter CLI mode")
            return 1

        # Step 3: Format data flash (optional)
        if args.format:
            print("\n--- Format data flash ---")
            resp = send_command(ser, 'format', char_delay, line_delay * 2)
            if resp and 'OK' in str(resp):
                print("  Format OK")
            else:
                print(f"  Format response: {resp}")

        # Step 4: Set thing name
        print(f"\n--- Set thing name: {args.thing_name} ---")
        send_command(ser, f'conf set thingname {args.thing_name}', char_delay, line_delay)

        # Step 5: Set endpoint
        print(f"\n--- Set endpoint: {args.endpoint} ---")
        send_command(ser, f'conf set endpoint {args.endpoint}', char_delay, line_delay)

        # Step 6: Set device certificate
        print(f"\n--- Set device certificate ---")
        if not send_pem_command(ser, 'cert', args.cert, char_delay, line_delay):
            print("ERROR: Failed to set certificate")
            return 1

        # Step 7: Set private key
        print(f"\n--- Set private key ---")
        if not send_pem_command(ser, 'key', args.key, char_delay, line_delay):
            print("ERROR: Failed to set private key")
            return 1

        # Step 8: Commit to data flash
        print(f"\n--- Commit to data flash ---")
        resp = send_command(ser, 'conf commit', char_delay, line_delay * 3)
        print(f"  {resp.strip() if resp else 'No response'}")

        # Step 9: Reset device
        if not args.no_reset:
            print(f"\n--- Reset device ---")
            send_command(ser, 'reset', char_delay, line_delay, expect_ok=False)
            print("  Reset command sent")

            # Wait and display boot output
            if not args.quiet:
                print("\n--- Device boot output ---")
                wait_for_boot(ser, 5.0)

    finally:
        ser.close()
        print(f"\nSerial port {args.port} closed")

    print("\n" + "=" * 60)
    print("PROVISIONING COMPLETE")
    print("=" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Provision AWS IoT credentials to CK-RX65N via UART CLI'
    )
    parser.add_argument('--port', required=True,
                        help='Serial port (e.g., COM9)')
    parser.add_argument('--baud', type=int, default=115200,
                        help='Baud rate (default: 115200)')
    parser.add_argument('--thing-name', required=True,
                        help='AWS IoT Thing name')
    parser.add_argument('--endpoint', required=True,
                        help='AWS IoT MQTT endpoint URL')
    parser.add_argument('--cert', required=True,
                        help='Path to device certificate PEM file')
    parser.add_argument('--key', required=True,
                        help='Path to device private key PEM file')
    parser.add_argument('--char-delay', type=float, default=DEFAULT_CHAR_DELAY,
                        help=f'Delay between characters in seconds (default: {DEFAULT_CHAR_DELAY})')
    parser.add_argument('--line-delay', type=float, default=DEFAULT_LINE_DELAY,
                        help=f'Delay after each command in seconds (default: {DEFAULT_LINE_DELAY})')
    parser.add_argument('--boot-wait', type=float, default=DEFAULT_BOOT_WAIT,
                        help=f'Seconds to wait for boot messages (default: {DEFAULT_BOOT_WAIT})')
    parser.add_argument('--format', action='store_true',
                        help='Format data flash before provisioning')
    parser.add_argument('--no-reset', action='store_true',
                        help='Do not reset device after provisioning')
    parser.add_argument('--skip-boot-wait', action='store_true',
                        help='Skip waiting for boot messages (device already in CLI mode)')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress boot output after reset')

    args = parser.parse_args()
    sys.exit(provision(args))


if __name__ == '__main__':
    main()

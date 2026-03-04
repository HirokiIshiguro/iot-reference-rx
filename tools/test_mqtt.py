#!/usr/bin/env python3
"""
MQTT connectivity test for iot-reference-rx (CK-RX65N).

Monitors UART output after device boot to verify:
1. MQTT broker connection succeeds
2. Topic subscription succeeds
3. At least one publish succeeds

Usage:
    python tools/test_mqtt.py --port COM9 --baud 115200 --timeout 120

The device must already be provisioned with valid AWS IoT credentials.
This script resets the device via DTR toggle, then monitors UART output
for success markers.

Exit codes:
    0 — All checks passed
    1 — One or more checks failed or timed out
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

# Success markers to detect in UART output (in expected order)
MARKERS = [
    {
        "name": "MQTT Connect",
        "pattern": "Successfully connected to MQTT broker",
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

# Error patterns that indicate failure
ERROR_PATTERNS = [
    "Failed to connect to MQTT broker",
    "Connection to the broker failed, all attempts exhausted",
    "Failed to subscribe to topic",
]


def reset_device_via_uart(ser):
    """Send 'reset' command via UART to trigger software reset.

    This works because the FreeRTOS CLI accepts 'reset' at any time
    (same method used by provision.py after writing credentials).
    """
    print("Resetting device via UART 'reset' command...")
    ser.reset_input_buffer()
    # Send reset command
    for ch in "reset":
        ser.write(ch.encode("ascii"))
        time.sleep(0.002)
    ser.write(b"\r\n")
    time.sleep(0.5)
    # Drain any immediate response
    if ser.in_waiting:
        ser.read(ser.in_waiting)
    # Wait for device to actually reset and start booting
    print("Waiting for device reboot (3s)...")
    time.sleep(3.0)
    ser.reset_input_buffer()


def monitor_uart(port, baud, timeout, verbose=False):
    """Monitor UART output and check for MQTT success markers.

    Returns:
        dict with results for each marker
    """
    results = {m["name"]: False for m in MARKERS}
    errors = []

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
        return results, [str(e)]

    # Reset device via UART to get fresh boot + MQTT connection
    reset_device_via_uart(ser)

    print(f"Monitoring UART ({port} @ {baud}bps, timeout={timeout}s)")
    print("=" * 60)

    start = time.time()
    collected = ""
    all_required_found = False

    try:
        while time.time() - start < timeout:
            if ser.in_waiting:
                try:
                    data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
                except serial.SerialException:
                    break
                collected += data

                # Print UART output (line by line for readability)
                if verbose:
                    sys.stdout.write(data)
                    sys.stdout.flush()
                else:
                    # Print only key lines
                    for line in data.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        # Print lines matching markers or errors
                        for m in MARKERS:
                            if m["pattern"] in line:
                                print(f"  [FOUND] {m['name']}: {line[:120]}")
                        for ep in ERROR_PATTERNS:
                            if ep in line:
                                print(f"  [ERROR] {line[:120]}")

                # Check markers
                for m in MARKERS:
                    if not results[m["name"]] and m["pattern"] in collected:
                        results[m["name"]] = True

                # Check error patterns
                for ep in ERROR_PATTERNS:
                    if ep in collected and ep not in errors:
                        errors.append(ep)

                # Early exit if all required markers found
                all_required_found = all(
                    results[m["name"]] for m in MARKERS if m["required"]
                )
                if all_required_found:
                    # Wait a bit more to collect any additional output
                    time.sleep(2)
                    if ser.in_waiting:
                        extra = ser.read(ser.in_waiting).decode(
                            "ascii", errors="replace"
                        )
                        if verbose:
                            sys.stdout.write(extra)
                            sys.stdout.flush()
                    break

            time.sleep(0.1)
    finally:
        ser.close()

    elapsed = time.time() - start
    print("=" * 60)
    print(f"Monitoring completed in {elapsed:.1f}s")

    return results, errors


def main():
    parser = argparse.ArgumentParser(
        description="Test MQTT connectivity for CK-RX65N"
    )
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM9)")
    parser.add_argument(
        "--baud", type=int, default=115200, help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds to wait for MQTT connection (default: 120)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print all UART output"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("iot-reference-rx MQTT Connectivity Test")
    print("=" * 60)
    print(f"Port:    {args.port}")
    print(f"Baud:    {args.baud}")
    print(f"Timeout: {args.timeout}s")
    print("=" * 60)

    results, errors = monitor_uart(args.port, args.baud, args.timeout, args.verbose)

    # Print results
    print("\n--- Test Results ---")
    all_passed = True
    for m in MARKERS:
        status = "PASS" if results[m["name"]] else "FAIL"
        marker_char = "+" if results[m["name"]] else "x"
        print(f"  [{marker_char}] {m['name']}: {status}")
        if m["required"] and not results[m["name"]]:
            all_passed = False

    if errors:
        print(f"\n--- Errors detected ---")
        for e in errors:
            print(f"  [!] {e}")
        all_passed = False

    print()
    if all_passed:
        print("MQTT TEST PASSED")
        return 0
    else:
        print("MQTT TEST FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

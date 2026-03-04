#!/usr/bin/env python3
"""
MQTT connectivity test for iot-reference-rx (CK-RX65N).

Monitors UART output after device boot to verify:
1. MQTT broker connection succeeds
2. Topic subscription succeeds
3. At least one publish succeeds

Usage (CI — device reset by rfp-cli beforehand):
    python tools/test_mqtt.py --port COM9 --baud 115200 --timeout 120 --no-reset

Usage (standalone — sends UART 'reset' command):
    python tools/test_mqtt.py --port COM9 --baud 115200 --timeout 120

The device must already be provisioned with valid AWS IoT credentials.

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
    "DHCP failed",
    "Network connection failed",
    "TLS connection failed",
    "DNS resolution failed",
]


def reset_device_via_uart(ser):
    """Send 'reset' command via UART to trigger software reset.

    This works ONLY if the FreeRTOS CLI is still active (within ~10s of boot,
    or if CLI mode was entered and no reset has been sent yet).
    """
    print("Attempting device reset via UART 'reset' command...")
    ser.reset_input_buffer()
    # Send reset command character by character
    for ch in "reset":
        ser.write(ch.encode("ascii"))
        time.sleep(0.002)
    ser.write(b"\r\n")
    time.sleep(0.5)
    # Drain any immediate response
    if ser.in_waiting:
        resp = ser.read(ser.in_waiting).decode("ascii", errors="replace")
        print(f"  Reset response: {resp.strip()[:80]}")
    # Wait for device to actually reset and start booting
    print("Waiting for device reboot (5s)...")
    time.sleep(5.0)
    ser.reset_input_buffer()


def monitor_uart(port, baud, timeout, skip_reset=False):
    """Monitor UART output and check for MQTT success markers.

    All UART output is printed for CI visibility.

    Args:
        port: Serial port name (e.g., COM9)
        baud: Baud rate
        timeout: Total monitoring timeout in seconds
        skip_reset: If True, skip UART reset (device reset by external tool)

    Returns:
        tuple of (results dict, errors list)
    """
    results = {m["name"]: False for m in MARKERS}
    errors = []
    total_bytes = 0

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

    if not skip_reset:
        reset_device_via_uart(ser)
    else:
        print("Skipping UART reset (device reset by external tool)")
        print("Starting UART monitoring immediately...")

    print(f"Monitoring UART ({port} @ {baud}bps, timeout={timeout}s)")
    print("=" * 60)

    start = time.time()
    collected = ""
    all_required_found = False
    last_progress = start

    try:
        while time.time() - start < timeout:
            if ser.in_waiting:
                try:
                    data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
                except serial.SerialException:
                    print("ERROR: Serial port read failed")
                    break
                total_bytes += len(data)
                collected += data

                # Always print UART output for CI visibility
                sys.stdout.write(data)
                sys.stdout.flush()

                # Check markers
                for m in MARKERS:
                    if not results[m["name"]] and m["pattern"] in collected:
                        results[m["name"]] = True
                        elapsed = time.time() - start
                        print(f"\n  >>> [FOUND] {m['name']} at {elapsed:.1f}s <<<")

                # Check error patterns
                for ep in ERROR_PATTERNS:
                    if ep in collected and ep not in errors:
                        errors.append(ep)
                        print(f"\n  >>> [ERROR DETECTED] {ep} <<<")

                # Early exit if all required markers found
                all_required_found = all(
                    results[m["name"]] for m in MARKERS if m["required"]
                )
                if all_required_found:
                    print("\n\nAll required markers found!")
                    # Wait a bit more to collect any additional output
                    time.sleep(2)
                    if ser.in_waiting:
                        extra = ser.read(ser.in_waiting).decode(
                            "ascii", errors="replace"
                        )
                        sys.stdout.write(extra)
                        sys.stdout.flush()
                    break
            else:
                # Print progress every 15 seconds when no data
                now = time.time()
                if now - last_progress >= 15:
                    elapsed = now - start
                    print(
                        f"  [WAITING] {elapsed:.0f}s elapsed, "
                        f"{total_bytes} bytes received so far..."
                    )
                    last_progress = now

            time.sleep(0.1)
    finally:
        ser.close()

    elapsed = time.time() - start
    print("=" * 60)
    print(f"Monitoring completed in {elapsed:.1f}s")
    print(f"Total UART bytes received: {total_bytes}")

    # Diagnostics for zero-data scenario
    if total_bytes == 0:
        print("\nDIAGNOSTIC: Zero bytes received from UART.")
        print("  Possible causes:")
        print(f"  - Serial port {port} not connected or wrong port")
        print(f"  - Device not powered or not running")
        print(f"  - Baud rate mismatch (expected {baud})")
        print(f"  - USB-Serial bridge (RL78/G1C) needs power cycle")
        print(f"  - Device stuck in boot_loader (no valid app image)")

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
        "--no-reset",
        action="store_true",
        help="Skip UART reset (use when device is reset by rfp-cli or other tool)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("iot-reference-rx MQTT Connectivity Test")
    print("=" * 60)
    print(f"Port:       {args.port}")
    print(f"Baud:       {args.baud}")
    print(f"Timeout:    {args.timeout}s")
    print(f"UART reset: {'disabled (--no-reset)' if args.no_reset else 'enabled'}")
    print("=" * 60)

    results, errors = monitor_uart(
        args.port, args.baud, args.timeout,
        skip_reset=args.no_reset,
    )

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
        print("\n--- Errors detected ---")
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

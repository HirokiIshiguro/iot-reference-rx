#!/usr/bin/env python3
"""
MQTT connectivity test for iot-reference-rx (CK-RX65N).

Monitors UART output after device boot to verify:
1. MQTT broker connection succeeds
2. Topic subscription succeeds
3. At least one publish succeeds

Usage (CI — reset device via external command):
    python tools/test_mqtt.py --port COM6 --timeout 120 \
        --reset-cmd "rfp-cli -d RX65x -t e2l:XXX -if fine -p userprog.mot -run -noquery"

Usage (standalone — sends UART 'reset' command):
    python tools/test_mqtt.py --port COM6 --timeout 120

The device must already be provisioned with valid AWS IoT credentials.

Key design: When --reset-cmd is provided, the reset command is executed FIRST,
then the serial port is opened AFTER. This avoids USB suspend / stale handle
issues that occur when the serial port is idle during long rfp-cli operations
(~2.5 min for erase + write). Since rfp-cli's device reset happens at the
very end (after programming completes), opening the serial port immediately
after subprocess.run() returns captures boot_loader output from the start.

Exit codes:
    0 — All checks passed
    1 — One or more checks failed or timed out
"""

import argparse
import subprocess
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

# Renesas RL78/G1C USB-Serial bridge VID:PID
RL78_G1C_VID_PID = "045B:8111"

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

# Boot loader markers (informational, not required for pass)
BOOT_MARKERS = [
    "BootLoader",
    "execute image",
    "send image",
    "error occurred",
    "software reset",
    "activating image",
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
    "error occurred. please reset your board",
]


def list_renesas_ports():
    """List all Renesas RL78/G1C USB-Serial ports.

    Returns:
        list of (port, description, hwid) tuples
    """
    ports = []
    for port_info in serial.tools.list_ports.comports():
        if RL78_G1C_VID_PID in port_info.hwid.upper():
            ports.append((port_info.device, port_info.description, port_info.hwid))
    return ports


def open_serial_port(port, baud):
    """Open a serial port with diagnostic output.

    Returns:
        serial.Serial instance or None on failure
    """
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

    # Print serial port diagnostics
    print(f"Serial port {port} opened @ {baud}bps")
    try:
        print(f"  DSR={ser.dsr}, CTS={ser.cts}, CD={ser.cd}, RI={ser.ri}")
    except (serial.SerialException, OSError):
        print("  (serial line status not available)")

    return ser


def probe_serial_port(ser, port):
    """Send CR to serial port and check for echo/response.

    This tests if the device is actively communicating on this port.
    Works when the FreeRTOS CLI is active (within ~10s of boot).

    Returns:
        Number of bytes received in response
    """
    print(f"  Probing {port} (sending CR)...")
    try:
        ser.reset_input_buffer()
        ser.write(b"\r\n")
        time.sleep(0.5)
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            text = data.decode("ascii", errors="replace").strip()
            print(f"  Probe response ({len(data)} bytes): {text[:80]}")
            return len(data)
        else:
            print(f"  Probe: no response")
            return 0
    except serial.SerialException as e:
        print(f"  Probe error: {e}")
        return 0


def quick_listen(ser, port, duration=5):
    """Listen on a serial port for a short duration.

    Returns:
        Data received (str), or empty string
    """
    print(f"  Quick listen on {port} ({duration}s)...")
    collected = ""
    start = time.time()
    try:
        while time.time() - start < duration:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting).decode("ascii", errors="replace")
                collected += data
                sys.stdout.write(data)
                sys.stdout.flush()
            time.sleep(0.1)
    except serial.SerialException as e:
        print(f"  Listen error: {e}")
    if collected:
        print(f"\n  Quick listen: received {len(collected)} bytes")
    else:
        print(f"  Quick listen: 0 bytes")
    return collected


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


def reset_device_via_command(reset_cmd):
    """Run an external command to reset the device (e.g., rfp-cli).

    Returns:
        True if command succeeded, False otherwise
    """
    print(f"Running reset command: {reset_cmd}")
    try:
        result = subprocess.run(
            reset_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        # Print command output for CI visibility (condensed)
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            # Show key lines only (skip progress bars)
            for line in lines:
                if line.strip():
                    print(f"  [reset-cmd] {line}")
        if result.stderr:
            # Show only non-progress-bar lines from stderr
            for line in result.stderr.strip().split("\n"):
                stripped = line.strip()
                if stripped and not stripped.startswith(("%", "[==")):
                    print(f"  [reset-cmd stderr] {stripped}")
        if result.returncode != 0:
            print(f"  WARNING: Reset command exited with code {result.returncode}")
            return False
        print("  Reset command completed successfully")
        return True
    except subprocess.TimeoutExpired:
        print("  ERROR: Reset command timed out (300s)")
        return False
    except Exception as e:
        print(f"  ERROR: Reset command failed: {e}")
        return False


def monitor_uart(port, baud, timeout, reset_cmd=None, skip_reset=False):
    """Monitor UART output and check for MQTT success markers.

    All UART output is printed for CI visibility.

    Key design: When --reset-cmd is provided, the reset command runs FIRST,
    then the serial port is opened AFTER. This avoids USB suspend / stale
    handle issues from keeping the port open during long rfp-cli operations.
    rfp-cli's device reset happens at the very end (after erase + write),
    so opening the port immediately after subprocess.run() returns still
    captures boot_loader output.

    Args:
        port: Serial port name (e.g., COM6)
        baud: Baud rate
        timeout: Total monitoring timeout in seconds
        reset_cmd: External command to reset device (runs before port open)
        skip_reset: If True, skip all reset methods

    Returns:
        tuple of (results dict, errors list)
    """
    results = {m["name"]: False for m in MARKERS}
    errors = []
    total_bytes = 0

    # Step 1: Run external reset command BEFORE opening serial port
    if reset_cmd:
        if not reset_device_via_command(reset_cmd):
            print("WARNING: Reset command failed, continuing to monitor anyway...")
        # Brief pause for device to start booting
        time.sleep(0.5)

    # Step 2: Open serial port (fresh handle, no USB suspend issues)
    ser = open_serial_port(port, baud)
    if ser is None:
        return results, [f"Cannot open {port}"]

    # Step 3: If using UART reset (no external command), send now
    if not reset_cmd and not skip_reset:
        reset_device_via_uart(ser)
    elif skip_reset:
        print("Skipping device reset")

    # Step 4: Quick probe — send CR to check if device responds
    probe_serial_port(ser, port)

    # Step 5: Monitor UART
    print(f"Monitoring UART ({port} @ {baud}bps, timeout={timeout}s)")
    print("=" * 60)

    start = time.time()
    collected = ""
    all_required_found = False
    last_progress = start
    boot_seen = False

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

                # Check boot loader markers (informational)
                if not boot_seen:
                    for bm in BOOT_MARKERS:
                        if bm in collected:
                            boot_seen = True
                            elapsed = time.time() - start
                            print(f"\n  >>> [BOOT] Boot loader activity detected at {elapsed:.1f}s <<<")
                            break

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
        print(f"  - Image signature verification failed in boot_loader")
        if reset_cmd:
            print(f"  - Reset command may not have properly started the device")

        # Try alternative Renesas RL78/G1C ports
        print(f"\n--- Scanning alternative Renesas ports ---")
        alt_ports = list_renesas_ports()
        for alt_port, alt_desc, alt_hwid in alt_ports:
            if alt_port == port:
                print(f"  {alt_port}: (primary port, already tested)")
                continue
            print(f"  {alt_port}: {alt_desc} [{alt_hwid}]")
            alt_ser = open_serial_port(alt_port, baud)
            if alt_ser:
                probe_serial_port(alt_ser, alt_port)
                quick_listen(alt_ser, alt_port, duration=5)
                alt_ser.close()
                print(f"  {alt_port}: closed")

    return results, errors


def main():
    parser = argparse.ArgumentParser(
        description="Test MQTT connectivity for CK-RX65N"
    )
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM6)")
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
        help="Skip all device reset (just monitor UART)",
    )
    parser.add_argument(
        "--reset-cmd",
        type=str,
        default=None,
        help="External command to reset device (e.g., rfp-cli). "
             "Command runs BEFORE serial port is opened.",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("iot-reference-rx MQTT Connectivity Test")
    print("=" * 60)
    print(f"Port:       {args.port}")
    print(f"Baud:       {args.baud}")
    print(f"Timeout:    {args.timeout}s")
    if args.reset_cmd:
        print(f"Reset:      external command (before port open)")
    elif args.no_reset:
        print(f"Reset:      disabled (--no-reset)")
    else:
        print(f"Reset:      UART 'reset' command")
    print("=" * 60)

    # List all available Renesas RL78/G1C ports
    rl78_ports = list_renesas_ports()
    if rl78_ports:
        print(f"\nRenesas RL78/G1C ports detected:")
        for p, d, h in rl78_ports:
            marker = " <-- primary" if p == args.port else ""
            print(f"  {p}: {d}{marker}")
            print(f"       {h}")
    else:
        print(f"\nWARNING: No Renesas RL78/G1C ports detected!")
    print()

    results, errors = monitor_uart(
        args.port, args.baud, args.timeout,
        reset_cmd=args.reset_cmd,
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

"""UART RSU download tool for CK-RX65N boot_loader.

Downloads .rsu firmware to the boot_loader via UART.
The boot_loader enters download mode when no valid image exists
(BL_INITIAL_IMAGE_INSTALL=1) and signals readiness with:
  "send image(*.rsu) via UART."

Flow control: boot_loader uses GPIO RTS (PORTC.0) to signal pause.
If connected to USB-Serial bridge CTS, pyserial rtscts handles it.
Otherwise, falls back to byte-level rate limiting.
"""

import argparse
import os
import sys
import time
import threading
import serial


# Boot loader messages
MSG_SEND_VIA_UART = b"send image(*.rsu) via UART."
MSG_SW_RESET = b"software reset..."
MSG_EXEC_IMG = b"execute image ..."
MSG_ERROR = b"error occurred"
MSG_ACTIVATE = b"activating image"
MSG_OK = b"OK"
MSG_NG = b"NG"

# Transfer settings
CHUNK_SIZE = 64  # bytes per write (smaller than 128-byte MCU buffer)
INTER_CHUNK_DELAY = 0.008  # 8ms between chunks (fallback without HW flow control)


def parse_args():
    parser = argparse.ArgumentParser(description="UART RSU download for CK-RX65N boot_loader")
    parser.add_argument("--rsu", required=True, help="Path to .rsu file")
    parser.add_argument("--port", default=os.environ.get("UART_PORT", "COM9"),
                        help="Serial port (default: $UART_PORT or COM9)")
    parser.add_argument("--baud", type=int, default=int(os.environ.get("UART_BAUD", "115200")),
                        help="Baud rate (default: $UART_BAUD or 115200)")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Total timeout in seconds (default: 300)")
    parser.add_argument("--no-hw-flow", action="store_true",
                        help="Disable hardware flow control (use timing-based)")
    parser.add_argument("--no-wait-for-ready", action="store_true",
                        help="Skip waiting for boot_loader ready message")
    parser.add_argument("--ready-timeout", type=int, default=60,
                        help="Timeout for boot_loader ready message (default: 60s)")
    parser.add_argument("--diag", action="store_true",
                        help="Print additional diagnostics")
    return parser.parse_args()


class UartDownloader:
    def __init__(self, port, baud, hw_flow=True, diag=False):
        self.port = port
        self.baud = baud
        self.hw_flow = hw_flow
        self.diag = diag
        self.ser = None
        self.rx_buf = b""
        self.rx_lock = threading.Lock()
        self.rx_thread = None
        self.running = False

    def open(self):
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            rtscts=self.hw_flow,
        )
        self.running = True
        self.rx_thread = threading.Thread(target=self._rx_worker, daemon=True)
        self.rx_thread.start()
        if self.diag:
            print(f"[DIAG] Opened {self.port} at {self.baud} bps, hw_flow={self.hw_flow}")

    def close(self):
        self.running = False
        if self.rx_thread:
            self.rx_thread.join(timeout=2)
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _rx_worker(self):
        """Background thread to continuously read UART."""
        while self.running:
            try:
                data = self.ser.read(256)
                if data:
                    with self.rx_lock:
                        self.rx_buf += data
                    if self.diag:
                        text = data.decode("ascii", errors="replace")
                        for line in text.splitlines():
                            if line.strip():
                                print(f"[RX] {line.strip()}")
                    else:
                        # Print boot_loader messages to stdout
                        text = data.decode("ascii", errors="replace")
                        for line in text.splitlines():
                            line = line.strip()
                            if line:
                                print(f"  boot_loader: {line}")
            except serial.SerialException:
                break

    def wait_for_message(self, msg, timeout):
        """Wait for a specific message from boot_loader."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.rx_lock:
                if msg in self.rx_buf:
                    return True
            time.sleep(0.1)
        return False

    def check_message(self, msg):
        """Check if a message has been received."""
        with self.rx_lock:
            return msg in self.rx_buf

    def send_rsu(self, rsu_path, timeout):
        """Send RSU file to boot_loader."""
        file_size = os.path.getsize(rsu_path)
        print(f"Sending {rsu_path} ({file_size} bytes)...")

        sent = 0
        deadline = time.time() + timeout

        with open(rsu_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break

                if time.time() > deadline:
                    print("ERROR: Transfer timeout")
                    return False

                # Hardware flow control: pyserial handles CTS automatically
                # Software fallback: add inter-chunk delay
                if not self.hw_flow:
                    time.sleep(INTER_CHUNK_DELAY)

                self.ser.write(chunk)
                sent += len(chunk)

                # Progress report every 10KB
                if sent % 10240 < CHUNK_SIZE:
                    pct = sent * 100 // file_size
                    print(f"\r  Sent {sent}/{file_size} bytes ({pct}%)", end="", flush=True)

        print(f"\r  Sent {sent}/{file_size} bytes (100%)")
        return True


def main():
    args = parse_args()

    # Verify RSU file exists
    if not os.path.isfile(args.rsu):
        print(f"ERROR: RSU file not found: {args.rsu}")
        sys.exit(1)

    hw_flow = not args.no_hw_flow
    dl = UartDownloader(args.port, args.baud, hw_flow=hw_flow, diag=args.diag)

    try:
        dl.open()

        # Wait for boot_loader ready message
        if not args.no_wait_for_ready:
            print(f"Waiting for boot_loader ready message (timeout: {args.ready_timeout}s)...")
            if not dl.wait_for_message(MSG_SEND_VIA_UART, args.ready_timeout):
                print("ERROR: Boot_loader did not send ready message.")
                print("  Expected: 'send image(*.rsu) via UART.'")
                print("  Check: Is boot_loader running? Is UART connected?")
                sys.exit(1)
            print("Boot_loader ready. Starting transfer...")
        else:
            print("Skipping ready message wait (--no-wait-for-ready)")

        # Small delay after ready message
        time.sleep(0.5)

        # Send RSU
        if not dl.send_rsu(args.rsu, args.timeout):
            sys.exit(1)

        # Wait for completion
        print("Transfer complete. Waiting for boot_loader response...")
        post_tx_timeout = 60

        # Check for activation message
        if dl.wait_for_message(MSG_ACTIVATE, post_tx_timeout):
            print("Boot_loader: activating image...")
            # Wait for OK/NG
            if dl.wait_for_message(MSG_OK, 30):
                print("Boot_loader: image activation OK")
            elif dl.check_message(MSG_NG):
                print("ERROR: Boot_loader: image activation NG")
                sys.exit(1)

        # Check for software reset (bank swap)
        if dl.wait_for_message(MSG_SW_RESET, 30):
            print("Boot_loader: software reset (bank swap)...")
            time.sleep(2)  # Wait for reset

        # Check for firmware execution
        if dl.wait_for_message(MSG_EXEC_IMG, 30):
            print("Boot_loader: executing new firmware")
            print("UART DOWNLOAD SUCCESS")
            sys.exit(0)

        # Check for error
        if dl.check_message(MSG_ERROR):
            print("ERROR: Boot_loader reported error")
            sys.exit(1)

        # If we got software reset, that's also success (MCU reboots)
        if dl.check_message(MSG_SW_RESET):
            print("UART DOWNLOAD SUCCESS (reset detected)")
            sys.exit(0)

        print("WARNING: No definitive success/failure message received.")
        print("  This may be normal if the MCU reset before sending the message.")
        print("UART DOWNLOAD COMPLETE (unconfirmed)")

    except serial.SerialException as e:
        print(f"ERROR: Serial port error: {e}")
        sys.exit(1)
    finally:
        dl.close()


if __name__ == "__main__":
    main()

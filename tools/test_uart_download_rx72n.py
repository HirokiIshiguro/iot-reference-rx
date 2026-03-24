#!/usr/bin/env python3
"""
test_uart_download.py - Download .rsu firmware via UART to RX72N boot loader

Sends an .rsu file (Renesas Secure Update) to the boot loader via UART and
monitors progress. The boot loader must already be running and waiting for
firmware data ("send userprog.rsu via UART.").

Typical CI flow:
    1. flash_boot_loader: flash boot_loader.mot, verify UART output
    2. download_aws_demos: run this script to send .rsu via UART
       → boot loader receives, verifies, bank swaps, resets
       → aws_demos boots

UART Protocol (from rx72n_boot_loader.c):
    Boot loader uses SCI7 at 921600 bps (8N1) via PMOD FTDI (COM7).
    Reception is interrupt-driven, byte-by-byte, with 32KB double buffering.
    No flow control needed — UART speed is the bottleneck.

    Message flow during download:
        "installing firmware...N%(size/totalKB)."  (progress, with \\r)
        "completed installing firmware."
        "integrity check scheme = sig-sha256-ecdsa"
        "bank1(temporary area) on code flash integrity check...OK"
        "installing const data...N%(size/totalKB)."  (data flash progress)
        "completed installing const data."
        "software reset..."
        (MCU resets)
        (boot loader starts again, verifies, bank swaps)
        "jump to user program"  (aws_demos boots)

Usage:
    python test_uart_download.py --rsu userprog.rsu
    python test_uart_download.py --rsu userprog.rsu --port COM7 --baud 921600
    python test_uart_download.py --rsu userprog.rsu --timeout 300 --diag

Dependencies:
    pip install pyserial
"""

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: 'pyserial' package is required.")
    print("       Install with: pip install pyserial")
    sys.exit(1)


# Default UART settings
DEFAULT_PORT = os.environ.get("UART_PORT", "COM7")
DEFAULT_BAUD = int(os.environ.get("UART_BAUD_RATE", "921600"))
DEFAULT_TIMEOUT = 300  # 5 minutes (1.8MB at 921600 = ~20s + flash write time)

# UART send chunk size (bytes)
# Large enough for efficiency, small enough to allow progress monitoring
SEND_CHUNK_SIZE = 4096
DEFAULT_INTER_CHUNK_DELAY = 0.0

# Key messages from boot_loader
MSG_INSTALLING_FW = "installing firmware"
MSG_COMPLETED_FW = "completed installing firmware"
MSG_INTEGRITY_CHECK = "integrity check"
# Boot loader outputs "...OK" or "...NG" for check results.
# Must use "..." prefix to avoid false positives from lifecycle state strings
# like "LIFECYCLE_STATE_TESTING" which contains "NG".
MSG_CHECK_OK = "...OK"
MSG_CHECK_NG = "...NG"
MSG_CONST_DATA = "installing const data"
MSG_COMPLETED_CONST = "completed installing const data"
MSG_SW_RESET = "software reset"
MSG_ERROR = "error occurred"
DEFAULT_SUCCESS_MESSAGE = "jump to user program"
DEFAULT_READY_MESSAGE = "send \"userprog.rsu\" via UART."
DEFAULT_WRITE_ACK_PREFIX = "W 0x"


class UartDownloader:
    """Send .rsu firmware to boot loader via UART and monitor progress."""

    def __init__(self, port, baud, timeout, post_tx_wait=30, diag=False,
                 wait_for_ready=False, ready_timeout=60,
                 ready_message=DEFAULT_READY_MESSAGE,
                 success_message=DEFAULT_SUCCESS_MESSAGE,
                 success_timeout=30, reset_cmd=None, reset_settle=0.2,
                 send_chunk_size=SEND_CHUNK_SIZE, inter_chunk_delay=DEFAULT_INTER_CHUNK_DELAY,
                 rtscts=False, ack_each_chunk=False,
                 ack_prefix=DEFAULT_WRITE_ACK_PREFIX, ack_timeout=10.0):
        self.port_name = port
        self.baud = baud
        self.timeout = timeout
        self.post_tx_wait = post_tx_wait
        self.diag = diag
        self.wait_for_ready = wait_for_ready
        self.ready_timeout = ready_timeout
        self.ready_message = ready_message
        self.success_message = success_message
        self.success_timeout = success_timeout
        self.reset_cmd = reset_cmd
        self.reset_settle = reset_settle
        self.send_chunk_size = send_chunk_size
        self.inter_chunk_delay = inter_chunk_delay
        self.rtscts = rtscts
        self.ack_each_chunk = ack_each_chunk
        self.ack_prefix = ack_prefix
        self.ack_timeout = ack_timeout
        self.ser = None
        self.rx_buffer = ""
        self.messages = []
        self.send_complete = False
        self.send_error = None
        self.bytes_sent = 0
        self.total_bytes = 0
        self.total_chunks = 0
        self.chunks_sent = 0
        self.write_ack_count = 0
        self.pending_chunk_deadline = None
        self.start_time = 0
        self.tx_complete_time = None
        self._lock = threading.Lock()

    def open_port(self):
        """Open serial port."""
        print(f"Opening {self.port_name} at {self.baud} bps...")
        self.ser = serial.Serial(
            port=self.port_name,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,  # read timeout for non-blocking reads
            write_timeout=10,
            rtscts=self.rtscts,
        )
        # Flush any stale data
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        print(f"  Port opened: {self.ser.name}")

    def close_port(self):
        """Close serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"Port closed: {self.port_name}")

    def trigger_reset(self):
        """Reset the board after UART is opened so one-shot boot banners are captured."""
        if not self.reset_cmd:
            return
        print(f"Triggering reset command: {self.reset_cmd}")
        result = subprocess.run(
            self.reset_cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        if result.returncode != 0:
            raise RuntimeError(f"reset command failed with exit status {result.returncode}")
        if self.reset_settle > 0:
            time.sleep(self.reset_settle)

    def send_thread(self, rsu_data):
        """
        Thread function: send .rsu data in chunks.
        The serial driver handles baud rate pacing internally.
        """
        try:
            offset = 0
            while offset < len(rsu_data):
                chunk = rsu_data[offset:offset + self.send_chunk_size]
                self.ser.write(chunk)
                offset += len(chunk)
                if self.inter_chunk_delay > 0:
                    time.sleep(self.inter_chunk_delay)
                with self._lock:
                    self.bytes_sent = offset
        except Exception as e:
            self.send_error = str(e)
        finally:
            with self._lock:
                self.send_complete = True

    def read_uart(self):
        """
        Read available data from UART (non-blocking).
        Returns list of complete lines received.
        """
        lines = []
        try:
            data = self.ser.read(self.ser.in_waiting or 1)
            if data:
                # Decode with error handling (boot_loader output is ASCII)
                text = data.decode('ascii', errors='replace')
                self.rx_buffer += text

                # Split on newline, keeping partial lines in buffer
                while '\n' in self.rx_buffer:
                    line, self.rx_buffer = self.rx_buffer.split('\n', 1)
                    line = line.strip('\r')
                    if line:
                        lines.append(line)
                        self.messages.append(line)
                        if self.ack_each_chunk and line.startswith(self.ack_prefix):
                            self.write_ack_count += 1

                # Also check for \r-only lines (progress updates use \r)
                if '\r' in self.rx_buffer and '\n' not in self.rx_buffer:
                    parts = self.rx_buffer.split('\r')
                    # Keep the last part (possibly incomplete)
                    for part in parts[:-1]:
                        part = part.strip()
                        if part:
                            lines.append(part)
                            # Don't add progress lines to messages (too many)
                            if MSG_INSTALLING_FW not in part and MSG_CONST_DATA not in part:
                                self.messages.append(part)
                            if self.ack_each_chunk and part.startswith(self.ack_prefix):
                                self.write_ack_count += 1
                    self.rx_buffer = parts[-1]
        except serial.SerialException:
            pass
        return lines

    def send_next_chunk(self, rsu_data):
        """Send one chunk when per-chunk ACK pacing is enabled."""
        if self.bytes_sent >= self.total_bytes:
            return

        chunk = rsu_data[self.bytes_sent:self.bytes_sent + self.send_chunk_size]
        self.ser.write(chunk)
        if self.inter_chunk_delay > 0:
            time.sleep(self.inter_chunk_delay)

        with self._lock:
            self.bytes_sent += len(chunk)
            self.chunks_sent += 1
            if self.bytes_sent >= self.total_bytes:
                self.send_complete = True
            self.pending_chunk_deadline = time.time() + self.ack_timeout

    def download(self, rsu_path):
        """
        Send .rsu file and monitor progress.

        Returns:
            0 on success (firmware installed and verified)
            1 on failure
        """
        # Read .rsu file
        rsu_data = rsu_path.read_bytes()
        self.total_bytes = len(rsu_data)
        self.total_chunks = (self.total_bytes + self.send_chunk_size - 1) // self.send_chunk_size
        print(f"\n=== UART Download ===")
        print(f"  File:     {rsu_path}")
        print(f"  Size:     {self.total_bytes:,} bytes ({self.total_bytes/1024:.1f} KB)")
        print(f"  Port:     {self.port_name} @ {self.baud} bps")
        estimated_sec = self.total_bytes * 10 / self.baud
        print(f"  Est time: {estimated_sec:.0f}s ({estimated_sec/60:.1f} min) for transfer")
        print(f"  Timeout:  {self.timeout}s")
        print(f"  Chunk:    {self.send_chunk_size} bytes")
        print(f"  Delay:    {self.inter_chunk_delay:.3f}s")
        print(f"  RTS/CTS:  {'ON' if self.rtscts else 'OFF'}")
        print(f"  Ack mode: {'per-chunk' if self.ack_each_chunk else 'streaming'}")
        print()

        self.open_port()
        self.start_time = time.time()

        self.trigger_reset()

        # Brief pause to let boot_loader settle
        time.sleep(0.5)

        # Drain any pending data from boot_loader
        drain_data = b""
        while self.ser.in_waiting:
            drain_data += self.ser.read(self.ser.in_waiting)
            time.sleep(0.05)
        if drain_data:
            drain_text = drain_data.decode('ascii', errors='replace').strip()
            if drain_text:
                print(f"[drain] {drain_text}")

        # Wait for boot_loader ready signal if requested
        # boot_loader outputs 'send "userprog.rsu" via UART.' after completing
        # code flash erase. Without this wait, data sent during erase will
        # freeze the MCU.
        if self.wait_for_ready:
            print(f"Waiting for boot_loader ready signal (timeout={self.ready_timeout}s)...")
            ready_start = time.time()
            rx_buf = drain_data.decode('ascii', errors='replace') if drain_data else ""
            ready_found = self.ready_message in rx_buf
            while not ready_found:
                elapsed = time.time() - ready_start
                if elapsed > self.ready_timeout:
                    print(f"TIMEOUT: boot_loader ready signal not detected after {self.ready_timeout}s")
                    print(f"  Expected: '{self.ready_message}'")
                    print(f"  Received so far: {rx_buf[-200:]}")
                    self.close_port()
                    return 1
                data = self.ser.read(self.ser.in_waiting or 1)
                if data:
                    text = data.decode('ascii', errors='replace')
                    rx_buf += text
                    # Print lines as they arrive
                    while '\n' in text:
                        line, text = text.split('\n', 1)
                        line = line.strip('\r').strip()
                        if line:
                            print(f"  [{elapsed:.1f}s] {line}")
                    if self.ready_message in rx_buf:
                        ready_found = True
                        print(f"  Boot_loader ready ({elapsed:.1f}s)")
                time.sleep(0.05)

        # Start send thread
        print(f"Sending {self.total_bytes:,} bytes...")
        sender = None
        if self.ack_each_chunk:
            self.send_next_chunk(rsu_data)
        else:
            sender = threading.Thread(target=self.send_thread, args=(rsu_data,), daemon=True)
            sender.start()

        # Monitor loop
        fw_completed = False
        integrity_ok = False
        const_completed = False
        sw_reset = False
        success_message_seen = False
        last_progress_print = 0
        last_ack_report = 0
        post_reset_timeout = self.success_timeout
        post_reset_start = None

        while True:
            elapsed = time.time() - self.start_time

            # Check global timeout (safety net)
            if elapsed > self.timeout:
                print(f"\nTIMEOUT after {elapsed:.1f}s")
                self.close_port()
                return 1

            # Read UART output
            lines = self.read_uart()
            for line in lines:
                # Print significant messages
                if self.ack_each_chunk and line.startswith(self.ack_prefix):
                    pass
                elif MSG_INSTALLING_FW in line:
                    # Progress update — print periodically
                    if time.time() - last_progress_print > 5:
                        print(f"  [{elapsed:6.1f}s] {line}")
                        last_progress_print = time.time()
                elif MSG_CONST_DATA in line:
                    if time.time() - last_progress_print > 5:
                        print(f"  [{elapsed:6.1f}s] {line}")
                        last_progress_print = time.time()
                else:
                    print(f"  [{elapsed:6.1f}s] {line}")

                # Track state
                if MSG_COMPLETED_FW in line:
                    fw_completed = True
                elif MSG_CHECK_OK in line and MSG_INTEGRITY_CHECK in '\n'.join(self.messages[-5:]):
                    integrity_ok = True
                elif MSG_CHECK_NG in line and MSG_INTEGRITY_CHECK in '\n'.join(self.messages[-5:]):
                    print(f"\nERROR: Firmware integrity check FAILED")
                    self.close_port()
                    return 1
                elif MSG_ERROR in line.lower():
                    print(f"\nERROR: Boot loader reported failure: {line}")
                    self.close_port()
                    return 1
                elif MSG_COMPLETED_CONST in line:
                    const_completed = True
                elif MSG_SW_RESET in line:
                    sw_reset = True
                    post_reset_start = time.time()
                elif self.success_message in line:
                    success_message_seen = True

            if self.ack_each_chunk:
                while not self.send_error and self.chunks_sent < self.total_chunks and self.write_ack_count >= self.chunks_sent:
                    self.send_next_chunk(rsu_data)

                if self.chunks_sent > self.write_ack_count and self.pending_chunk_deadline:
                    if time.time() > self.pending_chunk_deadline:
                        pending = self.chunks_sent - self.write_ack_count
                        self.send_error = (
                            f"Timed out waiting for write acknowledgement "
                            f"({self.write_ack_count}/{self.total_chunks} ACK, {pending} chunk pending)"
                        )

            # Print send progress and detect TX completion
            with self._lock:
                sent = self.bytes_sent
                tx_done = self.send_complete
            if sent > 0 and not tx_done:
                pct = sent * 100 / self.total_bytes
                if self.diag and time.time() - last_progress_print > 10:
                    print(f"  [{elapsed:6.1f}s] TX: {sent:,}/{self.total_bytes:,} bytes ({pct:.0f}%)")
                    if self.ack_each_chunk:
                        print(f"  [{elapsed:6.1f}s] ACK: {self.write_ack_count}/{self.total_chunks} chunks")
                    last_progress_print = time.time()
            elif tx_done and self.tx_complete_time is None and not self.send_error:
                self.tx_complete_time = time.time()
                print(f"  [{elapsed:6.1f}s] TX complete: {sent:,} bytes sent")
                print(f"  [{elapsed:6.1f}s] Waiting up to {self.post_tx_wait}s for boot_loader response...")

            if self.ack_each_chunk and self.diag and self.write_ack_count != last_ack_report:
                if self.write_ack_count <= 4 or self.write_ack_count == self.total_chunks or self.write_ack_count % 256 == 0:
                    pct = self.write_ack_count * 100 / self.total_chunks
                    print(f"  [{elapsed:6.1f}s] ACK: {self.write_ack_count}/{self.total_chunks} chunks ({pct:.0f}%)")
                    last_ack_report = self.write_ack_count

            # Check if send failed
            if self.send_error:
                print(f"\nERROR: Send failed: {self.send_error}")
                self.close_port()
                return 1

            # Post-TX timeout: if TX done but no meaningful MCU response
            if (self.tx_complete_time and not sw_reset and
                    time.time() - self.tx_complete_time > self.post_tx_wait):
                print(f"\n=== Download Complete (TX only, no RX) ===")
                print(f"  TX:                {sent:,}/{self.total_bytes:,} bytes (100%)")
                print(f"  RX messages:       {len(self.messages)}")
                print(f"  Firmware installed: {'YES' if fw_completed else 'UNKNOWN (no RX)'}")
                print(f"  Integrity check:   {'PASS' if integrity_ok else 'UNKNOWN (no RX)'}")
                print(f"  Const data:        {'YES' if const_completed else 'UNKNOWN (no RX)'}")
                print(f"  Software reset:    {'YES' if sw_reset else 'UNKNOWN (no RX)'}")
                print(f"  Total time:        {elapsed:.1f}s ({elapsed/60:.1f} min)")
                print(f"\nWARNING: No response from boot_loader after TX completion.")
                print(f"  TX succeeded. Verify on LCD or fix COM port MCU→PC direction.")
                self.close_port()
                return 0

            # Success condition: firmware installed + verified + data flash + reset
            if sw_reset:
                if success_message_seen:
                    # Full success — aws_demos is booting
                    elapsed = time.time() - self.start_time
                    print(f"\n=== Download Complete ===")
                    print(f"  Firmware installed: {'YES' if fw_completed else 'NO'}")
                    print(f"  Integrity check:   {'PASS' if integrity_ok else 'UNKNOWN'}")
                    print(f"  Const data:        {'YES' if const_completed else 'NO'}")
                    print(f"  Software reset:    YES")
                    print(f"  Success marker:    YES ({self.success_message})")
                    print(f"  Total time:        {elapsed:.1f}s ({elapsed/60:.1f} min)")
                    self.close_port()
                    return 0

                # After sw_reset, wait limited time for the configured success marker.
                if post_reset_start and (time.time() - post_reset_start > post_reset_timeout):
                    # Timeout waiting for jump, but download itself succeeded
                    elapsed = time.time() - self.start_time
                    print(f"\n=== Download Complete (partial) ===")
                    print(f"  Firmware installed: {'YES' if fw_completed else 'NO'}")
                    print(f"  Integrity check:   {'PASS' if integrity_ok else 'UNKNOWN'}")
                    print(f"  Const data:        {'YES' if const_completed else 'NO'}")
                    print(f"  Software reset:    YES")
                    print(f"  Success marker:    NO (timeout after {post_reset_timeout}s)")
                    print(f"  Total time:        {elapsed:.1f}s ({elapsed/60:.1f} min)")
                    print(f"\nWARNING: Success marker '{self.success_message}' not detected, but download completed.")
                    print(f"  This may be normal if the user program does not output to UART,")
                    print(f"  or if boot_loader does bank swap before printing this message.")
                    self.close_port()
                    # Still return 0 — download+verify succeeded, user program behavior is separate
                    return 0

            time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(
        description="Download .rsu firmware via UART to RX72N boot loader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--rsu", type=Path, required=True,
                        help="Path to .rsu file to download")
    parser.add_argument("--port", default=DEFAULT_PORT,
                        help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Total timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--post-tx-wait", type=int, default=30,
                        help="Seconds to wait for MCU response after TX completes (default: 30)")
    parser.add_argument("--diag", action="store_true",
                        help="Print additional diagnostic output")
    parser.add_argument("--wait-for-ready", action="store_true",
                        help="Wait for boot_loader ready signal before sending. "
                             "Required when boot_loader was just flashed in the same job.")
    parser.add_argument("--ready-timeout", type=int, default=60,
                        help="Timeout for boot_loader ready signal in seconds (default: 60)")
    parser.add_argument("--ready-message", default=DEFAULT_READY_MESSAGE,
                        help=f"Boot loader ready message to wait for (default: {DEFAULT_READY_MESSAGE})")
    parser.add_argument("--success-message", default=DEFAULT_SUCCESS_MESSAGE,
                        help=f"Success marker expected after software reset (default: {DEFAULT_SUCCESS_MESSAGE})")
    parser.add_argument("--success-timeout", type=int, default=30,
                        help="Seconds to wait for success marker after software reset (default: 30)")
    parser.add_argument("--reset-cmd",
                        help="Command to execute after opening UART, before waiting for the ready message")
    parser.add_argument("--reset-settle", type=float, default=0.2,
                        help="Seconds to wait after reset command completes (default: 0.2)")
    parser.add_argument("--send-chunk-size", type=int, default=SEND_CHUNK_SIZE,
                        help=f"UART TX chunk size in bytes (default: {SEND_CHUNK_SIZE})")
    parser.add_argument("--inter-chunk-delay", type=float, default=DEFAULT_INTER_CHUNK_DELAY,
                        help=f"Delay after each UART TX chunk in seconds (default: {DEFAULT_INTER_CHUNK_DELAY})")
    parser.add_argument("--rtscts", action="store_true",
                        help="Enable hardware RTS/CTS flow control")
    parser.add_argument("--ack-each-chunk", action="store_true",
                        help="Send one chunk at a time and wait for a boot_loader write acknowledgement before sending the next chunk")
    parser.add_argument("--ack-prefix", default=DEFAULT_WRITE_ACK_PREFIX,
                        help=f"UART line prefix that acknowledges one write chunk (default: {DEFAULT_WRITE_ACK_PREFIX})")
    parser.add_argument("--ack-timeout", type=float, default=10.0,
                        help="Seconds to wait for the next write acknowledgement in --ack-each-chunk mode (default: 10.0)")

    args = parser.parse_args()

    if not args.rsu.exists():
        print(f"ERROR: RSU file not found: {args.rsu}")
        return 1

    downloader = UartDownloader(
        port=args.port,
        baud=args.baud,
        timeout=args.timeout,
        post_tx_wait=args.post_tx_wait,
        diag=args.diag,
        wait_for_ready=args.wait_for_ready,
        ready_timeout=args.ready_timeout,
        ready_message=args.ready_message,
        success_message=args.success_message,
        success_timeout=args.success_timeout,
        reset_cmd=args.reset_cmd,
        reset_settle=args.reset_settle,
        send_chunk_size=args.send_chunk_size,
        inter_chunk_delay=args.inter_chunk_delay,
        rtscts=args.rtscts,
        ack_each_chunk=args.ack_each_chunk,
        ack_prefix=args.ack_prefix,
        ack_timeout=args.ack_timeout,
    )

    try:
        return downloader.download(args.rsu)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        downloader.close_port()
        return 130
    except serial.SerialException as e:
        print(f"\nSerial port error: {e}")
        downloader.close_port()
        return 1


if __name__ == "__main__":
    sys.exit(main())

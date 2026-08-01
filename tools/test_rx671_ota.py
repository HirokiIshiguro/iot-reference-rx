#!/usr/bin/env python3
"""Install an RX671 factory baseline over SCI6, then observe AWS IoT OTA.

SCI6 is opened before the boot loader is released and is held continuously
through baseline RSU installation, application startup, candidate download,
activation, reboot, self-test, acceptance, and commit.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from rx671_ota_host import (
    DEFAULT_BAUD,
    DEFAULT_PORT,
    RfpConfig,
    TimestampLog,
    cleanup_plaintext,
    open_serial,
    run_checked,
    stream_file,
    write_json,
    write_junit,
)
from test_ota import OtaLogAnalyzer


RSU_SIZE = 0x000C0000
READY_MARKER = 'send "userprog.rsu" via UART.'
BOOT_ERROR_MARKERS = (
    "fatal error occurred.",
    "not found; refusing to boot.",
    "integrity check...NG",
    "Code flash is completely broken.",
)
BOOT_REQUIRED = {
    "key_found": "Loading user code signer public key from LittleFS: found.",
    "install_started": "start installing user program.",
    "ready": READY_MARKER,
    "install_completed": "completed installing firmware.",
    "ecdsa": "integrity check scheme = sig-sha256-ecdsa",
    "integrity_ok": "on code flash integrity check...OK",
    "lifecycle": "update LIFECYCLE_STATE",
    "bank_swap": "software reset...",
    "jump": "jump to user program",
}

OTA_CAPACITY_RE = re.compile(
    r"\[RX671_OTA_CAPACITY\]\s+"
    r"minheap=(?P<min_heap_bytes>\d+)\s+"
    r"minnbuf=(?P<min_network_buffers>\d+)\s+"
    r"whdmax=(?P<whd_max_in_use>\d+)\s+"
    r"tempfail=(?P<whd_temp_fail_count>\d+)\s+"
    r"permfail=(?P<whd_perm_fail_count>\d+)\s+"
    r"waitloop=(?P<whd_wait_loop_count>\d+)"
)


def _required_file(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"file does not exist: {value}")
    return path


class Rx671OtaTransaction:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.started = time.monotonic()
        self.raw_log = TimestampLog(args.raw_log)
        self.ota = OtaLogAnalyzer(
            expected_version=args.candidate_version,
            require_tls_version=args.require_tls_version,
        )
        self.boot_required = dict(BOOT_REQUIRED)
        self.boot_required["baseline_version"] = f"Application version {args.baseline_version}"
        self.boot_hits = {name: 0 for name in self.boot_required}
        self.text = ""
        self.pending = ""
        self.total_uart_bytes = 0
        self.capacity_events = []

    def _consume(self, chunk: bytes) -> None:
        decoded = chunk.decode("ascii", errors="replace")
        self.total_uart_bytes += len(chunk)
        self.text = (self.text + decoded)[-65536:]
        self.raw_log.write(decoded)
        for name, marker in self.boot_required.items():
            if marker in self.text:
                self.boot_hits[name] = 1
        for marker in BOOT_ERROR_MARKERS:
            if marker in self.text:
                raise RuntimeError(f"boot loader fail-close marker observed: {marker}")
        combined = self.pending + decoded
        lines = combined.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\r", "\n")):
            self.pending = lines.pop()
        else:
            self.pending = ""
        elapsed = time.monotonic() - self.started
        for line in lines:
            self.ota.consume_line(line, elapsed)
            capacity_match = OTA_CAPACITY_RE.search(line)
            if capacity_match:
                self.capacity_events.append(
                    {
                        **{
                            name: int(value)
                            for name, value in capacity_match.groupdict().items()
                        },
                        "seen_at": round(elapsed, 3),
                        "line_number": self.ota.total_lines,
                    }
                )

    def _post_ota_capacity(self) -> dict | None:
        activate_line = self.ota.marker_state["activate_image"][
            "first_seen_line_number"
        ]
        if activate_line is None:
            return None
        return next(
            (
                event
                for event in self.capacity_events
                if event["line_number"] > activate_line
            ),
            None,
        )

    def _capacity_proof(self) -> dict:
        capacity = self._post_ota_capacity()
        thresholds = {
            "min_heap_bytes": int(
                getattr(self.args, "min_capacity_heap_bytes", 16384)
            ),
            "min_network_buffers": int(
                getattr(self.args, "min_capacity_network_buffers", 4)
            ),
            "whd_buffer_count": int(
                getattr(self.args, "expected_whd_buffer_count", 8)
            ),
        }
        checks = {
            "post_ota_line_observed": capacity is not None,
            "minimum_heap_met": bool(
                capacity is not None
                and capacity["min_heap_bytes"] >= thresholds["min_heap_bytes"]
            ),
            "minimum_network_buffers_met": bool(
                capacity is not None
                and capacity["min_network_buffers"]
                >= thresholds["min_network_buffers"]
            ),
            "whd_pool_not_exhausted": bool(
                capacity is not None
                and capacity["whd_max_in_use"] < thresholds["whd_buffer_count"]
            ),
            "whd_temporary_failures_zero": bool(
                capacity is not None
                and capacity["whd_temp_fail_count"] == 0
            ),
            "whd_permanent_failures_zero": bool(
                capacity is not None
                and capacity["whd_perm_fail_count"] == 0
            ),
            "whd_wait_loops_zero": bool(
                capacity is not None
                and capacity["whd_wait_loop_count"] == 0
            ),
        }
        return {
            "success": all(checks.values()),
            "metrics": capacity,
            "thresholds": thresholds,
            "checks": checks,
        }

    def _read(self, serial_port) -> bool:
        waiting = getattr(serial_port, "in_waiting", 0)
        chunk = serial_port.read(waiting or 1)
        if not chunk:
            return False
        self._consume(chunk)
        return True

    def wait_for(self, serial_port, marker: str, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if marker in self.text:
                return
            self._read(serial_port)
        raise TimeoutError(f"timed out waiting for target marker: {marker}")

    def run(self) -> dict:
        if self.args.baseline_rsu.stat().st_size != RSU_SIZE:
            raise ValueError(
                f"baseline RSU must be exactly 0x{RSU_SIZE:X} bytes; "
                f"got 0x{self.args.baseline_rsu.stat().st_size:X}"
            )
        rfp = RfpConfig(
            executable=self.args.rfp_cli,
            device=self.args.rfp_device,
            tool=self.args.rfp_tool,
            interface=self.args.rfp_interface,
            speed=self.args.rfp_speed,
            auth_id=self.args.rfp_auth_id,
        )
        serial_port = open_serial(self.args.port, self.args.baud)
        sent = 0
        digest = None
        try:
            serial_port.reset_input_buffer()
            serial_port.reset_output_buffer()
            run_checked(rfp.run_command(), label="boot-loader release")
            self.wait_for(serial_port, BOOT_REQUIRED["key_found"], self.args.boot_timeout)
            self.wait_for(serial_port, READY_MARKER, self.args.boot_timeout)
            sent, digest = stream_file(
                serial_port,
                self.args.baseline_rsu,
                chunk_size=self.args.chunk_size,
                inter_chunk_delay=self.args.inter_chunk_delay,
                timeout=self.args.transfer_timeout,
            )
            self.wait_for(serial_port, BOOT_REQUIRED["install_completed"], self.args.install_timeout)
            self.wait_for(serial_port, BOOT_REQUIRED["jump"], self.args.install_timeout)
            self.wait_for(
                serial_port,
                f"Application version {self.args.baseline_version}",
                self.args.application_timeout,
            )

            deadline = time.monotonic() + self.args.ota_timeout
            while time.monotonic() < deadline:
                self._read(serial_port)
                if self.ota.first_error() is not None:
                    error = self.ota.first_error()
                    raise RuntimeError(f"OTA fail-close marker: {error['classification']}")
                if self.ota.is_success() and self.ota.has_marker("image_committed"):
                    break
            else:
                raise TimeoutError("candidate OTA did not reach accepted-and-committed state")
        finally:
            serial_port.close()

        missing_boot = [name for name, count in self.boot_hits.items() if count == 0]
        ota_summary = self.ota.build_summary(
            total_bytes=self.total_uart_bytes,
            elapsed=time.monotonic() - self.started,
            success=self.ota.is_success(),
        )
        activate_at = self.ota.marker_seen_at("activate_image")
        candidate_tls_after_activate = bool(
            activate_at is not None
            and any(
                event["seen_at"] >= activate_at
                and event["version"] == self.args.require_tls_version
                for event in self.ota.tls_events
            )
        )
        capacity_proof = self._capacity_proof()
        success = (
            not missing_boot
            and ota_summary["success"]
            and self.ota.has_marker("image_committed")
            and ota_summary["tls_version_ok"]
            and candidate_tls_after_activate
            and capacity_proof["success"]
        )
        if success:
            classification = "pass"
        elif (
            missing_boot
            or not ota_summary["success"]
            or not self.ota.has_marker("image_committed")
            or not ota_summary["tls_version_ok"]
            or not candidate_tls_after_activate
        ):
            classification = "required_marker_missing"
        else:
            classification = "post_ota_capacity_check_failed"
        return {
            "success": success,
            "classification": classification,
            "baseline_version": self.args.baseline_version,
            "candidate_version": self.args.candidate_version,
            "require_tls_version": self.args.require_tls_version,
            "baseline_rsu": {
                "size": sent,
                "sha256": digest,
                "expected_size": RSU_SIZE,
            },
            "bootloader_markers": self.boot_hits,
            "bootloader_markers_missing": missing_boot,
            "uart_held_for_entire_transaction": True,
            "ota": ota_summary,
            "image_commit_observed": self.ota.has_marker("image_committed"),
            "candidate_tls_after_activate": candidate_tls_after_activate,
            "post_ota_capacity": capacity_proof,
            "duration_seconds": round(time.monotonic() - self.started, 3),
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-rsu", type=_required_file, required=True)
    parser.add_argument("--baseline-version", default="0.1.0")
    parser.add_argument("--candidate-version", default="0.1.1")
    parser.add_argument("--require-tls-version", default="TLSv1.2")
    parser.add_argument("--min-capacity-heap-bytes", type=int, default=16384)
    parser.add_argument("--min-capacity-network-buffers", type=int, default=4)
    parser.add_argument("--expected-whd-buffer-count", type=int, default=8)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--rfp-cli", default="./tools/rfp_cli_locked.sh")
    parser.add_argument("--rfp-device", default="RX671")
    parser.add_argument("--rfp-tool", default="e2l:OBE110024")
    parser.add_argument("--rfp-interface", default="fine")
    parser.add_argument("--rfp-speed", default="500K")
    parser.add_argument("--rfp-auth-id", default="FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
    parser.add_argument("--boot-timeout", type=float, default=60.0)
    parser.add_argument("--transfer-timeout", type=float, default=180.0)
    parser.add_argument("--install-timeout", type=float, default=180.0)
    parser.add_argument("--application-timeout", type=float, default=180.0)
    parser.add_argument("--ota-timeout", type=float, default=900.0)
    parser.add_argument("--chunk-size", type=int, default=4096)
    parser.add_argument("--inter-chunk-delay", type=float, default=0.0)
    parser.add_argument("--raw-log", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--junit-output", type=Path, required=True)
    parser.add_argument("--cleanup-root", type=Path)
    parser.add_argument("--cleanup-plaintext", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    if args.chunk_size <= 0:
        parser.error("--chunk-size must be positive")
    if args.min_capacity_heap_bytes <= 0:
        parser.error("--min-capacity-heap-bytes must be positive")
    if args.min_capacity_network_buffers <= 0:
        parser.error("--min-capacity-network-buffers must be positive")
    if args.expected_whd_buffer_count <= 0:
        parser.error("--expected-whd-buffer-count must be positive")
    if args.cleanup_plaintext and args.cleanup_root is None:
        parser.error("--cleanup-root is required with --cleanup-plaintext")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    try:
        summary = Rx671OtaTransaction(args).run()
        status = 0 if summary["success"] else 1
    except Exception as exc:
        summary = {
            "success": False,
            "classification": type(exc).__name__,
            "message": str(exc),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        print(f"RX671 OTA transaction failed: {exc}", file=sys.stderr)
        status = 1
    finally:
        if args.cleanup_plaintext:
            try:
                removed = cleanup_plaintext(args.cleanup_plaintext, args.cleanup_root)
                summary["plaintext_cleanup"] = {"success": True, "removed": removed}
            except Exception as exc:
                summary["success"] = False
                summary["plaintext_cleanup"] = {"success": False, "message": str(exc)}
                status = 1
    write_json(args.summary_json, summary)
    write_junit(
        args.junit_output,
        name="test_rx671_ota",
        success=bool(summary["success"]),
        message=summary.get("message", summary["classification"]),
        seconds=float(summary["duration_seconds"]),
    )
    return status


if __name__ == "__main__":
    sys.exit(main())

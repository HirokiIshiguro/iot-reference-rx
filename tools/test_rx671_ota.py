#!/usr/bin/env python3
"""Install an RX671 factory baseline over SCI6, then observe AWS IoT OTA.

SCI6 is opened before the boot loader is released and is held continuously
through baseline RSU installation, application startup, candidate download,
activation, reboot, self-test, image acceptance, and OTA success reporting.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

from rx671_ota_host import (
    BufferedSerialReader,
    DEFAULT_BAUD,
    DEFAULT_PORT,
    RfpConfig,
    TimestampLog,
    cleanup_plaintext,
    open_serial,
    run_checked,
    write_json,
    write_junit,
)
from test_ota import OtaLogAnalyzer


RSU_SIZE = 0x000C0000
BOOTLOADER_FLASH_BLOCK_SIZE = 0x00008000
READY_MARKER = 'send "userprog.rsu" via UART.'
KEY_LOAD_MARKER = "Loading user code signer public key from LittleFS:"
KEY_FOUND_MARKER = "found."
BOOT_ERROR_MARKERS = (
    "fatal error occurred.",
    "not found; refusing to boot.",
    "integrity check...NG",
    "Code flash is completely broken.",
    "RX671 OTA fatal:",
)
STARTUP_RETRY_MARKERS = {
    "whd_bringup_failed": "RX671 OTA startup retry: WHD bring-up failed",
    "whd_mac_unavailable": "RX671 OTA startup retry: WHD station MAC unavailable",
    "dhcp_lease_not_acquired": "RX671 OTA startup retry: DHCP lease not acquired",
}
STARTUP_READY_MARKER = "RX671 OTA startup ready: WHD and DHCP lease verified"
BOOT_REQUIRED = {
    "key_load_started": KEY_LOAD_MARKER,
    "key_found": KEY_FOUND_MARKER,
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
        self.startup_reset_events = []
        self.uart_capture = None

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

    def _ota_phase_anchor_line(self) -> int | None:
        activate_line = self.ota.marker_state["activate_image"][
            "first_seen_line_number"
        ]
        if activate_line is not None:
            return activate_line

        if (
            self.ota.success_proof()
            != "ordered_candidate_acceptance_and_completion"
        ):
            return None

        chain = self.ota.ordered_candidate_acceptance_chain()
        if chain is None:
            return None
        return chain["candidate_version"]["line_number"]

    def _post_ota_capacity(self) -> dict | None:
        phase_anchor_line = self._ota_phase_anchor_line()
        if phase_anchor_line is None:
            return None
        return next(
            (
                event
                for event in self.capacity_events
                if event["line_number"] > phase_anchor_line
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

    def _baseline_tls_before_activate(self) -> bool:
        phase_anchor_line = self._ota_phase_anchor_line()
        return bool(
            phase_anchor_line is not None
            and any(
                event["line_number"] < phase_anchor_line
                and event["version"] == self.args.require_tls_version
                for event in self.ota.tls_events
            )
        )

    def _candidate_tls_after_activate(self) -> bool:
        phase_anchor_line = self._ota_phase_anchor_line()
        return bool(
            phase_anchor_line is not None
            and any(
                event["line_number"] > phase_anchor_line
                and event["version"] == self.args.require_tls_version
                for event in self.ota.tls_events
            )
        )

    def _runtime_success_ready(self) -> bool:
        """Return true after the RX671 happy path has fully reported success.

        The primary-image ``OtaPalNewImageBooted`` path accepts the image,
        deletes the staging area, and reports the AWS IoT Job as succeeded.  It
        does not call ``otaPal_SetPlatformImageState( OtaImageStateAccepted )``,
        so the optional ``Accepted and committed final image.`` PAL log is not
        emitted on this path.  Requiring that optional log would turn a proven
        successful OTA into a 15-minute host-side timeout.
        """
        return bool(
            self.ota.is_success()
            and self.ota.has_marker("ota_completed")
            and self._baseline_tls_before_activate()
            and self._candidate_tls_after_activate()
            and self._capacity_proof()["success"]
        )

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

    def _startup_retry_reason(self) -> str | None:
        return next(
            (
                name
                for name, marker in STARTUP_RETRY_MARKERS.items()
                if marker in self.text
            ),
            None,
        )

    def _perform_startup_reset(
        self,
        serial_port,
        rfp: RfpConfig,
        *,
        reason: str,
        phase: str,
    ) -> None:
        reset_limit = int(getattr(self.args, "startup_reset_retries", 2))
        reset_number = len(self.startup_reset_events) + 1

        if reset_number > reset_limit:
            raise RuntimeError(
                "RX671 OTA startup reset retries exhausted "
                f"after {reset_limit} reset(s): {reason}"
            )

        self.startup_reset_events.append(
            {
                "reset_number": reset_number,
                "reason": reason,
                "phase": phase,
            }
        )
        self.raw_log.write(
            "[HOST] RX671 OTA bounded startup reset "
            f"{reset_number}/{reset_limit}: {reason} phase={phase}\n"
        )
        serial_port.reset_input_buffer()
        self.text = ""
        self.pending = ""
        run_checked(
            rfp.run_command(),
            label=f"RX671 OTA startup reset {reset_number}/{reset_limit}",
        )

    def wait_for_application_ready(self, serial_port, rfp: RfpConfig) -> None:
        """Boundedly reset before OTA/AWS side effects when startup asks for it.

        Every application boot enters ``sdio_host_init()``, which power-cycles
        the Type 1YN rail through P51. A whole-MCU reset is therefore safer
        than trying to unwind an unknown partially initialized WHD state.
        """
        application_marker = STARTUP_READY_MARKER
        reset_limit = int(getattr(self.args, "startup_reset_retries", 2))

        for attempt in range(reset_limit + 1):
            deadline = time.monotonic() + self.args.application_timeout
            while time.monotonic() < deadline:
                self._read(serial_port)
                retry_reason = self._startup_retry_reason()
                if retry_reason is not None:
                    break
                if application_marker in self.text:
                    return
            else:
                raise TimeoutError(
                    f"timed out waiting for target marker: {application_marker}"
                )

            self._perform_startup_reset(
                serial_port,
                rfp,
                reason=retry_reason,
                phase="baseline_startup",
            )

    def stream_baseline_rsu(self, serial_port) -> tuple[int, str]:
        """Send one flash block at a time and wait for its progress ACK.

        The RX boot loader owns two 32 KiB SCI buffers and programs Code Flash
        in the same 32 KiB unit.  An unrestricted 921600-bps host stream can
        lap the flash state machine and leave the final receive buffer partial.
        The existing progress line is emitted only after the corresponding
        flash write completes, so it is the natural flow-control boundary.
        """
        path = self.args.baseline_rsu
        expected_size = path.stat().st_size
        if expected_size % BOOTLOADER_FLASH_BLOCK_SIZE:
            raise ValueError(
                "baseline RSU size must be a multiple of the boot-loader flash block"
            )

        sent = 0
        digest = hashlib.sha256()
        deadline = time.monotonic() + self.args.transfer_timeout
        with path.open("rb") as source:
            while sent < expected_size:
                block = source.read(BOOTLOADER_FLASH_BLOCK_SIZE)
                if len(block) != BOOTLOADER_FLASH_BLOCK_SIZE:
                    raise IOError(
                        f"short baseline RSU block: {len(block)}/"
                        f"{BOOTLOADER_FLASH_BLOCK_SIZE} bytes"
                    )
                for offset in range(0, len(block), self.args.chunk_size):
                    chunk = block[offset : offset + self.args.chunk_size]
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"timed out after sending {sent}/{expected_size} bytes"
                        )
                    written = serial_port.write(chunk)
                    if written != len(chunk):
                        raise IOError(f"short UART write: {written}/{len(chunk)} bytes")
                    if self.args.inter_chunk_delay:
                        time.sleep(self.args.inter_chunk_delay)

                serial_port.flush()
                digest.update(block)
                sent += len(block)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"timed out waiting for flash progress after {sent}/{expected_size} bytes"
                    )
                progress_marker = f"({sent // 1024}/{expected_size // 1024}KB)."
                self.wait_for(serial_port, progress_marker, remaining)

        if sent != expected_size:
            raise IOError(f"RSU transfer size mismatch: {sent}/{expected_size}")
        return sent, digest.hexdigest()

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
        serial_port = BufferedSerialReader(
            open_serial(self.args.port, self.args.baud)
        )
        sent = 0
        digest = None
        transaction_error = None
        try:
            serial_port.reset_input_buffer()
            serial_port.reset_output_buffer()
            serial_port.start()
            run_checked(rfp.run_command(), label="boot-loader release")
            # LittleFS diagnostics can be emitted between the boot loader's
            # prefix and trailing "found." text.  Require both in order so the
            # proof remains strict without assuming one atomic UART line.
            self.wait_for(serial_port, KEY_LOAD_MARKER, self.args.boot_timeout)
            self.wait_for(serial_port, KEY_FOUND_MARKER, self.args.boot_timeout)
            self.wait_for(serial_port, READY_MARKER, self.args.boot_timeout)
            sent, digest = self.stream_baseline_rsu(serial_port)
            self.wait_for(
                serial_port,
                BOOT_REQUIRED["install_completed"],
                self.args.install_timeout,
            )
            self.wait_for(serial_port, BOOT_REQUIRED["jump"], self.args.install_timeout)
            self.wait_for_application_ready(serial_port, rfp)

            deadline = time.monotonic() + self.args.ota_timeout
            while time.monotonic() < deadline:
                self._read(serial_port)
                retry_reason = self._startup_retry_reason()
                if retry_reason is not None:
                    self._perform_startup_reset(
                        serial_port,
                        rfp,
                        reason=retry_reason,
                        phase="ota_observation",
                    )
                    continue
                if self.ota.first_error() is not None:
                    error = self.ota.first_error()
                    raise RuntimeError(f"OTA fail-close marker: {error['classification']}")
                if self._runtime_success_ready():
                    break
            else:
                raise TimeoutError(
                    "candidate OTA did not reach accepted-and-reported-success state"
                )
        except BaseException as exc:
            transaction_error = exc
            raise
        finally:
            shutdown_error = None
            try:
                if transaction_error is None:
                    serial_port.stop_after_quiet()
                else:
                    serial_port.stop()
                while serial_port.in_waiting:
                    self._read(serial_port)
            except Exception as exc:
                shutdown_error = exc
            try:
                serial_port.close()
            except Exception as exc:
                if shutdown_error is None:
                    shutdown_error = exc
            self.uart_capture = serial_port.stats()
            if transaction_error is None and shutdown_error is not None:
                raise shutdown_error

        missing_boot = [name for name, count in self.boot_hits.items() if count == 0]
        ota_summary = self.ota.build_summary(
            total_bytes=self.total_uart_bytes,
            elapsed=time.monotonic() - self.started,
            success=self.ota.is_success(),
        )
        baseline_tls_before_activate = self._baseline_tls_before_activate()
        candidate_tls_after_activate = self._candidate_tls_after_activate()
        capacity_proof = self._capacity_proof()
        success = (
            not missing_boot
            and self._runtime_success_ready()
        )
        if success:
            classification = "pass"
        elif (
            missing_boot
            or not ota_summary["success"]
            or not self.ota.has_marker("ota_completed")
            or not ota_summary["tls_version_ok"]
            or not baseline_tls_before_activate
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
            "uart_capture": self.uart_capture,
            "ota": ota_summary,
            "image_acceptance_observed": self.ota.has_marker("image_accepted"),
            "image_commit_observed": self.ota.has_marker("image_committed"),
            "ota_success_report_observed": self.ota.has_marker("ota_completed"),
            "baseline_tls_before_activate": baseline_tls_before_activate,
            "candidate_tls_after_activate": candidate_tls_after_activate,
            "post_ota_capacity": capacity_proof,
            "startup_recovery": {
                "reset_limit": int(getattr(self.args, "startup_reset_retries", 2)),
                "resets_used": len(self.startup_reset_events),
                "events": self.startup_reset_events,
            },
            "duration_seconds": round(time.monotonic() - self.started, 3),
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-rsu", type=_required_file, required=True)
    parser.add_argument("--baseline-version", default="0.1.0")
    parser.add_argument("--candidate-version", default="0.1.1")
    parser.add_argument(
        "--require-tls-version",
        choices=("TLSv1.2", "TLSv1.3"),
        default="TLSv1.2",
    )
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
    parser.add_argument("--startup-reset-retries", type=int, default=2)
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
    if not 0 <= args.startup_reset_retries <= 3:
        parser.error("--startup-reset-retries must be between 0 and 3")
    if args.cleanup_plaintext and args.cleanup_root is None:
        parser.error("--cleanup-root is required with --cleanup-plaintext")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    transaction = None
    try:
        transaction = Rx671OtaTransaction(args)
        summary = transaction.run()
        status = 0 if summary["success"] else 1
    except Exception as exc:
        summary = {
            "success": False,
            "classification": type(exc).__name__,
            "message": str(exc),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        if transaction is not None and transaction.uart_capture is not None:
            summary["uart_capture"] = transaction.uart_capture
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

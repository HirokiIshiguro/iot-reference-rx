#!/usr/bin/env python3
"""Validate the RX multi-TLS UART evidence contract.

Expected firmware markers are deliberately machine-readable::

    [MULTI_TLS] SESSION_UP s=1 cid=89abcdef net=0x100 tls=0x200 \
        sock=1 gen=1
    [MULTI_TLS] BOTH_UP
    [MULTI_TLS] HEARTBEAT_TX session=1 seq=1
    [MULTI_TLS] HEARTBEAT_RX session=1 seq=1
    [MULTI_TLS] SESSION_DOWN session=2 reason=ci_reconnect
    [MULTI_TLS] TEST_COMPLETE

The monitor does not accept marker presence alone.  It checks event order,
identity separation, two bounded BOTH_UP windows, matching TX/RX heartbeat
sequences, and continued session-1 traffic while session 2 reconnects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MARKER_RE = re.compile(r"\[MULTI_TLS\]\s+(?P<event>[A-Z0-9_]+)(?P<fields>.*)$")
REQUIRED_IDENTITY_FIELDS = ("client_id", "network_ctx", "tls_ctx", "socket")
REQUIRED_SESSION_UP_FIELDS = REQUIRED_IDENTITY_FIELDS + ("connection_generation",)
FIELD_ALIASES = {
    "s": "session",
    "id": "session",
    "cid": "client_id",
    "net": "network_ctx",
    "network": "network_ctx",
    "network_context": "network_ctx",
    "tls": "tls_ctx",
    "tls_context": "tls_ctx",
    "sock": "socket",
    "socket_id": "socket",
    "gen": "connection_generation",
}
SESSION_IDS = (1, 2)


def _round(value: float) -> float:
    return round(float(value), 3)


def parse_marker(line: str) -> tuple[str, dict[str, str]] | None:
    """Parse one UART line, returning ``(event, fields)`` for our markers."""

    match = MARKER_RE.search(line)
    if not match:
        return None

    fields: dict[str, str] = {}
    try:
        tokens = shlex.split(match.group("fields").strip())
    except ValueError:
        return match.group("event"), {"_parse_error": "invalid quoting"}

    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        key = FIELD_ALIASES.get(key.strip(), key.strip())
        fields[key] = value.strip()
    return match.group("event"), fields


class MultiTlsEvidence:
    """Stateful evaluator for timestamped multi-TLS UART lines."""

    def __init__(
        self,
        min_overlap_seconds: float = 30.0,
        max_duration_seconds: float = 180.0,
        require_tsip_wait: bool = False,
    ):
        if min_overlap_seconds < 0:
            raise ValueError("min_overlap_seconds must be non-negative")
        if max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")

        self.min_overlap_seconds = float(min_overlap_seconds)
        self.max_duration_seconds = float(max_duration_seconds)
        self.require_tsip_wait = bool(require_tsip_wait)
        self.events: list[dict[str, Any]] = []
        self.protocol_errors: list[str] = []
        self.up = {session: False for session in SESSION_IDS}
        self.active_identity: dict[int, dict[str, str] | None] = {
            session: None for session in SESSION_IDS
        }
        self.up_events: dict[int, list[dict[str, Any]]] = {session: [] for session in SESSION_IDS}
        self.down_events: dict[int, list[dict[str, Any]]] = {session: [] for session in SESSION_IDS}
        self.heartbeats: dict[int, dict[str, list[dict[str, Any]]]] = {
            session: {"tx": [], "rx": []} for session in SESSION_IDS
        }
        self.both_up_markers: list[dict[str, Any]] = []
        self.identity_checks: list[dict[str, Any]] = []
        self.overlap_windows: list[dict[str, Any]] = []
        self.current_overlap: dict[str, Any] | None = None
        self.complete_at: float | None = None
        self.tsip_wait_evidence: dict[str, Any] | None = None
        self.last_elapsed = 0.0

    def consume_line(self, line: str, elapsed: float) -> bool:
        """Consume one line.  Return true when TEST_COMPLETE is observed."""

        elapsed = float(elapsed)
        if elapsed < self.last_elapsed:
            self.protocol_errors.append(
                f"non-monotonic timestamp: {elapsed:.3f} after {self.last_elapsed:.3f}"
            )
        self.last_elapsed = max(self.last_elapsed, elapsed)

        parsed = parse_marker(line)
        if parsed is None:
            return self.complete_at is not None

        event, fields = parsed
        record = {
            "event": event,
            "at_seconds": _round(elapsed),
            "fields": fields,
            "line": line.rstrip("\r\n"),
        }
        self.events.append(record)
        if "_parse_error" in fields:
            self.protocol_errors.append(f"{event}: {fields['_parse_error']}")

        if event == "SESSION_UP":
            self._session_up(fields, elapsed, record)
        elif event == "SESSION_DOWN":
            self._session_down(fields, elapsed, record)
        elif event in ("HEARTBEAT_TX", "HEARTBEAT_RX"):
            self._heartbeat(event, fields, elapsed, record)
        elif event == "BOTH_UP":
            self._both_up(elapsed, record)
        elif event == "ERROR":
            self.protocol_errors.append(f"firmware error marker: {line.rstrip()}")
        elif event == "TEST_COMPLETE":
            if self.complete_at is None:
                self.complete_at = elapsed
                self._capture_tsip_wait(fields)
            else:
                self.protocol_errors.append("duplicate TEST_COMPLETE marker")
        else:
            self.protocol_errors.append(f"unknown MULTI_TLS event: {event}")
        return self.complete_at is not None

    def _capture_tsip_wait(self, fields: dict[str, str]) -> None:
        mode = fields.get("tsip_wait_mode", "")
        calls_text = fields.get("tsip_wait_calls", "")
        delays_text = fields.get("tsip_wait_delays", "")

        if not (mode or calls_text or delays_text):
            return

        try:
            calls = int(calls_text)
            delays = int(delays_text)
            if calls < 0 or delays < 0:
                raise ValueError
        except ValueError:
            self.protocol_errors.append(
                "TEST_COMPLETE: TSIP wait counters must be non-negative integers"
            )
            calls = None
            delays = None

        self.tsip_wait_evidence = {
            "mode": mode,
            "calls": calls,
            "delays": delays,
        }

    def _session(self, event: str, fields: dict[str, str]) -> int | None:
        try:
            session = int(fields.get("session", ""))
        except ValueError:
            session = -1
        if session not in SESSION_IDS:
            self.protocol_errors.append(f"{event}: session must be 1 or 2")
            return None
        return session

    def _session_up(
        self, fields: dict[str, str], elapsed: float, record: dict[str, Any]
    ) -> None:
        session = self._session("SESSION_UP", fields)
        if session is None:
            return

        missing = [field for field in REQUIRED_SESSION_UP_FIELDS if not fields.get(field)]
        if missing:
            self.protocol_errors.append(
                f"SESSION_UP session={session}: missing {', '.join(missing)}"
            )
        generation = fields.get("connection_generation", "")
        try:
            if int(generation) <= 0:
                raise ValueError
        except ValueError:
            self.protocol_errors.append(
                f"SESSION_UP session={session}: connection_generation must be a positive integer"
            )
        identity = {field: fields.get(field, "") for field in REQUIRED_IDENTITY_FIELDS}
        up_event = {
            "at_seconds": _round(elapsed),
            **identity,
            "connection_generation": generation,
            "line": record["line"],
        }
        self.up_events[session].append(up_event)
        self.active_identity[session] = identity
        self.up[session] = True
        self._start_overlap_if_needed(elapsed)

    def _session_down(
        self, fields: dict[str, str], elapsed: float, record: dict[str, Any]
    ) -> None:
        session = self._session("SESSION_DOWN", fields)
        if session is None:
            return
        if not self.up[session]:
            self.protocol_errors.append(f"SESSION_DOWN session={session}: session was not up")
        self._close_overlap(elapsed)
        self.up[session] = False
        self.down_events[session].append(
            {
                "at_seconds": _round(elapsed),
                "reason": fields.get("reason", ""),
                "line": record["line"],
            }
        )

    def _heartbeat(
        self, event: str, fields: dict[str, str], elapsed: float, record: dict[str, Any]
    ) -> None:
        session = self._session(event, fields)
        if session is None:
            return
        seq = fields.get("seq", "")
        if not seq:
            self.protocol_errors.append(f"{event} session={session}: missing seq")
        if not self.up[session]:
            self.protocol_errors.append(f"{event} session={session}: session was not up")
        direction = "tx" if event.endswith("_TX") else "rx"
        self.heartbeats[session][direction].append(
            {"at_seconds": _round(elapsed), "seq": seq, "line": record["line"]}
        )

    def _both_up(self, elapsed: float, record: dict[str, Any]) -> None:
        if not all(self.up.values()):
            self.protocol_errors.append("BOTH_UP marker observed while a session was down")
            return
        self._start_overlap_if_needed(elapsed)
        marker = {"at_seconds": _round(elapsed), "line": record["line"]}
        self.both_up_markers.append(marker)
        if self.current_overlap is not None:
            self.current_overlap["both_up_markers"].append(_round(elapsed))

        identities = {session: dict(self.active_identity[session] or {}) for session in SESSION_IDS}
        checks = {
            field: bool(identities[1].get(field))
            and bool(identities[2].get(field))
            and identities[1].get(field) != identities[2].get(field)
            for field in REQUIRED_IDENTITY_FIELDS
        }
        self.identity_checks.append(
            {
                "at_seconds": _round(elapsed),
                "sessions": {str(key): value for key, value in identities.items()},
                "distinct": checks,
                "success": all(checks.values()),
            }
        )

    def _start_overlap_if_needed(self, elapsed: float) -> None:
        if all(self.up.values()) and self.current_overlap is None:
            self.current_overlap = {
                "start_seconds": _round(elapsed),
                "both_up_markers": [],
            }

    def _close_overlap(self, elapsed: float) -> None:
        if self.current_overlap is None:
            return
        window = dict(self.current_overlap)
        window["end_seconds"] = _round(elapsed)
        window["duration_seconds"] = _round(elapsed - window["start_seconds"])
        self.overlap_windows.append(window)
        self.current_overlap = None

    def _windows_at(self, end: float) -> list[dict[str, Any]]:
        windows = [dict(window) for window in self.overlap_windows]
        if self.current_overlap is not None:
            window = dict(self.current_overlap)
            window["both_up_markers"] = list(window["both_up_markers"])
            window["end_seconds"] = _round(end)
            window["duration_seconds"] = _round(end - window["start_seconds"])
            windows.append(window)
        return windows

    def _matching_sequences(self, session: int, start: float, end: float) -> list[str]:
        tx = {
            item["seq"]
            for item in self.heartbeats[session]["tx"]
            if start <= item["at_seconds"] <= end and item["seq"]
        }
        rx = {
            item["seq"]
            for item in self.heartbeats[session]["rx"]
            if start <= item["at_seconds"] <= end and item["seq"]
        }
        return sorted(tx & rx)

    @staticmethod
    def _first_after(events: list[dict[str, Any]], after: float) -> float | None:
        for event in events:
            at = float(event["at_seconds"])
            if at > after:
                return at
        return None

    @staticmethod
    def _first_at_or_after(events: list[dict[str, Any]], threshold: float) -> float | None:
        """Return the first event at or after a rounded UART timestamp."""

        for event in events:
            at = float(event["at_seconds"])
            if at >= threshold:
                return at
        return None

    def build_summary(self, elapsed: float | None = None, timed_out: bool = False) -> dict[str, Any]:
        """Return the complete JSON-serializable verdict."""

        end = self.complete_at if self.complete_at is not None else (
            self.last_elapsed if elapsed is None else float(elapsed)
        )
        first_both = (
            float(self.both_up_markers[0]["at_seconds"]) if self.both_up_markers else None
        )
        session2_down = (
            self._first_after(self.down_events[2], first_both) if first_both is not None else None
        )
        session2_reconnect = (
            self._first_after(self.up_events[2], session2_down)
            if session2_down is not None
            else None
        )
        second_both = (
            # Firmware emits SESSION_UP and BOTH_UP consecutively.  At UART
            # millisecond resolution they can legitimately have equal
            # timestamps even though the markers are ordered correctly.
            self._first_at_or_after(self.both_up_markers, session2_reconnect)
            if session2_reconnect is not None
            else None
        )
        initial_identity_check = self.identity_checks[0] if self.identity_checks else None
        post_identity_check = next(
            (
                check
                for check in self.identity_checks
                if second_both is not None and check["at_seconds"] == second_both
            ),
            None,
        )
        session2_down_event = next(
            (
                event
                for event in self.down_events[2]
                if session2_down is not None and event["at_seconds"] == session2_down
            ),
            None,
        )
        initial_session2_up = self.up_events[2][0] if self.up_events[2] else None
        reconnect_session2_up = next(
            (
                event
                for event in self.up_events[2]
                if session2_reconnect is not None and event["at_seconds"] == session2_reconnect
            ),
            None,
        )
        try:
            initial_session2_generation = int(initial_session2_up["connection_generation"])
        except (KeyError, TypeError, ValueError):
            initial_session2_generation = None
        try:
            reconnect_session2_generation = int(reconnect_session2_up["connection_generation"])
        except (KeyError, TypeError, ValueError):
            reconnect_session2_generation = None

        initial_overlap = (
            session2_down - first_both
            if first_both is not None and session2_down is not None
            else 0.0
        )
        post_overlap = (
            end - second_both if second_both is not None and end >= second_both else 0.0
        )
        initial_pairs = {
            str(session): self._matching_sequences(session, first_both, session2_down)
            if first_both is not None and session2_down is not None
            else []
            for session in SESSION_IDS
        }
        outage_pairs = (
            self._matching_sequences(1, session2_down, session2_reconnect)
            if session2_down is not None and session2_reconnect is not None
            else []
        )
        post_pairs = {
            str(session): self._matching_sequences(session, second_both, end)
            if second_both is not None
            else []
            for session in SESSION_IDS
        }
        session1_down_during_test = bool(
            first_both is not None
            and any(
                first_both < float(event["at_seconds"]) <= end
                for event in self.down_events[1]
            )
        )
        session2_down_after_reconnect = bool(
            session2_reconnect is not None
            and any(
                session2_reconnect < float(event["at_seconds"]) <= end
                for event in self.down_events[2]
            )
        )

        checks = {
            "test_complete_seen": self.complete_at is not None,
            "duration_within_bound": self.complete_at is not None
            and self.complete_at <= self.max_duration_seconds,
            "initial_both_up_seen": first_both is not None,
            "initial_identities_distinct": bool(initial_identity_check)
            and initial_identity_check["success"],
            "initial_overlap_long_enough": initial_overlap >= self.min_overlap_seconds,
            "initial_session_1_tx_rx": bool(initial_pairs["1"]),
            "initial_session_2_tx_rx": bool(initial_pairs["2"]),
            "session_2_disconnect_seen": session2_down is not None,
            "session_2_disconnect_requested": bool(session2_down_event)
            and session2_down_event["reason"] == "ci_reconnect",
            "session_2_reconnect_seen": session2_reconnect is not None,
            "session_2_client_id_stable": bool(initial_session2_up)
            and bool(reconnect_session2_up)
            and initial_session2_up["client_id"] == reconnect_session2_up["client_id"],
            "session_2_connection_generation_increased": initial_session2_generation is not None
            and reconnect_session2_generation is not None
            and reconnect_session2_generation > initial_session2_generation,
            "session_1_stayed_up": not session1_down_during_test,
            "session_1_tx_rx_during_session_2_outage": bool(outage_pairs),
            "post_reconnect_both_up_seen": second_both is not None,
            "post_reconnect_identities_distinct": bool(post_identity_check)
            and post_identity_check["success"],
            "post_reconnect_overlap_long_enough": post_overlap >= self.min_overlap_seconds,
            "post_reconnect_session_1_tx_rx": bool(post_pairs["1"]),
            "post_reconnect_session_2_tx_rx": bool(post_pairs["2"]),
            "session_2_stable_after_reconnect": not session2_down_after_reconnect,
            "tsip_wait_hook_exercised": (
                not self.require_tsip_wait
                or (
                    bool(self.tsip_wait_evidence)
                    and self.tsip_wait_evidence["mode"] == "hybrid_tick"
                    and bool(self.tsip_wait_evidence["calls"])
                    and bool(self.tsip_wait_evidence["delays"])
                )
            ),
            "no_protocol_errors": not self.protocol_errors,
        }
        failures = [name for name, passed in checks.items() if not passed]
        windows = self._windows_at(end)
        return {
            "schema_version": 1,
            "success": not failures,
            "result": "PASS" if not failures else "FAIL",
            "duration_seconds": _round(end),
            "max_duration_seconds": self.max_duration_seconds,
            "min_overlap_seconds": self.min_overlap_seconds,
            "timed_out": bool(timed_out),
            "checks": checks,
            "failures": failures,
            "protocol_errors": list(self.protocol_errors),
            "timeline": {
                "first_both_up_seconds": _round(first_both) if first_both is not None else None,
                "session_2_down_seconds": _round(session2_down) if session2_down is not None else None,
                "session_2_reconnect_seconds": _round(session2_reconnect)
                if session2_reconnect is not None
                else None,
                "session_2_initial_connection_generation": initial_session2_generation,
                "session_2_reconnect_connection_generation": reconnect_session2_generation,
                "second_both_up_seconds": _round(second_both) if second_both is not None else None,
                "test_complete_seconds": _round(self.complete_at)
                if self.complete_at is not None
                else None,
                "initial_overlap_seconds": _round(initial_overlap),
                "post_reconnect_overlap_seconds": _round(post_overlap),
            },
            "heartbeat_evidence": {
                "initial_matching_sequences": initial_pairs,
                "session_1_outage_matching_sequences": outage_pairs,
                "post_reconnect_matching_sequences": post_pairs,
            },
            "tsip_wait_evidence": self.tsip_wait_evidence,
            "overlap_windows": windows,
            "identity_checks": self.identity_checks,
            "sessions": {
                str(session): {
                    "up_events": self.up_events[session],
                    "down_events": self.down_events[session],
                    "heartbeat_tx": self.heartbeats[session]["tx"],
                    "heartbeat_rx": self.heartbeats[session]["rx"],
                }
                for session in SESSION_IDS
            },
            "events": self.events,
        }


def _write_raw(path: Path | None, elapsed: float, text: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        stamp = datetime.now(timezone.utc).isoformat()
        handle.write(f"[{stamp}][+{elapsed:08.3f}s] {text}")


def _subprocess_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_reset_command(command: str, timeout: float) -> dict[str, Any]:
    """Run an external reset after UART capture is active."""

    started = time.monotonic()
    print(f"[RESET] Running: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        reset = {
            "requested": True,
            "success": False,
            "failure": "reset_command_timeout",
            "return_code": None,
            "timeout_seconds": timeout,
            "duration_seconds": _round(time.monotonic() - started),
            "stdout": _subprocess_output(exc.stdout),
            "stderr": _subprocess_output(exc.stderr),
        }
        print(f"[RESET][FAIL] command timed out after {timeout:g}s")
        return reset
    except Exception as exc:  # pragma: no cover - OS-specific failures
        reset = {
            "requested": True,
            "success": False,
            "failure": "reset_command_error",
            "return_code": None,
            "timeout_seconds": timeout,
            "duration_seconds": _round(time.monotonic() - started),
            "stdout": "",
            "stderr": str(exc),
        }
        print(f"[RESET][FAIL] command error: {exc}")
        return reset

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    for output_line in stdout.splitlines():
        if output_line.strip():
            print(f"[RESET] {output_line.strip()}")
    progress_re = re.compile(r"^\d+%\s*\[")
    for output_line in stderr.splitlines():
        if output_line.strip() and not progress_re.match(output_line.strip()):
            print(f"[RESET][STDERR] {output_line.strip()}")

    success = result.returncode == 0
    reset = {
        "requested": True,
        "success": success,
        "failure": None if success else "reset_command_nonzero_exit",
        "return_code": result.returncode,
        "timeout_seconds": timeout,
        "duration_seconds": _round(time.monotonic() - started),
        "stdout": stdout,
        "stderr": stderr,
    }
    status = "PASS" if success else "FAIL"
    print(f"[RESET][{status}] command exited with code {result.returncode}")
    return reset


def _apply_reset_result(summary: dict[str, Any], reset: dict[str, Any]) -> None:
    summary["reset_command"] = reset
    summary["checks"]["reset_command_succeeded"] = reset["success"]
    if not reset["success"]:
        summary["success"] = False
        summary["result"] = "FAIL"
        if reset["failure"] not in summary["failures"]:
            summary["failures"].append(reset["failure"])


def monitor_uart(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import serial
    except ImportError as exc:  # pragma: no cover - depends on runner image
        raise RuntimeError("pyserial not installed; run: pip install pyserial") from exc

    evidence = MultiTlsEvidence(
        args.min_overlap_seconds,
        args.timeout,
        require_tsip_wait=getattr(args, "require_tsip_wait", False),
    )
    partial = ""
    total_bytes = 0
    start = time.monotonic()
    timed_out = False
    reset_result: dict[str, Any] = {
        "requested": False,
        "success": True,
        "failure": None,
        "return_code": None,
        "timeout_seconds": args.reset_timeout,
        "duration_seconds": 0.0,
        "stdout": "",
        "stderr": "",
    }

    if args.raw_log:
        args.raw_log.parent.mkdir(parents=True, exist_ok=True)
        args.raw_log.write_text("", encoding="utf-8")

    port = serial.Serial(
        port=args.uart_port,
        baudrate=args.baud,
        timeout=0.1,
        write_timeout=10,
        dsrdtr=False,
        rtscts=False,
    )
    try:
        port.reset_input_buffer()
        if args.reset_cmd:
            reset_result = run_reset_command(args.reset_cmd, args.reset_timeout)
            if not reset_result["success"]:
                elapsed = min(time.monotonic() - start, args.timeout)
                summary = evidence.build_summary(elapsed=elapsed, timed_out=False)
                _apply_reset_result(summary, reset_result)
                summary["uart_port"] = args.uart_port
                summary["baud"] = args.baud
                summary["total_bytes"] = total_bytes
                return summary
        # Match the existing RX72N MQTT monitor: the reset command has its own
        # timeout, while the UART evidence timeout starts after reset completes.
        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= args.timeout:
                timed_out = evidence.complete_at is None
                break
            chunk = port.read(port.in_waiting or 1)
            if not chunk:
                continue
            total_bytes += len(chunk)
            text = chunk.decode("utf-8", errors="replace")
            sys.stdout.write(text)
            sys.stdout.flush()
            _write_raw(args.raw_log, elapsed, text)
            content = partial + text
            lines = content.splitlines(keepends=True)
            if lines and not lines[-1].endswith(("\n", "\r")):
                partial = lines.pop()
            else:
                partial = ""
            for line in lines:
                if evidence.consume_line(line.strip(), time.monotonic() - start):
                    break
            if evidence.complete_at is not None:
                break
    finally:
        port.close()

    elapsed = min(time.monotonic() - start, args.timeout)
    summary = evidence.build_summary(elapsed=elapsed, timed_out=timed_out)
    _apply_reset_result(summary, reset_result)
    summary["uart_port"] = args.uart_port
    summary["baud"] = args.baud
    summary["total_bytes"] = total_bytes
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify two persistent TLS/MQTT sessions from UART")
    parser.add_argument("--uart-port", required=True)
    parser.add_argument("--baud", type=int, default=int(os.environ.get("UART_BAUD_RATE", "921600")))
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("MULTI_TLS_TIMEOUT_SECONDS", "180")),
        help="Hard observation bound in seconds (default: 180)",
    )
    parser.add_argument(
        "--min-overlap-seconds",
        type=float,
        default=float(os.environ.get("MULTI_TLS_MIN_OVERLAP_SECONDS", "30")),
        help="Minimum duration required for both initial and post-reconnect BOTH_UP windows",
    )
    parser.add_argument(
        "--reset-cmd",
        help="External reset command to run after opening and draining the UART",
    )
    parser.add_argument(
        "--reset-timeout",
        type=float,
        default=float(os.environ.get("MULTI_TLS_RESET_TIMEOUT_SECONDS", "180")),
        help="Reset command timeout in seconds (default: 180)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Monitor an already-running target without issuing a reset",
    )
    parser.add_argument(
        "--require-tsip-wait",
        action="store_true",
        help="Require non-zero hybrid TSIP wait-hook counters in TEST_COMPLETE",
    )
    parser.add_argument("--raw-log", type=Path)
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args(argv)
    if not args.no_reset and not args.reset_cmd:
        parser.error("--reset-cmd is required unless --no-reset is specified")
    if args.no_reset:
        args.reset_cmd = None
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = monitor_uart(args)
    except Exception as exc:
        summary = {
            "schema_version": 1,
            "success": False,
            "result": "FAIL",
            "failures": ["monitor_error"],
            "monitor_error": str(exc),
        }

    rendered = json.dumps(summary, indent=2, ensure_ascii=True)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(rendered + "\n", encoding="utf-8")
    print("\n--- Multi-TLS Summary ---")
    print(rendered)
    if summary.get("success"):
        print("[PASS] MULTI_TLS persistent dual-session evidence verified")
        return 0
    print("[FAIL] MULTI_TLS persistent dual-session evidence incomplete")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

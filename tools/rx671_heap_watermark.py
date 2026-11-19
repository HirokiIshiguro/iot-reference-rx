"""Read the FreeRTOS heap watermark lines that the EK-RX671 application prints on the UART.

The application prints (Projects/aws_wifi_rx671_ek*/e2studio_ccrx/src/aws_wifi_rx671_ek.c)

    RX671 heap: at=<place> free=<bytes> min=<bytes> total=<bytes> tasks=<count>

where min is xPortGetMinimumEverFreeHeapSize(). The value is recorded only: no test passes or fails on it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

HEAP_LINE_RE = re.compile(
    r"RX671 heap: at=(?P<at>\S+) free=(?P<free>\d+) min=(?P<min>\d+) total=(?P<total>\d+) tasks=(?P<tasks>\d+)"
)
_TICK_RE = re.compile(r"tick(\d+)$")


def parse_lines(text: str) -> list[dict]:
    """Every heap line of the text, in order. "boot" counts the restarts of the tick counter (a reset)."""
    entries: list[dict] = []
    boot = 0
    last_tick = -1
    for match in HEAP_LINE_RE.finditer(text):
        tick = _TICK_RE.match(match["at"])
        if tick:
            number = int(tick.group(1))
            if number <= last_tick:
                boot += 1
            last_tick = number
        entries.append({"at": match["at"], "free": int(match["free"]), "min": int(match["min"]),
                        "total": int(match["total"]), "tasks": int(match["tasks"]), "boot": boot})
    return entries


def summarize(text_or_lines: str | Iterable[str]) -> dict:
    """The smallest min of all lines (also across resets) and, per boot, the smallest min of that boot."""
    text = text_or_lines if isinstance(text_or_lines, str) else "\n".join(text_or_lines)
    entries = parse_lines(text)
    if not entries:
        return {"lines": 0}
    lowest = min(entries, key=lambda entry: entry["min"])
    per_boot: dict[int, dict] = {}
    for entry in entries:
        current = per_boot.get(entry["boot"])
        if current is None or entry["min"] < current["min_free_bytes"]:
            per_boot[entry["boot"]] = {"boot": entry["boot"], "min_free_bytes": entry["min"], "at": entry["at"],
                                       "lines": 0}
    for entry in entries:
        per_boot[entry["boot"]]["lines"] += 1
    return {
        "lines": len(entries),
        "min_free_bytes": lowest["min"],
        "at": lowest["at"],
        "total_bytes": lowest["total"],
        "percent": round(100.0 * lowest["min"] / lowest["total"], 1) if lowest["total"] else 0.0,
        "tasks_at_min": lowest["tasks"],
        "per_boot": [per_boot[key] for key in sorted(per_boot)],
    }


def format_line(summary: dict) -> str:
    if not summary.get("lines"):
        return "heap watermark: no line"
    return (f"heap watermark: min free {summary['min_free_bytes']} B of {summary['total_bytes']} B "
            f"({summary['percent']}%) at {summary['at']}")


def report(text: str, json_path: Path | None = None) -> dict:
    """Print the one-line result, write the JSON when a path is given and return the summary."""
    summary = summarize(text)
    print(format_line(summary), flush=True)
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def print_from_json(path: Path) -> None:
    """Print the line of a summary written earlier (the job log shows it, the UART observer log does not)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("heap watermark: no line", flush=True)
        return
    summary = data.get("heap_watermark", data) if isinstance(data, dict) else {}
    print(format_line(summary if isinstance(summary, dict) else {}), flush=True)

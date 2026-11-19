"""Read the memory watermark lines that the EK-RX671 application prints on the UART.

The application prints (Projects/aws_wifi_rx671_ek*/e2studio_ccrx/src/aws_wifi_rx671_ek.c, bsp_usage_probe.c)

    RX671 heap: at=<place> free=<bytes> min=<bytes> largest=<bytes> blocks=<count> total=<bytes> tasks=<count>
    RX671 bsp: ustack=<used>/<size> istack=<used>/<size> cheap=<used>/<size>

where min is xPortGetMinimumEverFreeHeapSize() and largest the biggest contiguous free block of the FreeRTOS heap.
bsp is the high water mark of the BSP user stack, the interrupt stack and the C library heap.
The values are recorded only: no test passes or fails on them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

HEAP_LINE_RE = re.compile(
    r"RX671 heap: at=(?P<at>\S+) free=(?P<free>\d+) min=(?P<min>\d+)"
    r"(?: largest=(?P<largest>\d+) blocks=(?P<blocks>\d+))?"
    r" total=(?P<total>\d+) tasks=(?P<tasks>\d+)"
)
BSP_LINE_RE = re.compile(
    r"RX671 bsp: ustack=(?P<ustack>\d+)/(?P<ustack_size>\d+) istack=(?P<istack>\d+)/(?P<istack_size>\d+)"
    r"(?: over=(?P<over>\d+))? cheap=(?P<cheap>\d+)/(?P<cheap_size>\d+)"
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
                        "largest": None if match["largest"] is None else int(match["largest"]),
                        "blocks": None if match["blocks"] is None else int(match["blocks"]),
                        "total": int(match["total"]), "tasks": int(match["tasks"]), "boot": boot})
    return entries


def parse_bsp_lines(text: str) -> list[dict]:
    return [{key: (0 if value is None else int(value)) for key, value in match.groupdict().items()}
            for match in BSP_LINE_RE.finditer(text)]


def summarize_bsp(text: str) -> dict:
    """The largest used value of each BSP area (they only grow, so this is the last line unless a reset intervenes)."""
    entries = parse_bsp_lines(text)
    if not entries:
        return {"lines": 0}
    last = entries[-1]
    return {"lines": len(entries),
            "ustack_used_max": max(e["ustack"] for e in entries), "ustack_size": last["ustack_size"],
            "istack_used_max": max(e["istack"] for e in entries), "istack_size": last["istack_size"],
            "over_max": max(e["over"] for e in entries),
            "cheap_used_max": max(e["cheap"] for e in entries), "cheap_size": last["cheap_size"]}


def summarize(text_or_lines: str | Iterable[str]) -> dict:
    """The smallest min of all lines (also across resets) and, per boot, the smallest min of that boot."""
    text = text_or_lines if isinstance(text_or_lines, str) else "\n".join(text_or_lines)
    entries = parse_lines(text)
    bsp = summarize_bsp(text)
    if not entries:
        return {"lines": 0, "bsp": bsp}
    lowest = min(entries, key=lambda entry: entry["min"])
    per_boot: dict[int, dict] = {}
    for entry in entries:
        current = per_boot.get(entry["boot"])
        if current is None or entry["min"] < current["min_free_bytes"]:
            per_boot[entry["boot"]] = {"boot": entry["boot"], "min_free_bytes": entry["min"], "at": entry["at"],
                                       "lines": 0}
    for entry in entries:
        per_boot[entry["boot"]]["lines"] += 1
    summary = {
        "lines": len(entries),
        "min_free_bytes": lowest["min"],
        "at": lowest["at"],
        "total_bytes": lowest["total"],
        "percent": round(100.0 * lowest["min"] / lowest["total"], 1) if lowest["total"] else 0.0,
        "tasks_at_min": lowest["tasks"],
        "per_boot": [per_boot[key] for key in sorted(per_boot)],
        "bsp": bsp,
    }
    with_largest = [entry for entry in entries if entry["largest"] is not None]
    if with_largest:
        smallest = min(with_largest, key=lambda entry: entry["largest"])
        summary["min_largest_free_block_bytes"] = smallest["largest"]
        summary["min_largest_free_block_at"] = smallest["at"]
        summary["max_free_blocks"] = max(entry["blocks"] for entry in with_largest)
    return summary


def format_line(summary: dict) -> str:
    if not summary.get("lines"):
        return "heap watermark: no line"
    return (f"heap watermark: min free {summary['min_free_bytes']} B of {summary['total_bytes']} B "
            f"({summary['percent']}%) at {summary['at']}")


def format_extra_lines(summary: dict) -> list[str]:
    """The smallest largest-free-block and the BSP areas: the lines after the main one (none when nothing was read)."""
    lines: list[str] = []
    if summary.get("min_largest_free_block_bytes") is not None:
        lines.append(f"heap largest free block: min {summary['min_largest_free_block_bytes']} B "
                     f"at {summary['min_largest_free_block_at']} (up to {summary['max_free_blocks']} free blocks)")
    bsp = summary.get("bsp") or {}
    if bsp.get("lines"):
        lines.append(f"bsp watermark: ustack {bsp['ustack_used_max']}/{bsp['ustack_size']} B, "
                     f"istack {bsp['istack_used_max']}/{bsp['istack_size']} B (over into SU: {bsp.get('over_max', 0)} B), "
                     f"C library heap {bsp['cheap_used_max']}/{bsp['cheap_size']} B")
    return lines


def _print_summary(summary: dict) -> None:
    print(format_line(summary), flush=True)
    for line in format_extra_lines(summary):
        print(line, flush=True)


def report(text: str, json_path: Path | None = None) -> dict:
    """Print the result lines, write the JSON when a path is given and return the summary."""
    summary = summarize(text)
    _print_summary(summary)
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def print_from_json(path: Path) -> None:
    """Print the lines of a summary written earlier (the job log shows it, the UART observer log does not)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("heap watermark: no line", flush=True)
        return
    summary = data.get("heap_watermark", data) if isinstance(data, dict) else {}
    _print_summary(summary if isinstance(summary, dict) else {})

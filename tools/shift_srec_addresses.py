#!/usr/bin/env python3
"""Create an S-record image with selected addresses shifted by a constant."""

from __future__ import annotations

import argparse
from pathlib import Path


RECORD_ADDR_BYTES = {
    "S1": 2,
    "S2": 3,
    "S3": 4,
    "S7": 4,
    "S8": 3,
    "S9": 2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shift Motorola S-record addresses")
    parser.add_argument("--input", required=True, type=Path, help="Input .mot/.srec file")
    parser.add_argument("--output", required=True, type=Path, help="Output .mot/.srec file")
    parser.add_argument("--shift", required=True, type=lambda value: int(value, 0), help="Signed address shift")
    parser.add_argument("--range-start", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--range-end", required=True, type=lambda value: int(value, 0))
    parser.add_argument(
        "--drop-out-of-range",
        action="store_true",
        help="Drop data/start records outside the selected address range",
    )
    return parser.parse_args()


def checksum(record_bytes: list[int]) -> int:
    return (~sum(record_bytes)) & 0xFF


def rewrite_record(line: str, shift: int, range_start: int, range_end: int, drop_out_of_range: bool) -> str | None:
    record_type = line[:2]
    addr_bytes = RECORD_ADDR_BYTES.get(record_type)
    if addr_bytes is None:
        return line

    count = int(line[2:4], 16)
    address_start = 4
    address_end = address_start + (addr_bytes * 2)
    address = int(line[address_start:address_end], 16)
    in_range = range_start <= address <= range_end
    if not in_range:
        return None if drop_out_of_range and record_type in {"S1", "S2", "S3", "S7", "S8", "S9"} else line

    shifted_address = address + shift
    max_address = (1 << (addr_bytes * 8)) - 1
    if shifted_address < 0 or shifted_address > max_address:
        raise ValueError(f"shifted address out of range for {record_type}: 0x{shifted_address:X}")

    data_hex = line[address_end:-2]
    record_bytes = [count]
    for index in range(addr_bytes - 1, -1, -1):
        record_bytes.append((shifted_address >> (index * 8)) & 0xFF)
    record_bytes.extend(bytes.fromhex(data_hex))
    return f"{record_type}{count:02X}{shifted_address:0{addr_bytes * 2}X}{data_hex}{checksum(record_bytes):02X}"


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"input file not found: {args.input}")
    if args.range_end < args.range_start:
        raise SystemExit("--range-end must be greater than or equal to --range-start")

    output_lines: list[str] = []
    shifted_count = 0
    for raw_line in args.input.read_text(encoding="ascii").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rewritten = rewrite_record(line, args.shift, args.range_start, args.range_end, args.drop_out_of_range)
        if rewritten is None:
            continue
        if rewritten != line:
            shifted_count += 1
        output_lines.append(rewritten)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(output_lines) + "\n", encoding="ascii")
    print(f"Wrote {args.output} with {shifted_count} shifted records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

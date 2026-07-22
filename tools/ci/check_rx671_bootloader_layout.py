#!/usr/bin/env python3
"""Validate the EK-RX671 boot-loader S-record and linker map layout."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


BOOT_START = 0xFFFC0000
BOOT_END = 0xFFFFFFFF
BOOT_WINDOW_BYTES = BOOT_END - BOOT_START + 1
OPTION_RANGES = (
    (0xFE7F5D00, 0xFE7F5D7F),
    (0xFE7F7D70, 0xFE7F7D9F),
)


@dataclass(frozen=True)
class DataRecord:
    address: int
    data: bytes

    @property
    def end(self) -> int:
        return self.address + len(self.data) - 1


def parse_srecords(path: Path) -> list[DataRecord]:
    records: list[DataRecord] = []
    address_bytes = {"1": 2, "2": 3, "3": 4}

    for line_number, raw_line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        line = raw_line.strip()
        if not line or not line.startswith("S") or line[1:2] not in address_bytes:
            continue
        try:
            encoded = bytes.fromhex(line[2:])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: malformed S-record") from exc
        if not encoded or encoded[0] != len(encoded) - 1:
            raise ValueError(f"{path}:{line_number}: byte count mismatch")
        if sum(encoded) & 0xFF != 0xFF:
            raise ValueError(f"{path}:{line_number}: checksum mismatch")

        address_length = address_bytes[line[1]]
        address = int.from_bytes(encoded[1 : 1 + address_length], "big")
        data = encoded[1 + address_length : -1]
        if data:
            records.append(DataRecord(address, data))

    if not records:
        raise ValueError(f"{path}: no S1/S2/S3 data records")
    return records


def _contained(start: int, end: int, allowed_start: int, allowed_end: int) -> bool:
    return allowed_start <= start <= end <= allowed_end


def validate_records(records: list[DataRecord]) -> tuple[int, int]:
    boot_records: list[DataRecord] = []
    for record in records:
        if _contained(record.address, record.end, BOOT_START, BOOT_END):
            boot_records.append(record)
            continue
        if any(_contained(record.address, record.end, start, end) for start, end in OPTION_RANGES):
            continue
        raise ValueError(
            f"S-record data outside RX671 boot/option ranges: "
            f"0x{record.address:08X}-0x{record.end:08X}"
        )

    if not boot_records:
        raise ValueError("S-record contains no boot-loader Code Flash data")
    addresses = {record.address + offset for record in boot_records for offset in range(len(record.data))}
    if BOOT_START not in addresses:
        raise ValueError(f"boot entry 0x{BOOT_START:08X} is not populated")
    if not all(address in addresses for address in range(0xFFFFFF80, 0x100000000)):
        raise ValueError("exception/reset vector range 0xFFFFFF80-0xFFFFFFFF is not fully populated")

    used_bytes = sum(len(record.data) for record in boot_records)
    if used_bytes > BOOT_WINDOW_BYTES:
        raise ValueError(
            f"boot payload {used_bytes} bytes exceeds {BOOT_WINDOW_BYTES}-byte reserved window"
        )
    return used_bytes, len(records) - len(boot_records)


def validate_map(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    expected = {
        "PResetPRG": 0xFFFC0000,
        "EXCEPTVECT": 0xFFFFFF80,
        "RESETVECT": 0xFFFFFFFC,
    }
    for section, expected_start in expected.items():
        match = re.search(
            rf"(?m)^{re.escape(section)}\s*$\s*^\s*([0-9a-fA-F]{{8}})\s+",
            text,
        )
        if not match:
            raise ValueError(f"{path}: section {section} is missing from Mapping List")
        actual_start = int(match.group(1), 16)
        if actual_start != expected_start:
            raise ValueError(
                f"{path}: {section} starts at 0x{actual_start:08X}; "
                f"expected 0x{expected_start:08X}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mot", required=True, type=Path)
    parser.add_argument("--map", required=True, type=Path)
    args = parser.parse_args()

    records = parse_srecords(args.mot)
    used_bytes, non_boot_records = validate_records(records)
    validate_map(args.map)
    print(
        "RX671_BOOTLOADER_LAYOUT_PASS "
        f"window=0x{BOOT_START:08X}-0x{BOOT_END:08X} "
        f"reserved={BOOT_WINDOW_BYTES} payload={used_bytes} "
        f"option_records={non_boot_records}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

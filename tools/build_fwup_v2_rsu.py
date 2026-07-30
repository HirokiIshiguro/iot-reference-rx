#!/usr/bin/env python3
"""
Generate a RELFWV2 RSU for the legacy RX72N Envision Kit bootloader.

Unlike the r_fwup sample bootloader, this bootloader expects the RSU payload to
contain the whole bank-1 user image area (excluding the 0x300-byte RSU header +
descriptor) rather than sparse segments only.

The implementation is aligned with the working `mot_to_rsu.py` flow used by the
known-good rx72n-envision-kit pipeline.
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


RSU_HEADER_SIZE = 0x200
RSU_DESCRIPTOR_SIZE = 0x100
IMAGE_FLAG_TESTING = 0xFE
SIG_TYPE = b"sig-sha256-ecdsa"

# Legacy RX72N Envision Kit secure-boot layout.
HW_ID = 0x00000009
USER_PROGRAM_TOP = 0xFFE00300
USER_PROGRAM_BOTTOM = 0xFFFBFFFF
BOOTLOADER_TOP = 0xFFFC0000
BOOTLOADER_BOTTOM = 0xFFFFFFFF
FLASH_WRITE_SIZE = 128
USER_CONST_DATA_TOP = 0x00100800
USER_CONST_DATA_BOTTOM = 0x001077FF
DATA_FLASH_PAD_SIZE = 32768  # bootloader expects one 32 KB DF block


@dataclass(frozen=True)
class PrmLayout:
    device_type: str
    bootloader_start: int
    bootloader_end: int
    user_program_start: int
    user_program_end: int
    flash_write_size: int


def load_prm_layout(prm_path: Path) -> PrmLayout:
    required_fields = {
        "device Type",
        "Bootloader Start Address",
        "Bootloader End Address",
        "User Program Start Address",
        "User Program End Address",
        "Flash Write Size",
    }
    values: dict[str, str] = {}

    with prm_path.open(newline="", encoding="utf-8-sig") as handle:
        for line_no, row in enumerate(csv.reader(handle), 1):
            if not row or all(not column.strip() for column in row):
                continue
            if len(row) != 2:
                raise RuntimeError(
                    f"PRM line {line_no} must contain exactly two columns, got {len(row)}"
                )
            key, value = (column.strip() for column in row)
            if key in values:
                raise RuntimeError(f"duplicate PRM field on line {line_no}: {key}")
            values[key] = value

    missing = sorted(required_fields - values.keys())
    if missing:
        raise RuntimeError(f"missing required PRM fields: {', '.join(missing)}")

    def parse_integer(field: str) -> int:
        try:
            return int(values[field], 0)
        except ValueError as exc:
            raise RuntimeError(
                f"PRM field {field!r} is not an integer: {values[field]!r}"
            ) from exc

    return PrmLayout(
        device_type=values["device Type"],
        bootloader_start=parse_integer("Bootloader Start Address"),
        bootloader_end=parse_integer("Bootloader End Address"),
        user_program_start=parse_integer("User Program Start Address"),
        user_program_end=parse_integer("User Program End Address"),
        flash_write_size=parse_integer("Flash Write Size"),
    )


def validate_prm_layout(layout: PrmLayout) -> None:
    expected_user_payload_start = (
        layout.user_program_start + RSU_HEADER_SIZE + RSU_DESCRIPTOR_SIZE
    )
    mismatches: list[str] = []

    if layout.device_type != "Dual Mode":
        mismatches.append(f"device Type={layout.device_type!r} (expected 'Dual Mode')")
    if expected_user_payload_start != USER_PROGRAM_TOP:
        mismatches.append(
            "User Program Start Address + RSU header/descriptor="
            f"0x{expected_user_payload_start:08X} (expected 0x{USER_PROGRAM_TOP:08X})"
        )
    if layout.user_program_end != USER_PROGRAM_BOTTOM:
        mismatches.append(
            f"User Program End Address=0x{layout.user_program_end:08X} "
            f"(expected 0x{USER_PROGRAM_BOTTOM:08X})"
        )
    if layout.bootloader_start != BOOTLOADER_TOP:
        mismatches.append(
            f"Bootloader Start Address=0x{layout.bootloader_start:08X} "
            f"(expected 0x{BOOTLOADER_TOP:08X})"
        )
    if layout.bootloader_end != BOOTLOADER_BOTTOM:
        mismatches.append(
            f"Bootloader End Address=0x{layout.bootloader_end:08X} "
            f"(expected 0x{BOOTLOADER_BOTTOM:08X})"
        )
    if layout.user_program_end + 1 != layout.bootloader_start:
        mismatches.append(
            "User Program End Address and Bootloader Start Address are not contiguous"
        )
    if layout.flash_write_size != FLASH_WRITE_SIZE:
        mismatches.append(
            f"Flash Write Size={layout.flash_write_size} (expected {FLASH_WRITE_SIZE})"
        )

    if mismatches:
        raise RuntimeError("incompatible RX72N PRM layout: " + "; ".join(mismatches))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RELFWV2 RSU for the legacy RX72N bootloader"
    )
    parser.add_argument("--mot", required=True, type=Path, help="Input Motorola S-record (.mot)")
    parser.add_argument("--prm", required=True, type=Path, help="PRM CSV (validated for compatibility)")
    parser.add_argument("--key", required=True, type=Path, help="ECDSA private key in PEM format")
    parser.add_argument("--output", required=True, type=Path, help="Output .rsu file")
    parser.add_argument("--seq-no", type=int, default=1, help="Sequence number (default: 1)")
    parser.add_argument(
        "--format",
        choices=("legacy-full-rsu", "rtos-ota-payload"),
        default="legacy-full-rsu",
        help=(
            "Output format. legacy-full-rsu is for the UART bootloader. "
            "rtos-ota-payload starts at the FWUP descriptor for AWS OTA PAL."
        ),
    )
    return parser.parse_args()


def parse_mot_file(mot_path: Path) -> tuple[bytearray, bytearray, int, int]:
    user_prog_size = USER_PROGRAM_BOTTOM - USER_PROGRAM_TOP + 1
    const_data_size = USER_CONST_DATA_BOTTOM - USER_CONST_DATA_TOP + 1

    code_flash = bytearray(b"\xFF" * user_prog_size)
    data_flash = bytearray(b"\xFF" * const_data_size)
    code_bytes_written = 0
    data_bytes_written = 0

    with mot_path.open("r", encoding="ascii", errors="strict") as handle:
        for line_no, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                continue

            rec_type = line[0:2]
            if rec_type == "S0":
                continue
            if rec_type == "S1":
                addr_bytes = 2
            elif rec_type == "S2":
                addr_bytes = 3
            elif rec_type == "S3":
                addr_bytes = 4
            elif rec_type in {"S4", "S5", "S6", "S7", "S8", "S9"}:
                continue
            else:
                raise RuntimeError(f"unsupported S-record type on line {line_no}: {rec_type}")

            byte_count = int(line[2:4], 16)
            data_len = byte_count - addr_bytes - 1
            address = int(line[4:4 + addr_bytes * 2], 16)
            data_start = 4 + addr_bytes * 2
            data = bytes.fromhex(line[data_start:data_start + data_len * 2])

            if USER_CONST_DATA_TOP <= address <= USER_CONST_DATA_BOTTOM:
                offset = address - USER_CONST_DATA_TOP
                data_flash[offset:offset + len(data)] = data
                data_bytes_written += len(data)
                continue

            if USER_PROGRAM_TOP <= address <= USER_PROGRAM_BOTTOM + 1:
                offset = address - USER_PROGRAM_TOP
                code_flash[offset:offset + len(data)] = data
                code_bytes_written += len(data)

    return code_flash, data_flash, code_bytes_written, data_bytes_written


def sign_ecdsa(data: bytes, key_path: Path) -> bytes:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    with key_path.open("rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)

    der_signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_signature)
    return r.to_bytes(32, byteorder="big") + s.to_bytes(32, byteorder="big")


def verify_ecdsa(data: bytes, signature: bytes, key_path: Path) -> bool:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    with key_path.open("rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)

    public_key = private_key.public_key()
    r = int.from_bytes(signature[:32], byteorder="big")
    s = int.from_bytes(signature[32:64], byteorder="big")
    der_signature = utils.encode_dss_signature(r, s)

    try:
        public_key.verify(der_signature, data, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False


def build_rsu(code_flash: bytearray, data_flash: bytearray, key_path: Path, seq_no: int) -> bytes:
    user_prog_size = USER_PROGRAM_BOTTOM - USER_PROGRAM_TOP + 1
    exec_addr = USER_PROGRAM_BOTTOM - 3

    descriptor = bytearray(RSU_DESCRIPTOR_SIZE)
    struct.pack_into("<I", descriptor, 0, seq_no)
    struct.pack_into("<I", descriptor, 4, USER_PROGRAM_TOP)
    struct.pack_into("<I", descriptor, 8, USER_PROGRAM_BOTTOM)
    struct.pack_into("<I", descriptor, 12, exec_addr)
    struct.pack_into("<I", descriptor, 16, HW_ID)

    signed_data = bytes(descriptor) + bytes(code_flash[:user_prog_size])
    print(
        f"\nSigning {len(signed_data):,} bytes "
        f"(descriptor={RSU_DESCRIPTOR_SIZE}, code={user_prog_size:,})..."
    )

    signature = sign_ecdsa(signed_data, key_path)
    if not verify_ecdsa(signed_data, signature, key_path):
        raise RuntimeError("signature self-verification failed")
    print("  Verification: PASS")

    rsu = bytearray()
    rsu += b"Renesas"
    rsu += struct.pack("B", IMAGE_FLAG_TESTING)
    rsu += SIG_TYPE + b"\x00" * (32 - len(SIG_TYPE))
    rsu += struct.pack("<I", len(signature))
    rsu += signature + b"\x00" * (256 - len(signature))
    rsu += struct.pack("<I", 1)
    rsu += struct.pack("<I", USER_CONST_DATA_TOP)
    rsu += struct.pack("<I", USER_CONST_DATA_BOTTOM)
    rsu += b"\x00" * 200

    rsu += descriptor
    rsu += code_flash[:user_prog_size]

    const_data_size = USER_CONST_DATA_BOTTOM - USER_CONST_DATA_TOP + 1
    data_flash_block = bytearray(b"\xFF" * DATA_FLASH_PAD_SIZE)
    data_flash_block[:const_data_size] = data_flash[:const_data_size]
    rsu += data_flash_block

    return bytes(rsu)


def build_rtos_ota_payload(code_flash: bytearray, data_flash: bytearray, data_bytes_written: int) -> bytes:
    user_prog_size = USER_PROGRAM_BOTTOM - USER_PROGRAM_TOP + 1

    entries = [(USER_PROGRAM_TOP, user_prog_size)]
    if data_bytes_written > 0:
        entries.append((USER_CONST_DATA_TOP, USER_CONST_DATA_BOTTOM - USER_CONST_DATA_TOP + 1))

    descriptor = bytearray(b"\xFF" * RSU_DESCRIPTOR_SIZE)
    struct.pack_into("<I", descriptor, 0, len(entries))
    for index, (address, size) in enumerate(entries):
        struct.pack_into("<I", descriptor, 4 + (index * 8), address)
        struct.pack_into("<I", descriptor, 8 + (index * 8), size)

    payload = bytearray()
    payload += descriptor
    payload += code_flash[:user_prog_size]
    if data_bytes_written > 0:
        payload += data_flash[:USER_CONST_DATA_BOTTOM - USER_CONST_DATA_TOP + 1]
    return bytes(payload)


def main() -> int:
    args = parse_args()

    if not args.mot.is_file():
        raise SystemExit(f"input .mot not found: {args.mot}")
    if not args.prm.is_file():
        raise SystemExit(f"PRM CSV not found: {args.prm}")
    if not args.key.is_file():
        raise SystemExit(f"private key not found: {args.key}")
    if args.seq_no < 1 or args.seq_no > 0xFFFFFFFF:
        raise SystemExit(f"sequence number must be 1-4294967295, got {args.seq_no}")

    try:
        prm_layout = load_prm_layout(args.prm)
        validate_prm_layout(prm_layout)
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f"PRM validation failed for {args.prm}: {exc}") from exc

    print("=== mot_to_rsu converter ===")
    print(f"  MCU:     RX72N (HW_ID=0x{HW_ID:08X})")
    print(f"  MOT:     {args.mot}")
    print(f"  Key:     {args.key}")
    print(f"  Output:  {args.output}")
    print(f"  Seq No:  {args.seq_no}")
    print()
    print(
        f"  PRM:     {args.prm} "
        f"(validated: user=0x{prm_layout.user_program_start:08X}-"
        f"0x{prm_layout.user_program_end:08X}, "
        f"boot=0x{prm_layout.bootloader_start:08X}-"
        f"0x{prm_layout.bootloader_end:08X}, "
        f"write={prm_layout.flash_write_size})"
    )
    print()
    print("Parsing MOT file...")

    code_flash, data_flash, code_written, data_written = parse_mot_file(args.mot)
    user_prog_size = USER_PROGRAM_BOTTOM - USER_PROGRAM_TOP + 1
    const_data_size = USER_CONST_DATA_BOTTOM - USER_CONST_DATA_TOP + 1

    print(f"  Code flash: {code_written:,} bytes written")
    print(f"  Data flash: {data_written:,} bytes written")
    print(
        f"  Image size: code={user_prog_size:,} bytes ({user_prog_size/1024:.0f} KB), "
        f"data={const_data_size:,} bytes ({const_data_size/1024:.0f} KB)"
    )

    if args.format == "legacy-full-rsu":
        output_data = build_rsu(code_flash, data_flash, args.key, args.seq_no)
    else:
        output_data = build_rtos_ota_payload(code_flash, data_flash, data_written)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output_data)

    print()
    print(f"Output: {args.output}")
    print(f"  Format: {args.format}")
    print(f"  Size: {len(output_data):,} bytes ({len(output_data)/1024:.1f} KB)")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

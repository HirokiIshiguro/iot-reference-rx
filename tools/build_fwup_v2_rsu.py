#!/usr/bin/env python3
"""
Generate a FWUP v2 BareMetal RSU image from a Motorola S-record file.

This matches the RELFWV2 format expected by the phase8b RX72N boot loader.
Only the sparse user-program and data-flash blocks are emitted into the
descriptor + payload area, and the descriptor+payload is ECDSA-signed.
"""

import argparse
import csv
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


MAGIC = b"RELFWV2"
IMAGE_FLAG_TESTING = 0xFE
SIG_TYPE = b"sig-sha256-ecdsa"
HEADER_SIZE = 0x200
DESC_SIZE = 0x100
MAX_SEGMENTS = 31
UNUSED_U32 = 0xFFFFFFFF

PRM_USER_START = "User Program Start Address"
PRM_USER_END = "User Program End Address"
PRM_DATA_START = "Data Flash Start Address"
PRM_DATA_END = "Data Flash End Address"
PRM_FLASH_WRITE_SIZE = "Flash Write Size"


@dataclass
class Region:
    name: str
    start: int
    end: int
    write_size: int

    @property
    def size(self) -> int:
        return self.end - self.start + 1

    @property
    def block_count(self) -> int:
        return (self.size + self.write_size - 1) // self.write_size


def parse_args():
    parser = argparse.ArgumentParser(description="Generate RELFWV2 RSU for phase8b RX72N boot loader")
    parser.add_argument("--mot", required=True, type=Path, help="Input Motorola S-record (.mot)")
    parser.add_argument("--prm", required=True, type=Path, help="ImageGenerator PRM CSV")
    parser.add_argument("--key", required=True, type=Path, help="ECDSA private key in PEM format")
    parser.add_argument("--output", required=True, type=Path, help="Output .rsu file")
    return parser.parse_args()


def parse_int(text: str) -> int:
    value = text.strip()
    return int(value, 0)


def load_regions(prm_path: Path) -> list[Region]:
    values: dict[str, str] = {}
    with prm_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) != 2:
                continue
            key = row[0].strip()
            value = row[1].strip()
            if key:
                values[key] = value

    missing = [
        key
        for key in (PRM_USER_START, PRM_USER_END, PRM_DATA_START, PRM_DATA_END, PRM_FLASH_WRITE_SIZE)
        if key not in values
    ]
    if missing:
        raise RuntimeError(f"missing PRM keys: {', '.join(missing)}")

    write_size = parse_int(values[PRM_FLASH_WRITE_SIZE])
    return [
        Region("code_flash", parse_int(values[PRM_USER_START]), parse_int(values[PRM_USER_END]), write_size),
        Region("data_flash", parse_int(values[PRM_DATA_START]), parse_int(values[PRM_DATA_END]), write_size),
    ]


def iter_srec_records(mot_path: Path):
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
            addr_hex = line[4:4 + addr_bytes * 2]
            data_start = 4 + addr_bytes * 2
            data_hex = line[data_start:data_start + data_len * 2]
            yield int(addr_hex, 16), bytes.fromhex(data_hex)


def build_sparse_segments(mot_path: Path, regions: list[Region]):
    images = {region.name: bytearray(b"\xFF" * region.size) for region in regions}
    flags = {region.name: [False] * region.block_count for region in regions}
    ignored = 0

    for address, data in iter_srec_records(mot_path):
        for offset, byte in enumerate(data):
            current = address + offset
            matched = False
            for region in regions:
                if region.start <= current <= region.end:
                    region_offset = current - region.start
                    images[region.name][region_offset] = byte
                    flags[region.name][region_offset // region.write_size] = True
                    matched = True
                    break
            if not matched:
                ignored += 1

    segments: list[tuple[int, int]] = []
    payload_parts: list[bytes] = []
    for region in regions:
        block_flags = flags[region.name]
        image = images[region.name]
        index = 0
        while index < len(block_flags):
            if not block_flags[index]:
                index += 1
                continue
            start_block = index
            while index < len(block_flags) and block_flags[index]:
                index += 1
            end_block = index
            start_offset = start_block * region.write_size
            size = (end_block - start_block) * region.write_size
            segments.append((region.start + start_offset, size))
            payload_parts.append(bytes(image[start_offset:start_offset + size]))

    if len(segments) > MAX_SEGMENTS:
        raise RuntimeError(f"segment count {len(segments)} exceeds MAX_SEGMENTS={MAX_SEGMENTS}")
    return segments, b"".join(payload_parts), ignored


def build_descriptor(segments: list[tuple[int, int]]) -> bytes:
    desc = bytearray(b"\xFF" * DESC_SIZE)
    struct.pack_into("<I", desc, 0, len(segments))
    for index, (address, size) in enumerate(segments):
        struct.pack_into("<II", desc, 4 + index * 8, address, size)
    return bytes(desc)


def sign_ecdsa(payload: bytes, key_path: Path) -> bytes:
    with key_path.open("rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)
    der = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def verify_ecdsa(payload: bytes, signature: bytes, key_path: Path) -> None:
    if len(signature) != 64:
        raise RuntimeError(f"unexpected signature length: {len(signature)}")
    with key_path.open("rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)
    public_key = private_key.public_key()
    der = utils.encode_dss_signature(
        int.from_bytes(signature[:32], "big"),
        int.from_bytes(signature[32:], "big"),
    )
    try:
        public_key.verify(der, payload, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise RuntimeError("ECDSA verification failed") from exc


def build_header(signature: bytes, file_size: int) -> bytes:
    header = bytearray(b"\xFF" * HEADER_SIZE)
    header[0:len(MAGIC)] = MAGIC
    header[len(MAGIC)] = IMAGE_FLAG_TESTING
    header[8:8 + 32] = b"\x00" * 32
    header[8:8 + len(SIG_TYPE)] = SIG_TYPE
    struct.pack_into("<I", header, 0x28, len(signature))
    header[0x2C:0x2C + len(signature)] = signature
    struct.pack_into("<I", header, 0x6C, file_size)
    return bytes(header)


def main() -> int:
    args = parse_args()

    if not args.mot.is_file():
        raise SystemExit(f"input .mot not found: {args.mot}")
    if not args.prm.is_file():
        raise SystemExit(f"PRM CSV not found: {args.prm}")
    if not args.key.is_file():
        raise SystemExit(f"private key not found: {args.key}")

    regions = load_regions(args.prm)
    segments, payload, ignored = build_sparse_segments(args.mot, regions)
    descriptor = build_descriptor(segments)
    signed_payload = descriptor + payload
    signature = sign_ecdsa(signed_payload, args.key)
    verify_ecdsa(signed_payload, signature, args.key)
    file_size = HEADER_SIZE + len(signed_payload)
    header = build_header(signature, file_size)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(header + signed_payload)

    print("Generated FWUP v2 RSU")
    print(f"  input .mot:     {args.mot}")
    print(f"  input .prm:     {args.prm}")
    print(f"  output .rsu:    {args.output}")
    print(f"  file size:      {file_size:,} bytes")
    print(f"  segment count:  {len(segments)}")
    for index, (address, size) in enumerate(segments, 1):
        print(f"    {index:2d}: addr=0x{address:08X} size=0x{size:X} ({size:,} bytes)")
    if ignored:
        print(f"  ignored bytes:  {ignored:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

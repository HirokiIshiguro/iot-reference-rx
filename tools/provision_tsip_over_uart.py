#!/usr/bin/env python3
"""Provision TSIP runtime blobs through the FreeRTOS CLI."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


ROOT_CA_FILES = {
    "aws": {
        "rootca-sig": "root_ca/TSIP_TLS_ROOT_CA_BUNDLE_SIGNATURE_RSA_PSS_SHA256_C_ARRAY_FILE.txt",
        "rootca-der": "root_ca/TSIP_TLS_ROOT_CA_BUNDLE_DER_C_ARRAY_FILE.txt",
    },
    "lanbenchd": {
        "rootca-sig": "root_ca/TSIP_TLS_ROOT_CA_LANBENCHD_SIGNATURE_RSA_PSS_SHA256_C_ARRAY_FILE.txt",
        "rootca-der": "root_ca/TSIP_TLS_ROOT_CA_LANBENCHD_DER_C_ARRAY_FILE.txt",
    },
}

TARGET_ENV_NAMES = {
    "rx72n": {
        "root-signer": (
            "RENESAS_RX72N_SECURITY_IP_PROVISION_BLOB_TLS_ROOT_SIGNER_RSA2048_PUBLIC_HEX",
            "RX72N_TSIP_ROOT_SIGNER_RSA2048_PUBLIC_HEX",
        ),
        "client-pub": (
            "RENESAS_RX72N_SECURITY_IP_PROVISION_BLOB_TLS_CLIENT_RSA2048_PUBLIC_HEX",
            "RX72N_TSIP_CLIENT_RSA2048_PUBLIC_HEX",
        ),
        "client-pri": (
            "RENESAS_RX72N_SECURITY_IP_PROVISION_BLOB_TLS_CLIENT_RSA2048_PRIVATE_HEX",
            "RX72N_TSIP_CLIENT_RSA2048_PRIVATE_HEX",
        ),
    },
    "rx65n": {
        "root-signer": (
            "RENESAS_RX65N_SECURITY_IP_PROVISION_BLOB_TLS_ROOT_SIGNER_RSA2048_PUBLIC_HEX",
            "RX65N_BG96_TSIP_ROOT_SIGNER_RSA2048_PUBLIC_HEX",
            "RX65N_TSIP_ROOT_SIGNER_RSA2048_PUBLIC_HEX",
        ),
        "client-pub": (
            "RENESAS_RX65N_SECURITY_IP_PROVISION_BLOB_TLS_CLIENT_RSA2048_PUBLIC_HEX",
            "RX65N_BG96_TSIP_CLIENT_RSA2048_PUBLIC_HEX",
            "RX65N_TSIP_CLIENT_RSA2048_PUBLIC_HEX",
        ),
        "client-pri": (
            "RENESAS_RX65N_SECURITY_IP_PROVISION_BLOB_TLS_CLIENT_RSA2048_PRIVATE_HEX",
            "RX65N_BG96_TSIP_CLIENT_RSA2048_PRIVATE_HEX",
            "RX65N_TSIP_CLIENT_RSA2048_PRIVATE_HEX",
        ),
    },
}

SLOTS = ("rootca-sig", "rootca-der", "root-signer", "client-pub", "client-pri")
SENSITIVE_SLOTS = {"root-signer", "client-pub", "client-pri"}
LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{64,}\b")
WRITE_COMMAND_RE = re.compile(r"(tsipprov\s+write\s+\d+\s+)([0-9a-fA-F]+)")


def parse_byte_text(text: str, source: str) -> bytes:
    values = re.findall(r"0x([0-9a-fA-F]{2})(?![0-9a-fA-F])", text)
    if values:
        return bytes(int(value, 16) for value in values)

    compact = re.sub(r"[^0-9a-fA-F]", "", text)
    if not compact or len(compact) % 2 != 0:
        raise ValueError(f"no byte data found in {source}")
    return bytes.fromhex(compact)


def read_file_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(path)
    return parse_byte_text(path.read_text(encoding="utf-8"), str(path))


def read_env_bytes(names: tuple[str, ...]) -> tuple[bytes, str]:
    for name in names:
        value = os.environ.get(name)
        if not value:
            continue
        candidate = Path(value)
        try:
            if candidate.is_file():
                return read_file_bytes(candidate), name
        except OSError:
            pass
        return parse_byte_text(value, name), name
    raise RuntimeError("missing TSIP blob variable; checked " + ", ".join(names))


def sanitize_response(response: str) -> str:
    sanitized = WRITE_COMMAND_RE.sub(r"\1<hex omitted>", response)
    sanitized = LONG_HEX_RE.sub("<hex omitted>", sanitized)
    return sanitized


def read_until_prompt(ser: serial.Serial, timeout: float) -> tuple[str, bool]:
    deadline = time.monotonic() + timeout
    data = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(512)
        if chunk:
            data.extend(chunk)
            if b"\r\n>" in data or b"\n>" in data or data.endswith(b">"):
                time.sleep(0.2)
                tail = ser.read(2048)
                if tail:
                    data.extend(tail)
                return data.decode("utf-8", errors="replace"), True
        time.sleep(0.02)
    return data.decode("utf-8", errors="replace"), False


def write_command(ser: serial.Serial, command: str, inter_byte_delay: float) -> None:
    data = command.encode("ascii") + b"\r\n"
    if inter_byte_delay <= 0.0:
        ser.write(data)
        return

    for byte in data:
        ser.write(bytes((byte,)))
        time.sleep(inter_byte_delay)


def send_command(
    ser: serial.Serial,
    command: str,
    timeout: float,
    inter_byte_delay: float,
    *,
    sensitive: bool = False,
) -> str:
    write_command(ser, command, inter_byte_delay)
    response, ready = read_until_prompt(ser, timeout)
    printable = sanitize_response(response) if sensitive else response
    if not ready:
        raise TimeoutError(f"prompt not observed after command: {sanitize_response(command)}\n{printable}")
    if "Error:" in response:
        raise RuntimeError(f"command failed: {sanitize_response(command)}\n{printable}")
    return printable


def load_payloads(args: argparse.Namespace) -> list[tuple[str, bytes, str]]:
    selected = set(args.only or SLOTS)
    root_ca_files = ROOT_CA_FILES[args.root_ca]
    custom_env_names = {
        "root-signer": tuple(filter(None, (args.root_signer_hex_env,))),
        "client-pub": tuple(filter(None, (args.client_pub_hex_env,))),
        "client-pri": tuple(filter(None, (args.client_pri_hex_env,))),
    }
    payloads: list[tuple[str, bytes, str]] = []

    for slot in SLOTS:
        if slot not in selected:
            continue
        if slot in root_ca_files:
            path = args.data_dir / root_ca_files[slot]
            payloads.append((slot, read_file_bytes(path), str(path)))
            continue

        env_names = custom_env_names[slot] or TARGET_ENV_NAMES[args.target][slot]
        data, source = read_env_bytes(env_names)
        payloads.append((slot, data, source))

    return payloads


def provision_slot(
    ser: serial.Serial,
    slot: str,
    data: bytes,
    chunk_size: int,
    timeout: float,
    inter_byte_delay: float,
    source: str,
) -> None:
    sensitive = slot in SENSITIVE_SLOTS
    print(f"[{slot}] source {source}")
    print(f"[{slot}] begin {len(data)} bytes")
    print(send_command(ser, f"tsipprov begin {slot} {len(data)}", timeout, inter_byte_delay), end="")

    offset = 0
    while offset < len(data):
        chunk = data[offset : offset + chunk_size]
        print(f"[{slot}] write {offset}+{len(chunk)}")
        response = send_command(
            ser,
            f"tsipprov write {offset} {chunk.hex()}",
            timeout,
            inter_byte_delay,
            sensitive=sensitive,
        )
        print(response, end="")
        offset += len(chunk)

    print(f"[{slot}] end")
    print(send_command(ser, "tsipprov end", timeout, inter_byte_delay), end="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--target", choices=sorted(TARGET_ENV_NAMES), default="rx72n")
    parser.add_argument("--data-dir", type=Path, default=Path("external/tsip_provisioning_data/rx72n_ek2"))
    parser.add_argument("--root-ca", choices=sorted(ROOT_CA_FILES), default="aws")
    parser.add_argument("--root-signer-hex-env")
    parser.add_argument("--client-pub-hex-env")
    parser.add_argument("--client-pri-hex-env")
    parser.add_argument("--chunk-size", type=int, default=128)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--settle", type=float, default=2.0)
    parser.add_argument("--enter-cli", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--post-cli-delay", type=float, default=1.0)
    parser.add_argument("--format-first", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--inter-byte-delay", type=float, default=0.002)
    parser.add_argument("--refresh-credentials", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-prepare", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--reset-after", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--only", choices=SLOTS, action="append")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be positive")

    payloads = load_payloads(args)

    with serial.Serial(args.port, args.baud, timeout=0.1, write_timeout=5.0) as ser:
        time.sleep(args.settle)
        pending = ser.read(4096)
        if pending:
            print(sanitize_response(pending.decode("utf-8", errors="replace")), end="")

        if args.enter_cli:
            print("[cli] enter")
            print(send_command(ser, "CLI", args.timeout, args.inter_byte_delay), end="")
            time.sleep(args.post_cli_delay)

        if args.format_first:
            print("[format] littlefs")
            print(send_command(ser, "format", args.timeout, args.inter_byte_delay), end="")

        for slot, data, source in payloads:
            provision_slot(ser, slot, data, args.chunk_size, args.timeout, args.inter_byte_delay, source)

        print(send_command(ser, "tsipprov status", args.timeout, args.inter_byte_delay), end="")
        if args.refresh_credentials:
            print(send_command(ser, "tsipprov credentials", args.timeout, args.inter_byte_delay), end="")
        if not args.skip_prepare:
            print(send_command(ser, "tsipprov prepare", args.timeout, args.inter_byte_delay), end="")
        if args.reset_after:
            print("[reset] CLI reset")
            write_command(ser, "reset", args.inter_byte_delay)
            time.sleep(1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

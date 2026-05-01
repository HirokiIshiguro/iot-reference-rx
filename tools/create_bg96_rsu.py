#!/usr/bin/env python3
"""Create the contiguous RSU image expected by the CK-RX65N BG96 bootloader."""

import argparse
import struct
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


BASE_ADDRESS = 0xFFF00000
IMAGE_SIZE = 24 * 32768
HEADER_SIZE = 0x200
USER_START = 0xFFF00300
USER_END = 0xFFFBFFFF
USER_EXECUTION = 0xFFFBFFFC
HARDWARE_ID = 9
SIG_TYPE = b"sig-sha256-ecdsa"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mot", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sequence", type=int, default=1)
    parser.add_argument("--signature-raw-output", type=Path, default=None)
    parser.add_argument("--signature-der-output", type=Path, default=None)
    parser.add_argument(
        "--format",
        choices=("bootloader-rsu", "rtos-ota-payload"),
        default="bootloader-rsu",
        help=(
            "bootloader-rsu writes the full contiguous image expected by the UART bootloader. "
            "rtos-ota-payload writes descriptor + image data for AWS IoT OTA PAL."
        ),
    )
    return parser.parse_args()


def sign_payload(payload, key_path):
    with key_path.open("rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)
    der_sig = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_sig)
    raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    private_key.public_key().verify(utils.encode_dss_signature(r, s), payload, ec.ECDSA(hashes.SHA256()))
    return der_sig, raw_sig


def iter_srec_records(mot_path):
    with mot_path.open("r", encoding="ascii", errors="strict") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            rec_type = line[:2]
            if rec_type == "S1":
                addr_bytes = 2
            elif rec_type == "S2":
                addr_bytes = 3
            elif rec_type == "S3":
                addr_bytes = 4
            elif rec_type in {"S0", "S4", "S5", "S6", "S7", "S8", "S9"}:
                continue
            else:
                raise RuntimeError(f"unsupported S-record type at line {line_no}: {rec_type}")

            byte_count = int(line[2:4], 16)
            data_len = byte_count - addr_bytes - 1
            addr = int(line[4:4 + addr_bytes * 2], 16)
            data_start = 4 + addr_bytes * 2
            data = bytes.fromhex(line[data_start:data_start + data_len * 2])
            yield addr, data


def main():
    args = parse_args()
    image = bytearray(b"\xff" * IMAGE_SIZE)
    written = 0
    ignored = 0

    for addr, data in iter_srec_records(args.mot):
        for offset, byte in enumerate(data):
            current = addr + offset
            if USER_START <= current <= USER_END:
                image[current - BASE_ADDRESS] = byte
                written += 1
            else:
                ignored += 1

    reset_vector = image[USER_EXECUTION - BASE_ADDRESS:USER_EXECUTION - BASE_ADDRESS + 4]
    if reset_vector == b"\xff\xff\xff\xff":
        raise RuntimeError(
            "user reset vector is blank; BG96 app must place RESETVECT at 0xFFFBFFFC for bootloader launch"
        )

    image[0:7] = b"Renesas"
    image[7] = 0xFE
    image[8:40] = b"\x00" * 32
    image[8:8 + len(SIG_TYPE)] = SIG_TYPE
    struct.pack_into("<I", image, 0x12C, 0)
    struct.pack_into("<I", image, 0x130, 0xFFFFFFFF)
    struct.pack_into("<I", image, 0x134, 0xFFFFFFFF)
    struct.pack_into("<I", image, 0x200, args.sequence)
    struct.pack_into("<I", image, 0x204, USER_START)
    struct.pack_into("<I", image, 0x208, USER_END)
    struct.pack_into("<I", image, 0x20C, USER_EXECUTION)
    struct.pack_into("<I", image, 0x210, HARDWARE_ID)

    payload = bytes(image[HEADER_SIZE:])
    _, raw_sig = sign_payload(payload, args.key)

    struct.pack_into("<I", image, 0x28, len(raw_sig))
    image[0x2C:0x2C + len(raw_sig)] = raw_sig

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "rtos-ota-payload":
        rtos_descriptor = bytearray()
        rtos_descriptor += struct.pack("<I", 1)
        rtos_descriptor += struct.pack("<I", USER_START)
        rtos_descriptor += struct.pack("<I", USER_END - USER_START + 1)
        rtos_descriptor += b"\xff" * 240
        rtos_descriptor += struct.pack("<I", 1)
        output = bytes(rtos_descriptor) + bytes(image[USER_START - BASE_ADDRESS:])
        output_der_sig, output_raw_sig = sign_payload(output, args.key)
    else:
        output = bytes(image)
        output_der_sig, output_raw_sig = sign_payload(payload, args.key)

    if args.signature_raw_output is not None:
        args.signature_raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.signature_raw_output.write_bytes(output_raw_sig)
    if args.signature_der_output is not None:
        args.signature_der_output.parent.mkdir(parents=True, exist_ok=True)
        args.signature_der_output.write_bytes(output_der_sig)

    args.output.write_bytes(output)
    print(f"Generated {args.output}")
    print(f"  format={args.format} size={len(output)} written_bytes={written} ignored_bytes={ignored}")
    if args.signature_raw_output is not None:
        print(f"  signature_raw={args.signature_raw_output} size={len(output_raw_sig)}")
    if args.signature_der_output is not None:
        print(f"  signature_der={args.signature_der_output} size={len(output_der_sig)}")


if __name__ == "__main__":
    main()

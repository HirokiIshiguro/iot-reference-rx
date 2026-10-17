#!/usr/bin/env python3
"""Reset the BG96 app into CLI and provision its OTA certificate/public key."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

import serial

from bg96_bootloader_integration import (
    default_rfp_cli,
    enter_cli_mode,
    run_rfp,
    send_cli_command,
    send_cli_pem,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uart-port", required=True)
    parser.add_argument("--baud", type=int, default=int(os.environ.get("UART_BAUD_RATE", "921600")))
    parser.add_argument("--code-signer-cert", required=True, type=Path)
    parser.add_argument("--rfp-cli", default=default_rfp_cli())
    parser.add_argument("--rfp-device", default=os.environ.get("RFP_DEVICE", "RX65x"))
    parser.add_argument("--rfp-tool", default=os.environ.get("BG96_BOOTLOADER_E2LITE_SERIAL", "OBE110020"))
    parser.add_argument("--rfp-interface", default=os.environ.get("RFP_INTERFACE", "fine"))
    parser.add_argument("--rfp-speed", default=os.environ.get("RFP_SPEED", "1500K"))
    parser.add_argument("--rfp-auth-id", default=os.environ.get("RFP_AUTH_ID", "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"))
    parser.add_argument("--provision-cli-timeout", type=float, default=25.0)
    parser.add_argument("--provision-char-delay", type=float, default=0.002)
    parser.add_argument("--provision-line-delay", type=float, default=0.5)
    return parser.parse_args()


def code_signer_material(path: Path) -> tuple[str, str]:
    """Read one public certificate without consuming any appended private body."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    if path.is_symlink() or not path.is_file():
        raise RuntimeError("code signer certificate must be a regular public PEM file")
    invalid = "code signer input must contain exactly one public certificate PEM"
    with path.open("rb", buffering=0) as stream:
        first = stream.readline(80)
        if first.rstrip(b"\r\n") != b"-----BEGIN CERTIFICATE-----":
            raise RuntimeError(invalid)
        encoded = bytearray(first)
        while True:
            line = stream.readline(4097 - len(encoded))
            if not line or len(encoded) + len(line) > 4096:
                raise RuntimeError(invalid)
            content = line.rstrip(b"\r\n")
            if content != b"-----END CERTIFICATE-----" and not re.fullmatch(b"[A-Za-z0-9+/=]*", content):
                raise RuntimeError(invalid)
            encoded.extend(line)
            if content == b"-----END CERTIFICATE-----":
                break
        while True:
            extra = stream.read(1)
            if not extra:
                break
            if extra not in b" \t\r\n\v\f" or len(encoded) >= 4096:
                raise RuntimeError(invalid)
            encoded.extend(extra)
    try:
        certificate = x509.load_pem_x509_certificate(bytes(encoded).strip())
    except ValueError:
        raise RuntimeError("code signer input is not a valid public certificate") from None
    public = certificate.public_key()
    if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(public.curve, ec.SECP256R1):
        raise RuntimeError("code signer certificate must use ECDSA P-256")
    public_pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return bytes(encoded).strip().decode("ascii"), public_pem.decode("ascii")


def main() -> int:
    args = parse_args()
    certificate, public_key = code_signer_material(args.code_signer_cert)

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
        run_rfp(args, ["-sig", "-run"])
        enter_cli_mode(
            port,
            args.provision_cli_timeout,
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
        )
        send_cli_pem(
            port,
            "codesigncert",
            certificate,
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
        )
        send_cli_pem(
            port,
            "codesignpubkey",
            public_key,
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
        )
        send_cli_command(
            port,
            "conf commit",
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
            timeout=30.0,
            success_tokens=("Configuration save",),
        )
        print("[OTA] Code signer certificate and public key provisioned; device is parked in CLI mode.")
    finally:
        port.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

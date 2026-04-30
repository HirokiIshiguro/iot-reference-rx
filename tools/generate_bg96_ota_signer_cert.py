#!/usr/bin/env python3
"""Generate a PEM code-signing certificate from an OTA signing private key."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--common-name", default="bg96-ota-signer")
    parser.add_argument("--days", type=int, default=3650)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    private_key = serialization.load_pem_private_key(args.key.read_bytes(), password=None)
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, args.common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=args.days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Generated OTA code-signing certificate: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

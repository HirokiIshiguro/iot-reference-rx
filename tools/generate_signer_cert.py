#!/usr/bin/env python3
"""
Generate a PEM certificate from an OTA signing private key.

The OTA image is signed by image-gen.py with a private key, while the device
verifies the signature with a certificate stored in data flash. This helper
keeps those inputs aligned by deriving a self-signed certificate from the same
private key used for image generation.
"""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID


DEFAULT_COMMON_NAME = "iot-reference-rx OTA Signer"
DEFAULT_VALID_DAYS = 3650


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a PEM OTA signer certificate from a private key"
    )
    parser.add_argument(
        "--key",
        required=True,
        help="Path to a PEM private key used by image-gen.py",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for the generated PEM certificate",
    )
    parser.add_argument(
        "--common-name",
        default=DEFAULT_COMMON_NAME,
        help=f"Certificate common name (default: {DEFAULT_COMMON_NAME})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_VALID_DAYS,
        help=f"Certificate validity in days (default: {DEFAULT_VALID_DAYS})",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    key_path = Path(args.key)
    out_path = Path(args.out)

    private_key = serialization.load_pem_private_key(
        key_path.read_bytes(),
        password=None,
    )

    now = datetime.now(timezone.utc)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, args.common_name),
        ]
    )

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=args.days))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
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
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(private_key.public_key()),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    print(f"Generated OTA signer certificate: {out_path}")


if __name__ == "__main__":
    main()

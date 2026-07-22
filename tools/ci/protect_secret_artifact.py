#!/usr/bin/env python3
"""Encrypt or decrypt a CI artifact whose payload contains credentials.

The encryption key is derived from a CI/CD variable named on the command line.
Only the variable name is accepted as an argument so the secret value never
appears in the process command line or in the job log.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


MAGIC = b"SAFFTI-ENC-v1\0"
NONCE_BYTES = 12


def _secret_from_environment(name: str) -> bytes:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"required secret environment variable is empty: {name}")
    # GitLab file-type variables contain a temporary file path rather than the
    # secret itself. Derive the key from the file contents so a predictable
    # runner path can never become the artifact-encryption key.
    candidate = Path(value)
    if candidate.is_file():
        payload = candidate.read_bytes()
        if not payload:
            raise ValueError(f"secret file referenced by environment variable is empty: {name}")
        return payload
    return value.encode("utf-8")


def _derive_key(secret: bytes, context: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=MAGIC,
        info=context.encode("utf-8"),
    ).derive(secret)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def encrypt(input_path: Path, output_path: Path, secret: bytes, context: str) -> str:
    plaintext = input_path.read_bytes()
    nonce = os.urandom(NONCE_BYTES)
    aad = MAGIC + context.encode("utf-8")
    ciphertext = AESGCM(_derive_key(secret, context)).encrypt(nonce, plaintext, aad)
    payload = MAGIC + nonce + ciphertext
    _atomic_write(output_path, payload)
    return hashlib.sha256(payload).hexdigest()


def decrypt(input_path: Path, output_path: Path, secret: bytes, context: str) -> str:
    payload = input_path.read_bytes()
    header_size = len(MAGIC) + NONCE_BYTES
    if len(payload) <= header_size or not payload.startswith(MAGIC):
        raise ValueError("input is not a supported encrypted artifact")

    nonce = payload[len(MAGIC):header_size]
    ciphertext = payload[header_size:]
    aad = MAGIC + context.encode("utf-8")
    try:
        plaintext = AESGCM(_derive_key(secret, context)).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise ValueError("artifact authentication failed") from exc

    _atomic_write(output_path, plaintext)
    return hashlib.sha256(plaintext).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Protect credential-bearing CI artifacts with authenticated encryption."
    )
    parser.add_argument("operation", choices=("encrypt", "decrypt"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--secret-env", required=True)
    parser.add_argument("--context", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        raise ValueError("input and output paths must differ")
    if not input_path.is_file():
        raise FileNotFoundError(f"input artifact does not exist: {input_path}")

    secret = _secret_from_environment(args.secret_env)
    try:
        if args.operation == "encrypt":
            digest = encrypt(input_path, output_path, secret, args.context)
            label = "encrypted"
        else:
            digest = decrypt(input_path, output_path, secret, args.context)
            label = "plaintext"
    finally:
        secret = b""

    print(f"{label} artifact SHA-256: {digest}")
    print(f"{label} artifact written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

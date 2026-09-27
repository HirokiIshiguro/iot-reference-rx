#!/usr/bin/env python3
"""Validate an IDT source copy and inject only a matching disposable TLS key."""
import argparse
import json
import os
from pathlib import Path
import re


def validate_source(value):
    source = Path(value).resolve(strict=True)
    runtime = Path(os.environ["IDT_RUNTIME_DIR"]).resolve(strict=True)
    original = Path(os.environ["IDT_SOURCE_PATH"]).resolve(strict=True)
    if source != original and source.parent not in (runtime, runtime / "source"):
        raise RuntimeError("source must be the declared checkout or a direct IDT runtime source copy")
    if not (source / "Test/include/test_param_config.h").is_file():
        raise RuntimeError("source has no IDT test configuration")
    return source


def macro(lines, name):
    for index, line in enumerate(lines):
        match = re.match(r"^\s*#\s*define\s+" + re.escape(name) + r"\b\s*(.*)", line)
        if match:
            end, text = index + 1, match.group(1).rstrip()
            while text.endswith("\\"):
                if end >= len(lines):
                    raise RuntimeError("unterminated transport macro: " + name)
                text = text[:-1] + lines[end].rstrip()
                end += 1
            parts = re.findall(r'"(?:[^"\\]|\\.)*"', text)
            return index, end, "".join(json.loads(part) for part in parts) if parts else None
    raise RuntimeError("missing transport macro: " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()
    source = validate_source(args.source)
    runtime = Path(os.environ["IDT_RUNTIME_DIR"]).resolve(strict=True)
    # Source checkout is allowed for validation, but credential injection is runtime-only.
    if source.parent not in (runtime, runtime / "source"):
        raise RuntimeError("refusing credential injection into the original checkout")
    key_file = Path(os.environ["IDT_PRIVATE_KEY_FILE"]).resolve(strict=True)
    if runtime not in key_file.parents and key_file.parent != runtime.parent / "inputs":
        raise RuntimeError("disposable private key must be inside this run's private runtime")
    header = source / "Test/include/test_param_config.h"
    lines = header.read_text(encoding="utf-8").splitlines(keepends=True)
    _, _, certificate = macro(lines, "TRANSPORT_CLIENT_CERTIFICATE")
    start, end, private = macro(lines, "TRANSPORT_CLIENT_PRIVATE_KEY")
    if not certificate:
        raise RuntimeError("IDT did not provide a client certificate")
    imported = not bool(private)
    if imported:
        private = key_file.read_text(encoding="ascii")
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    key = serialization.load_pem_private_key(private.encode(), password=None)
    cert = x509.load_pem_x509_certificate(certificate.encode())
    def public_bytes(public_key):
        return public_key.public_bytes(serialization.Encoding.DER,
                                       serialization.PublicFormat.SubjectPublicKeyInfo)
    if public_bytes(key.public_key()) != public_bytes(cert.public_key()):
        raise RuntimeError("TLS client certificate and private key do not match")
    if imported:
        lines[start:end] = ["#define TRANSPORT_CLIENT_PRIVATE_KEY " + json.dumps(private) + "\n"]
    for index, line in enumerate(lines):
        if re.match(r"^\s*#\s*define\s+FORCE_GENERATE_NEW_KEY_PAIR\b", line):
            lines[index] = "#define FORCE_GENERATE_NEW_KEY_PAIR 0\n"
    header.write_text("".join(lines), encoding="utf-8")
    print("Transport certificate/key match verified; credential values omitted; host-import=" + str(imported))


if __name__ == "__main__":
    main()

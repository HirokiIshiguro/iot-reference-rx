#!/usr/bin/env python3
"""IDT Custom signing callback: ECDSA/SHA256 detached DER signature."""
import argparse
import os
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
try:
    from .ota_support import load_signer, private_input
except ImportError:
    from ota_support import load_signer, private_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_image")
    parser.add_argument("output_signature")
    parser.add_argument("--key", required=True)
    parser.add_argument("--certificate", required=True)
    args = parser.parse_args()
    runtime = Path(os.environ["IDT_RUNTIME_DIR"]).resolve(strict=True)
    image = Path(args.input_image).resolve(strict=True)
    signature_path = Path(args.output_signature).resolve()
    if runtime not in image.parents or runtime not in signature_path.parents:
        raise RuntimeError("IDT signing input/output must stay in private runtime")
    key = load_signer(private_input(args.key, runtime), private_input(args.certificate, runtime))
    payload = image.read_bytes()
    signature = key.sign(payload, ec.ECDSA(hashes.SHA256()))
    key.public_key().verify(signature, payload, ec.ECDSA(hashes.SHA256()))
    descriptor = os.open(signature_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(signature)
    print("IDT_OTA_SIGNATURE verified; credential values omitted")


if __name__ == "__main__":
    main()

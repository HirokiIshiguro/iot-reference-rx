"""Public-only PEM and raw ECDSA helpers shared by RX trust controllers.

No hardware entry point and no private key loading. The unbuffered reader rejects
an unexpected PEM header or second object before reading its body.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

PRIVATE_PEM_SCAN_POLICY = "nul_terminated_header_literals_only"


def reject_private_pem_payloads(data):
    """Reject private PEM data while allowing Mbed TLS's header constants.

    Pristine pkparse.c/pkwrite.c compile header-only C strings, optionally
    including a newline. A payload, unterminated marker, or truncated object
    must still fail; never include matched bytes in an error message.
    """
    for match in re.finditer(br"-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----", data):
        if not data.startswith((b"\0", b"\n\0", b"\r\n\0"), match.end()):
            raise RuntimeError("Private PEM payload or unterminated header detected in maintenance artifact")


def public_signer(certificate_path, public_key_path, *, context="RX"):
    """Validate public-only PEM objects and return their matching P-256 key."""
    if context not in {"RX", "RX671"}:
        raise ValueError("Unsupported public signer error context")
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    def public_pem(path, label):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Missing or symbolic link ' + context + ' public signer input')
        with path.open('rb', buffering=0) as stream:
            # FileIO does not prefetch a private body behind the header. Read
            # public lines only through the matching END marker; after that,
            # reject on the first extra non-whitespace byte before its body.
            first = stream.readline(80)
            if first.rstrip(b'\r\n') != b'-----BEGIN ' + label + b'-----':
                raise RuntimeError(context + ' signer input must contain exactly one public PEM object')
            encoded = bytearray(first)
            total = len(first)
            ending = b'-----END ' + label + b'-----'
            while True:
                line = stream.readline(4097 - total)
                total += len(line)
                if total > 4096:
                    raise RuntimeError(context + ' public signer PEM exceeds the provisioner CLI input limit')
                if not line:
                    raise RuntimeError(context + ' signer input must contain exactly one public PEM object')
                content = line.rstrip(b'\r\n')
                if content != ending and not re.fullmatch(b'[A-Za-z0-9+/=]*', content):
                    raise RuntimeError(context + ' signer input must contain exactly one public PEM object')
                encoded.extend(line)
                if content == ending:
                    break
                if total == 4096:
                    raise RuntimeError(context + ' public signer PEM exceeds the provisioner CLI input limit')
            while True:
                extra = stream.read(1)
                if not extra:
                    break
                if extra not in b' \t\r\n\v\f':
                    raise RuntimeError(context + ' signer input must contain exactly one public PEM object')
                total += 1
                if total > 4096:
                    raise RuntimeError(context + ' public signer PEM exceeds the provisioner CLI input limit')
            encoded = bytes(encoded).strip()
            if len(encoded) >= 4096:
                raise RuntimeError(context + ' public signer PEM exceeds the provisioner CLI input limit')
        pattern = (b'-----BEGIN ' + label + b'-----\r?\n[A-Za-z0-9+/=\r\n]+\r?\n-----END '
                   + label + b'-----')
        if not re.fullmatch(pattern, encoded):
            raise RuntimeError(context + ' signer input must contain exactly one public PEM object')
        return encoded
    certificate = x509.load_pem_x509_certificate(public_pem(certificate_path, b'CERTIFICATE'))
    public = serialization.load_pem_public_key(public_pem(public_key_path, b'PUBLIC KEY'))
    if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(public.curve, ec.SECP256R1):
        raise RuntimeError(context + ' initial signer must be ECDSA P-256')
    def der(key):
        return key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if der(public) != der(certificate.public_key()):
        raise RuntimeError(context + ' signer certificate and public key differ')
    return public


def _spki_sha256(public):
    from cryptography.hazmat.primitives import serialization
    return hashlib.sha256(public.public_bytes(serialization.Encoding.DER,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()



def verify_raw_p256(public, signature, payload, *, context="RX"):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    if len(signature) != 64:
        raise RuntimeError(context + " initial RSU requires a raw P-256 signature")
    try:
        public.verify(utils.encode_dss_signature(int.from_bytes(signature[:32], "big"),
                                                 int.from_bytes(signature[32:], "big")),
                      payload, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise RuntimeError(context + " initial RSU does not match the provisioned public signer") from None

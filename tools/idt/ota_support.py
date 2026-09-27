#!/usr/bin/env python3
"""Private-runtime preparation for the RX72N IDT OTA happy-path pilot.

The versioned sample signing key is deliberately used only for development.
No function in this module creates AWS resources or operates the board.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PAYLOAD = "artifacts/idt/build_transport/rx72n_idt_ota_payload.bin"
TRUSTED_CERT = "ota-signer-cert.pem"
SIGNING_KEY = "ota-signer-private.pem"
UNTRUSTED_CERT = "ota-untrusted-cert.pem"
UNTRUSTED_KEY = "ota-untrusted-private.pem"


def _write_private(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def _certificate(key, common_name):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                        key_encipherment=False, data_encipherment=False,
                                        key_agreement=False, key_cert_sign=False, crl_sign=False,
                                        encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CODE_SIGNING]), critical=False)
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM)


def make_ota_config(inputs, source, path_converter, python_executable="python3"):
    """Windows-callable helper: write private inputs and return otaConfiguration.

    path_converter maps a host Path to the IDT Linux host path. The caller must
    restrict access to inputs, retain these files only in private runtime, and
    pass ota_environment() to the IDT process. Only GreaterVersion is enabled by
    the caller: this helper does not claim full OTA or qualification coverage.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    inputs, source = Path(inputs).resolve(), Path(source).resolve(strict=True)
    if inputs == source or source in inputs.parents:
        raise ValueError("OTA credential inputs must be outside the source repository")
    inputs.mkdir(parents=True, exist_ok=True)
    # Match the existing RX72N development bootloader/signing path.
    key_bytes = (source / "sample_keys/secp256r1.privatekey").read_bytes()
    key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("RX72N OTA pilot requires an EC P-256 signing key")
    # Refuse a signing key that the freshly flashed development bootloader rejects.
    try:
        from .prepare_transport_key import macro
    except ImportError:
        from prepare_transport_key import macro
    public_header = source / "Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/src/key/code_signer_public_key.h"
    _, _, public_pem = macro(public_header.read_text(encoding="utf-8").splitlines(keepends=True),
                             "CODE_SIGNER_PUBLIC_KEY_PEM")
    if not public_pem:
        raise ValueError("bootloader signing public key is missing")
    public_body = public_pem.split("-----BEGIN PUBLIC KEY-----", 1)[1].split("-----END PUBLIC KEY-----", 1)[0]
    boot_key = serialization.load_der_public_key(base64.b64decode(re.sub(r"\s+", "", public_body), validate=True))
    if key.public_key().public_numbers() != boot_key.public_numbers():
        raise ValueError("OTA signing key does not match the development bootloader public key")
    _write_private(inputs / SIGNING_KEY, key_bytes)
    _write_private(inputs / TRUSTED_CERT, _certificate(key, "RX72N IDT development signer"))
    untrusted = ec.generate_private_key(ec.SECP256R1())
    _write_private(inputs / UNTRUSTED_KEY, untrusted.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    _write_private(inputs / UNTRUSTED_CERT, _certificate(untrusted, "RX72N IDT untrusted signer"))
    command = [str(python_executable), str(path_converter(source / "tools/idt/ota_sign.py")),
               "{{inputImageFilePath}}", "{{outputSignatureFilePath}}",
               "--key", str(path_converter(inputs / SIGNING_KEY)),
               "--certificate", str(path_converter(inputs / TRUSTED_CERT))]
    if any(any(character.isspace() for character in part) for part in command):
        raise ValueError("FRQ custom signing callback paths must not contain whitespace")
    return {"otaE2EFirmwarePath": "{{testData.sourcePath}}/" + PAYLOAD,
            "otaPALCertificatePath": TRUSTED_CERT,
            "deviceFirmwarePath": "NA",
            "codeSigningConfiguration": {
                "signingMethod": "Custom", "signerHashingAlgorithm": "SHA256",
                "signerSigningAlgorithm": "ECDSA",
                "signerCertificate": str(path_converter(inputs / TRUSTED_CERT)),
                "untrustedSignerCertificate": str(path_converter(inputs / UNTRUSTED_CERT)),
                "signerCertificateFileName": TRUSTED_CERT,
                "compileSignerCertificate": False,
                "signCommand": " ".join(command)}}


def ota_environment(inputs, path_converter):
    inputs = Path(inputs).resolve(strict=True)
    return {"IDT_OTA_SIGNING_KEY_FILE": str(path_converter(inputs / SIGNING_KEY)),
            "IDT_OTA_SIGNER_CERT_FILE": str(path_converter(inputs / TRUSTED_CERT))}


def runtime_source(value):
    try:
        from .prepare_transport_key import validate_source
    except ImportError:
        from prepare_transport_key import validate_source
    source = validate_source(value)
    runtime = Path(os.environ["IDT_RUNTIME_DIR"]).resolve(strict=True)
    if source.parent not in (runtime, runtime / "source"):
        raise RuntimeError("OTA injected source and firmware must remain in private runtime")
    return source, runtime


def private_input(value, runtime):
    path = Path(value).resolve(strict=True)
    if runtime not in path.parents and path.parent != runtime.parent / "inputs":
        raise RuntimeError("OTA signing inputs must belong to this private runtime")
    return path


def load_signer(key_path, certificate_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    cert = x509.load_pem_x509_certificate(Path(certificate_path).read_bytes())
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise RuntimeError("OTA signing requires ECDSA P-256")
    def der(public):
        return public.public_bytes(serialization.Encoding.DER,
                                   serialization.PublicFormat.SubjectPublicKeyInfo)
    if der(key.public_key()) != der(cert.public_key()):
        raise RuntimeError("OTA signer certificate and private key differ")
    return key


def ota_version(source):
    text = (source / "Test/include/test_param_config.h").read_text(encoding="utf-8")
    values = []
    for name, maximum in (("MAJOR", 255), ("MINOR", 255), ("BUILD", 65535)):
        matches = re.findall(r"^\s*#\s*define\s+OTA_APP_VERSION_" + name +
                             r"\s+\(?\s*(\d+)[uUlL]*\s*\)?\s*$", text, re.MULTILINE)
        if len(matches) != 1 or not 0 <= int(matches[0]) <= maximum:
            raise RuntimeError("invalid IDT OTA version macro: " + name)
        values.append(int(matches[0]))
    return ".".join(map(str, values))


def prepare_source(value):
    source, runtime = runtime_source(value)
    execution = (source / "Test/include/test_execution_config.h").read_text(encoding="utf-8")
    if not re.search(r"^\s*#\s*define\s+OTA_E2E_TEST_ENABLED\s+\(?\s*1\s*\)?\s*$",
                     execution, re.MULTILINE):
        raise RuntimeError("IDT did not select OTA_E2E_TEST_ENABLED=1")
    key = private_input(os.environ["IDT_OTA_SIGNING_KEY_FILE"], runtime)
    cert = private_input(os.environ["IDT_OTA_SIGNER_CERT_FILE"], runtime)
    load_signer(key, cert)
    header = ("/* Generated inside private IDT runtime; do not publish. */\n"
              "#ifndef IDT_OTA_SIGNER_H\n#define IDT_OTA_SIGNER_H\n"
              "#define IDT_OTA_SIGNER_CERTIFICATE " + json.dumps(cert.read_text(encoding="ascii")) +
              "\n#endif\n")
    (source / "Test/include/idt_ota_signer.h").write_text(header, encoding="utf-8")
    print("IDT OTA signer prepared; version=" + ota_version(source) + "; credential values omitted")


def build_payload(value):
    source, runtime = runtime_source(value)
    key = private_input(os.environ["IDT_OTA_SIGNING_KEY_FILE"], runtime)
    cert = private_input(os.environ["IDT_OTA_SIGNER_CERT_FILE"], runtime)
    load_signer(key, cert)
    output = source / "artifacts/idt/build_transport"
    mot = output / "rx72n_idt_transport.mot"
    payload = source / PAYLOAD
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = json.loads((output / "build_manifest.json").read_text(encoding="utf-8-sig"))
    if sha(mot) != manifest.get("outputs", {}).get("mot", {}).get("sha256"):
        raise RuntimeError("OTA MOT differs from the completed build manifest")
    parameters_sha = sha(source / "Test/include/test_param_config.h")
    if parameters_sha != manifest.get("parameter_config_sha256"):
        raise RuntimeError("OTA parameters changed after firmware compilation")
    version = ota_version(source)
    expected_version = dict(zip(("MAJOR", "MINOR", "BUILD"), map(int, version.split("."))))
    if manifest.get("application_version") != expected_version:
        raise RuntimeError("compiled application version differs from the IDT OTA version")
    subprocess.run([sys.executable, str(source / "tools/build_fwup_v2_rsu.py"),
                    "--mot", str(mot), "--prm", str(source / "tools/fwup/rx72n_envision_kit_dual_bank.prm.csv"),
                    "--key", str(key), "--output", str(payload), "--format", "rtos-ota-payload"], check=True)
    entry = {"schema_version": 1, "built_utc": datetime.now(timezone.utc).isoformat(),
             "ota_version": version, "source_runtime_path": str(source.relative_to(runtime)),
             "mot_sha256": sha(mot), "payload_sha256": sha(payload), "payload_bytes": payload.stat().st_size,
             "parameter_config_sha256": parameters_sha}
    for field in ("source_sha", "test_library_sha", "source_tree_dirty"):
        if field in manifest:
            entry[field] = manifest[field]
    # Keep every callback's evidence even when IDT reuses one source tree.
    import fcntl
    descriptor = os.open(runtime / "ota-build-ledger.jsonl", os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(entry, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print("IDT_OTA_BUILD " + json.dumps(entry, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "payload"))
    parser.add_argument("source")
    args = parser.parse_args()
    {"prepare": prepare_source, "payload": build_payload}[args.action](args.source)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Private-runtime preparation and packaging for the selected IDT target.

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
import secrets
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

try:
    from .targets import DEFAULT_TARGET, get_target, target_fingerprint
except ImportError:
    from targets import DEFAULT_TARGET, get_target, target_fingerprint

PAYLOAD = "artifacts/idt/build_transport/rx72n_idt_ota_payload.bin"
TRUSTED_CERT = "ota-signer-cert.pem"
SIGNING_KEY = "ota-signer-private.pem"
UNTRUSTED_CERT = "ota-untrusted-cert.pem"
UNTRUSTED_KEY = "ota-untrusted-private.pem"


def selected_target(value=None):
    if isinstance(value, dict):
        target = get_target(value.get("id"))
        if value != target:
            raise ValueError("IDT target differs from the reviewed target manifest")
        return target
    return get_target(value)


def validate_target_manifest(manifest, target, *, allow_legacy=False):
    identity, fingerprint = manifest.get("target_id"), manifest.get("target_sha256")
    if identity is None and fingerprint is None and allow_legacy and target["id"] == DEFAULT_TARGET:
        return
    if identity != target["id"] or fingerprint != target_fingerprint(target):
        raise RuntimeError("build manifest belongs to a different IDT target or target configuration")


def verify_bootloader_signer(source, target, key, *, runtime=None, source_sha=None, environ=None):
    """Validate the public key actually selected by a development bootloader."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    if target["id"] == "rx671-wifi":
        # Local public materials bind the intended signer, not existing Data
        # Flash contents. The guarded flash callback must still run the real
        # linear provisioner and verify this signer's actual initial RSU.
        if runtime is None or source_sha is None:
            raise ValueError("RX671 OTA requires verified LittleFS code_signer_public_key provisioning inputs "
                             "and their exact source SHA before building")
        try:
            from .rx671_provision import validate_prepared_signer
        except ImportError:
            from rx671_provision import validate_prepared_signer
        prepared = validate_prepared_signer(source, runtime, target, source_sha, environ)
        public = key.public_key().public_bytes(serialization.Encoding.DER,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
        if hashlib.sha256(public).hexdigest() != prepared["public_signer_spki_sha256"]:
            raise ValueError("OTA signing key does not match the prepared RX671 public signer")
        return Path(prepared["signer_certificate"]).read_bytes()
    try:
        from .prepare_transport_key import macro
    except ImportError:
        from prepare_transport_key import macro
    public_header = Path(source) / target["bootloader_project"] / "src/key/code_signer_public_key.h"
    _, _, public_pem = macro(public_header.read_text(encoding="utf-8").splitlines(keepends=True),
                             "CODE_SIGNER_PUBLIC_KEY_PEM")
    if not public_pem:
        raise ValueError("bootloader signing public key is missing")
    public_body = public_pem.split("-----BEGIN PUBLIC KEY-----", 1)[1].split("-----END PUBLIC KEY-----", 1)[0]
    boot_key = serialization.load_der_public_key(base64.b64decode(re.sub(r"\s+", "", public_body), validate=True))
    if (not isinstance(boot_key, ec.EllipticCurvePublicKey)
            or not isinstance(boot_key.curve, ec.SECP256R1)
            or key.public_key().public_numbers() != boot_key.public_numbers()):
        raise ValueError("OTA signing key does not match the development bootloader public key")


def payload_relative_path(target):
    # Existing RX72N callbacks and retained IDT source copies use this name.
    # Keep that contract while deriving other targets' paths consistently for
    # both otaConfiguration and the payload build callback.
    if target["id"] == DEFAULT_TARGET:
        return PAYLOAD
    return "artifacts/idt/build_transport/" + target["artifact_basename"] + "_ota_payload.bin"


def source_stack_metadata(source, target=None):
    """Read the selected project's MQTT sources without consulting Git or secrets.

    These are source and pinned-suite compatibility observations, never native
    IDT results. A matching MQTT wire protocol does not establish qualification.
    """
    target = selected_target(target)
    source = Path(source).resolve(strict=True)
    project = source / target["application_project"]
    descriptor = ET.parse(project / ".project").getroot()
    links = [node.findtext("locationURI") for node in descriptor.findall("./linkedResources/link")
             if node.findtext("name") == "Middleware"]
    if links:
        roots = [node.findtext("value") for node in descriptor.findall("./variableList/variable")
                 if node.findtext("name") == "AWS_IOT_MCU_ROOT"]
        if (links != ["AWS_IOT_MCU_ROOT/Middleware"]
                or roots != ["$%7BPARENT-3-PROJECT_LOC%7D"]):
            raise RuntimeError("selected project has an unreviewed Middleware source mapping")
        middleware = source / "Middleware"
    else:
        middleware = project / "Middleware"
    mqtt_source = middleware / "FreeRTOS/coreMQTT/source"
    header = mqtt_source / "include/core_mqtt.h"
    version_matches = re.findall(r'^\s*#\s*define\s+MQTT_LIBRARY_VERSION\s+"([^"\r\n]+)"\s*$',
                                 header.read_text(encoding="utf-8"), re.MULTILINE)
    if len(version_matches) != 1:
        raise RuntimeError("selected coreMQTT source has no unique library version")
    # The production CONNECT serializer supplies the protocol level. Reading
    # this source avoids assigning BG96 the root manifest's shared MQTT v5.
    serializer = mqtt_source / "core_mqtt_serializer.c"
    serializer_text = serializer.read_text(encoding="utf-8")
    protocol, level = "3.1.1", 4
    macro = "MQTT_VERSION_3_1_1"
    constant = r'^\s*#\s*define\s+' + macro + r'\s+\(\s*\(\s*uint8_t\s*\)\s*4U\s*\)\s*$'
    if not re.search(constant, serializer_text, re.MULTILINE):
        serializer = mqtt_source / "core_mqtt_serializer_private.c"
        serializer_text = serializer.read_text(encoding="utf-8")
        protocol, level, macro = "5.0", 5, "MQTT_VERSION_5"
        constant = r'^\s*#\s*define\s+' + macro + r'\s+\(\s*5U\s*\)\s*$'
    if (len(re.findall(constant, serializer_text, re.MULTILINE)) != 1
            or len(re.findall(r'\*pIndexLocal\s*=\s*' + macro + r'\s*;', serializer_text)) != 1):
        raise RuntimeError("selected coreMQTT CONNECT serializer has an unreviewed protocol level")
    manifest = source / "manifest.yml"
    manifest_versions = re.findall(r'^version:\s*["\']?([^"\'\s]+)',
                                   manifest.read_text(encoding="utf-8"), re.MULTILINE)
    if len(manifest_versions) != 1:
        raise RuntimeError("source manifest has no unique FreeRTOS version")
    bundle = json.loads((source / "tools/idt/bundle-manifest.json").read_text(encoding="utf-8"))
    pinned_suite = (bundle["idt_version"], bundle["suite"]) == ("4.9.0", "FRQ_2.5.0")
    expected_protocol = "3.1.1" if pinned_suite else None
    version_status = "unsupported" if pinned_suite and manifest_versions[0] == "202604.00-LTS" else "not-assessed"
    def evidence(path):
        return {"path": path.relative_to(source).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"source_manifest_version": manifest_versions[0], "source_manifest": evidence(manifest),
            "core_mqtt": {"version": version_matches[0], "protocol": protocol, "wire_level": level,
                          "header": evidence(header), "connect_serializer": evidence(serializer)},
            "idt": {"version": bundle["idt_version"], "suite": bundle["suite"],
                    "freertos_version_check": {"status": version_status, "native_result": "not-run"},
                    "mqtt_protocol_check": {
                        "expected_protocol": expected_protocol,
                        "status": "not-assessed" if expected_protocol is None else
                                  "protocol-match-only" if protocol == expected_protocol else "protocol-mismatch",
                        "native_result": "not-run"}},
            "qualification": "not-established"}


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


def make_ota_config(inputs, source, path_converter, python_executable="python3", target=None,
                    *, bootstrap_environment=None, source_sha=None):
    """Windows-callable helper: write private inputs and return otaConfiguration.

    path_converter maps a host Path to the IDT Linux host path. The caller must
    restrict access to inputs, retain these files only in private runtime, and
    pass ota_environment() to the IDT process. Only GreaterVersion is enabled by
    the caller: this helper does not claim full OTA or qualification coverage.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    target = selected_target(target)
    inputs, source = Path(inputs).resolve(), Path(source).resolve(strict=True)
    if inputs == source or source in inputs.parents:
        raise ValueError("OTA credential inputs must be outside the source repository")
    inputs.mkdir(parents=True, exist_ok=True)
    key_bytes = (source / target["signing_key"]).read_bytes()
    key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("IDT OTA requires an EC P-256 signing key")
    prepared_certificate = verify_bootloader_signer(source, target, key, runtime=inputs.parent,
                                                   source_sha=source_sha, environ=bootstrap_environment)
    _write_private(inputs / SIGNING_KEY, key_bytes)
    _write_private(inputs / TRUSTED_CERT, prepared_certificate if prepared_certificate is not None else
                   _certificate(key, target["id"] + " IDT development signer"))
    untrusted = ec.generate_private_key(ec.SECP256R1())
    _write_private(inputs / UNTRUSTED_KEY, untrusted.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    _write_private(inputs / UNTRUSTED_CERT, _certificate(untrusted, target["id"] + " IDT untrusted signer"))
    command = [str(python_executable), str(path_converter(source / "tools/idt/ota_sign.py")),
               "{{inputImageFilePath}}", "{{outputSignatureFilePath}}",
               "--key", str(path_converter(inputs / SIGNING_KEY)),
               "--certificate", str(path_converter(inputs / TRUSTED_CERT))]
    if any(any(character.isspace() for character in part) for part in command):
        raise ValueError("FRQ custom signing callback paths must not contain whitespace")
    return {"otaE2EFirmwarePath": "{{testData.sourcePath}}/" + payload_relative_path(target),
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


def prepare_source(value, target=None):
    target = selected_target(target)
    source, runtime = runtime_source(value)
    execution = (source / "Test/include/test_execution_config.h").read_text(encoding="utf-8")
    if not re.search(r"^\s*#\s*define\s+OTA_E2E_TEST_ENABLED\s+\(?\s*1\s*\)?\s*$",
                     execution, re.MULTILINE):
        raise RuntimeError("IDT did not select OTA_E2E_TEST_ENABLED=1")
    key = private_input(os.environ["IDT_OTA_SIGNING_KEY_FILE"], runtime)
    cert = private_input(os.environ["IDT_OTA_SIGNER_CERT_FILE"], runtime)
    signer = load_signer(key, cert)
    if target["id"] != DEFAULT_TARGET:
        verify_bootloader_signer(source, target, signer, runtime=runtime,
                                 source_sha=os.environ.get("IDT_SOURCE_SHA"), environ=os.environ)
    header = ("/* Generated inside private IDT runtime; do not publish. */\n"
              "#ifndef IDT_OTA_SIGNER_H\n#define IDT_OTA_SIGNER_H\n"
              "#define IDT_OTA_IMAGE_ID " + json.dumps(secrets.token_hex(16)) + "\n"
              "#define IDT_OTA_SIGNER_CERTIFICATE " + json.dumps(cert.read_text(encoding="ascii")) +
              "\n#endif\n")
    (source / "Test/include/idt_ota_signer.h").write_text(header, encoding="utf-8")
    print("IDT OTA signer prepared; version=" + ota_version(source) + "; credential values omitted")


def packaging_manifest(source, target, *, allow_legacy=False):
    output = source / "artifacts/idt/build_transport"
    manifest = json.loads((output / "build_manifest.json").read_text(encoding="utf-8-sig"))
    validate_target_manifest(manifest, target, allow_legacy=allow_legacy)
    mot = output / (target["artifact_basename"] + ".mot")
    if hashlib.sha256(mot.read_bytes()).hexdigest() != manifest.get("outputs", {}).get("mot", {}).get("sha256"):
        raise RuntimeError("OTA MOT differs from the completed build manifest")
    return output, manifest, mot


def validate_packaging(value, target=None):
    target = selected_target(target)
    source, _ = runtime_source(value)
    output, manifest, _ = packaging_manifest(source, target)
    bootloader = output / "bootloader.mot"
    if hashlib.sha256(bootloader.read_bytes()).hexdigest() != manifest.get("outputs", {}).get("bootloader", {}).get("sha256"):
        raise RuntimeError("bootloader MOT differs from the completed build manifest")


def record_packaging(value, target=None):
    """Bind every UART/programmer input to the selected target's build."""
    target = selected_target(target)
    validate_packaging(value, target)
    source, _ = runtime_source(value)
    output, manifest, _ = packaging_manifest(source, target)
    rsu = output / (target["artifact_basename"] + ".rsu")
    artifacts = (("rsu", rsu), ("bootloader_bank1", output / "bootloader_bank1.mot"))
    for kind, path in artifacts:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("packaged firmware artifact is missing or a symlink: " + kind)
    if target["id"] == "rx65n-bg96":
        # The BG96 UART downloader sends this pad separately in production.
        # The generic IDT downloader streams one file, so retain the same exact
        # bytes in its UART artifact; OTA payloads never include this trailer.
        image = rsu.read_bytes()
        if len(image) == 0xC0000:
            rsu.write_bytes(image + b"\xff" * 32768)
        elif len(image) != 0xC8000 or image[-32768:] != b"\xff" * 32768:
            raise RuntimeError("BG96 UART RSU has an unexpected image or const-data trailer")
    for kind, path in artifacts:
        manifest.setdefault("outputs", {})[kind] = {
            "path": path.relative_to(source).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    manifest["uart_trailer_bytes"] = 32768 if target["id"] == "rx65n-bg96" else 0
    (output / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def rx671_transfer_payload(rsu, key):
    """Verify and extract the production RX671 OTA descriptor plus image.

    Matches tools/build_rx671_ota_images.py:_create_ota_transfer_artifacts:
    the RSU's raw P-256 signature covers bytes following the 0x200 header.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    if (len(rsu) != 0xC0000 or rsu[:7] != b"Renesas"
            or rsu[8:40].rstrip(b"\0") != b"sig-sha256-ecdsa"
            or struct.unpack_from("<I", rsu, 0x28)[0] != 64):
        raise RuntimeError("RX671 RSU has an invalid image header or size")
    if struct.unpack_from("<III", rsu, 0x12C) != (0, 0xFFFFFFFF, 0xFFFFFFFF):
        raise RuntimeError("RX671 OTA RSU must preserve application-owned Data Flash")
    payload = rsu[0x200:]
    if struct.unpack_from("<III", payload) != (1, 0xFFF00300, 0xBFD00):
        raise RuntimeError("RX671 OTA RSU has an unexpected application descriptor")
    raw_signature = rsu[0x2C:0x6C]
    der_signature = utils.encode_dss_signature(int.from_bytes(raw_signature[:32], "big"),
                                               int.from_bytes(raw_signature[32:], "big"))
    key.public_key().verify(der_signature, payload, ec.ECDSA(hashes.SHA256()))
    return payload


def build_payload(value, target=None):
    target = selected_target(target)
    source, runtime = runtime_source(value)
    key = private_input(os.environ["IDT_OTA_SIGNING_KEY_FILE"], runtime)
    cert = private_input(os.environ["IDT_OTA_SIGNER_CERT_FILE"], runtime)
    signer = load_signer(key, cert)
    output, manifest, mot = packaging_manifest(source, target, allow_legacy=True)
    payload = source / payload_relative_path(target)
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    parameters_sha = sha(source / "Test/include/test_param_config.h")
    if parameters_sha != manifest.get("parameter_config_sha256"):
        raise RuntimeError("OTA parameters changed after firmware compilation")
    version = ota_version(source)
    expected_version = dict(zip(("MAJOR", "MINOR", "BUILD"), map(int, version.split("."))))
    if manifest.get("application_version") != expected_version:
        raise RuntimeError("compiled application version differs from the IDT OTA version")
    signer_header = source / "Test/include/idt_ota_signer.h"
    if sha(signer_header) != manifest.get("signer_header_sha256"):
        raise RuntimeError("OTA signer/image identity header changed after firmware compilation")
    identifiers = re.findall(r'^#define IDT_OTA_IMAGE_ID "([a-f0-9]{32})"$',
                             signer_header.read_text(encoding="utf-8"), re.MULTILINE)
    if len(identifiers) != 1 or identifiers[0] != manifest.get("image_id"):
        raise RuntimeError("OTA image identity differs from the completed build manifest")
    command = [sys.executable, str(source / target["packager"]), "--mot", str(mot), "--key", str(key)]
    if target["prm"]:
        command += ["--prm", str(source / target["prm"])]
    if target["id"] == "rx671-wifi":
        signed_rsu = output / (target["artifact_basename"] + "_ota_signed.rsu")
        subprocess.run(command + ["--output", str(signed_rsu)], check=True)
        payload.write_bytes(rx671_transfer_payload(signed_rsu.read_bytes(), signer))
    else:
        subprocess.run(command + ["--output", str(payload), "--format", "rtos-ota-payload"], check=True)
    entry = {"schema_version": 1, "built_utc": datetime.now(timezone.utc).isoformat(),
             "ota_version": version, "image_id": identifiers[0],
             "signer_header_sha256": manifest["signer_header_sha256"],
             "source_runtime_path": str(source.relative_to(runtime)),
             "mot_sha256": sha(mot), "payload_sha256": sha(payload), "payload_bytes": payload.stat().st_size,
             "parameter_config_sha256": parameters_sha,
             "target_id": target["id"], "target_sha256": target_fingerprint(target)}
    for field in ("source_sha", "test_library_sha", "source_tree_dirty", "production_stack"):
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
    parser.add_argument("action", choices=("prepare", "payload", "validate-packaging", "record-packaging", "stack-metadata"))
    parser.add_argument("source")
    parser.add_argument("--target")
    args = parser.parse_args()
    if args.action == "stack-metadata":
        print(json.dumps(source_stack_metadata(args.source, args.target), sort_keys=True))
        return
    {"prepare": prepare_source, "payload": build_payload, "validate-packaging": validate_packaging,
     "record-packaging": record_packaging}[args.action](args.source, target=args.target)


if __name__ == "__main__":
    main()

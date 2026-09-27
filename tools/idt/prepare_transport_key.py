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


def certificate_public_key(certificate):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    return x509.load_pem_x509_certificate(certificate.encode()).public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def matching_iot_certificate(client, account, region, thing_name, public_key):
    """Read only the IDT-created thing and require exactly one active matching key."""
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", thing_name or ""):
        raise RuntimeError("IDT did not provide a valid thing name")
    principals, token, seen_tokens = set(), None, set()
    while True:
        args = {"thingName": thing_name}
        if token:
            args["nextToken"] = token
        page = client.list_thing_principals(**args)
        principals.update(page.get("principals", []))
        token = page.get("nextToken")
        if not token:
            break
        if token in seen_tokens:
            raise RuntimeError("IoT principal pagination did not advance")
        seen_tokens.add(token)
    matches = []
    for principal in sorted(principals):
        parts = principal.split(":", 5)
        if (len(parts) != 6 or parts[0] != "arn" or parts[2] != "iot"
                or parts[3] != region or parts[4] != account
                or not re.fullmatch(r"cert/[a-fA-F0-9]{64}", parts[5])):
            raise RuntimeError("IDT thing has an unexpected certificate principal")
        result = client.describe_certificate(certificateId=parts[5][5:])["certificateDescription"]
        if result.get("certificateArn") != principal:
            raise RuntimeError("IoT returned a different certificate identity")
        if result.get("status") == "ACTIVE":
            certificate = result["certificatePem"]
            if certificate_public_key(certificate) == public_key:
                matches.append(certificate)
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one active IDT thing certificate matching the disposable key")
    return matches[0]


def fetch_iot_certificate(thing_name, public_key):
    import boto3
    from botocore.config import Config
    region = os.environ["AWS_REGION"]
    config = Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2})
    session = boto3.Session(region_name=region)
    account = session.client("sts", config=config).get_caller_identity()["Account"]
    return matching_iot_certificate(session.client("iot", config=config), account, region,
                                    thing_name, public_key)


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
    prefix = "TRANSPORT" if os.environ.get("IDT_SCOPE", "transport") == "transport" else "MQTT"
    _, _, certificate = macro(lines, prefix + "_CLIENT_CERTIFICATE")
    _, _, private = macro(lines, prefix + "_CLIENT_PRIVATE_KEY")
    imported = private in (None, "", "PLACE_HOLDER")
    if imported:
        private = key_file.read_text(encoding="ascii")
    from cryptography.hazmat.primitives import serialization
    key = serialization.load_pem_private_key(private.encode(), password=None)
    public_key = key.public_key().public_bytes(serialization.Encoding.DER,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)
    if not certificate or certificate == "PLACE_HOLDER":
        if prefix != "MQTT":
            raise RuntimeError("IDT did not provide a client certificate")
        # FRQ 2.5 registers the supplied public key with IoT Core but only
        # injects the endpoint and thing name for CloudIoT/OTA demo builds.
        # Fetch that exact thing's certificate; do not create or substitute one.
        _, _, thing_name = macro(lines, "IOT_THING_NAME")
        certificate = fetch_iot_certificate(thing_name, public_key)
        start, end, _ = macro(lines, prefix + "_CLIENT_CERTIFICATE")
        lines[start:end] = ["#define " + prefix + "_CLIENT_CERTIFICATE " + json.dumps(certificate) + "\n"]
    if public_key != certificate_public_key(certificate):
        raise RuntimeError("TLS client certificate and private key do not match")
    if imported:
        start, end, _ = macro(lines, prefix + "_CLIENT_PRIVATE_KEY")
        lines[start:end] = ["#define " + prefix + "_CLIENT_PRIVATE_KEY " + json.dumps(private) + "\n"]
    for index, line in enumerate(lines):
        if re.match(r"^\s*#\s*define\s+FORCE_GENERATE_NEW_KEY_PAIR\b", line):
            lines[index] = "#define FORCE_GENERATE_NEW_KEY_PAIR 0\n"
    header.write_text("".join(lines), encoding="utf-8")
    print(prefix + " certificate/key match verified; credential values omitted; host-import=" + str(imported))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate transient MQTT credential headers for the CK-RX65N BG96 build."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


ENDPOINT_VARS = (
    "RX65N_BG96_AWS_IOT_ENDPOINT_OVERRIDE",
    "AWS_IOT_MQTT_BROKER_ENDPOINT_CK_RX65N_01",
    "BG96_AWS_IOT_ENDPOINT",
    "BG96_AWS_IOT_MQTT_BROKER_ENDPOINT",
    "BG96_MQTT_ENDPOINT",
    "BG96_MQTT_BROKER_ENDPOINT",
    "AWS_IOT_ENDPOINT",
    "AWS_IOT_MQTT_BROKER_ENDPOINT",
)
THING_NAME_VARS = (
    "AWS_IOT_THING_NAME_CK_RX65N_01",
    "RX65N_BG96_AWS_IOT_THING_NAME",
    "BG96_AWS_IOT_THING_NAME",
    "BG96_MQTT_THING_NAME",
    "AWS_IOT_THING_NAME",
)
CLIENT_CERT_VARS = (
    "AWS_IOT_DEVICE_CERT_PEM_FILE_CK_RX65N_01",
    "AWS_IOT_DEVICE_CERT_PEM_CK_RX65N_01",
    "AWS_IOT_CLIENT_CERT_PEM_CK_RX65N_01",
    "AWS_IOT_CLIENT_CERTIFICATE_PEM_CK_RX65N_01",
    "BG96_AWS_IOT_CLIENT_CERT_PEM",
    "BG96_AWS_IOT_DEVICE_CERT_PEM_FILE",
    "BG96_AWS_IOT_DEVICE_CERT_PEM",
    "BG96_AWS_IOT_CLIENT_CERTIFICATE_PEM",
    "BG96_AWS_IOT_CLIENT_CERTIFICATE_PEM_FILE",
    "BG96_AWS_IOT_CLIENT_CERT",
    "BG96_AWS_IOT_CLIENT_CERTIFICATE",
    "BG96_MQTT_CLIENT_CERT_PEM",
    "BG96_MQTT_DEVICE_CERT_PEM_FILE",
    "BG96_MQTT_DEVICE_CERT_PEM",
    "BG96_MQTT_CLIENT_CERTIFICATE_PEM",
    "BG96_MQTT_CLIENT_CERT",
    "BG96_MQTT_CLIENT_CERTIFICATE",
    "AWS_IOT_CLIENT_CERT_PEM",
    "AWS_IOT_DEVICE_CERT_PEM_FILE",
    "AWS_IOT_DEVICE_CERT_PEM",
    "AWS_IOT_CLIENT_CERTIFICATE_PEM",
    "AWS_IOT_CLIENT_CERT",
    "AWS_IOT_CLIENT_CERTIFICATE",
    "AWS_CLIENT_CERTIFICATE_PEM",
    "CLIENT_CERTIFICATE_PEM",
    "AWS_IOT_CERT",
)
PRIVATE_KEY_VARS = (
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM_FILE_CK_RX65N_01",
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM_CK_RX65N_01",
    "AWS_IOT_CLIENT_PRIVATE_KEY_PEM_CK_RX65N_01",
    "AWS_IOT_PRIVATE_KEY_PEM_CK_RX65N_01",
    "BG96_AWS_IOT_CLIENT_PRIVATE_KEY_PEM",
    "BG96_AWS_IOT_DEVICE_PRIVATE_KEY_PEM_FILE",
    "BG96_AWS_IOT_DEVICE_PRIVATE_KEY_PEM",
    "BG96_AWS_IOT_PRIVATE_KEY_PEM",
    "BG96_AWS_IOT_CLIENT_PRIVATE_KEY",
    "BG96_AWS_IOT_DEVICE_PRIVATE_KEY",
    "BG96_AWS_IOT_PRIVATE_KEY",
    "BG96_MQTT_CLIENT_PRIVATE_KEY_PEM",
    "BG96_MQTT_DEVICE_PRIVATE_KEY_PEM_FILE",
    "BG96_MQTT_DEVICE_PRIVATE_KEY_PEM",
    "BG96_MQTT_PRIVATE_KEY_PEM",
    "BG96_MQTT_CLIENT_PRIVATE_KEY",
    "BG96_MQTT_DEVICE_PRIVATE_KEY",
    "BG96_MQTT_PRIVATE_KEY",
    "AWS_IOT_CLIENT_PRIVATE_KEY_PEM",
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM_FILE",
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM",
    "AWS_IOT_PRIVATE_KEY_PEM",
    "AWS_IOT_CLIENT_PRIVATE_KEY",
    "AWS_IOT_DEVICE_PRIVATE_KEY",
    "AWS_IOT_PRIVATE_KEY",
    "AWS_CLIENT_PRIVATE_KEY_PEM",
    "CLIENT_PRIVATE_KEY_PEM",
    "AWS_IOT_PRIVKEY",
)
DYNAMIC_THING_NAME_VARS = ("RX65N_BG96_AWS_IOT_THING_NAME",)
DYNAMIC_CLIENT_CERT_VARS = ("AWS_IOT_CERT",)
DYNAMIC_PRIVATE_KEY_VARS = ("AWS_IOT_PRIVKEY",)
ROOT_CA_VARS = (
    "AWS_IOT_ROOT_CA_PEM_CK_RX65N_01",
    "BG96_AWS_IOT_ROOT_CA_PEM",
    "BG96_MQTT_ROOT_CA_PEM",
    "AWS_IOT_ROOT_CA_PEM",
)
def env_value(names: tuple[str, ...]) -> tuple[str | None, str | None]:
    for name in names:
        value = os.environ.get(name)
        if value:
            path = Path(value)
            if path.is_file():
                return path.read_text(encoding="utf-8").strip(), name
            return value.strip(), name
    return None, None


def normalize_pem(value: str | None) -> str | None:
    if value is None:
        return None
    if "\\n" in value and "\n" not in value:
        value = value.replace("\\r", "").replace("\\n", "\n")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        return None
    return value + "\n"


def normalize_certificate_pem(value: str | None) -> str | None:
    normalized = normalize_pem(value)
    if normalized is None:
        return None

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
    except ModuleNotFoundError as exc:
        raise RuntimeError("cryptography is required to validate MQTT client certificates") from exc

    try:
        cert = x509.load_pem_x509_certificate(normalized.encode("utf-8"))
    except ValueError as exc:
        raise RuntimeError("MQTT client certificate PEM could not be parsed") from exc

    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def normalize_private_key_pem(value: str | None) -> str | None:
    normalized = normalize_pem(value)
    if normalized is None:
        return None

    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec, rsa
    except ModuleNotFoundError as exc:
        raise RuntimeError("cryptography is required to validate MQTT private keys") from exc

    try:
        key = serialization.load_pem_private_key(normalized.encode("utf-8"), password=None)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("MQTT private key PEM could not be parsed as an unencrypted key") from exc

    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise RuntimeError(f"unsupported MQTT private key type: {type(key).__name__}")

    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode("ascii")


def credential_summary(client_cert: str, private_key: str) -> list[str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

    cert = x509.load_pem_x509_certificate(client_cert.encode("utf-8"))
    key = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
    cert_public_key = cert.public_key()
    first_line = private_key.splitlines()[0] if private_key.splitlines() else ""

    if isinstance(key, rsa.RSAPrivateKey):
        key_type = f"RSA {key.key_size}"
        message = b"bg96-mqtt-key-match"
        signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        matches = isinstance(cert_public_key, rsa.RSAPublicKey) and cert_public_key.key_size == key.key_size
        if matches:
            try:
                cert_public_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
            except Exception:
                matches = False
    elif isinstance(key, ec.EllipticCurvePrivateKey):
        key_type = f"EC {key.curve.name}"
        message = b"bg96-mqtt-key-match"
        signature = key.sign(message, ec.ECDSA(hashes.SHA256()))
        matches = isinstance(cert_public_key, ec.EllipticCurvePublicKey) and cert_public_key.curve.name == key.curve.name
        if matches:
            try:
                cert_public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            except Exception:
                matches = False
    else:
        key_type = type(key).__name__
        matches = False

    if not matches:
        raise RuntimeError("MQTT private key does not match the client certificate")

    return [
        f"MQTT credential private key type: {key_type}",
        f"MQTT credential private key header after normalization: {first_line}",
        "MQTT credential certificate/private key match: true",
    ]


def c_string_literal(value: str) -> str:
    return f'"{value.encode("unicode_escape").decode("ascii")}"'


def pem_c_string_literal(value: str) -> str:
    lines = value.splitlines()
    if not lines:
        return '""'
    return " \\\n".join(f'"{line.encode("unicode_escape").decode("ascii")}\\n"' for line in lines)


def patch_define(path: Path, macro: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^#define\s+{re.escape(macro)}\s+\(\s*[01]\s*\)\s*$", re.MULTILINE)
    replacement = f"#define {macro:<32}({value})"
    updated, count = pattern.subn(replacement, text)
    if count != 1:
        raise RuntimeError(f"could not patch {macro} in {path}")
    path.write_text(updated, encoding="utf-8", newline="")


def write_credentials(app_dir: Path, credentials: dict[str, str]) -> None:
    frtos_config = app_dir / "src" / "frtos_config"
    frtos_config.mkdir(parents=True, exist_ok=True)

    endpoint = c_string_literal(credentials["endpoint"])
    thing_name = c_string_literal(credentials["thing_name"])
    cert = pem_c_string_literal(credentials["client_cert"])
    private_key = pem_c_string_literal(credentials["private_key"]) if credentials.get("private_key") else "(NULL)"

    (frtos_config / "aws_clientcredential.h").write_text(
        f"""#ifndef __AWS_CLIENTCREDENTIAL__H__
#define __AWS_CLIENTCREDENTIAL__H__

#define clientcredentialMQTT_BROKER_ENDPOINT         {endpoint}
#define clientcredentialIOT_THING_NAME               {thing_name}
#define clientcredentialMQTT_BROKER_PORT             (8883)
#define clientcredentialGREENGRASS_DISCOVERY_PORT    (8443)
#define clientcredentialWIFI_SSID                    ""
#define clientcredentialWIFI_PASSWORD                ""
#define clientcredentialWIFI_SECURITY                (eWiFiSecurityWPA2)

#endif /* __AWS_CLIENTCREDENTIAL__H__ */
""",
        encoding="utf-8",
        newline="\n",
    )

    (frtos_config / "aws_clientcredential_keys.h").write_text(
        f"""#ifndef AWS_CLIENT_CREDENTIAL_KEYS_H
#define AWS_CLIENT_CREDENTIAL_KEYS_H

#define BG96_CI_MQTT_CREDENTIALS           (1)
#define keyCLIENT_CERTIFICATE_PEM                   {cert}
#define keyJITR_DEVICE_CERTIFICATE_AUTHORITY_PEM    (NULL)
#define keyCLIENT_PRIVATE_KEY_PEM                   {private_key}

#endif /* AWS_CLIENT_CREDENTIAL_KEYS_H */
""",
        encoding="utf-8",
        newline="\n",
    )

    root_ca = normalize_pem(credentials.get("root_ca"))
    if root_ca:
        demo_config = frtos_config / "demo_config.h"
        text = demo_config.read_text(encoding="utf-8")
        text = re.sub(
            r"^#define\s+democonfigROOT_CA_PEM\s+.+$",
            f"#define democonfigROOT_CA_PEM                   {pem_c_string_literal(root_ca)}",
            text,
            flags=re.MULTILINE,
        )
        demo_config.write_text(text, encoding="utf-8", newline="")

    demo_config = frtos_config / "demo_config.h"
    text = demo_config.read_text(encoding="utf-8")
    text, client_identifier_count = re.subn(
        r"^\s*#define\s+democonfigCLIENT_IDENTIFIER\s+.+$",
        f"#define democonfigCLIENT_IDENTIFIER       {thing_name}",
        text,
        flags=re.MULTILINE,
    )
    text, endpoint_count = re.subn(
        r"^\s*#define\s+democonfigMQTT_BROKER_ENDPOINT\s+.+$",
        f"#define democonfigMQTT_BROKER_ENDPOINT     {endpoint}",
        text,
        flags=re.MULTILINE,
    )
    if client_identifier_count == 0:
        raise RuntimeError("could not patch democonfigCLIENT_IDENTIFIER in demo_config.h")
    if endpoint_count != 1:
        raise RuntimeError("could not patch democonfigMQTT_BROKER_ENDPOINT in demo_config.h")
    demo_config.write_text(text, encoding="utf-8", newline="")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", type=Path, default=Path("Projects/aws_bg96_ck_rx65n/e2studio_ccrx"))
    parser.add_argument("--marker", type=Path, default=Path("artifacts/mqtt_credentials_configured"))
    parser.add_argument("--require", action="store_true", default=os.environ.get("BG96_MQTT_REQUIRE_CREDENTIALS") == "true")
    parser.add_argument("--tls-backend", choices=("software", "tsip"),
                        default=os.environ.get("RX65N_BG96_TLS_BACKEND", "software"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    endpoint, endpoint_var = env_value(ENDPOINT_VARS)
    if args.tls_backend == "tsip":
        thing_name, thing_name_var = env_value(THING_NAME_VARS)
        client_cert, client_cert_var = env_value(CLIENT_CERT_VARS)
        private_key, private_key_var = None, None
    else:
        dynamic_thing_name, dynamic_thing_name_var = env_value(DYNAMIC_THING_NAME_VARS)
        dynamic_client_cert, dynamic_client_cert_var = env_value(DYNAMIC_CLIENT_CERT_VARS)
        dynamic_private_key, dynamic_private_key_var = env_value(DYNAMIC_PRIVATE_KEY_VARS)
        if any((dynamic_thing_name, dynamic_client_cert, dynamic_private_key)):
            thing_name, thing_name_var = dynamic_thing_name, dynamic_thing_name_var
            client_cert, client_cert_var = dynamic_client_cert, dynamic_client_cert_var
            private_key, private_key_var = dynamic_private_key, dynamic_private_key_var
        else:
            thing_name, thing_name_var = env_value(THING_NAME_VARS)
            client_cert, client_cert_var = env_value(CLIENT_CERT_VARS)
            private_key, private_key_var = env_value(PRIVATE_KEY_VARS)
    root_ca, root_ca_var = env_value(ROOT_CA_VARS)

    normalized_client_cert = normalize_certificate_pem(client_cert)
    normalized_private_key = None if args.tls_backend == "tsip" else normalize_private_key_pem(private_key)
    required = {
        "endpoint": endpoint,
        "thing_name": thing_name,
        "client_cert": normalized_client_cert,
    }
    if args.tls_backend != "tsip":
        required["private_key"] = normalized_private_key
    missing = [name for name, value in required.items() if not value]
    if missing:
        message = f"MQTT credential variables incomplete; missing {', '.join(missing)}. Leaving CLI provisioning enabled."
        if args.require:
            raise RuntimeError(message)
        print(message)
        return 0

    if args.tls_backend == "tsip":
        print("MQTT credential private key PEM is omitted for TSIP backend.")
    else:
        for line in credential_summary(required["client_cert"], required["private_key"]):  # type: ignore[arg-type]
            print(line)

    write_credentials(
        args.app_dir,
        {
            **required,  # type: ignore[arg-type]
            "private_key": normalized_private_key or "",
            "root_ca": root_ca or "",
        },
    )
    args.marker.parent.mkdir(parents=True, exist_ok=True)
    args.marker.write_text("configured\n", encoding="utf-8")

    used = [endpoint_var, thing_name_var, client_cert_var]
    if args.tls_backend != "tsip":
        used.append(private_key_var)
    if root_ca_var:
        used.append(root_ca_var)
    print("Configured MQTT credentials from CI variables: " + ", ".join(name for name in used if name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

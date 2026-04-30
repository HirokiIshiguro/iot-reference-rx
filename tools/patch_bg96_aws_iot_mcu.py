#!/usr/bin/env python3
"""Patch and restore the local AWS IoT MCU tree for CK-RX65N BG96 CI builds."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path


DEFAULT_AWS_ROOT = Path("Projects/aws_bg96_ck_rx65n/e2studio_ccrx")
RELATIVE_SOURCE = Path("Demos/dev_mode_key_provisioning/src/aws_dev_mode_key_provisioning.c")
RELATIVE_MQTT_AGENT_SOURCE = Path("Demos/mqtt_agent/mqtt_agent_task.c")
PATCH_MARKER = "Codex CI patch: use the initialized PKCS#11 RNG for Mbed TLS 3 key parsing."
MQTT_AGENT_PATCH_MARKER = "defined(__TEST__) || defined(BG96_CI_MQTT_CREDENTIALS)"
MQTT_AGENT_DEMOCONFIG_PATCH_MARKER = "Codex CI patch: use demo_config CI credentials in MQTT agent."


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", newline="")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def convert_newlines(text: str, newline: str) -> str:
    return text.replace("\n", newline)


def patch_text(text: str) -> str:
    if PATCH_MARKER in text:
        return text

    newline = newline_for(text)
    include = '#include "core_pki_utils.h"'
    if include not in text:
        raise RuntimeError("could not find core_pki_utils include")

    callback = convert_newlines(
        f"""
#if MBEDTLS_VERSION_NUMBER >= 0x03000000
/* {PATCH_MARKER} */
static int prvPkcs11RandomCallback( void * pvCtx,
                                    unsigned char * pucOutput,
                                    size_t xOutputLength )
{{
    CK_FUNCTION_LIST_PTR pxFunctionList = NULL;
    CK_SESSION_HANDLE * pxSession = ( CK_SESSION_HANDLE * ) pvCtx;
    CK_RV xResult = C_GetFunctionList( &pxFunctionList );

    if( ( xResult != CKR_OK ) || ( pxFunctionList == NULL ) || ( pxSession == NULL ) )
    {{
        return MBEDTLS_ERR_ENTROPY_SOURCE_FAILED;
    }}

    xResult = pxFunctionList->C_GenerateRandom( *pxSession,
                                                pucOutput,
                                                ( CK_ULONG ) xOutputLength );

    return ( xResult == CKR_OK ) ? 0 : MBEDTLS_ERR_ENTROPY_SOURCE_FAILED;
}}
#endif

""",
        newline,
    )
    insert_before = convert_newlines("/* Import the specified private key into storage. */", newline)
    if insert_before not in text:
        raise RuntimeError("could not find xProvisionPrivateKey insertion point")
    text = text.replace(insert_before, callback + insert_before, 1)

    declaration_pattern = re.compile(
        r"\n\s*#if MBEDTLS_VERSION_NUMBER >= 0x03000000\r?\n"
        r"\s*mbedtls_entropy_context xEntropyContext;\r?\n"
        r"\s*mbedtls_ctr_drbg_context xDrbgContext;\r?\n"
        r"\s*#endif\r?\n",
        re.MULTILINE,
    )
    text, count = declaration_pattern.subn(newline, text, count=1)
    if count != 1:
        raise RuntimeError("could not remove local Mbed TLS RNG declarations")

    parse_pattern = re.compile(
        r"#if MBEDTLS_VERSION_NUMBER < 0x03000000\r?\n"
        r"\s*lMbedResult = mbedtls_pk_parse_key\( &xMbedPkContext, pucPrivateKey, xPrivateKeyLength, NULL, 0 \);\r?\n"
        r"\s*#else\r?\n"
        r"\s*mbedtls_entropy_init\( &xEntropyContext \);\r?\n"
        r"\s*mbedtls_ctr_drbg_init\( &xDrbgContext \);\r?\n"
        r"\s*lMbedResult = mbedtls_ctr_drbg_seed\( &xDrbgContext, mbedtls_entropy_func, &xEntropyContext, NULL, 0 \);\r?\n"
        r"\s*if\( lMbedResult == 0 \)\r?\n"
        r"\s*\{\r?\n"
        r"\s*lMbedResult = mbedtls_pk_parse_key\( &xMbedPkContext, pucPrivateKey, xPrivateKeyLength, NULL, 0,\r?\n"
        r"\s*mbedtls_ctr_drbg_random, &xDrbgContext \);\r?\n"
        r"\s*\}\r?\n"
        r"\s*mbedtls_ctr_drbg_free\( &xDrbgContext \);\r?\n"
        r"\s*mbedtls_entropy_free\( &xEntropyContext \);\r?\n"
        r"\s*#endif /\* MBEDTLS_VERSION_NUMBER < 0x03000000 \*/",
        re.MULTILINE,
    )
    replacement = convert_newlines(
        """#if MBEDTLS_VERSION_NUMBER < 0x03000000
        lMbedResult = mbedtls_pk_parse_key( &xMbedPkContext, pucPrivateKey, xPrivateKeyLength, NULL, 0 );
    #else
        lMbedResult = mbedtls_pk_parse_key( &xMbedPkContext,
                                            pucPrivateKey,
                                            xPrivateKeyLength,
                                            NULL,
                                            0,
                                            prvPkcs11RandomCallback,
                                            &xSession );
    #endif /* MBEDTLS_VERSION_NUMBER < 0x03000000 */""",
        newline,
    )
    text, count = parse_pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("could not patch private key parse RNG block")

    return text


def patch_mqtt_agent_text(text: str) -> str:
    newline = newline_for(text)
    old = "#if defined(__TEST__)"
    new = f"#if {MQTT_AGENT_PATCH_MARKER}"
    if old in text:
        text = text.replace(old, new, 1)
    elif MQTT_AGENT_PATCH_MARKER not in text:
        raise RuntimeError("could not find MQTT agent credential selection block")

    if MQTT_AGENT_DEMOCONFIG_PATCH_MARKER in text:
        return text

    pattern = re.compile(
        r"(?P<if>#if\s+defined\(__TEST__\)\s+\|\|\s+defined\(BG96_CI_MQTT_CREDENTIALS\)\r?\n)"
        r"\s*pcThingName\s*=\s*clientcredentialIOT_THING_NAME\s*;\r?\n"
        r"\s*pcBrokerEndpoint\s*=\s*clientcredentialMQTT_BROKER_ENDPOINT\s*;\r?\n"
        r"\s*pcRootCA\s*=\s*\(char \*\)\s*democonfigROOT_CA_PEM\s*;\r?\n",
        re.MULTILINE,
    )
    replacement = convert_newlines(
        f"""\\g<if>    /* {MQTT_AGENT_DEMOCONFIG_PATCH_MARKER} */
    pcThingName = democonfigCLIENT_IDENTIFIER ;
    pcBrokerEndpoint = democonfigMQTT_BROKER_ENDPOINT;
    pcRootCA = (char *) democonfigROOT_CA_PEM;
""",
        newline,
    )
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("could not patch MQTT agent CI credential values")
    return text


def mqtt_agent_backup_path(backup: Path) -> Path:
    return backup.with_name(backup.name + ".mqtt_agent_task.c")


def patch(args: argparse.Namespace) -> int:
    source = args.aws_root / RELATIVE_SOURCE
    mqtt_agent_source = args.aws_root / RELATIVE_MQTT_AGENT_SOURCE
    if not source.is_file():
        raise RuntimeError(f"AWS IoT MCU source not found: {source}")
    if not mqtt_agent_source.is_file():
        raise RuntimeError(f"AWS IoT MCU MQTT agent source not found: {mqtt_agent_source}")

    original_bytes = source.read_bytes()
    original_text = original_bytes.decode("utf-8")
    patched_text = patch_text(original_text)

    mqtt_agent_original_bytes = mqtt_agent_source.read_bytes()
    mqtt_agent_original_text = mqtt_agent_original_bytes.decode("utf-8")
    mqtt_agent_patched_text = patch_mqtt_agent_text(mqtt_agent_original_text)

    if patched_text == original_text:
        print(f"AWS IoT MCU dev-mode key provisioning source already patched: {source}")
    else:
        args.backup.parent.mkdir(parents=True, exist_ok=True)
        if not args.backup.exists():
            args.backup.write_bytes(original_bytes)
        write_text(source, patched_text)
        print(f"Patched AWS IoT MCU dev-mode key provisioning source: {source}")

    mqtt_backup = mqtt_agent_backup_path(args.backup)
    if mqtt_agent_patched_text == mqtt_agent_original_text:
        print(f"AWS IoT MCU MQTT agent source already patched: {mqtt_agent_source}")
    else:
        mqtt_backup.parent.mkdir(parents=True, exist_ok=True)
        if not mqtt_backup.exists():
            mqtt_backup.write_bytes(mqtt_agent_original_bytes)
        write_text(mqtt_agent_source, mqtt_agent_patched_text)
        print(f"Patched AWS IoT MCU MQTT agent source: {mqtt_agent_source}")
    return 0


def restore(args: argparse.Namespace) -> int:
    source = args.aws_root / RELATIVE_SOURCE
    mqtt_agent_source = args.aws_root / RELATIVE_MQTT_AGENT_SOURCE
    restored = False
    if args.backup.exists():
        shutil.copyfile(args.backup, source)
        args.backup.unlink()
        restored = True
        print(f"Restored AWS IoT MCU dev-mode key provisioning source: {source}")

    mqtt_backup = mqtt_agent_backup_path(args.backup)
    if mqtt_backup.exists():
        shutil.copyfile(mqtt_backup, mqtt_agent_source)
        mqtt_backup.unlink()
        restored = True
        print(f"Restored AWS IoT MCU MQTT agent source: {mqtt_agent_source}")

    if not restored:
        print("No AWS IoT MCU patch backup found; restore skipped.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("patch", "restore"))
    parser.add_argument("--aws-root", type=Path, default=Path(os.environ.get("AWS_IOT_MCU_ROOT", DEFAULT_AWS_ROOT)))
    parser.add_argument("--backup", type=Path, default=Path("artifacts/aws_dev_mode_key_provisioning.c.orig"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return patch(args) if args.action == "patch" else restore(args)


if __name__ == "__main__":
    raise SystemExit(main())

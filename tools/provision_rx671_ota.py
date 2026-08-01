#!/usr/bin/env python3
"""Provision EK-RX671 OTA credentials and install only the boot-loader MOT.

The provisioner image is programmed without chip erase, its short-lived CLI is
used to format and populate LittleFS, and the boot-loader MOT is then programmed
without touching Data Flash.  The boot loader is deliberately left in reset;
``test_rx671_ota.py`` opens SCI6 before releasing it so no one-shot marker is
lost and keeps that same UART open through the complete OTA transaction.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from rx671_ota_host import (
    DEFAULT_BAUD,
    DEFAULT_PORT,
    DEFAULT_RFP_TIMEOUT,
    CLI_PROMPT_TOKENS,
    RfpConfig,
    TimestampLog,
    cleanup_plaintext,
    open_serial,
    read_until,
    run_checked,
    send_ascii_command,
    send_ascii_bytes_command,
    write_json,
    write_junit,
)


CLI_INVITES = (
    b"Press CLI and enter",
    b"FreeRTOS command server.",
    b"Going to FreeRTOS-CLI",
    *CLI_PROMPT_TOKENS,
)

WIFI_SSID_MAX_BYTES = 32
WIFI_PASSPHRASE_MIN_BYTES = 8
WIFI_PASSPHRASE_MAX_BYTES = 63


def _required_file(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"file does not exist: {value}")
    return path


def enter_cli(serial_port, *, timeout: float, char_delay: float) -> None:
    try:
        read_until(serial_port, success_tokens=CLI_INVITES, timeout=timeout)
    except TimeoutError:
        # A quiet provisioner may already be in its command loop.
        pass
    for _ in range(3):
        for character in "CLI":
            serial_port.write(character.encode("ascii"))
            if char_delay:
                time.sleep(char_delay)
        serial_port.write(b"\r\n")
        serial_port.flush()
        try:
            read_until(
                serial_port,
                success_tokens=(b"Going to FreeRTOS-CLI", *CLI_PROMPT_TOKENS),
                error_tokens=(b"fatal error",),
                timeout=5.0,
            )
            return
        except TimeoutError:
            time.sleep(0.25)
    raise TimeoutError("RX671 provisioner CLI did not become ready")


def _set_pem(serial_port, name: str, path: Path, *, char_delay: float, timeout: float) -> None:
    pem = path.read_text(encoding="ascii").replace("\r\n", "\n").replace("\r", "\n").strip()
    if "-----BEGIN " not in pem or "-----END " not in pem:
        raise ValueError(f"{name} is not a PEM file")
    send_ascii_command(
        serial_port,
        f"conf set {name} {pem}",
        timeout=timeout,
        char_delay=char_delay,
    )


def _wifi_credentials_from_environment(
    ssid_variable: str,
    passphrase_variable: str,
    environ: dict[str, str] | None = None,
) -> tuple[bytearray, bytearray]:
    source = os.environ if environ is None else environ
    ssid_text = source.get(ssid_variable, "")
    passphrase_text = source.get(passphrase_variable, "")
    if not ssid_text:
        raise ValueError(f"Wi-Fi SSID environment variable is empty: {ssid_variable}")
    if not passphrase_text:
        raise ValueError(
            "Wi-Fi passphrase environment variable is empty: "
            f"{passphrase_variable}"
        )
    ssid = bytearray(ssid_text, "utf-8")
    passphrase = bytearray(passphrase_text, "utf-8")
    try:
        if not 1 <= len(ssid) <= WIFI_SSID_MAX_BYTES:
            raise ValueError(
                f"Wi-Fi SSID must be 1..{WIFI_SSID_MAX_BYTES} UTF-8 octets"
            )
        if not WIFI_PASSPHRASE_MIN_BYTES <= len(passphrase) <= WIFI_PASSPHRASE_MAX_BYTES:
            raise ValueError(
                "Wi-Fi passphrase must be "
                f"{WIFI_PASSPHRASE_MIN_BYTES}..{WIFI_PASSPHRASE_MAX_BYTES} UTF-8 octets"
            )
    except Exception:
        _zeroize(ssid)
        _zeroize(passphrase)
        raise
    return ssid, passphrase


def _zeroize(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _hex_command(prefix: bytes, value: bytearray) -> bytearray:
    alphabet = b"0123456789abcdef"
    command = bytearray(prefix)
    for byte in value:
        command.append(alphabet[byte >> 4])
        command.append(alphabet[byte & 0x0F])
    return command


def _set_wifi_credentials(
    serial_port,
    *,
    ssid_variable: str,
    passphrase_variable: str,
    char_delay: float,
    timeout: float,
) -> None:
    ssid, passphrase = _wifi_credentials_from_environment(
        ssid_variable,
        passphrase_variable,
    )
    ssid_command = bytearray()
    passphrase_command = bytearray()
    try:
        ssid_command = _hex_command(b"conf sethex wifissid ", ssid)
        passphrase_command = _hex_command(b"conf sethex wifipass ", passphrase)
        send_ascii_bytes_command(
            serial_port,
            ssid_command,
            timeout=timeout,
            char_delay=char_delay,
        )
        send_ascii_bytes_command(
            serial_port,
            passphrase_command,
            timeout=timeout,
            char_delay=char_delay,
        )
    finally:
        _zeroize(ssid_command)
        _zeroize(passphrase_command)
        _zeroize(ssid)
        _zeroize(passphrase)


def _verify_value(
    serial_port,
    name: str,
    expected: str,
    *,
    char_delay: float,
    timeout: float,
) -> None:
    """Verify a non-secret CLI value without printing its command response."""
    try:
        expected_bytes = expected.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("CLI readback value must contain ASCII only") from None
    send_ascii_command(
        serial_port,
        f"conf get {name}",
        timeout=timeout,
        char_delay=char_delay,
        success_tokens=(
            b"\r\n" + expected_bytes + b"\r\n\r\n>",
            b"\n" + expected_bytes + b"\r\n\r\n>",
        ),
    )


def provision(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    wifi_ssid, wifi_passphrase = _wifi_credentials_from_environment(
        args.wifi_ssid_env,
        args.wifi_passphrase_env,
    )
    _zeroize(wifi_ssid)
    _zeroize(wifi_passphrase)
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    event_log = TimestampLog(artifact_dir / "provision-events.log")
    rfp = RfpConfig(
        executable=args.rfp_cli,
        device=args.rfp_device,
        tool=args.rfp_tool,
        interface=args.rfp_interface,
        speed=args.rfp_speed,
        auth_id=args.rfp_auth_id,
    )
    completed: list[str] = []
    event_log.write("program provisioner MOT without chip erase; leave target reset\n")
    run_checked(
        rfp.program_command(args.provisioner_mot, leave_reset=True),
        label="provisioner programming",
        timeout=args.rfp_timeout,
    )
    completed.append("provisioner_programmed")

    serial_port = open_serial(args.port, args.baud)
    try:
        serial_port.reset_input_buffer()
        serial_port.reset_output_buffer()
        event_log.write("release provisioner after SCI6 is open\n")
        run_checked(
            rfp.run_command(),
            label="provisioner run",
            timeout=args.rfp_timeout,
        )
        enter_cli(serial_port, timeout=args.boot_timeout, char_delay=args.char_delay)
        completed.append("cli_ready")

        # Never log command strings or UART responses: a CLI echo can contain PEM.
        send_ascii_command(
            serial_port,
            "format",
            timeout=args.command_timeout,
            char_delay=args.char_delay,
            success_tokens=(b"Format OK !",),
        )
        completed.append("format")
        event_log.write("LittleFS format OK\n")

        _set_wifi_credentials(
            serial_port,
            ssid_variable=args.wifi_ssid_env,
            passphrase_variable=args.wifi_passphrase_env,
            char_delay=args.char_delay,
            timeout=args.command_timeout,
        )
        completed.append("wifi_credentials")
        event_log.write("Wi-Fi SSID/passphrase stored (values redacted)\n")

        send_ascii_command(
            serial_port,
            f"conf set endpoint {args.endpoint}",
            timeout=args.command_timeout,
            char_delay=args.char_delay,
        )
        completed.append("endpoint")
        event_log.write("endpoint stored (value redacted)\n")

        send_ascii_command(
            serial_port,
            f"conf set thingname {args.thing_name}",
            timeout=args.command_timeout,
            char_delay=args.char_delay,
        )
        completed.append("thing")
        event_log.write("Thing name stored (value redacted)\n")

        verification_values = {
            "endpoint": args.endpoint,
            "thingname": args.thing_name,
        }
        for name, path in (
            ("cert", args.certificate),
            ("key", args.private_key),
            ("codesigncert", args.codesigner_certificate),
            ("codesignpubkey", args.codesigner_public_key),
        ):
            _set_pem(
                serial_port,
                name,
                path,
                char_delay=args.char_delay,
                timeout=args.command_timeout,
            )
            completed.append(name)
            event_log.write(f"{name} stored (payload redacted)\n")

        send_ascii_command(
            serial_port,
            "conf commit",
            timeout=args.commit_timeout,
            char_delay=args.char_delay,
            success_tokens=(b"Configuration save",),
        )
        completed.append("commit")
        event_log.write("LittleFS commit OK\n")
        for name, expected in verification_values.items():
            _verify_value(
                serial_port,
                name,
                expected,
                char_delay=args.char_delay,
                timeout=args.command_timeout,
            )
        completed.append("public_config_readback_verified")
        event_log.write(
            "endpoint and Thing name readback verified; PEM persistence is "
            "delegated to bootloader key loading, TLS, and OTA signature proof\n"
        )
    finally:
        serial_port.close()

    event_log.write("program boot-loader MOT without chip erase; preserve Data Flash and leave reset\n")
    run_checked(
        rfp.program_command(args.bootloader_mot, leave_reset=True),
        label="boot-loader programming",
        timeout=args.rfp_timeout,
    )
    completed.append("bootloader_programmed")
    event_log.write("boot-loader programming OK; target remains reset\n")
    return {
        "success": True,
        "classification": "provisioned_and_bootloader_left_reset",
        "completed_steps": completed,
        "data_flash_preserved_during_rfp_programming": True,
        "pem_readback_performed": False,
        "wifi_passphrase_readback_performed": False,
        "wifi_credentials_source": "environment_to_sci6_to_littlefs",
        "pem_verification": "delegated_to_bootloader_tls_and_ota_signature",
        "port": args.port,
        "baud": args.baud,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provisioner-mot", type=_required_file, required=True)
    parser.add_argument("--bootloader-mot", type=_required_file, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--thing-name", required=True)
    parser.add_argument("--certificate", type=_required_file, required=True)
    parser.add_argument("--private-key", type=_required_file, required=True)
    parser.add_argument("--codesigner-certificate", type=_required_file, required=True)
    parser.add_argument("--codesigner-public-key", type=_required_file, required=True)
    parser.add_argument("--wifi-ssid-env", default="RX671_EK_WIFI_SSID")
    parser.add_argument(
        "--wifi-passphrase-env",
        default="RX671_EK_WIFI_PASSPHRASE",
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--rfp-cli", default="./tools/rfp_cli_locked.sh")
    parser.add_argument("--rfp-device", default="RX671")
    parser.add_argument("--rfp-tool", default="e2l:OBE110024")
    parser.add_argument("--rfp-interface", default="fine")
    parser.add_argument("--rfp-speed", default="500K")
    parser.add_argument("--rfp-auth-id", default="FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
    parser.add_argument("--rfp-timeout", type=float, default=DEFAULT_RFP_TIMEOUT)
    parser.add_argument("--boot-timeout", type=float, default=45.0)
    parser.add_argument("--command-timeout", type=float, default=15.0)
    parser.add_argument("--commit-timeout", type=float, default=30.0)
    parser.add_argument("--char-delay", type=float, default=0.002)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--cleanup-root", type=Path)
    parser.add_argument("--cleanup-plaintext", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    if args.rfp_timeout <= 0:
        parser.error("--rfp-timeout must be positive")
    if args.cleanup_plaintext and args.cleanup_root is None:
        parser.error("--cleanup-root is required with --cleanup-plaintext")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    summary_path = args.artifact_dir / "provision-summary.json"
    junit_path = args.artifact_dir / "junit.xml"
    try:
        summary = provision(args)
        status = 0
    except Exception as exc:
        summary = {
            "success": False,
            "classification": type(exc).__name__,
            "message": str(exc),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        print(f"RX671 OTA provisioning failed: {exc}", file=sys.stderr)
        status = 1
    finally:
        if args.cleanup_plaintext:
            try:
                removed = cleanup_plaintext(args.cleanup_plaintext, args.cleanup_root)
                summary["plaintext_cleanup"] = {"success": True, "removed": removed}
            except Exception as exc:
                summary["success"] = False
                summary["plaintext_cleanup"] = {"success": False, "message": str(exc)}
                status = 1
    write_json(summary_path, summary)
    write_junit(
        junit_path,
        name="provision_rx671_ota",
        success=bool(summary["success"]),
        message=summary.get("message", summary["classification"]),
        seconds=float(summary["duration_seconds"]),
    )
    return status


if __name__ == "__main__":
    sys.exit(main())

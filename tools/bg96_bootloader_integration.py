#!/usr/bin/env python3
"""Flash bootloader, download app RSU over UART, and verify app MQTT activity."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import serial
from serial.tools import list_ports


READY = 'send "userprog.rsu" via UART.'
CODE_FLASH_BLOCK_SIZE = 32768
CODE_FLASH_BLOCKS = 24
CODE_FLASH_SIZE = CODE_FLASH_BLOCK_SIZE * CODE_FLASH_BLOCKS
CODE_FLASH_SIZE_KB = CODE_FLASH_SIZE // 1024
DF_PAD_SIZE = CODE_FLASH_BLOCK_SIZE
DEFAULT_READY_TIMEOUT_SECONDS = 180

APP_START_MARKERS = (
    "FreeRTOS command server",
    "Called: R_CELLULAR_Open()",
    "---------STARTING DEMO---------",
    "Initialise the RTOS's TCP/IP stack",
    "Start PubSub Demo Task",
)
APP_STARTUP_ERROR_MARKERS = (
    "Unable to parse private key",
    "Invalid private key type provided",
    "Failed to parse RSA private key",
    "Failed to parse EC private key",
    "ERROR: Failed to provision device Private key",
    "ERROR: Failed to provision device certificate",
)
MQTT_SUCCESS_MARKERS = (
    "Successfully subscribed to topic",
    "Successfully sent QoS",
    "---------Finish PubSub Demo Task",
)
MQTT_REACHED_MARKERS = (
    "Start MQTT Agent Task",
    "Creating a TLS connection",
)
MQTT_MISSING_CREDENTIAL_MARKERS = (
    "Invalid input parameter(s): Arguments cannot be NULL",
    "Thing name is not stored in Data Flash",
)
APP_ERROR_MARKERS = (
    "Cellular init failed",
    "failed to connect",
    "MQTT Agent connect fail",
    "MQTT connection failed",
)
ENDPOINT_VARS = (
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
    "BG96_AWS_IOT_DEVICE_CERT_PEM_FILE",
    "BG96_AWS_IOT_DEVICE_CERT_PEM",
    "BG96_AWS_IOT_CLIENT_CERTIFICATE_PEM",
    "AWS_IOT_DEVICE_CERT_PEM_FILE",
    "AWS_IOT_DEVICE_CERT_PEM",
    "AWS_IOT_CLIENT_CERTIFICATE_PEM",
    "AWS_IOT_CERT",
)
PRIVATE_KEY_VARS = (
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM_FILE_CK_RX65N_01",
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM_CK_RX65N_01",
    "AWS_IOT_CLIENT_PRIVATE_KEY_PEM_CK_RX65N_01",
    "AWS_IOT_PRIVATE_KEY_PEM_CK_RX65N_01",
    "BG96_AWS_IOT_DEVICE_PRIVATE_KEY_PEM_FILE",
    "BG96_AWS_IOT_DEVICE_PRIVATE_KEY_PEM",
    "BG96_AWS_IOT_PRIVATE_KEY_PEM",
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM_FILE",
    "AWS_IOT_DEVICE_PRIVATE_KEY_PEM",
    "AWS_IOT_PRIVATE_KEY_PEM",
    "AWS_IOT_PRIVKEY",
    "AWS_IOT_PRIVATE_KEY",
)
CELLULAR_APN_VARS = (
    "AWS_IOT_CELLULAR_APN_CK_RX65N_01",
    "BG96_CELLULAR_APN",
    "BG96_MQTT_APN",
    "CELLULAR_APN",
)
CELLULAR_APN_USER_VARS = (
    "AWS_IOT_CELLULAR_APN_USER_CK_RX65N_01",
    "BG96_CELLULAR_APN_USER",
    "BG96_MQTT_APN_USER",
    "CELLULAR_APN_USER",
)
CELLULAR_APN_PASS_VARS = (
    "AWS_IOT_CELLULAR_APN_PASS_CK_RX65N_01",
    "BG96_CELLULAR_APN_PASS",
    "BG96_MQTT_APN_PASS",
    "CELLULAR_APN_PASS",
)
CELLULAR_APN_AUTH_VARS = (
    "AWS_IOT_CELLULAR_APN_AUTH_CK_RX65N_01",
    "BG96_CELLULAR_APN_AUTH",
    "BG96_MQTT_APN_AUTH",
    "CELLULAR_APN_AUTH",
)
FLEET_TEMPLATE_VARS = (
    "AWS_FLEET_PROVISIONING_TEMPLATE_CK_RX65N_01",
    "RX65N_BG96_FLEET_PROVISIONING_TEMPLATE",
    "BG96_FLEET_PROVISIONING_TEMPLATE",
    "AWS_FLEET_PROVISIONING_TEMPLATE_RX72N_02",
    "AWS_FLEET_PROVISIONING_TEMPLATE",
)
FLEET_CLAIM_CERT_VARS = (
    "AWS_FLEET_CLAIM_CERT_CK_RX65N_01",
    "RX65N_BG96_FLEET_CLAIM_CERT_PEM",
    "RX65N_BG96_FLEET_CLAIM_CERT",
    "BG96_FLEET_CLAIM_CERT_PEM",
    "BG96_FLEET_CLAIM_CERT",
    "AWS_FLEET_CLAIM_CERT_RX72N_02",
    "AWS_FLEET_CLAIM_CERT",
)
FLEET_CLAIM_KEY_VARS = (
    "AWS_FLEET_CLAIM_PRIVATE_KEY_CK_RX65N_01",
    "RX65N_BG96_FLEET_CLAIM_PRIVATE_KEY_PEM",
    "RX65N_BG96_FLEET_CLAIM_PRIVATE_KEY",
    "BG96_FLEET_CLAIM_PRIVATE_KEY_PEM",
    "BG96_FLEET_CLAIM_PRIVATE_KEY",
    "AWS_FLEET_CLAIM_PRIVATE_KEY_RX72N_02",
    "AWS_FLEET_CLAIM_PRIVATE_KEY",
)
@dataclass
class SerialCandidate:
    path: str
    port: serial.Serial
    label: str
    received: int = 0
    tail: str = ""


def default_rfp_cli() -> str:
    return (
        os.environ.get("RFP_CLI")
        or os.environ.get("RFP_CLI_PATH")
        or (
            r"C:\Program Files (x86)\Renesas Electronics\Programming Tools\Renesas Flash Programmer V3.22\rfp-cli.exe"
            if os.name == "nt"
            else "/usr/local/bin/rfp-cli"
        )
    )


def normalize_tool_spec(tool: str) -> str:
    if not tool:
        return "e2l"
    lowered = tool.lower()
    if lowered.startswith(("e2l", "e2", "jlink", "ezcube")):
        return tool
    return f"e2l:{tool}"


def run_rfp(args: argparse.Namespace, rfp_args: list[str]) -> None:
    tool = normalize_tool_spec(args.rfp_tool)
    command = [
        args.rfp_cli,
        "-d", args.rfp_device,
        "-t", tool,
        "-if", args.rfp_interface,
        "-s", args.rfp_speed,
        "-auth", "id", args.rfp_auth_id,
        *rfp_args,
        "-noquery",
    ]
    print("[RFP] " + " ".join(command))
    subprocess.run(command, check=True)


def write_serial_text(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.buffer.write(text.encode(encoding, errors="replace"))
    sys.stdout.flush()


def read_text(port: serial.Serial, timeout: float) -> str:
    deadline = time.time() + timeout
    data = bytearray()
    while time.time() < deadline:
        chunk = port.read(port.in_waiting or 1)
        if chunk:
            data.extend(chunk)
            text = chunk.decode("utf-8", errors="replace")
            write_serial_text(text)
        else:
            time.sleep(0.02)
    return data.decode("utf-8", errors="replace")


def env_text(names: tuple[str, ...]) -> tuple[str | None, str | None]:
    for name in names:
        value = os.environ.get(name)
        if not value:
            continue
        path = Path(value)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip(), name
        return value.strip(), name
    return None, None


def normalize_cli_pem(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def send_serial_chars(port: serial.Serial, text: str, char_delay: float) -> None:
    for char in text:
        port.write(char.encode("ascii"))
        if char_delay > 0:
            time.sleep(char_delay)


def read_cli_response(
    port: serial.Serial,
    timeout: float,
    *,
    echo: bool,
    success_tokens: tuple[str, ...] = (),
    error_tokens: tuple[str, ...] = ("Error",),
) -> str:
    deadline = time.time() + timeout
    buffer = ""
    while time.time() < deadline:
        chunk = port.read(port.in_waiting or 1)
        if chunk:
            text = chunk.decode("utf-8", errors="replace")
            buffer += text
            if echo:
                write_serial_text(text)
            if any(token in buffer for token in error_tokens):
                return buffer
            if success_tokens and any(token in buffer for token in success_tokens):
                return buffer
        else:
            time.sleep(0.05)
    return buffer


def enter_cli_mode(port: serial.Serial, timeout: float, *, char_delay: float, line_delay: float) -> None:
    print("\n[CLI] waiting for short CLI window")
    deadline = time.time() + timeout
    buffer = ""
    next_retry = 0.0
    while time.time() < deadline:
        now = time.time()
        if now >= next_retry:
            send_serial_chars(port, "CLI", char_delay)
            port.write(b"\r\n")
            port.flush()
            next_retry = now + 0.7
            time.sleep(line_delay)

        chunk = port.read(port.in_waiting or 1)
        if chunk:
            text = chunk.decode("utf-8", errors="replace")
            buffer += text
            write_serial_text(text)
            if "Going to FreeRTOS-CLI" in buffer:
                print("\n[CLI] entered CLI mode")
                return
            if READY in buffer:
                raise RuntimeError("bootloader prompt observed while waiting for app CLI")
        else:
            time.sleep(0.05)
    raise RuntimeError("timed out waiting for app CLI mode")


def send_cli_command(
    port: serial.Serial,
    command: str,
    *,
    char_delay: float,
    line_delay: float,
    timeout: float = 3.0,
    success_tokens: tuple[str, ...] = ("OK",),
    secret: bool = False,
) -> str:
    label = command if not secret else " ".join(command.split(" ", 3)[:3]) + " <redacted>"
    print(f"\n[CLI] {label}")
    port.reset_input_buffer()
    send_serial_chars(port, command, char_delay)
    port.write(b"\r\n")
    port.flush()
    time.sleep(line_delay)
    response = read_cli_response(port, timeout, echo=not secret, success_tokens=success_tokens)
    if secret:
        print("[CLI] response: " + ("OK" if "OK" in response else "Error" if "Error" in response else "<no visible response>"))
    if "Error" in response:
        raise RuntimeError(f"CLI command failed: {label}")
    if success_tokens and not any(token in response for token in success_tokens):
        raise RuntimeError(f"CLI command did not report success: {label}")
    return response


def send_cli_pem(
    port: serial.Serial,
    key_name: str,
    pem: str,
    *,
    char_delay: float,
    line_delay: float,
) -> None:
    pem_content = normalize_cli_pem(pem)
    total_len = len(f"conf set {key_name} ") + len(pem_content)
    if total_len > 4090:
        print(f"[CLI] warning: conf set {key_name} command length {total_len} is near CLI buffer limit")
    send_cli_command(
        port,
        f"conf set {key_name} " + pem_content,
        char_delay=char_delay,
        line_delay=line_delay,
        timeout=5.0,
        secret=True,
    )


def provision_cellular_apn(args: argparse.Namespace, port: serial.Serial) -> None:
    apn, apn_var = env_text(CELLULAR_APN_VARS)
    apn_user, user_var = env_text(CELLULAR_APN_USER_VARS)
    apn_pass, pass_var = env_text(CELLULAR_APN_PASS_VARS)
    apn_auth, auth_var = env_text(CELLULAR_APN_AUTH_VARS)

    if not any((apn, apn_user, apn_pass, apn_auth)):
        print("\n[CLI] no cellular APN override variables configured; using firmware built-in APN")
        return
    if not apn:
        raise RuntimeError("cellular APN user/pass/auth overrides require an APN value")

    print("\n[CLI] provisioning cellular APN from variables: " + apn_var)
    send_cli_command(
        port,
        f"conf set apn {apn}",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
    )
    if apn_user:
        print("[CLI] provisioning cellular APN user from variable: " + user_var)
        send_cli_command(
            port,
            f"conf set apnuser {apn_user}",
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
            secret=True,
        )
    if apn_pass:
        print("[CLI] provisioning cellular APN password from variable: " + pass_var)
        send_cli_command(
            port,
            f"conf set apnpass {apn_pass}",
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
            secret=True,
        )
    if apn_auth:
        if apn_auth not in {"0", "1", "2"}:
            raise RuntimeError(f"cellular APN auth must be 0, 1, or 2; got {apn_auth!r}")
        print("[CLI] provisioning cellular APN auth from variable: " + auth_var)
        send_cli_command(
            port,
            f"conf set apnauth {apn_auth}",
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
        )


def provision_mqtt_credentials(args: argparse.Namespace, port: serial.Serial) -> None:
    endpoint, endpoint_var = env_text(ENDPOINT_VARS)
    thing_name, thing_name_var = env_text(THING_NAME_VARS)
    client_cert, cert_var = env_text(CLIENT_CERT_VARS)
    private_key, key_var = env_text(PRIVATE_KEY_VARS)
    missing = [
        name
        for name, value in (
            ("endpoint", endpoint),
            ("thing_name", thing_name),
            ("client_cert", client_cert),
            ("private_key", private_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("cannot provision MQTT credentials; missing " + ", ".join(missing))

    print(
        "\n[CLI] provisioning MQTT credentials from variables: "
        + ", ".join(name for name in (endpoint_var, thing_name_var, cert_var, key_var) if name)
    )
    enter_cli_mode(port, args.provision_cli_timeout, char_delay=args.provision_char_delay, line_delay=args.provision_line_delay)
    send_cli_command(
        port,
        "format",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
        timeout=6.0,
        success_tokens=("OK",),
    )
    provision_cellular_apn(args, port)
    send_cli_command(
        port,
        f"conf set endpoint {endpoint}",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
    )
    send_cli_command(
        port,
        f"conf set thingname {thing_name}",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
    )
    send_cli_pem(port, "cert", client_cert, char_delay=args.provision_char_delay, line_delay=args.provision_line_delay)
    send_cli_pem(port, "key", private_key, char_delay=args.provision_char_delay, line_delay=args.provision_line_delay)
    send_cli_command(
        port,
        "conf commit",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
        timeout=30.0,
        success_tokens=("Configuration save",),
    )
    print("\n[CLI] MQTT credential provisioning complete; resetting app")
    port.reset_input_buffer()
    run_rfp(args, ["-sig", "-run"])


def provision_fleet_credentials(args: argparse.Namespace, port: serial.Serial) -> None:
    endpoint, endpoint_var = env_text(ENDPOINT_VARS)
    template, template_var = env_text(FLEET_TEMPLATE_VARS)
    claim_cert, claim_cert_var = env_text(FLEET_CLAIM_CERT_VARS)
    claim_key, claim_key_var = env_text(FLEET_CLAIM_KEY_VARS)
    missing = [
        name
        for name, value in (
            ("endpoint", endpoint),
            ("template", template),
            ("claim_cert", claim_cert),
            ("claim_key", claim_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("cannot provision Fleet credentials; missing " + ", ".join(missing))

    print(
        "\n[CLI] provisioning Fleet credentials from variables: "
        + ", ".join(name for name in (endpoint_var, template_var, claim_cert_var, claim_key_var) if name)
    )
    enter_cli_mode(port, args.provision_cli_timeout, char_delay=args.provision_char_delay, line_delay=args.provision_line_delay)
    send_cli_command(
        port,
        "format",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
        timeout=6.0,
        success_tokens=("OK",),
    )
    provision_cellular_apn(args, port)
    send_cli_command(
        port,
        f"conf set endpoint {endpoint}",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
    )
    send_cli_command(
        port,
        f"conf set template {template}",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
    )
    send_cli_pem(port, "claimcert", claim_cert, char_delay=args.provision_char_delay, line_delay=args.provision_line_delay)
    send_cli_pem(port, "claimkey", claim_key, char_delay=args.provision_char_delay, line_delay=args.provision_line_delay)
    send_cli_command(
        port,
        "conf commit",
        char_delay=args.provision_char_delay,
        line_delay=args.provision_line_delay,
        timeout=30.0,
        success_tokens=("Configuration save",),
    )
    print("\n[CLI] Fleet credential provisioning complete; leaving app in CLI mode for test reset")
    port.reset_input_buffer()


def serial_display_name(path: str) -> str:
    return Path(path).name if path.startswith("/dev/") else path


def auto_probe_ports() -> list[str]:
    candidates: list[str] = []
    for pattern in (
        "/dev/serial/by-id/*",
        "/dev/serial/by-path/*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    ):
        candidates.extend(str(path) for path in sorted(Path("/").glob(pattern.removeprefix("/"))))

    for port_info in list_ports.comports():
        if port_info.device:
            candidates.append(port_info.device)

    return candidates


def print_uart_inventory() -> None:
    print("[UART] serial inventory:")
    ports = list(list_ports.comports())
    if ports:
        for port_info in ports:
            details = []
            if port_info.description:
                details.append(port_info.description)
            if port_info.serial_number:
                details.append(f"serial={port_info.serial_number}")
            if port_info.hwid:
                details.append(port_info.hwid)
            print(f"[UART]   {port_info.device}: {'; '.join(details)}")
    else:
        print("[UART]   pyserial reported no ports")

    for directory in (Path("/dev/serial/by-id"), Path("/dev/serial/by-path")):
        if not directory.exists():
            print(f"[UART]   {directory}: missing")
            continue
        for entry in sorted(directory.iterdir()):
            try:
                target = entry.resolve()
            except OSError:
                target = Path("?")
            print(f"[UART]   {entry} -> {target}")


def parse_probe_ports(primary: str) -> list[str]:
    candidates = []
    if primary and primary != "unused":
        candidates.append(primary)

    raw = os.environ.get("BG96_BOOTLOADER_PROBE_UART_PORTS", "")
    for entry in raw.replace(";", ",").split(","):
        entry = entry.strip()
        if entry:
            candidates.append(entry)

    if os.environ.get("BG96_BOOTLOADER_AUTO_PROBE", "true").lower() in ("1", "true", "yes", "on"):
        candidates.extend(auto_probe_ports())

    deduped: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        key = os.path.realpath(path) if path.startswith("/dev/") and os.path.exists(path) else path
        if path and key not in seen:
            deduped.append(path)
            seen.add(key)
    return deduped


def open_serial_candidate(path: str, baud: int) -> SerialCandidate:
    port = serial.Serial()
    port.port = path
    port.baudrate = baud
    port.timeout = 0.1
    port.write_timeout = 10
    port.dtr = False
    port.rts = False
    port.open()
    port.reset_input_buffer()
    label = serial_display_name(path)
    print(f"[UART] opened {label} at {baud} bps")
    return SerialCandidate(path=path, port=port, label=label)


def open_serial_candidates(paths: list[str], baud: int) -> list[SerialCandidate]:
    print_uart_inventory()
    opened: list[SerialCandidate] = []
    for path in paths:
        try:
            opened.append(open_serial_candidate(path, baud))
        except serial.SerialException as exc:
            print(f"[UART] skipped {serial_display_name(path)}: {exc}")
    if not opened:
        raise RuntimeError("no UART candidate could be opened")
    return opened


def close_unselected_candidates(candidates: list[SerialCandidate], selected: SerialCandidate) -> None:
    for candidate in candidates:
        if candidate is selected:
            continue
        try:
            candidate.port.close()
        except serial.SerialException:
            pass


def wait_for_ready_on_any(candidates: list[SerialCandidate], timeout: float) -> SerialCandidate | None:
    deadline = time.time() + timeout
    buffers = {candidate.path: "" for candidate in candidates}
    while time.time() < deadline:
        saw_data = False
        for candidate in candidates:
            port = candidate.port
            chunk = port.read(port.in_waiting or 1)
            if not chunk:
                continue

            saw_data = True
            candidate.received += len(chunk)
            text = chunk.decode("utf-8", errors="replace")
            if len(candidates) == 1:
                write_serial_text(text)
            else:
                for line in text.splitlines(keepends=True):
                    write_serial_text(f"[UART:{candidate.label}] {line}")

            candidate.tail = (candidate.tail + text)[-512:]
            buffers[candidate.path] = (buffers[candidate.path] + text)[-8192:]
            if READY in buffers[candidate.path]:
                print(f"\n[UART] bootloader ready observed on {candidate.label}")
                return candidate

        if not saw_data:
            time.sleep(0.02)

    print("\n[UART] bootloader ready was not observed on any candidate")
    for candidate in candidates:
        tail = candidate.tail.replace("\r", "\\r").replace("\n", "\\n")
        print(f"[UART] {candidate.label}: received={candidate.received} tail={tail!r}")
    return None


def wait_for(port: serial.Serial, marker: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    buffer = ""
    while time.time() < deadline:
        chunk = port.read(port.in_waiting or 1)
        if chunk:
            text = chunk.decode("utf-8", errors="replace")
            write_serial_text(text)
            buffer += text
            if marker in buffer:
                return True
            if len(buffer) > 8192:
                buffer = buffer[-8192:]
        else:
            time.sleep(0.02)
    return False


def wait_for_any(
    port: serial.Serial,
    markers: tuple[str, ...],
    timeout: float,
    failure_markers: tuple[str, ...] = (),
) -> str | None:
    deadline = time.time() + timeout
    buffer = ""
    while time.time() < deadline:
        chunk = port.read(port.in_waiting or 1)
        if chunk:
            text = chunk.decode("utf-8", errors="replace")
            write_serial_text(text)
            buffer += text
            for marker in markers:
                if marker in buffer:
                    return marker
            lowered = buffer.lower()
            for marker in failure_markers:
                if marker.lower() in lowered:
                    raise RuntimeError(f"app startup failed before MQTT verification: {marker}")
            if len(buffer) > 8192:
                buffer = buffer[-8192:]
        else:
            time.sleep(0.02)
    return None


def send_block(port: serial.Serial, data: bytes, offset: int, size: int) -> None:
    view = memoryview(data)[offset:offset + size]
    while view:
        written = port.write(view[:4096])
        view = view[written:]
    port.flush()


def download_rsu(port: serial.Serial, rsu_path: Path, ready_observed: bool = False) -> None:
    data = rsu_path.read_bytes()
    if len(data) != CODE_FLASH_SIZE:
        raise RuntimeError(f"unexpected RSU size for contiguous bootloader protocol: {len(data)}")

    if not ready_observed and not wait_for(port, READY, DEFAULT_READY_TIMEOUT_SECONDS):
        raise RuntimeError(f"bootloader ready message not observed: {READY}")

    for block in range(CODE_FLASH_BLOCKS):
        send_block(port, data, block * CODE_FLASH_BLOCK_SIZE, CODE_FLASH_BLOCK_SIZE)
        kb = (block + 1) * (CODE_FLASH_BLOCK_SIZE // 1024)
        if block == CODE_FLASH_BLOCKS - 1:
            if not wait_for(port, "bank1(temporary area) on code flash integrity check...OK", 180):
                raise RuntimeError("downloaded RSU did not pass bootloader integrity check")
            break
        if not wait_for(port, f"({kb}/{CODE_FLASH_SIZE_KB}KB)", 45):
            raise RuntimeError(f"timed out waiting for firmware progress {kb}/{CODE_FLASH_SIZE_KB}KB")

    pad = b"\xff" * DF_PAD_SIZE
    send_block(port, pad, 0, len(pad))
    if not wait_for(port, "completed installing const data.", 180):
        raise RuntimeError("data flash install did not complete")
    if not wait_for(port, "swap bank", 180):
        raise RuntimeError("bank swap was not observed")


def verify_app_mqtt(port: serial.Serial, startup_timeout: int, timeout: int, require_pubsub: bool) -> None:
    print("\n[APP] waiting for app startup markers")
    marker = wait_for_any(port, APP_START_MARKERS, startup_timeout, APP_STARTUP_ERROR_MARKERS)
    if marker is None:
        raise RuntimeError("app startup marker was not observed after bootloader bank swap")
    print(f"\n[APP] observed startup marker: {marker}")

    detected: set[str] = set()
    mqtt_reached: set[str] = set()
    missing_credentials: set[str] = set()
    errors: list[str] = []
    cellular_state: dict[str, str] = {}
    last_qisend_at = 0.0
    qisend_errors = 0
    qisend_error_limit = int(os.environ.get("BG96_MQTT_QISEND_ERROR_LIMIT", "30"))
    deadline = time.time() + timeout
    buffer = ""
    while time.time() < deadline:
        chunk = port.read(port.in_waiting or 1)
        if not chunk:
            time.sleep(0.05)
            continue

        text = chunk.decode("utf-8", errors="replace")
        write_serial_text(text)
        buffer += text

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            stripped = line.strip()
            if not stripped:
                continue

            for marker in MQTT_SUCCESS_MARKERS:
                if marker in stripped:
                    detected.add(marker)

            for marker in MQTT_REACHED_MARKERS:
                if marker in stripped:
                    mqtt_reached.add(marker)

            for marker in MQTT_MISSING_CREDENTIAL_MARKERS:
                if marker in stripped:
                    missing_credentials.add(marker)

            for marker in APP_ERROR_MARKERS:
                if marker.lower() in stripped.lower():
                    errors.append(stripped)
                    if marker == "Cellular init failed":
                        raise RuntimeError(f"app reported fatal connectivity error: {stripped}")
                    if require_pubsub:
                        raise RuntimeError(f"app reported MQTT error: {stripped}")

            if "generated AT command: AT+QISEND" in stripped:
                last_qisend_at = time.time()
            elif stripped == "ERROR" and last_qisend_at and time.time() - last_qisend_at < 2.0:
                qisend_errors += 1
                if require_pubsub and qisend_errors >= qisend_error_limit:
                    raise RuntimeError(
                        f"MQTT QISEND returned ERROR {qisend_errors} times without cellular recovery"
                    )
            elif "SEND OK" in stripped:
                qisend_errors = 0
                last_qisend_at = 0.0
            elif (
                "Resetting Cellular Hardware" in stripped
                or "Connected to AccessPoint" in stripped
                or "Established TCP connection" in stripped
            ):
                qisend_errors = 0
                last_qisend_at = 0.0

            if "+CPIN:" in stripped:
                cellular_state["cpin"] = stripped
            if "+CFUN:" in stripped:
                cellular_state["cfun"] = stripped
            if "+CGATT:" in stripped:
                cellular_state["cgatt"] = stripped
            if "Trying access point" in stripped:
                cellular_state["access_point"] = stripped
            if "Remaining retry count" in stripped:
                cellular_state["remaining_retry"] = stripped

        if "Successfully sent QoS" in detected and (
            "Successfully subscribed to topic" in detected or "---------Finish PubSub Demo Task" in detected
        ):
            print("\n[PASS] app MQTT Pub/Sub activity verified")
            return

        if mqtt_reached and missing_credentials and require_pubsub:
            raise RuntimeError(
                "MQTT Pub/Sub verification is required, but credentials are not provisioned in Data Flash"
            )

        if mqtt_reached and missing_credentials:
            print(
                "\n[PASS] app reached MQTT/TLS startup; "
                "Pub/Sub credentials are not provisioned in Data Flash"
            )
            return

    raise RuntimeError(
        "timed out waiting for app MQTT success; "
        f"detected={sorted(detected)} mqtt_reached={sorted(mqtt_reached)} "
        f"missing_credentials={sorted(missing_credentials)} cellular_state={cellular_state} "
        f"errors={errors[-5:]}"
    )


def verify_app_activity_with_reset_retries(
    args: argparse.Namespace,
    port: serial.Serial,
) -> None:
    for attempt in range(args.app_reset_retries + 1):
        try:
            verify_app_mqtt(port, args.app_startup_timeout, args.mqtt_timeout, args.require_mqtt_pubsub)
            return
        except RuntimeError as exc:
            retryable = ("Cellular init failed", "MQTT QISEND returned ERROR")
            if not any(marker in str(exc) for marker in retryable) or attempt >= args.app_reset_retries:
                raise
            print(f"\n[APP] retryable app connectivity error; resetting app and retrying ({attempt + 1}/{args.app_reset_retries}): {exc}")
            port.reset_input_buffer()
            run_rfp(args, ["-sig", "-run"])


def require_file(path: Path | None, label: str) -> Path:
    if path is None:
        raise RuntimeError(f"{label} is required")
    if not path.is_file():
        raise RuntimeError(f"{label} not found: {path}")
    return path


def open_uart(args: argparse.Namespace) -> serial.Serial:
    return serial.Serial(
        port=args.uart_port,
        baudrate=args.baud,
        timeout=0.1,
        write_timeout=10,
        dsrdtr=False,
        rtscts=False,
    )


def wait_app_startup(args: argparse.Namespace, port: serial.Serial) -> None:
    print("\n[APP] waiting for app startup markers")
    marker = wait_for_any(port, APP_START_MARKERS, args.app_startup_timeout, APP_STARTUP_ERROR_MARKERS)
    if marker is None:
        raise RuntimeError("app startup marker was not observed")
    print(f"\n[APP] observed startup marker: {marker}")


def flash_bootloader(args: argparse.Namespace) -> None:
    bootloader_mot = require_file(args.bootloader_mot, "bootloader MOT")
    run_rfp(args, ["-erase-chip"])
    run_rfp(args, ["-p", str(bootloader_mot)])
    print("[BOOTLOADER] bootloader image programmed")


def download_rsu_via_bootloader(args: argparse.Namespace) -> None:
    userprog_rsu = require_file(args.userprog_rsu, "userprog RSU")
    bootloader_mot = require_file(args.bootloader_mot, "bootloader MOT") if args.bootloader_mot else None
    candidates = open_serial_candidates(parse_probe_ports(args.uart_port), args.baud)
    try:
        if bootloader_mot:
            run_rfp(args, ["-p", str(bootloader_mot), "-run"])
        else:
            run_rfp(args, ["-sig", "-run"])
        selected = wait_for_ready_on_any(candidates, args.ready_timeout)
        if selected is None:
            raise RuntimeError(f"bootloader ready message not observed: {READY}")
        close_unselected_candidates(candidates, selected)
        if args.selected_uart_out:
            args.selected_uart_out.parent.mkdir(parents=True, exist_ok=True)
            args.selected_uart_out.write_text(selected.path + "\n", encoding="ascii")
            print(f"[UART] selected UART path written to {args.selected_uart_out}")
        download_rsu(selected.port, userprog_rsu, ready_observed=True)
    finally:
        for candidate in candidates:
            if candidate.port.is_open:
                candidate.port.close()
    print("[BOOTLOADER] userprog RSU downloaded and bank swap observed")


def run_app(args: argparse.Namespace) -> None:
    with open_uart(args) as port:
        port.reset_input_buffer()
        run_rfp(args, ["-sig", "-run"])
        wait_app_startup(args, port)
    print("[APP] startup verified")


def provision_mqtt(args: argparse.Namespace) -> None:
    with open_uart(args) as port:
        port.reset_input_buffer()
        run_rfp(args, ["-sig", "-run"])
        provision_mqtt_credentials(args, port)
    print("[CLI] MQTT credential provisioning job complete")


def provision_fleet(args: argparse.Namespace) -> None:
    with open_uart(args) as port:
        port.reset_input_buffer()
        run_rfp(args, ["-sig", "-run"])
        provision_fleet_credentials(args, port)
    print("[CLI] Fleet credential provisioning job complete")


def reset_app(args: argparse.Namespace) -> None:
    run_rfp(args, ["-sig", "-run"])
    print("[APP] reset issued")


def verify_mqtt(args: argparse.Namespace) -> None:
    with open_uart(args) as port:
        port.reset_input_buffer()
        run_rfp(args, ["-sig", "-run"])
        verify_app_activity_with_reset_retries(args, port)
    print("[PASS] app MQTT communication verified")


def full_integration(args: argparse.Namespace) -> None:
    bootloader_mot = require_file(args.bootloader_mot, "bootloader MOT")
    userprog_rsu = require_file(args.userprog_rsu, "userprog RSU")

    run_rfp(args, ["-erase-chip"])

    candidates = open_serial_candidates(parse_probe_ports(args.uart_port), args.baud)
    try:
        run_rfp(args, ["-p", str(bootloader_mot), "-run"])
        selected = wait_for_ready_on_any(candidates, args.ready_timeout)
        if selected is None:
            raise RuntimeError(f"bootloader ready message not observed: {READY}")
        close_unselected_candidates(candidates, selected)
        port = selected.port
        download_rsu(port, userprog_rsu, ready_observed=True)
        if args.provision_mqtt_credentials:
            provision_mqtt_credentials(args, port)
        verify_app_activity_with_reset_retries(args, port)
    finally:
        for candidate in candidates:
            if candidate.port.is_open:
                candidate.port.close()


def parse_args() -> argparse.Namespace:
    default_mqtt_timeout = int(os.environ.get("BG96_MQTT_TIMEOUT_SECONDS", "900"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=(
            "full",
            "flash-bootloader",
            "download-rsu",
            "run-app",
            "provision-mqtt",
            "provision-fleet",
            "reset-app",
            "verify-mqtt",
        ),
        default="full",
    )
    parser.add_argument("--bootloader-mot", type=Path)
    parser.add_argument("--userprog-rsu", type=Path)
    parser.add_argument("--selected-uart-out", type=Path)
    parser.add_argument("--uart-port", required=True)
    parser.add_argument("--baud", type=int, default=int(os.environ.get("UART_BAUD_RATE", "921600")))
    parser.add_argument("--mqtt-timeout", type=int, default=default_mqtt_timeout)
    parser.add_argument("--app-startup-timeout", type=int,
                        default=int(os.environ.get("BG96_APP_STARTUP_TIMEOUT_SECONDS", str(max(180, default_mqtt_timeout)))))
    parser.add_argument("--ready-timeout", type=int,
                        default=int(os.environ.get("BG96_BOOTLOADER_READY_TIMEOUT_SECONDS", str(DEFAULT_READY_TIMEOUT_SECONDS))))
    parser.add_argument("--require-mqtt-pubsub", action="store_true",
                        default=os.environ.get("BG96_MQTT_REQUIRE_PUBSUB") == "true")
    parser.add_argument("--app-reset-retries", type=int,
                        default=int(os.environ.get("BG96_APP_RESET_RETRIES", "1")))
    parser.add_argument("--provision-mqtt-credentials", action="store_true",
                        default=os.environ.get("BG96_MQTT_PROVISION_CREDENTIALS") == "true")
    parser.add_argument("--provision-cli-timeout", type=float,
                        default=float(os.environ.get("BG96_MQTT_PROVISION_CLI_TIMEOUT_SECONDS", "25")))
    parser.add_argument("--provision-char-delay", type=float,
                        default=float(os.environ.get("BG96_MQTT_PROVISION_CHAR_DELAY_SECONDS", "0.002")))
    parser.add_argument("--provision-line-delay", type=float,
                        default=float(os.environ.get("BG96_MQTT_PROVISION_LINE_DELAY_SECONDS", "0.5")))
    parser.add_argument("--rfp-cli", default=default_rfp_cli())
    parser.add_argument("--rfp-device", default=os.environ.get("RFP_DEVICE", "RX65x"))
    parser.add_argument("--rfp-tool", default=os.environ.get("BG96_BOOTLOADER_E2LITE_SERIAL", os.environ.get("BG96_E2LITE_SERIAL", "OBE110020")))
    parser.add_argument("--rfp-interface", default=os.environ.get("RFP_INTERFACE", "fine"))
    parser.add_argument("--rfp-speed", default=os.environ.get("RFP_SPEED", "500K"))
    parser.add_argument("--rfp-auth-id", default=os.environ.get("RFP_AUTH_ID", "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    actions = {
        "full": full_integration,
        "flash-bootloader": flash_bootloader,
        "download-rsu": download_rsu_via_bootloader,
        "run-app": run_app,
        "provision-mqtt": provision_mqtt,
        "provision-fleet": provision_fleet,
        "reset-app": reset_app,
        "verify-mqtt": verify_mqtt,
    }
    actions[args.action](args)

    print(f"CK-RX65N BG96 action passed: {args.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

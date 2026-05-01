#!/usr/bin/env python3
"""Reset the BG96 app into CLI and provision the OTA code signer certificate."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import serial

from bg96_bootloader_integration import (
    default_rfp_cli,
    enter_cli_mode,
    run_rfp,
    send_cli_command,
    send_cli_pem,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uart-port", required=True)
    parser.add_argument("--baud", type=int, default=int(os.environ.get("UART_BAUD_RATE", "921600")))
    parser.add_argument("--code-signer-cert", required=True, type=Path)
    parser.add_argument("--rfp-cli", default=default_rfp_cli())
    parser.add_argument("--rfp-device", default=os.environ.get("RFP_DEVICE", "RX65x"))
    parser.add_argument("--rfp-tool", default=os.environ.get("BG96_BOOTLOADER_E2LITE_SERIAL", "OBE110020"))
    parser.add_argument("--rfp-interface", default=os.environ.get("RFP_INTERFACE", "fine"))
    parser.add_argument("--rfp-speed", default=os.environ.get("RFP_SPEED", "1500K"))
    parser.add_argument("--rfp-auth-id", default=os.environ.get("RFP_AUTH_ID", "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"))
    parser.add_argument("--provision-cli-timeout", type=float, default=25.0)
    parser.add_argument("--provision-char-delay", type=float, default=0.002)
    parser.add_argument("--provision-line-delay", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.code_signer_cert.is_file():
        raise RuntimeError(f"code signer certificate not found: {args.code_signer_cert}")

    port = serial.Serial(
        port=args.uart_port,
        baudrate=args.baud,
        timeout=0.1,
        write_timeout=10,
        dsrdtr=False,
        rtscts=False,
    )
    try:
        port.reset_input_buffer()
        run_rfp(args, ["-sig", "-run"])
        enter_cli_mode(
            port,
            args.provision_cli_timeout,
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
        )
        send_cli_pem(
            port,
            "codesigncert",
            args.code_signer_cert.read_text(encoding="utf-8"),
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
        )
        send_cli_command(
            port,
            "conf commit",
            char_delay=args.provision_char_delay,
            line_delay=args.provision_line_delay,
            timeout=30.0,
            success_tokens=("Configuration save",),
        )
        print("[OTA] Code signer certificate provisioned; device is parked in CLI mode.")
    finally:
        port.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

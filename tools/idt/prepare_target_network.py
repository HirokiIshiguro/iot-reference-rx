"""Seed target network settings in a restricted source copy from runner inputs.

Only the established board-specific environment variables are accepted. Values
remain in private runtime and firmware; no network or hardware operation occurs.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from .prepare_transport_key import validate_source
    from .targets import get_target
except ImportError:
    from prepare_transport_key import validate_source
    from targets import get_target

INPUTS = {
    "rx671-wifi": {
        "IDT_WIFI_SSID": "RX671_EK_WIFI_SSID",
        "IDT_WIFI_PASSPHRASE": "RX671_EK_WIFI_PASSPHRASE",
    },
    "rx65n-bg96": {
        "IDT_CELLULAR_APN": "AWS_IOT_CELLULAR_APN_CK_RX65N_01",
        "IDT_CELLULAR_APN_USER": "AWS_IOT_CELLULAR_APN_USER_CK_RX65N_01",
        "IDT_CELLULAR_APN_PASSWORD": "AWS_IOT_CELLULAR_APN_PASS_CK_RX65N_01",
        "IDT_CELLULAR_APN_AUTH": "AWS_IOT_CELLULAR_APN_AUTH_CK_RX65N_01",
    },
}


def network_values(target, environ=None):
    env = os.environ if environ is None else environ
    values = {macro: env.get(variable, "") for macro, variable in INPUTS.get(target["id"], {}).items()}
    if target["id"] == "rx671-wifi":
        if not values["IDT_WIFI_SSID"] or not values["IDT_WIFI_PASSPHRASE"]:
            raise RuntimeError("RX671 IDT requires existing RX671_EK_WIFI_SSID and RX671_EK_WIFI_PASSPHRASE runner inputs")
        if len(values["IDT_WIFI_SSID"].encode("utf-8")) > 32:
            raise ValueError("Wi-Fi SSID exceeds 32 bytes")
        phrase = values["IDT_WIFI_PASSPHRASE"]
        if not (8 <= len(phrase.encode("utf-8")) <= 63 or
                (len(phrase) == 64 and all(c in "0123456789abcdefABCDEF" for c in phrase))):
            raise ValueError("Wi-Fi passphrase must be 8–63 bytes or a 64-character hexadecimal PSK")
    elif target["id"] == "rx65n-bg96":
        if not values["IDT_CELLULAR_APN"]:
            raise RuntimeError("RX65N IDT requires existing AWS_IOT_CELLULAR_APN_CK_RX65N_01 runner input")
        values["IDT_CELLULAR_APN_AUTH"] = values["IDT_CELLULAR_APN_AUTH"] or "0"
        if values["IDT_CELLULAR_APN_AUTH"] not in {"0", "1", "2"}:
            raise ValueError("Cellular APN authentication must be 0, 1 or 2")
    if any(any(c in v for c in "\r\n\0") for v in values.values()):
        raise ValueError("Network inputs must be single-line strings")
    return values


def prepare(source_value, target=None):
    target = get_target() if target is None else target
    source = validate_source(source_value)
    runtime = Path(os.environ["IDT_RUNTIME_DIR"]).resolve(strict=True)
    if source.parent not in (runtime, runtime / "source"):
        raise RuntimeError("Refusing network credential injection into original checkout")
    values = network_values(target)
    if not values:
        return
    header = source / "Test/include/idt_network_config.h"
    content = "/* Private runtime only; do not publish source or firmware. */\n"
    content += "#ifndef IDT_NETWORK_CONFIG_H\n#define IDT_NETWORK_CONFIG_H\n"
    content += "".join("#define " + macro + " " + json.dumps(value, ensure_ascii=True) + "\n"
                       for macro, value in values.items())
    content += "#endif\n"
    header.write_text(content, encoding="utf-8")
    os.chmod(header, 0o600)
    print("IDT network inputs prepared for " + target["id"] + "; values omitted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()
    prepare(args.source)

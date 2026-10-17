"""Normalize public RX CI runtime settings without inspecting hardware or secrets."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.idt.targets import get_target

PREFIXES = {"rx72n-ethernet": "RX72N_", "rx65n-bg96": "RX65N_BG96_", "rx671-wifi": "RX671_WIFI_"}
PHYSICAL = frozenset(("UART_PORT", "RFP_TOOL", "RFP_DEVICE", "RFP_INTERFACE",
                      "RFP_SPEED", "RFP_AUTH_ID", "RUNNER_HOSTNAME", "HARDWARE_LOCK_PATH"))


def _definitions(target_id):
    if target_id not in PREFIXES:
        raise ValueError("Unsupported RX CI target")
    target = get_target(target_id)
    prefix = PREFIXES[target_id]
    defaults = {"UART_PORT": target["uart"], "UART_BAUD_RATE": str(target["baud"]),
                "RFP_CLI": "./tools/rfp_cli_locked.sh", "RFP_TOOL": "e2l:" + target["e2lite"],
                "RFP_DEVICE": target["rfp_device"], "RFP_INTERFACE": "fine", "RFP_SPEED": target["rfp_speed"],
                "RFP_AUTH_ID": "F" * 32, "RUNNER_HOSTNAME": target["hostname"],
                "HARDWARE_LOCK_PATH": target["bench_lock"],
                "HARDWARE_LOCK_TIMEOUT_SECONDS": "0" if target_id == "rx65n-bg96" else "3600",
                "FLEET_TEST_TIMEOUT_SECONDS": "600" if target_id == "rx72n-ethernet" else "900"}
    aliases = {"RFP_CLI": (prefix + "LINUX_RFP_CLI",)}
    if target_id == "rx72n-ethernet":
        aliases.update({"UART_PORT": ("RX72N_LINUX_UART_PORT",),
                        "UART_BAUD_RATE": ("RX72N_LINUX_UART_BAUD_RATE",),
                        "RFP_TOOL": ("RX72N_LINUX_RFP_TOOL",), "RFP_SPEED": ("RFP_SPEED",),
                        "RFP_AUTH_ID": ("RFP_AUTH",),
                        "HARDWARE_LOCK_PATH": ("RX72N_RPI1_HARDWARE_LOCK_PATH",),
                        "HARDWARE_LOCK_TIMEOUT_SECONDS": ("RX72N_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS",),
                        "FLEET_TEST_TIMEOUT_SECONDS": ("RX72N_FLEET_TEST_TIMEOUT",)})
    elif target_id == "rx671-wifi":
        aliases.update({"HARDWARE_LOCK_PATH": ("RX671_RPI1_HARDWARE_LOCK_PATH",),
                        "HARDWARE_LOCK_TIMEOUT_SECONDS": ("RX671_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS",)})
    return prefix, defaults, aliases


def _configured(environ, key):
    value = environ.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Invalid public CI setting type for " + key)
    return value if value.strip() else ""


def normalize(target_id, environ):
    """Return only preferred public keys and their reviewed legacy aliases.

    A preferred input may supersede a legacy YAML default. Distinct nondefault
    legacy input is an explicit conflict and must not silently select a bench.
    """
    prefix, defaults, aliases = _definitions(target_id)
    exports = {}
    for suffix, default in defaults.items():
        preferred = prefix + suffix
        legacy_keys = aliases.get(suffix, ())
        current = _configured(environ, preferred)
        legacy = [_configured(environ, key) for key in legacy_keys]
        selected = current or next((value for value in legacy if value), default)
        for value in legacy:
            if value and value != selected and value != default:
                raise ValueError("Conflicting public CI settings for " + preferred)
        if suffix in PHYSICAL and selected != default:
            raise ValueError("Public CI setting differs from the reviewed target: " + preferred)
        if suffix in ("UART_BAUD_RATE", "HARDWARE_LOCK_TIMEOUT_SECONDS", "FLEET_TEST_TIMEOUT_SECONDS"):
            if not re.fullmatch(r"[0-9]+", selected):
                raise ValueError("Invalid public CI integer for " + preferred)
            number = int(selected)
            minimum = 0 if suffix == "HARDWARE_LOCK_TIMEOUT_SECONDS" else 1
            if number < minimum or (suffix == "UART_BAUD_RATE" and number != int(default)):
                raise ValueError("Public CI integer is outside the reviewed policy: " + preferred)
            selected = str(number)
        exports[preferred] = selected
        exports.update({key: selected for key in legacy_keys})
    return exports


def shell_exports(settings):
    return "\n".join("export " + key + "=" + shlex.quote(value) for key, value in sorted(settings.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=tuple(PREFIXES))
    arguments = parser.parse_args(argv)
    try:
        exports = normalize(arguments.target, os.environ)
    except Exception:
        print("RX CI settings validation failed", file=sys.stderr)
        return 1
    print(shell_exports(exports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

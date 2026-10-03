"""Reviewed board identities shared by the builder, host, and remote helpers.

Select an identity, never an arbitrary UART or programmer. Host configuration
cannot override a board identity. Remote bootstraps inject the same manifest.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

DEFAULT_TARGET = "rx72n-ethernet"
_MANIFEST = None


def load_manifest():
    manifest = _MANIFEST
    if manifest is None:
        manifest = json.loads(Path(__file__).with_name("targets.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("targets"), dict):
        raise ValueError("Unsupported IDT target manifest")
    return manifest


def target_ids():
    return tuple(load_manifest()["targets"])


def get_target(target_id=None):
    selected = os.environ.get("IDT_TARGET", DEFAULT_TARGET) if target_id is None else target_id
    targets = load_manifest()["targets"]
    if not isinstance(selected, str) or selected not in targets:
        raise ValueError("Unknown IDT target: " + str(selected))
    target = copy.deepcopy(targets[selected])
    if target.get("id") != selected:
        raise ValueError("IDT target identity does not match its manifest key")
    return target


def target_fingerprint(target):
    return hashlib.sha256(json.dumps(target, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def hardware_end_state_status(target):
    """Use the existing CI reset/quiet observation, without claiming pin voltage.

    Every touched run must complete the guarded reset command and a fresh UART
    quiet interval. Failure retains ownership; interrupted privileged commands
    remain subject to the independent persistent unsafe sentinel.
    """
    return {"target_id": target["id"], "supported": True,
            "status": "reset_command_and_uart_quiet", "physical_reset_hold": "unverified",
            "required_observations": ["reset_command_exit_zero", "fresh_uart_quiet_1s"],
            "reason": "Existing RX72N CI end-state procedure; RESET pin voltage is not measured"}



def device_template(target, scope, public_key_path=None):
    """Native feature flags describe the actual selected board's connection."""
    features = [{"name": "Wifi", "value": "Yes" if target["connectivity"] == "wifi" else "No"},
                {"name": "Cellular", "value": "Yes" if target["connectivity"] == "cellular" else "No"},
                {"name": "BLE", "value": "No"}, {"name": "PKCS11", "value": "ECC"},
                {"name": "KeyProvisioning", "value": "Onboard" if scope == "ota-mqtt" else "Import"},
                {"name": "OTA", "value": "Yes", "configs": [{"name": "OTADataPlaneProtocol", "value": "MQTT"}]}]
    secure = {"preProvisioned": "No", "pkcs11JITPCodeVerifyRootCertSupport": "No"}
    if public_key_path is not None:
        secure["publicKeyAsciiHexFilePath"] = public_key_path
    device = {"id": target["id"] + "-" + target["ssh_alias"], "secureElementConfig": secure}
    if scope == "preflight":
        device["connectivity"] = {"protocol": "uart", "serialPort": "COM0"}
    return [{"id": target["id"] + ("-host-preflight" if scope == "preflight" else "-development"),
             "sku": target["sku"], "features": features, "devices": [device]}]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=target_ids(), default=None)
    parser.add_argument("--field")
    args = parser.parse_args()
    target = get_target(args.target)
    print(str(target[args.field]) if args.field else json.dumps(target, sort_keys=True))

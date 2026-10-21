"""Public provenance for the isolated historical RX671 normal-MQTT build.

Never read generated private headers, dump firmware bytes, or hash secret values.
Run only from the new CI delivery checkout; it does not invoke native tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

OLD = "666d97f64eecc2451ec3b54ee101b5b53a603c51"
BASE = "5d4b4a62e6e1def5e9bcedd26ff5502fb32caf0a"
PROJECT = "Projects/aws_wifi_rx671_ek/e2studio_ccrx"
WHD = "Projects/aws_wifi_rx671_ek/external/wifi-host-driver"
PATCH = "Projects/aws_wifi_rx671_ek/external/patches/whd-v1.70.0-ccrx-portability.patch"
PATCH_SHA = "d3274f3f4d6c571d2eb410fbada0e7b2a9ef5346aebb7f2b0772b80633d3cdad"


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if result.returncode:
        raise RuntimeError("Required Git provenance check failed; raw output suppressed")
    return result.stdout


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pins(root: Path) -> dict[str, str]:
    result = {}
    for entry in git(root, "ls-tree", "-rz", "-r", OLD).split(b"\0"):
        if entry.startswith(b"160000 "):
            info, path = entry.split(b"\t", 1)
            result[path.decode()] = info.split()[2].decode()
    if len(result) != 31:
        raise RuntimeError("Historical source must contain exactly 31 top-level gitlinks")
    return result


def public_inputs(root: Path) -> dict:
    # Git applies the checked-in EOL attributes when comparing tracked files.
    # Historical C/H files normally check out CRLF; raw bytes need not equal
    # canonical blob bytes. No raw-working-byte equivalence is claimed.
    git(root, "diff", "--exit-code", "--", PROJECT)
    git(root, "diff", "--cached", "--exit-code", "--", PROJECT)
    listing = git(root, "ls-tree", "-rz", "-r", OLD, "--", PROJECT)
    if not listing:
        raise RuntimeError("Historical project tree is missing")
    cproject = git(root, "show", f"{OLD}:{PROJECT}/.cproject")
    return {
        "source_equivalence": "clean-tracked-Git-diff-with-normal-checkout-filters",
        "working_bytes_equal_git_blob_for_all_project_files": "not-claimed",
        "product_project_git_tree_oid": git(root, "rev-parse", f"{OLD}:{PROJECT}").decode().strip(),
        "product_project_sha256": sha(listing),
        "product_project_digest_basis": "sha256-of-git-ls-tree-rz-r-fixed-source-project-output",
        "cproject_sha256": sha(cproject),
        "cproject_digest_basis": "canonical-Git-blob",
    }

def verify_source(root: Path, post: bool) -> dict:
    if git(root, "rev-parse", "HEAD").decode().strip() != OLD:
        raise RuntimeError("Historical worktree HEAD differs from fixed runtime source")
    expected_pins = pins(root)
    if git(root, "diff", "--name-only", "--ignore-submodules=all").strip():
        raise RuntimeError("Historical parent tracked files changed")
    if git(root, "diff", "--cached", "--name-only").strip():
        raise RuntimeError("Historical parent has staged changes")
    for path, expected in expected_pins.items():
        module = root / path
        if git(module, "rev-parse", "HEAD").decode().strip() != expected:
            raise RuntimeError("Historical submodule pin differs")
        changed = git(module, "diff", "--name-only").decode().splitlines()
        if git(module, "diff", "--cached", "--name-only").strip():
            raise RuntimeError("Historical submodule has staged changes")
        if post and path == WHD:
            patch = root / PATCH
            if sha(patch.read_bytes()) != PATCH_SHA:
                raise RuntimeError("Historical portability patch differs")
            git(module, "apply", "--ignore-space-change", "--ignore-whitespace", "--reverse", "--check", str(patch))
            expected_paths = set(re.findall(r"^diff --git a/(.+?) b/", patch.read_text(), re.M))
            if not changed or set(changed) != expected_paths:
                raise RuntimeError("WHD changes are not exactly the historical helper patch paths")
        elif changed:
            raise RuntimeError("Historical submodule contains unexpected tracked changes")
    return {"submodule_pins": expected_pins, **public_inputs(root),
            "historical_whd_portability_patch_sha256": PATCH_SHA,
            "historical_whd_patch_check": "original-helper-reverse-check-and-exact-changed-path-set"}

def verify_profile(root: Path) -> dict:
    # The original helper has restored .cproject by now. Inspect only generated
    # compiler commands, never included private configuration headers.
    command_file = root / PROJECT / "HardwareDebug/compile_commands.json"
    commands = json.loads(command_file.read_text(encoding="utf-8-sig"))
    observed = set()
    for item in commands:
        command = item.get("command", "") or " ".join(item.get("arguments", []))
        observed.update(re.findall(r"-define=([^\s]+)", command))
    required = {"WHD_JOIN_USE_LOCAL_CONFIG", "AWS_IOT_USE_LOCAL_CONFIG", "PLATFORM_WLAN_ALLOW_BUS_TO_SLEEP_DELAY_MS=600000"}
    if not required.issubset(observed):
        raise RuntimeError("Normal MQTT compiler configuration is incomplete")
    prohibited = ("RX671_OTA_RUNTIME_ENABLE", "RX671_OTA_PROVISIONER_ENABLE", "RX671_FLEET_USE_LOCAL_CONFIG",
                  "RX671_FLEET_PROVISIONING_ENABLE", "WHD_JOIN_USE_KVS", "TCP_THROUGHPUT_USE_LOCAL_CONFIG",
                  "TCP_THROUGHPUT_ENABLE", "AWS_IOT_USE_TSIP_ENTROPY", "AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3")
    if any(define.split("=", 1)[0] in prohibited for define in observed):
        raise RuntimeError("Non-normal or historical-profile-changing compiler define detected")
    return {"ota_runtime": False, "ota_provisioner": False, "fleet": False, "wifi_kvs": False,
            "throughput": False, "tsip_entropy": False}


def srecord_ranges(path: Path) -> dict:
    addresses = set()
    for line in path.read_text(encoding="ascii").splitlines():
        line = line.strip()
        if not line:
            continue
        if not re.fullmatch(r"S[0-9][0-9A-Fa-f]+", line):
            raise RuntimeError("Malformed S-record")
        record = bytes.fromhex(line[2:])
        if not record or record[0] != len(record) - 1 or sum(record) & 255 != 255:
            raise RuntimeError("Invalid S-record checksum or length")
        n = {"1": 2, "2": 3, "3": 4}.get(line[1])
        if n:
            start = int.from_bytes(record[1:1+n], "big")
            addresses.update(range(start, start + len(record) - n - 2))
    if not addresses:
        raise RuntimeError("Empty S-record data")
    cf = [a for a in addresses if 0xFFE00000 <= a <= 0xFFFFFFFF]
    options = [a for a in addresses if 0xFE7F5D00 <= a <= 0xFE7F5D7F or 0xFE7F7D70 <= a <= 0xFE7F7D9F]
    if len(cf) + len(options) != len(addresses) or not cf:
        raise RuntimeError("Historical image contains data outside code-flash/option ranges")
    def ranges(values):
        output = []
        for a in sorted(values):
            if output and output[-1][1] + 1 == a:
                output[-1][1] = a
            else:
                output.append([a, a])
        return [{"start": f"0x{a:08X}", "end": f"0x{b:08X}", "byte_count": b-a+1} for a, b in output]
    return {"code_flash": ranges(cf), "options": ranges(options), "data_flash_bytes": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("pre", "post", "restore"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    delivery = os.environ["CI_COMMIT_SHA"]
    if not re.fullmatch(r"[0-9a-f]{40}", delivery):
        raise RuntimeError("Invalid CI delivery source")
    identity = {"delivery_source_sha": delivery, "pipeline_id": int(os.environ["CI_PIPELINE_ID"]),
                "producer_job_id": int(os.environ["CI_JOB_ID"])}
    if args.mode == "restore":
        # Prove the CI delivery commit changed only CI/tooling, then attach a
        # small receipt without modifying any of the ten normal bundle files.
        changed = git(args.source, "diff", "--name-only", BASE, delivery).decode().splitlines()
        if any(p != ".gitlab-ci.yml" and not p.startswith("tools/ci/") for p in changed):
            raise RuntimeError("Control delivery changes product inputs beyond reviewed CI/tool paths")
        manifest = args.output / "normal_install_manifest.json"
        data = json.loads(manifest.read_text())
        if data.get("source_sha") != delivery:
            raise RuntimeError("Restore normal manifest delivery source differs")
        data = {"schema_version": 1, "profile": "rx671-known-good-restore-input-v1", **identity,
                "product_base_source_sha": BASE, "normal_manifest_sha256": sha(manifest.read_bytes())}
        target = args.output / "restore_producer_manifest.json"
    else:
        data = verify_source(args.source, args.mode == "post")
        if args.mode == "post":
            flags = verify_profile(args.source)
            mot = args.source / PROJECT / "HardwareDebug/aws_wifi_rx671_ek.mot"
            data.update({"schema_version": 1, "profile": "rx671-known-good-control-input-v1", **identity,
                         "product_source_sha": OLD, "target_id": "rx671-wifi",
                         "artifact_file": "aws_wifi_rx671_ek.mot", "artifact_sha256": sha(mot.read_bytes()),
                         "profile_flags": flags, "embedded_credentials": True,
                         "build_mode": "normal-mqtt", "e2studio_timeout_seconds": 180,
                         "historical_private_variable_equality": "not-claimed", "mot_ranges": srecord_ranges(mot)})
        target = args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise RuntimeError("Provenance output already exists")
    target.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("RX671 known-good provenance check failed; private inputs and raw output suppressed")

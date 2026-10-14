#!/usr/bin/env python3
"""Build a standalone dual-bank public signer maintenance application."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping

try:
    from .idt.targets import get_target, target_fingerprint
    from .build_rx671_fwup_v2_rsu import _decode_srecord
except ImportError:
    from idt.targets import get_target, target_fingerprint
    from build_rx671_fwup_v2_rsu import _decode_srecord


PROFILE = "rx-dual-public-signer-provisioner-v1"
BUILD_HELPERS = {
    "rx72n-ethernet": "build_headless_rx72n.ps1",
    "rx65n-bg96": "build_headless_rx65n_bg96.ps1",
    "rx671-wifi": "build_headless_rx671_wifi.ps1",
}
CODE_FLASH_START = {"rx72n-ethernet": 0xFFE00000, "rx65n-bg96": 0xFFF00000, "rx671-wifi": 0xFFF00000}
LOCAL_HEADERS = ("src/whd_join_config_local.h", "src/frtos_config/aws_iot_config_local.h",
                 "src/frtos_config/rx671_fleet_config_local.h", "src/frtos_config/tcp_throughput_config_local.h")
BLANK_HEADERS = {
    "aws_clientcredential.h": """/* Product maintenance build: no embedded client or Wi-Fi credentials. */
#ifndef __AWS_CLIENTCREDENTIAL__H__
#define __AWS_CLIENTCREDENTIAL__H__
#define clientcredentialMQTT_BROKER_ENDPOINT ""
#define clientcredentialIOT_THING_NAME ""
#define clientcredentialMQTT_BROKER_PORT 8883
#define clientcredentialGREENGRASS_DISCOVERY_PORT 8445
#define clientcredentialWIFI_SSID ""
#define clientcredentialWIFI_PASSWORD ""
#define clientcredentialWIFI_SECURITY 0
#endif
""",
    "aws_clientcredential_keys.h": """/* Product maintenance build: no embedded client/claim credential material. */
#ifndef AWS_CLIENT_CREDENTIAL_KEYS_H
#define AWS_CLIENT_CREDENTIAL_KEYS_H
#define keyCLIENT_CERTIFICATE_PEM ""
#define keyJITR_DEVICE_CERTIFICATE_AUTHORITY_PEM ""
#define keyCLIENT_PRIVATE_KEY_PEM ""
#endif
""",
}
FORBIDDEN_DEFINES = ("WHD_JOIN_CONFIG_USE_LOCAL", "WHD_JOIN_USE_LOCAL_CONFIG", "AWS_IOT_USE_LOCAL_CONFIG",
                     "RX671_FLEET_USE_LOCAL_CONFIG", "ENABLE_IDT_TRANSPORT_TEST", "ENABLE_IDT_CLOUD_DEMO",
                     "ENABLE_IDT_PKCS11_TEST", "ENABLE_IDT_OTAPAL_TEST", "OTA_E2E_TEST_ENABLED")


def isolated_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Exclude injection/overrides, retaining legitimate compiler/license paths."""
    return {key: value for key, value in source.items() if not (
        key.upper().startswith(("AWS_IOT_", "RX671_EK_WIFI_", "RX671_EK_AWS_", "IDT_", "LANBENCH_")) or
        re.search(r"(?:CLIENT_CERT|PRIVATE_KEY|PRIVKEY|CLAIM|PASSPHRASE|WIFI_PASSWORD|SIGNING_KEY)", key.upper()) or
        key.upper() in {"RX72N_TLS_BACKEND", "RX72N_REQUIRE_TLS_VERSION", "RX65N_BG96_TLS_BACKEND",
                        "RX65N_BG96_REQUIRE_TLS_VERSION", "CPATH", "C_INCLUDE_PATH", "CFLAGS", "CPPFLAGS",
                        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"})}


def _ordinary_file(path: Path, repo: Path, required=True) -> None:
    ancestors = [path, *path.parents]
    if any(item.is_symlink() for item in ancestors if item != repo.parent) or not path.resolve().is_relative_to(repo.resolve()):
        raise RuntimeError("Maintenance input must stay inside the source repository")
    if required and not path.is_file():
        raise RuntimeError("Missing maintenance build input: " + path.name)


class CredentialIsolation:
    """Preserve source bytes/absence while exposing only reviewed empty inputs."""
    def __init__(self, repo: Path, project: Path):
        self.repo, self.project = repo, project
        self.snapshots: dict[Path, bytes | None] = {}
        self.effective: dict[Path, bytes] = {}
        self.applied: set[Path] = set()

    def __enter__(self):
        planned = {self.repo / "Demos/include" / name: body.encode("utf-8")
                   for name, body in BLANK_HEADERS.items()}
        for name, body in BLANK_HEADERS.items():
            path = self.project / "src/frtos_config" / name
            if path.exists():
                planned[path] = body.encode("utf-8")
        planned.update({self.project / relative: None for relative in LOCAL_HEADERS})
        # Validate and snapshot every input before making the first edit.
        for path in planned:
            _ordinary_file(path, self.repo, required=False)
            self.snapshots[path] = path.read_bytes() if path.exists() else None
        try:
            for path, content in planned.items():
                self.applied.add(path)
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    self.effective[path] = content
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def validate(self) -> None:
        for path, expected in self.effective.items():
            _ordinary_file(path, self.repo)
            if path.read_bytes() != expected:
                raise RuntimeError("Credential isolation changed during build")
        if any((self.project / relative).exists() for relative in LOCAL_HEADERS):
            raise RuntimeError("A local credential input reappeared during maintenance build")

    def __exit__(self, *_):
        conflicts = []
        for path, original in self.snapshots.items():
            if path not in self.applied:
                continue
            _ordinary_file(path, self.repo, required=False)
            current = path.read_bytes() if path.is_file() else None
            expected = self.effective.get(path)
            if current != expected and current != original:
                conflicts.append((path, current))
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        if conflicts:
            private = Path(tempfile.mkdtemp(prefix="rx-signer-source-conflicts-"))
            for number, (path, content) in enumerate(conflicts):
                if content is not None:
                    saved = private / f"{number}-{path.name}"
                    saved.write_bytes(content)
                    saved.chmod(0o600)
            raise RuntimeError("Unexpected build-time source changes preserved in private temporary storage: " + str(private))


def make_profile(text: str, source_sha: str = "0" * 40) -> str:
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise ValueError("Maintenance profile requires an exact source SHA")
    if 'modes="bank.single"' in text or text.count('modes="bank.dual"') != 1:
        raise ValueError("Maintenance profile requires a canonical dual-bank project")
    if text.count('value="PFRAM2=RPFRAM2"') != 1:
        raise ValueError("Maintenance profile requires the Flash RAM mapping")
    values = re.findall(r'value="([^"]*EXCEPTVECT/[^"]*RESETVECT/[^"]*)"', text)
    if len(values) != 1:
        raise ValueError("Maintenance profile requires one application vector layout")
    start = values[0]
    standalone = re.sub(r"EXCEPTVECT/0?[Ff]{3}[Bb][Ff]{2}80", "EXCEPTVECT/0FFFFFF80", start)
    standalone = re.sub(r"RESETVECT/0?[Ff]{3}[Bb][Ff]{3}[Cc]", "RESETVECT/0FFFFFFFC", standalone)
    if standalone == start or "RESETVECT/0FFFFFFFC" not in standalone:
        raise ValueError("Unsupported application vector layout")
    text = text.replace('value="' + start + '"', 'value="' + standalone + '"', 1)
    tree = ET.fromstring(text)
    options = [item for item in tree.iter("option")
               if item.get("superClass", "").endswith(".compiler.option.userBefore")]
    if len(options) != 1:
        raise ValueError("Expected one compiler userBefore option")
    if "PUBLIC_SIGNER_PROVISIONER_ENABLE" in text or "PUBLIC_SIGNER_SOURCE_SHA" in text:
        raise ValueError("A maintenance define must not persist in the normal project")
    for option in options[0].iter("listOptionValue"):
        value = option.get("value", "")
        for name in FORBIDDEN_DEFINES:
            if re.search(r"(?:^|[=,\s])" + name + r"(?:=1|(?=[,\s]|$))", value):
                raise ValueError("Maintenance input contains an active injection/test override")
    for define in (
        "PUBLIC_SIGNER_PROVISIONER_ENABLE=1",
        "PUBLIC_SIGNER_SOURCE_SHA=" + source_sha,
        "RX671_OTA_RUNTIME_ENABLE=0",
        "WHD_BRINGUP_ENABLE=0", "WHD_JOIN_ENABLE=0", "AWS_IOT_MQTT_ENABLE=0",
        "RX671_FLEET_PROVISIONING_ENABLE=0", "ENABLE_FLEET_PROVISIONING_DEMO=0",
        "ENABLE_OTA_UPDATE_DEMO=0",
        "LFS_NO_DEBUG", "LFS_NO_WARN", "LFS_NO_ERROR",
        "LIBRARY_LOG_LEVEL=LOG_NONE",
    ):
        ET.SubElement(options[0], "listOptionValue",
                      {"builtIn": "false", "value": "-define=" + define})
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(tree, encoding="unicode")


@contextmanager
def temporary_profile(project: Path, source_sha: str = "0" * 40):
    path = project / ".cproject"
    original = path.read_bytes()
    try:
        path.write_text(make_profile(original.decode("utf-8"), source_sha), encoding="utf-8")
        yield
    finally:
        path.write_bytes(original)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_image(path: Path, target_id: str, source_sha: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise RuntimeError("Invalid maintenance source identity")
    memory = {}
    ranges = ((CODE_FLASH_START[target_id], 0xFFFFFFFF), (0xFE7F5D00, 0xFE7F5D7F),
              (0xFE7F7D70, 0xFE7F7D9F))
    for number, line in enumerate(path.read_bytes().decode("ascii").splitlines(), 1):
        if not line.strip():
            continue
        kind, address, data = _decode_srecord(line.strip(), number)
        if kind not in {"S1", "S2", "S3"}:
            continue
        if not data or not any(low <= address <= address + len(data)-1 <= high for low, high in ranges):
            raise RuntimeError("Maintenance MOT writes outside reviewed Code Flash/option ranges")
        for offset, value in enumerate(data):
            position = address + offset
            if position in memory and memory[position] != value:
                raise RuntimeError("Conflicting maintenance MOT data")
            memory[position] = value
    def field(start):
        try:
            return bytes(memory[index] for index in range(start, start+4))
        except KeyError as error:
            raise RuntimeError("Maintenance MOT is missing required vector/option data") from error
    if field(0xFE7F5D00) != bytes.fromhex("8FFFFFFF") or field(0xFE7F5D20) != bytes.fromhex("FFFFFFFF"):
        raise RuntimeError("Maintenance MOT must use dual/little-endian and initial bank0")
    vector = int.from_bytes(field(0xFFFFFFFC), "little")
    if not CODE_FLASH_START[target_id]+0x300 <= vector <= 0xFFFBFFFF or vector not in memory:
        raise RuntimeError("Maintenance reset vector is outside its loaded application")
    marker = b"PUBLIC_SIGNER_PROVISIONER source_sha=" + source_sha.encode("ascii") + b"\r\n"
    runs, current, previous = [], bytearray(), None
    for address in sorted(memory):
        if previous is not None and address != previous+1:
            runs.append(bytes(current)); current.clear()
        current.append(memory[address]); previous = address
    runs.append(bytes(current))
    if not any(marker in data for data in runs):
        raise RuntimeError("Maintenance image has no matching compiled source identity")
    if any(re.search(br"-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----", data) for data in runs):
        raise RuntimeError("Private credential material detected in maintenance image")
    return {"reset_vector": f"0x{vector:08X}", "mde": "0xFFFFFF8F", "initial_bank": 0,
            "compiled_source_identity_verified": True, "code_flash_and_options_only": True}


def validate_effective_commands(project: Path, source_sha: str, log_path: Path) -> dict:
    directory = project / "HardwareDebug"
    candidates = [log_path, *directory.rglob("*.sub"), *directory.rglob("*.tmp"), *directory.rglob("subdir.mk")]
    content = "\n".join(path.read_bytes().decode("utf-8", errors="replace") for path in candidates if path.is_file())
    if not all(define in content for define in ("PUBLIC_SIGNER_PROVISIONER_ENABLE=1", "PUBLIC_SIGNER_SOURCE_SHA="+source_sha)):
        raise RuntimeError("Missing effective maintenance compiler defines")
    if not re.search(r"-start=[^\r\n]*EXCEPTVECT/0?FFFFFF80[^\r\n]*RESETVECT/0?FFFFFFFC", content, re.I):
        raise RuntimeError("Missing effective standalone hardware vector layout")
    if "PFRAM2=RPFRAM2" not in content:
        raise RuntimeError("Missing effective Flash RAM mapping")
    if any(re.search(r"-define[^\r\n]*\b"+name+r"(?:=1\b|(?=[,\s]|$))", content)
           for name in FORBIDDEN_DEFINES):
        raise RuntimeError("Effective build contains an injection/test override")
    return {"maintenance_compiler_defines_verified": True, "standalone_vectors_verified": True,
            "flash_ram_mapping_verified": True}


def build(repo: Path, target_id: str, output: Path, workspace: Path, python: str) -> dict:
    target = get_target(target_id)
    project = repo / target["application_project"]
    _ordinary_file(project / ".project", repo)
    _ordinary_file(project / ".cproject", repo)
    name = ET.parse(project / ".project").getroot().findtext("name")
    if not name or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Invalid application project name")
    output.mkdir(parents=True, exist_ok=False)
    command = [
        "pwsh", "-NoProfile", "-File", str(repo / "tools" / BUILD_HELPERS[target_id]),
        "-ProjectRoot", str(repo), "-Workspace", str(workspace),
        "-LogFile", str(output / "build-private.log"),
    ]
    if target_id != "rx671-wifi":
        command += ["-TlsBackend", "software", "-RequireTlsVersion", ""]
    if target_id == "rx671-wifi":
        command += ["-SkipWifiConfig", "-SkipAwsIotConfig", "-Python", python]
    source_dirty = bool(subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"], text=True
    ).strip())
    source_sha = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise RuntimeError("Invalid source revision")
    environment = isolated_environment(os.environ)
    started = time.time_ns()
    with CredentialIsolation(repo, project) as isolation, temporary_profile(project, source_sha):
        effective = {path.relative_to(repo).as_posix(): hashlib.sha256(body).hexdigest()
                     for path, body in isolation.effective.items()}
        effective[(project / ".cproject").relative_to(repo).as_posix()] = sha256(project / ".cproject")
        result = subprocess.run(command, cwd=repo, capture_output=True, timeout=1800, env=environment)
        (output / "launcher-private.log").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Public signer provisioner build failed; inspect private build logs")
        isolation.validate()
        commands = validate_effective_commands(project, source_sha, output / "build-private.log")
        artifacts = {}
        for suffix in ("mot", "map", "abs"):
            source = project / "HardwareDebug" / (name + "." + suffix)
            if not source.is_file():
                raise RuntimeError("Missing provisioner artifact: " + suffix)
            if source.stat().st_mtime_ns < started:
                raise RuntimeError("Maintenance build returned a stale artifact: " + suffix)
            if suffix in {"mot", "abs"} and re.search(br"-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----", source.read_bytes()):
                raise RuntimeError("Private credential material detected in maintenance artifact")
            if suffix == "mot":
                image = validate_image(source, target_id, source_sha)
            destination = output / source.name
            destination.write_bytes(source.read_bytes())
            artifacts[destination.name] = sha256(destination)
    current_source = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if current_source != source_sha:
        raise RuntimeError("Source revision changed during maintenance build")
    manifest = {
        "schema_version": 1,
        "profile": PROFILE,
        "target_id": target_id,
        "target_sha256": target_fingerprint(target),
        "tls_backend": "software",
        "cli_scope": "public_signer_only",
        "source_sha": source_sha,
        "source_tree_dirty": source_dirty,
        "formal": not source_dirty,
        "bank_mode": "bank.dual",
        "reset_vector_kind": "standalone_hardware_vector",
        "credential_injection_requested": False,
        "credentials_embedded": False,
        "credential_verification": {"client_and_wifi_headers_empty": True, "local_overrides_absent": True,
                                    "injection_environment_removed": True, "private_pem_markers_absent": True,
                                    "scope": "embedded_client_claim_private_and_wifi_credentials"},
        "effective_input_sha256": effective,
        "effective_command_validation": commands,
        "image_validation": image,
        "sha256": artifacts,
    }
    (output / "provisioner-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--target", choices=tuple(BUILD_HELPERS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--python", default="python")
    args = parser.parse_args()
    manifest = build(args.repo_root.resolve(), args.target, args.output.resolve(),
                     args.workspace.resolve(), args.python)
    print(json.dumps({"profile": manifest["profile"], "target_id": manifest["target_id"],
                      "source_sha": manifest["source_sha"], "bank_mode": manifest["bank_mode"]}))


if __name__ == "__main__":
    main()

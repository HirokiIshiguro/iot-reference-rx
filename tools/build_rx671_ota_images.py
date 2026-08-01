#!/usr/bin/env python3
"""Build traceable RX671 dual-bank OTA baseline and candidate artifacts.

The checked-in RX671 Wi-Fi project intentionally remains a normal linear-mode
runtime image.  This helper applies the OTA linker/BSP/FWUP settings only while
building each image, records the effective inputs, and restores every touched
source file byte-for-byte even when a build fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


PROFILE_NAME = "rx671-dual-bank-ota-v1"
PROVISIONER_PROFILE_NAME = "rx671-bank-single-ota-provisioner-v1"
PROJECT_RELATIVE = Path("Projects/aws_wifi_rx671_ek/e2studio_ccrx")
BOOTLOADER_PROJECT_RELATIVE = Path("Projects/boot_loader_rx671_ek/e2studio_ccrx")
BOOTLOADER_SUBMODULE_RELATIVE = (
    BOOTLOADER_PROJECT_RELATIVE / "lib/rx_bootloader"
)
LAYOUT_CONTRACT_NAME = "ota-layout-contract.json"
PROVENANCE_MANIFEST_NAME = "ota-layout-provenance.json"
REPORT_NAME = "ota-layout-report.json"
SIGNER_CERTIFICATE_NAME = "rx671-ota-signer.crt.pem"
SIGNER_PUBLIC_KEY_NAME = "rx671-ota-signer.pub.pem"
ARTIFACT_BASENAME = "aws_wifi_rx671_ek"
OTA_TRANSFER_PAYLOAD_NAME = f"{ARTIFACT_BASENAME}.ota.bin"
OTA_TRANSFER_SIGNATURE_NAME = f"{ARTIFACT_BASENAME}.ota-signature.der"
RSU_HEADER_SIZE = 0x200
RSU_RAW_SIGNATURE_OFFSET = 0x2C
RSU_RAW_SIGNATURE_SIZE = 64
LOCAL_JOIN_CONFIG_RELATIVE = Path("src/whd_join_config_local.h")
WHD_SUBMODULE_RELATIVE = Path(
    "Projects/aws_wifi_rx671_ek/external/wifi-host-driver"
)
WHD_PATCH_RELATIVE = Path(
    "Projects/aws_wifi_rx671_ek/external/patches/"
    "whd-v1.70.0-ccrx-portability.patch"
)
WIFI_CREDENTIAL_ENVIRONMENT_VARIABLES = (
    "RX671_EK_WIFI_SSID",
    "RX671_EK_WIFI_PASSPHRASE",
    "RX671_EK_WIFI_PASSWORD",
)
FORMAL_INPUT_SUBMODULES = (
    Path("Middleware/3rdparty/littlefs"),
    Path("Middleware/3rdparty/mbedtls"),
    Path("Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk"),
    Path("Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk"),
    Path("Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c"),
    Path("Middleware/FreeRTOS/FreeRTOS-Kernel"),
    Path("Middleware/FreeRTOS/FreeRTOS-Plus-TCP"),
    Path("Middleware/FreeRTOS/backoffAlgorithm"),
    Path("Middleware/FreeRTOS/coreJSON"),
    Path("Middleware/FreeRTOS/coreMQTT"),
    Path("Middleware/FreeRTOS/coreMQTT-Agent"),
    Path("Middleware/FreeRTOS/corePKCS11"),
    Path("Projects/aws_wifi_rx671_ek/external/TraceRecorderSource"),
    Path(
        "Projects/aws_wifi_rx671_ek/external/type1yn-blobs/"
        "sources/cyw-fmac-nvram"
    ),
    Path(
        "Projects/aws_wifi_rx671_ek/external/type1yn-blobs/"
        "sources/firmware-wifi-host-driver"
    ),
    Path(
        "Projects/aws_wifi_rx671_ek/external/type1yn-blobs/"
        "sources/wifi-resources"
    ),
    Path("Projects/aws_wifi_rx671_ek/external/wifi-host-driver"),
    BOOTLOADER_SUBMODULE_RELATIVE,
)

PROFILE_PATHS = (
    Path(".cproject"),
    Path("src/frtos_config/r_fwup_config.h"),
    Path("src/smc_gen/r_config/r_bsp_config.h"),
    Path("src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h"),
)
PROVENANCE_PROJECT_PATHS = (
    Path(".cproject"),
    Path(LAYOUT_CONTRACT_NAME),
    Path("src/frtos_config/r_fwup_config.h"),
    Path("src/frtos_config/rm_littlefs_flash_config.h"),
    Path("src/smc_gen/r_config/r_bsp_config.h"),
    Path("src/sdio_host.c"),
    Path("src/whd_port/whd_port_resource.c"),
)
BOOTLOADER_PROVENANCE_PATHS = (
    BOOTLOADER_PROJECT_RELATIVE / ".cproject",
    BOOTLOADER_PROJECT_RELATIVE / "src/rx671.h",
    BOOTLOADER_PROJECT_RELATIVE / "src/rx_bootloader_config.h",
    BOOTLOADER_PROJECT_RELATIVE / "src/smc_gen/r_config/r_bsp_config.h",
    BOOTLOADER_SUBMODULE_RELATIVE / "config/rx671.h",
    BOOTLOADER_PROJECT_RELATIVE / "HardwareDebug/boot_loader_rx671_ek.map",
    BOOTLOADER_PROJECT_RELATIVE / "HardwareDebug/boot_loader_rx671_ek.mot",
)
WHD_BLOB_PATHS = (
    Path("Projects/aws_wifi_rx671_ek/external/type1yn-blobs/staging/43439A0.bin"),
    Path("Projects/aws_wifi_rx671_ek/external/type1yn-blobs/staging/nvram_1yn.bin"),
    Path("Projects/aws_wifi_rx671_ek/external/type1yn-blobs/staging/43439A0.clm_blob"),
)

NORMAL_START_VALUE = (
    "SU,SI,B_1,R_1,B_2,R_2,B,R,B_8,R_8/04,"
    "PResetPRG,C_1,C_2,C,C_8,C$*,D*,W*,L,P/0FFE00000,"
    "TYPE1YN_FW_BLOB/0FFF00000,TYPE1YN_NVRAM_BLOB/0FFF80000,"
    "TYPE1YN_CLM_BLOB/0FFF90000,EXCEPTVECT/0FFFFFF80,"
    "RESETVECT/0FFFFFFFC"
)
OTA_START_VALUE = (
    "SU,SI,B_1,R_1,B_2,R_2,B,R,B_8,R_8,RPFRAM2/04,"
    "PResetPRG,C_1,C_2,C,C_8,C$*,D*,W*,L,P,PFRAM2,"
    "TYPE1YN_FW_BLOB,TYPE1YN_NVRAM_BLOB,TYPE1YN_CLM_BLOB/0FFF00300,"
    "EXCEPTVECT/0FFFBFF80,RESETVECT/0FFFBFFFC"
)
ROM_MAPPING_ANCHOR = (
    '<listOptionValue builtIn="false" value="D_8=R_8"/>'
)
ROM_MAPPING_PFRAM2 = (
    '<listOptionValue builtIn="false" value="PFRAM2=RPFRAM2"/>'
)
DEFINE_ANCHOR = (
    '<listOptionValue builtIn="false" value="-define=__FUNCTION__=__func__"/>'
)
VERSION_MARKER_LINKER_OPTION = (
    '<listOptionValue builtIn="false" '
    'value="-symbol_forbid=_g_rx671_ota_image_version_marker"/>'
)


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    build: int

    @property
    def text(self) -> str:
        return f"{self.major}.{self.minor}.{self.build}"


def parse_version(value: str) -> Version:
    match = re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    if not match:
        raise ValueError(
            f"invalid version {value!r}: expected x.y.z without leading zeroes"
        )
    version = Version(*(int(group) for group in match.groups()))
    if version.major > 255 or version.minor > 255 or version.build > 65535:
        raise ValueError(
            f"invalid version {value!r}: major/minor must be 0..255 and "
            "build must be 0..65535"
        )
    return version


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


def make_ota_cproject(text: str, version: Version) -> str:
    existing_version_defines = re.findall(
        r'-define=APP_VERSION_(?:MAJOR|MINOR|BUILD)=[^"]+', text
    )
    if existing_version_defines:
        raise ValueError(
            ".cproject contains persistent APP_VERSION defines: "
            + ", ".join(existing_version_defines)
        )
    text = _replace_once(
        text,
        'modes="bank.single"',
        'modes="bank.dual"',
        ".cproject bank mode",
    )
    if ROM_MAPPING_PFRAM2 in text:
        raise ValueError(".cproject already contains the OTA PFRAM2 mapping")
    text = _replace_once(
        text,
        ROM_MAPPING_ANCHOR,
        ROM_MAPPING_ANCHOR + "\n\t\t\t\t\t\t\t\t\t" + ROM_MAPPING_PFRAM2,
        ".cproject ROM mapping",
    )
    text = _replace_once(
        text,
        f'value="{NORMAL_START_VALUE}"',
        f'value="{OTA_START_VALUE}"',
        ".cproject linker start",
    )
    defines = (
        f'<listOptionValue builtIn="false" value="-define=APP_VERSION_MAJOR={version.major}"/>',
        f'<listOptionValue builtIn="false" value="-define=APP_VERSION_MINOR={version.minor}"/>',
        f'<listOptionValue builtIn="false" value="-define=APP_VERSION_BUILD={version.build}"/>',
        '<listOptionValue builtIn="false" value="-define=RX671_OTA_RUNTIME_ENABLE=1"/>',
        '<listOptionValue builtIn="false" value="-define=RX671_FREERTOS_HEAP_SIZE_KB=128"/>',
        '<listOptionValue builtIn="false" value="-define=RX671_NETWORK_BUFFER_DESCRIPTORS=24"/>',
        '<listOptionValue builtIn="false" value="-define=MQTT_AGENT_NETWORK_BUFFER_SIZE=8192"/>',
        '<listOptionValue builtIn="false" value="-define=mqttFileDownloader_CONFIG_BLOCK_SIZE=4096"/>',
        '<listOptionValue builtIn="false" value="-define=WHD_PORT_BUFFER_COUNT=8"/>',
        '<listOptionValue builtIn="false" value="-define=WHD_SCAN_ENABLE=0"/>',
        '<listOptionValue builtIn="false" value="-define=WHD_JOIN_USE_SCAN_RESULT=0"/>',
        '<listOptionValue builtIn="false" value="-define=WHD_JOIN_ENABLE=1"/>',
        '<listOptionValue builtIn="false" value="-define=WHD_JOIN_USE_KVS=1"/>',
        '<listOptionValue builtIn="false" value="-define=CONFIG_USE_PERCEPIO_TRACE_RECORDER=0"/>',
    )
    insertion = DEFINE_ANCHOR + "".join(
        "\n\t\t\t\t\t\t\t\t\t" + define for define in defines
    )
    text = _replace_once(
        text,
        DEFINE_ANCHOR,
        insertion,
        ".cproject compiler define anchor",
    )
    linker_option = re.search(
        r'(<option\b[^>]*\bsuperClass="'
        r'com\.renesas\.cdt\.managedbuild\.renesas\.ccrx\.linker\.option\.userBefore"'
        r'[^>]*>)(.*?)(</option>)',
        text,
        re.DOTALL,
    )
    if linker_option is None:
        raise ValueError(".cproject linker userBefore option was not found")
    if VERSION_MARKER_LINKER_OPTION in linker_option.group(2):
        raise ValueError(".cproject already contains the OTA marker linker option")
    updated_body = _replace_once(
        linker_option.group(2),
        '<listOptionValue builtIn="false" value=""/>',
        '<listOptionValue builtIn="false" value=""/>'
        + "\n\t\t\t\t\t\t\t\t\t"
        + VERSION_MARKER_LINKER_OPTION,
        ".cproject linker userBefore value",
    )
    return (
        text[: linker_option.start(2)]
        + updated_body
        + text[linker_option.end(2) :]
    )


def make_provisioner_cproject(text: str) -> str:
    if 'modes="bank.single"' not in text or 'modes="bank.dual"' in text:
        raise ValueError("provisioner requires the checked-in bank.single project")
    if "RX671_OTA_PROVISIONER_ENABLE" in text:
        raise ValueError(".cproject contains a persistent OTA provisioner define")
    define = (
        '<listOptionValue builtIn="false" '
        'value="-define=RX671_OTA_PROVISIONER_ENABLE=1"/>'
    )
    return _replace_once(
        text,
        DEFINE_ANCHOR,
        DEFINE_ANCHOR + "\n\t\t\t\t\t\t\t\t\t" + define,
        ".cproject provisioner define anchor",
    )


def make_ota_bank_config(text: str, label: str) -> str:
    return _replace_once(
        text,
        "#define BSP_CFG_CODE_FLASH_BANK_MODE    (1)",
        "#define BSP_CFG_CODE_FLASH_BANK_MODE    (0)",
        label,
    )


def make_ota_fwup_config(text: str) -> str:
    return _replace_once(
        text,
        "#define FWUP_CFG_AREA_SIZE                          (0x00100000U)",
        "#define FWUP_CFG_AREA_SIZE                          (0x000C0000U)",
        "r_fwup_config.h install area size",
    )


class TemporaryOtaProfile:
    """Apply an OTA build profile and restore the source byte-for-byte."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.snapshots = {
            relative: (project_dir / relative).read_bytes()
            for relative in PROFILE_PATHS
        }

    def apply(self, version: Version) -> None:
        cproject = self.snapshots[Path(".cproject")].decode("utf-8")
        fwup = self.snapshots[Path("src/frtos_config/r_fwup_config.h")].decode(
            "utf-8"
        )
        bsp = self.snapshots[
            Path("src/smc_gen/r_config/r_bsp_config.h")
        ].decode("utf-8")
        reference = self.snapshots[
            Path("src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h")
        ].decode("utf-8")
        (self.project_dir / ".cproject").write_text(
            make_ota_cproject(cproject, version), encoding="utf-8", newline=""
        )
        (self.project_dir / "src/frtos_config/r_fwup_config.h").write_text(
            make_ota_fwup_config(fwup), encoding="utf-8", newline=""
        )
        (self.project_dir / "src/smc_gen/r_config/r_bsp_config.h").write_text(
            make_ota_bank_config(bsp, "r_bsp_config.h bank mode"),
            encoding="utf-8",
            newline="",
        )
        (
            self.project_dir
            / "src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h"
        ).write_text(
            make_ota_bank_config(reference, "r_bsp_config_reference.h bank mode"),
            encoding="utf-8",
            newline="",
        )

    def restore(self) -> None:
        for relative, content in self.snapshots.items():
            (self.project_dir / relative).write_bytes(content)

    def __enter__(self) -> TemporaryOtaProfile:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.restore()


class TemporaryProvisionerProfile:
    """Apply the credential-only bank.single profile and restore .cproject."""

    def __init__(self, project_dir: Path):
        self.path = project_dir / ".cproject"
        self.snapshot = self.path.read_bytes()

    def __enter__(self) -> TemporaryProvisionerProfile:
        source = self.snapshot.decode("utf-8")
        self.path.write_text(
            make_provisioner_cproject(source), encoding="utf-8", newline=""
        )
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.path.write_bytes(self.snapshot)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def source_state(repo_root: Path) -> str:
    unstaged = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--binary", "--ignore-submodules=dirty"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    staged = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--cached",
            "--binary",
            "--ignore-submodules=dirty",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    untracked = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--others",
            "--exclude-standard",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.splitlines()
    return json.dumps(
        {
            "unstaged": unstaged,
            "staged": staged,
            "untracked": sorted(untracked),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def tracked_source_is_dirty(repo_root: Path) -> bool:
    state = json.loads(source_state(repo_root))
    return bool(state["unstaged"] or state["staged"] or state["untracked"])


def validate_formal_input_submodules(repo_root: Path) -> dict[str, str]:
    command = [
        "git",
        "-C",
        str(repo_root),
        "submodule",
        "status",
        "--",
        *(path.as_posix() for path in FORMAL_INPUT_SUBMODULES),
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    gitlinks: dict[str, str] = {}
    invalid: list[str] = []
    for line in result.stdout.splitlines():
        match = re.fullmatch(r" ([0-9a-f]{40}) ([^\s]+)(?: .*)?", line)
        if match is None:
            invalid.append(line[:80])
            continue
        sha, relative = match.groups()
        submodule = repo_root / relative
        status = _git(
            submodule,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=none",
        )
        if status:
            invalid.append(f"{relative}: worktree dirty")
            continue
        gitlinks[relative] = sha

    missing = [
        path.as_posix()
        for path in FORMAL_INPUT_SUBMODULES
        if path.as_posix() not in gitlinks
    ]
    if invalid or missing:
        details = [*(f"invalid={item}" for item in invalid)]
        if missing:
            details.append("missing=" + ",".join(missing))
        raise RuntimeError(
            "formal OTA input submodules must match gitlinks and be clean: "
            + "; ".join(details)
        )
    return dict(sorted(gitlinks.items()))


def _safe_recreate_output(path: Path, repo_root: Path) -> None:
    allowed_root = (repo_root / "build/rx671-ota").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"refusing to recreate output outside {allowed_root}: {resolved}"
        ) from exc
    if resolved == allowed_root:
        raise ValueError("output must be a child of build/rx671-ota")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _validate_output_root(path: Path, repo_root: Path) -> None:
    allowed_root = (repo_root / "build/rx671-ota").resolve()
    if path.resolve() != allowed_root:
        raise ValueError(
            f"output root must be the dedicated repository path {allowed_root}: "
            f"{path.resolve()}"
        )


def _validate_workspace_root(path: Path) -> None:
    allowed_root = Path("C:/ai/codex/ws").resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"e2 studio workspace must stay below {allowed_root}: {resolved}"
        ) from exc
    if not relative.parts:
        raise ValueError(
            f"e2 studio workspace must be a child of {allowed_root}"
        )


def _remove_transient_build_products(
    project_dir: Path,
    workspace: Path,
) -> None:
    """Remove compiler/workspace outputs after copying formal artifacts."""
    resolved_project = project_dir.resolve()
    hardware_debug = (resolved_project / "HardwareDebug").resolve()
    resolved_workspace = workspace.resolve()
    _validate_workspace_root(resolved_workspace)
    try:
        hardware_debug.relative_to(resolved_project)
    except ValueError as exc:
        raise ValueError(
            "RX671 HardwareDebug cleanup escaped the project directory"
        ) from exc

    for path in (hardware_debug, resolved_workspace):
        if path.exists():
            shutil.rmtree(path)
    remaining = [
        str(path)
        for path in (hardware_debug, resolved_workspace)
        if path.exists()
    ]
    if remaining:
        raise RuntimeError(
            "RX671 transient build cleanup failed: "
            + ", ".join(remaining)
        )


def _run(
    command: list[str],
    cwd: Path,
    *,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+", subprocess.list2cmdline(command), flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
        env=env,
    )


def ota_build_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(os.environ if source is None else source)
    for variable in WIFI_CREDENTIAL_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


def assert_wifi_credentials_absent(
    paths: list[Path],
    source: Mapping[str, str] | None = None,
) -> None:
    environment = os.environ if source is None else source
    needles = {
        variable: value.encode("utf-8") + b"\0"
        for variable in WIFI_CREDENTIAL_ENVIRONMENT_VARIABLES
        if (value := environment.get(variable))
    }
    for path in paths:
        content = path.read_bytes()
        for variable, needle in needles.items():
            if needle in content:
                raise RuntimeError(
                    "Wi-Fi credential material detected in OTA output "
                    f"{path.name} ({variable})"
                )


class TemporaryWifiCredentialIsolation:
    """Keep ignored local Wi-Fi credentials out of an OTA artifact build."""

    def __init__(self, path: Path, *, restore_existing: bool):
        self.path = path
        self.restore_existing = restore_existing
        self.original: bytes | None = None

    def __enter__(self) -> "TemporaryWifiCredentialIsolation":
        if self.path.exists():
            self.original = self.path.read_bytes()
            self.path.unlink()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.path.unlink(missing_ok=True)
        if self.restore_existing and self.original is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(self.original)


class TemporaryWhdPatchIsolation:
    """Restore the known WHD portability patch after a headless build."""

    def __init__(self, repo_root: Path):
        self.submodule = repo_root / WHD_SUBMODULE_RELATIVE
        self.patch = repo_root / WHD_PATCH_RELATIVE
        self.patch_is_temporary = False
        self.snapshots: dict[Path, bytes] = {}

    def _check(self, *, reverse: bool) -> bool:
        command = [
            "git",
            "-C",
            str(self.submodule),
            "apply",
            "--ignore-space-change",
            "--ignore-whitespace",
        ]
        if reverse:
            command.append("--reverse")
        command.extend(("--check", str(self.patch)))
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
        ).returncode == 0

    def __enter__(self) -> "TemporaryWhdPatchIsolation":
        status = _git(
            self.submodule,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=none",
        )
        if status:
            raise RuntimeError("WHD submodule must be clean before OTA build")
        if self._check(reverse=False):
            self.patch_is_temporary = True
            patch_text = self.patch.read_text(encoding="utf-8")
            relative_paths = sorted(
                {
                    Path(match)
                    for match in re.findall(
                        r"^\+\+\+ b/(.+)$",
                        patch_text,
                        flags=re.MULTILINE,
                    )
                    if match != "/dev/null"
                }
            )
            if not relative_paths:
                raise RuntimeError("WHD portability patch contains no files")
            for relative in relative_paths:
                target = self.submodule / relative
                if not target.is_file():
                    raise RuntimeError(
                        f"WHD portability patch input is missing: {relative}"
                    )
                self.snapshots[relative] = target.read_bytes()
        elif self._check(reverse=True):
            self.patch_is_temporary = False
        else:
            raise RuntimeError(
                "WHD portability patch is neither applicable nor committed"
            )
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        status = _git(
            self.submodule,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=none",
        )
        if not status:
            return
        if not self.patch_is_temporary or not self.snapshots:
            raise RuntimeError(
                "WHD submodule contains changes other than the expected "
                "temporary portability patch"
            )
        for relative, content in self.snapshots.items():
            (self.submodule / relative).write_bytes(content)
        remaining = _git(
            self.submodule,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=none",
        )
        if remaining:
            raise RuntimeError(
                "WHD submodule did not return to its clean gitlink state"
            )


def _copy_build_outputs(project_dir: Path, artifact_dir: Path) -> dict[str, Path]:
    output_dir = project_dir / "HardwareDebug"
    outputs: dict[str, Path] = {}
    for extension in ("mot", "abs", "map"):
        source = output_dir / f"{ARTIFACT_BASENAME}.{extension}"
        if not source.is_file():
            raise FileNotFoundError(f"RX671 OTA build artifact missing: {source}")
        destination = artifact_dir / source.name
        shutil.copy2(source, destination)
        outputs[extension] = destination
    return outputs


def _write_signer_public_key(signing_key: Path, destination: Path) -> None:
    encoded = signing_key.read_bytes()
    private_key = serialization.load_pem_private_key(encoded, password=None)
    if (
        not isinstance(private_key, ec.EllipticCurvePrivateKey)
        or not isinstance(private_key.curve, ec.SECP256R1)
    ):
        raise ValueError("OTA signing key must be an ECDSA P-256 private key")
    destination.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def _create_ota_transfer_artifacts(
    *,
    rsu_path: Path,
    signer_public_key: Path,
    payload_path: Path,
    signature_path: Path,
) -> None:
    """Write the OTA PAL payload and matching DER ECDSA signature."""

    rsu = rsu_path.read_bytes()
    if len(rsu) <= RSU_HEADER_SIZE:
        raise ValueError("RX671 RSU is too short to contain an OTA payload")
    raw_signature = rsu[
        RSU_RAW_SIGNATURE_OFFSET :
        RSU_RAW_SIGNATURE_OFFSET + RSU_RAW_SIGNATURE_SIZE
    ]
    if len(raw_signature) != RSU_RAW_SIGNATURE_SIZE:
        raise ValueError("RX671 RSU does not contain a complete P-256 signature")

    payload = rsu[RSU_HEADER_SIZE:]
    r = int.from_bytes(raw_signature[:32], "big")
    s = int.from_bytes(raw_signature[32:], "big")
    der_signature = utils.encode_dss_signature(r, s)
    public_key = serialization.load_pem_public_key(
        signer_public_key.read_bytes()
    )
    if (
        not isinstance(public_key, ec.EllipticCurvePublicKey)
        or not isinstance(public_key.curve, ec.SECP256R1)
    ):
        raise ValueError("OTA signer public key must be ECDSA P-256")
    try:
        public_key.verify(
            der_signature,
            payload,
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise RuntimeError(
            "candidate OTA transfer signature does not verify"
        ) from exc

    payload_path.write_bytes(payload)
    signature_path.write_bytes(der_signature)


def _build_provisioner(
    *,
    repo_root: Path,
    project_dir: Path,
    output_root: Path,
    e2studio: Path,
    workspace: Path,
    timeout_seconds: int,
    input_gitlinks: dict[str, str],
) -> None:
    artifact_dir = output_root / "provisioner"
    _safe_recreate_output(artifact_dir, repo_root)
    build_log = artifact_dir / "e2studio-build.log"
    build_environment = ota_build_environment()
    local_join_config = project_dir / LOCAL_JOIN_CONFIG_RELATIVE
    restore_local_config = build_environment.get("CI", "").lower() != "true"

    with TemporaryProvisionerProfile(project_dir):
        with TemporaryWhdPatchIsolation(repo_root):
            with TemporaryWifiCredentialIsolation(
                local_join_config,
                restore_existing=restore_local_config,
            ):
                _run(
                    [
                        "pwsh",
                        "-NoProfile",
                        "-File",
                        str(repo_root / "tools/build_headless_rx671_wifi.ps1"),
                        "-ProjectRoot",
                        str(repo_root),
                        "-E2Studio",
                        str(e2studio),
                        "-Workspace",
                        str(workspace),
                        "-LogFile",
                        str(build_log),
                        "-E2StudioTimeoutSeconds",
                        str(timeout_seconds),
                        "-SkipWifiConfig",
                        "-SkipAwsIotConfig",
                    ],
                    repo_root,
                    env=build_environment,
                )
        if validate_formal_input_submodules(repo_root) != input_gitlinks:
            raise RuntimeError(
                "formal OTA input submodule state changed during provisioner build"
            )
        outputs = _copy_build_outputs(project_dir, artifact_dir)
        assert_wifi_credentials_absent(outputs.values())
        metadata = {
            "schema_version": 1,
            "profile": PROVISIONER_PROFILE_NAME,
            "source_sha": _git(repo_root, "rev-parse", "HEAD"),
            "bank_mode": "bank.single",
            "credentials_embedded": False,
            "sha256": {
                path.name: sha256(path)
                for path in outputs.values()
            },
        }
        (artifact_dir / "provisioner-manifest.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _copy_bootloader_outputs(repo_root: Path, output_root: Path) -> list[Path]:
    artifact_dir = output_root / "bootloader"
    _safe_recreate_output(artifact_dir, repo_root)
    source_dir = repo_root / BOOTLOADER_PROJECT_RELATIVE / "HardwareDebug"
    copied: list[Path] = []
    for extension in ("mot", "abs", "map"):
        source = source_dir / f"boot_loader_rx671_ek.{extension}"
        if not source.is_file():
            raise FileNotFoundError(
                f"RX671 bootloader artifact missing; run its build first: {source}"
            )
        destination = artifact_dir / source.name
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def _copy_failed_build_diagnostics(project_dir: Path, artifact_dir: Path) -> None:
    """Preserve linker/make diagnostics before the outer cleanup removes them."""
    hardware_debug = project_dir / "HardwareDebug"
    diagnostic_dir = artifact_dir / "failed-build-diagnostics"
    copied = False
    for name in (
        f"{ARTIFACT_BASENAME}.map",
        "LinkerSubCommand.tmp",
        f"Linker{ARTIFACT_BASENAME}.tmp",
        "makefile",
    ):
        source = hardware_debug / name
        if source.is_file():
            diagnostic_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, diagnostic_dir / name)
            copied = True
    if copied:
        print(f"RX671 OTA failed-build diagnostics: {diagnostic_dir}")


def _copy_effective_inputs(
    repo_root: Path, project_dir: Path, artifact_dir: Path
) -> list[Path]:
    snapshot_root = artifact_dir / "effective-config"
    copied: list[Path] = []
    for relative in PROVENANCE_PROJECT_PATHS:
        source = project_dir / relative
        destination = snapshot_root / PROJECT_RELATIVE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    for relative in BOOTLOADER_PROVENANCE_PATHS:
        source = repo_root / relative
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def _create_manifest(
    *,
    repo_root: Path,
    project_dir: Path,
    artifact_dir: Path,
    version: Version,
    dirty: bool,
    outputs: dict[str, Path],
    rsu_path: Path,
    certificate_path: Path,
    public_key_path: Path,
    transfer_payload_path: Path | None,
    transfer_signature_path: Path | None,
    effective_inputs: list[Path],
    bootloader_artifacts: list[Path],
    input_gitlinks: dict[str, str],
) -> Path:
    required = [
        *(project_dir / relative for relative in PROVENANCE_PROJECT_PATHS),
        *outputs.values(),
        *WHD_BLOB_PATHS,
        *BOOTLOADER_PROVENANCE_PATHS,
        rsu_path,
        certificate_path,
        public_key_path,
        *(
            [transfer_payload_path, transfer_signature_path]
            if transfer_payload_path is not None
            and transfer_signature_path is not None
            else []
        ),
        *effective_inputs,
        *bootloader_artifacts,
    ]
    absolute_required = [
        path if path.is_absolute() else repo_root / path for path in required
    ]
    missing = [str(path) for path in absolute_required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "provenance input is missing: " + ", ".join(missing)
        )
    hashes = {
        path.resolve().relative_to(repo_root.resolve()).as_posix(): sha256(path)
        for path in absolute_required
    }
    source_sha = _git(repo_root, "rev-parse", "HEAD")
    manifest = {
        "schema_version": 1,
        "source_sha": source_sha,
        "dirty": dirty,
        "project_path": PROJECT_RELATIVE.as_posix(),
        "profile": PROFILE_NAME,
        "formal": not dirty,
        "credentials_embedded": False,
        "wifi_credentials_source": "littlefs_kvs_runtime_provisioning",
        "ota_image_version": version.text,
        "rsu_path": rsu_path.relative_to(repo_root).as_posix(),
        "signer_certificate_path": certificate_path.relative_to(repo_root).as_posix(),
        "signer_public_key_path": public_key_path.relative_to(repo_root).as_posix(),
        "sha256": dict(sorted(hashes.items())),
        "gitlinks": dict(sorted(input_gitlinks.items())),
    }
    if transfer_payload_path is not None and transfer_signature_path is not None:
        manifest["ota_transfer_payload_path"] = (
            transfer_payload_path.relative_to(repo_root).as_posix()
        )
        manifest["ota_transfer_signature_der_path"] = (
            transfer_signature_path.relative_to(repo_root).as_posix()
        )
    manifest_path = artifact_dir / PROVENANCE_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _dirty_analysis_is_structurally_safe(report: dict[str, object]) -> bool:
    gates = report.get("gates")
    if not isinstance(gates, list):
        return False
    allowed_non_pass = {
        "artifact_provenance",
        "whd_blob_sizes",
        "ram_capacity",
        "map_image_single_area",
        "mot_image_single_area",
    }
    saw_dirty_provenance = False
    for gate in gates:
        if not isinstance(gate, dict):
            return False
        name = gate.get("name")
        status = gate.get("status")
        detail = gate.get("detail")
        if status == "PASS":
            continue
        if name not in allowed_non_pass:
            return False
        if name == "artifact_provenance":
            saw_dirty_provenance = (
                status == "FAIL"
                and isinstance(detail, str)
                and "dirty=false" in detail
            )
        elif status != "UNKNOWN":
            return False
    return saw_dirty_provenance


def _build_one(
    *,
    repo_root: Path,
    project_dir: Path,
    artifact_dir: Path,
    version: Version,
    e2studio: Path,
    workspace: Path,
    signing_key: Path,
    certificate_source: Path,
    public_key_source: Path,
    create_transfer_payload: bool,
    dirty: bool,
    allow_dirty: bool,
    timeout_seconds: int,
    bootloader_artifacts: list[Path],
    input_gitlinks: dict[str, str],
) -> None:
    _safe_recreate_output(artifact_dir, repo_root)
    build_log = artifact_dir / "e2studio-build.log"
    build_environment = ota_build_environment()
    restore_local_config = build_environment.get("CI", "").lower() != "true"
    local_join_config = project_dir / LOCAL_JOIN_CONFIG_RELATIVE
    with TemporaryWhdPatchIsolation(repo_root):
        with TemporaryWifiCredentialIsolation(
            local_join_config,
            restore_existing=restore_local_config,
        ):
            build_command = [
                "pwsh",
                "-NoProfile",
                "-File",
                str(repo_root / "tools/build_headless_rx671_wifi.ps1"),
                "-ProjectRoot",
                str(repo_root),
                "-E2Studio",
                str(e2studio),
                "-Workspace",
                str(workspace),
                "-LogFile",
                str(build_log),
                "-E2StudioTimeoutSeconds",
                str(timeout_seconds),
                "-OtaImageVersion",
                version.text,
                "-SkipAwsIotConfig",
            ]
            # The KVS JOIN defines are part of the temporary .cproject above,
            # so the copied effective configuration and its hash describe the
            # exact compiler input.  The child builder only has to suppress
            # every legacy credential-bearing local JOIN path.
            build_command.append("-SkipWifiConfig")
            try:
                _run(
                    build_command,
                    repo_root,
                    env=build_environment,
                )
            except subprocess.CalledProcessError:
                _copy_failed_build_diagnostics(project_dir, artifact_dir)
                raise
    if validate_formal_input_submodules(repo_root) != input_gitlinks:
        raise RuntimeError("formal OTA input submodule state changed during build")
    outputs = _copy_build_outputs(project_dir, artifact_dir)
    rsu_path = artifact_dir / f"{ARTIFACT_BASENAME}.rsu"
    _run(
        [
            sys.executable,
            str(repo_root / "tools/build_rx671_fwup_v2_rsu.py"),
            "--mot",
            str(outputs["mot"]),
            "--key",
            str(signing_key),
            "--output",
            str(rsu_path),
        ],
        repo_root,
    )
    assert_wifi_credentials_absent([*outputs.values(), rsu_path])
    certificate_path = artifact_dir / SIGNER_CERTIFICATE_NAME
    shutil.copy2(certificate_source, certificate_path)
    public_key_path = artifact_dir / SIGNER_PUBLIC_KEY_NAME
    shutil.copy2(public_key_source, public_key_path)
    transfer_payload_path: Path | None = None
    transfer_signature_path: Path | None = None
    if create_transfer_payload:
        transfer_payload_path = artifact_dir / OTA_TRANSFER_PAYLOAD_NAME
        transfer_signature_path = artifact_dir / OTA_TRANSFER_SIGNATURE_NAME
        _create_ota_transfer_artifacts(
            rsu_path=rsu_path,
            signer_public_key=public_key_path,
            payload_path=transfer_payload_path,
            signature_path=transfer_signature_path,
        )
        assert_wifi_credentials_absent(
            [transfer_payload_path, transfer_signature_path]
        )
    effective_inputs = _copy_effective_inputs(
        repo_root, project_dir, artifact_dir
    )
    _create_manifest(
        repo_root=repo_root,
        project_dir=project_dir,
        artifact_dir=artifact_dir,
        version=version,
        dirty=dirty,
        outputs=outputs,
        rsu_path=rsu_path,
        certificate_path=certificate_path,
        public_key_path=public_key_path,
        transfer_payload_path=transfer_payload_path,
        transfer_signature_path=transfer_signature_path,
        effective_inputs=effective_inputs,
        bootloader_artifacts=bootloader_artifacts,
        input_gitlinks=input_gitlinks,
    )
    analysis_environment = os.environ.copy()
    analysis_environment["PYTHONIOENCODING"] = "utf-8"
    analysis = subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools/ci/analyze_rx671_ota_layout.py"),
            "--project-dir",
            str(project_dir),
            "--build-dir",
            str(artifact_dir),
            "--rsu",
            str(rsu_path),
            "--signer-certificate",
            str(certificate_path),
            "--expected-version",
            version.text,
            "--json",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=analysis_environment,
    )
    (artifact_dir / REPORT_NAME).write_text(analysis.stdout, encoding="utf-8")
    if analysis.stderr:
        print(analysis.stderr, file=sys.stderr)
    dirty_analysis_safe = False
    if analysis.returncode != 0 and allow_dirty:
        try:
            dirty_analysis_safe = _dirty_analysis_is_structurally_safe(
                json.loads(analysis.stdout)
            )
        except json.JSONDecodeError:
            dirty_analysis_safe = False
    if analysis.returncode != 0 and not dirty_analysis_safe:
        raise RuntimeError(
            f"RX671 OTA layout analysis failed for {version.text}; "
            f"see {artifact_dir / REPORT_NAME}"
        )
    if analysis.returncode != 0:
        print(
            f"WARNING: analysis exit={analysis.returncode} contains only the "
            "expected dirty-provenance block and dependent UNKNOWN gates",
            file=sys.stderr,
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--baseline-version", default="0.1.0")
    parser.add_argument("--candidate-version", default="0.1.1")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_root / "build/rx671-ota",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(
            "C:/ai/codex/ws/iot-reference-rx-rx671-ota-2026-04-2"
        ),
    )
    parser.add_argument(
        "--e2studio",
        type=Path,
        default=Path(
            "C:/Renesas/e2_studio_2026_04_2/eclipse/e2studioc.exe"
        ),
    )
    parser.add_argument(
        "--signing-key",
        type=Path,
        default=default_root / "sample_keys/secp256r1.privatekey",
    )
    parser.add_argument("--e2studio-timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help=(
            "Allow an exploratory build from modified tracked source. "
            "The manifest records dirty=true and formal analysis remains blocked."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    project_dir = repo_root / PROJECT_RELATIVE
    output_root = args.output_root.resolve()
    _validate_output_root(output_root, repo_root)
    _validate_workspace_root(args.workspace_root)
    signing_key = args.signing_key.resolve()
    versions = (
        ("baseline", parse_version(args.baseline_version)),
        ("candidate", parse_version(args.candidate_version)),
    )
    if versions[0][1] == versions[1][1]:
        raise SystemExit("baseline and candidate versions must differ")
    if not args.e2studio.is_file():
        raise SystemExit(f"e2 studio executable not found: {args.e2studio}")
    if not signing_key.is_file():
        raise SystemExit(f"OTA signing key not found: {signing_key}")
    input_gitlinks = validate_formal_input_submodules(repo_root)
    initial_source_state = source_state(repo_root)
    dirty = tracked_source_is_dirty(repo_root)
    if dirty and not args.allow_dirty:
        raise SystemExit(
            "tracked source is dirty; commit the deterministic OTA inputs "
            "before generating formal provenance"
        )

    certificate_source = output_root / SIGNER_CERTIFICATE_NAME
    public_key_source = output_root / SIGNER_PUBLIC_KEY_NAME
    output_root.mkdir(parents=True, exist_ok=True)
    bootloader_artifacts = _copy_bootloader_outputs(repo_root, output_root)
    _run(
        [
            sys.executable,
            str(repo_root / "tools/generate_signer_cert.py"),
            "--key",
            str(signing_key),
            "--out",
            str(certificate_source),
            "--common-name",
            "iot-reference-rx RX671 OTA Signer",
        ],
        repo_root,
    )
    _write_signer_public_key(signing_key, public_key_source)

    try:
        _build_provisioner(
            repo_root=repo_root,
            project_dir=project_dir,
            output_root=output_root,
            e2studio=args.e2studio.resolve(),
            workspace=args.workspace_root.resolve(),
            timeout_seconds=args.e2studio_timeout_seconds,
            input_gitlinks=input_gitlinks,
        )
        with TemporaryOtaProfile(project_dir) as profile:
            for label, version in versions:
                profile.apply(version)
                artifact_dir = output_root / f"{label}-{version.text}"
                _build_one(
                    repo_root=repo_root,
                    project_dir=project_dir,
                    artifact_dir=artifact_dir,
                    version=version,
                    e2studio=args.e2studio.resolve(),
                    workspace=args.workspace_root.resolve(),
                    signing_key=signing_key,
                    certificate_source=certificate_source,
                    public_key_source=public_key_source,
                    create_transfer_payload=(label == "candidate"),
                    dirty=dirty,
                    allow_dirty=args.allow_dirty,
                    timeout_seconds=args.e2studio_timeout_seconds,
                    bootloader_artifacts=bootloader_artifacts,
                    input_gitlinks=input_gitlinks,
                )
    finally:
        cleanup_errors: list[str] = []
        try:
            _remove_transient_build_products(
                project_dir,
                args.workspace_root,
            )
        except Exception as error:
            cleanup_errors.append(str(error))
        # TemporaryOtaProfile restores the tracked inputs. Keep this explicit
        # postcondition so an accidental future profile-path omission fails.
        if source_state(repo_root) != initial_source_state:
            cleanup_errors.append(
                "RX671 OTA helper did not restore the tracked source state"
            )
        if validate_formal_input_submodules(repo_root) != input_gitlinks:
            cleanup_errors.append(
                "RX671 OTA helper did not restore the formal input submodules"
            )
        if cleanup_errors:
            raise RuntimeError("; ".join(cleanup_errors))

    print(f"RX671 OTA baseline/candidate artifacts: {output_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

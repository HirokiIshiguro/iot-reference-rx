#!/usr/bin/env python3
"""Validate the RX671/Type 1YN OTA flash layout without guessing sizes.

Exit codes:
    0: every gate is PASS
    1: one or more gates are FAIL
    2: no FAIL, but one or more gates are UNKNOWN
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ADDRESS_SPACE_END = 1 << 32
RESOURCE_SIZE_MACROS = {
    "TYPE1YN_FW_BLOB": "TYPE1YN_FW_BLOB_SIZE",
    "TYPE1YN_NVRAM_BLOB": "TYPE1YN_NVRAM_BLOB_SIZE",
    "TYPE1YN_CLM_BLOB": "TYPE1YN_CLM_BLOB_SIZE",
}
RESOURCE_LINKER_SYMBOLS = {
    "TYPE1YN_FW_BLOB": "g_type1yn_firmware_bin",
    "TYPE1YN_NVRAM_BLOB": "g_type1yn_nvram_bin",
    "TYPE1YN_CLM_BLOB": "g_type1yn_clm_blob",
}
PROVENANCE_MANIFEST_NAME = "ota-layout-provenance.json"
LAYOUT_CONTRACT_NAME = "ota-layout-contract.json"
PROVENANCE_CONFIG_PATHS = (
    ".cproject",
    LAYOUT_CONTRACT_NAME,
    "src/frtos_config/r_fwup_config.h",
    "src/frtos_config/rm_littlefs_flash_config.h",
    "src/smc_gen/r_config/r_bsp_config.h",
    "src/sdio_host.c",
    "src/whd_port/whd_port_resource.c",
)
FWUP_HEADER_SIZE = 0x200
FWUP_DESCRIPTOR_SIZE = 0x100
FWUP_APPLICATION_OFFSET = FWUP_HEADER_SIZE + FWUP_DESCRIPTOR_SIZE
FWUP_AREA_START = 0xFFF00000
FWUP_AREA_SIZE = 0x000C0000
FWUP_APPLICATION_START = FWUP_AREA_START + FWUP_APPLICATION_OFFSET
FWUP_APPLICATION_SIZE = FWUP_AREA_SIZE - FWUP_APPLICATION_OFFSET
FWUP_SIGNATURE_TYPE = b"sig-sha256-ecdsa"
FWUP_RAW_P256_SIGNATURE_SIZE = 64
OTA_PROFILE_NAME = "rx671-dual-bank-ota-v1"
OTA_VERSION_MARKER_PREFIX = b"RX671_OTA_IMAGE_VERSION="
LITTLEFS_LINKER_SECTION = "C_LITTLEFS_MANAGEMENT_AREA"
BOOTLOADER_PROJECT_RELATIVE = Path("Projects/boot_loader_rx671_ek/e2studio_ccrx")
BOOTLOADER_SUBMODULE_RELATIVE = (
    BOOTLOADER_PROJECT_RELATIVE / "lib/rx_bootloader"
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
OTA_MQTT_FILE_BLOCK_SIZE = 4096
OTA_MQTT_NETWORK_BUFFER_SIZE = 8192
OTA_MQTT_JSON_AND_PROTOCOL_OVERHEAD = 1024


@dataclass(frozen=True)
class Gate:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class Region:
    name: str
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size

    def contains(self, start: int, end: int) -> bool:
        return self.start <= start and end <= self.end


@dataclass(frozen=True)
class Section:
    name: str
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size


def _parse_c_integer(value: str) -> int:
    value = value.strip().strip("()")
    value = re.sub(r"[uUlL]+$", "", value)
    return int(value, 0)


def _macro(text: str, name: str) -> int | None:
    match = re.search(
        rf"^\s*#\s*define\s+{re.escape(name)}\s+\(?\s*"
        r"(0[xX][0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*\)?",
        text,
        re.MULTILINE,
    )
    return _parse_c_integer(match.group(1)) if match else None


def _macro_rhs(text: str, name: str) -> str | None:
    match = re.search(
        rf"^\s*#\s*define\s+{re.escape(name)}\s+(.+?)\s*$",
        text,
        re.MULTILINE,
    )
    if not match:
        return None
    return re.sub(r"/\*.*?\*/|//.*$", "", match.group(1)).strip()


def _resolve_numeric_macro(text: str, name: str, aliases: dict[str, int]) -> int | None:
    value = _macro(text, name)
    if value is not None:
        return value
    rhs = _macro_rhs(text, name)
    if rhs is None:
        return None
    token = rhs.strip().strip("()")
    return aliases.get(token)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_text_lines(left: Path, right: Path) -> bool:
    return left.read_text(encoding="utf-8").splitlines() == right.read_text(
        encoding="utf-8"
    ).splitlines()


def _git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip().lower()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


def _relative_to_repo(path: Path, repo_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def _memory_size_for_selected_part(
    config_text: str, mcu_info_text: str, size_macro: str
) -> int | None:
    selected = _macro(config_text, "BSP_CFG_MCU_PART_MEMORY_SIZE")
    if selected is None:
        return None
    choices = re.finditer(
        r"^\s*#\s*(?:if|elif)\s+BSP_CFG_MCU_PART_MEMORY_SIZE\s*==\s*"
        r"(0[xX][0-9A-Fa-f]+|[0-9]+).*?"
        rf"^\s*#\s*define\s+{re.escape(size_macro)}\s+\(?\s*"
        r"(0[xX][0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*\)?",
        mcu_info_text,
        re.MULTILINE | re.DOTALL,
    )
    for choice in choices:
        if _parse_c_integer(choice.group(1)) == selected:
            return _parse_c_integer(choice.group(2))
    return None


def _parse_start_anchors(value: str) -> dict[str, int]:
    anchors: dict[str, int] = {}
    previous_end = 0
    for match in re.finditer(r"/(0[xX][0-9A-Fa-f]+|[0-9A-Fa-f]+)", value):
        section_list = value[previous_end : match.start()].lstrip(",")
        address = int(match.group(1), 16)
        for section in section_list.split(","):
            section = section.strip()
            if section:
                anchors[section] = address
        previous_end = match.end()
    return anchors


def _parse_cproject(path: Path) -> tuple[str, Path, str, dict[str, int], dict[str, str]]:
    root = ET.parse(path).getroot()
    device = root.find(".//deviceConfiguration")
    if device is None:
        raise ValueError("deviceConfiguration が見つかりません")
    mode = device.get("modes", "")

    builder = root.find(".//builder")
    build_path = builder.get("buildPath", "") if builder is not None else ""
    build_name = build_path.rsplit("/", 1)[-1] if build_path else "HardwareDebug"

    configuration = root.find(".//configuration")
    # Both tracked RX671 projects use ${ProjName}. The directory immediately
    # above e2studio_ccrx is the canonical e2 studio project name.
    artifact_name = path.parent.parent.name
    if configuration is not None:
        configured = configuration.get("artifactName", "")
        if configured and configured != "${ProjName}":
            artifact_name = configured

    start_value = None
    binary_value = None
    for option in root.findall(".//option"):
        superclass = option.get("superClass", "")
        if superclass.endswith("linker.option.linkerSection"):
            start_value = option.get("value")
        if superclass.endswith("linker.option.userAfter"):
            for item in option.findall("listOptionValue"):
                value = item.get("value", "")
                if value.startswith("-binary="):
                    binary_value = value[len("-binary=") :]
    if not start_value:
        raise ValueError("CC-RX -start 設定が見つかりません")

    binaries: dict[str, str] = {}
    if binary_value:
        for match in re.finditer(r"(?:^|,)([^,]+)\(([^:(),]+):", binary_value):
            binaries[match.group(2)] = match.group(1)
    return mode, path.parent / build_name, artifact_name, _parse_start_anchors(start_value), binaries


def _parse_declared_resource_sizes(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    sizes: dict[str, int] = {}
    for section, macro_name in RESOURCE_SIZE_MACROS.items():
        value = _macro(text, macro_name)
        if value is not None:
            sizes[section] = value
    return sizes


def _parse_map_sections(path: Path) -> dict[str, Section]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    in_table = False
    pending_name: str | None = None
    sections: dict[str, Section] = {}
    values_re = re.compile(
        r"^\s*([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s+"
        r"([0-9A-Fa-f]+)\s+[0-9A-Fa-f]+\s*$"
    )
    for line in lines:
        if line.strip().startswith("SECTION") and "START" in line and "SIZE" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("***"):
            break
        match = values_re.match(line)
        if match and pending_name:
            start = int(match.group(1), 16)
            declared_size = int(match.group(3), 16)
            sections[pending_name] = Section(pending_name, start, declared_size)
            pending_name = None
            continue
        stripped = line.strip()
        if stripped and not stripped.startswith("SECTION"):
            pending_name = stripped.split()[0]
    if not sections:
        raise ValueError("map の Mapping List を解析できません")
    return sections


def _cproject_integer_define(text: str, name: str) -> int | None:
    values = {
        _parse_c_integer(match.group(1))
        for match in re.finditer(
            rf'value="-define={re.escape(name)}='
            r'\(?\s*(0[xX][0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*\)?"',
            text,
        )
    }
    return next(iter(values)) if len(values) == 1 else None


def _ram_capacity_gate(
    *,
    sections: dict[str, Section] | None,
    ram_size: int | None,
    data_flash_start: int | None,
) -> Gate:
    if ram_size is None or data_flash_start is None:
        return Gate(
            "ram_capacity",
            "UNKNOWN",
            "選択MCUのBSP_RAM_SIZE_BYTESまたはData Flash開始addressを導出できません",
        )
    if sections is None:
        return Gate("ram_capacity", "UNKNOWN", "mapがないためRAM使用量を検証できません")

    ram_sections = [
        section
        for section in sections.values()
        if section.size and section.start < data_flash_start
    ]
    if not ram_sections:
        return Gate("ram_capacity", "FAIL", "mapにRAM sectionがありません")

    outside = [section for section in ram_sections if section.end > ram_size]
    high_water = max(section.end for section in ram_sections)
    allocated = sum(section.size for section in ram_sections)
    detail = (
        f"BSP_RAM_SIZE_BYTES={ram_size}; high-water=0x{high_water - 1:08X}; "
        f"mapped={allocated} bytes; headroom={ram_size - high_water} bytes"
    )
    if outside:
        detail += "; RAM外section=" + ", ".join(
            f"{section.name}@0x{section.start:08X}-0x{section.end - 1:08X}"
            for section in outside
        )
    return Gate("ram_capacity", "FAIL" if outside else "PASS", detail)


def _mqtt_ota_buffer_gate(
    *, block_size: int | None, network_buffer_size: int | None
) -> Gate:
    if block_size is None or network_buffer_size is None:
        return Gate(
            "mqtt_ota_buffer_fit",
            "FAIL",
            "OTA profileのmqttFileDownloader_CONFIG_BLOCK_SIZEまたは"
            "MQTT_AGENT_NETWORK_BUFFER_SIZEを一意に導出できません",
        )

    base64_size = 4 * ((block_size + 2) // 3)
    required_size = base64_size + OTA_MQTT_JSON_AND_PROTOCOL_OVERHEAD
    profile_ok = (
        block_size == OTA_MQTT_FILE_BLOCK_SIZE
        and network_buffer_size == OTA_MQTT_NETWORK_BUFFER_SIZE
    )
    fit_ok = required_size <= network_buffer_size
    detail = (
        f"block={block_size}; base64={base64_size}; "
        f"JSON/MQTT overhead allowance={OTA_MQTT_JSON_AND_PROTOCOL_OVERHEAD}; "
        f"required={required_size}; network buffer={network_buffer_size}; "
        f"required profile={OTA_MQTT_FILE_BLOCK_SIZE}/{OTA_MQTT_NETWORK_BUFFER_SIZE}"
    )
    return Gate(
        "mqtt_ota_buffer_fit",
        "PASS" if profile_ok and fit_ok else "FAIL",
        detail,
    )


def _parse_srecord_ranges(path: Path) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    address_bytes = {"1": 2, "2": 3, "3": 4}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="ascii", errors="strict").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or not line.startswith("S") or line[1:2] not in address_bytes:
            continue
        try:
            count = int(line[2:4], 16)
            payload = bytes.fromhex(line[4:])
        except ValueError as exc:
            raise ValueError(f"MOT {line_number} 行目が不正です") from exc
        if len(payload) != count:
            raise ValueError(f"MOT {line_number} 行目のbyte countが一致しません")
        if (count + sum(payload)) & 0xFF != 0xFF:
            raise ValueError(f"MOT {line_number} 行目のchecksumが不正です")
        width = address_bytes[line[1]]
        address = int.from_bytes(payload[:width], "big")
        data = payload[width:-1]
        if data:
            ranges.append((address, address + len(data)))
    if not ranges:
        raise ValueError("MOT にS1/S2/S3データレコードがありません")
    return ranges


def _classify_ranges(
    ranges: Iterable[tuple[int, int]], regions: list[Region], flash_start: int
) -> tuple[set[str], int, list[tuple[int, int]]]:
    names: set[str] = set()
    byte_count = 0
    outside: list[tuple[int, int]] = []
    for start, end in ranges:
        if end <= flash_start or start >= ADDRESS_SPACE_END:
            continue
        clipped_start = max(start, flash_start)
        clipped_end = min(end, ADDRESS_SPACE_END)
        byte_count += clipped_end - clipped_start
        matched = [region.name for region in regions if region.contains(clipped_start, clipped_end)]
        if len(matched) == 1:
            names.add(matched[0])
        else:
            outside.append((clipped_start, clipped_end))
    return names, byte_count, outside


def _hex_region(region: Region) -> str:
    return f"{region.name}=0x{region.start:08X}-0x{region.end - 1:08X} ({region.size} bytes)"


def _fwup_data_flash_geometry_gate(
    *,
    bsp_size: int | None,
    fwup_start: int | None,
    fwup_block_size: int | None,
    fwup_block_count: int | None,
    fit_start: int | None,
    fit_block_size: int | None,
    fit_block_count: int | None,
) -> Gate:
    values = (
        bsp_size,
        fwup_start,
        fwup_block_size,
        fwup_block_count,
        fit_start,
        fit_block_size,
        fit_block_count,
    )
    if any(value is None for value in values):
        return Gate(
            "fwup_data_flash_geometry",
            "UNKNOWN",
            "BSP/FWUP/FITからdata flashのstart/block-size/block-countを導出できません",
        )
    assert bsp_size is not None and fwup_start is not None
    assert fwup_block_size is not None and fwup_block_count is not None
    assert fit_start is not None and fit_block_size is not None and fit_block_count is not None
    configured_size = fwup_block_size * fwup_block_count
    fit_size = fit_block_size * fit_block_count
    ok = (
        fwup_start == fit_start
        and fwup_block_size == fit_block_size
        and fwup_block_count == fit_block_count
        and configured_size == fit_size == bsp_size
    )
    return Gate(
        "fwup_data_flash_geometry",
        "PASS" if ok else "FAIL",
        f"FWUP=start 0x{fwup_start:08X}, {fwup_block_size} bytes x {fwup_block_count}; "
        f"FIT=start 0x{fit_start:08X}, {fit_block_size} bytes x {fit_block_count}; "
        f"BSP={bsp_size} bytes",
    )


def _littlefs_data_flash_geometry_gate(
    *,
    data_flash_start: int | None,
    data_flash_size: int | None,
    fit_erase_size: int | None,
    fit_program_size: int | None,
    littlefs_start: int | None,
    littlefs_block_size: int | None,
    littlefs_block_count: int | None,
    littlefs_program_size: int | None,
) -> Gate:
    values = (
        data_flash_start,
        data_flash_size,
        fit_erase_size,
        fit_program_size,
        littlefs_start,
        littlefs_block_size,
        littlefs_block_count,
        littlefs_program_size,
    )
    if any(value is None for value in values):
        return Gate(
            "littlefs_data_flash_geometry",
            "UNKNOWN",
            "LittleFS/FIT/BSPからdata flash geometryを導出できません",
        )
    assert data_flash_start is not None and data_flash_size is not None
    assert fit_erase_size is not None and fit_program_size is not None
    assert littlefs_start is not None and littlefs_block_size is not None
    assert littlefs_block_count is not None and littlefs_program_size is not None
    littlefs_size = littlefs_block_size * littlefs_block_count
    data_flash_end = data_flash_start + data_flash_size
    littlefs_end = littlefs_start + littlefs_size
    ok = (
        littlefs_start >= data_flash_start
        and littlefs_end <= data_flash_end
        and (littlefs_start - data_flash_start) % fit_erase_size == 0
        and littlefs_block_size % fit_erase_size == 0
        and littlefs_program_size == fit_program_size
    )
    return Gate(
        "littlefs_data_flash_geometry",
        "PASS" if ok else "FAIL",
        f"LittleFS=0x{littlefs_start:08X}-0x{littlefs_end - 1:08X}, "
        f"block={littlefs_block_size}, program={littlefs_program_size}; "
        f"FIT erase={fit_erase_size}, program={fit_program_size}",
    )


def _data_flash_non_overlap_gate(
    *,
    data_flash_start: int | None,
    data_flash_size: int | None,
    littlefs_start: int | None,
    littlefs_block_size: int | None,
    littlefs_block_count: int | None,
    consumer_ranges: Iterable[Region] = (),
    consumer_layout_complete: bool = False,
) -> Gate:
    values = (
        data_flash_start,
        data_flash_size,
        littlefs_start,
        littlefs_block_size,
        littlefs_block_count,
    )
    if any(value is None for value in values):
        return Gate(
            "data_flash_non_overlap",
            "UNKNOWN",
            "data flashまたはLittleFSの範囲を導出できません",
        )
    assert data_flash_start is not None and data_flash_size is not None
    assert littlefs_start is not None
    assert littlefs_block_size is not None and littlefs_block_count is not None
    data_flash_end = data_flash_start + data_flash_size
    littlefs_end = littlefs_start + littlefs_block_size * littlefs_block_count
    littlefs_inside = (
        data_flash_start <= littlefs_start < littlefs_end <= data_flash_end
    )
    if not littlefs_inside:
        return Gate(
            "data_flash_non_overlap",
            "FAIL",
            f"LittleFS=0x{littlefs_start:08X}-0x{littlefs_end - 1:08X}が"
            f"data flash=0x{data_flash_start:08X}-0x{data_flash_end - 1:08X}の範囲外です",
        )

    ranges = list(consumer_ranges)
    consumers = [
        Region("LittleFS", littlefs_start, littlefs_end - littlefs_start),
        *ranges,
    ]
    errors: list[str] = []
    for region in consumers:
        if not (data_flash_start <= region.start < region.end <= data_flash_end):
            errors.append(
                f"{region.name}=0x{region.start:08X}-0x{region.end - 1:08X}がdata flash範囲外"
            )
    for index, left in enumerate(consumers):
        for right in consumers[index + 1 :]:
            if max(left.start, right.start) < min(left.end, right.end):
                errors.append(f"{left.name}と{right.name}が重複")
    detail = "; ".join(
        f"{region.name}=0x{region.start:08X}-0x{region.end - 1:08X}"
        for region in consumers
    )
    if not ranges and littlefs_start == data_flash_start and littlefs_end == data_flash_end:
        detail += "; LittleFSが全8 KiBを使用"
    if errors:
        detail += "; " + "; ".join(errors)
        return Gate("data_flash_non_overlap", "FAIL", detail)
    if not consumer_layout_complete:
        detail += (
            "; LittleFS以外のraw Data Flash consumerについて、"
            "install/key-store/OTA payloadを含む所有権証跡が未確定"
        )
        return Gate("data_flash_non_overlap", "UNKNOWN", detail)
    detail += "; consumer所有権証跡が完備"
    return Gate("data_flash_non_overlap", "PASS", detail)


def _contract_integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"{field} is not an integer: {value!r}") from exc
    raise ValueError(f"{field} must be an integer")


def _data_flash_ownership_contract_gate(
    *,
    contract_path: Path,
    bootloader_config_path: Path,
    data_flash_start: int | None,
    data_flash_size: int | None,
    littlefs_start: int | None,
    littlefs_size: int | None,
) -> Gate:
    if not contract_path.is_file():
        return Gate(
            "data_flash_ownership_contract",
            "UNKNOWN",
            f"ownership contractなし: {contract_path}",
        )
    if not bootloader_config_path.is_file():
        return Gate(
            "data_flash_ownership_contract",
            "UNKNOWN",
            f"RX671 bootloader configなし: {bootloader_config_path}",
        )
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        bootloader_text = bootloader_config_path.read_text(encoding="utf-8")
        data_flash = contract["data_flash"]
        contract_start = _contract_integer(data_flash["start"], "data_flash.start")
        contract_size = _contract_integer(data_flash["size"], "data_flash.size")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return Gate("data_flash_ownership_contract", "FAIL", f"contract解析失敗: {exc}")

    errors: list[str] = []
    if contract.get("schema_version") != 1:
        errors.append("schema_version!=1")
    if contract.get("target") != "R5F5671EHxFB":
        errors.append("target!=R5F5671EHxFB")
    if data_flash.get("owner") != "LittleFS":
        errors.append("owner!=LittleFS")
    if data_flash.get("application_raw_consumers") != []:
        errors.append("application_raw_consumersが空ではない")
    if data_flash.get("bootloader_install_data_flash") is not False:
        errors.append("bootloader_install_data_flash=falseではない")
    if data_flash.get("ota_payload_data_flash") is not False:
        errors.append("ota_payload_data_flash=falseではない")
    if contract_start != data_flash_start or contract_size != data_flash_size:
        errors.append(
            "contract/BSP Data Flash不一致 "
            f"(contract=0x{contract_start:08X}+{contract_size}, "
            f"BSP={data_flash_start!r}+{data_flash_size!r})"
        )
    if littlefs_start != contract_start or littlefs_size != contract_size:
        errors.append(
            "LittleFSがcontractの全Data Flashを単独所有していない "
            f"(LittleFS={littlefs_start!r}+{littlefs_size!r})"
        )
    if _macro(bootloader_text, "RX_BOOTLOADER_INSTALL_DATA_FLASH") != 0:
        errors.append("RX_BOOTLOADER_INSTALL_DATA_FLASH!=0")

    detail = (
        f"owner=LittleFS 0x{contract_start:08X}-"
        f"0x{contract_start + contract_size - 1:08X}; "
        "application raw consumers=0; bootloader install=0; OTA payload Data Flash=0"
    )
    if errors:
        detail += "; " + "; ".join(errors)
    return Gate(
        "data_flash_ownership_contract",
        "FAIL" if errors else "PASS",
        detail,
    )


def _fwup_partition_gate(
    *,
    flash_start: int,
    flash_size: int,
    main_start: int,
    buffer_start: int,
    area_size: int,
) -> Gate:
    if flash_size <= 0 or flash_size % 2 != 0:
        return Gate("fwup_partition", "FAIL", f"code flash size={flash_size}は2 bankに等分不能")

    bank_size = flash_size // 2
    expected_buffer_start = flash_start
    expected_main_start = flash_start + bank_size
    reserved_tail = bank_size - area_size
    ok = (
        0 < area_size <= bank_size
        and buffer_start == expected_buffer_start
        and main_start == expected_main_start
    )
    detail = (
        f"bank size={bank_size} bytes; buffer start=0x{buffer_start:08X}"
        f" (必要値=0x{expected_buffer_start:08X}); main start=0x{main_start:08X}"
        f" (必要値=0x{expected_main_start:08X}); install area={area_size} bytes"
    )
    if ok:
        detail += f"; 各bank末尾の予約候補={reserved_tail} bytes"
    else:
        detail += "; 2 bankの同一offset/同一size配置になっていません"
    return Gate("fwup_partition", "PASS" if ok else "FAIL", detail)


def _fwup_code_flash_layout_gate(
    *,
    main_start: int | None,
    buffer_start: int | None,
    area_size: int | None,
    application_anchor: int | None,
    except_vector_anchor: int | None,
    reset_vector_anchor: int | None,
    code_flash_anchors: dict[str, int] | None = None,
) -> Gate:
    if main_start is None or buffer_start is None or area_size is None:
        return Gate(
            "fwup_code_flash_layout",
            "UNKNOWN",
            "FWUP main/buffer/area sizeを導出できません",
        )

    main_header = Region("main-header", main_start, FWUP_HEADER_SIZE)
    main_descriptor = Region(
        "main-descriptor", main_start + FWUP_HEADER_SIZE, FWUP_DESCRIPTOR_SIZE
    )
    buffer_header = Region("buffer-header", buffer_start, FWUP_HEADER_SIZE)
    buffer_descriptor = Region(
        "buffer-descriptor", buffer_start + FWUP_HEADER_SIZE, FWUP_DESCRIPTOR_SIZE
    )
    expected_application = main_start + FWUP_APPLICATION_OFFSET
    expected_except_vector = main_start + area_size - 0x80
    expected_reset_vector = main_start + area_size - 0x04

    errors: list[str] = []
    if area_size <= FWUP_APPLICATION_OFFSET:
        errors.append(
            f"FWUP area {area_size} bytesがheader+descriptor {FWUP_APPLICATION_OFFSET} bytes以下"
        )
    if application_anchor != expected_application:
        errors.append(
            "application anchor="
            f"{application_anchor if application_anchor is None else f'0x{application_anchor:08X}'}、"
            f"必要値=0x{expected_application:08X}"
        )
    if except_vector_anchor != expected_except_vector:
        errors.append(
            "EXCEPTVECT="
            f"{except_vector_anchor if except_vector_anchor is None else f'0x{except_vector_anchor:08X}'}、"
            f"必要値=0x{expected_except_vector:08X}"
        )
    if reset_vector_anchor != expected_reset_vector:
        errors.append(
            "RESETVECT="
            f"{reset_vector_anchor if reset_vector_anchor is None else f'0x{reset_vector_anchor:08X}'}、"
            f"必要値=0x{expected_reset_vector:08X}"
        )
    reserved_anchors = sorted(
        f"{name}@0x{address:08X}"
        for name, address in (code_flash_anchors or {}).items()
        if main_start <= address < expected_application
    )
    if reserved_anchors:
        errors.append("header/descriptor予約域内anchor=" + ", ".join(reserved_anchors))

    detail = "; ".join(
        (
            _hex_region(main_header),
            _hex_region(main_descriptor),
            _hex_region(buffer_header),
            _hex_region(buffer_descriptor),
            f"application=0x{expected_application:08X}",
            f"vectors=0x{expected_except_vector:08X}/0x{expected_reset_vector:08X}",
        )
    )
    if errors:
        detail += "; " + "; ".join(errors)
    else:
        detail += "; linker objectsはheader/descriptor予約域外"
    return Gate("fwup_code_flash_layout", "FAIL" if errors else "PASS", detail)


def _strip_c_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\r\n]*", "", text, flags=re.DOTALL)


def _has_non_declaration_symbol_use(text: str, symbol: str) -> bool:
    clean = _strip_c_comments(text)
    for line in clean.splitlines():
        if re.search(rf"\b{re.escape(symbol)}\b", line) and not re.match(
            r"^\s*extern\b", line
        ):
            return True
    return False


def _sdio_resource_addressing_gate(sdio_text: str, resource_text: str) -> Gate:
    sdio_symbols = (
        RESOURCE_LINKER_SYMBOLS["TYPE1YN_FW_BLOB"],
        RESOURCE_LINKER_SYMBOLS["TYPE1YN_NVRAM_BLOB"],
    )
    provider_symbols = tuple(RESOURCE_LINKER_SYMBOLS.values())
    missing_sdio = [
        symbol for symbol in sdio_symbols if not _has_non_declaration_symbol_use(sdio_text, symbol)
    ]
    missing_provider = [
        symbol
        for symbol in provider_symbols
        if not _has_non_declaration_symbol_use(resource_text, symbol)
    ]
    code_flash_literals: list[str] = []
    for value in re.findall(r"0[xX][0-9A-Fa-f]+", _strip_c_comments(sdio_text)):
        numeric = int(value, 16)
        if 0xFFE00000 <= numeric <= 0xFFFFFFFF:
            code_flash_literals.append(value)
    ok = not missing_sdio and not missing_provider and not code_flash_literals
    details: list[str] = []
    if missing_sdio:
        details.append("primitive pathのlinker symbol参照なし: " + ", ".join(missing_sdio))
    if missing_provider:
        details.append("WHD resource providerの実参照なし: " + ", ".join(missing_provider))
    if code_flash_literals:
        details.append("code flash固定値あり: " + ", ".join(sorted(set(code_flash_literals))))
    if ok:
        details.append("primitive pathとWHD providerがg_type1yn_* linker symbolを実参照")
    return Gate("sdio_resource_addressing", "PASS" if ok else "FAIL", "; ".join(details))


def _whd_resources_follow_application_gate(
    anchors: dict[str, int], regions: list[Region], application_anchor: int | None
) -> Gate:
    missing_resource_anchors = sorted(set(RESOURCE_SIZE_MACROS) - anchors.keys())
    resource_areas: dict[str, str] = {}
    outside_resource_anchors: list[str] = []
    for section in RESOURCE_SIZE_MACROS:
        if section not in anchors:
            continue
        containing = [
            region.name
            for region in regions
            if region.contains(anchors[section], anchors[section] + 1)
        ]
        if len(containing) == 1:
            resource_areas[section] = containing[0]
        else:
            outside_resource_anchors.append(f"{section}@0x{anchors[section]:08X}")
    app_area = next(
        (
            region.name
            for region in regions
            if application_anchor is not None
            and region.contains(application_anchor, application_anchor + 1)
        ),
        None,
    )
    ok = (
        app_area is not None
        and not missing_resource_anchors
        and not outside_resource_anchors
        and set(resource_areas.values()) == {app_area}
        and len(resource_areas) == len(RESOURCE_SIZE_MACROS)
    )
    detail = f"application area={app_area}; WHD resource areas={resource_areas}"
    if missing_resource_anchors:
        detail += "; missing anchors=" + ", ".join(missing_resource_anchors)
    if outside_resource_anchors:
        detail += "; area外=" + ", ".join(outside_resource_anchors)
    return Gate("whd_resources_follow_application", "PASS" if ok else "FAIL", detail)


def _gitlink_sha(repo_root: Path, relative_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-tree", "HEAD", "--", relative_path.as_posix()],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    match = re.fullmatch(
        rf"160000\s+commit\s+([0-9a-f]{{40}})\t{re.escape(relative_path.as_posix())}\s*",
        result.stdout,
    )
    return match.group(1) if match else None


def _bootloader_layout_gate(repo_root: Path, provenance_manifest_path: Path | None = None) -> Gate:
    project_dir = repo_root / BOOTLOADER_PROJECT_RELATIVE
    if not project_dir.is_dir():
        return Gate(
            "bootloader_layout",
            "UNKNOWN",
            "RX671専用bootloader project/map、明示予約range、source provenanceがありません",
        )
    bsp_config = project_dir / "src/smc_gen/r_config/r_bsp_config.h"
    cproject = project_dir / ".cproject"
    compiled_target_config = project_dir / "src/rx671.h"
    canonical_target_config = repo_root / BOOTLOADER_SUBMODULE_RELATIVE / "config/rx671.h"
    if (
        not bsp_config.is_file()
        or not cproject.is_file()
        or not compiled_target_config.is_file()
        or not canonical_target_config.is_file()
    ):
        return Gate(
            "bootloader_layout",
            "FAIL",
            f"RX671 bootloader projectの必須設定不足: {project_dir}",
        )
    try:
        bsp_text = bsp_config.read_text(encoding="utf-8")
        compiled_target_lines = compiled_target_config.read_text(
            encoding="utf-8"
        ).splitlines()
        canonical_target_lines = canonical_target_config.read_text(
            encoding="utf-8"
        ).splitlines()
        mode, build_dir, artifact_name, anchors, _binaries = _parse_cproject(cproject)
    except (ET.ParseError, OSError, ValueError) as exc:
        return Gate("bootloader_layout", "FAIL", f"RX671 bootloader設定解析失敗: {exc}")
    if compiled_target_lines != canonical_target_lines:
        return Gate(
            "bootloader_layout",
            "FAIL",
            "実際にcompileするsrc/rx671.hがbootloader submoduleの"
            "config/rx671.hと一致しません",
        )
    if _macro(bsp_text, "BSP_CFG_BOOTLOADER_PROJECT") != 1 or mode != "bank.dual":
        return Gate(
            "bootloader_layout",
            "FAIL",
            "RX671 bootloaderはBSP_CFG_BOOTLOADER_PROJECT=1かつbank.dualである必要があります",
        )
    expected_anchors = {
        "PResetPRG": 0xFFFC0000,
        "EXCEPTVECT": 0xFFFFFF80,
        "RESETVECT": 0xFFFFFFFC,
    }
    wrong_anchors = [
        f"{name}={anchors.get(name)!r}"
        for name, expected in expected_anchors.items()
        if anchors.get(name) != expected
    ]
    if wrong_anchors:
        return Gate(
            "bootloader_layout",
            "FAIL",
            "RX671 bootloader linker anchor不一致: " + ", ".join(wrong_anchors),
        )
    map_path = build_dir / f"{artifact_name}.map"
    mot_path = build_dir / f"{artifact_name}.mot"
    if not map_path.is_file() or not mot_path.is_file():
        return Gate(
            "bootloader_layout",
            "UNKNOWN",
            f"RX671 bootloader map/MOTなし: {map_path}, {mot_path}",
        )
    checker = repo_root / "tools/ci/check_rx671_bootloader_layout.py"
    try:
        checked = subprocess.run(
            [
                sys.executable,
                str(checker),
                "--mot",
                str(mot_path),
                "--map",
                str(map_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return Gate("bootloader_layout", "FAIL", f"bootloader layout checker実行失敗: {exc}")
    if checked.returncode != 0:
        detail = (checked.stderr or checked.stdout).strip()
        return Gate("bootloader_layout", "FAIL", f"bootloader layout不正: {detail}")

    if provenance_manifest_path is None or not provenance_manifest_path.is_file():
        return Gate(
            "bootloader_layout",
            "UNKNOWN",
            "bootloader配置はPASSですが、application build provenanceにbootloader証跡がありません",
        )
    try:
        manifest = json.loads(provenance_manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return Gate("bootloader_layout", "FAIL", f"provenance manifest解析失敗: {exc}")

    hashes = manifest.get("sha256")
    gitlinks = manifest.get("gitlinks")
    errors: list[str] = []
    if not isinstance(hashes, dict):
        errors.append("sha256 tableなし")
        hashes = {}
    if not isinstance(gitlinks, dict):
        errors.append("gitlinks tableなし")
        gitlinks = {}
    for relative in BOOTLOADER_PROVENANCE_PATHS:
        path = repo_root / relative
        expected_hash = hashes.get(relative.as_posix())
        if not isinstance(expected_hash, str):
            errors.append(f"hashなし: {relative.as_posix()}")
        elif not path.is_file() or expected_hash.lower() != _sha256(path):
            errors.append(f"hash不一致: {relative.as_posix()}")
    parent_rx671 = repo_root / BOOTLOADER_PROJECT_RELATIVE / "src/rx671.h"
    canonical_rx671 = repo_root / BOOTLOADER_SUBMODULE_RELATIVE / "config/rx671.h"
    try:
        if not _same_text_lines(parent_rx671, canonical_rx671):
            errors.append("bootloader src/rx671.hとsubmodule config/rx671.hの内容不一致")
    except (OSError, UnicodeError) as exc:
        errors.append(f"bootloader rx671.h同期確認失敗: {exc}")
    indexed_sha = _gitlink_sha(repo_root, BOOTLOADER_SUBMODULE_RELATIVE)
    recorded_sha = gitlinks.get(BOOTLOADER_SUBMODULE_RELATIVE.as_posix())
    try:
        checkout_sha = subprocess.run(
            ["git", "-C", str(repo_root / BOOTLOADER_SUBMODULE_RELATIVE), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        checkout_sha = None
    if indexed_sha is None or recorded_sha != indexed_sha or checkout_sha != indexed_sha:
        errors.append(
            "bootloader submodule SHA不一致 "
            f"(index={indexed_sha}, checkout={checkout_sha}, manifest={recorded_sha})"
        )
    if errors:
        return Gate("bootloader_layout", "FAIL", "; ".join(errors))
    return Gate(
        "bootloader_layout",
        "PASS",
        checked.stdout.strip()
        + f"; submodule={indexed_sha}; map/MOT/config SHA-256一致",
    )


def _artifact_provenance_gate(
    *,
    repo_root: Path,
    project_dir: Path,
    map_path: Path,
    mot_path: Path,
    blob_paths: Iterable[Path],
    expected_source_sha: str | None = None,
) -> Gate:
    blob_paths = list(blob_paths)
    existing_artifacts = [path for path in (map_path, mot_path) if path.is_file()]
    if not existing_artifacts:
        return Gate("artifact_provenance", "UNKNOWN", "map/MOTがありません")
    if len(existing_artifacts) != 2:
        return Gate(
            "artifact_provenance",
            "FAIL",
            "map/MOTの一方だけが存在し、同一build成果物として検証できません",
        )
    manifest_path = map_path.parent / PROVENANCE_MANIFEST_NAME
    if not manifest_path.is_file():
        return Gate(
            "artifact_provenance",
            "UNKNOWN",
            f"provenance manifestなし: {manifest_path}",
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return Gate("artifact_provenance", "FAIL", f"manifest解析失敗: {exc}")
    source_sha = expected_source_sha or _git_head(repo_root)
    project_relative = _relative_to_repo(project_dir, repo_root)
    if source_sha is None or project_relative is None:
        return Gate(
            "artifact_provenance",
            "UNKNOWN",
            "現在のsource SHAまたはproject相対pathを導出できません",
        )
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version!=1")
    if manifest.get("source_sha") != source_sha:
        errors.append("source_sha不一致")
    if manifest.get("dirty") is not False:
        errors.append("dirty=falseではない")
    if manifest.get("project_path") != project_relative:
        errors.append("project_path不一致")
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict):
        errors.append("sha256 tableなし")
        hashes = {}
    required_paths = [project_dir / relative for relative in PROVENANCE_CONFIG_PATHS]
    required_paths.extend((map_path, mot_path))
    required_paths.extend(path for path in blob_paths if path.is_file())
    missing_blob_paths = [path for path in blob_paths if not path.is_file()]
    if len(blob_paths) != len(RESOURCE_SIZE_MACROS):
        errors.append(
            f"WHD blob path数={len(blob_paths)}、必要数={len(RESOURCE_SIZE_MACROS)}"
        )
    if missing_blob_paths:
        errors.append("WHD blob実ファイル不足")
    for path in required_paths:
        relative = _relative_to_repo(path, repo_root)
        if relative is None:
            errors.append(f"repo外path: {path}")
            continue
        expected_hash = hashes.get(relative)
        if not isinstance(expected_hash, str):
            errors.append(f"hashなし: {relative}")
            continue
        try:
            actual_hash = _sha256(path)
        except OSError:
            errors.append(f"fileなし: {relative}")
            continue
        if expected_hash.lower() != actual_hash:
            errors.append(f"hash不一致: {relative}")
    if errors:
        return Gate("artifact_provenance", "FAIL", "; ".join(errors))
    return Gate(
        "artifact_provenance",
        "PASS",
        f"source={source_sha}; project={project_relative}; config/map/MOT/blob SHA-256一致",
    )


def _rsu_image_gate(
    *,
    repo_root: Path,
    rsu_path: Path | None,
    signer_certificate_path: Path | None,
    expected_version: str | None,
    provenance_manifest_path: Path,
) -> Gate:
    provided = (
        rsu_path is not None,
        signer_certificate_path is not None,
        expected_version is not None,
    )
    if not any(provided):
        return Gate(
            "rsu_image",
            "UNKNOWN",
            "RSU、signer certificate、expected versionが指定されていません",
        )
    if not all(provided):
        return Gate(
            "rsu_image",
            "FAIL",
            "RSU検証には--rsu、--signer-certificate、--expected-versionがすべて必要です",
        )
    assert rsu_path is not None
    assert signer_certificate_path is not None
    assert expected_version is not None
    if not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)",
        expected_version,
    ):
        return Gate("rsu_image", "FAIL", f"expected version形式不正: {expected_version!r}")
    if not rsu_path.is_file() or not signer_certificate_path.is_file():
        return Gate(
            "rsu_image",
            "FAIL",
            f"RSU/certificateなし: {rsu_path}, {signer_certificate_path}",
        )
    if not provenance_manifest_path.is_file():
        return Gate(
            "rsu_image",
            "FAIL",
            f"RSU provenance manifestなし: {provenance_manifest_path}",
        )

    errors: list[str] = []
    try:
        image = rsu_path.read_bytes()
        certificate_bytes = signer_certificate_path.read_bytes()
        manifest = json.loads(provenance_manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return Gate("rsu_image", "FAIL", f"RSU入力解析失敗: {exc}")

    if len(image) != FWUP_AREA_SIZE:
        errors.append(f"size={len(image)} (expected={FWUP_AREA_SIZE})")
    if len(image) < FWUP_APPLICATION_OFFSET:
        return Gate(
            "rsu_image",
            "FAIL",
            f"RSUがheader+descriptorより短い: {len(image)} bytes",
        )

    if image[0:7] != b"Renesas":
        errors.append("magic!=Renesas")
    if image[7] != 0xFE:
        errors.append(f"image_flag=0x{image[7]:02X} (expected=0xFE)")
    signature_type_field = image[0x08:0x28]
    expected_signature_type_field = FWUP_SIGNATURE_TYPE.ljust(32, b"\x00")
    if signature_type_field != expected_signature_type_field:
        errors.append("signature_type!=sig-sha256-ecdsa")
    signature_size = struct.unpack_from("<I", image, 0x28)[0]
    if signature_size != FWUP_RAW_P256_SIGNATURE_SIZE:
        errors.append(
            f"signature_size={signature_size} "
            f"(expected={FWUP_RAW_P256_SIGNATURE_SIZE})"
        )
    signature = image[0x2C : 0x2C + FWUP_RAW_P256_SIGNATURE_SIZE]
    if image[0x2C + FWUP_RAW_P256_SIGNATURE_SIZE : 0x12C] != b"\x00" * (
        0x100 - FWUP_RAW_P256_SIGNATURE_SIZE
    ):
        errors.append("signature reserved fieldがzeroではない")
    data_flash_flag = struct.unpack_from("<I", image, 0x12C)[0]
    data_flash_start = struct.unpack_from("<I", image, 0x130)[0]
    data_flash_end = struct.unpack_from("<I", image, 0x134)[0]
    if (
        data_flash_flag != 0
        or data_flash_start != 0xFFFFFFFF
        or data_flash_end != 0xFFFFFFFF
    ):
        errors.append(
            "Data Flash payloadが無効化されていない "
            f"(flag={data_flash_flag}, start=0x{data_flash_start:08X}, "
            f"end=0x{data_flash_end:08X})"
        )
    if image[0x138:FWUP_HEADER_SIZE] != b"\xFF" * (FWUP_HEADER_SIZE - 0x138):
        errors.append("header reserved tailが0xFFではない")

    descriptor = image[FWUP_HEADER_SIZE:FWUP_APPLICATION_OFFSET]
    segment_count, segment_start, segment_size = struct.unpack_from(
        "<III", descriptor, 0
    )
    if segment_count != 1:
        errors.append(f"descriptor segments={segment_count} (expected=1)")
    if segment_start != FWUP_APPLICATION_START:
        errors.append(
            f"segment start=0x{segment_start:08X} "
            f"(expected=0x{FWUP_APPLICATION_START:08X})"
        )
    if segment_size != FWUP_APPLICATION_SIZE:
        errors.append(
            f"segment size={segment_size} (expected={FWUP_APPLICATION_SIZE})"
        )
    if descriptor[12:] != b"\xFF" * (FWUP_DESCRIPTOR_SIZE - 12):
        errors.append("descriptorの未使用領域が0xFFではない")
    segment_end = segment_start + segment_size
    if (
        segment_start < FWUP_AREA_START + FWUP_APPLICATION_OFFSET
        or segment_end > FWUP_AREA_START + FWUP_AREA_SIZE
    ):
        errors.append(
            f"segmentが768 KiB install area外: "
            f"0x{segment_start:08X}-0x{segment_end - 1:08X}"
        )

    marker = OTA_VERSION_MARKER_PREFIX + expected_version.encode("ascii") + b"\x00"
    marker_prefix_count = image.count(OTA_VERSION_MARKER_PREFIX)
    if marker_prefix_count != 1 or image.count(marker) != 1:
        errors.append(
            f"OTA version marker不一致: expected={expected_version}, "
            f"prefix_count={marker_prefix_count}"
        )

    try:
        from cryptography import x509
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils

        certificate = x509.load_pem_x509_certificate(certificate_bytes)
        public_key = certificate.public_key()
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
            public_key.curve, ec.SECP256R1
        ):
            errors.append("signer certificateはECDSA P-256ではない")
        elif len(signature) != FWUP_RAW_P256_SIGNATURE_SIZE:
            errors.append("raw P-256 signature長不正")
        else:
            r = int.from_bytes(signature[:32], "big")
            s = int.from_bytes(signature[32:], "big")
            public_key.verify(
                utils.encode_dss_signature(r, s),
                image[FWUP_HEADER_SIZE:],
                ec.ECDSA(hashes.SHA256()),
            )
    except ImportError as exc:
        errors.append(f"cryptography packageなし: {exc}")
    except (TypeError, ValueError) as exc:
        errors.append(f"signer certificate/signature解析失敗: {exc}")
    except InvalidSignature:
        errors.append("descriptor+payload ECDSA署名不一致")

    rsu_relative = _relative_to_repo(rsu_path, repo_root)
    certificate_relative = _relative_to_repo(signer_certificate_path, repo_root)
    hashes_table = manifest.get("sha256")
    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version!=1")
    if manifest.get("profile") != OTA_PROFILE_NAME:
        errors.append(f"manifest profile!={OTA_PROFILE_NAME}")
    if manifest.get("ota_image_version") != expected_version:
        errors.append("manifest ota_image_version不一致")
    if rsu_relative is None or manifest.get("rsu_path") != rsu_relative:
        errors.append("manifest rsu_path不一致")
    if (
        certificate_relative is None
        or manifest.get("signer_certificate_path") != certificate_relative
    ):
        errors.append("manifest signer_certificate_path不一致")
    if not isinstance(hashes_table, dict):
        errors.append("manifest sha256 tableなし")
        hashes_table = {}
    for relative, path in (
        (rsu_relative, rsu_path),
        (certificate_relative, signer_certificate_path),
    ):
        if relative is None:
            continue
        expected_hash = hashes_table.get(relative)
        if not isinstance(expected_hash, str):
            errors.append(f"manifest hashなし: {relative}")
        elif expected_hash.lower() != _sha256(path):
            errors.append(f"manifest hash不一致: {relative}")

    if errors:
        return Gate("rsu_image", "FAIL", "; ".join(errors))
    return Gate(
        "rsu_image",
        "PASS",
        f"size={len(image)}; segment=0x{segment_start:08X}-"
        f"0x{segment_end - 1:08X}; Data Flashなし; version={expected_version}; "
        "descriptor+payload ECDSA P-256署名とprovenance一致",
    )


def analyze(
    project_dir: Path,
    build_dir_override: Path | None = None,
    rsu_path: Path | None = None,
    signer_certificate_path: Path | None = None,
    expected_version: str | None = None,
) -> list[Gate]:
    gates: list[Gate] = []
    repo_root = project_dir.parents[2]
    cproject = project_dir / ".cproject"
    fwup_config = project_dir / "src/frtos_config/r_fwup_config.h"
    littlefs_config = project_dir / "src/frtos_config/rm_littlefs_flash_config.h"
    bsp_config = project_dir / "src/smc_gen/r_config/r_bsp_config.h"
    mcu_info = project_dir / "src/smc_gen/r_bsp/mcu/rx671/mcu_info.h"
    resource_source = project_dir / "src/whd_port/whd_port_resource.c"
    sdio_host = project_dir / "src/sdio_host.c"
    flash_target = project_dir / "src/smc_gen/r_flash_rx/src/targets/rx671/r_flash_rx671.h"
    layout_contract = project_dir / LAYOUT_CONTRACT_NAME
    bootloader_config = (
        repo_root
        / "Projects/boot_loader_rx671_ek/e2studio_ccrx/lib/rx_bootloader/config/rx671.h"
    )
    littlefs_target = (
        repo_root / "Common/littlefs_common/rm_littlefs_df/targets/rx65n/rm_littlefs_df_rx65n.h"
    )

    required = [
        cproject,
        fwup_config,
        littlefs_config,
        bsp_config,
        mcu_info,
        resource_source,
        sdio_host,
        flash_target,
        layout_contract,
        littlefs_target,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return [Gate("source_inputs", "FAIL", "必須ファイルなし: " + ", ".join(missing))]

    try:
        mode, configured_build_dir, artifact_name, anchors, binaries = _parse_cproject(cproject)
        cproject_text = cproject.read_text(encoding="utf-8")
        fwup_text = fwup_config.read_text(encoding="utf-8")
        littlefs_text = littlefs_config.read_text(encoding="utf-8")
        bsp_text = bsp_config.read_text(encoding="utf-8")
        mcu_info_text = mcu_info.read_text(encoding="utf-8")
        declared_sizes = _parse_declared_resource_sizes(resource_source)
        resource_text = resource_source.read_text(encoding="utf-8")
        sdio_text = sdio_host.read_text(encoding="utf-8")
        flash_target_text = flash_target.read_text(encoding="utf-8")
        littlefs_target_text = littlefs_target.read_text(encoding="utf-8")
    except (ET.ParseError, OSError, ValueError) as exc:
        return [Gate("source_inputs", "FAIL", f"設定解析失敗: {exc}")]
    gates.append(Gate("source_inputs", "PASS", "CC-RX/BSP/FWUP/WHD設定を解析しました"))
    gates.append(
        _mqtt_ota_buffer_gate(
            block_size=_cproject_integer_define(
                cproject_text, "mqttFileDownloader_CONFIG_BLOCK_SIZE"
            ),
            network_buffer_size=_cproject_integer_define(
                cproject_text, "MQTT_AGENT_NETWORK_BUFFER_SIZE"
            ),
        )
    )
    build_dir = build_dir_override or configured_build_dir
    gates.append(
        _bootloader_layout_gate(
            repo_root,
            build_dir / PROVENANCE_MANIFEST_NAME,
        )
    )

    rom_size = _memory_size_for_selected_part(bsp_text, mcu_info_text, "BSP_ROM_SIZE_BYTES")
    ram_size = _memory_size_for_selected_part(bsp_text, mcu_info_text, "BSP_RAM_SIZE_BYTES")
    if rom_size is None:
        gates.append(Gate("rom_capacity", "UNKNOWN", "選択MCUのBSP_ROM_SIZE_BYTESを導出できません"))
        return gates
    flash_start = ADDRESS_SPACE_END - rom_size
    gates.append(
        Gate(
            "rom_capacity",
            "PASS",
            f"BSP生成物: {rom_size} bytes, 0x{flash_start:08X}-0xFFFFFFFF",
        )
    )

    data_flash_size = _memory_size_for_selected_part(
        bsp_text, mcu_info_text, "BSP_DATA_FLASH_SIZE_BYTES"
    )
    df_start = _macro(fwup_text, "FWUP_CFG_DF_ADDR_L")
    df_block_size = _macro(fwup_text, "FWUP_CFG_DF_BLK_SIZE")
    df_block_count = _macro(fwup_text, "FWUP_CFG_DF_NUM_BLKS")
    df_base_match = re.search(
        r"\bFLASH_DF_BLOCK_0\s*=\s*(0[xX][0-9A-Fa-f]+)", flash_target_text
    )
    target_df_start = _parse_c_integer(df_base_match.group(1)) if df_base_match else None
    fit_df_block_size = _macro(flash_target_text, "FLASH_DF_BLOCK_SIZE")
    fit_df_block_count = _macro(flash_target_text, "FLASH_NUM_BLOCKS_DF")
    fit_df_program_size = _macro(flash_target_text, "FLASH_DF_MIN_PGM_SIZE")
    littlefs_target_start = _macro(littlefs_target_text, "FLASH_DF_BLOCK_0_MACRO")
    littlefs_start = _resolve_numeric_macro(
        littlefs_text,
        "RM_LITTLEFS_FLASH_DATA_START",
        {"FLASH_DF_BLOCK_0_MACRO": littlefs_target_start}
        if littlefs_target_start is not None
        else {},
    )
    littlefs_block_size = _macro(littlefs_text, "LFS_FLASH_BLOCK_SIZE")
    littlefs_block_count = _macro(littlefs_text, "LFS_FLASH_BLOCK_COUNT")
    littlefs_program_size = _macro(littlefs_text, "LFS_FLASH_PROGRAM_SIZE")
    raw_data_flash_consumers: list[Region] = []
    if target_df_start is not None and data_flash_size is not None:
        target_df_end = target_df_start + data_flash_size
        raw_data_flash_consumers = [
            Region(f"linker:{name}", address, 1)
            for name, address in anchors.items()
            if name != LITTLEFS_LINKER_SECTION
            and target_df_start <= address < target_df_end
        ]
    gates.append(
        _fwup_data_flash_geometry_gate(
            bsp_size=data_flash_size,
            fwup_start=df_start,
            fwup_block_size=df_block_size,
            fwup_block_count=df_block_count,
            fit_start=target_df_start,
            fit_block_size=fit_df_block_size,
            fit_block_count=fit_df_block_count,
        )
    )
    gates.append(
        _littlefs_data_flash_geometry_gate(
            data_flash_start=target_df_start,
            data_flash_size=data_flash_size,
            fit_erase_size=fit_df_block_size,
            fit_program_size=fit_df_program_size,
            littlefs_start=littlefs_start,
            littlefs_block_size=littlefs_block_size,
            littlefs_block_count=littlefs_block_count,
            littlefs_program_size=littlefs_program_size,
        )
    )
    littlefs_size = (
        littlefs_block_size * littlefs_block_count
        if littlefs_block_size is not None and littlefs_block_count is not None
        else None
    )
    ownership_gate = _data_flash_ownership_contract_gate(
        contract_path=layout_contract,
        bootloader_config_path=bootloader_config,
        data_flash_start=target_df_start,
        data_flash_size=data_flash_size,
        littlefs_start=littlefs_start,
        littlefs_size=littlefs_size,
    )
    gates.append(ownership_gate)
    gates.append(
        _data_flash_non_overlap_gate(
            data_flash_start=target_df_start,
            data_flash_size=data_flash_size,
            littlefs_start=littlefs_start,
            littlefs_block_size=littlefs_block_size,
            littlefs_block_count=littlefs_block_count,
            consumer_ranges=raw_data_flash_consumers,
            consumer_layout_complete=ownership_gate.status == "PASS",
        )
    )

    main_start = _macro(fwup_text, "FWUP_CFG_MAIN_AREA_ADDR_L")
    buffer_start = _macro(fwup_text, "FWUP_CFG_BUF_AREA_ADDR_L")
    area_size = _macro(fwup_text, "FWUP_CFG_AREA_SIZE")
    if None in (main_start, buffer_start, area_size):
        gates.append(Gate("fwup_partition", "UNKNOWN", "FWUP領域macroをすべて解析できません"))
        return gates
    assert main_start is not None and buffer_start is not None and area_size is not None
    regions = [Region("main", main_start, area_size), Region("buffer", buffer_start, area_size)]
    gates.append(
        _fwup_partition_gate(
            flash_start=flash_start,
            flash_size=rom_size,
            main_start=main_start,
            buffer_start=buffer_start,
            area_size=area_size,
        )
    )

    bsp_bank_mode = _macro(bsp_text, "BSP_CFG_CODE_FLASH_BANK_MODE")
    dual_ok = mode == "bank.dual" and bsp_bank_mode == 0
    gates.append(
        Gate(
            "dual_bank_mode",
            "PASS" if dual_ok else "FAIL",
            f".cproject modes={mode or '(empty)'}, BSP_CFG_CODE_FLASH_BANK_MODE={bsp_bank_mode!r}; "
            "必要値は bank.dual / 0(Dual mode)",
        )
    )

    application_anchor = anchors.get("PResetPRG", anchors.get("P"))
    if application_anchor is None:
        gates.append(Gate("application_in_main_area", "UNKNOWN", "PResetPRG/Pのlinker anchorなし"))
    else:
        in_main = regions[0].contains(application_anchor, application_anchor + 1)
        gates.append(
            Gate(
                "application_in_main_area",
                "PASS" if in_main else "FAIL",
                f"application anchor=0x{application_anchor:08X}; {_hex_region(regions[0])}",
            )
        )

    code_flash_anchors = {
        name: address for name, address in anchors.items() if flash_start <= address < ADDRESS_SPACE_END
    }
    anchor_areas: set[str] = set()
    outside_anchors: list[str] = []
    for name, address in code_flash_anchors.items():
        containing = [region.name for region in regions if region.contains(address, address + 1)]
        if len(containing) == 1:
            anchor_areas.add(containing[0])
        else:
            outside_anchors.append(f"{name}@0x{address:08X}")
    anchors_ok = len(anchor_areas) == 1 and not outside_anchors
    gates.append(
        Gate(
            "static_image_single_area",
            "PASS" if anchors_ok else "FAIL",
            f"code-flash anchor areas={sorted(anchor_areas)}"
            + (f"; outside={outside_anchors}" if outside_anchors else ""),
        )
    )

    gates.append(_whd_resources_follow_application_gate(anchors, regions, application_anchor))

    gates.append(_sdio_resource_addressing_gate(sdio_text, resource_text))

    gates.append(
        _fwup_code_flash_layout_gate(
            main_start=main_start,
            buffer_start=buffer_start,
            area_size=area_size,
            application_anchor=application_anchor,
            except_vector_anchor=anchors.get("EXCEPTVECT"),
            reset_vector_anchor=anchors.get("RESETVECT"),
            code_flash_anchors=code_flash_anchors,
        )
    )

    blob_details: list[str] = []
    blob_missing: list[str] = []
    blob_mismatch: list[str] = []
    blob_paths: list[Path] = []
    for section, macro_name in RESOURCE_SIZE_MACROS.items():
        expected = declared_sizes.get(section)
        raw_path = binaries.get(section)
        if expected is None or raw_path is None:
            blob_missing.append(f"{section}(宣言または-binary設定なし)")
            continue
        # -binary paths are relative to the managed-build directory recorded
        # in .cproject, even when --build-dir redirects map/MOT validation.
        path = (configured_build_dir / Path(raw_path.replace("\\", "/"))).resolve()
        blob_paths.append(path)
        if not path.is_file():
            blob_missing.append(str(path))
            continue
        actual = path.stat().st_size
        blob_details.append(f"{section}={actual} bytes")
        if actual != expected:
            blob_mismatch.append(f"{section}: actual={actual}, declared={expected}({macro_name})")
    map_path = build_dir / f"{artifact_name}.map"
    mot_path = build_dir / f"{artifact_name}.mot"
    provenance_gate = _artifact_provenance_gate(
        repo_root=repo_root,
        project_dir=project_dir,
        map_path=map_path,
        mot_path=mot_path,
        blob_paths=blob_paths,
    )
    gates.append(provenance_gate)
    gates.append(
        _rsu_image_gate(
            repo_root=repo_root,
            rsu_path=rsu_path,
            signer_certificate_path=signer_certificate_path,
            expected_version=expected_version,
            provenance_manifest_path=build_dir / PROVENANCE_MANIFEST_NAME,
        )
    )
    if blob_mismatch:
        gates.append(Gate("whd_blob_sizes", "FAIL", "; ".join(blob_mismatch)))
    elif blob_missing:
        gates.append(
            Gate(
                "whd_blob_sizes",
                "UNKNOWN",
                "実ファイルを測定できません: " + "; ".join(blob_missing),
            )
        )
    else:
        gates.append(
            Gate(
                "whd_blob_sizes",
                "PASS" if provenance_gate.status == "PASS" else "UNKNOWN",
                "; ".join(blob_details)
                + (
                    ""
                    if provenance_gate.status == "PASS"
                    else f"; artifact_provenance={provenance_gate.status}のため確定値にしません"
                ),
            )
        )

    if not map_path.is_file():
        gates.append(
            _ram_capacity_gate(
                sections=None,
                ram_size=ram_size,
                data_flash_start=target_df_start,
            )
        )
        gates.append(Gate("map_image_single_area", "UNKNOWN", f"mapなし: {map_path}"))
    else:
        try:
            map_sections = _parse_map_sections(map_path)
            ram_gate = _ram_capacity_gate(
                sections=map_sections,
                ram_size=ram_size,
                data_flash_start=target_df_start,
            )
            if ram_gate.status == "PASS" and provenance_gate.status != "PASS":
                ram_gate = Gate(
                    ram_gate.name,
                    "UNKNOWN",
                    ram_gate.detail
                    + f"; artifact_provenance={provenance_gate.status}のため現行source証跡にしません",
                )
            gates.append(ram_gate)
            map_ranges = [(section.start, section.end) for section in map_sections.values() if section.size]
            areas, byte_count, outside = _classify_ranges(map_ranges, regions, flash_start)
            map_size_errors = [
                f"{name}: map={map_sections[name].size}, declared={declared_sizes[name]}"
                for name in RESOURCE_SIZE_MACROS
                if name in map_sections
                and name in declared_sizes
                and map_sections[name].size != declared_sizes[name]
            ]
            ok = len(areas) == 1 and not outside and not map_size_errors
            detail = f"code-flash section bytes={byte_count}; areas={sorted(areas)}"
            if outside:
                detail += f"; area外/境界跨ぎ={len(outside)}"
            if map_size_errors:
                detail += "; " + "; ".join(map_size_errors)
            if provenance_gate.status == "PASS":
                status = "PASS" if ok else "FAIL"
            else:
                status = "UNKNOWN"
                detail += (
                    f"; structure={'PASS' if ok else 'FAIL'}だが"
                    f"artifact_provenance={provenance_gate.status}のため現行source証跡にしません"
                )
            gates.append(Gate("map_image_single_area", status, detail))
        except (OSError, ValueError) as exc:
            gates.append(Gate("ram_capacity", "FAIL", f"map解析失敗: {exc}"))
            gates.append(Gate("map_image_single_area", "FAIL", f"map解析失敗: {exc}"))

    if not mot_path.is_file():
        gates.append(Gate("mot_image_single_area", "UNKNOWN", f"MOTなし: {mot_path}"))
    else:
        try:
            mot_ranges = _parse_srecord_ranges(mot_path)
            areas, byte_count, outside = _classify_ranges(mot_ranges, regions, flash_start)
            ok = len(areas) == 1 and not outside
            detail = f"code-flash load bytes={byte_count}; areas={sorted(areas)}"
            if outside:
                detail += f"; area外/境界跨ぎ={len(outside)}"
            if provenance_gate.status == "PASS":
                status = "PASS" if ok else "FAIL"
            else:
                status = "UNKNOWN"
                detail += (
                    f"; structure={'PASS' if ok else 'FAIL'}だが"
                    f"artifact_provenance={provenance_gate.status}のため現行source証跡にしません"
                )
            gates.append(Gate("mot_image_single_area", status, detail))
        except (OSError, UnicodeError, ValueError) as exc:
            gates.append(Gate("mot_image_single_area", "FAIL", f"MOT解析失敗: {exc}"))

    return gates


def exit_code(gates: Iterable[Gate]) -> int:
    statuses = {gate.status for gate in gates}
    if "FAIL" in statuses:
        return 1
    if "UNKNOWN" in statuses:
        return 2
    return 0


def _default_project_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "Projects/aws_wifi_rx671_ek/e2studio_ccrx"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=_default_project_dir())
    parser.add_argument(
        "--build-dir",
        type=Path,
        help="map/MOT/provenanceの配置先。省略時は.cprojectのbuildPathを使用",
    )
    parser.add_argument("--rsu", type=Path, help="検証するRX671 FWUP v2 RSU")
    parser.add_argument(
        "--signer-certificate",
        type=Path,
        help="RSU署名検証に使うPEM X.509 certificate",
    )
    parser.add_argument(
        "--expected-version",
        help="RSU内で要求するRX671_OTA_IMAGE_VERSION=x.y.z",
    )
    parser.add_argument("--json", action="store_true", help="機械可読JSONを出力")
    args = parser.parse_args(argv)

    gates = analyze(
        args.project_dir.resolve(),
        args.build_dir.resolve() if args.build_dir else None,
        args.rsu.resolve() if args.rsu else None,
        args.signer_certificate.resolve() if args.signer_certificate else None,
        args.expected_version,
    )
    code = exit_code(gates)
    if args.json:
        print(json.dumps({"exit_code": code, "gates": [asdict(gate) for gate in gates]}, ensure_ascii=False, indent=2))
    else:
        for gate in gates:
            print(f"[{gate.status:7}] {gate.name}: {gate.detail}")
        print(f"RESULT: {'PASS' if code == 0 else 'BLOCKED'} (exit={code})")
    return code


if __name__ == "__main__":
    sys.exit(main())

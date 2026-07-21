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
PROVENANCE_CONFIG_PATHS = (
    ".cproject",
    "src/frtos_config/r_fwup_config.h",
    "src/frtos_config/rm_littlefs_flash_config.h",
    "src/smc_gen/r_config/r_bsp_config.h",
    "src/sdio_host.c",
    "src/whd_port/whd_port_resource.c",
)
PROVENANCE_MANIFEST_NAME = "ota-layout-provenance.json"


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
    artifact_name = "aws_wifi_rx671_ek"
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

    remaining_bytes = data_flash_size - (littlefs_end - littlefs_start)
    if remaining_bytes <= 0:
        return Gate(
            "data_flash_non_overlap",
            "FAIL",
            f"LittleFS=0x{littlefs_start:08X}-0x{littlefs_end - 1:08X}が"
            f"data flash全{data_flash_size} bytesを占有し、FWUP control/mirror/"
            "user-app metadataとbootloader key用の独立領域がありません",
        )

    ranges = list(consumer_ranges)
    if not consumer_layout_complete:
        return Gate(
            "data_flash_non_overlap",
            "UNKNOWN",
            f"LittleFS外に{remaining_bytes} bytesありますが、FWUP control/mirror/"
            "user-app metadataとbootloader keyの実測rangeが未確定です",
        )

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
    if errors:
        detail += "; " + "; ".join(errors)
    return Gate("data_flash_non_overlap", "FAIL" if errors else "PASS", detail)


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


def _bootloader_layout_gate(repo_root: Path) -> Gate:
    project_dir = repo_root / "Projects/boot_loader_rx671_ek/e2studio_ccrx"
    if not project_dir.is_dir():
        return Gate(
            "bootloader_layout",
            "UNKNOWN",
            "RX671専用bootloader project/map、明示予約range、source provenanceがありません",
        )
    bsp_config = project_dir / "src/smc_gen/r_config/r_bsp_config.h"
    cproject = project_dir / ".cproject"
    if not bsp_config.is_file() or not cproject.is_file():
        return Gate(
            "bootloader_layout",
            "FAIL",
            f"RX671 bootloader projectの必須設定不足: {project_dir}",
        )
    try:
        bsp_text = bsp_config.read_text(encoding="utf-8")
        mode, build_dir, artifact_name, _anchors, _binaries = _parse_cproject(cproject)
    except (ET.ParseError, OSError, ValueError) as exc:
        return Gate("bootloader_layout", "FAIL", f"RX671 bootloader設定解析失敗: {exc}")
    if _macro(bsp_text, "BSP_CFG_BOOTLOADER_PROJECT") != 1 or mode != "bank.dual":
        return Gate(
            "bootloader_layout",
            "FAIL",
            "RX671 bootloaderはBSP_CFG_BOOTLOADER_PROJECT=1かつbank.dualである必要があります",
        )
    map_path = build_dir / f"{artifact_name}.map"
    if not map_path.is_file():
        return Gate("bootloader_layout", "UNKNOWN", f"RX671 bootloader mapなし: {map_path}")
    return Gate(
        "bootloader_layout",
        "UNKNOWN",
        "bootloader mapはありますが、明示予約range・複製配置・source provenance検証が未実装です",
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


def analyze(project_dir: Path, build_dir_override: Path | None = None) -> list[Gate]:
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
        littlefs_target,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return [Gate("source_inputs", "FAIL", "必須ファイルなし: " + ", ".join(missing))]

    try:
        mode, configured_build_dir, artifact_name, anchors, binaries = _parse_cproject(cproject)
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
    gates.append(_bootloader_layout_gate(repo_root))

    rom_size = _memory_size_for_selected_part(bsp_text, mcu_info_text, "BSP_ROM_SIZE_BYTES")
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
    gates.append(
        _data_flash_non_overlap_gate(
            data_flash_start=target_df_start,
            data_flash_size=data_flash_size,
            littlefs_start=littlefs_start,
            littlefs_block_size=littlefs_block_size,
            littlefs_block_count=littlefs_block_count,
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
    ordered = sorted(regions, key=lambda region: region.start)
    partition_ok = (
        area_size > 0
        and ordered[0].start == flash_start
        and ordered[0].end == ordered[1].start
        and ordered[1].end == ADDRESS_SPACE_END
    )
    gates.append(
        Gate(
            "fwup_partition",
            "PASS" if partition_ok else "FAIL",
            "; ".join(_hex_region(region) for region in regions)
            + ("; 2領域でコードフラッシュ全体を被覆" if partition_ok else "; 連続2分割になっていません"),
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

    required_fwup_sections = {
        "C_FIRMWARE_UPDATE_CONTROL_BLOCK",
        "C_FIRMWARE_UPDATE_CONTROL_BLOCK_MIRROR",
        "C_USER_APPLICATION_AREA",
    }
    missing_fwup_sections = sorted(required_fwup_sections - anchors.keys())
    gates.append(
        Gate(
            "fwup_control_sections",
            "FAIL" if missing_fwup_sections else "PASS",
            (
                "linker -startに不足: " + ", ".join(missing_fwup_sections)
                if missing_fwup_sections
                else "FWUP管理・ユーザー領域sectionあり"
            ),
        )
    )

    build_dir = build_dir_override or configured_build_dir
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
        path = (build_dir / Path(raw_path.replace("\\", "/"))).resolve()
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
        gates.append(Gate("map_image_single_area", "UNKNOWN", f"mapなし: {map_path}"))
    else:
        try:
            map_sections = _parse_map_sections(map_path)
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
        help="map/MOTと-binary相対パスの基準。省略時は.cprojectのbuildPathを使用",
    )
    parser.add_argument("--json", action="store_true", help="機械可読JSONを出力")
    args = parser.parse_args(argv)

    gates = analyze(args.project_dir.resolve(), args.build_dir.resolve() if args.build_dir else None)
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

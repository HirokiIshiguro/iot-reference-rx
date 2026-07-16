#!/usr/bin/env python3
"""Verify the pinned RX72N custom TSIP FIT integration."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


EXPECTED_VERSION = "1.23.saffti-custom"
EXPECTED_FILE_COUNT = 271
EXPECTED_B25_WAITS = 1780


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_pattern(text: str, pattern: str, label: str) -> None:
    require(re.search(pattern, text, re.MULTILINE) is not None, f"missing {label}")


def check(root: Path) -> dict[str, int | str]:
    project = root / "Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx"
    driver = project / "src/smc_gen/r_tsip_rx"
    target = driver / "src/targets/rx72m_rx72n_rx66n"
    ip = target / "ip"
    config_path = project / "src/smc_gen/r_config/r_tsip_rx_config.h"
    scfg_path = project / "aws_ether_rx72n_envision_kit_tsip.scfg"
    qe_path = project / ".settings/com.renesas.smc.e2studio.qe.xml"

    # FIT PDF manuals live below doc/ in the source package, but this repository
    # intentionally ignores generated/bundled PDFs. Verify the checked-in
    # driver payload that is present in clean CI clones.
    files = sorted(
        path
        for path in driver.rglob("*")
        if path.is_file() and path.relative_to(driver).parts[0] != "doc"
    )
    require(
        len(files) == EXPECTED_FILE_COUNT,
        f"driver file count: expected {EXPECTED_FILE_COUNT}, found {len(files)}",
    )

    interface = (driver / "r_tsip_rx_if.h").read_text(encoding="utf-8")
    require_pattern(interface, r"^#define\s+TSIP_VERSION_MAJOR\s+\(1u\)$", "TSIP major version 1")
    require_pattern(interface, r"^#define\s+TSIP_VERSION_MINOR\s+\(23u\)$", "TSIP minor version 23")

    config = config_path.read_text(encoding="utf-8")
    require_pattern(config, r"^#define\s+TSIP_MULTI_THREADING\s+\(1\)$", "TSIP_MULTI_THREADING=1")
    require_pattern(
        config,
        r"^#define\s+TSIP_MULTI_THREADING_LOCK_FUNCTION\s+\(user_lock_function\)$",
        "TSIP lock callback",
    )
    require_pattern(
        config,
        r"^#define\s+TSIP_MULTI_THREADING_UNLOCK_FUNCTION\s+\(user_unlock_function\)$",
        "TSIP unlock callback",
    )
    require_pattern(
        config,
        r"^#define\s+TSIP_CFG_WAIT_LOOP_HOOK_ENABLE\s+\(0\)$",
        "disabled TSIP wait hook",
    )
    require_pattern(
        config,
        r"^#define\s+TSIP_CFG_WAIT_LOOP_HOOK_FUNCTION\s+\(vTsipWaitLoopHook\)$",
        "TSIP wait-hook callback",
    )

    scfg_root = ET.parse(scfg_path).getroot()
    components = [node for node in scfg_root.iter("component") if node.get("display") == "r_tsip_rx"]
    require(
        len(components) == 1,
        f"Smart Configurator TSIP components: expected 1, found {len(components)}",
    )
    component = components[0]
    require(component.get("id") == f"r_tsip_rx{EXPECTED_VERSION}", "Smart Configurator TSIP component id")
    require(component.get("version") == EXPECTED_VERSION, "Smart Configurator TSIP component version")
    grid = {node.get("id"): node.get("selectedIndex") for node in component.findall("gridItem")}
    require(len(grid) == 74, f"Smart Configurator TSIP settings: expected 74, found {len(grid)}")
    require(grid.get("TSIP_MULTI_THREADING") == "1", "Smart Configurator TSIP_MULTI_THREADING")
    require(grid.get("TSIP_CFG_WAIT_LOOP_HOOK_ENABLE") == "0", "Smart Configurator wait-hook mode")

    qe_root = ET.parse(qe_path).getroot()
    segments = [node for node in qe_root.iter("Segment") if node.get("id") == "r_tsip_rx"]
    require(len(segments) == 1, f"QE TSIP segments: expected 1, found {len(segments)}")
    segment = segments[0]
    require(segment.get("component") == f"r_tsip_rx{EXPECTED_VERSION}", "QE TSIP component version")
    settings = {node.get("id"): node.get("value") for node in segment.findall("Setting")}
    require(len(settings) == 74, f"QE TSIP settings: expected 74, found {len(settings)}")
    require(settings.get("TSIP_MULTI_THREADING") == "1", "QE TSIP_MULTI_THREADING")
    require(settings.get("TSIP_CFG_WAIT_LOOP_HOOK_ENABLE") == "0", "QE wait-hook mode")

    b25_waits = 0
    hook_calls = 0
    for source in ip.glob("*.c"):
        text = source.read_text(encoding="utf-8")
        b25_waits += text.count("TSIP.REG_00H.BIT.B25")
        hook_calls += text.count("TSIP_PRV_WAIT_LOOP_HOOK();")
    require(
        b25_waits == EXPECTED_B25_WAITS,
        f"REG_00H.B25 waits: expected {EXPECTED_B25_WAITS}, found {b25_waits}",
    )
    require(hook_calls == b25_waits, f"wait-hook coverage: expected {b25_waits}, found {hook_calls}")

    private_header = (target / "r_tsip_rx_private.h").read_text(encoding="utf-8")
    require("#define TSIP_PRV_WAIT_LOOP_HOOK()" in private_header, "wait-hook macro")

    for obsolete in ("r_tsip_rx_p23.c", "r_tsip_rx_p26.c", "r_tsip_rx_subprc04.c"):
        require(not (ip / obsolete).exists(), f"obsolete v1.21 source remains: {obsolete}")
    for expected in ("r_tsip_rx_function403.c", "r_tsip_rx_p23f.c", "r_tsip_rx_p26f.c"):
        require((ip / expected).is_file(), f"missing v1.23 source: {expected}")
    require((target / "r_tsip_key_injection_rx.c").is_file(), "missing v1.23 key-injection source")

    return {
        "version": EXPECTED_VERSION,
        "driver_files": len(files),
        "smart_config_settings": len(grid),
        "qe_settings": len(settings),
        "b25_waits": b25_waits,
        "hook_calls": hook_calls,
        "wait_hook_enabled": 0,
        "multithreading_enabled": 1,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    try:
        summary = check(root)
    except (OSError, ET.ParseError, RuntimeError) as exc:
        print(f"RX72N TSIP integration check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

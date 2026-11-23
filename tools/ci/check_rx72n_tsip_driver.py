#!/usr/bin/env python3
"""Verify RX72N selects the pinned, unmodified official RDP TSIP driver."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EXPECTED_VERSION = "1.24"
EXPECTED_RDP_SHA = "bcc409d331b0bff68d4b09bf6fc41376f75d42bc"
EXPECTED_FILE_COUNT = 1010
RDP_PATH = "Middleware/Renesas/rx-driver-package"
LIBRARY_PATH = "source/r_tsip_rx_lib"
DRIVER_PATH = LIBRARY_PATH + "/r_tsip_rx_vx.xx/r_tsip_rx"
MDF_PATH = LIBRARY_PATH + "/r_tsip_rx_vx.xx_extend.mdf"
PACKAGE_PATH = LIBRARY_PATH + "/r_tsip_rx_vx.xx.xml"
CONFIG_TEMPLATE_PATH = LIBRARY_PATH + "/r_tsip_rx_vx.xx/r_config/r_tsip_rx_config.h"
SOURCE_ENTRY = "Vendor/r_tsip_rx/src/targets/rx72m_rx72n_rx66n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_pattern(text: str, pattern: str, label: str) -> None:
    require(re.search(pattern, text, re.MULTILINE) is not None, "missing " + label)


def git(folder: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", str(folder), *arguments], capture_output=True)
    require(result.returncode == 0, "cannot read fixed Git provenance: " + arguments[0])
    return result.stdout


def verify_pinned_files(rdp: Path, expected: dict[str, str]) -> None:
    driver = rdp / DRIVER_PATH
    actual = {p.relative_to(rdp).as_posix() for p in driver.rglob("*")
              if p.is_file() and p.relative_to(driver).parts[0] != "doc"}
    selected = {p for p in expected if p.startswith(DRIVER_PATH + "/")}
    require(actual == selected, "official driver file set differs from the fixed RDP tree")
    for relative, oid in expected.items():
        path = rdp / relative
        require(path.is_file(), "missing fixed RDP file: " + relative)
        data = path.read_bytes()
        require(b"TSIP_PRV_WAIT_LOOP_HOOK" not in data and b"vTsipWaitLoopHook" not in data,
                "custom wait hook in official RDP input: " + relative)
        blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        require(hashlib.sha1(blob).hexdigest() == oid,
                "official RDP bytes changed: " + relative)


def verify_original_driver(root: Path) -> dict[str, str]:
    row = git(root, "ls-tree", "HEAD", "--", RDP_PATH).decode("utf-8").strip()
    require(row == "160000 commit " + EXPECTED_RDP_SHA + "\t" + RDP_PATH,
            "root gitlink does not select the reviewed official RDP pin")
    rdp = root / RDP_PATH
    top = Path(git(rdp, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    require(top == rdp.resolve(), "official RDP checkout is uninitialized or belongs to another repository")
    require(git(rdp, "rev-parse", "HEAD").decode().strip() == EXPECTED_RDP_SHA,
            "official RDP checkout HEAD differs from the root gitlink")
    tree = git(rdp, "ls-tree", "-rz", EXPECTED_RDP_SHA, "--", DRIVER_PATH,
               MDF_PATH, PACKAGE_PATH, CONFIG_TEMPLATE_PATH)
    expected = {}
    for row in tree.split(b"\0"):
        if not row:
            continue
        header, path = row.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        relative = path.decode("utf-8")
        require(kind == "blob" and mode == "100644", "unexpected official RDP file mode")
        if relative.startswith(DRIVER_PATH + "/doc/"):
            continue
        expected[relative] = oid
    count = sum(p.startswith(DRIVER_PATH + "/") for p in expected)
    require(count == EXPECTED_FILE_COUNT, "fixed official driver file count differs from reviewed pin")
    require(all(p in expected for p in [MDF_PATH, PACKAGE_PATH, CONFIG_TEMPLATE_PATH]),
            "official TSIP module metadata is missing from the fixed RDP tree")
    verify_pinned_files(rdp, expected)
    return expected


def check(root: Path) -> dict[str, int | str]:
    verify_original_driver(root)
    project = root / "Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx"
    rdp = root / RDP_PATH
    driver = rdp / DRIVER_PATH
    legacy = project / "src/smc_gen/r_tsip_rx"
    require(not any(p.is_file() for p in legacy.rglob("*")), "legacy copied TSIP driver remains")
    interface = (driver / "r_tsip_rx_if.h").read_text(encoding="utf-8")
    require_pattern(interface, r"^#define\s+TSIP_VERSION_MAJOR\s+\(1u\)$", "TSIP major version 1")
    require_pattern(interface, r"^#define\s+TSIP_VERSION_MINOR\s+\(24u\)$", "official TSIP minor version 24")
    config = (project / "src/smc_gen/r_config/r_tsip_rx_config.h").read_text(encoding="utf-8")
    require("TSIP_CFG_WAIT_LOOP_HOOK" not in config, "custom wait-hook selectors remain in project config")
    for name, value in [("TSIP_MULTI_THREADING", "1"),
                        ("TSIP_MULTI_THREADING_LOCK_FUNCTION", "user_lock_function"),
                        ("TSIP_MULTI_THREADING_UNLOCK_FUNCTION", "user_unlock_function")]:
        require_pattern(config, r"^#define\s+" + name + r"\s+\(" + value + r"\)$", name + "=" + value)

    links = ET.parse(project / ".project").getroot()
    selected = [n for n in links.findall("linkedResources/link") if n.findtext("name") == "Vendor/r_tsip_rx"]
    require(len(selected) == 1 and selected[0].findtext("locationURI") ==
            "AWS_IOT_MCU_ROOT/" + RDP_PATH + "/" + DRIVER_PATH,
            "project does not link the canonical official TSIP source")
    cproject = ET.parse(project / ".cproject").getroot()
    entries = [n.get("name") for n in cproject.findall(".//sourceEntries/entry")
               if "r_tsip_rx" in n.get("name", "")]
    require(entries == [SOURCE_ENTRY], "compiler does not select only the official RX72N TSIP target")
    require(any("/Vendor/r_tsip_rx}" in n.get("value", "")
                for n in cproject.findall(".//listOptionValue")), "missing canonical TSIP include path")

    official = {n.get("id") for n in ET.parse(rdp / MDF_PATH).getroot().iter("property")}
    scfg = ET.parse(project / "aws_ether_rx72n_envision_kit_tsip.scfg").getroot()
    components = [n for n in scfg.iter("component") if n.get("display") == "r_tsip_rx"]
    require(len(components) == 1, "Smart Configurator TSIP component must be unique")
    component = components[0]
    require(component.get("id") == "r_tsip_rx" + EXPECTED_VERSION and
            component.get("version") == EXPECTED_VERSION, "Smart Configurator TSIP version differs from official RDP")
    require("custom" not in component.get("detailDescription", "").lower(), "obsolete custom TSIP component description")
    grid = {n.get("id"): n.get("selectedIndex") for n in component.findall("gridItem")}
    require(len(grid) == len(component.findall("gridItem")) and set(grid) == official,
            "Smart Configurator selectors differ from the official TSIP MDF")
    qe = ET.parse(project / ".settings/com.renesas.smc.e2studio.qe.xml").getroot()
    segments = [n for n in qe.iter("Segment") if n.get("id") == "r_tsip_rx"]
    require(len(segments) == 1 and segments[0].get("component") == "r_tsip_rx" + EXPECTED_VERSION,
            "QE TSIP component differs from official RDP")
    settings = {n.get("id"): n.get("value") for n in segments[0].findall("Setting")}
    require(len(settings) == len(segments[0].findall("Setting")) and settings == grid,
            "QE TSIP settings differ from Smart Configurator")
    require(grid.get("TSIP_MULTI_THREADING") == "1" and
            grid.get("TSIP_MULTI_THREADING_LOCK_FUNCTION") == "user_lock_function" and
            grid.get("TSIP_MULTI_THREADING_UNLOCK_FUNCTION") == "user_unlock_function",
            "official TSIP multithreading settings differ from project config")
    return {"version": EXPECTED_VERSION, "rdp_sha": EXPECTED_RDP_SHA,
            "driver_files": EXPECTED_FILE_COUNT, "smart_config_settings": len(grid),
            "qe_settings": len(settings), "custom_wait_hook_present": 0,
            "multithreading_enabled": 1}


def main() -> int:
    try:
        summary = check(Path(__file__).resolve().parents[2])
    except (OSError, ET.ParseError, RuntimeError) as exc:
        print("RX72N TSIP integration check failed: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

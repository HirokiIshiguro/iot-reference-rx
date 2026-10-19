"""Keep CC-RX common-code extraction out of the FreeRTOS stack restorers.

The two outer port functions contain inline assembly ending in RTE. Extracting
their restore sequence into a BSR-called common helper adds an unwanted return
address to the manually restored task stack. Keep other linker optimizations
enabled and exempt only these two functions. This checks project policy, not
the linked machine code or runtime behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


PROJECTS = (
    "aws_wifi_rx671_ek",
    "aws_ether_rx72n_envision_kit",
    "aws_ether_rx72n_envision_kit_tsip",
    "aws_bg96_ck_rx65n",
    "aws_bg96_ck_rx65n_tsip",
)
PREFIX = "com.renesas.cdt.managedbuild.renesas.ccrx."
FORBID = PREFIX + "linker.option.samecodeForbid"
LINK_OPTIMIZE = PREFIX + "linker.option.optimize"
COMPILER_OPTIMIZE = PREFIX + "compiler.option.optimize"
COMPILER_ENABLED = PREFIX + "compiler.option.gOptimize"
FUNCTIONS = {"_xPortStartScheduler", "_vSoftwareInterruptISR"}
# Raw flags must not override the managed options checked below. Match complete
# option names, without confusing a source definition or a path with a flag.
RAW_OPTIMIZER = re.compile(
    r"(?:^|[\s\"'])-(?:no)?(?:opt(?:imize)?|same_code|samecode_forbid|"
    r"symbol_delete|short_format|branch)(?==|\s|$)", re.IGNORECASE
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_configuration(config: ET.Element) -> None:
    """Validate each managed configuration, including future added profiles."""
    folders = config.findall("folderInfo[@resourcePath='']")
    require(len(folders) == 1, "expected one root folder configuration")
    tools = folders[0].findall("toolChain/tool")

    def tool(role: str) -> ET.Element:
        found = [t for t in tools if t.get("superClass") == PREFIX + "base." + role]
        require(len(found) == 1, f"expected one root {role} tool")
        return found[0]

    compiler, linker = tool("compiler"), tool("linker")

    def option(parent: ET.Element, key: str, optional: bool = False) -> ET.Element | None:
        # A second option on a per-file/folder tool can override the root policy.
        found = config.findall(f".//option[@superClass='{key}']")
        require(len(found) <= 1 if optional else len(found) == 1,
                "missing or duplicate managed option: " + key)
        if not found:
            return None
        require(found[0] in list(parent), "managed option must belong to the root tool: " + key)
        return found[0]

    enabled = option(compiler, COMPILER_ENABLED)
    require(enabled.get("valueType") == "boolean" and enabled.get("value") == "true",
            "compiler optimization must remain enabled")
    level = option(compiler, COMPILER_OPTIMIZE, optional=True)
    # CC-RX's omitted level is 2; do not require a new command-line override.
    require(level is None or (level.get("valueType") == "enumerated" and
            level.get("value") == COMPILER_OPTIMIZE + ".level2"),
            "compiler optimization must remain default level 2 or explicit level 2")
    optimize = option(linker, LINK_OPTIMIZE)
    require(optimize.get("valueType") == "enumerated" and
            optimize.get("value") == LINK_OPTIMIZE + ".all",
            "linker optimization must remain all (including symbol_delete)")
    forbid = option(linker, FORBID)
    require(forbid.get("valueType") == "stringList" and forbid.get("value") is None,
            "samecodeForbid must use the supported stringList option")
    entries = list(forbid)
    require(len(entries) == 2 and all(e.tag == "listOptionValue" and
            e.get("builtIn") == "false" for e in entries) and
            {e.get("value") for e in entries} == FUNCTIONS,
            "samecodeForbid must contain exactly the two outer FreeRTOS restore functions")
    for raw in config.iter("option"):
        key = raw.get("superClass", "")
        if key.startswith(PREFIX) and key.rsplit(".", 1)[-1] in {"userBefore", "userAfter"}:
            values = [raw.get("value", "")] + [e.get("value", "") for e in raw]
            require(not any(RAW_OPTIMIZER.search(v) for v in values),
                    "raw user options must not override managed optimization policy")


def check(root: Path) -> dict[str, int]:
    configurations = 0
    for project in PROJECTS:
        path = root / "Projects" / project / "e2studio_ccrx/.cproject"
        try:
            configs = ET.parse(path).getroot().findall(".//configuration[@name]")
            require(bool(configs), "no managed build configuration")
            for config in configs:
                try:
                    validate_configuration(config)
                except RuntimeError as exc:
                    raise RuntimeError(f"{config.get('name')}: {exc}") from exc
                configurations += 1
        except (OSError, ET.ParseError, RuntimeError) as exc:
            raise RuntimeError(f"{project}: {exc}") from exc
    return {"projects": len(PROJECTS), "configurations": configurations,
            "restore_function_exemptions_per_configuration": 2}


def main() -> int:
    try:
        summary = check(Path(__file__).resolve().parents[2])
    except RuntimeError as exc:
        print("RX context restore policy check failed: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Construct IDT's RX671 profile using the reviewed production OTA layout.

This command returns file contents; it never modifies the source tree. The
PowerShell builder owns the temporary writes and byte-for-byte restoration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_rx671_ota_images import (
    PROFILE_NAME,
    PROFILE_PATHS,
    Version,
    make_ota_bank_config,
    make_ota_cproject,
    make_ota_fwup_config,
    parse_version,
)


def make_profile(project: Path, group: str, version: Version) -> dict[str, str]:
    files = {path.as_posix(): (project / path).read_text(encoding="utf-8")
             for path in PROFILE_PATHS}
    files[".cproject"] = make_ota_cproject(files[".cproject"], version)
    if group != "OTAE2E":
        files[".cproject"] = files[".cproject"].replace(
            "-define=RX671_OTA_RUNTIME_ENABLE=1", "-define=RX671_OTA_RUNTIME_ENABLE=0"
        )
    files["src/frtos_config/r_fwup_config.h"] = make_ota_fwup_config(
        files["src/frtos_config/r_fwup_config.h"]
    )
    for path in (
        "src/smc_gen/r_config/r_bsp_config.h",
        "src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h",
    ):
        files[path] = make_ota_bank_config(files[path], path)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--group", required=True,
                        choices=("Transport", "DeviceAdvisor", "OTAE2E", "PKCS11", "OTAPAL"))
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args()
    print(json.dumps({"profile": PROFILE_NAME,
                      "files": make_profile(args.project, args.group, parse_version(args.version))}))


if __name__ == "__main__":
    main()

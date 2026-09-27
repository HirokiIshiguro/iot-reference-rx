"""Resolve nonsecret IDT host settings without changing the pinned RX72N bench."""
from __future__ import annotations

import argparse
import json
import ntpath
import os
from pathlib import Path, PureWindowsPath
from typing import Mapping

_SOURCE_ROOT = str(Path(__file__).resolve().parents[2])


def _under(value: str, base: str, *, allow_equal: bool = False) -> bool:
    path = PureWindowsPath(ntpath.normpath(value))
    root = PureWindowsPath(base)
    return root in path.parents or (allow_equal and path == root)


def load_host_profile(
    profile_path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ if environ is None else environ
    windows = PureWindowsPath(env.get("WINDIR", r"C:\Windows"))
    programs = PureWindowsPath(env.get("ProgramFiles", r"C:\Program Files"))
    profile = {
        "install_root": r"C:\ai\codex\tools\aws-idt",
        "runtime_root": r"C:\ai\codex\tmp\rx72n-idt",
        "workspace_root": r"C:\ai\codex\ws",
        "wsl_distribution": "Ubuntu",
        "wsl_python": "python3",
        "windows_powershell": str(programs / "PowerShell/7/pwsh.exe"),
        "e2studio_cli": r"C:\Renesas\e2_studio_2026_04_2\eclipse\e2studioc.exe",
        "ccrx": r"C:\Program Files (x86)\Renesas\RX\3_7_0\bin\ccrx.exe",
        "windows_ssh": str(windows / "System32/OpenSSH/ssh.exe"),
        "windows_scp": str(windows / "System32/OpenSSH/scp.exe"),
    }
    selected = profile_path or env.get("RX72N_IDT_HOST_PROFILE")
    if selected:
        with Path(selected).open(encoding="utf-8-sig") as source:
            supplied = json.load(source)
        if not isinstance(supplied, dict) or supplied.get("schema_version") != 1:
            raise ValueError("IDT host profile must be a schema_version=1 JSON object")
        if set(supplied) - (set(profile) | {"schema_version"}):
            raise ValueError("IDT host profile has unsupported keys; credentials and board settings do not belong here")
        profile.update({key: value for key, value in supplied.items() if key != "schema_version"})
    # Preserve existing CI/local overrides, including an alternate tool install.
    for key, variable in (("windows_powershell", "RX72N_IDT_POWERSHELL"), ("e2studio_cli", "E2STUDIO_CLI")):
        if env.get(variable):
            profile[key] = env[variable]
    for key, value in profile.items():
        if not isinstance(value, str) or not value or any(char in value for char in "\r\n\0"):
            raise ValueError("IDT host profile values must be nonempty single-line strings")
        if key not in {"wsl_distribution", "wsl_python"} and not PureWindowsPath(value).is_absolute():
            raise ValueError("IDT host paths must be absolute Windows paths")
    for key in ("install_root", "runtime_root", "workspace_root"):
        base = r"C:\ai\codex\ws" if key == "workspace_root" else r"C:\ai\codex"
        if not _under(profile[key], base, allow_equal=key == "workspace_root"):
            raise ValueError("IDT runtime/install roots must stay below C:\\ai\\codex; workspace must stay below C:\\ai\\codex\\ws")
        if any(char.isspace() for char in profile[key]):
            raise ValueError("FRQ install/runtime/workspace paths must not contain whitespace")
    for key in ("runtime_root", "workspace_root", "install_root"):
        # Resolve existing junctions/symlinks on the execution host as well as
        # checking the configured spelling. An Eclipse workspace can retain
        # injected credentials and must never be created inside the checkout.
        resolved = str(Path(profile[key]).resolve()) if os.name == "nt" else profile[key]
        if any(_under(value, _SOURCE_ROOT, allow_equal=True) for value in (profile[key], resolved)):
            raise ValueError("IDT runtime, workspace and install roots must be outside the source checkout")
    return profile


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(load_host_profile(arguments.profile), indent=2))

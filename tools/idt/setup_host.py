"""Create dedicated Python environments; never install OS/Renesas tools or credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import venv

try:
    from .host_profile import load_host_profile, _under
except ImportError:
    from host_profile import load_host_profile, _under


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--venv", type=Path, default=Path(r"C:\ai\codex\tools\venvs\rx72n-idt-windows"))
    parser.add_argument("--wsl-venv", help="Optional absolute WSL path below /mnt/c/ai/codex/tools/venvs")
    args = parser.parse_args()
    if os.name != "nt" or sys.version_info < (3, 11):
        parser.error("Use Windows Python 3.11 or newer")
    profile = load_host_profile(args.profile)
    destination = args.venv.resolve()
    if not _under(str(destination), r"C:\ai\codex\tools\venvs"):
        parser.error("Dedicated Windows venv must be below C:\\ai\\codex\\tools\\venvs")
    if destination.exists() and not (destination / "pyvenv.cfg").is_file():
        parser.error("Existing destination is not a Python venv")
    command = None
    linux_root = None
    if args.wsl_venv:
        linux_root = PurePosixPath(args.wsl_venv)
        if (PurePosixPath("/mnt/c/ai/codex/tools/venvs") not in linux_root.parents
                or ".." in linux_root.parts or any(char.isspace() for char in str(linux_root))):
            parser.error("WSL venv must be below /mnt/c/ai/codex/tools/venvs without whitespace")
        wsl = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/wsl.exe"
        command = [str(wsl), "-d", profile["wsl_distribution"], "--exec"]
        guard = (
            "from pathlib import Path; import sys; p=Path(sys.argv[1]); "
            "sys.exit('Existing WSL destination is not a Python venv') "
            "if p.is_symlink() or (p.exists() and not (p/'pyvenv.cfg').is_file()) else None"
        )
        subprocess.run(command + ["python3", "-c", guard, str(linux_root)], check=True)
    venv.EnvBuilder(with_pip=True).create(destination)
    python = destination / "Scripts/python.exe"
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(Path(__file__).with_name("requirements-windows.txt"))], check=True)
    subprocess.run([str(python), "-m", "pip", "check"], check=True)
    if command is not None:
        requirements = subprocess.check_output(command + ["wslpath", "-a", "-u", str(Path(__file__).with_name("requirements-wsl.txt").resolve())], text=True).strip()
        # --copies avoids relying on Linux symlink support on the Windows mount.
        subprocess.run(command + ["python3", "-m", "venv", "--copies", str(linux_root)], check=True)
        profile["wsl_python"] = str(linux_root / "bin/python")
        subprocess.run(command + [profile["wsl_python"], "-m", "pip", "install", "-r", requirements], check=True)
        subprocess.run(command + [profile["wsl_python"], "-m", "pip", "check"], check=True)
    output = destination / "host-profile.json"
    output.write_text(json.dumps({"schema_version": 1, **profile}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"windows_python": str(python), "host_profile": str(output), "wsl_python": profile["wsl_python"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

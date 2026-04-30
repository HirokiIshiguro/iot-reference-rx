#!/usr/bin/env python3
"""Build a CK-RX65N BG96 OTA candidate with a temporary app version."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def parse_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise argparse.ArgumentTypeError("version must be MAJOR.MINOR.BUILD")
    return tuple(int(part) for part in match.groups())


def write_utf8(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def replace_version(text: str, version: tuple[int, int, int]) -> str:
    updated = text
    for macro, value in zip(("APP_VERSION_MAJOR", "APP_VERSION_MINOR", "APP_VERSION_BUILD"), version):
        pattern = rf"(^\s*#define\s+{macro}\s+)\d+"
        updated, count = re.subn(pattern, rf"\g<1>{value}", updated, count=1, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError(f"could not patch {macro} in demo_config.h")
    return updated


def run(command: list[str], cwd: Path) -> None:
    print("+ " + " ".join(command))
    result = subprocess.run(command, cwd=str(cwd))
    if result.returncode != 0:
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--app-dir", type=Path, default=Path("Projects/aws_bg96_ck_rx65n/e2studio_ccrx"))
    parser.add_argument("--version", required=True, type=parse_version)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--signing-key", required=True, type=Path)
    parser.add_argument("--e2studio-cli", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--e2studio-timeout", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    app_dir = (repo_root / args.app_dir).resolve() if not args.app_dir.is_absolute() else args.app_dir.resolve()
    output_dir = (repo_root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir.resolve()
    signing_key = (repo_root / args.signing_key).resolve() if not args.signing_key.is_absolute() else args.signing_key.resolve()

    demo_config = app_dir / "src/frtos_config/demo_config.h"
    app_mot = app_dir / "HardwareDebug/aws_bg96_ck_rx65n.mot"
    rsu_tool = repo_root / "tools/create_bg96_rsu.py"
    cert_tool = repo_root / "tools/generate_bg96_ota_signer_cert.py"

    for path in (demo_config, signing_key, args.e2studio_cli, rsu_tool, cert_tool):
        if not path.exists():
            raise RuntimeError(f"required path not found: {path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    version_text = ".".join(str(part) for part in args.version)
    version_token = version_text.replace(".", "_")
    full_rsu = output_dir / f"bg96_{version_token}.rsu"
    ota_payload = output_dir / f"bg96_{version_token}_ota_payload.bin"
    code_sign_cert = output_dir / "bg96_ota_codesign_cert.pem"
    log_path = output_dir / "build_bg96_ota_candidate.log"

    snapshot_paths = [
        demo_config,
        app_dir / ".settings/com.renesas.smc.generationsetting.properties",
        app_dir / ".settings/com.renesas.smc.tools.swcomponent.fit.properties",
    ]
    snapshots = {path: path.read_bytes() for path in snapshot_paths if path.exists()}
    original = snapshots[demo_config].decode("utf-8")
    try:
        write_utf8(demo_config, replace_version(original, args.version))

        if args.workspace.exists():
            import shutil

            shutil.rmtree(args.workspace)
        args.workspace.mkdir(parents=True, exist_ok=True)

        project_uri = "file:///" + str(app_dir).replace("\\", "/").replace(" ", "%20")
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            for command in (
                [str(args.e2studio_cli), "-consoleLog", "-data", str(args.workspace), "project", "import", project_uri],
                [
                    str(args.e2studio_cli),
                    "-consoleLog",
                    "-data",
                    str(args.workspace),
                    "project",
                    "build",
                    "aws_bg96_ck_rx65n/HardwareDebug",
                ],
            ):
                print("+ " + " ".join(command))
                try:
                    result = subprocess.run(
                        command,
                        cwd=str(repo_root),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=args.e2studio_timeout,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError(
                        f"e2 studio command timed out after {args.e2studio_timeout} seconds: {' '.join(command)}"
                    ) from exc
                if result.returncode != 0:
                    raise RuntimeError(f"e2 studio command failed with exit {result.returncode}: {' '.join(command)}")

        if not app_mot.exists():
            raise RuntimeError(f"aws_bg96_ck_rx65n.mot was not generated: {app_mot}")

        run(["python", str(rsu_tool), "--mot", str(app_mot), "--key", str(signing_key), "--output", str(full_rsu)], repo_root)
        run(
            [
                "python",
                str(rsu_tool),
                "--mot",
                str(app_mot),
                "--key",
                str(signing_key),
                "--output",
                str(ota_payload),
                "--format",
                "rtos-ota-payload",
            ],
            repo_root,
        )
        run(["python", str(cert_tool), "--key", str(signing_key), "--out", str(code_sign_cert)], repo_root)
    finally:
        for path, content in snapshots.items():
            path.write_bytes(content)

    print("CK-RX65N BG96 OTA candidate build complete")
    print(f"  version: {version_text}")
    print(f"  full_rsu: {full_rsu}")
    print(f"  ota_payload: {ota_payload}")
    print(f"  code_sign_cert: {code_sign_cert}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

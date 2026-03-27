#!/usr/bin/env python3
"""
Build an RX72N OTA candidate image with a temporary app version override.

This helper updates APP_VERSION_{MAJOR,MINOR,BUILD} in demo_config.h,
builds the RX72N app/boot_loader, generates a signed .rsu image, then
restores the original source file so the workspace stays on the baseline
version after the command finishes.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd):
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)} (exit={result.returncode})")


def replace_version(text, major, minor, build):
    replacements = {
        "APP_VERSION_MAJOR": str(major),
        "APP_VERSION_MINOR": str(minor),
        "APP_VERSION_BUILD": str(build),
    }
    updated = text
    for macro, value in replacements.items():
        pattern = rf"(^\s*#define\s+{macro}\s+)\d+"
        updated, count = re.subn(pattern, rf"\g<1>{value}", updated, count=1, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError(f"failed to update {macro} in demo_config.h")
    return updated


def parse_version(version):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise argparse.ArgumentTypeError("version must be like 0.9.3")
    return tuple(int(part) for part in match.groups())


def main():
    parser = argparse.ArgumentParser(description="Build RX72N OTA candidate with temporary version override")
    parser.add_argument(
        "--repo-root",
        default=str((Path(__file__).resolve().parent / "..").resolve()),
        help="Repository root (default: parent of tools/)",
    )
    parser.add_argument(
        "--version",
        required=True,
        type=parse_version,
        help="OTA candidate version (e.g. 0.9.3)",
    )
    parser.add_argument(
        "--output-prefix",
        required=True,
        help="Output prefix for image-gen.py (e.g. C:\\temp\\ck-rx65n-01_0_9_3)",
    )
    parser.add_argument(
        "--signing-key",
        default=None,
        help="Private key for image-gen.py; defaults to tools/test_keys/secp256r1.privatekey",
    )
    parser.add_argument(
        "--e2studio-cli",
        default=None,
        help="Optional path passed to build_headless.bat",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Optional workspace path passed to build_headless.bat",
    )
    parser.add_argument(
        "--code-sign-cert-out",
        default=None,
        help="Optional PEM output path for generate_signer_cert.py",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    tools_dir = repo_root / "tools"
    demo_config = repo_root / "Projects" / "aws_ether_rx72n_envision_kit" / "e2studio_ccrx" / "src" / "frtos_config" / "demo_config.h"
    build_script = tools_dir / "build_headless_rx72n.ps1"
    generate_cert = tools_dir / "generate_signer_cert.py"
    rsu_builder = tools_dir / "build_fwup_v2_rsu.py"
    app_mot = repo_root / "Projects" / "aws_ether_rx72n_envision_kit" / "e2studio_ccrx" / "HardwareDebug" / "aws_ether_rx72n_envision_kit.mot"
    prm_csv = repo_root / "Projects" / "aws_ether_rx72n_envision_kit" / "e2studio_ccrx" / "src" / "smc_gen" / "r_fwup" / "tool" / "RX72N_DualBank_ImageGenerator_PRM.csv"

    signing_key = Path(args.signing_key).resolve() if args.signing_key else tools_dir / "test_keys" / "secp256r1.privatekey"
    code_sign_cert_out = Path(args.code_sign_cert_out).resolve() if args.code_sign_cert_out else Path(f"{args.output_prefix}_codesign_cert.pem")
    output_prefix = Path(args.output_prefix).resolve()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    code_sign_cert_out.parent.mkdir(parents=True, exist_ok=True)

    with open(demo_config, "r", encoding="utf-8", newline="") as handle:
        original_text = handle.read()
    updated_text = replace_version(original_text, *args.version)

    try:
        with open(demo_config, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated_text)

        build_cmd = [
            "powershell",
            "-NoProfile",
            "-File",
            str(build_script),
            "-ProjectRoot",
            str(repo_root),
        ]
        if args.e2studio_cli:
            build_cmd.extend(["-E2Studio", args.e2studio_cli])
        if args.workspace:
            build_cmd.extend(["-Workspace", args.workspace])
        run(build_cmd, repo_root)

        run(
            [
                sys.executable,
                str(generate_cert),
                "--key",
                str(signing_key),
                "--out",
                str(code_sign_cert_out),
            ],
            repo_root,
        )

        run(
            [
                sys.executable,
                str(rsu_builder),
                "--mot",
                str(app_mot),
                "--prm",
                str(prm_csv),
                "--key",
                str(signing_key),
                "--output",
                str(output_prefix.with_suffix(".rsu")),
            ],
            repo_root,
        )
    finally:
        with open(demo_config, "w", encoding="utf-8", newline="") as handle:
            handle.write(original_text)

    rsu_path = output_prefix.with_suffix(".rsu")
    if not rsu_path.exists():
        raise RuntimeError(f"OTA candidate not generated: {rsu_path}")

    version_str = ".".join(str(part) for part in args.version)
    print("")
    print("RX72N OTA candidate build complete")
    print(f"  version:         {version_str}")
    print(f"  candidate .rsu:  {rsu_path}")
    print(f"  code-sign cert:  {code_sign_cert_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

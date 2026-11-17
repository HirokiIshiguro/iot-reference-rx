"""Firmware builds of tools/ci/rxci.py (Windows runner, e2 studio + CC-RX).

A variant is "<board>/<name>". Every variant writes its files into one output
directory, so a test job can take what it needs from the artifacts of the build jobs:

  <board>/common          provisioner image, signer certificate and public key (one per commit)
  <board>/software/app    signed application image and the boot loader (one per commit)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIGNING_KEY = ROOT / "sample_keys" / "secp256r1.privatekey"


def run(command: list, *, timeout: int) -> None:
    print("+ " + " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True, timeout=timeout)


def workspace(registry: dict, name: str) -> Path:
    """Short, job-local e2 studio workspace (long paths break CC-RX builds)."""
    job = os.environ.get("CI_JOB_ID", "local")
    path = Path(registry["workspace_root"]) / f"rxci-{job}-{name}"
    shutil.rmtree(path, ignore_errors=True)
    return path


def publish(out: Path, files: dict[str, Path]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        if not source.is_file():
            raise SystemExit(f"Build output is missing: {source}")
        shutil.copyfile(source, out / name)
        print(f"  {out / name}  ({source.stat().st_size} bytes)")


def build_common(registry: dict, board: str, out: Path) -> None:
    """Provisioner that stores the signer's public key, plus the signer certificate."""
    target = registry["boards"][board]["target"]
    work = workspace(registry, f"{board}-common")
    public = work / "public"
    try:
        run([sys.executable, "tools/idt/prepare_public_signer.py", "--source", ROOT, "--target", target,
             "--output", public, "--workspace", work / "e2ws", "--python", sys.executable,
             "--signing-key", SIGNING_KEY], timeout=1800)
        publish(out, {name: public / name for name in (
            "public_signer_provisioner.mot", "signer.crt.pem", "signer.pub.pem")})
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_rx72n_app(registry: dict, backend: str, out: Path) -> None:
    project = "aws_ether_rx72n_envision_kit" if backend == "software" else "aws_ether_rx72n_envision_kit_tsip"
    work = workspace(registry, f"rx72n-{backend}")
    log = ROOT / "rx72n_e2studio_build.log"
    boot_dir = ROOT / "Projects" / "boot_loader_rx72n_envision_kit" / "e2studio_ccrx" / "HardwareDebug"
    app_mot = ROOT / "Projects" / project / "e2studio_ccrx" / "HardwareDebug" / f"{project}.mot"
    boot = boot_dir / "boot_loader_rx72n_envision_kit.mot"
    boot_bank1 = boot_dir / "boot_loader_rx72n_envision_kit_bank1.mot"
    rsu = ROOT / "rx72n_app.rsu"
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    try:
        run(["pwsh", "-NoProfile", "-File", "tools/build_headless_rx72n.ps1", "-ProjectRoot", ROOT,
             "-E2Studio", cli, "-Workspace", work, "-LogFile", log, "-E2StudioTimeoutSeconds", "1200",
             "-TlsBackend", "software" if backend == "software" else "tsip"], timeout=1500)
        run([sys.executable, "tools/shift_srec_addresses.py", "--input", boot, "--output", boot_bank1,
             "--range-start", "0xFFE00000", "--range-end", "0xFFFFFFFF", "--shift=-0x200000",
             "--drop-out-of-range"], timeout=120)
        run([sys.executable, "tools/build_fwup_v2_rsu.py", "--mot", app_mot,
             "--prm", "tools/fwup/rx72n_envision_kit_dual_bank.prm.csv", "--key", SIGNING_KEY,
             "--output", rsu], timeout=120)
        publish(out, {"app.rsu": rsu, "bootloader.mot": boot, "bootloader_bank1.mot": boot_bank1})
    finally:
        if log.is_file():
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(log, out / "e2studio_build.log")
        shutil.rmtree(work, ignore_errors=True)


def build(registry: dict, variant: str, out: Path) -> None:
    board, _, name = variant.partition("/")
    if board not in registry["boards"]:
        raise SystemExit(f"Unknown board in build variant: {variant}")
    if name == "common":
        return build_common(registry, board, out)
    if board == "rx72n" and name == "software/app":
        return build_rx72n_app(registry, "software", out)
    raise SystemExit(f"Build variant is not implemented yet: {variant}")

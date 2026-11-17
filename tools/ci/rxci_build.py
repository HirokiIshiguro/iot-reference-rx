"""Firmware builds of tools/ci/rxci.py (Windows runner, e2 studio + CC-RX).

A variant is "<board>/<name>". Every variant writes its files into one output
directory, so a test job can take what it needs from the artifacts of the build jobs:

  <board>/common                 provisioner image, signer certificate and public key (one per commit);
                                 on RX671 also the boot loader
  rx72n/software/app             signed application and the boot loader
  rx72n/software/fleet           the same with the Fleet Provisioning demo enabled
  rx65n/software/app             signed application and the boot loader
  rx65n/software/fleet           the same with the Fleet Provisioning demo enabled
  rx671/software-<tls>/app       signed application with the Wi-Fi and device credentials compiled in
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
        if board == "rx671":
            cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
            run(["pwsh", "-NoProfile", "-File", "tools/build_headless_rx671_bootloader.ps1", "-ProjectRoot", ROOT,
                 "-E2Studio", cli,
                 # The build script accepts only this workspace name below the workspace root.
                 "-Workspace", work / "e2ws_iot_ref_rx671_bootloader_2026_04_2",
                 "-LogFile", work / "bootloader_build.log", "-Python", sys.executable], timeout=900)
            publish(out, {"bootloader.mot": ROOT / "Projects" / "boot_loader_rx671_ek" / "e2studio_ccrx" /
                          "HardwareDebug" / "boot_loader_rx671_ek.mot"})
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_rx65n_app(registry: dict, backend: str, kind: str, out: Path) -> None:
    project = "aws_bg96_ck_rx65n" if backend == "software" else "aws_bg96_ck_rx65n_tsip"
    work = workspace(registry, f"rx65n-{backend}-{kind}")
    log = ROOT / "rx65n_bg96_e2studio_build.log"
    boot_dir = ROOT / "Projects" / "boot_loader_ck_rx65n" / "e2studio_ccrx" / "HardwareDebug"
    app_mot = ROOT / "Projects" / project / "e2studio_ccrx" / "HardwareDebug" / f"{project}.mot"
    boot = boot_dir / "boot_loader_ck_rx65n.mot"
    boot_bank1 = boot_dir / "boot_loader_ck_rx65n_bank1.mot"
    rsu = ROOT / "rx65n_app.rsu"
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    try:
        script = "tools/build_headless_rx65n_bg96_fleet.ps1" if kind == "fleet" else "tools/build_headless_rx65n_bg96.ps1"
        extra = (["-FleetDemoId", registry["boards"]["rx65n"]["fleet_demo_id"], "-E2StudioTimeoutSeconds", "1800"]
                 if kind == "fleet" else [])
        run(["pwsh", "-NoProfile", "-File", script, "-ProjectRoot", ROOT,
             "-E2Studio", cli, "-Workspace", work, "-LogFile", log,
             "-TlsBackend", "software" if backend == "software" else "tsip", *extra], timeout=2400)
        run([sys.executable, "tools/shift_srec_addresses.py", "--input", boot, "--output", boot_bank1,
             "--range-start", "0xFFFC0000", "--range-end", "0xFFFFFFFF", "--shift=-0x100000",
             "--drop-out-of-range"], timeout=120)
        run([sys.executable, "tools/create_bg96_rsu.py", "--mot", app_mot, "--key", SIGNING_KEY,
             "--output", rsu], timeout=120)
        publish(out, {"app.rsu": rsu, "bootloader.mot": boot, "bootloader_bank1.mot": boot_bank1})
    finally:
        if log.is_file():
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(log, out / "e2studio_build.log")
        shutil.rmtree(work, ignore_errors=True)


def build_rx671_app(registry: dict, tls: str, out: Path) -> None:
    """MQTT application of EK-RX671. The Wi-Fi and device credentials are compiled in from CI variables."""
    for name in ("RX671_EK_WIFI_SSID", "RX671_EK_WIFI_PASSPHRASE", "RX671_EK_AWS_IOT_THING_NAME",
                 "RX671_EK_AWS_IOT_CERT_PEM", "RX671_EK_AWS_IOT_PRIVATE_KEY_PEM"):
        if not os.environ.get(name):
            raise SystemExit(f"CI variable {name} is not available to this job.")
    entry = registry["endpoints"][tls]
    endpoint = entry.get("value") or os.environ.get("RX671_EK_AWS_IOT_ENDPOINT") or os.environ.get(entry["variable"], "")
    if not endpoint:
        raise SystemExit(f"The AWS IoT endpoint for {tls} is not set.")
    work = workspace(registry, f"rx671-{tls}")
    log = ROOT / "rx671_wifi_e2studio_build.log"
    mot = ROOT / "Projects" / "aws_wifi_rx671_ek" / "e2studio_ccrx" / "HardwareDebug" / "aws_wifi_rx671_ek.mot"
    rsu = ROOT / "rx671_app.rsu"
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    command = ["pwsh", "-NoProfile", "-File", "tools/build_headless_rx671_wifi.ps1", "-ProjectRoot", ROOT,
               "-E2Studio", cli, "-Workspace", work, "-LogFile", log, "-WlanAllowBusSleepDelayMs", "600000",
               "-UseLocalJoinConfig", "-UseAwsIotLocalConfig", "-AwsIotEndpoint", endpoint]
    if tls == "tls13":
        command += ["-RequireTlsVersion", "TLSv1.3"]
    try:
        run(command, timeout=1500)
        run([sys.executable, "tools/build_rx671_fwup_v2_rsu.py", "--mot", mot, "--key", SIGNING_KEY,
             "--output", rsu], timeout=120)
        publish(out, {"app.rsu": rsu})
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_rx72n_app(registry: dict, backend: str, kind: str, out: Path) -> None:
    project = "aws_ether_rx72n_envision_kit" if backend == "software" else "aws_ether_rx72n_envision_kit_tsip"
    work = workspace(registry, f"rx72n-{backend}-{kind}")
    log = ROOT / "rx72n_e2studio_build.log"
    boot_dir = ROOT / "Projects" / "boot_loader_rx72n_envision_kit" / "e2studio_ccrx" / "HardwareDebug"
    app_mot = ROOT / "Projects" / project / "e2studio_ccrx" / "HardwareDebug" / f"{project}.mot"
    boot = boot_dir / "boot_loader_rx72n_envision_kit.mot"
    boot_bank1 = boot_dir / "boot_loader_rx72n_envision_kit_bank1.mot"
    rsu = ROOT / "rx72n_app.rsu"
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    try:
        script = "tools/build_headless_rx72n_fleet.ps1" if kind == "fleet" else "tools/build_headless_rx72n.ps1"
        extra = ["-FleetDemoId", registry["boards"]["rx72n"]["thing"] + "-fp"] if kind == "fleet" else []
        run(["pwsh", "-NoProfile", "-File", script, "-ProjectRoot", ROOT,
             "-E2Studio", cli, "-Workspace", work, "-LogFile", log, "-E2StudioTimeoutSeconds", "1200",
             "-TlsBackend", "software" if backend == "software" else "tsip", *extra], timeout=1500)
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
    if board == "rx72n" and name in ("software/app", "software/fleet"):
        return build_rx72n_app(registry, "software", name.split("/")[1], out)
    if board == "rx65n" and name in ("software/app", "software/fleet"):
        return build_rx65n_app(registry, "software", name.split("/")[1], out)
    if board == "rx671" and name in ("software-tls12/app", "software-tls13/app"):
        return build_rx671_app(registry, name.split("/")[0].split("-")[1], out)
    raise SystemExit(f"Build variant is not implemented yet: {variant}")

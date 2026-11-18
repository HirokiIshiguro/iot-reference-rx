"""Firmware builds of tools/ci/rxci.py (Windows runner, e2 studio + CC-RX).

A variant is "<board>/<name>". Every variant writes its files into one output
directory, so a test job can take what it needs from the artifacts of the build jobs:

  <board>/common                 provisioner image, signer certificate and public key (one per commit);
                                 on RX671 also the boot loader
  rx72n/software/app             signed application and the boot loader
  rx72n/software/fleet           the same with the Fleet Provisioning demo enabled
  rx72n/software/ota             OTA candidate (a newer application version) and its code signing certificate
  rx65n/software/app             signed application and the boot loader
  rx65n/software/fleet           the same with the Fleet Provisioning demo enabled
  rx65n/software/ota             OTA candidate payload, its signature and the code signing certificate
  rx72n|rx65n/tsip-<tls>/<kind>  the same three kinds built from the TSIP project; the TLS version is compiled in
  rx671/software-<tls>/app       signed application with the Wi-Fi and device credentials compiled in
  rx671/software-<tls>/fleet     signed application with the Wi-Fi and claim credentials compiled in
  rx671/software-<tls>/ota       OTA bundle without credentials: provisioner, boot loader, baseline and candidate

RX671 applications carry credentials, so they leave the build job only encrypted (app.rsu.enc).
The key is derived from a CI variable that the test job also has.

A build is reused when its inputs are the same as those of an earlier build on this runner:
the committed files (dependencies by their pinned commits), the variant and the settings of
the board in tests.json. Files that only steer the pipeline or the tests are not inputs.
Images that carry credentials are never kept. REBUILD=true (and every scheduled pipeline)
builds again and replaces what was kept. Use it after the compiler or e2 studio changed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIGNING_KEY = ROOT / "sample_keys" / "secp256r1.privatekey"


CACHE_ENTRIES = 80
# Committed files that do not change what a build produces.
NOT_BUILD_INPUTS = ("docs/", ".gitlab-ci.yml", "tools/ci/rxci.py", "tools/ci/rxci_board.py", "tools/ci/rxci_aws.py",
                    "tools/ci/test_rxci.py", "tools/ci/tests.json", "tools/ci/requirements.txt", "tools/ci/tests/",
                    # Tools that run next to the board or talk to AWS; no build script uses them.
                    "tools/bg96_bootloader_integration.py", "tools/bg96_ota_monitor.py", "tools/bg96_ota_prepare.py",
                    "tools/create_bg96_ota_update.py", "tools/create_ota_update.py",
                    "tools/manage_ephemeral_iot_thing.py", "tools/provision_rx72n.py",
                    "tools/provision_tsip_over_uart.py", "tools/test_fleet_rx72n.py", "tools/test_mqtt_rx72n.py",
                    "tools/test_ota.py", "tools/test_rx671_ota.py", "tools/verify_ota_aws_state.py")


def run(command: list, *, timeout: int, env: dict | None = None) -> None:
    print("+ " + " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True, timeout=timeout, env=env)


def workspace(registry: dict, name: str) -> Path:
    """Short, job-local e2 studio workspace (long paths break CC-RX builds)."""
    job = os.environ.get("CI_JOB_ID", "local")
    path = Path(registry["workspace_root"]) / f"rxci-{job}-{name}"
    shutil.rmtree(path, ignore_errors=True)
    return path


def init_nested_dependencies() -> None:
    """Fetch the submodules of the submodules, as the headless build scripts do at their start."""
    run(["pwsh", "-NoProfile", "-Command",
         f". '{ROOT / 'tools' / 'rx_e2studio_cli.ps1'}'; Initialize-RxBuildDependencies -ProjectRoot '{ROOT}'"],
        timeout=900)


def keep_logs(folder: Path, out: Path) -> None:
    """Copy the build logs of a helper into the job artifacts, also after a failure."""
    if folder.is_dir():
        out.mkdir(parents=True, exist_ok=True)
        for log in folder.glob("*.log"):
            shutil.copyfile(log, out / log.name)


LINKER_ERROR = re.compile(r"\b[CEF]05\d{5}\b|Abort")


def linker_error_lines(log: Path) -> list[str]:
    """Lines of an e2 studio build log that name a compiler, assembler or linker abort (E05..., F05..., Abort)."""
    if not log.is_file():
        return []
    text = log.read_text(encoding="utf-8", errors="replace")
    return [line.rstrip() for line in text.splitlines() if LINKER_ERROR.search(line)]


def report_build_failure(log: Path) -> None:
    """Print the linker errors into the job log; the build log itself is overwritten by the next job."""
    lines = linker_error_lines(log)
    print("--- linker errors of the e2 studio build log ---" if lines else "--- no linker error line found in the e2 studio build log ---")
    for line in lines[:40]:
        print(line, flush=True)


def keep_map(map_file: Path, out: Path) -> None:
    """Keep the linker map in the job artifacts when the linker wrote one."""
    if map_file.is_file():
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(map_file, out / map_file.name)


def publish(out: Path, files: dict[str, Path]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        if not source.is_file():
            raise SystemExit(f"Build output is missing: {source}")
        shutil.copyfile(source, out / name)
        print(f"  {out / name}  ({source.stat().st_size} bytes)")


def build_rx671_bootloader(registry: dict, work: Path) -> Path:
    """Build the RX671 boot loader in its project folder and return the image."""
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    run(["pwsh", "-NoProfile", "-File", "tools/build_headless_rx671_bootloader.ps1", "-ProjectRoot", ROOT,
         "-E2Studio", cli,
         # The build script accepts only this workspace name below the workspace root.
         "-Workspace", work / "e2ws_iot_ref_rx671_bootloader_2026_04_2",
         "-LogFile", work / "bootloader_build.log", "-Python", sys.executable], timeout=900)
    return ROOT / "Projects" / "boot_loader_rx671_ek" / "e2studio_ccrx" / "HardwareDebug" / "boot_loader_rx671_ek.mot"


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
            publish(out, {"bootloader.mot": build_rx671_bootloader(registry, work)})
    finally:
        shutil.rmtree(work, ignore_errors=True)


def tls_arguments(backend: str, tls: str, flag: str) -> list[str]:
    """A TSIP build selects its mbed TLS configuration by the TLS version; a software build does not."""
    return [flag, "TLSv1.3"] if backend == "tsip" and tls == "tls13" else []


def build_rx72n_ota(registry: dict, backend: str, tls: str, out: Path) -> None:
    """Application with a higher version number, packaged as the payload of an AWS IoT OTA update."""
    work = workspace(registry, f"rx72n-{backend}{tls}-ota")
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    version = registry["boards"]["rx72n"]["ota_candidate_version"]
    try:
        work.mkdir(parents=True)
        run([sys.executable, "tools/build_ota_candidate.py", "--repo-root", ROOT, "--version", version,
             "--output-prefix", work / "candidate", "--signing-key", SIGNING_KEY, "--e2studio-cli", cli,
             "--workspace", work / "e2ws", "--tls-backend", backend,
             *tls_arguments(backend, tls, "--require-tls-version"),
             "--code-sign-cert-out", work / "codesign_cert.pem"], timeout=1800)
        publish(out, {"candidate.rsu": work / "candidate.rsu", "codesign_cert.pem": work / "codesign_cert.pem"})
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_rx65n_app(registry: dict, backend: str, tls: str, kind: str, out: Path) -> None:
    project = "aws_bg96_ck_rx65n" if backend == "software" else "aws_bg96_ck_rx65n_tsip"
    work = workspace(registry, f"rx65n-{backend}{tls}-{kind}")
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
             "-TlsBackend", backend, *tls_arguments(backend, tls, "-RequireTlsVersion"), *extra], timeout=2400)
        run([sys.executable, "tools/shift_srec_addresses.py", "--input", boot, "--output", boot_bank1,
             "--range-start", "0xFFFF0000", "--range-end", "0xFFFFFFFF", "--shift=-0x100000",
             "--drop-out-of-range"], timeout=120)
        run([sys.executable, "tools/create_bg96_rsu.py", "--mot", app_mot, "--key", SIGNING_KEY,
             "--output", rsu], timeout=120)
        publish(out, {"app.rsu": rsu, "bootloader.mot": boot, "bootloader_bank1.mot": boot_bank1})
    finally:
        if log.is_file():
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(log, out / "e2studio_build.log")
        shutil.rmtree(work, ignore_errors=True)


def build_rx671_ota(registry: dict, tls: str, out: Path) -> None:
    """Everything the RX671 OTA test needs. Credentials are entered on the board, not compiled in."""
    board = registry["boards"]["rx671"]
    work = workspace(registry, f"rx671-{tls}-ota")
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    bundle = ROOT / "build" / "rx671-ota"      # the only output folder the build script accepts
    baseline = f"baseline-{board['ota_baseline_version']}"
    candidate = f"candidate-{board['ota_candidate_version']}"
    try:
        work.mkdir(parents=True)
        build_rx671_bootloader(registry, work)      # the image helper copies it and does not build it
        run([sys.executable, "tools/build_rx671_ota_images.py", "--baseline-version", board["ota_baseline_version"],
             "--candidate-version", board["ota_candidate_version"],
             "--tls-version", "TLSv1.3" if tls == "tls13" else "TLSv1.2", "--e2studio", cli,
             "--workspace-root", work / "e2ws", "--signing-key", SIGNING_KEY,
             "--e2studio-timeout-seconds", "1200"], timeout=3000)
        publish(out, {
            "provisioner.mot": bundle / "provisioner" / "aws_wifi_rx671_ek.mot",
            "bootloader.mot": bundle / "bootloader" / "boot_loader_rx671_ek.mot",
            "baseline.rsu": bundle / baseline / "aws_wifi_rx671_ek.rsu",
            "signer.crt.pem": bundle / baseline / "rx671-ota-signer.crt.pem",
            "signer.pub.pem": bundle / baseline / "rx671-ota-signer.pub.pem",
            "candidate.ota.bin": bundle / candidate / "aws_wifi_rx671_ek.ota.bin",
            "candidate.ota-signature.der": bundle / candidate / "aws_wifi_rx671_ek.ota-signature.der",
        })
        # Memory layout of the baseline, to read when a test runs out of heap.
        for name in ("aws_wifi_rx671_ek.map", "ota-layout-report.json"):
            if (bundle / baseline / name).is_file():
                shutil.copyfile(bundle / baseline / name, out / f"baseline-{name}")
    finally:
        keep_logs(work, out)
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


def image_key(registry: dict, board: str, kind: str) -> bytes:
    """AES key for an image that carries credentials, derived from a File variable both jobs have."""
    variable = registry["boards"][board]["image_secret_variable"][kind]
    path = os.environ.get(variable, "")
    if not path or not Path(path).is_file():
        raise SystemExit(f"CI variable {variable} (type File) is not available to this job.")
    return hashlib.sha256(b"rxci image v1\0" + Path(path).read_bytes().replace(b"\r", b"").strip()).digest()


def encrypt_file(source: Path, target: Path, key: bytes) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    target.write_bytes(nonce + AESGCM(key).encrypt(nonce, source.read_bytes(), b"rxci"))


def build_rx65n_ota(registry: dict, backend: str, tls: str, out: Path) -> None:
    """OTA candidate of CK-RX65N. No credentials are compiled in: the board keeps using its data flash."""
    project = "aws_bg96_ck_rx65n" if backend == "software" else "aws_bg96_ck_rx65n_tsip"
    work = workspace(registry, f"rx65n-{backend}{tls}-ota")
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    version = registry["boards"]["rx65n"]["ota_candidate_version"]
    token = version.replace(".", "_")
    try:
        work.mkdir(parents=True)
        init_nested_dependencies()      # this helper does not do it itself
        run([sys.executable, "tools/build_bg96_ota_candidate.py", "--repo-root", ROOT,
             "--app-dir", f"Projects/{project}/e2studio_ccrx", "--version", version, "--output-dir", work / "out",
             "--signing-key", SIGNING_KEY, "--e2studio-cli", cli, "--workspace", work / "e2ws",
             "--e2studio-timeout", "1800", "--tls-backend", backend,
             *tls_arguments(backend, tls, "--require-tls-version")], timeout=2400)
        publish(out, {"candidate_payload.bin": work / "out" / f"bg96_{token}_ota_payload.bin",
                      "candidate_payload.sig.der": work / "out" / f"bg96_{token}_ota_payload.sig.der",
                      "codesign_cert.pem": work / "out" / "bg96_ota_codesign_cert.pem"})
    finally:
        keep_logs(work / "out", out)
        shutil.rmtree(work, ignore_errors=True)


def build_rx671_app(registry: dict, backend: str, tls: str, kind: str, out: Path) -> None:
    """Application of EK-RX671. The Wi-Fi and AWS credentials are compiled in from CI variables."""
    board = registry["boards"]["rx671"]
    required = ["RX671_EK_WIFI_SSID", "RX671_EK_WIFI_PASSPHRASE"]
    if kind == "app":
        required += ["RX671_EK_AWS_IOT_THING_NAME", "RX671_EK_AWS_IOT_CERT_PEM", "RX671_EK_AWS_IOT_PRIVATE_KEY_PEM"]
    else:
        required += [board["fleet_template_variable"], board["claim_certificate_variable"],
                     board["claim_private_key_variable"]]
    for name in required:
        if not os.environ.get(name):
            raise SystemExit(f"CI variable {name} is not available to this job.")
    key = image_key(registry, "rx671", kind)
    entry = registry["endpoints"][tls]
    endpoint = entry.get("value") or os.environ.get("RX671_EK_AWS_IOT_ENDPOINT") or os.environ.get(entry["variable"], "")
    if not endpoint:
        raise SystemExit(f"The AWS IoT endpoint for {tls} is not set.")
    work = workspace(registry, f"rx671-{backend}-{tls}-{kind}")
    log = ROOT / "rx671_wifi_e2studio_build.log"
    project = "aws_wifi_rx671_ek_tsip" if backend == "tsip" else "aws_wifi_rx671_ek"
    project_dir = ROOT / "Projects" / project / "e2studio_ccrx"
    sources = project_dir / "src"
    mot = project_dir / "HardwareDebug" / f"{project}.mot"
    rsu = ROOT / "rx671_app.rsu"
    cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
    command = ["pwsh", "-NoProfile", "-File", "tools/build_headless_rx671_wifi.ps1", "-ProjectRoot", ROOT,
               "-E2Studio", cli, "-Workspace", work, "-LogFile", log, "-WlanAllowBusSleepDelayMs", "600000",
               "-UseLocalJoinConfig"]
    build_env = None
    if backend == "tsip":
        command += ["-TlsBackend", "tsip"]
    if kind == "app":
        command += ["-UseAwsIotLocalConfig", "-AwsIotEndpoint", endpoint]
    else:
        # Heap size and SDIO clock are the values the Fleet image was proven with on this board.
        # The TSIP project has more static RAM, so 250 KiB of heap does not fit in the 384 KiB of RAM.
        heap_kb = "224" if backend == "tsip" else "250"
        command += ["-SkipAwsIotConfig", "-FleetProvisioningEnable",
                    "-FreeRtosHeapSizeKb", heap_kb, "-SdioRunClockDiv", "SDHI_DIV_8"]
        build_env = {**os.environ, "RX671_EK_FLEET_ENDPOINT": endpoint,
                     "RX671_EK_FLEET_TEMPLATE_NAME": os.environ[board["fleet_template_variable"]],
                     "RX671_EK_FLEET_CLAIM_CERT_PEM": os.environ[board["claim_certificate_variable"]],
                     "RX671_EK_FLEET_CLAIM_PRIVATE_KEY_PEM": os.environ[board["claim_private_key_variable"]]}
    if tls == "tls13":
        command += ["-RequireTlsVersion", "TLSv1.3"]
    try:
        try:
            run(command, timeout=1500, env=build_env)
        except subprocess.CalledProcessError:
            report_build_failure(log)
            raise
        run([sys.executable, "tools/build_rx671_fwup_v2_rsu.py", "--mot", mot, "--key", SIGNING_KEY,
             "--output", rsu], timeout=120)
        out.mkdir(parents=True, exist_ok=True)
        encrypt_file(rsu, out / "app.rsu.enc", key)
        print(f"  {out / 'app.rsu.enc'}  (encrypted, {rsu.stat().st_size} bytes of firmware)")
    finally:
        # Credentials were written into generated headers and build outputs of this checkout.
        rsu.unlink(missing_ok=True)
        keep_map(mot.with_suffix(".map"), out)
        subprocess.run(["git", "clean", "-fdxq", "--", str(sources)], cwd=ROOT, check=False)
        shutil.rmtree(mot.parent, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


def build_rx72n_app(registry: dict, backend: str, tls: str, kind: str, out: Path) -> None:
    project = "aws_ether_rx72n_envision_kit" if backend == "software" else "aws_ether_rx72n_envision_kit_tsip"
    work = workspace(registry, f"rx72n-{backend}{tls}-{kind}")
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
             "-TlsBackend", backend, *tls_arguments(backend, tls, "-RequireTlsVersion"), *extra], timeout=1500)
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


def cache_key(registry: dict, variant: str) -> str:
    """Name of the build inputs, or "" when the build must not be kept."""
    board, _, name = variant.partition("/")
    if name.rpartition("/")[2] in registry["boards"][board].get("image_secret_variable", {}):
        return ""       # the image carries credentials from CI variables
    tree = subprocess.run(["git", "ls-tree", "-r", "HEAD"], cwd=ROOT, check=True, capture_output=True,
                          text=True).stdout.splitlines()
    inputs = [line for line in tree
              if not line.split("\t", 1)[1].startswith(NOT_BUILD_INPUTS) and not line.endswith(".md")]
    digest = hashlib.sha256()
    for part in ("rxci build v1", variant, json.dumps(registry["boards"][board], sort_keys=True),
                 os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"], "\n".join(inputs)):
        digest.update(part.encode("utf-8") + b"\0")
    return digest.hexdigest()[:40]


def restore(entry: Path, out: Path) -> bool:
    """Copy an earlier build with the same inputs into the output folder."""
    if not (entry / "build.json").is_file():
        return False
    shutil.copytree(entry, out, dirs_exist_ok=True)
    os.utime(entry)     # the least recently used entries are deleted first
    made = json.loads((entry / "build.json").read_text(encoding="utf-8"))
    print(f"Reused the build of job {made['job']} (commit {made['commit'][:8]}): the build inputs are the same.")
    for file in sorted(out.iterdir()):
        print(f"  {file}  ({file.stat().st_size} bytes)")
    return True


def store(entry: Path, out: Path) -> None:
    """Keep a finished build for later jobs and drop the least recently used entries."""
    (out / "build.json").write_text(json.dumps({
        "job": os.environ.get("CI_JOB_ID", "local"), "pipeline": os.environ.get("CI_PIPELINE_ID", "local"),
        "commit": os.environ.get("CI_COMMIT_SHA", "local"), "inputs": entry.name}, indent=2) + "\n", encoding="utf-8")
    entry.parent.mkdir(parents=True, exist_ok=True)
    temporary = entry.with_name(f"{entry.name}.{os.environ.get('CI_JOB_ID', os.getpid())}.tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    shutil.copytree(out, temporary)
    shutil.rmtree(entry, ignore_errors=True)
    temporary.rename(entry)
    entries = sorted((path for path in entry.parent.iterdir() if path.is_dir()),
                     key=lambda path: path.stat().st_mtime, reverse=True)
    for old in entries[CACHE_ENTRIES:]:
        shutil.rmtree(old, ignore_errors=True)


def fetch_dependencies() -> None:
    """Clone the pinned dependencies. The job checked out only this repository."""
    if not os.environ.get("CI"):
        return          # a developer's checkout keeps its dependencies as they are
    include = subprocess.run(["git", "config", "--get", "include.path"], cwd=ROOT, capture_output=True,
                             text=True).stdout.strip()
    # The runner keeps its access settings for this GitLab in a file that clones do not inherit.
    access = ["-c", f"include.path={include}"] if include else []
    run(["git", *access, "submodule", "update", "--init", "--depth", "20", "--jobs", "8"], timeout=1500)


def build(registry: dict, variant: str, out: Path) -> None:
    if variant.partition("/")[0] not in registry["boards"]:
        raise SystemExit(f"Unknown board in build variant: {variant}")
    key = cache_key(registry, variant)
    entry = Path(registry["workspace_root"]) / "rxci-build-cache" / key if key else None
    if entry and os.environ.get("RXCI_REBUILD") != "1" and restore(entry, out):
        return
    fetch_dependencies()
    build_from_source(registry, variant, out)
    if entry:
        store(entry, out)


def build_from_source(registry: dict, variant: str, out: Path) -> None:
    board, _, name = variant.partition("/")
    if name == "common":
        return build_common(registry, board, out)
    flavor, _, kind = name.partition("/")
    backend, _, tls = flavor.partition("-")
    # RX72N and RX65N: "software" serves both TLS versions; "tsip-tls12" and "tsip-tls13" differ.
    if board in ("rx72n", "rx65n") and (flavor == "software" or (backend == "tsip" and tls in ("tls12", "tls13"))):
        app, ota = ((build_rx72n_app, build_rx72n_ota) if board == "rx72n" else (build_rx65n_app, build_rx65n_ota))
        if kind in ("app", "fleet"):
            return app(registry, backend, tls, kind, out)
        if kind == "ota":
            return ota(registry, backend, tls, out)
    if board == "rx671" and name in ("software-tls12/ota", "software-tls13/ota"):
        return build_rx671_ota(registry, name.split("/")[0].split("-")[1], out)
    if board == "rx671" and tls in ("tls12", "tls13") and (
            (backend == "software" and kind in ("app", "fleet")) or
            (backend == "tsip" and kind == "fleet")):
        return build_rx671_app(registry, backend, tls, kind, out)
    raise SystemExit(f"Build variant is not implemented yet: {variant}")

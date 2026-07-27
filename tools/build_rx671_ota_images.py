#!/usr/bin/env python3
"""Build traceable RX671 dual-bank OTA baseline and candidate artifacts.

The checked-in RX671 Wi-Fi project intentionally remains a normal linear-mode
runtime image.  This helper applies the OTA linker/BSP/FWUP settings only while
building each image, records the effective inputs, and restores every touched
source file byte-for-byte even when a build fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROFILE_NAME = "rx671-dual-bank-ota-v1"
PROJECT_RELATIVE = Path("Projects/aws_wifi_rx671_ek/e2studio_ccrx")
BOOTLOADER_PROJECT_RELATIVE = Path("Projects/boot_loader_rx671_ek/e2studio_ccrx")
BOOTLOADER_SUBMODULE_RELATIVE = (
    BOOTLOADER_PROJECT_RELATIVE / "lib/rx_bootloader"
)
LAYOUT_CONTRACT_NAME = "ota-layout-contract.json"
PROVENANCE_MANIFEST_NAME = "ota-layout-provenance.json"
REPORT_NAME = "ota-layout-report.json"
SIGNER_CERTIFICATE_NAME = "rx671-ota-signer.crt.pem"
ARTIFACT_BASENAME = "aws_wifi_rx671_ek"

PROFILE_PATHS = (
    Path(".cproject"),
    Path("src/frtos_config/r_fwup_config.h"),
    Path("src/smc_gen/r_config/r_bsp_config.h"),
    Path("src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h"),
)
PROVENANCE_PROJECT_PATHS = (
    Path(".cproject"),
    Path(LAYOUT_CONTRACT_NAME),
    Path("src/frtos_config/r_fwup_config.h"),
    Path("src/frtos_config/rm_littlefs_flash_config.h"),
    Path("src/smc_gen/r_config/r_bsp_config.h"),
    Path("src/sdio_host.c"),
    Path("src/whd_port/whd_port_resource.c"),
)
BOOTLOADER_PROVENANCE_PATHS = (
    BOOTLOADER_PROJECT_RELATIVE / ".cproject",
    BOOTLOADER_PROJECT_RELATIVE / "src/smc_gen/r_config/r_bsp_config.h",
    BOOTLOADER_SUBMODULE_RELATIVE / "config/rx671.h",
    BOOTLOADER_PROJECT_RELATIVE / "HardwareDebug/boot_loader_rx671_ek.map",
    BOOTLOADER_PROJECT_RELATIVE / "HardwareDebug/boot_loader_rx671_ek.mot",
)
WHD_BLOB_PATHS = (
    Path("Projects/aws_wifi_rx671_ek/external/type1yn-blobs/staging/43439A0.bin"),
    Path("Projects/aws_wifi_rx671_ek/external/type1yn-blobs/staging/nvram_1yn.bin"),
    Path("Projects/aws_wifi_rx671_ek/external/type1yn-blobs/staging/43439A0.clm_blob"),
)

NORMAL_START_VALUE = (
    "SU,SI,B_1,R_1,B_2,R_2,B,R,B_8,R_8/04,"
    "PResetPRG,C_1,C_2,C,C_8,C$*,D*,W*,L,P/0FFE00000,"
    "TYPE1YN_FW_BLOB/0FFF00000,TYPE1YN_NVRAM_BLOB/0FFF80000,"
    "TYPE1YN_CLM_BLOB/0FFF90000,EXCEPTVECT/0FFFFFF80,"
    "RESETVECT/0FFFFFFFC"
)
OTA_START_VALUE = (
    "SU,SI,B_1,R_1,B_2,R_2,B,R,B_8,R_8,RPFRAM2/04,"
    "PResetPRG,C_1,C_2,C,C_8,C$*,D*,W*,L,P,PFRAM2,"
    "TYPE1YN_FW_BLOB,TYPE1YN_NVRAM_BLOB,TYPE1YN_CLM_BLOB/0FFF00300,"
    "EXCEPTVECT/0FFFBFF80,RESETVECT/0FFFBFFFC"
)
ROM_MAPPING_ANCHOR = (
    '<listOptionValue builtIn="false" value="D_8=R_8"/>'
)
ROM_MAPPING_PFRAM2 = (
    '<listOptionValue builtIn="false" value="PFRAM2=RPFRAM2"/>'
)
DEFINE_ANCHOR = (
    '<listOptionValue builtIn="false" value="-define=__FUNCTION__=__func__"/>'
)
VERSION_MARKER_LINKER_OPTION = (
    '<listOptionValue builtIn="false" '
    'value="-symbol_forbid=_g_rx671_ota_image_version_marker"/>'
)


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    build: int

    @property
    def text(self) -> str:
        return f"{self.major}.{self.minor}.{self.build}"


def parse_version(value: str) -> Version:
    match = re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    if not match:
        raise ValueError(
            f"invalid version {value!r}: expected x.y.z without leading zeroes"
        )
    version = Version(*(int(group) for group in match.groups()))
    if version.major > 255 or version.minor > 255 or version.build > 65535:
        raise ValueError(
            f"invalid version {value!r}: major/minor must be 0..255 and "
            "build must be 0..65535"
        )
    return version


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


def make_ota_cproject(text: str, version: Version) -> str:
    existing_version_defines = re.findall(
        r'-define=APP_VERSION_(?:MAJOR|MINOR|BUILD)=[^"]+', text
    )
    if existing_version_defines:
        raise ValueError(
            ".cproject contains persistent APP_VERSION defines: "
            + ", ".join(existing_version_defines)
        )
    text = _replace_once(
        text,
        'modes="bank.single"',
        'modes="bank.dual"',
        ".cproject bank mode",
    )
    if ROM_MAPPING_PFRAM2 in text:
        raise ValueError(".cproject already contains the OTA PFRAM2 mapping")
    text = _replace_once(
        text,
        ROM_MAPPING_ANCHOR,
        ROM_MAPPING_ANCHOR + "\n\t\t\t\t\t\t\t\t\t" + ROM_MAPPING_PFRAM2,
        ".cproject ROM mapping",
    )
    text = _replace_once(
        text,
        f'value="{NORMAL_START_VALUE}"',
        f'value="{OTA_START_VALUE}"',
        ".cproject linker start",
    )
    defines = (
        f'<listOptionValue builtIn="false" value="-define=APP_VERSION_MAJOR={version.major}"/>',
        f'<listOptionValue builtIn="false" value="-define=APP_VERSION_MINOR={version.minor}"/>',
        f'<listOptionValue builtIn="false" value="-define=APP_VERSION_BUILD={version.build}"/>',
    )
    insertion = DEFINE_ANCHOR + "".join(
        "\n\t\t\t\t\t\t\t\t\t" + define for define in defines
    )
    text = _replace_once(
        text,
        DEFINE_ANCHOR,
        insertion,
        ".cproject compiler define anchor",
    )
    linker_option = re.search(
        r'(<option\b[^>]*\bsuperClass="'
        r'com\.renesas\.cdt\.managedbuild\.renesas\.ccrx\.linker\.option\.userBefore"'
        r'[^>]*>)(.*?)(</option>)',
        text,
        re.DOTALL,
    )
    if linker_option is None:
        raise ValueError(".cproject linker userBefore option was not found")
    if VERSION_MARKER_LINKER_OPTION in linker_option.group(2):
        raise ValueError(".cproject already contains the OTA marker linker option")
    updated_body = _replace_once(
        linker_option.group(2),
        '<listOptionValue builtIn="false" value=""/>',
        '<listOptionValue builtIn="false" value=""/>'
        + "\n\t\t\t\t\t\t\t\t\t"
        + VERSION_MARKER_LINKER_OPTION,
        ".cproject linker userBefore value",
    )
    return (
        text[: linker_option.start(2)]
        + updated_body
        + text[linker_option.end(2) :]
    )


def make_ota_bank_config(text: str, label: str) -> str:
    return _replace_once(
        text,
        "#define BSP_CFG_CODE_FLASH_BANK_MODE    (1)",
        "#define BSP_CFG_CODE_FLASH_BANK_MODE    (0)",
        label,
    )


def make_ota_fwup_config(text: str) -> str:
    return _replace_once(
        text,
        "#define FWUP_CFG_AREA_SIZE                          (0x00100000U)",
        "#define FWUP_CFG_AREA_SIZE                          (0x000C0000U)",
        "r_fwup_config.h install area size",
    )


class TemporaryOtaProfile:
    """Apply an OTA build profile and restore the source byte-for-byte."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.snapshots = {
            relative: (project_dir / relative).read_bytes()
            for relative in PROFILE_PATHS
        }

    def apply(self, version: Version) -> None:
        cproject = self.snapshots[Path(".cproject")].decode("utf-8")
        fwup = self.snapshots[Path("src/frtos_config/r_fwup_config.h")].decode(
            "utf-8"
        )
        bsp = self.snapshots[
            Path("src/smc_gen/r_config/r_bsp_config.h")
        ].decode("utf-8")
        reference = self.snapshots[
            Path("src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h")
        ].decode("utf-8")
        (self.project_dir / ".cproject").write_text(
            make_ota_cproject(cproject, version), encoding="utf-8", newline=""
        )
        (self.project_dir / "src/frtos_config/r_fwup_config.h").write_text(
            make_ota_fwup_config(fwup), encoding="utf-8", newline=""
        )
        (self.project_dir / "src/smc_gen/r_config/r_bsp_config.h").write_text(
            make_ota_bank_config(bsp, "r_bsp_config.h bank mode"),
            encoding="utf-8",
            newline="",
        )
        (
            self.project_dir
            / "src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h"
        ).write_text(
            make_ota_bank_config(reference, "r_bsp_config_reference.h bank mode"),
            encoding="utf-8",
            newline="",
        )

    def restore(self) -> None:
        for relative, content in self.snapshots.items():
            (self.project_dir / relative).write_bytes(content)

    def __enter__(self) -> TemporaryOtaProfile:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.restore()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def source_state(repo_root: Path) -> str:
    unstaged = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--binary", "--ignore-submodules=dirty"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    staged = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--cached",
            "--binary",
            "--ignore-submodules=dirty",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    untracked = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--others",
            "--exclude-standard",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.splitlines()
    return json.dumps(
        {
            "unstaged": unstaged,
            "staged": staged,
            "untracked": sorted(untracked),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def tracked_source_is_dirty(repo_root: Path) -> bool:
    state = json.loads(source_state(repo_root))
    return bool(state["unstaged"] or state["staged"] or state["untracked"])


def _safe_recreate_output(path: Path, repo_root: Path) -> None:
    allowed_root = (repo_root / "build/rx671-ota").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"refusing to recreate output outside {allowed_root}: {resolved}"
        ) from exc
    if resolved == allowed_root:
        raise ValueError("output must be a child of build/rx671-ota")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _validate_output_root(path: Path, repo_root: Path) -> None:
    allowed_root = (repo_root / "build/rx671-ota").resolve()
    if path.resolve() != allowed_root:
        raise ValueError(
            f"output root must be the dedicated repository path {allowed_root}: "
            f"{path.resolve()}"
        )


def _validate_workspace_root(path: Path) -> None:
    allowed_root = Path("C:/ai/codex/ws").resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"e2 studio workspace must stay below {allowed_root}: {resolved}"
        ) from exc
    if not relative.parts:
        raise ValueError(
            f"e2 studio workspace must be a child of {allowed_root}"
        )


def _run(command: list[str], cwd: Path, *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+", subprocess.list2cmdline(command), flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
    )


def _copy_build_outputs(project_dir: Path, artifact_dir: Path) -> dict[str, Path]:
    output_dir = project_dir / "HardwareDebug"
    outputs: dict[str, Path] = {}
    for extension in ("mot", "abs", "map"):
        source = output_dir / f"{ARTIFACT_BASENAME}.{extension}"
        if not source.is_file():
            raise FileNotFoundError(f"RX671 OTA build artifact missing: {source}")
        destination = artifact_dir / source.name
        shutil.copy2(source, destination)
        outputs[extension] = destination
    return outputs


def _copy_bootloader_outputs(repo_root: Path, output_root: Path) -> list[Path]:
    artifact_dir = output_root / "bootloader"
    _safe_recreate_output(artifact_dir, repo_root)
    source_dir = repo_root / BOOTLOADER_PROJECT_RELATIVE / "HardwareDebug"
    copied: list[Path] = []
    for extension in ("mot", "abs", "map"):
        source = source_dir / f"boot_loader_rx671_ek.{extension}"
        if not source.is_file():
            raise FileNotFoundError(
                f"RX671 bootloader artifact missing; run its build first: {source}"
            )
        destination = artifact_dir / source.name
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def _copy_effective_inputs(
    repo_root: Path, project_dir: Path, artifact_dir: Path
) -> list[Path]:
    snapshot_root = artifact_dir / "effective-config"
    copied: list[Path] = []
    for relative in PROVENANCE_PROJECT_PATHS:
        source = project_dir / relative
        destination = snapshot_root / PROJECT_RELATIVE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    for relative in BOOTLOADER_PROVENANCE_PATHS:
        source = repo_root / relative
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def _create_manifest(
    *,
    repo_root: Path,
    project_dir: Path,
    artifact_dir: Path,
    version: Version,
    dirty: bool,
    outputs: dict[str, Path],
    rsu_path: Path,
    certificate_path: Path,
    effective_inputs: list[Path],
    bootloader_artifacts: list[Path],
) -> Path:
    required = [
        *(project_dir / relative for relative in PROVENANCE_PROJECT_PATHS),
        *outputs.values(),
        *WHD_BLOB_PATHS,
        *BOOTLOADER_PROVENANCE_PATHS,
        rsu_path,
        certificate_path,
        *effective_inputs,
        *bootloader_artifacts,
    ]
    absolute_required = [
        path if path.is_absolute() else repo_root / path for path in required
    ]
    missing = [str(path) for path in absolute_required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "provenance input is missing: " + ", ".join(missing)
        )
    hashes = {
        path.resolve().relative_to(repo_root.resolve()).as_posix(): sha256(path)
        for path in absolute_required
    }
    source_sha = _git(repo_root, "rev-parse", "HEAD")
    gitlink_line = _git(
        repo_root,
        "ls-tree",
        "HEAD",
        "--",
        BOOTLOADER_SUBMODULE_RELATIVE.as_posix(),
    )
    match = re.fullmatch(
        rf"160000\s+commit\s+([0-9a-f]{{40}})\t"
        rf"{re.escape(BOOTLOADER_SUBMODULE_RELATIVE.as_posix())}",
        gitlink_line,
    )
    if not match:
        raise RuntimeError("could not resolve the RX671 bootloader gitlink SHA")
    manifest = {
        "schema_version": 1,
        "source_sha": source_sha,
        "dirty": dirty,
        "project_path": PROJECT_RELATIVE.as_posix(),
        "profile": PROFILE_NAME,
        "ota_image_version": version.text,
        "rsu_path": rsu_path.relative_to(repo_root).as_posix(),
        "signer_certificate_path": certificate_path.relative_to(repo_root).as_posix(),
        "sha256": dict(sorted(hashes.items())),
        "gitlinks": {
            BOOTLOADER_SUBMODULE_RELATIVE.as_posix(): match.group(1),
        },
    }
    manifest_path = artifact_dir / PROVENANCE_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _dirty_analysis_is_structurally_safe(report: dict[str, object]) -> bool:
    gates = report.get("gates")
    if not isinstance(gates, list):
        return False
    allowed_non_pass = {
        "artifact_provenance",
        "whd_blob_sizes",
        "map_image_single_area",
        "mot_image_single_area",
    }
    saw_dirty_provenance = False
    for gate in gates:
        if not isinstance(gate, dict):
            return False
        name = gate.get("name")
        status = gate.get("status")
        detail = gate.get("detail")
        if status == "PASS":
            continue
        if name not in allowed_non_pass:
            return False
        if name == "artifact_provenance":
            saw_dirty_provenance = (
                status == "FAIL"
                and isinstance(detail, str)
                and "dirty=false" in detail
            )
        elif status != "UNKNOWN":
            return False
    return saw_dirty_provenance


def _build_one(
    *,
    repo_root: Path,
    project_dir: Path,
    artifact_dir: Path,
    version: Version,
    e2studio: Path,
    workspace: Path,
    signing_key: Path,
    certificate_source: Path,
    dirty: bool,
    allow_dirty: bool,
    timeout_seconds: int,
    bootloader_artifacts: list[Path],
) -> None:
    _safe_recreate_output(artifact_dir, repo_root)
    build_log = artifact_dir / "e2studio-build.log"
    _run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(repo_root / "tools/build_headless_rx671_wifi.ps1"),
            "-ProjectRoot",
            str(repo_root),
            "-E2Studio",
            str(e2studio),
            "-Workspace",
            str(workspace),
            "-LogFile",
            str(build_log),
            "-E2StudioTimeoutSeconds",
            str(timeout_seconds),
            "-OtaImageVersion",
            version.text,
            "-SkipAwsIotConfig",
        ],
        repo_root,
    )
    outputs = _copy_build_outputs(project_dir, artifact_dir)
    rsu_path = artifact_dir / f"{ARTIFACT_BASENAME}.rsu"
    _run(
        [
            sys.executable,
            str(repo_root / "tools/build_rx671_fwup_v2_rsu.py"),
            "--mot",
            str(outputs["mot"]),
            "--key",
            str(signing_key),
            "--output",
            str(rsu_path),
        ],
        repo_root,
    )
    certificate_path = artifact_dir / SIGNER_CERTIFICATE_NAME
    shutil.copy2(certificate_source, certificate_path)
    effective_inputs = _copy_effective_inputs(
        repo_root, project_dir, artifact_dir
    )
    _create_manifest(
        repo_root=repo_root,
        project_dir=project_dir,
        artifact_dir=artifact_dir,
        version=version,
        dirty=dirty,
        outputs=outputs,
        rsu_path=rsu_path,
        certificate_path=certificate_path,
        effective_inputs=effective_inputs,
        bootloader_artifacts=bootloader_artifacts,
    )
    analysis_environment = os.environ.copy()
    analysis_environment["PYTHONIOENCODING"] = "utf-8"
    analysis = subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools/ci/analyze_rx671_ota_layout.py"),
            "--project-dir",
            str(project_dir),
            "--build-dir",
            str(artifact_dir),
            "--rsu",
            str(rsu_path),
            "--signer-certificate",
            str(certificate_path),
            "--expected-version",
            version.text,
            "--json",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=analysis_environment,
    )
    (artifact_dir / REPORT_NAME).write_text(analysis.stdout, encoding="utf-8")
    if analysis.stderr:
        print(analysis.stderr, file=sys.stderr)
    dirty_analysis_safe = False
    if analysis.returncode != 0 and allow_dirty:
        try:
            dirty_analysis_safe = _dirty_analysis_is_structurally_safe(
                json.loads(analysis.stdout)
            )
        except json.JSONDecodeError:
            dirty_analysis_safe = False
    if analysis.returncode != 0 and not dirty_analysis_safe:
        raise RuntimeError(
            f"RX671 OTA layout analysis failed for {version.text}; "
            f"see {artifact_dir / REPORT_NAME}"
        )
    if analysis.returncode != 0:
        print(
            f"WARNING: analysis exit={analysis.returncode} contains only the "
            "expected dirty-provenance block and dependent UNKNOWN gates",
            file=sys.stderr,
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--baseline-version", default="0.1.0")
    parser.add_argument("--candidate-version", default="0.1.1")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_root / "build/rx671-ota",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(
            "C:/ai/codex/ws/iot-reference-rx-rx671-ota-2026-04-2"
        ),
    )
    parser.add_argument(
        "--e2studio",
        type=Path,
        default=Path(
            "C:/Renesas/e2_studio_2026_04_2/eclipse/e2studioc.exe"
        ),
    )
    parser.add_argument(
        "--signing-key",
        type=Path,
        default=default_root / "sample_keys/secp256r1.privatekey",
    )
    parser.add_argument("--e2studio-timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help=(
            "Allow an exploratory build from modified tracked source. "
            "The manifest records dirty=true and formal analysis remains blocked."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    project_dir = repo_root / PROJECT_RELATIVE
    output_root = args.output_root.resolve()
    _validate_output_root(output_root, repo_root)
    _validate_workspace_root(args.workspace_root)
    signing_key = args.signing_key.resolve()
    versions = (
        ("baseline", parse_version(args.baseline_version)),
        ("candidate", parse_version(args.candidate_version)),
    )
    if versions[0][1] == versions[1][1]:
        raise SystemExit("baseline and candidate versions must differ")
    if not args.e2studio.is_file():
        raise SystemExit(f"e2 studio executable not found: {args.e2studio}")
    if not signing_key.is_file():
        raise SystemExit(f"OTA signing key not found: {signing_key}")
    initial_source_state = source_state(repo_root)
    dirty = tracked_source_is_dirty(repo_root)
    if dirty and not args.allow_dirty:
        raise SystemExit(
            "tracked source is dirty; commit the deterministic OTA inputs "
            "before generating formal provenance"
        )

    certificate_source = output_root / SIGNER_CERTIFICATE_NAME
    output_root.mkdir(parents=True, exist_ok=True)
    bootloader_artifacts = _copy_bootloader_outputs(repo_root, output_root)
    _run(
        [
            sys.executable,
            str(repo_root / "tools/generate_signer_cert.py"),
            "--key",
            str(signing_key),
            "--out",
            str(certificate_source),
            "--common-name",
            "iot-reference-rx RX671 OTA Signer",
        ],
        repo_root,
    )

    try:
        with TemporaryOtaProfile(project_dir) as profile:
            for label, version in versions:
                profile.apply(version)
                artifact_dir = output_root / f"{label}-{version.text}"
                _build_one(
                    repo_root=repo_root,
                    project_dir=project_dir,
                    artifact_dir=artifact_dir,
                    version=version,
                    e2studio=args.e2studio.resolve(),
                    workspace=args.workspace_root.resolve(),
                    signing_key=signing_key,
                    certificate_source=certificate_source,
                    dirty=dirty,
                    allow_dirty=args.allow_dirty,
                    timeout_seconds=args.e2studio_timeout_seconds,
                    bootloader_artifacts=bootloader_artifacts,
                )
    finally:
        # TemporaryOtaProfile restores the tracked inputs. Keep this explicit
        # postcondition so an accidental future profile-path omission fails.
        if source_state(repo_root) != initial_source_state:
            raise RuntimeError(
                "RX671 OTA helper did not restore the tracked source state"
            )

    print(f"RX671 OTA baseline/candidate artifacts: {output_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build a CK-RX65N BG96 OTA candidate with a temporary app version."""

from __future__ import annotations

import argparse
import os
import re
import shutil
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


def run_logged(
    command: list[str],
    cwd: Path,
    log,
    env: dict[str, str],
    timeout: int,
    allow_nonzero_exit: bool = False,
) -> None:
    print("+ " + " ".join(command))
    log.write("+ " + " ".join(command) + "\n")
    log.flush()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"build command timed out after {timeout} seconds: {' '.join(command)}") from exc
    if result.returncode != 0 and not allow_nonzero_exit:
        raise RuntimeError(f"build command failed with exit {result.returncode}: {' '.join(command)}")
    if result.returncode != 0:
        print(
            "warning: build command returned "
            f"exit {result.returncode}; continuing after generated file validation"
        )
        log.write(
            "warning: build command returned "
            f"exit {result.returncode}; continuing after generated file validation\n"
        )
        log.flush()


def e2studio_plugin_dir(e2studio_cli: Path) -> Path | None:
    if not e2studio_cli.exists():
        return None
    base_dir = e2studio_cli.resolve().parent
    for candidate in (base_dir / "plugins", base_dir / "eclipse" / "plugins"):
        if candidate.is_dir():
            return candidate
    return None


def resolve_plugin_tool(e2studio_cli: Path, plugin_glob: str, relative_path: str) -> Path | None:
    plugins = e2studio_plugin_dir(e2studio_cli)
    if plugins is None:
        return None
    for plugin_dir in sorted(plugins.glob(plugin_glob), reverse=True):
        candidate = plugin_dir / relative_path
        if candidate.exists():
            return candidate.resolve()
    return None


def resolve_make(e2studio_cli: Path, explicit_make: Path | None) -> Path:
    if explicit_make is not None:
        if not explicit_make.exists():
            raise RuntimeError(f"make executable not found: {explicit_make}")
        return explicit_make.resolve()

    candidate = resolve_plugin_tool(
        e2studio_cli,
        "com.renesas.ide.exttools.gnumake.win32.x86_64_*",
        "mk/make.exe",
    )
    if candidate is not None:
        return candidate

    raise RuntimeError("GNU make was not found. Set RX65N_BG96_MAKE or provide a valid e2 studio path.")


def selected_mbedtls_config(tls_backend: str, require_tls_version: str | None) -> str | None:
    if tls_backend.lower() != "tsip":
        return None
    normalized_tls = (require_tls_version or "").lower()
    if normalized_tls in {"tlsv1.3", "tls1.3", "tls13"}:
        return "aws_mbedtls_config_with_tsip13.h"
    return "aws_mbedtls_config_with_tsip.h"


def use_mbedtls_config_file(app_dir: Path, config_file: str) -> None:
    cproject = app_dir / ".cproject"
    if not cproject.exists():
        raise RuntimeError(f".cproject not found: {cproject}")

    content = cproject.read_text(encoding="utf-8")
    pattern = re.compile(
        r'MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip(?:13)?\.h&quot;&gt;'
    )
    replacement = f'MBEDTLS_CONFIG_FILE=&lt;&quot;{config_file}&quot;&gt;'
    updated, count = pattern.subn(replacement, content)
    if count == 0:
        raise RuntimeError(f"TSIP mbed TLS config macro not found in {cproject}")
    cproject.write_text(updated, encoding="utf-8", newline="")
    print(f"Selected mbed TLS config for OTA candidate: {config_file}")


def generated_mbedtls_configs(app_dir: Path) -> set[str]:
    hardware_debug = app_dir / "HardwareDebug"
    if not hardware_debug.exists():
        return set()

    configs: set[str] = set()
    command_file_names = {"cSubCommand.tmp", "cDepSubCommand.tmp"}
    config_re = re.compile(r'MBEDTLS_CONFIG_FILE=<"([^"]+)">')
    for path in hardware_debug.rglob("*"):
        if path.name not in command_file_names or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        configs.update(config_re.findall(text))
    return configs


def clear_generated_build_files(app_dir: Path) -> None:
    hardware_debug = app_dir / "HardwareDebug"
    if hardware_debug.exists():
        shutil.rmtree(hardware_debug)
        print(f"Cleared generated build files: {hardware_debug}")


def reset_generated_build_files_on_config_drift(app_dir: Path, expected_config: str) -> None:
    configs = generated_mbedtls_configs(app_dir)
    if configs and configs != {expected_config}:
        print(
            "Generated build files use a different TSIP mbed TLS config; "
            f"regenerating. Expected: {expected_config}, observed: {', '.join(sorted(configs))}"
        )
        clear_generated_build_files(app_dir)


def resolve_e2studio_headless(e2studio_cli: Path) -> Path:
    if not e2studio_cli.exists():
        raise RuntimeError(f"e2 studio executable not found: {e2studio_cli}")
    console = e2studio_cli.resolve().parent / "e2studioc.exe"
    if console.exists():
        return console.resolve()
    return e2studio_cli.resolve()


def run_e2studio_managed_build(
    e2studio_cli: Path,
    workspace: Path,
    app_dir: Path,
    log,
    timeout: int,
) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)

    command = [
        str(resolve_e2studio_headless(e2studio_cli)),
        "--launcher.suppressErrors",
        "-nosplash",
        "-application",
        "org.eclipse.cdt.managedbuilder.core.headlessbuild",
        "-data",
        str(workspace),
        "-import",
        str(app_dir),
        "-build",
        "all",
    ]
    run_logged(command, app_dir, log, os.environ.copy(), timeout, allow_nonzero_exit=True)


def build_environment(e2studio_cli: Path, ccrx_bin_arg: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    if ccrx_bin_arg is not None:
        ccrx_bin = ccrx_bin_arg
    elif env.get("BIN_RX"):
        ccrx_bin = Path(env["BIN_RX"])
    elif env.get("CCRX_BIN"):
        ccrx_bin = Path(env["CCRX_BIN"])
    else:
        ccrx_bin = Path(r"C:\Program Files (x86)\Renesas\RX\3_7_0\bin")
    if not ccrx_bin.exists():
        raise RuntimeError(f"CC-RX bin directory not found: {ccrx_bin}")

    path_entries = [str(ccrx_bin.resolve())]
    busybox_bin = resolve_plugin_tool(
        e2studio_cli,
        "com.renesas.ide.exttools.busybox.win32.x86_64_*",
        "bin",
    )
    if busybox_bin is not None:
        path_entries.append(str(busybox_bin))
    path_entries.append(env.get("PATH", ""))
    env["PATH"] = os.pathsep.join(path_entries)
    return env


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
    parser.add_argument("--make", type=Path, default=Path(os.environ["RX65N_BG96_MAKE"]) if os.environ.get("RX65N_BG96_MAKE") else None)
    parser.add_argument("--ccrx-bin", type=Path, default=None)
    parser.add_argument(
        "--tls-backend",
        choices=("software", "tsip"),
        default=os.environ.get("RX65N_BG96_TLS_BACKEND", "software"),
    )
    parser.add_argument(
        "--require-tls-version",
        default=os.environ.get("RX65N_BG96_REQUIRE_TLS_VERSION", ""),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    app_dir = (repo_root / args.app_dir).resolve() if not args.app_dir.is_absolute() else args.app_dir.resolve()
    app_project_name = app_dir.parent.name
    output_dir = (repo_root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir.resolve()
    signing_key = (repo_root / args.signing_key).resolve() if not args.signing_key.is_absolute() else args.signing_key.resolve()

    demo_config = app_dir / "src/frtos_config/demo_config.h"
    app_mot = app_dir / f"HardwareDebug/{app_project_name}.mot"
    app_abs = app_dir / f"HardwareDebug/{app_project_name}.abs"
    app_makefile = app_dir / "HardwareDebug/makefile"
    rsu_tool = repo_root / "tools/create_bg96_rsu.py"
    cert_tool = repo_root / "tools/generate_bg96_ota_signer_cert.py"

    for path in (demo_config, signing_key, args.e2studio_cli, rsu_tool, cert_tool):
        if not path.exists():
            raise RuntimeError(f"required path not found: {path}")

    make_exe = resolve_make(args.e2studio_cli, args.make)
    build_env = build_environment(args.e2studio_cli, args.ccrx_bin)
    tls_config = selected_mbedtls_config(args.tls_backend, args.require_tls_version)

    print(f"TLS backend: {args.tls_backend}")
    print(f"Require TLS version: {args.require_tls_version or '<none>'}")

    output_dir.mkdir(parents=True, exist_ok=True)
    version_text = ".".join(str(part) for part in args.version)
    version_token = version_text.replace(".", "_")
    full_rsu = output_dir / f"bg96_{version_token}.rsu"
    ota_payload = output_dir / f"bg96_{version_token}_ota_payload.bin"
    ota_payload_sig_der = output_dir / f"bg96_{version_token}_ota_payload.sig.der"
    code_sign_cert = output_dir / "bg96_ota_codesign_cert.pem"
    log_path = output_dir / "build_bg96_ota_candidate.log"

    snapshot_paths = [
        demo_config,
        app_dir / ".project",
        app_dir / ".cproject",
        app_dir / ".settings/com.renesas.smc.generationsetting.properties",
        app_dir / ".settings/com.renesas.smc.tools.swcomponent.fit.properties",
    ]
    snapshot_paths.extend(app_dir.glob("*.rcpc"))
    snapshot_paths.extend(app_dir.glob("*.scfg"))
    settings_dir = app_dir / ".settings"
    if settings_dir.exists():
        snapshot_paths.extend(path for path in settings_dir.iterdir() if path.is_file())
    snapshots = {path: path.read_bytes() for path in snapshot_paths if path.exists()}
    original = snapshots[demo_config].decode("utf-8")
    try:
        if tls_config:
            use_mbedtls_config_file(app_dir, tls_config)
            reset_generated_build_files_on_config_drift(app_dir, tls_config)

        if not app_makefile.exists():
            with log_path.open("w", encoding="utf-8", errors="replace") as log:
                run_e2studio_managed_build(
                    args.e2studio_cli,
                    args.workspace,
                    app_dir,
                    log,
                    args.e2studio_timeout,
                )
        if not app_makefile.exists():
            raise RuntimeError(f"required path not found after e2 studio build: {app_makefile}")

        write_utf8(demo_config, replace_version(original, args.version))

        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            app_build_dir = app_dir / "HardwareDebug"
            run_logged([str(make_exe), "clean"], app_build_dir, log, build_env, args.e2studio_timeout)
            run_logged([str(make_exe), "-j2", f"{app_project_name}.mot"], app_build_dir, log, build_env, args.e2studio_timeout)

        if not app_mot.exists():
            raise RuntimeError(f"{app_project_name}.mot was not generated: {app_mot}")
        if not app_abs.exists():
            raise RuntimeError(f"{app_project_name}.abs was not generated: {app_abs}")

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
                "--signature-der-output",
                str(ota_payload_sig_der),
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
    print(f"  ota_payload_sig_der: {ota_payload_sig_der}")
    print(f"  code_sign_cert: {code_sign_cert}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

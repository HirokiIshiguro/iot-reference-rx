"""Read-only IDT host preflight for the selected profile and runner identity."""
from __future__ import annotations

import argparse
import getpass
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

try:
    from .host_profile import load_host_profile
    from .targets import get_target, target_ids
except ImportError:
    from host_profile import load_host_profile
    from targets import get_target, target_ids


def requirements(filename: str) -> dict[str, str]:
    lines = Path(__file__).with_name(filename).read_text(encoding="utf-8").splitlines()
    return dict(line.strip().split("==", 1) for line in lines if line.strip() and not line.startswith("#"))


def command(args: list[str], *, env=None) -> tuple[int, str]:
    try:
        process = subprocess.run(args, env=env, capture_output=True, timeout=45)
        raw = process.stdout
        output = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\0" in raw[:100] else "utf-8", errors="replace")
        return process.returncode, output.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def installed_toolchain(profile: dict[str, str], file_versions: dict) -> dict:
    """Read the Eclipse product/release files and the actual compiler PE version."""
    eclipse = Path(profile["e2studio_cli"]).parent

    def properties(path):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            return dict(line.split("=", 1) for line in lines if "=" in line and not line.lstrip().startswith("#"))
        except (OSError, UnicodeError):
            return {}

    product = properties(eclipse / ".eclipseproduct")
    configuration = properties(eclipse / "configuration/config.ini")
    release = configuration.get("e2studio.release")
    platform_version = product.get("version")
    product_id = product.get("id")
    e2_verified = bool(release and platform_version and product_id)
    e2_matches = e2_verified and (release, platform_version, product_id) == (
        "2026-04.2", "26.4.2", "com.renesas.platform")
    compiler = file_versions.get("ccrx") or {}
    compiler_version = compiler.get("ProductVersion")
    compiler_match = bool(compiler_version and re.fullmatch(r"3\.0?7\.0{1,2}(?:\.0{1,2})?", compiler_version))
    return {
        "e2studio": {"status": "verified" if e2_matches else "mismatch" if e2_verified else "unverified",
                     "release": release, "platform_version": platform_version, "product_id": product_id},
        "ccrx": {"status": "verified" if compiler_match else "mismatch" if compiler_version else "unverified",
                 "version": compiler_version},
    }


def check_host(profile: dict[str, str], *, check_aws: bool = False, target=None) -> dict:
    target = get_target() if target is None else target
    checks = []

    def record(name: str, passed: bool, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    record("windows_x64", os.name == "nt" and platform.machine().lower() in {"amd64", "x86_64"}, platform.platform())
    record("windows_python", sys.version_info >= (3, 11), {"version": platform.python_version(), "executable": sys.executable})
    installed = {}
    for name, expected in requirements("requirements-windows.txt").items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        installed[name] = {"actual": actual, "expected": expected}
    record("windows_python_packages", all(item["actual"] == item["expected"] for item in installed.values()), installed)
    code, _ = command([sys.executable, "-m", "pip", "check"])
    record("windows_python_dependency_consistency", code == 0)
    for key in ("windows_powershell", "e2studio_cli", "ccrx", "windows_ssh", "windows_scp"):
        record(key, Path(profile[key]).is_file(), profile[key])
    wsl_version = None
    linux_os_release = {}
    if os.name == "nt":
        code, version = command([profile["windows_powershell"], "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"])
        record("powershell_7", code == 0 and version.startswith("7."), version if code == 0 else "unavailable")
        tool_versions = {}
        for key in ("e2studio_cli", "ccrx"):
            env = dict(os.environ, IDT_CHECK_TOOL_PATH=profile[key])
            code, value = command([profile["windows_powershell"], "-NoProfile", "-Command",
                "(Get-Item -LiteralPath $env:IDT_CHECK_TOOL_PATH).VersionInfo | Select-Object FileVersion,ProductVersion | ConvertTo-Json -Compress"], env=env)
            try:
                tool_versions[key] = json.loads(value) if code == 0 else None
            except json.JSONDecodeError:
                tool_versions[key] = None
        wsl = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/wsl.exe")
        code, value = command([wsl, "--version"])
        wsl_version = value if code == 0 else None
        code, distributions = command([wsl, "--list", "--verbose"])
        match = re.search(r"^\s*\*?\s*" + re.escape(profile["wsl_distribution"]) + r"\s+.+?\s+(\d+)\s*$", distributions, re.MULTILINE)
        record("wsl2_distribution", code == 0 and match is not None and match.group(1) == "2", profile["wsl_distribution"])
        probe = (
            "import importlib.metadata as m,json,platform,sys; "
            "print(json.dumps({'machine':platform.machine(),'python':platform.python_version(),"
            "'executable':sys.executable,'os_release':{key:platform.freedesktop_os_release().get(key) for key in ['ID','VERSION_ID','PRETTY_NAME']},"
            "'packages':{name:m.version(name) for name in "
            + repr(list(requirements("requirements-wsl.txt"))) + "}}))"
        )
        code, value = command([wsl, "-d", profile["wsl_distribution"], "--exec", profile["wsl_python"], "-c", probe])
        try:
            linux = json.loads(value) if code == 0 else {}
        except json.JSONDecodeError:
            linux = {}
        linux_os_release = linux.get("os_release", {})
        version = tuple(int(part) for part in linux.get("python", "0.0").split(".")[:2])
        record("wsl_x64_python_packages", linux.get("machine") == "x86_64" and version >= (3, 11)
               and linux.get("packages") == requirements("requirements-wsl.txt"), linux)
        code, _ = command([wsl, "-d", profile["wsl_distribution"], "--exec", profile["wsl_python"], "-m", "pip", "check"])
        record("wsl_python_dependency_consistency", code == 0)
        # Only ask for the hostname. Do not open the UART, take a bench lock,
        # reset or flash a board. Run under the eventual service account.
        code, hostname = command([profile["windows_ssh"], "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", target["ssh_alias"], "hostname"])
        record("pinned_bench_ssh_identity", code == 0 and hostname == target["hostname"],
               target["ssh_alias"] + " -> " + target["hostname"])
    else:
        tool_versions = {}
    toolchain = installed_toolchain(profile, tool_versions)
    record("e2studio_release", toolchain["e2studio"]["status"] == "verified", toolchain["e2studio"])
    record("ccrx_release", toolchain["ccrx"]["status"] == "verified", toolchain["ccrx"])
    aws = {"checked": False}
    if check_aws:
        try:
            import boto3
            from botocore.config import Config
            session = boto3.Session()
            identity = session.client("sts", config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 0})).get_caller_identity()
            aws = {"checked": True, "account": identity["Account"], "arn": identity["Arn"]}
            record("aws_caller_identity", True)
        except Exception as error:
            aws = {"checked": True, "error_type": type(error).__name__}
            record("aws_caller_identity", False)
    return {"host_preflight_passed": all(check["passed"] for check in checks),
            "host": platform.node(), "execution_user": getpass.getuser(), "target_id": target["id"],
            "ci_runner_description": os.getenv("CI_RUNNER_DESCRIPTION"), "profile": profile,
            "checks": checks, "tool_file_versions": tool_versions, "wsl_version": wsl_version,
            "linux_os_release": linux_os_release, "installed_toolchain": toolchain, "aws": aws,
            "qualification": "not-assessed", "compiler_license": "not-verified; requires a representative firmware compile/link",
            "toolchain_expected": {"e2studio": "2026-04.2", "ccrx": "3.07.00"},
            "limitations": ["Host checks do not prove firmware build, AWS test permissions or IDT E2E success",
                            "Run again as the GitLab Runner service identity; WSL, SSH and AWS configuration are user-specific"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--target", choices=target_ids(), default=None)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-aws", action="store_true", help="Also call read-only AWS STS GetCallerIdentity")
    args = parser.parse_args()
    result = check_host(load_host_profile(args.profile), check_aws=args.check_aws,
                        target=get_target(args.target))
    text = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["host_preflight_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

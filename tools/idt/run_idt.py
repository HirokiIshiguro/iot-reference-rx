#!/usr/bin/env python3
"""Run explicit RX72N IDT checks; a partial group never qualifies a release."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET

VERSION = "4.9.0"
SUITE = "FRQ_2.5.0"
SOURCE = Path(__file__).resolve().parents[2]
INSTALL = Path(r"C:\ai\codex\tools\aws-idt")
RUNTIME = Path(r"C:\ai\codex\tmp\rx72n-idt")
WSL = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/wsl.exe"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def restrict_runtime(path: Path) -> None:
    identity = subprocess.check_output(["whoami.exe", "/user", "/fo", "csv", "/nh"], encoding="utf-8", errors="replace")
    sid = next(csv.reader(io.StringIO(identity)))[1]
    if not sid.startswith("S-1-"):
        raise RuntimeError("Cannot determine runtime directory owner SID")
    result = subprocess.run(["icacls.exe", str(path), "/inheritance:r", "/grant:r",
                             "*" + sid + ":(OI)(CI)F", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"],
                            capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("Cannot restrict the IDT credential runtime directory")


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(SOURCE), *args], encoding="utf-8").strip()


def manifest_version() -> str:
    match = re.search(r'^version:\s*["\']?([^"\'\s]+)', (SOURCE / "manifest.yml").read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise RuntimeError("Cannot read FreeRTOS version from the source manifest")
    return match.group(1)


def test_library_sha() -> str:
    library = SOURCE / "Test/FreeRTOS-Libraries-Integration-Tests"
    root = subprocess.check_output(["git", "-C", str(library), "rev-parse", "--show-toplevel"], encoding="utf-8").strip()
    if Path(root).resolve() != library.resolve():
        raise RuntimeError("Initialize the pinned FreeRTOS integration-test submodule before running IDT")
    return subprocess.check_output(["git", "-C", str(library), "rev-parse", "HEAD"], encoding="utf-8").strip()


def submodule_pins() -> list[dict]:
    lines = subprocess.check_output(["git", "-C", str(SOURCE), "submodule", "status", "--recursive"], encoding="utf-8").splitlines()
    pins = []
    for line in lines:
        match = re.match(r"^([-+ U])([0-9a-f]{40})\s+(\S+)", line)
        if match:
            pins.append({"path": match.group(3), "sha": match.group(2), "state": match.group(1)})
    return pins


def redact(text: str, credentials) -> str:
    for value in (credentials.access_key, credentials.secret_key, credentials.token):
        if value:
            text = text.replace(value, "[REDACTED]")
    return text


def export_report(source: Path, target: Path, credentials) -> None:
    """Retain test identities/status/counts, never raw errors or serial output."""
    parsed = ET.parse(source).getroot()
    allowed = {"testsuites", "testsuite", "testcase", "failure", "error", "skipped"}
    attributes = {"name", "classname", "time", "tests", "failures", "errors", "skipped", "disabled"}

    def clean(node):
        tag = node.tag.rsplit("}", 1)[-1]
        result = ET.Element(tag, {key: redact(value, credentials) for key, value in node.attrib.items() if key in attributes})
        if tag in {"failure", "error", "skipped"}:
            result.text = "IDT reported this status; detailed diagnostics remain in the restricted runtime directory."
        for child in node:
            if child.tag.rsplit("}", 1)[-1] in allowed:
                result.append(clean(child))
        return result

    if parsed.tag.rsplit("}", 1)[-1] not in {"testsuites", "testsuite"}:
        raise RuntimeError("IDT report has an unexpected root")
    ET.ElementTree(clean(parsed)).write(target, encoding="utf-8", xml_declaration=True)


def combined_summary(junit_result: dict, runner_exit_code: int) -> dict:
    result = dict(junit_result, runner_exit_code=runner_exit_code)
    result["problems"] = list(junit_result.get("problems", []))
    result["passed"] = bool(junit_result.get("passed")) and runner_exit_code == 0
    if runner_exit_code != 0:
        result["problems"].append("IDT execution or runtime cleanup did not succeed")
    return result


def install_idt(host_os: str, credentials) -> Path:
    """Use AWS's documented signed API; never print the temporary download URL."""
    import requests
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    suffix = "win" if host_os == "windows" else "linux"
    folder = INSTALL / (VERSION if suffix == "win" else VERSION + "-linux")
    root = folder / ("devicetester_freertos_" + suffix)
    binary = root / "bin" / ("devicetester_win_x86-64.exe" if suffix == "win" else "devicetester_linux_x86-64")
    if binary.is_file():
        return root
    url = "https://download.devicetester.iotdevicesecosystem.amazonaws.com/latestidt?HostOs=" + host_os + "&TestSuiteType=FR"
    request = AWSRequest(method="GET", url=url)
    SigV4Auth(credentials, "iot-device-tester", "us-west-2").add_auth(request)
    response = requests.get(url, headers=dict(request.headers), timeout=45)
    if response.status_code != 200:
        raise RuntimeError("AWS IDT download API returned HTTP " + str(response.status_code))
    result = response.json()
    bundle = result.get("LatestBk", {})
    if not result.get("Success") or bundle.get("Version") != VERSION or bundle.get("TestSuiteVersion") != "2.5.0":
        raise RuntimeError("AWS IDT bundle changed; verify suite compatibility before updating the pin")
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "bundle.zip"
    digest = hashlib.sha256()
    with requests.get(bundle["DownloadURL"], stream=True, timeout=90) as download:
        if download.status_code != 200:
            raise RuntimeError("AWS IDT archive download failed (HTTP " + str(download.status_code) + ")")
        with archive.open("wb") as target:
            for chunk in download.iter_content(1024 * 1024):
                if chunk:
                    target.write(chunk)
                    digest.update(chunk)
    with zipfile.ZipFile(archive) as source:
        for member in source.namelist():
            if folder.resolve() not in (folder / member).resolve().parents:
                raise RuntimeError("Unsafe member in IDT archive")
        source.extractall(folder)
    write_json(folder / "bundle-metadata.json", {"version": VERSION, "suite": SUITE, "sha256": digest.hexdigest()})
    return root


@contextmanager
def package_config(root: Path, config: dict):
    import msvcrt

    with (root / ".rx72n-idt.lock").open("a+b") as lock:
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        path = root / "configs/config.json"
        original = path.read_bytes()
        try:
            write_json(path, config)
            yield
        finally:
            path.write_bytes(original)
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def preflight(runtime: Path, region: str, credentials) -> tuple[Path, int]:
    root = install_idt("windows", credentials)
    device = [{"id": "rx72n-host-preflight", "sku": "RX72N-Envision-Kit-Ethernet", "features": [
        {"name": "Wifi", "value": "No"}, {"name": "Cellular", "value": "No"},
        {"name": "BLE", "value": "No"}, {"name": "PKCS11", "value": "ECC"},
        {"name": "KeyProvisioning", "value": "Import"},
        {"name": "OTA", "value": "Yes", "configs": [{"name": "OTADataPlaneProtocol", "value": "MQTT"}]}],
        "devices": [{"id": "metadata-only-no-hardware", "connectivity": {"protocol": "uart", "serialPort": "COM0"},
                     "secureElementConfig": {"preProvisioned": "No", "pkcs11JITPCodeVerifyRootCertSupport": "No"}}]}]
    write_json(runtime / "device.json", device)
    write_json(runtime / "userdata.json", {"sourcePath": str(SOURCE), "freeRTOSVersion": manifest_version(), "retainModifiedSourceDirectories": True})
    config = {"log": {"location": str(runtime / "logs")},
              "configFiles": {"root": str(runtime), "device": str(runtime / "device.json")},
              "testPath": str(root / "tests"), "reportPath": str(runtime / "results"),
              "certificatePath": str(runtime / "certificates"), "awsRegion": region,
              "auth": {"method": "environment"}}
    env = os.environ.copy()
    env.update(AWS_ACCESS_KEY_ID=credentials.access_key, AWS_SECRET_ACCESS_KEY=credentials.secret_key)
    if credentials.token:
        env["AWS_SESSION_TOKEN"] = credentials.token
    command = [str(root / "bin/devicetester_win_x86-64.exe"), "run-suite", "--suite-id", SUITE,
               "--pool-id", "rx72n-host-preflight", "--group-id", "FreeRTOSVersion", "--userdata", "userdata.json",
               "--update-idt", "n", "--upgrade-test-suite", "n", "--update-managed-policy", "n"]
    with package_config(root, config):
        completed = subprocess.run(command, cwd=root / "bin", env=env, capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=900)
    (runtime / "console.log").write_text(redact(completed.stdout + completed.stderr, credentials), encoding="utf-8")
    reports = list((runtime / "results").rglob("FRQ_Report.xml"))
    if len(reports) != 1:
        raise RuntimeError("Expected exactly one current IDT JUnit report")
    return reports[0], completed.returncode


def wsl_path(path: Path) -> str:
    return subprocess.check_output([str(WSL), "-d", "Ubuntu", "--exec", "wslpath", "-a", "-u", str(path.resolve())], encoding="utf-8").strip()


def transport(runtime: Path, region: str, credentials, provenance: dict) -> tuple[Path, int]:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    powershell = Path(os.getenv("RX72N_IDT_POWERSHELL", str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PowerShell/7/pwsh.exe")))
    if not powershell.is_file():
        raise RuntimeError("PowerShell 7 is required for the IDT build callback; configure RX72N_IDT_POWERSHELL if installed elsewhere")
    major = subprocess.check_output([str(powershell), "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"], encoding="utf-8").strip()
    if major != "7":
        raise RuntimeError("IDT build callbacks require the validated PowerShell 7 runtime")
    root = install_idt("linux", credentials)
    inputs = runtime / "inputs"
    inputs.mkdir()
    private_path = inputs / "transport-private.pem"
    public_path = inputs / "transport-public.hex"
    key = ec.generate_private_key(ec.SECP256R1())
    private_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_text(key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo).hex(), encoding="ascii")
    os.chmod(private_path, 0o600)
    provenance_file = runtime / "source-provenance.json"
    write_json(provenance_file, provenance)
    device = [{"id": "rx72n-ether-development", "sku": "RX72N-Envision-Kit-Ethernet", "features": [
        {"name": "Wifi", "value": "No"}, {"name": "Cellular", "value": "No"},
        {"name": "BLE", "value": "No"}, {"name": "PKCS11", "value": "ECC"},
        {"name": "KeyProvisioning", "value": "Import"},
        {"name": "OTA", "value": "Yes", "configs": [{"name": "OTADataPlaneProtocol", "value": "MQTT"}]}],
        "devices": [{"id": "rx72n-ether-rpi1", "secureElementConfig": {
            "preProvisioned": "No", "pkcs11JITPCodeVerifyRootCertSupport": "No", "publicKeyAsciiHexFilePath": wsl_path(public_path)}}]}]
    userdata = {"freeRTOSVersion": manifest_version(), "retainModifiedSourceDirectories": True,
                "freeRTOSTestParamConfigPath": "{{testData.sourcePath}}/Test/include/test_param_config.h",
                "freeRTOSTestExecutionConfigPath": "{{testData.sourcePath}}/Test/include/test_execution_config.h",
                "buildTool": {"name": "CC-RX/e2studio", "version": "3.07.00/2026-04.2", "command": []},
                "flashTool": {"name": "rfp-cli", "version": "1.15", "command": []},
                "testStartDelayms": 0, "echoServerConfiguration": {"keyGenerationMethod": "EC", "serverPort": 9000}}
    write_json(inputs / "device.json", device)
    write_json(inputs / "userdata.json", userdata)
    execution = runtime / "execution"
    root_linux = wsl_path(root)
    binaries = [root_linux + "/bin/devicetester_linux_x86-64", root_linux + "/tests/FRQ_2.5.0/frq_linux_x86-64",
                root_linux + "/tests/FRQ_2.5.0/suite/parseProductVersion_linux_x86-64"]
    subprocess.run([str(WSL), "-d", "Ubuntu", "--exec", "chmod", "+x", *binaries], check=True)
    env = os.environ.copy()
    inherited = {"AWS_ACCESS_KEY_ID": credentials.access_key, "AWS_SECRET_ACCESS_KEY": credentials.secret_key,
                 "AWS_REGION": region, "AWS_DEFAULT_REGION": region, "IDT_RUNTIME_DIR": wsl_path(execution),
                 "IDT_PRIVATE_KEY_FILE": wsl_path(private_path), "IDT_PROVENANCE_FILE": str(provenance_file),
                 "IDT_WINDOWS_PYTHON": wsl_path(Path(sys.executable)), "IDT_WINDOWS_PWSH": wsl_path(powershell)}
    if credentials.token:
        inherited["AWS_SESSION_TOKEN"] = credentials.token
    env.update(inherited)
    env["WSLENV"] = env.get("WSLENV", "") + ":" + ":".join(name + "/u" for name in inherited)
    command = [str(WSL), "-d", "Ubuntu", "--exec", "python3", wsl_path(Path(__file__).with_name("run_transport.py")),
               "--source-path", wsl_path(SOURCE), "--idt-root", root_linux, "--output", wsl_path(execution),
               "--userdata-template", wsl_path(inputs / "userdata.json"), "--device-template", wsl_path(inputs / "device.json"), "--region", region]
    with (runtime / "console.log").open("w", encoding="utf-8") as console:
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   encoding="utf-8", errors="replace")
        for line in process.stdout:
            line = redact(line, credentials)
            console.write(line)
            console.flush()
            # Keep the unrestricted raw log local, while CI shows phase progress.
            for phase in ("IDT_UART_READY", "Creating EC2 instance", "Starting echo server", "Building source code", "Flashing", "Cleaning up test resources", "IDT_UART_END_STATE"):
                if phase in line:
                    print("IDT phase: " + phase, flush=True)
                    break
        code = process.wait()
    reports = list((execution / "results").rglob("FRQ_Report.xml"))
    if len(reports) != 1:
        raise RuntimeError("Transport run did not produce exactly one JUnit report; inspect restricted runtime diagnostics")
    return reports[0], code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["preflight", "transport"], default="preflight")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1"))
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Run this entry point on the Windows CC-RX/AWS runner")
    args.output.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix="run-", dir=RUNTIME))
    restrict_runtime(runtime)
    import boto3
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    metadata = {"scope": args.scope, "source_sha": git("rev-parse", "HEAD"),
                "source_dirty": bool(git("status", "--porcelain")), "idt_version": VERSION,
                "suite": SUITE, "started_utc": datetime.now(timezone.utc).isoformat(),
                "qualification": "not-established", "runtime_directory": str(runtime),
                "submodule_pins": submodule_pins(), "board": "RX72N Envision Kit Ethernet",
                "tls_backend": "software"}
    write_json(args.output / "metadata.json", metadata)
    try:
        if args.scope == "transport":
            library_sha = test_library_sha()
            provenance = {"source_sha": metadata["source_sha"], "test_library_sha": library_sha, "source_tree_dirty": metadata["source_dirty"]}
            report, idt_code = transport(runtime, args.region, credentials, provenance)
        else:
            report, idt_code = preflight(runtime, args.region, credentials)
    except Exception as error:
        write_json(args.output / "summary.json", {"passed": False, "scope": args.scope, "problem": "IDT runtime/setup failure", "error_type": type(error).__name__})
        metadata.update(finished_utc=datetime.now(timezone.utc).isoformat(), runtime_failed=True)
        write_json(args.output / "metadata.json", metadata)
        raise
    exported = args.output / "FRQ_Report.xml"
    export_report(report, exported, credentials)
    checked = subprocess.run([sys.executable, str(Path(__file__).with_name("check_idt_report.py")),
                              str(exported), "--required-group", "FullTransportInterfaceTLS" if args.scope == "transport" else "FreeRTOSVersion"],
                             capture_output=True, encoding="utf-8", errors="replace")
    summary = combined_summary(json.loads(checked.stdout), idt_code)
    write_json(args.output / "summary.json", summary)
    metadata.update(runner_exit_code=idt_code, report_check_exit_code=checked.returncode,
                    finished_utc=datetime.now(timezone.utc).isoformat())
    if args.scope == "transport":
        detail = runtime / "execution/transport-result.json"
        if detail.is_file():
            metadata["idt_exit_code"] = json.loads(detail.read_text(encoding="utf-8")).get("idtExitCode")
    else:
        metadata["idt_exit_code"] = idt_code
    if args.scope == "transport" and idt_code == checked.returncode == 0:
        manifests = list((runtime / "execution").rglob("build_manifest.json"))
        if len(manifests) == 1:
            build = json.loads(manifests[0].read_text(encoding="utf-8-sig"))
            metadata["firmware_sha256"] = {name: value["sha256"] for name, value in build["outputs"].items()}
            metadata["execution_config_sha256"] = build["execution_config_sha256"]
            metadata["parameter_config_sha256"] = build["parameter_config_sha256"]
            rsu = manifests[0].with_name("rx72n_idt_transport.rsu")
            if rsu.is_file():
                metadata["firmware_sha256"]["rsu"] = hashlib.sha256(rsu.read_bytes()).hexdigest()
    write_json(args.output / "metadata.json", metadata)
    print(json.dumps(summary, sort_keys=True))
    return 0 if idt_code == 0 and checked.returncode == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Transport exceptions can embed temporary signed download URLs.
        detail = str(error) if isinstance(error, RuntimeError) else "See restricted runtime diagnostics."
        print("IDT run failed: " + type(error).__name__ + ": " + detail, file=sys.stderr)
        raise SystemExit(1)

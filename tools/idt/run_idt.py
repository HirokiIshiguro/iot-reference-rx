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
import time
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET

try:
    from .host_profile import load_host_profile
    from .idt_bundle import verify_install, verify_archive_digest
except ImportError:
    from host_profile import load_host_profile
    from idt_bundle import verify_install, verify_archive_digest

VERSION = "4.9.0"
SUITE = "FRQ_2.5.0"
SCOPE_GROUPS = {"preflight": "FreeRTOSVersion", "transport": "FullTransportInterfaceTLS",
                "mqtt": "FullCloudIoT", "ota-mqtt": "OTADataplaneMQTT", "pkcs11": "FullPKCS11_Core",
                "ota-pal": "OTACore"}
SOURCE = Path(__file__).resolve().parents[2]
INSTALL = Path(r"C:\ai\codex\tools\aws-idt")
RUNTIME = Path(r"C:\ai\codex\tmp\rx72n-idt")
WSL = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/wsl.exe"
HOST: dict = {}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def restrict_runtime(path: Path) -> None:
    system32 = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32"
    identity = subprocess.check_output([str(system32 / "whoami.exe"), "/user", "/fo", "csv", "/nh"], encoding="utf-8", errors="replace")
    sid = next(csv.reader(io.StringIO(identity)))[1]
    if not sid.startswith("S-1-"):
        raise RuntimeError("Cannot determine runtime directory owner SID")
    result = subprocess.run([str(system32 / "icacls.exe"), str(path), "/inheritance:r", "/grant:r",
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


def public_warnings(console: str) -> list[dict]:
    """Preserve Device Advisor warning codes, never arbitrary diagnostic text."""
    warnings = []
    for match in re.finditer(r"-- Finished: ([A-Za-z0-9_]+) with status PASS_WITH_WARNINGS and message (.*?) --", console):
        codes, ciphers = set(), set()
        try:
            messages = json.loads(match.group(2))
            for item in messages if isinstance(messages, list) else []:
                code = item.get("message")
                if code in {"FOUND_UNSUPPORTED_CIPHER_SUITE", "NO_RECOMMENDED_CIPHER_SUITE"}:
                    codes.add(code)
                    if code == "FOUND_UNSUPPORTED_CIPHER_SUITE":
                        ciphers.update(re.findall(r"\b0x[0-9a-fA-F]{1,4}\b", item.get("description", "")))
        except (ValueError, TypeError, AttributeError):
            pass
        warnings.append({"test_case": match.group(1), "codes": sorted(codes or {"UNCLASSIFIED_WARNING"}),
                         "cipher_ids": sorted(ciphers)})
    unmatched = console.count("with status PASS_WITH_WARNINGS") - len(warnings)
    if unmatched > 0 or ("PASS_WITH_WARNINGS" in console and not warnings):
        warnings.append({"test_case": "unparsed_native_warning", "codes": ["UNCLASSIFIED_WARNING"],
                         "cipher_ids": []})
    return warnings


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
        verify_install(root, host_os)
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
    verify_archive_digest(host_os, digest.hexdigest())
    with zipfile.ZipFile(archive) as source:
        for member in source.namelist():
            if folder.resolve() not in (folder / member).resolve().parents:
                raise RuntimeError("Unsafe member in IDT archive")
        source.extractall(folder)
    verify_install(root, host_os)
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
    return subprocess.check_output([str(WSL), "-d", HOST["wsl_distribution"], "--exec", "wslpath", "-a", "-u", str(path.resolve())], encoding="utf-8").strip()


def stop_hardware_runtime(process, runtime, env, credentials):
    """Let the owned Linux supervisor clean AWS and reset the board on interruption."""
    command = [str(WSL), "-d", HOST["wsl_distribution"], "--exec", HOST["wsl_python"],
               wsl_path(Path(__file__).with_name("stop_runtime.py")), "--source", wsl_path(SOURCE),
               "--runtime", wsl_path(runtime / "execution")]
    # Account for interruption during WSL/Python startup, before the supervisor
    # is visible. This is bounded startup recovery, not device-command polling.
    for attempt in range(3):
        if process.poll() is not None:
            break
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            raise RuntimeError("Could not signal the owned IDT supervisor")
        if json.loads(result.stdout)["signaled"]:
            break
        if attempt < 2:
            time.sleep(1)
    try:
        remaining, _ = process.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        # Killing wsl.exe alone would abandon the Linux SDK and bench helper.
        # Keep the ownership journal and fail rather than delete live signers.
        raise RuntimeError("Owned IDT cleanup did not finish; inspect the private runtime before reuse") from None
    if remaining:
        with (runtime / "console.log").open("a", encoding="utf-8") as stream:
            stream.write(redact(remaining, credentials))


def transport(runtime: Path, region: str, credentials, provenance: dict, scope: str = "transport",
              test_id: str | None = None, diagnostic_only: bool = False) -> tuple[Path, int]:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    powershell = Path(HOST["windows_powershell"])
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
        # OTA's native Import route creates an RSA key without exposing it to
        # the callback. Exercise its supplied-public-key route for development;
        # the firmware still imports a host-generated EC key. This must never
        # be described as an onboard key-generation qualification result.
        {"name": "KeyProvisioning", "value": "Onboard" if scope == "ota-mqtt" else "Import"},
        {"name": "OTA", "value": "Yes", "configs": [{"name": "OTADataPlaneProtocol", "value": "MQTT"}]}],
        "devices": [{"id": "rx72n-ether-rpi1", "secureElementConfig": {
            "preProvisioned": "No", "pkcs11JITPCodeVerifyRootCertSupport": "No", "publicKeyAsciiHexFilePath": wsl_path(public_path)}}]}]
    userdata = {"freeRTOSVersion": manifest_version(), "retainModifiedSourceDirectories": True,
                "freeRTOSTestParamConfigPath": "{{testData.sourcePath}}/Test/include/test_param_config.h",
                "freeRTOSTestExecutionConfigPath": "{{testData.sourcePath}}/Test/include/test_execution_config.h",
                "buildTool": {"name": "CC-RX/e2studio", "version": "3.07.00/2026-04.2", "command": []},
                "flashTool": {"name": "rfp-cli", "version": "1.15", "command": []},
                "testStartDelayms": 0, "echoServerConfiguration": {"keyGenerationMethod": "EC", "serverPort": 9000}}
    if scope == "pkcs11":
        userdata["pkcs11LabelConfiguration"] = {
            # FRQ inserts C expressions verbatim. Resolve through the same
            # project/default macros as the production PAL, including overrides.
            "pkcs11LabelDevicePrivateKeyForTLS": "pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS",
            "pkcs11LabelDevicePublicKeyForTLS": "pkcs11configLABEL_DEVICE_PUBLIC_KEY_FOR_TLS",
            "pkcs11LabelDeviceCertificateForTLS": "pkcs11configLABEL_DEVICE_CERTIFICATE_FOR_TLS",
        }
    ota_env = {}
    if scope == "ota-pal":
        # PAL uses its verified local fixture. It does not create signing jobs.
        userdata["otaConfiguration"] = {
            "otaPALCertificatePath": "ecdsa-sha256-signer.crt.pem", "deviceFirmwarePath": "NA",
            "codeSigningConfiguration": {"signerSigningAlgorithm": "ECDSA", "signerHashingAlgorithm": "SHA256"},
        }
    if scope == "ota-mqtt":
        try:
            from .ota_support import make_ota_config, ota_environment
        except ImportError:
            from ota_support import make_ota_config, ota_environment
        userdata["otaConfiguration"] = make_ota_config(inputs, SOURCE, wsl_path,
                                                       python_executable=HOST["wsl_python"])
        ota_env = ota_environment(inputs, wsl_path)
    write_json(inputs / "device.json", device)
    write_json(inputs / "userdata.json", userdata)
    execution = runtime / "execution"
    # e2 studio recreates its workspace; keep it below a restricted parent so
    # any generated index/cache inherits the same boundary as injected sources.
    workspace_parent = Path(HOST["workspace_root"]) / ("idt-private-" + runtime.name)
    workspace_parent.mkdir(parents=True, exist_ok=False)
    restrict_runtime(workspace_parent)
    root_linux = wsl_path(root)
    binaries = [root_linux + "/bin/devicetester_linux_x86-64", root_linux + "/tests/FRQ_2.5.0/frq_linux_x86-64",
                root_linux + "/tests/FRQ_2.5.0/suite/parseProductVersion_linux_x86-64"]
    subprocess.run([str(WSL), "-d", HOST["wsl_distribution"], "--exec", "chmod", "+x", *binaries], check=True)
    env = os.environ.copy()
    inherited = {"AWS_ACCESS_KEY_ID": credentials.access_key, "AWS_SECRET_ACCESS_KEY": credentials.secret_key,
                 "AWS_REGION": region, "AWS_DEFAULT_REGION": region, "IDT_RUNTIME_DIR": wsl_path(execution),
                 "IDT_PRIVATE_KEY_FILE": wsl_path(private_path), "IDT_PROVENANCE_FILE": str(provenance_file),
                 "IDT_WINDOWS_PYTHON": wsl_path(Path(sys.executable)), "IDT_WINDOWS_PWSH": wsl_path(powershell),
                 "IDT_SCOPE": scope, "IDT_E2STUDIO_CLI": HOST["e2studio_cli"],
                 "IDT_WORKSPACE_ROOT": str(workspace_parent),
                 "IDT_LINUX_PYTHON": HOST["wsl_python"],
                 "IDT_WINDOWS_SSH": wsl_path(Path(HOST["windows_ssh"])),
                 "IDT_WINDOWS_SCP": wsl_path(Path(HOST["windows_scp"]))}
    inherited.update(ota_env)
    if diagnostic_only:
        inherited["IDT_DIAGNOSTIC_ONLY"] = "1"
    if credentials.token:
        inherited["AWS_SESSION_TOKEN"] = credentials.token
    env.update(inherited)
    existing = [item for item in env.get("WSLENV", "").split(":")
                if item and item.split("/", 1)[0] not in inherited]
    env["WSLENV"] = ":".join(existing + [name + "/u" for name in inherited])
    command = [str(WSL), "-d", HOST["wsl_distribution"], "--exec", HOST["wsl_python"], wsl_path(Path(__file__).with_name("run_transport.py")),
               "--source-path", wsl_path(SOURCE), "--idt-root", root_linux, "--output", wsl_path(execution),
               "--userdata-template", wsl_path(inputs / "userdata.json"), "--device-template", wsl_path(inputs / "device.json"), "--region", region,
               "--group", SCOPE_GROUPS[scope]]
    if test_id:
        command += ["--test-id", test_id]
    signer_session = None
    cleanup_failed = False
    process = None
    try:
        if scope == "ota-mqtt":
            import boto3
            try:
                from .ota_aws_signers import prepare_aws_signers, cleanup_aws_signers
            except ImportError:
                from ota_aws_signers import prepare_aws_signers, cleanup_aws_signers
            signer_session = boto3.Session(aws_access_key_id=credentials.access_key,
                                           aws_secret_access_key=credentials.secret_key,
                                           aws_session_token=credentials.token, region_name=region)
            userdata["otaConfiguration"] = prepare_aws_signers(inputs, region, runtime.name,
                                                               userdata["otaConfiguration"], signer_session)
            write_json(inputs / "userdata.json", userdata)
            print("IDT phase: temporary AWS signing certificates prepared", flush=True)
        with (runtime / "console.log").open("w", encoding="utf-8") as console:
            process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       encoding="utf-8", errors="replace")
            for line in process.stdout:
                line = redact(line, credentials)
                console.write(line)
                console.flush()
                # Keep the unrestricted raw log local, while CI shows phase progress.
                for phase in ("IDT_UART_READY", "Copying source code", "Provisioning cloud resources",
                              "Creating EC2 instance", "Starting echo server", "Building source code",
                              "Building device image", "Flashing", "Cleaning up test resources", "IDT_UART_END_STATE"):
                    if phase in line:
                        print("IDT phase: " + phase, flush=True)
                        break
            code = process.wait()
    except BaseException:
        if process is not None and process.poll() is None:
            stop_hardware_runtime(process, runtime, env, credentials)
        raise
    finally:
        if signer_session is not None:
            try:
                if process is not None and process.poll() is None:
                    raise RuntimeError("IDT must finish its native cleanup before signer deletion")
                journal = cleanup_aws_signers(inputs, signer_session)
                status = {"state": journal["state"], "certificates": len(journal["certificates"]),
                          "certificates_deleted": sum(bool(item.get("deleted")) for item in journal["certificates"])}
            except Exception as error:
                cleanup_failed = True
                status = {"state": "cleanup_failed", "error_type": type(error).__name__}
            write_json(runtime / "ota-signers-cleanup.json", status)
            print("IDT phase: temporary signer cleanup " + status["state"], flush=True)
    if cleanup_failed:
        code = 1
    reports = list((execution / "results").rglob("FRQ_Report.xml"))
    if len(reports) != 1:
        raise RuntimeError("IDT run did not produce exactly one JUnit report; inspect restricted runtime diagnostics")
    return reports[0], code


def main() -> int:
    global HOST, INSTALL, RUNTIME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=list(SCOPE_GROUPS), default="preflight")
    parser.add_argument("--test-id", choices=["OTAE2EGreaterVersion"],
                        default=os.getenv("RX72N_IDT_TEST_ID") or None,
                        help="Optional single-case OTA bring-up; not a complete group result")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-only", action="store_true", help="OTA credential diagnosis; stops before compiler/flash")
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1"))
    args = parser.parse_args()
    if args.test_id not in {None, "OTAE2EGreaterVersion"}:
        parser.error("Unsupported RX72N_IDT_TEST_ID")
    if args.test_id and args.scope != "ota-mqtt":
        parser.error("The selected test ID requires --scope ota-mqtt")
    if args.diagnostic_only and args.scope != "ota-mqtt":
        parser.error("Diagnostic-only is restricted to OTA credential bring-up")
    if os.name != "nt":
        parser.error("Run this entry point on the Windows CC-RX/AWS runner")
    HOST = load_host_profile()
    INSTALL, RUNTIME = Path(HOST["install_root"]), Path(HOST["runtime_root"])
    args.output.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix="run-", dir=RUNTIME))
    restrict_runtime(runtime)
    import boto3
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    metadata = {"scope": args.scope, "test_id": args.test_id,
                "diagnostic_only": args.diagnostic_only,
                "complete_group_requested": args.test_id is None,
                "source_sha": git("rev-parse", "HEAD"),
                "source_dirty": bool(git("status", "--porcelain")), "idt_version": VERSION,
                "suite": SUITE, "started_utc": datetime.now(timezone.utc).isoformat(),
                "qualification": "not-established", "runtime_directory": str(runtime),
                "submodule_pins": submodule_pins(), "board": "RX72N Envision Kit Ethernet",
                "tls_backend": "software"}
    if args.scope == "ota-mqtt":
        metadata["device_provisioning"] = "development host-generated EC key via native supplied-public-key route; no onboard key-generation qualification"
    write_json(args.output / "metadata.json", metadata)
    try:
        if args.scope != "preflight":
            library_sha = test_library_sha()
            provenance = {"source_sha": metadata["source_sha"], "test_library_sha": library_sha, "source_tree_dirty": metadata["source_dirty"]}
            report, idt_code = transport(runtime, args.region, credentials, provenance, args.scope, args.test_id, args.diagnostic_only)
        else:
            report, idt_code = preflight(runtime, args.region, credentials)
    except (Exception, KeyboardInterrupt) as error:
        write_json(args.output / "summary.json", {"passed": False, "scope": args.scope, "problem": "IDT runtime/setup failure", "error_type": type(error).__name__})
        metadata.update(finished_utc=datetime.now(timezone.utc).isoformat(), runtime_failed=True)
        write_json(args.output / "metadata.json", metadata)
        if isinstance(error, KeyboardInterrupt):
            raise SystemExit(130) from None
        raise
    exported = args.output / "FRQ_Report.xml"
    export_report(report, exported, credentials)
    checked = subprocess.run([sys.executable, str(Path(__file__).with_name("check_idt_report.py")),
                              str(exported), "--required-group", SCOPE_GROUPS[args.scope]],
                             capture_output=True, encoding="utf-8", errors="replace")
    try:
        junit_summary = json.loads(checked.stdout)
    except (ValueError, TypeError):
        junit_summary = {"passed": False, "problems": ["IDT report checker did not return a valid result"]}
    summary = combined_summary(junit_summary, idt_code)
    if checked.returncode != 0:
        summary["passed"] = False
    summary.update(scope=args.scope, test_id=args.test_id, complete_group_requested=args.test_id is None,
                   interrupted=idt_code == 130)
    if idt_code == 130:
        summary["problems"].append("IDT was interrupted; unfinished cases can appear as failures in the native report")
    if args.test_id:
        summary["result_scope"] = "selected_test_cases_only"
    console_file = runtime / "console.log"
    warnings = public_warnings(console_file.read_text(encoding="utf-8")) if console_file.is_file() else []
    summary["warnings"] = warnings
    metadata["warnings"] = warnings
    # A partially written/corrupt build manifest must not leave an apparent
    # passing summary when the host exits during evidence collection.
    incomplete = dict(summary, passed=False,
                      problems=list(summary["problems"]) + ["IDT evidence collection did not finish"])
    write_json(args.output / "summary.json", incomplete)
    metadata.update(runner_exit_code=idt_code, report_check_exit_code=checked.returncode,
                    finished_utc=datetime.now(timezone.utc).isoformat())
    if args.scope != "preflight":
        detail = runtime / "execution/transport-result.json"
        if detail.is_file():
            metadata["idt_exit_code"] = json.loads(detail.read_text(encoding="utf-8")).get("idtExitCode")
        signer_cleanup = runtime / "ota-signers-cleanup.json"
        if signer_cleanup.is_file():
            metadata["ota_signer_cleanup"] = json.loads(signer_cleanup.read_text(encoding="utf-8"))
    else:
        metadata["idt_exit_code"] = idt_code
    if args.scope != "preflight":
        manifests = list((runtime / "execution").rglob("build_manifest.json"))
        ledger = runtime / "execution/ota-build-ledger.jsonl"
        if ledger.is_file():
            metadata["ota_builds"] = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        metadata["builds"] = []
        for manifest in manifests:
            build = json.loads(manifest.read_text(encoding="utf-8-sig"))
            metadata["builds"].append({
                "suite": build.get("suite"),
                "source_sha": build.get("source_sha"),
                "firmware_sha256": {name: value["sha256"] for name, value in build["outputs"].items()},
                "execution_config_sha256": build["execution_config_sha256"],
                "parameter_config_sha256": build["parameter_config_sha256"],
            })
        if len(manifests) == 1:
            build = json.loads(manifests[0].read_text(encoding="utf-8-sig"))
            metadata["firmware_sha256"] = {name: value["sha256"] for name, value in build["outputs"].items()}
            metadata["execution_config_sha256"] = build["execution_config_sha256"]
            metadata["parameter_config_sha256"] = build["parameter_config_sha256"]
            rsu = manifests[0].with_name("rx72n_idt_transport.rsu")
            if rsu.is_file():
                metadata["firmware_sha256"]["rsu"] = hashlib.sha256(rsu.read_bytes()).hexdigest()
    write_json(args.output / "metadata.json", metadata)
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] and idt_code == 0 and checked.returncode == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Transport exceptions can embed temporary signed download URLs.
        detail = str(error) if isinstance(error, RuntimeError) else "See restricted runtime diagnostics."
        print("IDT run failed: " + type(error).__name__ + ": " + detail, file=sys.stderr)
        raise SystemExit(1)

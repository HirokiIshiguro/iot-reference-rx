#!/usr/bin/env python3
"""Run explicit target-selected RX IDT checks; a partial group never qualifies a release."""
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
import shutil
import zipfile
import xml.etree.ElementTree as ET

try:
    from .host_profile import load_host_profile
    from .idt_bundle import verify_install, verify_archive_digest
    from .test_selection import parse_test_ids
    from .ota_witness import analyze_ota_witness, version_tuple
    from .cleanup_budget import NATIVE_CLEANUP_SECONDS, owned_runtime_cleanup_seconds
    from .ota_support import source_stack_metadata
except ImportError:
    from host_profile import load_host_profile
    from idt_bundle import verify_install, verify_archive_digest
    from test_selection import parse_test_ids
    from ota_witness import analyze_ota_witness, version_tuple
    from cleanup_budget import NATIVE_CLEANUP_SECONDS, owned_runtime_cleanup_seconds
    from ota_support import source_stack_metadata

try:
    from ..idt_source_manifest import capture_dependency_provenance
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from idt_source_manifest import capture_dependency_provenance

VERSION = "4.9.0"
SUITE = "FRQ_2.5.0"
SCOPE_GROUPS = {"preflight": "FreeRTOSVersion", "transport": "FullTransportInterfaceTLS",
                "mqtt": "FullCloudIoT", "ota-mqtt": "OTADataplaneMQTT", "pkcs11": "FullPKCS11_Core",
                "ota-pal": "OTACore"}
try:
    from .targets import (get_target, target_ids, target_fingerprint, device_template,
                          hardware_end_state_status)
    from .prepare_target_network import network_values, INPUTS as NETWORK_INPUTS
except ImportError:
    from targets import (get_target, target_ids, target_fingerprint, device_template,
                         hardware_end_state_status)
    from prepare_target_network import network_values, INPUTS as NETWORK_INPUTS

SOURCE = Path(__file__).resolve().parents[2]
INSTALL = Path(r"C:\ai\codex\tools\aws-idt")
RUNTIME = Path(r"C:\ai\codex\tmp\rx72n-idt")
WSL = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/wsl.exe"
HOST: dict = {}
RX671_BOOTSTRAP_INPUTS = {
    "IDT_RX671_PROVISIONER_MOT_FILE": "rx671_provisioner.mot",
    "IDT_RX671_PROVISIONER_MANIFEST_FILE": "rx671_provisioner_manifest.json",
    "IDT_RX671_SIGNER_CERT_FILE": "rx671_signer.crt.pem",
    "IDT_RX671_SIGNER_PUBLIC_KEY_FILE": "rx671_signer.pub.pem",
}


def rx671_bootstrap_environment(inputs: Path, source_sha: str, environ=None) -> dict[str, str]:
    """Validate public bootstrap inputs before native/AWS setup, then copy them."""
    try:
        from .rx671_provision import validate_public_signer_material, validate_prepared_signer
    except ImportError:
        from rx671_provision import validate_public_signer_material, validate_prepared_signer
    environment = os.environ if environ is None else environ
    original = {}
    for variable in RX671_BOOTSTRAP_INPUTS:
        value = environment.get(variable)
        if not value:
            raise RuntimeError("RX671 native IDT requires reviewed public bootstrap input: " + variable)
        raw = Path(value)
        if not raw.is_file() or any(path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())
                                    for path in (raw, *raw.parents)):
            raise RuntimeError("RX671 public bootstrap input must be a regular unlinked file: " + variable)
        original[variable] = raw.resolve(strict=True)
    # Reject private PEM objects before any input can be copied into a runtime.
    public_material = validate_public_signer_material(original["IDT_RX671_SIGNER_CERT_FILE"],
                                                      original["IDT_RX671_SIGNER_PUBLIC_KEY_FILE"])
    # Every initial build is packaged with the reviewed development key. Bind
    # the public bootstrap signer before provisioning any native cloud resource.
    from cryptography.hazmat.primitives import serialization
    public_path = (SOURCE / get_target("rx671-wifi")["signing_key"]).with_suffix(".publickey")
    reviewed_public = serialization.load_pem_public_key(public_path.read_bytes())
    reviewed_spki = reviewed_public.public_bytes(serialization.Encoding.DER,
                                                serialization.PublicFormat.SubjectPublicKeyInfo)
    if public_material["public_signer_spki_sha256"] != hashlib.sha256(reviewed_spki).hexdigest():
        raise RuntimeError("RX671 public bootstrap signer differs from the initial development package signer")
    destination = inputs / "rx671-bootstrap"
    destination.mkdir(exist_ok=False)
    copied = {}
    try:
        for variable, name in RX671_BOOTSTRAP_INPUTS.items():
            path = destination / name
            copied[variable] = str(path)
            shutil.copyfile(original[variable], path)
        validate_prepared_signer(SOURCE, inputs.parent, get_target("rx671-wifi"), source_sha,
                                 environ=copied)
    except BaseException:
        for value in copied.values():
            Path(value).unlink(missing_ok=True)
        destination.rmdir()
        raise
    return copied


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
    return subprocess.check_output(["git", "--no-optional-locks", "-c", "safe.directory=" + str(SOURCE), "-C", str(SOURCE), *args], encoding="utf-8").strip()


def manifest_version() -> str:
    match = re.search(r'^version:\s*["\']?([^"\'\s]+)', (SOURCE / "manifest.yml").read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise RuntimeError("Cannot read FreeRTOS version from the source manifest")
    return match.group(1)


def plan_stack_metadata(target: dict) -> dict:
    """An offline plan can describe missing inputs without asserting a stack."""
    try:
        return source_stack_metadata(SOURCE, target)
    except (OSError, RuntimeError, ValueError) as error:
        return {"status": "unavailable", "native_result": "not-run", "qualification": "not-established",
                "problem": "Initialize and verify selected production dependencies before stack assessment",
                "error_type": type(error).__name__}


def test_library_sha() -> str:
    library = SOURCE / "Test/FreeRTOS-Libraries-Integration-Tests"
    command = ["git", "--no-optional-locks", "-c", "safe.directory=" + str(library), "-C", str(library)]
    root = subprocess.check_output(command + ["rev-parse", "--show-toplevel"], encoding="utf-8").strip()
    if Path(root).resolve() != library.resolve():
        raise RuntimeError("Initialize the pinned FreeRTOS integration-test submodule before running IDT")
    return subprocess.check_output(command + ["rev-parse", "HEAD"], encoding="utf-8").strip()


def submodule_pins() -> list[dict]:
    lines = git("submodule", "status", "--recursive").splitlines()
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


def preflight(runtime: Path, region: str, credentials, target=None) -> tuple[Path, int]:
    root = install_idt("windows", credentials)
    target = get_target() if target is None else target
    device = device_template(target, "preflight")
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
               "--pool-id", device[0]["id"], "--group-id", "FreeRTOSVersion", "--userdata", "userdata.json",
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
        remaining, _ = process.communicate(timeout=owned_runtime_cleanup_seconds(NATIVE_CLEANUP_SECONDS))
    except subprocess.TimeoutExpired:
        # Killing wsl.exe alone would abandon the Linux SDK and bench helper.
        # Keep the ownership journal and fail rather than delete live signers.
        raise RuntimeError("Owned IDT cleanup did not finish; inspect the private runtime before reuse") from None
    if remaining:
        with (runtime / "console.log").open("a", encoding="utf-8") as stream:
            stream.write(redact(remaining, credentials))


def transport(runtime: Path, region: str, credentials, provenance: dict, scope: str = "transport",
              test_id: str | None = None, diagnostic_only: bool = False, target=None) -> tuple[Path, int]:
    target = get_target() if target is None else target
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    powershell = Path(HOST["windows_powershell"])
    if not powershell.is_file():
        raise RuntimeError("PowerShell 7 is required for the IDT build callback; configure RX72N_IDT_POWERSHELL if installed elsewhere")
    major = subprocess.check_output([str(powershell), "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"], encoding="utf-8").strip()
    if major != "7":
        raise RuntimeError("IDT build callbacks require the validated PowerShell 7 runtime")
    target = get_target() if target is None else target
    inputs = runtime / "inputs"
    inputs.mkdir()
    bootstrap_environment = rx671_bootstrap_environment(inputs, provenance["source_sha"]) if target["id"] == "rx671-wifi" else {}
    root = install_idt("linux", credentials)
    private_path = inputs / "transport-private.pem"
    public_path = inputs / "transport-public.hex"
    key = ec.generate_private_key(ec.SECP256R1())
    private_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_text(key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo).hex(), encoding="ascii")
    os.chmod(private_path, 0o600)
    provenance_file = runtime / "source-provenance.json"
    write_json(provenance_file, provenance)
    device = device_template(target, scope, wsl_path(public_path))
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
                                                       python_executable=HOST["wsl_python"], target=target,
                                                       bootstrap_environment=bootstrap_environment,
                                                       source_sha=provenance["source_sha"])
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
                 "IDT_SCOPE": scope, "IDT_TARGET": target["id"], "IDT_SOURCE_SHA": provenance["source_sha"],
                 "IDT_E2STUDIO_CLI": HOST["e2studio_cli"],
                 "IDT_WORKSPACE_ROOT": str(workspace_parent),
                 "IDT_LINUX_PYTHON": HOST["wsl_python"],
                 "IDT_WINDOWS_SSH": wsl_path(Path(HOST["windows_ssh"])),
                 "IDT_WINDOWS_SCP": wsl_path(Path(HOST["windows_scp"]))}
    if scope in {"transport", "mqtt", "ota-mqtt"}:
        inherited.update({variable: os.environ[variable] for variable in NETWORK_INPUTS.get(target["id"], {}).values()
                          if variable in os.environ})
    inherited.update(ota_env)
    inherited.update({variable: wsl_path(Path(path)) for variable, path in bootstrap_environment.items()})
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
               "--group", SCOPE_GROUPS[scope], "--target", target["id"],
               "--cleanup-timeout-seconds", str(NATIVE_CLEANUP_SECONDS)]
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
    parser.add_argument("--target", choices=target_ids(), default=os.getenv("IDT_TARGET", "rx72n-ethernet"))
    parser.add_argument("--plan-only", action="store_true", help="Write a nonsecret execution plan without AWS, build, UART or flash")
    parser.add_argument("--scope", choices=list(SCOPE_GROUPS), default="preflight")
    parser.add_argument("--test-id",
                        default=os.getenv("IDT_TEST_ID") or os.getenv("RX72N_IDT_TEST_ID") or None,
                        help="Optional comma-separated OTA test IDs; not a complete group result")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-only", action="store_true", help="OTA credential diagnosis; stops before compiler/flash")
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1"))
    args = parser.parse_args()
    try:
        selected_test_ids = parse_test_ids(args.test_id)
    except ValueError as error:
        parser.error(str(error))
    args.test_id = ",".join(selected_test_ids) if selected_test_ids else None
    if args.test_id and args.scope != "ota-mqtt":
        parser.error("The selected test ID requires --scope ota-mqtt")
    if args.diagnostic_only and args.scope != "ota-mqtt":
        parser.error("Diagnostic-only is restricted to OTA credential bring-up")
    target = get_target(args.target)
    if args.plan_only:
        args.output.mkdir(parents=True, exist_ok=True)
        plan = {"status": "not_run", "target_id": target["id"], "target_sha256": target_fingerprint(target),
                "board": target["board"], "scope": args.scope, "native_group": SCOPE_GROUPS[args.scope],
                "selected_test_ids": list(selected_test_ids), "qualification": "not-established",
                "host_os": "Windows x86_64 + WSL x86_64", "bench": {key: target[key] for key in
                    ("hostname", "ssh_alias", "uart", "baud", "e2lite", "bench_lock", "rfp_lock")},
                "application_project": target["application_project"], "bootloader_project": target["bootloader_project"],
                "idt_version": VERSION, "suite": SUITE, "freeRTOSVersion": manifest_version(),
                "production_stack": plan_stack_metadata(target),
                "hardware_end_state": hardware_end_state_status(target),
                "requirements": ["Selected target source and dependency pins must be verified",
                    "IDT 4.9.0 does not establish 202604.00-LTS version qualification",
                    "Native reports, including failure/skip, must be preserved"],
                "hardware_execution": "not_requested_by_plan"}
        if args.scope != "preflight":
            plan["requirements"] += ["Exclusive board use, reset-command/UART-quiet end state, and normal firmware restoration must be agreed",
                "Native cloud resource usage requires a separate approved cost/scope budget"]
        if target["id"] == "rx65n-bg96":
            plan["requirements"].append("BG96 normal CI and IDT must use the shared device transaction flock")
        if target["id"] == "rx671-wifi" and args.scope != "preflight":
            plan["requirements"].append("Same-source reviewed linear signer-only provisioner MOT/manifest and matching P-256 public signer certificate/key are required before native launch")
            plan["required_public_bootstrap_inputs"] = list(RX671_BOOTSTRAP_INPUTS)
            if args.scope == "ota-mqtt":
                plan["requirements"].append("Native OTA signer material, stored boot public signer and initial package signature must match; local checks do not establish runtime trust")
        write_json(args.output / "plan.json", plan)
        print(json.dumps(plan, sort_keys=True))
        return 0
    if os.name != "nt":
        parser.error("Run this entry point on the Windows CC-RX/AWS runner")
    if args.scope in {"transport", "mqtt", "ota-mqtt"}:
        network_values(target)
    HOST = load_host_profile()
    INSTALL, RUNTIME = Path(HOST["install_root"]), Path(HOST["runtime_root"])
    args.output.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix="run-", dir=RUNTIME))
    restrict_runtime(runtime)
    import boto3
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    metadata = {"scope": args.scope, "test_id": args.test_id,
                "selected_test_ids": list(selected_test_ids),
                "diagnostic_only": args.diagnostic_only,
                "complete_group_requested": args.test_id is None,
                "source_sha": git("rev-parse", "HEAD"),
                "source_dirty": bool(git("status", "--porcelain")), "idt_version": VERSION,
                "suite": SUITE, "started_utc": datetime.now(timezone.utc).isoformat(),
                "qualification": "not-established", "runtime_directory": str(runtime),
                "submodule_pins": submodule_pins(), "board": target["board"],
                "target_id": target["id"], "target_sha256": target_fingerprint(target),
                "tls_backend": "software"}
    metadata["production_stack"] = source_stack_metadata(SOURCE, target)
    if args.scope == "ota-mqtt":
        metadata["device_provisioning"] = "development host-generated EC key via native supplied-public-key route; no onboard key-generation qualification"
    write_json(args.output / "metadata.json", metadata)
    try:
        if args.scope != "preflight":
            library_sha = test_library_sha()
            provenance = {"source_sha": metadata["source_sha"], "test_library_sha": library_sha, "source_tree_dirty": metadata["source_dirty"],
                          "target_id": target["id"], "target_sha256": target_fingerprint(target)}
            provenance.update(capture_dependency_provenance(SOURCE, target["id"]))
            metadata["dependency_source_copy"] = {
                "schema_version": provenance["dependency_manifest_schema_version"],
                "target_id": provenance["dependency_target_id"],
                "file_count": len(provenance["dependency_files_sha256"]),
                "submodule_shas": provenance["submodule_shas"],
                "manifest_sha256": hashlib.sha256(json.dumps(provenance["dependency_files_sha256"], sort_keys=True,
                                                             separators=(",", ":")).encode()).hexdigest(),
            }
            report, idt_code = transport(runtime, args.region, credentials, provenance, args.scope, args.test_id, args.diagnostic_only, target)
        else:
            report, idt_code = preflight(runtime, args.region, credentials, target)
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
    summary["native_junit_passed"] = bool(junit_summary.get("passed")) and checked.returncode == 0
    if checked.returncode != 0:
        summary["passed"] = False
    summary.update(target_id=target["id"], target_sha256=target_fingerprint(target), scope=args.scope, test_id=args.test_id, complete_group_requested=args.test_id is None,
                   selected_test_ids=list(selected_test_ids),
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
        capture_path = runtime / "execution/uart-capture.json"
        capture = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.is_file() else {}
        metadata["uart_capture"] = {key: capture.get(key) for key in
                                    ("complete", "error", "raw_bytes", "raw_sha256",
                                     "invalid_marker_count", "truncated_marker")}
        if capture.get("complete") is not True:
            summary["passed"] = False
            summary["problems"].append("Private UART capture is missing or incomplete")
        manifests = list((runtime / "execution").rglob("build_manifest.json"))
        ledger = runtime / "execution/ota-build-ledger.jsonl"
        if ledger.is_file():
            metadata["ota_builds"] = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.scope == "ota-mqtt":
            builds = metadata.get("ota_builds", [])
            initial_id = candidate_id = None
            # The pinned native GT setup builds one candidate and one initial
            # image (confirmed by run #11255); ambiguous ledgers fail closed.
            if args.test_id == "OTAE2EGreaterVersion" and len(builds) == 2:
                ordered = sorted(builds, key=lambda item: version_tuple(item["ota_version"]))
                initial_id, candidate_id = (item["image_id"] for item in ordered)
            witness = analyze_ota_witness(capture.get("events", []), builds,
                                          target_id=target["id"], target_sha256=target_fingerprint(target),
                                          selected_test_id=args.test_id,
                                          capture_complete=capture.get("complete") is True,
                                          initial_image_id=initial_id, candidate_image_id=candidate_id)
            if any(item.get("source_sha") != metadata["source_sha"] or
                   item.get("source_tree_dirty") != metadata["source_dirty"] for item in builds):
                witness.update(verified=False, verdict="not_verified")
                witness["reasons"].append("Build provenance does not match this run")
                summary["passed"] = False
                summary["problems"].append("Build provenance does not match this run")
            if capture.get("invalid_marker_count") or capture.get("truncated_marker"):
                witness.update(verified=False, verdict="not_verified")
                witness["reasons"].append("Unparseable or truncated boot markers were captured")
            metadata["ota_witness"] = witness
            summary["ota_boot_verified"] = witness["verified"]
            if witness["required"] and not witness["verified"]:
                summary["passed"] = False
                summary["problems"].extend(witness["reasons"] or ["OTA boot witness is not verified"])
        metadata["builds"] = []
        for manifest in manifests:
            build = json.loads(manifest.read_text(encoding="utf-8-sig"))
            if build.get("target_id") != target["id"] or build.get("target_sha256") != target_fingerprint(target):
                summary["passed"] = False
                summary["problems"].append("Firmware target provenance differs from this run")
            metadata["builds"].append({
                "target_id": build.get("target_id"),
                "target_sha256": build.get("target_sha256"),
                "suite": build.get("suite"),
                "source_sha": build.get("source_sha"),
                "source_tree_dirty": build.get("source_tree_dirty"),
                "production_stack": build.get("production_stack"),
                "mode": build.get("mode"),
                "dependency_target_id": build.get("dependency_target_id"),
                "submodule_shas": build.get("submodule_shas"),
                "firmware_sha256": {name: value["sha256"] for name, value in build["outputs"].items()},
                "execution_config_sha256": build["execution_config_sha256"],
                "parameter_config_sha256": build["parameter_config_sha256"],
            })
        if len(manifests) == 1:
            build = json.loads(manifests[0].read_text(encoding="utf-8-sig"))
            metadata["firmware_sha256"] = {name: value["sha256"] for name, value in build["outputs"].items()}
            metadata["execution_config_sha256"] = build["execution_config_sha256"]
            metadata["parameter_config_sha256"] = build["parameter_config_sha256"]
            rsu = manifests[0].with_name(target["artifact_basename"] + ".rsu")
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

"""Validate and install public boot trust inside the caller's locked transaction.

This module has no hardware command-line entry point. Bench/UART/RFP ownership,
command supervision and final reset/quiet observations belong to the caller.
Offline signature checks never establish runtime trust.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import sys
import time
from types import SimpleNamespace

try:
    from .targets import get_target, target_fingerprint
    from . import public_signer_material as material
except ImportError:
    from targets import get_target, target_fingerprint
    import public_signer_material as material

PROFILE = "rx-dual-public-signer-provisioner-v1"
PUBLIC_SIGNER_INPUTS = frozenset((
    "public_signer_provision.py", "public_signer_material.py",
    "provision_rx671_ota.py", "rx671_ota_host.py", "build_rx671_fwup_v2_rsu.py",
    "public_signer_provisioner.mot", "public_signer_provisioner_manifest.json",
    "signer.crt.pem", "signer.pub.pem", "public_signer_bootloader_config.h",
    "public_signer_target.h",
))
ENVIRONMENT_INPUTS = {
    "public_signer_provisioner.mot": "IDT_PUBLIC_SIGNER_PROVISIONER_MOT_FILE",
    "public_signer_provisioner_manifest.json": "IDT_PUBLIC_SIGNER_PROVISIONER_MANIFEST_FILE",
    "signer.crt.pem": "IDT_PUBLIC_SIGNER_CERT_FILE",
    "signer.pub.pem": "IDT_PUBLIC_SIGNER_PUBLIC_KEY_FILE",
}
CHIP_HEADERS = {"rx72n-ethernet": "rx72n.h", "rx65n-bg96": "rx65n.h", "rx671-wifi": "rx671.h"}
LAYOUTS = {"rx72n-ethernet": (0xFFE00000, 0x200000),
           "rx65n-bg96": (0xFFF00000, 0x100000), "rx671-wifi": (0xFFF00000, 0x100000)}
OPTIONS = ((0xFE7F5D00, 0xFE7F5D7F), (0xFE7F7D70, 0xFE7F7D9F))


def _tools_module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name:
            raise
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        return importlib.import_module(name)


def _ordinary(path):
    path = Path(path)
    if any(item.is_symlink() for item in (path, *path.parents)) or not path.is_file():
        raise RuntimeError("Missing or symbolic link public signer input: " + path.name)
    return path


def _bytes(path):
    return _ordinary(path).read_bytes()


def _hash(path):
    return hashlib.sha256(_bytes(path)).hexdigest()


def _identity(target, source_sha):
    if (not isinstance(target, dict) or target.get("id") not in LAYOUTS or
            target != get_target(target["id"])):
        raise RuntimeError("Public signer target differs from the reviewed hardware identity")
    if not isinstance(source_sha, str) or not re.fullmatch("[a-f0-9]{40}", source_sha):
        raise RuntimeError("Public signer requires the exact build source SHA")
    start, shift = LAYOUTS[target["id"]]
    if (int(target["bank_range_start"], 0) != start or
            int(target["bank_range_end"], 0) != 0xFFFFFFFF or
            int(target["bank_shift"], 0) != -shift):
        raise RuntimeError("Public signer target bank layout mismatch")
    return start, shift


def policy_hashes(files, target):
    return {"rx_bootloader_config.h": _hash(files["public_signer_bootloader_config.h"]),
            CHIP_HEADERS[target["id"]]: _hash(files["public_signer_target.h"])}


def chip_config(source, target):
    boot = Path(source)/target["bootloader_project"]
    local = boot/"src"/CHIP_HEADERS[target["id"]]
    return local if local.exists() else boot/"lib/rx_bootloader/config"/CHIP_HEADERS[target["id"]]


def _policy(path):
    text = _bytes(path).decode("utf-8")
    expected = {"RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE": 1,
                "RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE": 0,
                "RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK": 0,
                "RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE": 1,
                "RX_BOOTLOADER_INSTALL_DATA_FLASH": 0,
                "RX_BOOTLOADER_USE_DUAL_BANK": 1}
    for name, value in expected.items():
        matches = re.findall(r"^\s*#\s*define\s+" + name + r"\s+([^\r\n]+)", text, re.M)
        normalized = [re.sub(r"/\*.*?\*/|//.*", "", item).strip() for item in matches]
        if (len(normalized) != 1 or not re.fullmatch(r"\(?\s*" + str(value) +
                                                  r"[uU]?\s*\)?", normalized[0])):
            raise RuntimeError("Unsafe or ambiguous public bootloader policy: " + name)


def _srecords(path, ranges, required=()):
    decoder = _tools_module("build_rx671_fwup_v2_rsu")._decode_srecord
    memory = {}
    for number, line in enumerate(_bytes(path).decode("ascii").splitlines(), 1):
        if not line.strip():
            continue
        kind, address, data = decoder(line.strip(), number)
        if kind not in {"S1", "S2", "S3"}:
            continue
        if not data or not any(start <= address <= address + len(data)-1 <= end for start, end in ranges):
            raise RuntimeError("Public signer MOT writes outside the reviewed Code Flash/option ranges")
        for offset, value in enumerate(data):
            position = address + offset
            if position in memory and memory[position] != value:
                raise RuntimeError("Conflicting public signer S-record data")
            memory[position] = value
    if not memory or any(position not in memory for position in required):
        raise RuntimeError("Public signer MOT is missing required vector/option data")
    return memory


def _field(memory, address, size=4):
    try:
        return bytes(memory[position] for position in range(address, address+size))
    except KeyError:
        raise RuntimeError("Public signer MOT is missing required vector/option data") from None


def _runs(memory):
    runs, run, previous = [], bytearray(), None
    for address in sorted(memory):
        if previous is not None and address != previous+1:
            runs.append(bytes(run)); run.clear()
        run.append(memory[address]); previous = address
    runs.append(bytes(run))
    return runs


def _options(memory):
    if (_field(memory, 0xFE7F5D00) != bytes.fromhex("8FFFFFFF") or
            _field(memory, 0xFE7F5D20) != bytes.fromhex("FFFFFFFF")):
        raise RuntimeError("Public signer requires dual/little-endian and initial bank0 options")


def _prepared(files, target, source_sha):
    start, _ = _identity(target, source_sha)
    # Public-only parsing occurs before generic file hashing can read a PEM body.
    public = material.public_signer(files["signer.crt.pem"], files["signer.pub.pem"])
    for name, label in (("signer.crt.pem", "codesigncert"), ("signer.pub.pem", "codesignpubkey")):
        pem = _bytes(files[name]).decode("ascii").replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(("conf set " + label + " " + pem).encode("ascii")) >= 4096:
            raise RuntimeError("Public signer PEM exceeds the maintenance CLI input limit")
    metadata = json.loads(_bytes(files["public_signer_provisioner_manifest.json"]))
    required = {"profile": PROFILE, "target_id": target["id"], "target_sha256": target_fingerprint(target),
                "source_sha": source_sha, "bank_mode": "bank.dual", "tls_backend": "software",
                "cli_scope": "public_signer_only", "reset_vector_kind": "standalone_hardware_vector"}
    if (type(metadata.get("schema_version")) is not int or metadata.get("schema_version") != 1 or
            any(metadata.get(name) != value for name, value in required.items()) or
            metadata.get("formal") is not True or metadata.get("source_tree_dirty") is not False or
            metadata.get("credentials_embedded") is not False or
            metadata.get("credential_injection_requested") is not False):
        raise RuntimeError("Public signer formal manifest/source/target/profile mismatch")
    basename = Path(target["application_project"]).parent.name
    hashes = metadata.get("sha256")
    if (not isinstance(hashes, dict) or set(hashes) != {basename+suffix for suffix in (".mot", ".map", ".abs")} or
            any(not isinstance(value, str) or not re.fullmatch("[a-f0-9]{64}", value) for value in hashes.values()) or
            hashes[basename+".mot"] != _hash(files["public_signer_provisioner.mot"])):
        raise RuntimeError("Public signer provisioner manifest/hash mismatch")
    verification = metadata.get("credential_verification", {})
    if (not isinstance(verification, dict) or any(verification.get(name) is not True for name in
            ("client_and_wifi_headers_empty", "local_overrides_absent", "injection_environment_removed", "private_pem_markers_absent")) or
            verification.get("scope") != "embedded_client_claim_private_and_wifi_credentials"):
        raise RuntimeError("Public signer credential isolation is not verified")
    commands = metadata.get("effective_command_validation", {})
    if not isinstance(commands, dict) or any(commands.get(name) is not True for name in
            ("maintenance_compiler_defines_verified", "standalone_vectors_verified", "flash_ram_mapping_verified")):
        raise RuntimeError("Public signer effective compiler/linker commands are not verified")
    inputs = metadata.get("effective_input_sha256")
    project = target["application_project"]
    required_inputs = {project+"/.cproject", "Demos/include/aws_clientcredential.h", "Demos/include/aws_clientcredential_keys.h"}
    allowed_inputs = required_inputs | {project+"/src/frtos_config/"+name for name in
                                      ("aws_clientcredential.h", "aws_clientcredential_keys.h")}
    if (not isinstance(inputs, dict) or not required_inputs <= set(inputs) <= allowed_inputs or
            any(not isinstance(value, str) or not re.fullmatch("[a-f0-9]{64}", value) for value in inputs.values())):
        raise RuntimeError("Public signer effective input identities are incomplete")
    _policy(files["public_signer_bootloader_config.h"])
    memory = _srecords(files["public_signer_provisioner.mot"], ((start, 0xFFFFFFFF), *OPTIONS))
    _options(memory)
    vector = int.from_bytes(_field(memory, 0xFFFFFFFC), "little")
    if not start+0x300 <= vector <= 0xFFFBFFFF or vector not in memory:
        raise RuntimeError("Public signer provisioner reset vector is outside its loaded application")
    marker = b"PUBLIC_SIGNER_PROVISIONER source_sha=" + source_sha.encode("ascii") + b"\r\n"
    runs = _runs(memory)
    if not any(marker in run for run in runs):
        raise RuntimeError("Public signer provisioner has no matching compiled source identity")
    if any(re.search(br"-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----", run) for run in runs):
        raise RuntimeError("Private credential material detected in public maintenance image")
    actual = {"reset_vector": f"0x{vector:08X}", "mde": "0xFFFFFF8F", "initial_bank": 0,
              "compiled_source_identity_verified": True, "code_flash_and_options_only": True}
    claims = metadata.get("image_validation")
    if (not isinstance(claims, dict) or set(claims) != set(actual) or
            any(type(claims[name]) is not type(value) or claims[name] != value for name, value in actual.items())):
        raise RuntimeError("Public signer manifest image claims differ from the actual MOT")
    return {"schema_version": 1, "target_id": target["id"], "target_sha256": target_fingerprint(target),
            "source_sha": source_sha, "public_signer_spki_sha256": material._spki_sha256(public),
            "runtime_trust": "not_established"}


def validate_public_signer_material(certificate_path, public_key_path):
    public = material.public_signer(certificate_path, public_key_path)
    return {"public_signer_spki_sha256": material._spki_sha256(public), "runtime_trust": "not_established"}


def validate_initial_rsu(files, target):
    start, _ = LAYOUTS[target["id"]]
    image = _bytes(files["idt_transport.rsu"])
    if len(image) != 0xFFFC0000-start:
        raise RuntimeError("Initial RSU size differs from the reviewed dual-bank Code Flash layout")
    if (image[:8] != b"Renesas\xfe" or image[8:40] != b"sig-sha256-ecdsa"+b"\0"*16 or
            struct.unpack_from("<I", image, 0x28)[0] != 64 or
            struct.unpack_from("<III", image, 0x12C) != (0, 0xFFFFFFFF, 0xFFFFFFFF)):
        raise RuntimeError("Initial RSU header/signature/raw Data Flash policy mismatch")
    if target["id"] == "rx671-wifi":
        if image[0x200:0x300] != _tools_module("build_rx671_fwup_v2_rsu").build_descriptor():
            raise RuntimeError("Initial RX671 RSU descriptor layout mismatch")
    else:
        sequence, app, end, vector, hardware = struct.unpack_from("<IIIII", image, 0x200)
        if (sequence != 1 or app != start+0x300 or end != 0xFFFBFFFF or
                vector != 0xFFFBFFFC or hardware != 9):
            raise RuntimeError("Initial legacy RSU descriptor layout mismatch")
    vector = int.from_bytes(image[0xFFFBFFFC-start:0xFFFC0000-start], "little")
    if not start+0x300 <= vector <= 0xFFFBFFFF:
        raise RuntimeError("Initial RSU application reset vector is outside its application")
    public = material.public_signer(files["signer.crt.pem"], files["signer.pub.pem"])
    material.verify_raw_p256(public, image[0x2C:0x6C], image[0x200:])
    return material._spki_sha256(public)


def validate_boot_trust(files, target, source_sha):
    plan = _prepared(files, target, source_sha)
    _, shift = LAYOUTS[target["id"]]
    bank0 = _srecords(files["bootloader.mot"], ((0xFFFC0000, 0xFFFFFFFF), *OPTIONS),
                     (0xFFFC0000, *range(0xFFFFFF80, 0x100000000)))
    _options(bank0)
    mirror_start, mirror_end = 0xFFFC0000-shift, 0xFFFFFFFF-shift
    bank1 = _srecords(files["bootloader_bank1.mot"], ((mirror_start, mirror_end),),
                     (mirror_start, *range(0xFFFFFF80-shift, 0x100000000-shift)))
    if bank1 != {address-shift: value for address, value in bank0.items() if address >= 0xFFFC0000}:
        raise RuntimeError("Bank1 bootloader is not the exact reviewed bank0 shift")
    return plan


def validate_bundle(files, target, source_sha):
    plan = validate_boot_trust(files, target, source_sha)
    signer = validate_initial_rsu(files, target)
    return {**plan, "public_signer_spki_sha256": signer, "status": "not_run",
            "builtin_public_key_fallback": False, "private_credentials_used": False,
            "initial_state_reset": "rfp_chip_erase_before_signer_provisioning",
            "data_flash_preserved_during_initialization": False,
            "steps": ["erase_chip_and_clear_flash_options", "program_dual_provisioner", "run_dual_cli",
                      "verify_maintenance_source_witness", "format_littlefs", "store_codesigncert_and_codesignpubkey",
                      "commit_littlefs", "erase_install_ranges_preserving_data_flash", "program_bootloader_bank0",
                      "program_bootloader_bank1", "uart_install_signed_dualbank_application"],
            "verification_boundary": "Local signature binding does not prove runtime LittleFS persistence or IDT PASS"}


def source_inputs(source, runtime, target, source_sha, environ=None):
    _identity(target, source_sha)
    environment = os.environ if environ is None else environ
    raw_runtime = Path(runtime)
    if any(item.is_symlink() for item in (raw_runtime, *raw_runtime.parents)) or not raw_runtime.is_dir():
        raise RuntimeError("Public signer requires a private IDT runtime directory")
    runtime = raw_runtime.resolve(strict=True)
    files = {}
    for name, variable in ENVIRONMENT_INPUTS.items():
        value = environment.get(variable)
        if not value:
            raise RuntimeError("Public signer provisioning inputs are required for every bootloader-backed IDT scope: " + variable)
        path = _ordinary(value).resolve(strict=True)
        if runtime not in path.parents and runtime.parent/"inputs" not in path.parents:
            raise RuntimeError("Public signer inputs must remain in the private IDT runtime")
        files[name] = path
    source, here = Path(source), Path(__file__).resolve().parent
    boot = source / target["bootloader_project"]
    chip = chip_config(source, target)
    files.update({"public_signer_provision.py": here/"public_signer_provision.py",
                  "public_signer_material.py": here/"public_signer_material.py",
                  "provision_rx671_ota.py": source/"tools/provision_rx671_ota.py",
                  "rx671_ota_host.py": source/"tools/rx671_ota_host.py",
                  "build_rx671_fwup_v2_rsu.py": source/"tools/build_rx671_fwup_v2_rsu.py",
                  "public_signer_bootloader_config.h": boot/"src/rx_bootloader_config.h",
                  "public_signer_target.h": chip})
    if set(files) != PUBLIC_SIGNER_INPUTS:
        raise RuntimeError("Unexpected public signer input set")
    for path in files.values():
        _ordinary(path)
    return files


def validate_prepared_signer(source, runtime, target, source_sha, environ=None):
    return _prepared(source_inputs(source, runtime, target, source_sha, environ), target, source_sha)


class _DeadlineSerial:
    def __init__(self, serial_port, deadline, check_owner):
        self._serial, self._deadline, self._check_owner = serial_port, deadline, check_owner
    def _remaining(self):
        self._check_owner()
        remaining = self._deadline-time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Public signer CLI time budget exhausted")
        return remaining
    def __getattr__(self, name):
        self._remaining(); return getattr(self._serial, name)
    def read(self, size):
        self._serial.timeout = min(self._serial.timeout or 0.1, self._remaining())
        result = self._serial.read(size); self._remaining(); return result
    def write(self, data):
        self._serial.write_timeout = min(self._serial.write_timeout or 10, self._remaining())
        result = self._serial.write(data); self._remaining(); return result
    def close(self):
        self._serial.close()


def _download_command(download, root, target):
    if not isinstance(download, (list, tuple)) or any(not isinstance(value, str) for value in download):
        raise RuntimeError("Public signer requires the reviewed strict UART downloader argv")
    flags = {"--strict-success", "--wait-for-ready", "--ack-each-chunk"}
    options = {"--rsu", "--port", "--baud", "--timeout", "--post-tx-wait", "--ready-timeout",
               "--ready-message", "--reset-cmd", "--success-message", "--send-chunk-size", "--ack-prefix"}
    index, seen = 2, set()
    while index < len(download):
        option = download[index]
        if option in seen or option not in flags | options:
            raise RuntimeError("Unexpected strict UART downloader option")
        seen.add(option)
        index += 1 if option in flags else 2
        if index > len(download):
            raise RuntimeError("Missing strict UART downloader option value")
    def value(option):
        if download.count(option) != 1:
            raise RuntimeError("Missing or ambiguous strict UART downloader option")
        index = download.index(option)+1
        if index >= len(download):
            raise RuntimeError("Missing strict UART downloader option value")
        return download[index]
    if (len(download) < 2 or Path(download[1]) != root/"test_uart_download_rx72n.py" or
            download.count("--strict-success") != 1 or download.count("--wait-for-ready") != 1 or
            Path(value("--rsu")) != root/"idt_transport.rsu" or value("--port") != target["uart"] or
            value("--baud") != str(target["baud"]) or
            value("--success-message") != ("swap bank" if target["id"] == "rx65n-bg96" else "jump to user program") or
            value("--ready-message") != 'send "userprog.rsu" via UART.'):
        raise RuntimeError("Strict UART downloader target/image/success policy mismatch")
    reset = shlex.split(value("--reset-cmd"))
    expected = ["sudo", "-n", "/usr/local/bin/rfp-cli", "-device", target["rfp_device"], "-tool",
                "e2l:"+target["e2lite"], "-if", "fine", "-speed", target["rfp_speed"],
                "-auth", "id", "F"*32, "-sig", "-run", "-noquery"]
    if reset != expected:
        raise RuntimeError("Strict UART downloader reset command differs from the reviewed target")


def _checked_call(call, check_owner, command, timeout):
    check_owner()
    result = call(command, timeout=timeout)
    if getattr(result, "returncode", None) != 0:
        raise RuntimeError("Guarded public signer command did not return success")
    check_owner()
    return result


def provision_boot_trust(root, target, source_sha, call, check_owner=None, *, artifact_dir=None):
    """Install public boot trust; the caller keeps its lock through app install."""
    if not callable(call) or not callable(check_owner):
        raise RuntimeError("Public signer transaction requires guarded commands and ownership checks")
    root = Path(root)
    files = {name: root/name for name in PUBLIC_SIGNER_INPUTS | {"bootloader.mot", "bootloader_bank1.mot"}}
    plan = validate_boot_trust(files, target, source_sha)
    host, provisioner = _tools_module("rx671_ota_host"), _tools_module("provision_rx671_ota")
    try:
        from . import cleanup_budget as budget
    except ImportError:
        import cleanup_budget as budget
    start, shift = LAYOUTS[target["id"]]
    ranges = ((start-shift, 0xFFFBFFFF-shift), (start, 0xFFFBFFFF))
    rfp = host.RfpConfig(executable="/usr/local/bin/rfp-cli", device=target["rfp_device"],
                         tool="e2l:"+target["e2lite"], speed=target["rfp_speed"], install_ranges=ranges)
    expected = [rfp.program_command(root/"public_signer_provisioner.mot", leave_reset=True),
                rfp.run_command(), rfp.erase_ota_install_areas_command(),
                rfp.program_command(root/"bootloader.mot", leave_reset=True),
                rfp.program_command(root/"bootloader_bank1.mot", leave_reset=True)]
    phase, serial_opened = 0, False
    def checked_call(command, timeout):
        return _checked_call(call, check_owner, command, timeout)
    def guarded(command, *, timeout, label):
        nonlocal phase
        if phase >= len(expected) or list(command) != expected[phase] or "-erase-chip" in command:
            raise RuntimeError("Public signer RFP sequence differs from the reviewed transaction")
        if phase >= 1 and not serial_opened:
            raise RuntimeError("Public signer run requires an already-owned UART")
        result = checked_call(["sudo", "-n", *command], min(timeout, budget.FLASH_RFP_COMMAND_SECONDS))
        phase += 1
        return result
    def serial_opener(port, baud):
        nonlocal serial_opened
        check_owner()
        if phase != 1 or serial_opened or port != target["uart"] or baud != target["baud"]:
            raise RuntimeError("Public signer UART differs from the reviewed transaction")
        serial_opened = True
        seconds = getattr(budget, "PUBLIC_SIGNER_PROVISION_SECONDS", budget.RX671_SIGNER_PROVISION_SECONDS)
        return _DeadlineSerial(host.open_serial(port, baud), time.monotonic()+seconds, check_owner)
    events = Path(artifact_dir) if artifact_dir is not None else root/"public-signer-events"
    if any(item.is_symlink() for item in (events, *events.parents)):
        raise RuntimeError("Linked public signer event directory")
    events.mkdir(parents=True, mode=0o700, exist_ok=True)
    # Fail before chip erase if event storage is unavailable, including a
    # read-only bundle. Normal callers supply a private directory outside it.
    probe = events/(".write-check-"+str(os.getpid()))
    descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"public-signer-event-storage\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        probe.unlink()
    args = SimpleNamespace(artifact_dir=events, rfp_cli=rfp.executable,
        rfp_device=rfp.device, rfp_tool=rfp.tool, rfp_interface=rfp.interface, rfp_speed=rfp.speed,
        rfp_auth_id=rfp.auth_id, rfp_timeout=budget.FLASH_RFP_COMMAND_SECONDS,
        provisioner_mot=root/"public_signer_provisioner.mot", bootloader_mot=root/"bootloader.mot",
        port=target["uart"], baud=target["baud"], boot_timeout=45, command_timeout=15,
        commit_timeout=30, char_delay=0.002, codesigner_certificate=root/"signer.crt.pem",
        codesigner_public_key=root/"signer.pub.pem")
    # This independent command is the only chip erase. Trust is reconstructed
    # before any application boot; all later erase operations preserve DF.
    checked_call(["sudo", "-n", *rfp.common_command(), "-erase-chip", "-reset", "-noquery"],
                 budget.FLASH_RFP_COMMAND_SECONDS)
    summary = provisioner.provision(args, signer_only=True, runner=guarded, serial_opener=serial_opener,
                                    rfp_config=rfp, ready_source_sha=source_sha)
    required_steps = {"maintenance_source_witness", "cli_ready", "format", "codesigncert", "codesignpubkey", "commit",
                      "ota_install_areas_erased_after_provisioning", "bootloader_programmed"}
    if (phase != 4 or not serial_opened or summary.get("success") is not True or summary.get("signer_only") is not True or
            summary.get("data_flash_preserved_during_rfp_operations") is not True or
            not required_steps <= set(summary.get("completed_steps", [])) or
            summary.get("ota_install_area_erase_ranges") != [f"0x{a:08X}-0x{b:08X}" for a, b in ranges]):
        raise RuntimeError("Public signer CLI provisioning did not complete the actual reviewed transaction")
    guarded(expected[4], timeout=budget.FLASH_RFP_COMMAND_SECONDS, label="bank1 bootloader programming")
    return {**plan, "status": "public_boot_trust_prepared", "completed_steps": summary["completed_steps"],
            "runtime_trust": "not_established_until_signed_application_install"}


def provision_and_install(root, target, source_sha, call, download, check_owner=None):
    if not callable(call) or not callable(check_owner):
        raise RuntimeError("Public signer transaction requires guarded commands and ownership checks")
    root = Path(root)
    files = {name: root/name for name in PUBLIC_SIGNER_INPUTS | {"bootloader.mot", "bootloader_bank1.mot", "idt_transport.rsu"}}
    plan = validate_bundle(files, target, source_sha)
    _download_command(download, root, target)
    provision_boot_trust(root, target, source_sha, call, check_owner)
    try:
        from . import cleanup_budget as budget
    except ImportError:
        import cleanup_budget as budget
    _checked_call(call, check_owner, download, budget.FLASH_DOWNLOAD_SECONDS)
    return {**plan, "status": "provisioned_and_initial_image_installed",
            "runtime_trust": "signature_checked_by_bootloader_on_initial_install"}

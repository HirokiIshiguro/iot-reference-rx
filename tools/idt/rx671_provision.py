#!/usr/bin/env python3
"""Validate and install RX671 initial public signer trust through its linear CLI.

Planning/validation reads public signer files and firmware only. The actual
transaction is called by rpi_flash while it holds the bench and RFP locks; this
module has no standalone hardware-execution entry point or receipt bypass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

try:
    from .targets import get_target, target_fingerprint
except ImportError:
    from targets import get_target, target_fingerprint


RX671_INPUTS = frozenset((
    'rx671_provision.py', 'provision_rx671_ota.py', 'rx671_ota_host.py',
    'build_rx671_fwup_v2_rsu.py', 'rx671_provisioner.mot',
    'rx671_provisioner_manifest.json', 'rx671_signer.crt.pem', 'rx671_signer.pub.pem',
    'rx671_bootloader_config.h', 'rx671_target.h',
))
ENVIRONMENT_INPUTS = {
    'rx671_provisioner.mot': 'IDT_RX671_PROVISIONER_MOT_FILE',
    'rx671_provisioner_manifest.json': 'IDT_RX671_PROVISIONER_MANIFEST_FILE',
    'rx671_signer.crt.pem': 'IDT_RX671_SIGNER_CERT_FILE',
    'rx671_signer.pub.pem': 'IDT_RX671_SIGNER_PUBLIC_KEY_FILE',
}


def _tools_module(name):
    # In the remote staging directory these modules are siblings; inside the
    # source copy production helpers live one directory above this IDT module.
    try:
        return __import__(name)
    except ModuleNotFoundError as error:
        if error.name != name:
            raise
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        return __import__(name)


def _bytes(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Missing or symbolic link RX671 provisioning input: ' + path.name)
    return path.read_bytes()


def _hash(path):
    return hashlib.sha256(_bytes(path)).hexdigest()


def _policy(config_path, target_path):
    config = _bytes(config_path).decode('utf-8')
    target = _bytes(target_path).decode('utf-8')
    for text, name, value in (
        (config, 'RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE', 1),
        (config, 'RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE', 0),
        (config, 'RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK', 0),
        (config, 'RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE', 1),
        (target, 'RX_BOOTLOADER_INSTALL_DATA_FLASH', 0),
    ):
        matches = re.findall(r'^\s*#\s*define\s+' + name + r'\s+\((\d+)\)\s*(?://.*)?$', text, re.M)
        if matches != [str(value)]:
            raise RuntimeError('Unsafe or ambiguous RX671 bootloader policy: ' + name)


def _srecords(path, ranges, required):
    packager = _tools_module('build_rx671_fwup_v2_rsu')
    memory = {}
    for number, line in enumerate(_bytes(path).decode('ascii').splitlines(), 1):
        if not line.strip():
            continue
        kind, address, data = packager._decode_srecord(line.strip(), number)
        if kind not in {'S1', 'S2', 'S3'}:
            continue
        if not data or not any(start <= address <= address + len(data) - 1 <= end
                               for start, end in ranges):
            raise RuntimeError('RX671 provisioning MOT writes outside its reviewed Code Flash/option ranges')
        for offset, value in enumerate(data):
            position = address + offset
            if position in memory and memory[position] != value:
                raise RuntimeError('Conflicting RX671 provisioning S-record data')
            memory[position] = value
    if not memory or any(address not in memory for address in required):
        raise RuntimeError('RX671 provisioning MOT is missing entry/reset vector data')
    return memory


def public_signer(certificate_path, public_key_path):
    """Validate public-only PEM objects and return their matching P-256 key."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    def public_pem(path, label):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Missing or symbolic link RX671 public signer input')
        with path.open('rb', buffering=0) as stream:
            # FileIO does not prefetch a private body behind the header. Read
            # public lines only through the matching END marker; after that,
            # reject on the first extra non-whitespace byte before its body.
            first = stream.readline(80)
            if first.rstrip(b'\r\n') != b'-----BEGIN ' + label + b'-----':
                raise RuntimeError('RX671 signer input must contain exactly one public PEM object')
            encoded = bytearray(first)
            total = len(first)
            ending = b'-----END ' + label + b'-----'
            while True:
                line = stream.readline(4097 - total)
                total += len(line)
                if total > 4096:
                    raise RuntimeError('RX671 public signer PEM exceeds the provisioner CLI input limit')
                if not line:
                    raise RuntimeError('RX671 signer input must contain exactly one public PEM object')
                content = line.rstrip(b'\r\n')
                if content != ending and not re.fullmatch(b'[A-Za-z0-9+/=]*', content):
                    raise RuntimeError('RX671 signer input must contain exactly one public PEM object')
                encoded.extend(line)
                if content == ending:
                    break
                if total == 4096:
                    raise RuntimeError('RX671 public signer PEM exceeds the provisioner CLI input limit')
            while True:
                extra = stream.read(1)
                if not extra:
                    break
                if extra not in b' \t\r\n\v\f':
                    raise RuntimeError('RX671 signer input must contain exactly one public PEM object')
                total += 1
                if total > 4096:
                    raise RuntimeError('RX671 public signer PEM exceeds the provisioner CLI input limit')
            encoded = bytes(encoded).strip()
            if len(encoded) >= 4096:
                raise RuntimeError('RX671 public signer PEM exceeds the provisioner CLI input limit')
        pattern = (b'-----BEGIN ' + label + b'-----\r?\n[A-Za-z0-9+/=\r\n]+\r?\n-----END '
                   + label + b'-----')
        if not re.fullmatch(pattern, encoded):
            raise RuntimeError('RX671 signer input must contain exactly one public PEM object')
        return encoded
    certificate = x509.load_pem_x509_certificate(public_pem(certificate_path, b'CERTIFICATE'))
    public = serialization.load_pem_public_key(public_pem(public_key_path, b'PUBLIC KEY'))
    if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(public.curve, ec.SECP256R1):
        raise RuntimeError('RX671 initial signer must be ECDSA P-256')
    def der(key):
        return key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if der(public) != der(certificate.public_key()):
        raise RuntimeError('RX671 signer certificate and public key differ')
    return public


def _spki_sha256(public):
    from cryptography.hazmat.primitives import serialization
    return hashlib.sha256(public.public_bytes(serialization.Encoding.DER,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()


def validate_public_signer_material(certificate_path, public_key_path):
    public = public_signer(certificate_path, public_key_path)
    return {'signer_certificate': str(certificate_path), 'signer_public_key': str(public_key_path),
            'public_signer_spki_sha256': _spki_sha256(public), 'runtime_trust': 'not_established'}


def validate_public_signer(certificate_path, public_key_path, rsu_path):
    """Bind the public certificate, public key, and actual initial RSU signature."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    packager = _tools_module('build_rx671_fwup_v2_rsu')
    public = public_signer(certificate_path, public_key_path)
    image = _bytes(rsu_path)
    if len(image) != packager.FWUP_AREA_SIZE:
        raise RuntimeError('RX671 initial RSU size differs from the reviewed dual-bank layout')
    signature = image[0x2C:0x6C]
    if (image[:packager.RSU_HEADER_SIZE] != packager.build_header(signature) or
            image[packager.RSU_HEADER_SIZE:packager.APPLICATION_START-packager.FWUP_AREA_START]
            != packager.build_descriptor()):
        raise RuntimeError('RX671 initial RSU header/descriptor policy mismatch')
    try:
        public.verify(utils.encode_dss_signature(int.from_bytes(signature[:32], 'big'),
                                                 int.from_bytes(signature[32:], 'big')),
                      image[packager.RSU_HEADER_SIZE:], ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise RuntimeError('RX671 initial RSU does not match the provisioned public signer') from None
    return _spki_sha256(public)


def _validate_prepared_files(files, target, source_sha):
    reviewed = get_target('rx671-wifi')
    if target != reviewed:
        raise RuntimeError('RX671 provisioning target differs from the reviewed hardware identity')
    if not isinstance(source_sha, str) or not re.fullmatch('[a-f0-9]{40}', source_sha):
        raise RuntimeError('RX671 provisioner requires the exact IDT build source SHA')
    metadata = json.loads(_bytes(files['rx671_provisioner_manifest.json']))
    if (metadata.get('schema_version') != 1 or
            metadata.get('profile') != 'rx671-bank-single-ota-provisioner-v1' or
            metadata.get('bank_mode') != 'bank.single' or
            metadata.get('credentials_embedded') is not False or
            metadata.get('source_sha') != source_sha or
            metadata.get('sha256', {}).get('aws_wifi_rx671_ek.mot') != _hash(files['rx671_provisioner.mot'])):
        raise RuntimeError('RX671 linear production provisioner manifest/hash/source mismatch')
    _policy(files['rx671_bootloader_config.h'], files['rx671_target.h'])
    options = ((0xFE7F5D00, 0xFE7F5D7F), (0xFE7F7D70, 0xFE7F7D9F))
    _srecords(files['rx671_provisioner.mot'], ((0xFFE00000, 0xFFFFFFFF), *options),
              range(0xFFFFFFFC, 0x100000000))
    return {
        'schema_version': 1, 'target_id': target['id'], 'target_sha256': target_fingerprint(target),
        'source_sha': source_sha,
        'signer_certificate': str(files['rx671_signer.crt.pem']),
        'signer_public_key': str(files['rx671_signer.pub.pem']),
        'public_signer_spki_sha256': _spki_sha256(public_signer(files['rx671_signer.crt.pem'], files['rx671_signer.pub.pem'])),
        'runtime_trust': 'not_established',
    }


def validate_prepared_signer(source, runtime, target, source_sha, environ=None):
    """Check local public bootstrap materials before firmware packaging/build.

    This proves only the intended public signer binding and provisioner inputs,
    never existing Data Flash contents. The flash transaction still has to run
    the real linear CLI and verify the actual signed initial RSU.
    """
    files = source_inputs(source, runtime, target, source_sha, environ)
    return _validate_prepared_files(files, target, source_sha)


def validate_bundle(files, target, source_sha):
    """Validate all inputs on the host and again remotely before any board I/O."""
    _validate_prepared_files(files, target, source_sha)
    options = ((0xFE7F5D00, 0xFE7F5D7F), (0xFE7F7D70, 0xFE7F7D9F))
    bank0 = _srecords(files['bootloader.mot'], ((0xFFFC0000, 0xFFFFFFFF), *options),
                     (0xFFFC0000, *range(0xFFFFFF80, 0x100000000)))
    bank1 = _srecords(files['bootloader_bank1.mot'], ((0xFFEC0000, 0xFFEFFFFF),),
                     (0xFFEC0000, *range(0xFFEFFF80, 0xFFF00000)))
    shifted = {address - 0x100000: value for address, value in bank0.items() if address >= 0xFFF00000}
    if bank1 != shifted:
        raise RuntimeError('RX671 bank1 bootloader is not the exact reviewed bank0 shift')
    signer_sha = validate_public_signer(files['rx671_signer.crt.pem'], files['rx671_signer.pub.pem'],
                                        files['idt_transport.rsu'])
    return {
        'schema_version': 1, 'target_id': target['id'], 'target_sha256': target_fingerprint(target),
        'source_sha': source_sha, 'public_signer_spki_sha256': signer_sha,
        'status': 'not_run', 'runtime_trust': 'not_established',
        'builtin_public_key_fallback': False, 'private_credentials_used': False,
        'steps': ['program_linear_provisioner', 'run_linear_cli', 'format_littlefs',
                  'store_codesigncert_and_codesignpubkey', 'commit_littlefs',
                  'erase_install_ranges_preserving_data_flash', 'program_bootloader_bank0',
                  'program_bootloader_bank1', 'uart_install_signed_dualbank_application'],
        'authorization_boundary': 'board UART/programming/reset require separate hardware authorization',
        'verification_boundary': 'local signature binding does not prove runtime LittleFS persistence or IDT PASS',
    }


def source_inputs(source, runtime, target, source_sha, environ=None):
    environment = os.environ if environ is None else environ
    runtime = Path(runtime).resolve(strict=True)
    files = {}
    for name, variable in ENVIRONMENT_INPUTS.items():
        value = environment.get(variable)
        if not value:
            raise RuntimeError('RX671 initial public signer provisioning is required for every bootloader-backed IDT scope: ' + variable)
        raw = Path(value)
        if raw.is_symlink() or not raw.is_file():
            raise RuntimeError('Missing or symbolic link RX671 provisioning input: ' + name)
        path = raw.resolve(strict=True)
        if runtime not in path.parents and runtime.parent / 'inputs' not in path.parents:
            raise RuntimeError('RX671 provisioning inputs must remain in the private IDT runtime')
        files[name] = path
    source = Path(source)
    here = Path(__file__).resolve().parent
    files.update({
        'rx671_provision.py': here / 'rx671_provision.py',
        'provision_rx671_ota.py': source / 'tools/provision_rx671_ota.py',
        'rx671_ota_host.py': source / 'tools/rx671_ota_host.py',
        'build_rx671_fwup_v2_rsu.py': source / 'tools/build_rx671_fwup_v2_rsu.py',
        'rx671_bootloader_config.h': source / target['bootloader_project'] / 'src/rx_bootloader_config.h',
        'rx671_target.h': source / target['bootloader_project'] / 'src/rx671.h',
    })
    return files


class _DeadlineSerial:
    """Bound the CLI phase independently of its individual prompt timeouts."""
    def __init__(self, serial_port, deadline, check_owner):
        self._serial = serial_port
        self._deadline = deadline
        self._check_owner = check_owner

    def _remaining(self):
        self._check_owner()
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('RX671 signer provisioning CLI time budget exhausted')
        return remaining

    def __getattr__(self, name):
        self._remaining()
        return getattr(self._serial, name)

    def read(self, size):
        self._serial.timeout = min(self._serial.timeout or 0.1, self._remaining())
        result = self._serial.read(size)
        self._remaining()
        return result

    def write(self, data):
        self._serial.write_timeout = min(self._serial.write_timeout or 10, self._remaining())
        result = self._serial.write(data)
        self._remaining()
        return result

    def close(self):
        self._serial.close()


def provision_and_install(root, target, source_sha, call, download, check_owner=lambda: None):
    """Execute only inside the caller's guarded, locked flash transaction.

    The production helper performs the actual CLI commit and DF-preserving
    transition. No pre-existing summary/receipt can substitute for that call.
    The UART downloader then requires a signed-image boot success marker.
    """
    root = Path(root)
    files = {name: root / name for name in RX671_INPUTS}
    files.update({name: root / name for name in ('bootloader.mot', 'bootloader_bank1.mot', 'idt_transport.rsu')})
    plan = validate_bundle(files, target, source_sha)
    provisioner = _tools_module('provision_rx671_ota')
    host = _tools_module('rx671_ota_host')
    try:
        from .cleanup_budget import FLASH_RFP_COMMAND_SECONDS, FLASH_DOWNLOAD_SECONDS, RX671_SIGNER_PROVISION_SECONDS
    except ImportError:
        from cleanup_budget import FLASH_RFP_COMMAND_SECONDS, FLASH_DOWNLOAD_SECONDS, RX671_SIGNER_PROVISION_SECONDS
    args = SimpleNamespace(
        artifact_dir=root / 'rx671-provision-events',
        rfp_cli='/usr/local/bin/rfp-cli', rfp_device=target['rfp_device'],
        rfp_tool='e2l:' + target['e2lite'], rfp_interface='fine', rfp_speed=target['rfp_speed'],
        rfp_auth_id='F' * 32, rfp_timeout=FLASH_RFP_COMMAND_SECONDS,
        provisioner_mot=root / 'rx671_provisioner.mot', bootloader_mot=root / 'bootloader.mot',
        port=target['uart'], baud=target['baud'], boot_timeout=45, command_timeout=15,
        commit_timeout=30, char_delay=0.002,
        codesigner_certificate=root / 'rx671_signer.crt.pem',
        codesigner_public_key=root / 'rx671_signer.pub.pem',
    )
    def guarded(command, *, timeout, label):
        if '-erase-chip' in command:
            raise RuntimeError('RX671 provisioning must preserve Data Flash')
        return call(['sudo', '-n', *command], timeout=timeout)
    def serial_opener(port, baud):
        check_owner()
        serial_port = host.open_serial(port, baud)
        return _DeadlineSerial(serial_port, time.monotonic() + RX671_SIGNER_PROVISION_SECONDS,
                               check_owner)
    summary = provisioner.provision(args, signer_only=True, runner=guarded, serial_opener=serial_opener)
    if (summary.get('success') is not True or summary.get('signer_only') is not True or
            summary.get('data_flash_preserved_during_rfp_operations') is not True or
            not {'codesigncert', 'codesignpubkey', 'commit',
                 'ota_install_areas_erased_after_provisioning', 'bootloader_programmed'}
            <= set(summary.get('completed_steps', []))):
        raise RuntimeError('RX671 production signer provisioning did not complete')
    rfp = host.RfpConfig(executable='/usr/local/bin/rfp-cli', device=target['rfp_device'],
                         tool='e2l:' + target['e2lite'], speed=target['rfp_speed'])
    guarded(rfp.program_command(root / 'bootloader_bank1.mot', leave_reset=True),
            label='bank1 bootloader programming', timeout=FLASH_RFP_COMMAND_SECONDS)
    call(download, timeout=FLASH_DOWNLOAD_SECONDS)
    return {**plan, 'status': 'provisioned_and_initial_image_installed',
            'runtime_trust': 'signature_checked_by_bootloader_on_initial_install'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Prepare an offline RX671 initial-signer plan; no hardware access')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    target = get_target('rx671-wifi')
    output = args.source / 'artifacts/idt/build_transport'
    manifest = json.loads(_bytes(output / 'build_manifest.json'))
    if (manifest.get('target_id') != target['id'] or
            manifest.get('target_sha256') != target_fingerprint(target)):
        raise RuntimeError('RX671 build manifest target mismatch')
    files = source_inputs(args.source, args.runtime, target, manifest.get('source_sha'))
    files.update({name: output / (target['artifact_basename'] + '.rsu' if name == 'idt_transport.rsu' else name)
                  for name in ('bootloader.mot', 'bootloader_bank1.mot', 'idt_transport.rsu')})
    plan = validate_bundle(files, target, manifest.get('source_sha'))
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())

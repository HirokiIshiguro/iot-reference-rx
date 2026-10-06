"""Public-only RX671 initial trust and guarded installation; no board/cloud I/O."""
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/idt'))
sys.path.insert(0, str(ROOT / 'tools'))
import rpi_flash
import flash_transport
from tools.idt import run_idt
import rx671_provision as controller
import provision_rx671_ota as provisioner
import rx671_ota_host as host
import build_rx671_fwup_v2_rsu as packager
from targets import get_target, target_fingerprint


SOURCE_SHA = 'a' * 40


def srecord(address, data):
    encoded = bytes([len(data) + 5]) + address.to_bytes(4, 'big') + data
    return 'S3' + (encoded + bytes([(~sum(encoded)) & 0xFF])).hex().upper() + '\n'


class GuardedPublicInput:
    """Observe actual raw-file reads, including a BufferedReader's prefetch."""
    def __init__(self, stream, private_body_start):
        self.stream = stream
        self.raw = getattr(stream, 'raw', stream)
        self.private_body_start = private_body_start
        self.last_position = 0

    def _check_raw_position(self):
        self.last_position = self.raw.tell()
        if self.last_position > self.private_body_start:
            raise AssertionError('dummy private body was read or prefetched')

    def readline(self, limit=-1):
        value = self.stream.readline(limit)
        self._check_raw_position()
        return value

    def read(self, count=-1):
        if count < 0 or self.raw.tell() + count > self.private_body_start:
            raise AssertionError('read would enter the dummy private body')
        value = self.stream.read(count)
        self._check_raw_position()
        return value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.last_position = self.raw.tell()
        self.stream.close()


class PublicFixture:
    """Synthetic ephemeral signing key; never load a repository/user private key."""
    def __init__(self, root):
        self.root = root
        self.files = {name: root / name for name in controller.RX671_INPUTS}
        self.files.update({name: root / name for name in ('bootloader.mot', 'bootloader_bank1.mot', 'idt_transport.rsu')})
        key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.now(timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic-unit-public-signer')])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(1).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                .sign(key, hashes.SHA256()))
        self.files['rx671_signer.crt.pem'].write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self.files['rx671_signer.pub.pem'].write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.files['idt_transport.rsu'].write_bytes(packager.build_image(b'\xff' * packager.APPLICATION_SIZE, key))
        self.files['rx671_provisioner.mot'].write_text(srecord(0xFFE00000, b'linear') + srecord(0xFFFFFFFC, b'\x00\x00\xe0\xff'))
        self.files['bootloader.mot'].write_text(srecord(0xFFFC0000, b'boot') + srecord(0xFFFFFF80, bytes(range(128))))
        self.files['bootloader_bank1.mot'].write_text(srecord(0xFFEC0000, b'boot') + srecord(0xFFEFFF80, bytes(range(128))))
        self.files['rx671_bootloader_config.h'].write_text(
            '#define RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE (1)\n'
            '#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE (0)\n'
            '#define RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK (0)\n'
            '#define RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE (1)\n')
        self.files['rx671_target.h'].write_text('#define RX_BOOTLOADER_INSTALL_DATA_FLASH (0)\n')
        self.source = root / 'source'
        sample_public = self.source / 'sample_keys/secp256r1.publickey'
        sample_public.parent.mkdir(parents=True)
        sample_public.write_bytes(self.files['rx671_signer.pub.pem'].read_bytes())
        boot_project = self.source / get_target('rx671-wifi')['bootloader_project'] / 'src'
        boot_project.mkdir(parents=True)
        (boot_project / 'rx_bootloader_config.h').write_bytes(self.files['rx671_bootloader_config.h'].read_bytes())
        (boot_project / 'rx671.h').write_bytes(self.files['rx671_target.h'].read_bytes())
        self.metadata = {'schema_version': 1, 'profile': 'rx671-bank-single-ota-provisioner-v1',
                         'bank_mode': 'bank.single', 'credentials_embedded': False, 'source_sha': SOURCE_SHA,
                         'sha256': {'aws_wifi_rx671_ek.mot': hashlib.sha256(self.files['rx671_provisioner.mot'].read_bytes()).hexdigest()}}
        self.write_metadata()

    def write_metadata(self):
        self.files['rx671_provisioner_manifest.json'].write_text(json.dumps(self.metadata))

    def plan(self):
        return controller.validate_bundle(self.files, get_target('rx671-wifi'), SOURCE_SHA)


class Rx671TrustTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = PublicFixture(Path(self.temporary.name))
        # Other legacy tests reload these names during unittest collection.
        # Always patch the same live module instance used by the controller.
        self.provisioner = controller._tools_module('provision_rx671_ota')
        self.host = controller._tools_module('rx671_ota_host')

    def test_selected_uart_downloaders_use_receiver_progress_without_changing_gates(self):
        for name in ('rx72n-ethernet', 'rx65n-bg96', 'rx671-wifi'):
            with self.subTest(target=name):
                command = rpi_flash.download_command(Path('/private'), get_target(name), ['inert-reset'])
                self.assertIn('--strict-success', command)
                self.assertEqual('420', command[command.index('--timeout') + 1])
                if name == 'rx72n-ethernet':
                    self.assertNotIn('--ack-each-chunk', command)
                else:
                    self.assertIn('--ack-each-chunk', command)
                    self.assertEqual('32768', command[command.index('--send-chunk-size') + 1])
                    self.assertEqual('installing firmware...', command[command.index('--ack-prefix') + 1])

    def test_public_plan_does_not_establish_runtime_or_qualification(self):
        plan = self.fixture.plan()
        self.assertEqual('not_run', plan['status'])
        self.assertEqual('not_established', plan['runtime_trust'])
        self.assertFalse(plan['builtin_public_key_fallback'])
        self.assertFalse(plan['private_credentials_used'])
        self.assertEqual('rx671-wifi', plan['target_id'])

    def test_prepared_api_needs_no_rsu_and_keeps_runtime_unknown(self):
        self.fixture.files['idt_transport.rsu'].unlink()
        environment = {variable: str(self.fixture.files[name])
                       for name, variable in controller.ENVIRONMENT_INPUTS.items()}
        result = controller.validate_prepared_signer(self.fixture.source, self.fixture.root, get_target('rx671-wifi'),
                                                     SOURCE_SHA, environ=environment)
        self.assertEqual('not_established', result['runtime_trust'])
        self.assertEqual(target_fingerprint(get_target('rx671-wifi')), result['target_sha256'])

    def test_private_input_header_is_rejected_without_loading_its_body(self):
        path = self.fixture.files['rx671_signer.crt.pem']
        header = b'-----BEGIN PRIVATE KEY-----\n'
        path.write_bytes(header + b'synthetic-value\n-----END PRIVATE KEY-----\n')
        streams = []
        original_open = Path.open
        def guarded_open(candidate, mode='r', buffering=-1, **kwargs):
            stream = original_open(candidate, mode, buffering=buffering, **kwargs)
            if candidate == path:
                stream = GuardedPublicInput(stream, len(header))
                streams.append(stream)
            return stream
        with patch.object(Path, 'open', guarded_open):
            with self.assertRaisesRegex(RuntimeError, 'exactly one public PEM'):
                controller.validate_public_signer_material(path, self.fixture.files['rx671_signer.pub.pem'])
        self.assertEqual(len(header), streams[0].last_position)

    def test_runtime_execution_accepts_only_private_inputs_sibling(self):
        root = self.fixture.root
        runtime, inputs = root / 'execution', root / 'inputs' / 'rx671-bootstrap'
        runtime.mkdir()
        inputs.mkdir(parents=True)
        public_inputs = PublicFixture(inputs)
        environment = {variable: str(public_inputs.files[name])
                       for name, variable in controller.ENVIRONMENT_INPUTS.items()}
        controller.validate_prepared_signer(public_inputs.source, runtime, get_target('rx671-wifi'), SOURCE_SHA, environ=environment)
        environment['IDT_RX671_SIGNER_CERT_FILE'] = str(self.fixture.files['rx671_signer.crt.pem'])
        with self.assertRaisesRegex(RuntimeError, 'private IDT runtime'):
            controller.source_inputs(ROOT, runtime, get_target('rx671-wifi'), SOURCE_SHA, environ=environment)

    def test_native_missing_bootstrap_is_rejected_before_idt_install(self):
        with patch.object(run_idt, 'HOST', {'windows_powershell': str(self.fixture.files['rx671_signer.crt.pem'])}), \
             patch.object(run_idt.subprocess, 'check_output', return_value='7'), \
             patch.object(run_idt, 'install_idt') as install, patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'requires reviewed public bootstrap input'):
                run_idt.transport(self.fixture.root, 'unit-region', Mock(), {'source_sha': SOURCE_SHA},
                                  'pkcs11', target=get_target('rx671-wifi'))
        install.assert_not_called()

    def test_native_private_pem_is_rejected_before_any_bootstrap_copy(self):
        inputs = self.fixture.root / 'inputs'
        inputs.mkdir()
        self.fixture.files['rx671_signer.crt.pem'].write_bytes(b'-----BEGIN PRIVATE KEY-----\nsynthetic\n')
        environment = {variable: str(self.fixture.files[name])
                       for name, variable in controller.ENVIRONMENT_INPUTS.items()}
        with self.assertRaisesRegex(RuntimeError, 'exactly one public PEM'):
            run_idt.rx671_bootstrap_environment(inputs, SOURCE_SHA, environ=environment)
        self.assertFalse((inputs / 'rx671-bootstrap').exists())

    def test_failed_prepared_validation_removes_only_its_input_copies(self):
        inputs = self.fixture.root / 'inputs'
        inputs.mkdir()
        unrelated = inputs / 'preserved.txt'
        unrelated.write_text('preserved')
        self.fixture.metadata['bank_mode'] = 'bank.dual'
        self.fixture.write_metadata()
        environment = {variable: str(self.fixture.files[name])
                       for name, variable in controller.ENVIRONMENT_INPUTS.items()}
        with patch.object(run_idt, 'SOURCE', self.fixture.source):
            with self.assertRaisesRegex(RuntimeError, 'manifest/hash/source mismatch'):
                run_idt.rx671_bootstrap_environment(inputs, SOURCE_SHA, environ=environment)
        self.assertFalse((inputs / 'rx671-bootstrap').exists())
        self.assertEqual('preserved', unrelated.read_text())

    def test_staged_boot_policy_requires_effective_input_hash_binding(self):
        hashes = {'rx_bootloader_config.h': hashlib.sha256(self.fixture.files['rx671_bootloader_config.h'].read_bytes()).hexdigest(),
                  'rx671.h': hashlib.sha256(self.fixture.files['rx671_target.h'].read_bytes()).hexdigest()}
        rpi_flash.validate_rx671_policy_binding(self.fixture.root, {'bootloader_policy_sha256': hashes})
        with self.assertRaisesRegex(RuntimeError, 'effective build inputs'):
            rpi_flash.validate_rx671_policy_binding(self.fixture.root, {'bootloader_policy_sha256': {}})

    def test_ssh_timeout_keeps_remote_staging_until_process_exit_is_proved(self):
        source = self.fixture.root / 'runtime-source'
        source.mkdir()
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            if 'rpi_flash.py' in command[-1]:
                raise subprocess.TimeoutExpired(['synthetic-ssh'], kwargs['timeout'])
            return Mock(returncode=0)
        with patch.dict(os.environ, {'IDT_BENCH_TOKEN': 'c' * 32,
                                     'IDT_RUNTIME_DIR': str(self.fixture.root),
                                     'IDT_TARGET': 'rx72n-ethernet', 'IDT_SCOPE': 'pkcs11'}, clear=True), \
             patch.object(sys, 'argv', ['synthetic-flash', str(source)]), \
             patch.object(flash_transport, 'validate_source', return_value=source), \
             patch.object(flash_transport, 'validated_inputs', return_value=({'dummy.mot': self.fixture.files['bootloader.mot']}, {})), \
             patch.object(flash_transport.subprocess, 'check_output', return_value='synthetic-path'), \
             patch.object(flash_transport.subprocess, 'run', side_effect=execute):
            with self.assertRaises(subprocess.TimeoutExpired):
                flash_transport.main()
        self.assertFalse(any('shutil.rmtree' in command[-1] for command in calls))

    def test_different_certificate_or_rsu_signature_fails_before_io(self):
        other = self.fixture.root / 'other'
        other.mkdir()
        other_fixture = PublicFixture(other)
        self.fixture.files['rx671_signer.crt.pem'].write_bytes(other_fixture.files['rx671_signer.crt.pem'].read_bytes())
        with self.assertRaisesRegex(RuntimeError, 'certificate and public key differ'):
            self.fixture.plan()
        self.fixture.files['rx671_signer.pub.pem'].write_bytes(other_fixture.files['rx671_signer.pub.pem'].read_bytes())
        with self.assertRaisesRegex(RuntimeError, 'does not match the provisioned public signer'):
            self.fixture.plan()

    def test_rsu_data_flash_and_layout_policy_fail_closed(self):
        image = bytearray(self.fixture.files['idt_transport.rsu'].read_bytes())
        image[0x12C] = 1
        self.fixture.files['idt_transport.rsu'].write_bytes(image)
        with self.assertRaisesRegex(RuntimeError, 'header/descriptor policy mismatch'):
            self.fixture.plan()

    def test_sample_or_self_attested_provisioner_metadata_is_insufficient(self):
        for name, value in (('profile', 'idt-dualbank'), ('source_sha', 'b' * 40),
                            ('bank_mode', 'bank.dual'), ('credentials_embedded', True)):
            old = self.fixture.metadata[name]
            self.fixture.metadata[name] = value
            self.fixture.write_metadata()
            with self.assertRaisesRegex(RuntimeError, 'manifest/hash/source mismatch'):
                self.fixture.plan()
            self.fixture.metadata[name] = old
        self.fixture.write_metadata()
        self.fixture.files['rx671_provisioner.mot'].write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'manifest/hash/source mismatch'):
            self.fixture.plan()

    def test_programming_data_flash_is_refused_even_with_matching_manifest_hash(self):
        path = self.fixture.files['rx671_provisioner.mot']
        path.write_text(path.read_text() + srecord(0x00100000, b'DF'))
        self.fixture.metadata['sha256']['aws_wifi_rx671_ek.mot'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.write_metadata()
        with self.assertRaisesRegex(RuntimeError, 'outside its reviewed Code Flash'):
            self.fixture.plan()

    def test_bank1_substitution_is_refused(self):
        self.fixture.files['bootloader_bank1.mot'].write_text(srecord(0xFFEC0000, b'evil') + srecord(0xFFEFFF80, bytes(range(128))))
        with self.assertRaisesRegex(RuntimeError, 'exact reviewed bank0 shift'):
            self.fixture.plan()

    def test_unsafe_builtin_fallback_is_refused(self):
        path = self.fixture.files['rx671_bootloader_config.h']
        path.write_text(path.read_text().replace('RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK (0)',
                                                'RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK (1)'))
        with self.assertRaisesRegex(RuntimeError, 'Unsafe or ambiguous'):
            self.fixture.plan()

    def test_public_pem_cannot_smuggle_private_material(self):
        path = self.fixture.files['rx671_signer.crt.pem']
        public = path.read_bytes()
        header = b'-----BEGIN PRIVATE KEY-----\n'
        path.write_bytes(public + header + b'synthetic\n-----END PRIVATE KEY-----\n')
        streams = []
        original_open = Path.open
        def guarded_open(candidate, mode='r', buffering=-1, **kwargs):
            stream = original_open(candidate, mode, buffering=buffering, **kwargs)
            if candidate == path:
                stream = GuardedPublicInput(stream, len(public) + len(header))
                streams.append(stream)
            return stream
        with patch.object(Path, 'open', guarded_open):
            with self.assertRaisesRegex(RuntimeError, 'exactly one public PEM'):
                controller.validate_public_signer_material(path, self.fixture.files['rx671_signer.pub.pem'])
        self.assertLessEqual(streams[0].last_position, len(public) + len(header))

    def test_single_public_pem_accepts_only_trailing_whitespace(self):
        path = self.fixture.files['rx671_signer.crt.pem']
        path.write_bytes(path.read_bytes() + b' \t\r\n')
        controller.validate_public_signer_material(path, self.fixture.files['rx671_signer.pub.pem'])
        path.write_bytes(path.read_bytes() + b'extra-public-object')
        with self.assertRaisesRegex(RuntimeError, 'exactly one public PEM'):
            controller.validate_public_signer_material(path, self.fixture.files['rx671_signer.pub.pem'])

    def test_public_pem_line_reader_keeps_four_kib_bound(self):
        path = self.fixture.files['rx671_signer.crt.pem']
        path.write_bytes(b'-----BEGIN CERTIFICATE-----\n' + b'A' * 4096 + b'\n-----END CERTIFICATE-----\n')
        with self.assertRaisesRegex(RuntimeError, 'CLI input limit'):
            controller.validate_public_signer_material(path, self.fixture.files['rx671_signer.pub.pem'])

    def test_all_scope_callback_inputs_are_required_before_hardware(self):
        for scope in ('transport', 'mqtt', 'ota-mqtt', 'pkcs11', 'ota-pal'):
            with patch.dict(os.environ, {'IDT_SCOPE': scope}, clear=True):
                with self.assertRaisesRegex(RuntimeError, 'required for every bootloader-backed'):
                    controller.source_inputs(ROOT, self.fixture.root, get_target('rx671-wifi'), SOURCE_SHA)
            with patch.object(rpi_flash, 'open_rfp_lock') as lock:
                with self.assertRaisesRegex(RuntimeError, 'provisioning inputs are required'):
                    rpi_flash.flash(self.fixture.root, get_target('rx671-wifi'), 'c' * 32)
                lock.assert_not_called()

    def test_incorrect_target_identity_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'reviewed hardware identity'):
            controller.validate_bundle(self.fixture.files, get_target('rx65n-bg96'), SOURCE_SHA)

    def test_real_linear_helper_public_only_order_preserves_data_flash(self):
        commands, cli = [], []
        serial = Mock(timeout=0.1, write_timeout=10)
        def run(command, **kwargs):
            commands.append(command)
            return Mock(returncode=0)
        def send(_serial, command, **kwargs):
            cli.append(command)
            return b'OK'
        with patch.object(self.host, 'open_serial', return_value=serial), \
             patch.object(self.provisioner, 'enter_cli'), \
             patch.object(self.provisioner, 'send_ascii_command', side_effect=send), \
             patch.object(self.provisioner, '_wifi_credentials_from_environment', side_effect=AssertionError('no secrets')), \
             patch.object(self.provisioner, '_set_wifi_credentials', side_effect=AssertionError('no secrets')):
            result = controller.provision_and_install(self.fixture.root, get_target('rx671-wifi'), SOURCE_SHA,
                                                      run, ['synthetic-uart-download'])
        self.assertEqual(6, len(commands))
        self.assertTrue(all('-erase-chip' not in command for command in commands))
        self.assertEqual(self.fixture.files['rx671_provisioner.mot'], Path(commands[0][-1]))
        self.assertIn('-run', commands[1])
        self.assertEqual(['FFE00000,FFEBFFFF', 'FFF00000,FFFBFFFF'],
                         [commands[2][index+1] for index, value in enumerate(commands[2]) if value == '-range'])
        self.assertEqual(self.fixture.files['bootloader.mot'], Path(commands[3][-1]))
        self.assertEqual(self.fixture.files['bootloader_bank1.mot'], Path(commands[4][-1]))
        self.assertEqual(['synthetic-uart-download'], commands[5])
        self.assertEqual('format', cli[0])
        self.assertTrue(cli[1].startswith('conf set codesigncert '))
        self.assertTrue(cli[2].startswith('conf set codesignpubkey '))
        self.assertEqual('conf commit', cli[3])
        self.assertEqual('provisioned_and_initial_image_installed', result['status'])
        serial.close.assert_called_once()

    def test_failed_real_provisioner_cannot_be_replaced_by_receipt(self):
        run = Mock()
        with patch.object(self.provisioner, 'provision', return_value={'success': True}), \
             patch.object(self.host, 'open_serial', side_effect=AssertionError('no board I/O')):
            with self.assertRaisesRegex(RuntimeError, 'did not complete'):
                controller.provision_and_install(self.fixture.root, get_target('rx671-wifi'), SOURCE_SHA,
                                                 run, ['synthetic-uart-download'])
        run.assert_not_called()

    def test_cli_commit_failure_stops_before_erase_and_closes_uart(self):
        commands = []
        serial = Mock(timeout=0.1, write_timeout=10)
        def send(_serial, command, **kwargs):
            if command == 'conf commit':
                raise RuntimeError('synthetic commit failure')
            return b'OK'
        with patch.object(self.host, 'open_serial', return_value=serial), \
             patch.object(self.provisioner, 'enter_cli'), \
             patch.object(self.provisioner, 'send_ascii_command', side_effect=send):
            with self.assertRaisesRegex(RuntimeError, 'synthetic commit failure'):
                controller.provision_and_install(self.fixture.root, get_target('rx671-wifi'), SOURCE_SHA,
                                                 lambda command, **kwargs: commands.append(command),
                                                 ['synthetic-uart-download'])
        self.assertEqual(2, len(commands))
        self.assertFalse(any('-erase' in command for command in commands))
        serial.close.assert_called_once()

    def test_cli_deadline_rejects_without_writing(self):
        serial = Mock()
        bounded = controller._DeadlineSerial(serial, 10, Mock())
        with patch.object(controller.time, 'monotonic', return_value=11):
            with self.assertRaisesRegex(RuntimeError, 'time budget exhausted'):
                bounded.write(b'public')
        serial.write.assert_not_called()

    def test_control_slow_partial_reply_cannot_extend_whole_phase_deadline(self):
        clock = [0.0]
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.connect.side_effect = lambda path: clock.__setitem__(0, clock[0] + 3)
        client.sendall.side_effect = lambda data: clock.__setitem__(0, clock[0] + 3)
        def partial(size):
            clock[0] += 4
            return b'{'  # Progress cannot refresh an absolute deadline.
        client.recv.side_effect = partial
        with patch.object(rpi_flash, 'validate_owner', return_value={'control_socket': '/synthetic.sock'}), \
             patch.object(rpi_flash.socket, 'AF_UNIX', 1, create=True), \
             patch.object(rpi_flash.socket, 'socket', return_value=client), \
             patch.object(rpi_flash.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(RuntimeError, 'control time budget exhausted'):
                rpi_flash.control(get_target('rx671-wifi'), 'c' * 32, 'pause')
        self.assertEqual(3, client.recv.call_count)
        self.assertEqual([15, 12, 9, 5, 1], [call.args[0] for call in client.settimeout.call_args_list])


if __name__ == '__main__':
    unittest.main()

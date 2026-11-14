import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.idt import rpi4_transport_overlay as overlay


class TransportOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.qemu = self.root / 'qemu'
        self.qemu.write_bytes(b'dummy qemu')
        self.qemu.chmod(0o700)
        self.sysroot = self.root / 'sysroot'
        (self.sysroot / 'lib').mkdir(parents=True)
        self.library_hashes = {}
        for name in overlay.SYSROOT_SHA256:
            path = self.sysroot / name
            path.write_bytes(name.encode())
            self.library_hashes[name] = hashlib.sha256(name.encode()).hexdigest()
        self.archive = self.root / 'bundle.zip'
        self.test_json = {'id': 'Full_Transport_Interface_TLS', 'execution': {'timeout': 123,
                          'linux': dict(overlay.EXPECTED_LINUX), 'win': {'cmd': 'unchanged'}}}
        self.write_archive(self.test_json)

    def write_archive(self, test_json, extra=None):
        with zipfile.ZipFile(self.archive, 'w') as z:
            prefix = 'devicetester_freertos_linux/'
            z.writestr(prefix + overlay.TEST_RELATIVE.as_posix(), json.dumps(test_json))
            z.writestr(prefix + overlay.FRQ_RELATIVE.as_posix(), b'unchanged frq')
            z.writestr(prefix + 'bin/devicetester_linux_x86-64', b'unchanged idt')
            if extra:
                z.writestr(extra, 'bad')

    def prepare(self):
        with patch.object(overlay, 'QEMU_SHA256', hashlib.sha256(b'dummy qemu').hexdigest()), \
             patch.object(overlay, 'SYSROOT_SHA256', self.library_hashes), \
             patch.object(overlay, 'verify_archive_digest') as verify_archive, \
             patch.object(overlay, 'verify_install') as verify_tree:
            result = overlay.prepare(self.archive, self.root, self.qemu, self.sysroot)
            verify_archive.assert_called_once()
            verify_tree.assert_called_once()
            return result

    def test_changes_only_the_selected_command_in_the_private_copy(self):
        source_hash = overlay.sha256(self.archive)
        run = self.prepare()
        idt = run / 'devicetester_freertos_linux'
        actual = json.loads((idt / overlay.TEST_RELATIVE).read_text())
        linux = actual['execution'].pop('linux')
        expected = json.loads(json.dumps(self.test_json))
        expected['execution'].pop('linux')
        self.assertEqual(expected, actual)
        self.assertEqual(str(self.qemu), linux['cmd'])
        self.assertEqual(['-L', str(self.sysroot), str(idt / overlay.FRQ_RELATIVE),
                          *overlay.EXPECTED_LINUX['args']], linux['args'])
        self.assertEqual(b'unchanged frq', (idt / overlay.FRQ_RELATIVE).read_bytes())
        self.assertEqual(source_hash, overlay.sha256(self.archive))
        provenance = json.loads((run / 'overlay-provenance.json').read_text())
        self.assertEqual('not-established', provenance['qualification'])
        self.assertEqual(overlay.TEST_RELATIVE.as_posix(), provenance['changed_file'])

    def test_rejects_unexpected_vendor_command_and_removes_partial_copy(self):
        bad = json.loads(json.dumps(self.test_json))
        bad['execution']['linux']['args'] = ['unexpected']
        self.write_archive(bad)
        with self.assertRaisesRegex(ValueError, 'unexpected Transport'):
            self.prepare()
        self.assertEqual([], list(self.root.glob('idt-rpi4-transport-*')))

    def test_rejects_untrusted_qemu_and_unsafe_archive(self):
        self.qemu.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'QEMU executable hash'):
            self.prepare()
        self.qemu.write_bytes(b'dummy qemu')
        self.write_archive(self.test_json, extra='../escape')
        with self.assertRaisesRegex(ValueError, 'unsafe bundle'):
            self.prepare()
        self.assertEqual([], list(self.root.glob('idt-rpi4-transport-*')))


if __name__ == '__main__':
    unittest.main()

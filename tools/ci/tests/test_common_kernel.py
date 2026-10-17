"""Reject actual SC rollback/copy while preserving its generated evidence."""
from pathlib import Path
import tempfile
import unittest
from tools.ci import check_common_kernel as guard

ROOT = Path(__file__).resolve().parents[3]

class CommonKernelTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)
        paths = ['Configuration/sc_freertos_lts.xml', 'Configuration/sc_freertos_kernel.xml',
                 'Middleware/FreeRTOS/FreeRTOS-Kernel/include/task.h']
        for name in guard.PROJECTS:
            base = 'Projects/' + name + '/e2studio_ccrx/'
            paths += [base+'.project', base+name+'.scfg',
                      base+'.settings/smartconfigurator/rtos/nopg_freertos.xml',
                      base+'.settings/smartconfigurator/rtos/FreeRTOS_Kernel.xml']
        for relative in paths:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT/relative).read_bytes())
        return root

    def test_current_five_projects_keep_pristine_kernel_113_source(self):
        result = guard.validate(ROOT)
        self.assertEqual('V11.3.0', result['kernel_version'])
        self.assertEqual(5, result['project_count'])
        self.assertFalse(result['source_copy_enabled'])
        self.assertFalse(result['gui_generation_observed'])

    def test_regenerated_111_selection_or_kernel_body_copy_is_rejected_without_deleting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            app = root/'Projects'/guard.PROJECTS[0]/'e2studio_ccrx'
            scfg = app/(guard.PROJECTS[0]+'.scfg')
            original = scfg.read_bytes()
            reverted = original.replace(b'version="11.3.0"', b'version="11.1.0"')
            self.assertNotEqual(original, reverted)
            scfg.write_bytes(reverted)
            with self.assertRaisesRegex(ValueError, 'SC Kernel version reverted'):
                guard.validate(root)
            self.assertEqual(reverted, scfg.read_bytes())
            scfg.write_bytes(original)
            body = app/'src/FreeRTOS/include/task.h'
            body.parent.mkdir(parents=True)
            body.write_bytes(b'synthetic generated Kernel body')
            with self.assertRaisesRegex(ValueError, 'local Kernel body copy'):
                guard.validate(root)
            self.assertEqual(b'synthetic generated Kernel body', body.read_bytes())

    def test_source_copy_directive_cannot_be_added_even_to_all_matching_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            canonical = root/'Configuration/sc_freertos_lts.xml'
            changed = canonical.read_bytes().replace(b'</package>', b'<sourcecopy>src/FreeRTOS</sourcecopy></package>')
            canonical.write_bytes(changed)
            for name in guard.PROJECTS:
                (root/'Projects'/name/'e2studio_ccrx/.settings/smartconfigurator/rtos/nopg_freertos.xml').write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'configuration headers only'):
                guard.validate(root)

if __name__ == '__main__':
    unittest.main()

"""Reject actual SC rollback/copy while preserving its generated evidence."""
from pathlib import Path
import tempfile
import unittest
from tools.ci import check_common_kernel as guard

ROOT = Path(__file__).resolve().parents[3]

def copy_flash_configuration(root):
    for path in guard.FLASH_INPUTS:
        relative = guard.FLASH_LEAF + '/' + path
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    for name in guard.FLASH_PROJECTS:
        base = 'Projects/' + name + '/e2studio_ccrx/'
        for relative in (base + '.project', base + '.cproject', base + name + '.scfg',
                         base + '.settings/com.renesas.smc.e2studio.qe.xml',
                         base + 'src/smc_gen/r_config/r_flash_rx_config.h'):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / relative).read_bytes())

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
        copy_flash_configuration(root)
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

class FlashConfigurationTests(unittest.TestCase):
    def test_upstream_only_leaf_is_rejected_even_with_matching_consumer_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            copy_flash_configuration(root)
            makefile = root / guard.FLASH_LEAF / 'Makefile'
            makefile.write_text('VERSION = 5.31\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Flash leaf version differs'):
                guard.validate_flash(root)

    def test_selected_leaf_must_expose_the_nesting_capability(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            copy_flash_configuration(root)
            interface = root / guard.FLASH_LEAF / guard.FLASH_INPUTS[3]
            interface.write_text('#define FLASH_RX_SAFFTI_VERSION "' + guard.FLASH_VERSION + '"\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'FCU nesting API capability'):
                guard.validate_flash(root)

    def test_eight_projects_select_the_leaf_and_matching_generated_settings(self):
        result = guard.validate_flash(ROOT)
        self.assertEqual(8, result['project_count'])

    def test_regeneration_rollbacks_are_rejected_and_preserved(self):
        cases = (
            ('boot_loader_rx671_ek.scfg', b'FLASH_CFG_FCU_EN_NESTED_INT" selectedIndex="1"',
             b'FLASH_CFG_FCU_EN_NESTED_INT" selectedIndex="0"', 'SC FCU'),
            ('.settings/com.renesas.smc.e2studio.qe.xml', b'r_flash_rx5.31.saffti-custom.1',
             b'r_flash_rx5.31', 'QE Flash package'),
            ('src/smc_gen/r_config/r_flash_rx_config.h', b'FLASH_CFG_FCU_EN_NESTED_INT   (1)',
             b'FLASH_CFG_FCU_EN_NESTED_INT   (0)', 'generated FCU'),
            ('.project', b'Middleware/Renesas/r_flash_rx/r_flash_rx_vx.xx',
             b'Middleware/Renesas/rx-driver-package/source/r_flash_rx/r_flash_rx_vx.xx', 'reviewed leaf'),
            ('.cproject', b'smc_gen/r_flash_rx/', b'smc_gen/unrelated/', 'generated Flash body'),
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            copy_flash_configuration(root)
            project = root / 'Projects/boot_loader_rx671_ek/e2studio_ccrx'
            for relative, before, after, message in cases:
                with self.subTest(relative=relative):
                    path = project / relative
                    original = path.read_bytes()
                    changed = original.replace(before, after)
                    self.assertNotEqual(original, changed)
                    path.write_bytes(changed)
                    with self.assertRaisesRegex(ValueError, message):
                        guard.validate_flash(root)
                    self.assertEqual(changed, path.read_bytes())
                    path.write_bytes(original)

    def test_application_regeneration_cannot_enable_fcu_nesting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            copy_flash_configuration(root)
            header = root / ('Projects/' + guard.PROJECTS[0] +
                             '/e2studio_ccrx/src/smc_gen/r_config/r_flash_rx_config.h')
            changed = header.read_bytes().replace(b'FLASH_CFG_FCU_EN_NESTED_INT   (0)',
                                                  b'FLASH_CFG_FCU_EN_NESTED_INT   (1)')
            header.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'generated FCU'):
                guard.validate_flash(root)
            self.assertEqual(changed, header.read_bytes())

if __name__ == '__main__':
    unittest.main()

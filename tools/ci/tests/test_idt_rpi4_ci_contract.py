"""CI contract for the opt-in protected RPi4 Transport path."""
from pathlib import Path
import re
import unittest

from tools.ci.tests.test_windows_ccrx_build_serialization_contract import top_level_job_blocks

ROOT = Path(__file__).resolve().parents[3]


class Rpi4TransportCiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = (ROOT / '.gitlab-ci.yml').read_text(encoding='utf-8-sig')
        cls.pilot = (ROOT / 'tools/ci/rpi4_transport_pilot.yml').read_text(encoding='utf-8-sig')
        cls.jobs = top_level_job_blocks(cls.root)
        cls.pilot_jobs = top_level_job_blocks(cls.pilot)

    def test_normal_windows_idt_and_ota_entrypoints_are_preserved(self):
        job = self.jobs['.rx_idt_job']
        self.assertIn('tools/idt/run_idt.py', job)
        self.assertNotIn('tools/idt/oidc_job.py', job)
        for name in ('create_rx72n_ether_ota', 'test_rx72n_ether_ota', 'cleanup_rx72n_ether_ota'):
            self.assertNotIn('rpi4_', self.jobs[name])

    def test_only_opt_in_protected_transport_profiles_are_selected(self):
        self.assertIn('- local: /tools/ci/rpi4_transport_pilot.yml', self.root)
        workflow = self.jobs['workflow']
        first = workflow.index('$IDT_PAIR_MODE =~ /^(transport|transport-controller)$/')
        legacy = workflow.index('# Select RUN_RX_IDT')
        self.assertLess(first, legacy)
        self.assertIn('$CI_DEBUG_TRACE', workflow[first:legacy])
        for selector in ('RUN_RX_IDT', 'RUN_RX72N_IDT', 'RX72N_TEST_SCOPE', 'RX65N_BG96_TEST_SCOPE',
                         'RX671_WIFI_TEST_SCOPE', 'RUN_RX671_BOOTLOADER_SMOKE', 'PIPELINE_PROFILE'):
            self.assertIn('$' + selector, workflow[first:legacy])
        self.assertIn('$CI_COMMIT_REF_PROTECTED == "true"', workflow[first:legacy])
        self.assertIn('$CI_PIPELINE_SOURCE == "pipeline"', workflow[first:legacy])
        self.assertIn('PIPELINE_PROFILE: "rpi4-transport"', workflow[first:legacy])
        self.assertIn('- if: \'$IDT_PAIR_MODE =~ /^(transport|transport-controller)$/\'\n      when: never',
                      workflow[first:legacy])
        rules = self.pilot_jobs['.rpi4_linux_transport_common']
        self.assertIn('when: manual', rules)
        self.assertIn('allow_failure: false', rules)
        self.assertIn('$CI_COMMIT_REF_PROTECTED == "true"', rules)
        self.assertIn('RX_OIDC_ID_TOKEN:', rules)

    def test_same_sha_preparation_and_preflight_gate_the_controller(self):
        package = self.pilot_jobs['rpi4_prepare_package']
        snap = self.pilot_jobs['rpi4_snapshot_verify']
        controller = self.pilot_jobs['rpi4_transport_controller']
        self.assertIn('- job: rpi4_prepare_build', package)
        self.assertIn('windows-source-sha256.txt', package)
        self.assertIn('- job: rpi4_prepare_package', snap)
        self.assertIn('- job: rpi4_prepare_package', controller)
        self.assertIn('- job: rpi4_transport_preflight', controller)
        self.assertIn('junit: artifacts/idt/FRQ_Report.xml', controller)
        worker = self.pilot_jobs['rpi4_windows_worker']
        self.assertIn('$CI_PIPELINE_SOURCE == "pipeline"', worker)
        self.assertIn('$CI_COMMIT_REF_PROTECTED == "true"', worker)
        self.assertIn('resource_group: $WINDOWS_CCRX_BUILD_RESOURCE_GROUP', worker)
        self.assertNotIn('windows_ccrx_host_lease', worker)
        self.assertNotIn('IDT_PAIR_LEASE_DEFINITION', worker)
        self.assertNotIn('id_tokens:', worker)


if __name__ == '__main__':
    unittest.main()

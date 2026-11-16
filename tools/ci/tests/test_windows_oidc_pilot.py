"""Contracts for the opt-in Windows IDT OIDC candidate; no AWS or hardware."""
from pathlib import Path
import hashlib
import os
import sys
import unittest
from unittest.mock import patch

from tools.ci.tests.test_windows_ccrx_build_serialization_contract import top_level_job_blocks
from tools.idt import oidc_job
from tools.idt import check_host
from tools.ci.tests.test_idt_oidc_job import environment, SHA, NOW, ACCESS, SECRET, TOKEN
from tools.aws.oidc_session import FixedSession
from datetime import timedelta


ROOT = Path(__file__).resolve().parents[3]


class WindowsOidcPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = (ROOT / '.gitlab-ci.yml').read_text(encoding='utf-8-sig')
        cls.blocks = top_level_job_blocks(cls.ci)

    def test_existing_windows_and_rpi4_paths_remain_default(self):
        self.assertIn('  IDT_WINDOWS_OIDC_PILOT: ""', self.ci)
        legacy = self.blocks['.rx_idt_job']
        self.assertIn('tools/idt/run_idt.py', legacy)
        self.assertNotIn('tools/idt/oidc_job.py', legacy)
        matrix = self.blocks['matrix_rx_idt_transport']
        for target in ('rx72n-ethernet', 'rx65n-bg96', 'rx671-wifi'):
            self.assertIn(target, matrix)
        self.assertIn('.rx_idt_job', matrix)
        self.assertIn('- local: /tools/ci/rpi4_transport_pilot.yml', self.ci)
        self.assertIn('nightly_rx65n_r_cellular_tests', self.blocks)

    def test_opt_in_is_protected_single_target_and_rejects_mixed_profiles(self):
        job = self.blocks['windows_rx671_idt_oidc_pilot']
        for item in ('IDT_TARGET: "rx671-wifi"', 'RX_OIDC_ID_TOKEN:',
                     '$CI_COMMIT_REF_PROTECTED == "true"', 'IDT_WINDOWS_OIDC_PILOT == "rx671-preflight"',
                     'IDT_SCOPE == "preflight"', 'before_script: []', 'after_script: []',
                     'tools/idt/oidc_job.py'):
            self.assertIn(item, job)
        workflow = self.blocks['workflow']
        first = workflow.index('$IDT_WINDOWS_OIDC_PILOT != ""')
        pilot = workflow.index('IDT_WINDOWS_OIDC_PILOT == "rx671-preflight"')
        legacy = workflow.index('# Select RUN_RX_IDT')
        self.assertLess(first, pilot)
        self.assertLess(pilot, legacy)
        self.assertIn('$IDT_PAIR_MODE != ""', workflow[first:pilot])
        self.assertIn('$RUN_RX_IDT == "true"', workflow[first:pilot])
        self.assertIn('$CI_DEBUG_TRACE', workflow[first:pilot])
        self.assertIn('PIPELINE_PROFILE: "idt-windows-oidc"', workflow[pilot:legacy])

    def test_unreviewed_configuration_cannot_exchange_token(self):
        self.assertEqual({}, oidc_job.REVIEWED_CONFIGS)
        with self.assertRaisesRegex(oidc_job.OidcError, 'unreviewed IDT configuration'):
            oidc_job.prepare_child({'RUN_RX_IDT': 'true', 'IDT_SCOPE': 'transport',
                                    'IDT_TARGET': 'rx671-wifi'}, source_sha='a' * 40,
                                   config=None, user_name='test')

    def test_preflight_config_accepts_only_reviewed_role_ref_and_target(self):
        role = 'arn:aws:iam::123456789012:role/saffti-oss-gitlab-oidc'
        env = {'IDT_WINDOWS_OIDC_PILOT': 'rx671-preflight',
               'CI_COMMIT_BRANCH': oidc_job.PILOT_REF, 'RUN_RX_IDT': 'true',
               'IDT_TARGET': 'rx671-wifi', 'IDT_SCOPE': 'preflight', 'AWS_ROLE_ARN': role}
        with patch.object(oidc_job, 'PILOT_ROLE_SHA256', hashlib.sha256(role.encode()).hexdigest()):
            config = oidc_job.reviewed_preflight_config(env)
            self.assertEqual((oidc_job.PILOT_REF, 3, role), (config.ref, config.runner_id, config.role_arn))
            for key, value in (('CI_COMMIT_BRANCH', 'main'), ('RUN_RX_IDT', 'false'),
                               ('IDT_TARGET', 'rx72n-ethernet'), ('IDT_SCOPE', 'transport'),
                               ('AWS_ROLE_ARN', role + '-other')):
                with self.subTest(key=key), self.assertRaises(oidc_job.OidcError):
                    oidc_job.reviewed_preflight_config({**env, key: value})

    def test_preflight_passes_pinned_ref_into_fixed_session(self):
        role = 'arn:aws:iam::123456789012:role/saffti-oss-gitlab-oidc'
        env = {**environment(), 'IDT_WINDOWS_OIDC_PILOT': 'rx671-preflight',
               'CI_COMMIT_BRANCH': oidc_job.PILOT_REF, 'RUN_RX_IDT': 'true',
               'IDT_TARGET': 'rx671-wifi', 'IDT_SCOPE': 'preflight', 'AWS_ROLE_ARN': role,
               'RX671_EK_WIFI_SSID': 'fixture-only', 'RX671_EK_WIFI_PASSPHRASE': 'fixture-only'}
        seen = []
        def issue(_env, expected, **_kwargs):
            seen.append(expected)
            return FixedSession(ACCESS, SECRET, TOKEN, NOW + timedelta(hours=3))
        with patch.object(oidc_job, 'PILOT_ROLE_SHA256', hashlib.sha256(role.encode()).hexdigest()):
            config = oidc_job.reviewed_preflight_config(env)
            child = oidc_job.prepare_child(env, source_sha=SHA, config=config,
                                           user_name='ishig', session_factory=issue)
        self.assertEqual((oidc_job.PILOT_REF, SHA, 3), (seen[0].ref, seen[0].sha, seen[0].runner_id))
        self.assertEqual('true', child['RX_WINDOWS_IDT_OIDC_REQUIRED'])
        self.assertNotIn('RX_OIDC_ID_TOKEN', child)
        self.assertNotIn('RX671_EK_WIFI_SSID', child)
        self.assertNotIn('RX671_EK_WIFI_PASSPHRASE', child)

    def test_existing_host_check_runs_but_oidc_missing_session_fails_before_aws(self):
        with patch.object(sys, 'argv', ['check_host', '--check-aws']), \
             patch.object(check_host, 'load_host_profile', return_value={}), \
             patch.object(check_host, 'get_target', return_value={}), \
             patch.object(check_host, 'check_host', return_value={'host_preflight_passed': True}) as check, \
             patch('builtins.print'):
            with patch.dict(os.environ, {'CI': 'true'}, clear=True):
                self.assertEqual(0, check_host.main())
            check.assert_called_once()
            check.reset_mock()
            with patch.dict(os.environ, {'CI': 'true', 'RX_WINDOWS_IDT_OIDC_REQUIRED': 'true'}, clear=True):
                with self.assertRaisesRegex(oidc_job.OidcError, 'missing fixed OIDC session'):
                    check_host.main()
            check.assert_not_called()


if __name__ == '__main__':
    unittest.main()

"""Offline checks for the isolated, manually gated RX72N candidate."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
CI = (ROOT / '.gitlab-ci.yml').read_text(encoding='utf-8')
PWSH = shutil.which('pwsh')


def block(name, next_name):
    return CI.split('\n' + name + ':\n', 1)[1].split('\n' + next_name + ':\n', 1)[0]


def before_script(job):
    source = job.split('  before_script:\n    - |\n', 1)[1].split('  script:\n', 1)[0]
    return '\n'.join(line[6:] if line.startswith('      ') else line for line in source.splitlines())


class OneShotCandidateTests(unittest.TestCase):
    def test_manual_preparation_and_controller_are_scoped(self):
        build = block('build_rx72n_ether', '.normal_boot_package')
        package = block('package_normal_boot_rx72n', 'rpi4_windows_worker')
        snapshot = block('rpi4_snapshot_verify', '.rpi4_linux_transport_common')
        common = block('.rpi4_linux_transport_common', 'rpi4_transport_preflight')
        preflight = block('rpi4_transport_preflight', 'rpi4_transport_controller')
        controller = CI.split('\nrpi4_transport_controller:\n', 1)[1]
        self.assertIn('when: manual', build)
        self.assertIn('when: manual', common)
        self.assertIn('allow_failure: false', build)
        self.assertIn('allow_failure: false', common)
        self.assertIn('--preflight-only', preflight)
        self.assertIn('job: rpi4_transport_preflight', controller)
        self.assertIn('job: rpi4_snapshot_verify', common)
        self.assertIn('job: package_normal_boot_rx72n', snapshot)
        self.assertNotIn('id_tokens:', snapshot)
        self.assertNotIn('when: manual', snapshot)
        self.assertIn('job: package_normal_boot_rx72n', controller)
        self.assertIn('job: build_rx72n_ether', package)
        self.assertNotIn('id_tokens:', build)
        self.assertNotIn('id_tokens:', package)
        self.assertIn('RX_OIDC_ID_TOKEN:', common)
        self.assertEqual(CI.count('codex/209-rpi4-transport-once-20261115'), 4)
        for filename in ('public_signer_provisioner.mot', 'public_signer_provisioner_manifest.json',
                         'signer.crt.pem', 'signer.pub.pem'):
            self.assertIn('artifacts/normal_boot_rx72n/' + filename, common)

    @unittest.skipUnless(os.name == 'nt' and PWSH, 'Windows PowerShell 7 required')
    def test_preparation_guards_reject_wrong_context_and_clear_aws_values(self):
        build = before_script(block('build_rx72n_ether', '.normal_boot_package'))
        package = before_script(block('.normal_boot_package', 'package_normal_boot_rx72n'))
        env = dict(os.environ, CI_PROJECT_ID='38', CI_RUNNER_ID='3',
                   CI_COMMIT_BRANCH='codex/209-rpi4-transport-once-20261115',
                   CI_COMMIT_REF_PROTECTED='true', CI_PIPELINE_ID='123', CI_JOB_ID='456',
                   RX72N_TLS_BACKEND='software', RX72N_TLS13_0RTT_ENABLE='false',
                   RX72N_REQUIRE_TLS_VERSION='', RX72N_SIGNING_KEY='sample_keys/secp256r1.privatekey',
                   E2STUDIO_CLI='C:/Renesas/e2_studio_2026_04_2/eclipse/e2studio-cli.exe',
                   RX72N_E2STUDIO_TIMEOUT_SECONDS='1200',
                   E2STUDIO_WORKSPACE='C:/ai/codex/ws/ci-rx72n-ether-123-456',
                   NORMAL_BOOT_TARGET='rx72n-ethernet', NORMAL_BOOT_SIGNING_KEY_VARIABLE='RX72N_SIGNING_KEY',
                   NORMAL_BOOT_BACKEND_VARIABLE='RX72N_TLS_BACKEND',
                   NORMAL_BOOT_ARTIFACT_DIR='artifacts/normal_boot_rx72n', NORMAL_BOOT_RSU='rx72n_app.rsu',
                   NORMAL_BOOT_BOOT0='Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/HardwareDebug/boot_loader_rx72n_envision_kit.mot',
                   NORMAL_BOOT_BOOT1='Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/HardwareDebug/boot_loader_rx72n_envision_kit_bank1.mot',
                   AWS_ACCESS_KEY_ID='fixture', RX_OIDC_ID_TOKEN='fixture')
        for source in (build, package):
            check = source + "\nif (Test-Path Env:AWS_ACCESS_KEY_ID) { throw 'AWS value retained' }\n" \
                             "if (Test-Path Env:RX_OIDC_ID_TOKEN) { throw 'OIDC value retained' }\n"
            good = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', check],
                                  env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(good.returncode, 0, good.stderr)
            bad = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', check],
                                 env={**env, 'CI_RUNNER_ID': '29'}, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(bad.returncode, 0)


if __name__ == '__main__':
    unittest.main()

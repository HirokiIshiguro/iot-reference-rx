"""Verify public artifact staging without weakening source snapshots."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.idt import stage_public_assets as stage
from tools.idt import rpi4_snapshot_verify as verify


class WindowsSourceDigestTests(unittest.TestCase):
    def test_snapshot_job_requires_exact_runner_ref_and_sha(self):
        sha = 'a' * 40
        env = {'CI_PROJECT_ID': '38', 'CI_RUNNER_ID': '28', 'CI_COMMIT_REF_PROTECTED': 'true',
               'CI_COMMIT_BRANCH': verify.REF, 'CI_PIPELINE_SOURCE': 'api',
               'IDT_PAIR_MODE': 'transport-controller', 'CI_COMMIT_SHA': sha,
               'CI_JOB_ID': '17', 'CI_PIPELINE_ID': '19'}
        job = {'status': 'running', 'id': 17, 'pipeline': {'id': 19, 'ref': verify.REF},
               'runner': {'id': 28}, 'commit': {'id': sha}, 'tag_list': [verify.RUNNER_TAG]}
        verify.verify_job(env, job, sha)
        for changed in ({**env, 'CI_RUNNER_ID': '26'}, {**env, 'CI_COMMIT_BRANCH': 'main'},
                        {**env, 'CI_COMMIT_SHA': 'b' * 40}):
            with self.assertRaises(ValueError):
                verify.verify_job(changed, job, sha)

    def test_digest_is_taken_before_its_own_artifact_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory).resolve()
            (source / 'tracked.txt').write_text('source bytes\n', encoding='utf-8')
            expected = stage.source_digest(source)
            target = source / 'artifacts/idt-source/windows-source-sha256.txt'
            stage.write_source_digest(source, target)
            self.assertEqual(target.read_text(encoding='ascii').strip(), expected)
            self.assertNotEqual(stage.source_digest(source), expected)
            with self.assertRaises(ValueError):
                stage.write_source_digest(source, target)


@unittest.skipUnless(sys.platform == 'linux', 'Linux artifact ownership and no-follow required')
class PublicAssetStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'; self.source.mkdir()
        self.private = self.base / 'private'; self.private.mkdir()
        (self.source / '.gitlab-ci.yml').write_text('same source\n', encoding='utf-8')
        (self.source / 'tracked.txt').write_text('source bytes\n', encoding='utf-8')
        self.windows_digest = stage.source_digest(self.source)
        self.incoming = self.source / 'artifacts/normal_boot_rx72n'
        self.incoming.mkdir(parents=True)
        for name in stage.ARTIFACT_NAMES:
            (self.incoming / name).write_text(self.windows_digest + '\n' if name == stage.DIGEST_NAME else 'public fixture\n', encoding='utf-8')

    def test_staged_artifacts_do_not_enter_identical_source_snapshot(self):
        self.assertNotEqual(stage.source_digest(self.source), self.windows_digest)
        with patch.object(stage, 'validate_normal_bundle') as validate:
            env, expected = stage.stage_assets(self.source, self.private, 'a' * 40)
        validate.assert_called_once()
        self.assertEqual(expected, self.windows_digest)
        self.assertEqual(stage.source_digest(self.source), expected)
        self.assertFalse(self.incoming.exists())
        self.assertEqual(set(env), set(stage.ENVIRONMENT_INPUTS.values()))
        for value in env.values():
            self.assertTrue(Path(value).is_file())
            self.assertTrue(Path(value).is_relative_to(self.private))

    def test_extra_or_linked_artifacts_are_rejected(self):
        (self.incoming / 'unexpected').write_text('fixture', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'artifact set'):
            stage.stage_assets(self.source, self.private, 'a' * 40)
        (self.incoming / 'unexpected').unlink()
        file = self.incoming / 'signer.pub.pem'
        file.unlink(); file.symlink_to(self.source / 'tracked.txt')
        with self.assertRaises((OSError, ValueError)):
            stage.stage_assets(self.source, self.private, 'a' * 40)
        self.assertTrue((self.source / 'tracked.txt').is_file())


if __name__ == '__main__':
    unittest.main()

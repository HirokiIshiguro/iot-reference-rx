"""Offline checks for the protected no-AWS source snapshot and public staging."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.idt import rpi4_snapshot_verify as snapshot
from tools.idt import stage_public_assets as assets

SHA = 'a' * 40
REF = 'codex/209-rpi4-reviewed'


def identity():
    env = {'CI_PROJECT_ID': '38', 'CI_RUNNER_ID': '28', 'CI_COMMIT_REF_PROTECTED': 'true',
           'CI_COMMIT_BRANCH': REF, 'CI_PIPELINE_SOURCE': 'api', 'IDT_PAIR_MODE': 'transport-controller',
           'CI_COMMIT_SHA': SHA, 'CI_JOB_ID': '17', 'CI_PIPELINE_ID': '19'}
    job = {'id': 17, 'status': 'running', 'pipeline': {'id': 19, 'ref': REF},
           'runner': {'id': 28}, 'commit': {'id': SHA}, 'tag_list': [snapshot.RUNNER_TAG]}
    return env, job


class SnapshotIdentityTests(unittest.TestCase):
    def test_only_matching_protected_job_and_sha_are_accepted(self):
        env, job = identity()
        snapshot.verify_job(env, job, SHA)
        for key, bad in (('CI_COMMIT_REF_PROTECTED', 'false'), ('CI_COMMIT_BRANCH', 'different'),
                         ('CI_PROJECT_ID', '39'), ('CI_RUNNER_ID', '29'), ('CI_COMMIT_SHA', 'b' * 40),
                         ('CI_PIPELINE_SOURCE', 'push'), ('IDT_PAIR_MODE', 'transport')):
            with self.subTest(key=key):
                altered = dict(env, **{key: bad})
                with self.assertRaises(ValueError):
                    snapshot.verify_job(altered, job, SHA)
        for key, bad in (('status', 'success'), ('runner', {'id': 29}), ('commit', {'id': 'b' * 40}),
                         ('pipeline', {'id': 19, 'ref': 'different'})):
            with self.subTest(key=key):
                altered = dict(job, **{key: bad})
                with self.assertRaises(ValueError):
                    snapshot.verify_job(env, altered, SHA)


@unittest.skipUnless(os.name == 'posix', 'POSIX ownership and no-follow checks required')
class PublicAssetStagingTests(unittest.TestCase):
    def test_exact_public_set_is_validated_and_staged_outside_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source'; source.mkdir()
            incoming = source / 'artifacts' / 'normal_boot_rx72n'; incoming.mkdir(parents=True)
            private = root / 'private'; private.mkdir()
            for name in assets.ARTIFACT_NAMES:
                (incoming / name).write_text(('a' * 64 + '\n') if name == assets.DIGEST_NAME else 'public\n')
            with patch.object(assets, 'validate_normal_bundle') as validate:
                result, digest = assets.stage_assets(source, private, SHA)
            self.assertEqual(digest, 'a' * 64)
            self.assertEqual(set(result), set(assets.ENVIRONMENT_INPUTS.values()))
            validate.assert_called_once()
            self.assertEqual(validate.call_args.args[2], SHA)
            self.assertFalse(incoming.exists())
            self.assertEqual({p.name for p in (private / 'public-assets').iterdir()}, assets.ARTIFACT_NAMES)

    def test_unexpected_artifact_stops_before_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source'; source.mkdir()
            incoming = source / 'artifacts' / 'normal_boot_rx72n'; incoming.mkdir(parents=True)
            private = root / 'private'; private.mkdir()
            for name in assets.ARTIFACT_NAMES | {'unexpected'}:
                (incoming / name).write_text('fixture\n')
            with self.assertRaisesRegex(ValueError, 'unexpected public artifact set'):
                assets.stage_assets(source, private, SHA)
            self.assertTrue((incoming / 'unexpected').is_file())


if __name__ == '__main__':
    unittest.main()

"""Exercise real flock/shell behavior with an inert fake programmer."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.name == 'posix' and shutil.which('flock'), 'requires POSIX flock')
class RfpCliLockedTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.lock_dir = self.root / 'lock'
        self.lock_dir.mkdir()
        self.lock = self.lock_dir / 'rfp-cli.lock'
        self.marker = self.root / 'called.txt'
        self.fake = self.root / 'fake-rfp'
        self.fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$RFP_TEST_ARGS"\n')
        self.fake.chmod(0o700)
        self.env = dict(os.environ, RFP_CLI_LOCK_DIR=str(self.lock_dir),
                        REAL_RFP_CLI=str(self.fake), RFP_TEST_ARGS=str(self.marker))

    def command(self):
        return ['sh', str(ROOT / 'tools/rfp_cli_locked.sh'), '-sig', 'argument with spaces']

    def test_success_preserves_arguments(self):
        result = subprocess.run(self.command(), env=self.env, capture_output=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(['-sig', 'argument with spaces'], self.marker.read_text().splitlines())

    def test_existing_or_dangling_unsafe_sentinel_never_starts_programmer(self):
        sentinel = Path(str(self.lock) + '.unsafe.json')
        for dangling in (False, True):
            if dangling:
                sentinel.symlink_to(self.root / 'missing')
            else:
                sentinel.write_text('{}')
            result = subprocess.run(self.command(), env=self.env, capture_output=True, timeout=5)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse(self.marker.exists())
            sentinel.unlink()

    def test_sentinel_created_by_previous_lock_owner_blocks_waiting_programmer(self):
        # The real flock remains responsible for locking; this shim only
        # exposes that the wrapper has passed its early sentinel check.
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        flock = bin_dir / 'flock'
        flock.write_text('#!/bin/sh\necho entering-flock\nexec "' + shutil.which('flock') + '" "$@"\n')
        flock.chmod(0o700)
        self.env['PATH'] = str(bin_dir) + os.pathsep + self.env['PATH']
        holder_code = (
            "import fcntl,sys;from pathlib import Path;"
            "lock=Path(sys.argv[1]);f=lock.open('a');fcntl.flock(f,fcntl.LOCK_EX);"
            "print('ready',flush=True);sys.stdin.readline();"
            "Path(str(lock)+'.unsafe.json').write_text('{}');f.close()"
        )
        with subprocess.Popen([sys.executable, '-c', holder_code, str(self.lock)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as holder:
            self.assertEqual('ready', holder.stdout.readline().strip())
            with subprocess.Popen(self.command(), env=self.env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) as waiting:
                self.assertEqual(b'entering-flock', waiting.stdout.readline().strip())
                holder.stdin.write('release\n')
                holder.stdin.flush()
                holder.wait(timeout=5)
                waiting.communicate(timeout=5)
                self.assertNotEqual(0, waiting.returncode)
                self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()

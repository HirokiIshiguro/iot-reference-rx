"""Owned runtime cleanup tests, anchored to a disposable local test parent."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.ci import cleanup_rx671_fleet_runtime as runtime

SHA = "a" * 40


class FleetRuntimeCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "rx671-fleet-123-456"
        self.root.mkdir(mode=0o700)
        os.chmod(self.root, 0o700)
        (self.root / ".owner").write_bytes(f"123:456:{SHA}\n".encode())
        (self.root / "private.bin").write_bytes(b"synthetic-private-payload")
        self.sibling = self.parent / "unrelated.txt"
        self.sibling.write_bytes(b"preserve sibling")
        self.real_metadata = runtime._metadata
        self.uid = self.root.stat().st_uid
        for active_patch in (patch.object(runtime, "RUNTIME_PARENT", self.parent),
                             patch.object(runtime.sys, "platform", "linux"),
                             patch.object(runtime.os, "geteuid", return_value=self.uid, create=True),
                             patch.object(runtime, "_metadata", side_effect=self.metadata)):
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def metadata(self, path, **changes):
        item = self.real_metadata(path)
        values = {name: getattr(item, name, 0) for name in
                  ("st_mode", "st_uid", "st_nlink", "st_dev", "st_ino", "st_file_attributes")}
        # Windows lacks POSIX permission bits; simulate only that one Linux
        # attribute while exercising real directory traversal and deletion.
        if os.name == "nt" and path == self.root:
            values["st_mode"] = (values["st_mode"] & ~0o7777) | 0o700
        return SimpleNamespace(**{**values, **changes})

    def cleanup(self, **changes):
        return runtime.cleanup(**{**dict(runtime=self.root, pipeline_id=123, job_id=456, source_sha=SHA), **changes})

    def assert_preserved(self):
        self.assertTrue(self.root.is_dir())
        self.assertEqual(b"synthetic-private-payload", (self.root / "private.bin").read_bytes())
        self.assertEqual(b"preserve sibling", self.sibling.read_bytes())

    def test_success_removes_only_owned_tree_and_reads_only_public_marker(self):
        child = self.root / "nested"; child.mkdir()
        (child / "firmware.bin").write_bytes(b"synthetic-firmware")
        original_open = Path.open
        def public_marker_only(path, *args, **kwargs):
            self.assertEqual(self.root / ".owner", path)
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", public_marker_only):
            self.assertTrue(self.cleanup()["removed"])
        self.assertFalse(self.root.exists())
        self.assertEqual(b"preserve sibling", self.sibling.read_bytes())

    def test_absent_is_idempotent_without_creating_directories(self):
        self.cleanup()
        with patch.object(runtime.shutil, "rmtree") as remove:
            self.assertFalse(self.cleanup()["removed"])
            remove.assert_not_called()
        self.assertFalse(self.root.exists())
        self.assertEqual({"unrelated.txt"}, {item.name for item in self.parent.iterdir()})

    def test_wrong_identity_or_path_never_deletes(self):
        changes = ({"pipeline_id": 124}, {"job_id": 457}, {"pipeline_id": 0},
                   {"job_id": True}, {"source_sha": "invalid"}, {"runtime": self.parent},
                   {"runtime": self.parent / "other"}, {"runtime": self.root / ".." / self.root.name})
        for change in changes:
            with self.subTest(change=change), patch.object(runtime.shutil, "rmtree") as remove:
                with self.assertRaises(ValueError):
                    self.cleanup(**change)
                remove.assert_not_called()
                self.assert_preserved()

    def test_wrong_missing_or_oversized_marker_never_deletes(self):
        marker = self.root / ".owner"
        for payload in (b"wrong\n", f"123:456:{'b'*40}\n".encode(), f"123:456:{SHA}\nextra".encode()):
            with self.subTest(payload_length=len(payload)):
                marker.write_bytes(payload)
                with self.assertRaises(ValueError):
                    self.cleanup()
                self.assert_preserved()
        marker.unlink()
        with self.assertRaises(FileNotFoundError):
            self.cleanup()
        self.assert_preserved()

    def test_wrong_root_mode_root_owner_or_descendant_owner_never_deletes(self):
        cases = ((self.root, {"st_mode": stat.S_IFDIR | 0o755}),
                 (self.root, {"st_uid": self.uid + 1}),
                 (self.root / "private.bin", {"st_uid": self.uid + 1}))
        for path, changes in cases:
            with self.subTest(path=path.name, changes=changes):
                def altered(candidate):
                    return self.metadata(candidate, **changes) if candidate == path else self.metadata(candidate)
                with patch.object(runtime, "_metadata", side_effect=altered), \
                        patch.object(runtime.shutil, "rmtree") as remove:
                    with self.assertRaises(ValueError):
                        self.cleanup()
                    remove.assert_not_called()
                self.assert_preserved()

    def test_linked_root_ancestor_descendant_and_marker_never_delete(self):
        for path in (self.root, self.parent, self.root / "private.bin", self.root / ".owner"):
            with self.subTest(path=path.name):
                def linked(candidate):
                    return self.metadata(candidate, st_mode=stat.S_IFLNK | 0o777) if candidate == path else self.metadata(candidate)
                with patch.object(runtime, "_metadata", side_effect=linked), \
                        patch.object(runtime.shutil, "rmtree") as remove:
                    with self.assertRaisesRegex(ValueError, "Linked"):
                        self.cleanup()
                    remove.assert_not_called()
                self.assert_preserved()

    def test_windows_cli_rejects_and_linux_stdout_contains_only_public_identity(self):
        arguments = ["--runtime", str(self.root), "--pipeline-id", "123", "--job-id", "456", "--source-sha", SHA]
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(runtime.sys, "platform", "win32"), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(1, runtime.main(arguments))
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("Fleet runtime cleanup refused\n", stderr.getvalue())
        self.assert_preserved()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(0, runtime.main(arguments))
        result = json.loads(stdout.getvalue())
        self.assertEqual({"runtime", "pipeline_id", "job_id", "source_sha", "removed"}, set(result))
        self.assertEqual(str(self.root), result["runtime"])
        self.assertNotIn("synthetic-private-payload", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

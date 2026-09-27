from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.idt import idt_bundle


class IdtBundleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        files = {"bin/devicetester": b"official binary", "tests/FRQ_2.5.0/suite/group.json": b"official test definition"}
        for relative, content in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        digest = hashlib.sha256(b"official ZIP").hexdigest()
        self.manifest = {
            "common_files": {relative: hashlib.sha256(content).hexdigest() for relative, content in files.items()},
            "hosts": {host: {"archive_sha256": digest, "files": {}} for host in ("windows", "linux")},
        }
        self.reader = patch.object(idt_bundle, "_read_manifest", return_value=self.manifest)
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def test_clean_manual_cache_needs_no_local_receipt_and_ignores_mutable_files(self):
        for relative in ("configs/config.json", "logs/console.log", "results/FRQ_Report.xml", "certificates/private.pem"):
            path = self.root / relative
            path.parent.mkdir(parents=True)
            path.write_text("mutable runtime data", encoding="utf-8")
        self.assertFalse((self.root / "bundle-metadata.json").exists())
        idt_bundle.verify_install(self.root, "linux")

    def test_modified_executable_and_test_definition_each_fail(self):
        for relative in self.manifest["common_files"]:
            path = self.root / relative
            original = path.read_bytes()
            path.write_bytes(b"changed")
            with self.subTest(relative=relative), self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                idt_bundle.verify_install(self.root, "linux")
            self.assertEqual(b"changed", path.read_bytes(), "Verifier must not repair files")
            path.write_bytes(original)

    def test_missing_or_extra_static_file_fails(self):
        path = self.root / "tests/FRQ_2.5.0/suite/group.json"
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing=1"):
            idt_bundle.verify_install(self.root, "linux")
        path.write_bytes(original)
        (self.root / "tests/FRQ_2.5.0/suite/unexpected.json").write_text("extra")
        with self.assertRaisesRegex(RuntimeError, "extra=1"):
            idt_bundle.verify_install(self.root, "linux")

    def test_archive_digest_is_bound_to_selected_host(self):
        linux = self.manifest["hosts"]["linux"]["archive_sha256"]
        self.manifest["hosts"]["windows"]["archive_sha256"] = "b" * 64
        idt_bundle.verify_archive_digest("linux", linux)
        with self.assertRaises(RuntimeError):
            idt_bundle.verify_archive_digest("windows", linux)
        with self.assertRaises(ValueError):
            idt_bundle.verify_archive_digest("arm64", linux)

    def test_committed_manifest_pins_official_archive_and_consumed_definitions(self):
        manifest = json.loads(idt_bundle.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("4.9.0", manifest["idt_version"])
        self.assertEqual("FRQ_2.5.0", manifest["suite"])
        self.assertEqual("d50c70f2a05e0407d7909ded75b83c805bcc5abe1d5c2e320c6172f2dd3b3e4e", manifest["hosts"]["windows"]["archive_sha256"])
        self.assertEqual("59fdf0314d8196516e02806c972d13857c7d957516a22853c04f99855185cf84", manifest["hosts"]["linux"]["archive_sha256"])
        for host, bundle in manifest["hosts"].items():
            files = {**manifest["common_files"], **bundle["files"]}
            self.assertEqual(74, len(files), host)
            for relative in ("tests/FRQ_2.5.0/suite/suite.json", "tests/FRQ_2.5.0/suite/full_cloud_iot/group.json",
                             "tests/FRQ_2.5.0/suite/full_pkcs11_core/group.json", "tests/FRQ_2.5.0/suite/ota_dataplane_mqtt/group.json"):
                self.assertIn(relative, files)


if __name__ == "__main__":
    unittest.main()

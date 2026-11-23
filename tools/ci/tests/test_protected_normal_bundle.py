"""Synthetic encrypted normal-bundle transport; no hardware, builds or network."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from tools import normal_boot
from tools.ci import protected_normal_bundle as bundle
from tools.ci.tests.test_idt_public_signer_provision import Fixture, ROOT, SOURCE_SHA

SECRET_ENV = "SYNTHETIC_PROTECTED_NORMAL_BUNDLE_SECRET"
SECRET = b"synthetic-test-only-secret"
PIPELINE = 12345
TARGET = "rx671-wifi"


class ProtectedNormalBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        environment = patch.dict(os.environ, {SECRET_ENV: SECRET.decode()})
        environment.start()
        self.addCleanup(environment.stop)
        self.identity = dict(target=TARGET, source_sha=SOURCE_SHA, pipeline_id=PIPELINE, secret_env=SECRET_ENV)
        self.fixture = Fixture(self.root / "inputs", TARGET)
        inputs = {name: self.fixture.files[name] for name in normal_boot.FILES
                  if name not in {"normal_app.rsu", "public_signer_bootloader_config.h", "public_signer_target.h"}}
        inputs["normal_app.rsu"] = self.fixture.files["idt_transport.rsu"]
        self.source = self.root / "normal"
        with patch("tools.idt.prepare_public_signer._source_state", return_value=SOURCE_SHA):
            normal_boot.prepare(ROOT, TARGET, self.source, inputs)
        self.artifact, self.output = self.root / "artifact", self.root / "restored"
        self.sibling = self.root / "unrelated.txt"
        self.sibling.write_bytes(b"preserve unrelated sibling")

    def pack(self):
        return bundle.pack(self.source, self.artifact, **self.identity)

    def unpack(self, **overrides):
        return bundle.unpack(self.artifact, self.output, **{**self.identity, **overrides})

    def hashes(self, root):
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()}

    def assert_clean_failure(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(b"preserve unrelated sibling", self.sibling.read_bytes())
        self.assertFalse(list(self.root.glob(".protected-normal-*")))
        normal_boot.validate(self.source, self.fixture.target, SOURCE_SHA)

    def authenticate_zip(self, entries):
        """Attacker knows only this test's synthetic key; exercise ZIP defenses."""
        plaintext = self.root / "synthetic.zip"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(plaintext, "w") as archive:
                    for name, payload in entries:
                        archive.writestr(name, payload)
            manifest_path = self.artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["ciphertext_sha256"] = bundle.protection.encrypt(
                plaintext, self.artifact / "bundle.zip.enc", SECRET,
                bundle._identity(TARGET, SOURCE_SHA, PIPELINE)["context"])
            manifest_path.write_text(json.dumps(manifest))
        finally:
            plaintext.unlink(missing_ok=True)

    def entries(self):
        return [(name, (self.source / name).read_bytes()) for name in sorted(bundle.FILES)]

    def test_roundtrip_preserves_every_byte_signature_and_private_permissions(self):
        packed = self.pack()
        self.assertEqual(bundle.ARTIFACT_FILES, {path.name for path in self.artifact.iterdir()})
        self.assertEqual(bundle.protection.MAGIC, (self.artifact / "bundle.zip.enc").read_bytes()[:len(bundle.protection.MAGIC)])
        restored = self.unpack()
        self.assertEqual(self.hashes(self.source), self.hashes(self.output))
        normal_boot.validate(self.output, self.fixture.target, SOURCE_SHA)
        self.assertEqual(str(self.artifact), packed["artifact"])
        self.assertEqual(str(self.output), restored["bundle"])
        self.assertFalse(list(self.root.glob(".protected-normal-*")))
        if os.name != "nt":
            self.assertEqual(0o700, stat.S_IMODE(self.output.stat().st_mode))
            for path in self.output.iterdir():
                self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))

    def test_secret_file_variable_uses_synthetic_file_contents(self):
        secret_file = self.root / "synthetic-secret.txt"
        secret_file.write_bytes(SECRET)
        with patch.dict(os.environ, {SECRET_ENV: str(secret_file)}):
            self.pack()
        self.unpack()  # Literal contents produce the same derived key.
        self.assertEqual(self.hashes(self.source), self.hashes(self.output))

    def test_pack_plaintext_workspace_uses_private_input_parent_not_artifact_parent(self):
        private_parent = self.root / "private-runtime"
        private_parent.mkdir(mode=0o700)
        source = private_parent / "normal"
        source.mkdir(mode=0o700)
        for name in bundle.FILES:
            (source / name).write_bytes((self.source / name).read_bytes())
        artifact_parent = self.root / "artifact-collection"
        artifact_parent.mkdir()
        artifact = artifact_parent / "encrypted-bundle"
        allocated = []
        real_mkdtemp = bundle.tempfile.mkdtemp
        def record_workspace(*args, **kwargs):
            allocated.append((Path(kwargs["dir"]), Path(real_mkdtemp(*args, **kwargs))))
            self.assertEqual([], list(artifact_parent.iterdir()))
            return str(allocated[-1][1])
        with patch.object(bundle.tempfile, "mkdtemp", side_effect=record_workspace):
            bundle.pack(source, artifact, **self.identity)
        self.assertEqual(1, len(allocated))
        self.assertEqual(private_parent, allocated[0][0])
        self.assertEqual(private_parent, allocated[0][1].parent)
        self.assertFalse(allocated[0][1].is_relative_to(artifact_parent))
        self.assertFalse(allocated[0][1].exists())
        self.assertEqual({"encrypted-bundle"}, {path.name for path in artifact_parent.iterdir()})
        self.assertEqual(bundle.ARTIFACT_FILES, {path.name for path in artifact.iterdir()})

    def test_wrong_identity_and_manifest_fields_fail_before_decrypt(self):
        self.pack()
        for overrides in ({"source_sha": "b" * 40}, {"pipeline_id": PIPELINE + 1}, {"target": "rx65n-bg96"}):
            with self.subTest(overrides=overrides), patch.object(bundle.protection, "decrypt") as decrypt:
                with self.assertRaises(ValueError):
                    self.unpack(**overrides)
                decrypt.assert_not_called()
                self.assert_clean_failure()
        path = self.artifact / "manifest.json"
        original = json.loads(path.read_bytes())
        changes = ({"profile": "other"}, {"schema_version": True}, {"pipeline_id": True},
                   {"context": "arbitrary-context"}, {"source_sha": "b" * 40},
                   {"extra": "unexpected"}, {"ciphertext_sha256": "z" * 64})
        for change in changes:
            with self.subTest(change=change), patch.object(bundle.protection, "decrypt") as decrypt:
                path.write_text(json.dumps({**original, **change}))
                with self.assertRaises(ValueError):
                    self.unpack()
                decrypt.assert_not_called()
                self.assert_clean_failure()
        path.write_text(json.dumps(original)[:-1] + ',"profile":"duplicate"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.unpack()
        self.assert_clean_failure()

    def test_wrong_key_ciphertext_hash_and_authenticated_tamper_leave_no_output(self):
        self.pack()
        with patch.dict(os.environ, {SECRET_ENV: "different-synthetic-key"}):
            with self.assertRaisesRegex(ValueError, "authentication"):
                self.unpack()
        self.assert_clean_failure()
        cipher = self.artifact / "bundle.zip.enc"
        changed = bytearray(cipher.read_bytes()); changed[-1] ^= 1; cipher.write_bytes(changed)
        with patch.object(bundle.protection, "decrypt") as decrypt:
            with self.assertRaisesRegex(ValueError, "hash"):
                self.unpack()
            decrypt.assert_not_called()
        self.assert_clean_failure()
        manifest_path = self.artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["ciphertext_sha256"] = hashlib.sha256(changed).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "authentication"):
            self.unpack()
        self.assert_clean_failure()

    def test_authenticated_duplicate_traversal_symlink_extra_and_directory_rejected_before_output(self):
        self.pack()
        baseline = self.entries()
        linked = zipfile.ZipInfo(baseline[0][0]); linked.create_system = 3
        linked.external_attr = (stat.S_IFLNK | 0o777) << 16
        directory = zipfile.ZipInfo(baseline[0][0]); directory.create_system = 3
        directory.external_attr = (stat.S_IFDIR | 0o700) << 16
        attacks = (baseline + [baseline[0]], [("../escape", b"outside"), *baseline[1:]],
                   [(linked, b"../unrelated.txt"), *baseline[1:]],
                   baseline + [("extra", b"unexpected")], [(directory, b""), *baseline[1:]])
        for entries in attacks:
            with self.subTest(first=str(entries[0][0])):
                self.authenticate_zip(entries)
                with patch.object(bundle, "_output", side_effect=AssertionError("must reject before extraction")):
                    with self.assertRaises(ValueError):
                        self.unpack()
                self.assert_clean_failure()
                self.assertFalse((self.root / "escape").exists())

    def test_authenticated_bad_signature_and_zip_size_limits_clean_up_new_outputs(self):
        self.pack()
        entries = self.entries()
        malformed = [(name, payload[:-1] + bytes([payload[-1] ^ 1]) if name == "normal_app.rsu" else payload)
                     for name, payload in entries]
        self.authenticate_zip(malformed)
        with self.assertRaises((RuntimeError, ValueError)):
            self.unpack()
        self.assert_clean_failure()
        self.authenticate_zip(entries)
        with patch.object(bundle, "MAX_FILE", 512 * 1024), self.assertRaisesRegex(ValueError, "bounded"):
            self.unpack()
        self.assert_clean_failure()
        with patch.object(bundle, "MAX_TOTAL", 512 * 1024), self.assertRaisesRegex(ValueError, "total"):
            self.unpack()
        self.assert_clean_failure()

    def test_existing_output_and_input_extra_preserve_every_existing_byte(self):
        self.pack()
        hashes = self.hashes(self.artifact)
        with self.assertRaises(FileExistsError):
            self.pack()
        self.assertEqual(hashes, self.hashes(self.artifact))
        self.output.mkdir(); marker = self.output / "keep.txt"; marker.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.unpack()
        self.assertEqual(b"keep", marker.read_bytes())
        extra = self.source / "unexpected-private.pem"; extra.write_bytes(b"not-to-be-read")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("no unknown file reads")):
            with self.assertRaises(ValueError):
                bundle.pack(self.source, self.root / "other-artifact", **self.identity)
        self.assertEqual(b"not-to-be-read", extra.read_bytes())
        self.assertFalse((self.root / "other-artifact").exists())

    def test_invalid_pack_does_not_publish_and_pack_failure_removes_only_its_artifact(self):
        path = self.source / "normal_app.rsu"; original = path.read_bytes()
        changed = bytearray(original); changed[-8] ^= 1; path.write_bytes(changed)
        with self.assertRaises((RuntimeError, ValueError)):
            self.pack()
        self.assertFalse(self.artifact.exists())
        self.assertFalse(list(self.root.glob(".protected-normal-*")))
        path.write_bytes(original)
        real_encrypt = bundle.protection.encrypt
        def encrypt_then_fail(*args):
            real_encrypt(*args)
            raise RuntimeError("synthetic post-encrypt failure")
        with patch.object(bundle.protection, "encrypt", side_effect=encrypt_then_fail):
            with self.assertRaisesRegex(RuntimeError, "post-encrypt"):
                self.pack()
        self.assertFalse(self.artifact.exists())
        self.assert_clean_failure()

    def test_private_pem_is_rejected_before_bulk_snapshot_reads(self):
        path = self.source / "signer.pub.pem"
        path.write_bytes(b"-----BEGIN PRIVATE KEY-----\nSYNTHETIC-DO-NOT-READ-BODY\n")
        with patch.object(bundle, "_copy_bundle", side_effect=AssertionError("private PEM must not be copied")):
            with self.assertRaisesRegex(RuntimeError, "public PEM"):
                self.pack()
        self.assertFalse(self.artifact.exists())
        self.assertFalse(list(self.root.glob(".protected-normal-*")))

    def test_linked_ancestors_hardlinks_and_overlap_are_rejected(self):
        self.pack()
        with self.assertRaises(ValueError):
            bundle.pack(self.source, self.source / "nested", **self.identity)
        target = self.source / "signer.pub.pem"
        linked_file = self.root / "hardlink.pem"
        try:
            os.link(target, linked_file)
        except OSError:
            pass
        else:
            with self.assertRaisesRegex(ValueError, "unlinked"):
                bundle.pack(self.source, self.root / "hardlinked-artifact", **self.identity)
            linked_file.unlink()
        link = self.root / "linked-parent"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError:
            return  # Windows commonly withholds symlink creation privileges.
        with self.assertRaisesRegex(ValueError, "Linked"):
            bundle.pack(link / "normal", self.root / "linked-input-artifact", **self.identity)
        with self.assertRaisesRegex(ValueError, "Linked"):
            bundle.unpack(self.artifact, link / "restored", **self.identity)
        self.assert_clean_failure()

    def test_cli_stdout_is_only_public_json_and_errors_hide_payload_exceptions(self):
        arguments = ["pack", "--bundle", str(self.source), "--output", str(self.artifact),
                     "--target", TARGET, "--source-sha", SOURCE_SHA, "--pipeline-id", str(PIPELINE),
                     "--secret-env", SECRET_ENV]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(0, bundle.main(arguments))
        result = json.loads(stdout.getvalue())
        self.assertEqual(bundle.PROFILE, result["profile"])
        self.assertNotIn(SECRET.decode(), stdout.getvalue())
        self.assertNotIn("-----BEGIN", stdout.getvalue())
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(bundle, "pack", side_effect=RuntimeError("synthetic-sensitive-firmware")), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(1, bundle.main(arguments))
        self.assertEqual("", stdout.getvalue())
        self.assertNotIn("synthetic-sensitive-firmware", stderr.getvalue())
        self.assertEqual("Protected normal bundle operation failed\n", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

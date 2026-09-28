"""Local credential/payload contract tests; never invoke AWS or hardware."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
try:
    from . import ota_support
except ImportError:
    import ota_support


class OtaSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="idt-ota-unit-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source, self.inputs, self.runtime = root / "checkout", root / "run/inputs", root / "run/execution"
        self.runtime.mkdir(parents=True)
        (self.source / "sample_keys").mkdir(parents=True)
        self.key = ec.generate_private_key(ec.SECP256R1())
        private = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption())
        (self.source / "sample_keys/secp256r1.privatekey").write_bytes(private)
        public = self.key.public_key().public_bytes(serialization.Encoding.PEM,
                                                    serialization.PublicFormat.SubjectPublicKeyInfo)
        header = self.source / "Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/src/key/code_signer_public_key.h"
        header.parent.mkdir(parents=True)
        header.write_text("#define CODE_SIGNER_PUBLIC_KEY_PEM " + json.dumps(public.decode()) + "\n")
        self.config = ota_support.make_ota_config(self.inputs, self.source, str)
        self.environment = ota_support.ota_environment(self.inputs, str)
        self.environment.update(IDT_RUNTIME_DIR=str(self.runtime), IDT_SOURCE_PATH=str(self.source))
        self.env_patch = patch.dict(os.environ, self.environment)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_certificate_matches_bootloader_key_and_wrong_certificate_fails(self):
        cert = x509.load_pem_x509_certificate((self.inputs / ota_support.TRUSTED_CERT).read_bytes())
        self.assertEqual(cert.public_key().public_numbers(), self.key.public_key().public_numbers())
        with self.assertRaisesRegex(RuntimeError, "differ"):
            ota_support.load_signer(self.inputs / ota_support.SIGNING_KEY,
                                    self.inputs / ota_support.UNTRUSTED_CERT)

    def test_detached_der_signature_rejects_modified_payload(self):
        image, signature = self.runtime / "payload.bin", self.runtime / "payload.sig"
        image.write_bytes(b"IDT test payload\x00\r\n")
        subprocess.run([sys.executable, str(Path(ota_support.__file__).with_name("ota_sign.py")),
                        str(image), str(signature), "--key", self.environment["IDT_OTA_SIGNING_KEY_FILE"],
                        "--certificate", self.environment["IDT_OTA_SIGNER_CERT_FILE"]],
                       check=True, stdout=subprocess.DEVNULL)
        self.key.public_key().verify(signature.read_bytes(), image.read_bytes(), ec.ECDSA(hashes.SHA256()))
        with self.assertRaises(InvalidSignature):
            self.key.public_key().verify(signature.read_bytes(), image.read_bytes() + b"changed", ec.ECDSA(hashes.SHA256()))

    def test_signing_outside_runtime_is_rejected(self):
        image = self.source / "outside.bin"
        image.write_bytes(b"outside")
        result = subprocess.run([sys.executable, str(Path(ota_support.__file__).with_name("ota_sign.py")),
                                 str(image), str(self.runtime / "signature"), "--key", self.environment["IDT_OTA_SIGNING_KEY_FILE"],
                                 "--certificate", self.environment["IDT_OTA_SIGNER_CERT_FILE"]],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "signature").exists())

    def test_stale_mot_rejected_before_payload_tool(self):
        source = self.runtime / "abc-123456"
        (source / "Test/include").mkdir(parents=True)
        (source / "Test/include/test_param_config.h").write_text("#define OTA_APP_VERSION_MAJOR 0\n#define OTA_APP_VERSION_MINOR 9\n#define OTA_APP_VERSION_BUILD 3\n")
        output = source / "artifacts/idt/build_transport"
        output.mkdir(parents=True)
        (output / "rx72n_idt_transport.mot").write_text("modified image")
        (output / "build_manifest.json").write_text(json.dumps({"outputs": {"mot": {"sha256": "0" * 64}}}))
        with patch.object(ota_support.subprocess, "run") as execute:
            with self.assertRaisesRegex(RuntimeError, "MOT differs"):
                ota_support.build_payload(source)
            execute.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "runtime ledger uses Linux flock; execute this case in WSL")
    def test_ledger_preserves_each_variant_without_credentials(self):
        source = self.runtime / "abc-123456"
        (source / "Test/include").mkdir(parents=True)
        parameter = source / "Test/include/test_param_config.h"
        output = source / "artifacts/idt/build_transport"
        output.mkdir(parents=True)
        mot = output / "rx72n_idt_transport.mot"
        mot.write_bytes(b"synthetic MOT fixture")
        def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
        for version in (3, 4):
            parameter.write_text(f"#define OTA_APP_VERSION_MAJOR 0U\n#define OTA_APP_VERSION_MINOR 9U\n#define OTA_APP_VERSION_BUILD {version}U\n")
            image_id = f"{version:032x}"
            header = source / "Test/include/idt_ota_signer.h"
            header.write_text('#define IDT_OTA_IMAGE_ID "' + image_id + '"\n')
            (output / "build_manifest.json").write_text(json.dumps({
                "outputs": {"mot": {"sha256": sha(mot)}}, "parameter_config_sha256": sha(parameter),
                "image_id": image_id, "signer_header_sha256": sha(header),
                "application_version": {"MAJOR": 0, "MINOR": 9, "BUILD": version}}))
            def generate(command, **_kwargs):
                Path(command[command.index("--output") + 1]).write_bytes(bytes([version]))
            with patch.object(ota_support.subprocess, "run", side_effect=generate), contextlib.redirect_stdout(io.StringIO()):
                ota_support.build_payload(source)
        raw = (self.runtime / "ota-build-ledger.jsonl").read_text()
        records = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual([item["ota_version"] for item in records], ["0.9.3", "0.9.4"])
        self.assertEqual(records[0]["payload_sha256"], hashlib.sha256(b"\x03").hexdigest())
        self.assertNotEqual(records[0]["payload_sha256"], records[1]["payload_sha256"])
        self.assertNotEqual(records[0]["image_id"], records[1]["image_id"])
        self.assertNotIn("PRIVATE KEY", raw)
        self.assertNotIn("CERTIFICATE", raw)

    def test_changed_image_identity_header_is_rejected_before_payload_tool(self):
        source = self.runtime / "abc-123456"
        (source / "Test/include").mkdir(parents=True)
        parameter = source / "Test/include/test_param_config.h"
        parameter.write_text("#define OTA_APP_VERSION_MAJOR 1\n#define OTA_APP_VERSION_MINOR 9\n#define OTA_APP_VERSION_BUILD 2\n")
        header = source / "Test/include/idt_ota_signer.h"
        header.write_text('#define IDT_OTA_IMAGE_ID "' + "a" * 32 + '"\n')
        header_hash = hashlib.sha256(header.read_bytes()).hexdigest()
        output = source / "artifacts/idt/build_transport"
        output.mkdir(parents=True)
        mot = output / "rx72n_idt_transport.mot"
        mot.write_bytes(b"synthetic compiled image")
        (output / "build_manifest.json").write_text(json.dumps({
            "outputs": {"mot": {"sha256": hashlib.sha256(mot.read_bytes()).hexdigest()}},
            "parameter_config_sha256": hashlib.sha256(parameter.read_bytes()).hexdigest(),
            "application_version": {"MAJOR": 1, "MINOR": 9, "BUILD": 2},
            "image_id": "a" * 32, "signer_header_sha256": header_hash}))
        header.write_text('#define IDT_OTA_IMAGE_ID "' + "b" * 32 + '"\n')
        with patch.object(ota_support.subprocess, "run") as execute:
            with self.assertRaisesRegex(RuntimeError, "identity header changed"):
                ota_support.build_payload(source)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()

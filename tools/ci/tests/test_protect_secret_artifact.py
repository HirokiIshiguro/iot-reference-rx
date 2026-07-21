from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.ci import protect_secret_artifact


class ProtectSecretArtifactTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        plaintext = b"S-record with a credential\nS9030000FC\n"
        secret = b"test-only-high-entropy-secret"

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "firmware.mot"
            encrypted = root / "firmware.mot.enc"
            restored = root / "restored.mot"
            source.write_bytes(plaintext)

            protect_secret_artifact.encrypt(source, encrypted, secret, "pipeline-123")
            protect_secret_artifact.decrypt(encrypted, restored, secret, "pipeline-123")

            self.assertNotEqual(encrypted.read_bytes(), plaintext)
            self.assertEqual(restored.read_bytes(), plaintext)

    def test_wrong_secret_does_not_write_plaintext(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "firmware.mot"
            encrypted = root / "firmware.mot.enc"
            restored = root / "restored.mot"
            source.write_bytes(b"secret firmware")
            protect_secret_artifact.encrypt(source, encrypted, b"correct", "fleet")

            with self.assertRaises(ValueError):
                protect_secret_artifact.decrypt(encrypted, restored, b"wrong", "fleet")

            self.assertFalse(restored.exists())

    def test_empty_environment_secret_is_rejected(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "required secret environment variable"):
                protect_secret_artifact._secret_from_environment("MISSING_SECRET")

    def test_file_type_environment_secret_uses_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            secret_file = Path(temporary_directory) / "claim-private-key.pem"
            secret_file.write_bytes(b"private-key-contents")
            with mock.patch.dict(os.environ, {"CLAIM_KEY_FILE": str(secret_file)}, clear=True):
                secret = protect_secret_artifact._secret_from_environment("CLAIM_KEY_FILE")

        self.assertEqual(secret, b"private-key-contents")


if __name__ == "__main__":
    unittest.main()

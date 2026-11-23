"""Public metadata boundaries only; no firmware, keys, network or hardware."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import normal_boot

PARENT = "a" * 40
PRODUCER = "b" * 40
APP_HASH = "c" * 64


def provenance(role="benchmark"):
    return {"schema_version": 1, "project_id": 190, "pipeline_id": 100, "job_id": 200,
            "source_sha": PRODUCER, "application_source_sha": PRODUCER if role == "benchmark" else PARENT,
            "profile": "tsip-0rtt" if role == "benchmark" else "normal",
            "role": role, "application_sha256": APP_HASH}


class BenchmarkProvenanceTests(unittest.TestCase):
    def test_benchmark_and_restore_have_distinct_application_sources(self):
        manifest = {"source_sha": PARENT, "files": {"normal_app.rsu": APP_HASH}}
        for role in ("benchmark", "normal-restore"):
            value = provenance(role)
            self.assertEqual(value, normal_boot.validate_benchmark_provenance(value, manifest))
            with self.assertRaisesRegex(RuntimeError, "source/role"):
                normal_boot.validate_benchmark_provenance(
                    value | {"application_source_sha": PARENT if role == "benchmark" else PRODUCER}, manifest)

    def test_rejects_untyped_or_unbound_public_claims(self):
        manifest = {"source_sha": PARENT, "files": {"normal_app.rsu": APP_HASH}}
        changes = [{"schema_version": True}, {"schema_version": 2}, {"project_id": True},
                   {"pipeline_id": 0}, {"job_id": "200"}, {"source_sha": "b" * 39},
                   {"application_source_sha": "B" * 40}, {"profile": "not/a/profile"},
                   {"profile": ""}, {"role": "other"}, {"application_sha256": "d" * 64},
                   {"unexpected_field": "public-fixture"}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                normal_boot.validate_benchmark_provenance(provenance() | change, manifest)
        missing = provenance()
        del missing["job_id"]
        with self.assertRaises(RuntimeError):
            normal_boot.validate_benchmark_provenance(missing, manifest)

    def test_prepare_default_and_optional_metadata_then_validate_expected_producer(self):
        # Stub the existing cryptographic/file validators: this test exercises only
        # the added metadata path, while the existing normal-boot suite tests signatures.
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            target = {"id": "public-fixture-target", "bootloader_project": "boot"}
            inputs = {name: root / name for name in normal_boot.FILES
                      if name not in {"public_signer_bootloader_config.h", "public_signer_target.h"}}
            stack.enter_context(patch("tools.idt.prepare_public_signer._source_state", return_value=PARENT))
            stack.enter_context(patch.object(normal_boot, "get_target", return_value=target))
            stack.enter_context(patch.object(normal_boot, "target_fingerprint", return_value="fingerprint"))
            stack.enter_context(patch.object(normal_boot.trust, "chip_config", return_value=root / "public-target.h"))
            stack.enter_context(patch.object(normal_boot.trust, "validate_boot_trust",
                                             return_value={"public_signer_spki_sha256": "spki"}))
            stack.enter_context(patch.object(normal_boot.trust, "policy_hashes", return_value={"public": "policy"}))
            stack.enter_context(patch.object(normal_boot, "signed_application", return_value={"code_flash_only": True}))
            stack.enter_context(patch.object(normal_boot, "file_hash", return_value=APP_HASH))
            stack.enter_context(patch.object(normal_boot.trust, "_ordinary", side_effect=Path))
            stack.enter_context(patch.object(normal_boot.shutil, "copyfile"))
            plain = normal_boot.prepare(source, target["id"], root / "plain", inputs)
            self.assertNotIn("benchmark_provenance", plain)
            self.assertEqual(plain, normal_boot.validate(root / "plain", target, PARENT))
            with self.assertRaisesRegex(RuntimeError, "missing"):
                normal_boot.validate(root / "plain", target, PARENT,
                                     expected_benchmark_provenance=provenance())
            value = provenance()
            bundle = root / "benchmark"
            prepared = normal_boot.prepare(source, target["id"], bundle, inputs,
                                          tls_backend="tsip", benchmark_provenance=value)
            self.assertEqual(value, prepared["benchmark_provenance"])
            value["job_id"] = 999  # No caller-owned mutable dictionary aliases the prepared manifest.
            self.assertEqual(200, prepared["benchmark_provenance"]["job_id"])
            self.assertEqual(prepared, normal_boot.validate(
                bundle, target, PARENT, expected_benchmark_provenance=provenance()))
            other_source = "d" * 40
            expected_mismatches = [provenance() | {"job_id": 201}, provenance() | {"profile": "tsip"},
                                   provenance("normal-restore"),
                                   provenance() | {"source_sha": other_source,
                                                   "application_source_sha": other_source}]
            for expected in expected_mismatches:
                with self.subTest(expected=expected), self.assertRaisesRegex(RuntimeError, "expected producer"):
                    normal_boot.validate(bundle, target, PARENT, expected_benchmark_provenance=expected)
            path = bundle / "normal_install_manifest.json"
            altered = json.loads(path.read_text(encoding="utf-8"))
            altered["benchmark_provenance"]["application_sha256"] = "d" * 64
            path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                normal_boot.validate(bundle, target, PARENT)
            invalid_output = root / "invalid"
            with self.assertRaises(RuntimeError):
                normal_boot.prepare(source, target["id"], invalid_output, inputs,
                                    benchmark_provenance=provenance() | {"job_id": False})
            self.assertFalse(invalid_output.exists())


if __name__ == "__main__":
    unittest.main()

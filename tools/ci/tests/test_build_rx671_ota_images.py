from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import run

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


SCRIPT = Path(__file__).resolve().parents[2] / "build_rx671_ota_images.py"
SPEC = importlib.util.spec_from_file_location("build_rx671_ota_images", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / builder.PROJECT_RELATIVE


class VersionTests(unittest.TestCase):
    def test_accepts_fwup_version_domain(self) -> None:
        version = builder.parse_version("255.254.65535")
        self.assertEqual((255, 254, 65535), (version.major, version.minor, version.build))
        self.assertEqual("255.254.65535", version.text)

    def test_rejects_ambiguous_or_out_of_range_versions(self) -> None:
        for value in ("1.02.3", "1.2", "1.2.-1", "256.0.0", "0.256.0", "0.0.65536"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                builder.parse_version(value)


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cproject = (PROJECT / ".cproject").read_text(encoding="utf-8")
        cls.bsp = (
            PROJECT / "src/smc_gen/r_config/r_bsp_config.h"
        ).read_text(encoding="utf-8")
        cls.reference = (
            PROJECT
            / "src/smc_gen/r_bsp/board/generic_rx671/r_bsp_config_reference.h"
        ).read_text(encoding="utf-8")
        cls.fwup = (
            PROJECT / "src/frtos_config/r_fwup_config.h"
        ).read_text(encoding="utf-8")

    def test_cproject_profile_is_dual_bank_and_keeps_every_payload_in_main(self) -> None:
        result = builder.make_ota_cproject(
            self.cproject, builder.parse_version("1.2.3")
        )
        self.assertIn('modes="bank.dual"', result)
        self.assertNotIn('modes="bank.single"', result)
        self.assertIn('value="PFRAM2=RPFRAM2"', result)
        self.assertIn(f'value="{builder.OTA_START_VALUE}"', result)
        self.assertNotIn(f'value="{builder.NORMAL_START_VALUE}"', result)
        self.assertIn('value="-define=APP_VERSION_MAJOR=1"', result)
        self.assertIn('value="-define=APP_VERSION_MINOR=2"', result)
        self.assertIn('value="-define=APP_VERSION_BUILD=3"', result)
        self.assertIn(
            'value="-define=RX671_OTA_RUNTIME_ENABLE=1"', result
        )
        self.assertIn(
            'value="-define=RX671_FREERTOS_HEAP_SIZE_KB=128"', result
        )
        self.assertIn(
            'value="-define=RX671_NETWORK_BUFFER_DESCRIPTORS=24"', result
        )
        self.assertIn(
            'value="-define=MQTT_AGENT_NETWORK_BUFFER_SIZE=8192"', result
        )
        self.assertIn(
            'value="-define=mqttFileDownloader_CONFIG_BLOCK_SIZE=4096"', result
        )
        self.assertIn(
            'value="-define=WHD_PORT_BUFFER_COUNT=8"', result
        )
        self.assertIn('value="-define=WHD_SCAN_ENABLE=0"', result)
        self.assertIn(
            'value="-define=WHD_JOIN_USE_SCAN_RESULT=0"', result
        )
        self.assertIn(
            'value="-define=CONFIG_USE_PERCEPIO_TRACE_RECORDER=0"', result
        )
        self.assertIn('value="-define=MBEDTLS_ERROR_C"', result)
        self.assertIn(builder.VERSION_MARKER_LINKER_OPTION, result)
        self.assertIn(
            "TYPE1YN_FW_BLOB,TYPE1YN_NVRAM_BLOB,TYPE1YN_CLM_BLOB/0FFF00300",
            result,
        )
        self.assertIn("EXCEPTVECT/0FFFBFF80,RESETVECT/0FFFBFFFC", result)

    def test_bsp_and_fwup_profile_values_are_exact(self) -> None:
        for label, source in (
            ("bsp", self.bsp),
            ("reference", self.reference),
        ):
            with self.subTest(label=label):
                result = builder.make_ota_bank_config(source, label)
                self.assertIn(
                    "#define BSP_CFG_CODE_FLASH_BANK_MODE    (0)", result
                )
                self.assertNotIn(
                    "#define BSP_CFG_CODE_FLASH_BANK_MODE    (1)", result
                )
        fwup = builder.make_ota_fwup_config(self.fwup)
        self.assertIn(
            "#define FWUP_CFG_AREA_SIZE                          (0x000C0000U)",
            fwup,
        )

    def test_profile_restores_files_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for relative in builder.PROFILE_PATHS:
                source = PROJECT / relative
                destination = project / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            before = {
                relative: (project / relative).read_bytes()
                for relative in builder.PROFILE_PATHS
            }
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                with builder.TemporaryOtaProfile(project) as profile:
                    profile.apply(builder.parse_version("1.2.3"))
                    self.assertIn(
                        b'bank.dual', (project / ".cproject").read_bytes()
                    )
                    raise RuntimeError("synthetic")
            after = {
                relative: (project / relative).read_bytes()
                for relative in builder.PROFILE_PATHS
            }
            self.assertEqual(before, after)

    def test_profile_fails_closed_if_project_drifted(self) -> None:
        with self.assertRaisesRegex(ValueError, "bank mode"):
            builder.make_ota_cproject(
                self.cproject.replace('modes="bank.single"', 'modes="bank.dual"'),
                builder.parse_version("1.2.3"),
            )
        with self.assertRaisesRegex(ValueError, "persistent APP_VERSION"):
            builder.make_ota_cproject(
                self.cproject.replace(
                    builder.DEFINE_ANCHOR,
                    builder.DEFINE_ANCHOR
                    + '\n<listOptionValue builtIn="false" '
                    'value="-define=APP_VERSION_MAJOR=1"/>',
                ),
                builder.parse_version("1.2.3"),
            )

    def test_provisioner_profile_stays_bank_single_and_restores(self) -> None:
        result = builder.make_provisioner_cproject(self.cproject)
        self.assertIn('modes="bank.single"', result)
        self.assertNotIn('modes="bank.dual"', result)
        self.assertIn(
            'value="-define=RX671_OTA_PROVISIONER_ENABLE=1"', result
        )

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = project / ".cproject"
            original = (PROJECT / ".cproject").read_bytes()
            target.write_bytes(original)
            with builder.TemporaryProvisionerProfile(project):
                self.assertIn(
                    b"RX671_OTA_PROVISIONER_ENABLE=1",
                    target.read_bytes(),
                )
            self.assertEqual(
                original,
                target.read_bytes(),
            )


class TransferArtifactTests(unittest.TestCase):
    def test_candidate_payload_is_rsu_after_header_and_der_signature_verifies(
        self,
    ) -> None:
        private_key = ec.generate_private_key(ec.SECP256R1())
        payload = b"descriptor-and-application" * 16
        source_der = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
        r, s = utils.decode_dss_signature(source_der)
        raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        header = bytearray(b"\xFF" * builder.RSU_HEADER_SIZE)
        header[
            builder.RSU_RAW_SIGNATURE_OFFSET :
            builder.RSU_RAW_SIGNATURE_OFFSET + builder.RSU_RAW_SIGNATURE_SIZE
        ] = raw

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rsu = root / "candidate.rsu"
            public_key = root / builder.SIGNER_PUBLIC_KEY_NAME
            output = root / builder.OTA_TRANSFER_PAYLOAD_NAME
            signature = root / builder.OTA_TRANSFER_SIGNATURE_NAME
            rsu.write_bytes(bytes(header) + payload)
            public_key.write_bytes(
                private_key.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

            builder._create_ota_transfer_artifacts(
                rsu_path=rsu,
                signer_public_key=public_key,
                payload_path=output,
                signature_path=signature,
            )

            self.assertEqual(payload, output.read_bytes())
            private_key.public_key().verify(
                signature.read_bytes(),
                output.read_bytes(),
                ec.ECDSA(hashes.SHA256()),
            )


class OutputSafetyTests(unittest.TestCase):
    def test_output_must_be_below_dedicated_repo_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            allowed = repo / "build/rx671-ota/candidate-1.2.3"
            builder._safe_recreate_output(allowed, repo)
            self.assertTrue(allowed.is_dir())
            with self.assertRaisesRegex(ValueError, "outside"):
                builder._safe_recreate_output(repo / "elsewhere", repo)
            with self.assertRaisesRegex(ValueError, "must be a child"):
                builder._safe_recreate_output(repo / "build/rx671-ota", repo)

    def test_output_root_is_fixed_to_the_ignored_ota_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            builder._validate_output_root(repo / "build/rx671-ota", repo)
            with self.assertRaisesRegex(ValueError, "dedicated repository path"):
                builder._validate_output_root(repo / "artifacts/rx671-ota", repo)

    @unittest.skipUnless(sys.platform == "win32", "Windows path contract")
    def test_workspace_must_stay_under_codex_workspace_root(self) -> None:
        builder._validate_workspace_root(
            Path("C:/ai/codex/ws/iot-reference-rx-rx671-ota-test")
        )
        with self.assertRaisesRegex(ValueError, "must stay below"):
            builder._validate_workspace_root(Path("C:/Temp/not-approved"))
        with self.assertRaisesRegex(ValueError, "must be a child"):
            builder._validate_workspace_root(Path("C:/ai/codex/ws"))

    @unittest.skipUnless(sys.platform == "win32", "Windows path contract")
    def test_transient_build_products_are_removed_from_project_and_workspace(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            dir="C:/ai/codex/ws",
            prefix="rx671-ota-cleanup-test-",
        ) as temporary:
            root = Path(temporary)
            project = root / "project"
            hardware_debug = project / "HardwareDebug"
            workspace = root / "workspace"
            hardware_debug.mkdir(parents=True)
            workspace.mkdir()
            (hardware_debug / "credential-bearing.abs").write_bytes(
                b"secret"
            )
            (workspace / "credential-bearing.mot").write_bytes(b"secret")

            builder._remove_transient_build_products(
                project,
                workspace,
            )

            self.assertFalse(hardware_debug.exists())
            self.assertFalse(workspace.exists())


class WifiCredentialIsolationTests(unittest.TestCase):
    def test_ota_build_environment_removes_wifi_credentials(self) -> None:
        source = {
            "PATH": "safe",
            "CI": "true",
            "RX671_EK_WIFI_SSID": "secret-ssid",
            "RX671_EK_WIFI_PASSPHRASE": "secret-passphrase",
            "RX671_EK_WIFI_PASSWORD": "legacy-secret",
        }
        result = builder.ota_build_environment(source)
        self.assertEqual("safe", result["PATH"])
        self.assertEqual("true", result["CI"])
        for variable in builder.WIFI_CREDENTIAL_ENVIRONMENT_VARIABLES:
            self.assertNotIn(variable, result)

    def test_ota_build_always_enables_littlefs_kvs_join(self) -> None:
        profile_source = inspect.getsource(builder.make_ota_cproject)
        build_source = inspect.getsource(builder._build_one)
        self.assertIn('-define=WHD_JOIN_ENABLE=1', profile_source)
        self.assertIn('-define=WHD_JOIN_USE_KVS=1', profile_source)
        self.assertIn('build_command.append("-SkipWifiConfig")', build_source)
        self.assertNotIn("UseLocalJoinConfig", build_source)
        self.assertNotIn("runtime_wifi", build_source)

    def test_local_join_header_is_restored_outside_ci(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            header = Path(temporary) / "whd_join_config_local.h"
            original = b"local developer configuration"
            header.write_bytes(original)
            with builder.TemporaryWifiCredentialIsolation(
                header, restore_existing=True
            ):
                self.assertFalse(header.exists())
                header.write_bytes(b"unexpected generated credentials")
            self.assertEqual(original, header.read_bytes())

    def test_local_join_header_is_removed_on_ci_exit_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            header = Path(temporary) / "whd_join_config_local.h"
            header.write_bytes(b"stale shared-runner credentials")
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                with builder.TemporaryWifiCredentialIsolation(
                    header, restore_existing=False
                ):
                    self.assertFalse(header.exists())
                    header.write_bytes(b"unexpected generated credentials")
                    raise RuntimeError("synthetic")
            self.assertFalse(header.exists())

    def test_ota_outputs_reject_null_terminated_wifi_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "image.abs"
            output.write_bytes(b"binary-prefixsecret-passphrase\0suffix")
            with self.assertRaisesRegex(
                RuntimeError,
                r"image\.abs \(RX671_EK_WIFI_PASSPHRASE\)",
            ):
                builder.assert_wifi_credentials_absent(
                    [output],
                    {"RX671_EK_WIFI_PASSPHRASE": "secret-passphrase"},
                )
            output.write_bytes(b"credential-free image")
            builder.assert_wifi_credentials_absent(
                [output],
                {"RX671_EK_WIFI_PASSPHRASE": "secret-passphrase"},
            )


class SubmoduleProvenanceTests(unittest.TestCase):
    def test_formal_input_submodules_match_gitlinks_and_are_clean(self) -> None:
        gitlinks = builder.validate_formal_input_submodules(ROOT)
        self.assertTrue(
            {
                path.as_posix()
                for path in builder.FORMAL_INPUT_SUBMODULES
            }.issubset(gitlinks)
        )
        self.assertTrue(
            all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in gitlinks.values())
        )

    def test_temporary_whd_patch_is_reversed_after_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            submodule = repo / builder.WHD_SUBMODULE_RELATIVE
            patch = repo / builder.WHD_PATCH_RELATIVE
            submodule.mkdir(parents=True)
            patch.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "init", "--quiet"], cwd=submodule, check=True)
            run(
                ["git", "config", "user.name", "OTA test"],
                cwd=submodule,
                check=True,
            )
            run(
                ["git", "config", "user.email", "ota-test@example.invalid"],
                cwd=submodule,
                check=True,
            )
            source = submodule / "source.txt"
            source.write_text("original\n", encoding="utf-8")
            run(["git", "add", "source.txt"], cwd=submodule, check=True)
            run(
                ["git", "commit", "--quiet", "-m", "fixture"],
                cwd=submodule,
                check=True,
            )
            patch.write_bytes(
                b"diff --git a/source.txt b/source.txt\n"
                b"--- a/source.txt\n"
                b"+++ b/source.txt\n"
                b"@@ -1 +1 @@\n"
                b"-original\n"
                b"+patched\n"
            )
            with builder.TemporaryWhdPatchIsolation(repo):
                run(
                    [
                        "git",
                        "apply",
                        "--ignore-space-change",
                        "--ignore-whitespace",
                        str(patch),
                    ],
                    cwd=submodule,
                    check=True,
                )
                self.assertEqual(
                    "patched\n", source.read_text(encoding="utf-8")
                )
            self.assertEqual(
                "original\n", source.read_text(encoding="utf-8")
            )
            self.assertEqual(
                "",
                run(
                    [
                        "git",
                        "status",
                        "--porcelain=v1",
                        "--untracked-files=all",
                    ],
                    cwd=submodule,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout,
            )


class DirtyAnalysisTests(unittest.TestCase):
    def test_dirty_manifest_is_not_marked_formal(self) -> None:
        source = inspect.getsource(builder._create_manifest)
        self.assertIn('"formal": not dirty', source)

    def test_allows_only_dirty_provenance_and_its_dependent_unknowns(self) -> None:
        report = {
            "gates": [
                {"name": "dual_bank_mode", "status": "PASS", "detail": "ok"},
                {
                    "name": "artifact_provenance",
                    "status": "FAIL",
                    "detail": "dirty=falseではない",
                },
                {
                    "name": "whd_blob_sizes",
                    "status": "UNKNOWN",
                    "detail": "provenance",
                },
                {
                    "name": "map_image_single_area",
                    "status": "UNKNOWN",
                    "detail": "provenance",
                },
                {
                    "name": "mot_image_single_area",
                    "status": "UNKNOWN",
                    "detail": "provenance",
                },
            ]
        }
        self.assertTrue(builder._dirty_analysis_is_structurally_safe(report))

    def test_rejects_any_structural_failure(self) -> None:
        report = {
            "gates": [
                {
                    "name": "artifact_provenance",
                    "status": "FAIL",
                    "detail": "dirty=falseではない",
                },
                {
                    "name": "dual_bank_mode",
                    "status": "FAIL",
                    "detail": "linear",
                },
            ]
        }
        self.assertFalse(builder._dirty_analysis_is_structurally_safe(report))


class AnalysisEncodingTests(unittest.TestCase):
    def test_analyzer_subprocess_forces_utf8_for_machine_readable_report(self) -> None:
        source = inspect.getsource(builder._build_one)
        self.assertIn(
            'analysis_environment["PYTHONIOENCODING"] = "utf-8"',
            source,
        )
        self.assertIn('encoding="utf-8"', source)
        self.assertIn('errors="strict"', source)
        self.assertIn("env=analysis_environment", source)


if __name__ == "__main__":
    unittest.main()

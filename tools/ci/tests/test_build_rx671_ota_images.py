from __future__ import annotations

import importlib.util
import inspect
import sys
import tempfile
import unittest
from pathlib import Path


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


class DirtyAnalysisTests(unittest.TestCase):
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

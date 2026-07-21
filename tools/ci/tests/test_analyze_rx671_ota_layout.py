import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "analyze_rx671_ota_layout.py"
SPEC = importlib.util.spec_from_file_location("analyze_rx671_ota_layout", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
layout = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = layout
SPEC.loader.exec_module(layout)


def _s3_record(address: int, data: bytes) -> str:
    body = address.to_bytes(4, "big") + data
    count = len(body) + 1
    checksum = (~(count + sum(body))) & 0xFF
    return "S3" + bytes([count]).hex().upper() + body.hex().upper() + f"{checksum:02X}"


class ParseTests(unittest.TestCase):
    def test_parse_start_anchors(self):
        anchors = layout._parse_start_anchors(
            "SU,SI/04,PResetPRG,C,P/0FFF00300,EXCEPTVECT/0FFFFFF80"
        )
        self.assertEqual(0x04, anchors["SU"])
        self.assertEqual(0x04, anchors["SI"])
        self.assertEqual(0xFFF00300, anchors["PResetPRG"])
        self.assertEqual(0xFFF00300, anchors["P"])
        self.assertEqual(0xFFFFFF80, anchors["EXCEPTVECT"])

    def test_parse_ccrx_map_sections(self):
        content = """Renesas Optimizing Linker
*** Mapping List ***
SECTION                            START      END         SIZE   ALIGN
P
                                  fff00100  fff0010f        10   1
TYPE1YN_FW_BLOB
                                  fff10000  fff10002         3   4
*** Symbol List ***
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.map"
            path.write_text(content, encoding="utf-8")
            sections = layout._parse_map_sections(path)
        self.assertEqual(layout.Section("P", 0xFFF00100, 0x10), sections["P"])
        self.assertEqual(3, sections["TYPE1YN_FW_BLOB"].size)

    def test_parse_srecord_ranges_and_validate_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mot"
            path.write_text(_s3_record(0xFFF00000, b"abc") + "\n", encoding="ascii")
            self.assertEqual([(0xFFF00000, 0xFFF00003)], layout._parse_srecord_ranges(path))

            path.write_text("S308FFF0000061626300\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "checksum"):
                layout._parse_srecord_ranges(path)


class GateTests(unittest.TestCase):
    def test_current_source_detects_confirmed_collisions_and_unknown_artifacts(self):
        repo_root = Path(__file__).resolve().parents[3]
        project_dir = repo_root / "Projects/aws_wifi_rx671_ek/e2studio_ccrx"
        with tempfile.TemporaryDirectory() as empty_build:
            gates = layout.analyze(project_dir, Path(empty_build))
        by_name = {gate.name: gate for gate in gates}

        self.assertEqual("UNKNOWN", by_name["bootloader_layout"].status)
        self.assertEqual("PASS", by_name["rom_capacity"].status)
        self.assertEqual("PASS", by_name["fwup_data_flash_geometry"].status)
        self.assertEqual("PASS", by_name["littlefs_data_flash_geometry"].status)
        self.assertEqual("FAIL", by_name["data_flash_non_overlap"].status)
        self.assertEqual("PASS", by_name["fwup_partition"].status)
        self.assertEqual("FAIL", by_name["dual_bank_mode"].status)
        self.assertEqual("FAIL", by_name["application_in_main_area"].status)
        self.assertEqual("FAIL", by_name["static_image_single_area"].status)
        self.assertEqual("FAIL", by_name["whd_resources_follow_application"].status)
        self.assertEqual("FAIL", by_name["sdio_resource_addressing"].status)
        self.assertEqual("FAIL", by_name["fwup_control_sections"].status)
        self.assertEqual("UNKNOWN", by_name["artifact_provenance"].status)
        self.assertEqual("UNKNOWN", by_name["whd_blob_sizes"].status)
        self.assertEqual("UNKNOWN", by_name["map_image_single_area"].status)
        self.assertEqual("UNKNOWN", by_name["mot_image_single_area"].status)

    def test_unknown_is_fail_safe_exit(self):
        self.assertEqual(0, layout.exit_code([layout.Gate("a", "PASS", "")]))
        self.assertEqual(2, layout.exit_code([layout.Gate("a", "UNKNOWN", "")]))
        self.assertEqual(
            1,
            layout.exit_code(
                [layout.Gate("a", "UNKNOWN", ""), layout.Gate("b", "FAIL", "")]
            ),
        )

    def test_fwup_geometry_rejects_equal_total_with_wrong_fit_blocks(self):
        gate = layout._fwup_data_flash_geometry_gate(
            bsp_size=8192,
            fwup_start=0x00100000,
            fwup_block_size=128,
            fwup_block_count=64,
            fit_start=0x00100000,
            fit_block_size=64,
            fit_block_count=128,
        )
        self.assertEqual("FAIL", gate.status)

    def test_data_flash_overlap_is_explicit_failure(self):
        gate = layout._data_flash_non_overlap_gate(
            data_flash_start=0x00100000,
            data_flash_size=8192,
            littlefs_start=0x00100000,
            littlefs_block_size=128,
            littlefs_block_count=64,
        )
        self.assertEqual("FAIL", gate.status)
        self.assertIn("0x00100000-0x00101FFF", gate.detail)

    def test_partial_littlefs_is_unknown_until_real_consumers_are_measured(self):
        gate = layout._data_flash_non_overlap_gate(
            data_flash_start=0x00100000,
            data_flash_size=8192,
            littlefs_start=0x00100800,
            littlefs_block_size=128,
            littlefs_block_count=32,
        )
        self.assertEqual("UNKNOWN", gate.status)
        self.assertIn("実測rangeが未確定", gate.detail)

    def test_measured_data_flash_consumers_must_not_overlap(self):
        common = {
            "data_flash_start": 0x00100000,
            "data_flash_size": 8192,
            "littlefs_start": 0x00100800,
            "littlefs_block_size": 128,
            "littlefs_block_count": 32,
            "consumer_layout_complete": True,
        }
        passing = layout._data_flash_non_overlap_gate(
            **common,
            consumer_ranges=(
                layout.Region("control", 0x00100000, 0x100),
                layout.Region("mirror", 0x00100100, 0x100),
                layout.Region("bootloader-key", 0x00100200, 0x100),
            ),
        )
        overlapping = layout._data_flash_non_overlap_gate(
            **common,
            consumer_ranges=(layout.Region("control", 0x00100800, 0x100),),
        )
        self.assertEqual("PASS", passing.status)
        self.assertEqual("FAIL", overlapping.status)
        self.assertIn("LittleFSとcontrolが重複", overlapping.detail)

    def test_sdio_numeric_alias_does_not_false_pass(self):
        sdio_text = """
extern const unsigned char g_type1yn_firmware_bin[];
extern const unsigned char g_type1yn_nvram_bin[];
#define LEGACY_FW_ADDRESS 0xFFF00000UL
#define LEGACY_NVRAM_ADDRESS 0xFFF80000UL
const unsigned char * firmware = (const unsigned char *) LEGACY_FW_ADDRESS;
const unsigned char * nvram = (const unsigned char *) LEGACY_NVRAM_ADDRESS;
"""
        provider_text = """
const unsigned char * a = g_type1yn_firmware_bin;
const unsigned char * b = g_type1yn_nvram_bin;
const unsigned char * c = g_type1yn_clm_blob;
"""
        gate = layout._sdio_resource_addressing_gate(sdio_text, provider_text)
        self.assertEqual("FAIL", gate.status)
        self.assertIn("linker symbol参照なし", gate.detail)
        self.assertIn("code flash固定値あり", gate.detail)

    def test_sdio_linker_symbol_consumers_pass(self):
        sdio_text = """
const unsigned char * firmware = g_type1yn_firmware_bin;
const unsigned char * nvram = g_type1yn_nvram_bin;
"""
        provider_text = """
const unsigned char * a = g_type1yn_firmware_bin;
const unsigned char * b = g_type1yn_nvram_bin;
const unsigned char * c = g_type1yn_clm_blob;
"""
        self.assertEqual(
            "PASS",
            layout._sdio_resource_addressing_gate(sdio_text, provider_text).status,
        )

    def test_missing_one_whd_anchor_is_failure(self):
        anchors = {
            "P": 0xFFF00000,
            "TYPE1YN_FW_BLOB": 0xFFF40000,
            "TYPE1YN_NVRAM_BLOB": 0xFFF80000,
        }
        gate = layout._whd_resources_follow_application_gate(
            anchors,
            [layout.Region("main", 0xFFF00000, 0x00100000)],
            anchors["P"],
        )
        self.assertEqual("FAIL", gate.status)
        self.assertIn("TYPE1YN_CLM_BLOB", gate.detail)

    def test_artifact_provenance_requires_manifest_and_all_hashes(self):
        source_sha = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            project_dir = repo_root / "Projects/aws_wifi_rx671_ek/e2studio_ccrx"
            build_dir = project_dir / "HardwareDebug"
            build_dir.mkdir(parents=True)
            for relative in layout.PROVENANCE_CONFIG_PATHS:
                path = project_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative, encoding="utf-8")
            map_path = build_dir / "aws_wifi_rx671_ek.map"
            mot_path = build_dir / "aws_wifi_rx671_ek.mot"
            map_path.write_text("map", encoding="utf-8")
            mot_path.write_text("mot", encoding="utf-8")
            blob_paths = []
            for name in ("43439A0.bin", "nvram_1yn.bin", "43439A0.clm_blob"):
                path = repo_root / "Projects/aws_wifi_rx671_ek/external/type1yn-blobs/staging" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode("ascii"))
                blob_paths.append(path)

            missing = layout._artifact_provenance_gate(
                repo_root=repo_root,
                project_dir=project_dir,
                map_path=map_path,
                mot_path=mot_path,
                blob_paths=blob_paths,
                expected_source_sha=source_sha,
            )
            self.assertEqual("UNKNOWN", missing.status)

            paths = [project_dir / item for item in layout.PROVENANCE_CONFIG_PATHS]
            paths.extend((map_path, mot_path, *blob_paths))
            manifest = {
                "schema_version": 1,
                "source_sha": source_sha,
                "dirty": False,
                "project_path": "Projects/aws_wifi_rx671_ek/e2studio_ccrx",
                "sha256": {
                    path.relative_to(repo_root).as_posix(): layout._sha256(path)
                    for path in paths
                },
            }
            (build_dir / layout.PROVENANCE_MANIFEST_NAME).write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            valid = layout._artifact_provenance_gate(
                repo_root=repo_root,
                project_dir=project_dir,
                map_path=map_path,
                mot_path=mot_path,
                blob_paths=blob_paths,
                expected_source_sha=source_sha,
            )
            self.assertEqual("PASS", valid.status)

            map_path.write_text("stale map", encoding="utf-8")
            stale = layout._artifact_provenance_gate(
                repo_root=repo_root,
                project_dir=project_dir,
                map_path=map_path,
                mot_path=mot_path,
                blob_paths=blob_paths,
                expected_source_sha=source_sha,
            )
            self.assertEqual("FAIL", stale.status)
            self.assertIn("hash不一致", stale.detail)


if __name__ == "__main__":
    unittest.main()

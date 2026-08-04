import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


SCRIPT = Path(__file__).resolve().parents[1] / "analyze_rx671_ota_layout.py"
ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("analyze_rx671_ota_layout", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
layout = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = layout
SPEC.loader.exec_module(layout)

RSU_SCRIPT = Path(__file__).resolve().parents[2] / "build_rx671_fwup_v2_rsu.py"
RSU_SPEC = importlib.util.spec_from_file_location(
    "build_rx671_fwup_v2_rsu_for_analyzer_tests", RSU_SCRIPT
)
assert RSU_SPEC is not None and RSU_SPEC.loader is not None
rsu_builder = importlib.util.module_from_spec(RSU_SPEC)
sys.modules[RSU_SPEC.name] = rsu_builder
RSU_SPEC.loader.exec_module(rsu_builder)


def _s3_record(address: int, data: bytes) -> str:
    body = address.to_bytes(4, "big") + data
    count = len(body) + 1
    checksum = (~(count + sum(body))) & 0xFF
    return "S3" + bytes([count]).hex().upper() + body.hex().upper() + f"{checksum:02X}"


class ParseTests(unittest.TestCase):
    def test_parse_project_name_placeholder_from_directory(self):
        repo_root = Path(__file__).resolve().parents[3]
        cproject = repo_root / "Projects/boot_loader_rx671_ek/e2studio_ccrx/.cproject"
        _mode, _build_dir, artifact_name, _anchors, _binaries = layout._parse_cproject(
            cproject
        )
        self.assertEqual("boot_loader_rx671_ek", artifact_name)

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

    def test_parse_unique_ota_integer_defines(self):
        text = """
<listOptionValue value="-define=mqttFileDownloader_CONFIG_BLOCK_SIZE=4096"/>
<listOptionValue value="-define=MQTT_AGENT_NETWORK_BUFFER_SIZE=(8192U)"/>
"""
        self.assertEqual(
            4096,
            layout._cproject_integer_define(
                text, "mqttFileDownloader_CONFIG_BLOCK_SIZE"
            ),
        )
        self.assertEqual(
            8192,
            layout._cproject_integer_define(text, "MQTT_AGENT_NETWORK_BUFFER_SIZE"),
        )
        self.assertIsNone(layout._cproject_integer_define(text, "MISSING"))

        ambiguous = text + (
            '<listOptionValue value="-define=MQTT_AGENT_NETWORK_BUFFER_SIZE=16384"/>'
        )
        self.assertIsNone(
            layout._cproject_integer_define(
                ambiguous, "MQTT_AGENT_NETWORK_BUFFER_SIZE"
            )
        )

    def test_parse_unique_ota_symbol_defines(self):
        text = (
            '<listOptionValue value="-define='
            'SDIO_HOST_CFG_RUN_CLOCK_DIV=SDHI_DIV_8"/>'
        )
        self.assertEqual(
            "SDHI_DIV_8",
            layout._cproject_symbol_define(
                text, "SDIO_HOST_CFG_RUN_CLOCK_DIV"
            ),
        )
        self.assertIsNone(layout._cproject_symbol_define(text, "MISSING"))
        self.assertIsNone(
            layout._cproject_symbol_define(
                text
                + '<listOptionValue value="-define='
                + 'SDIO_HOST_CFG_RUN_CLOCK_DIV=SDHI_DIV_2"/>',
                "SDIO_HOST_CFG_RUN_CLOCK_DIV",
            )
        )

    def test_parse_srecord_ranges_and_validate_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mot"
            path.write_text(_s3_record(0xFFF00000, b"abc") + "\n", encoding="ascii")
            self.assertEqual([(0xFFF00000, 0xFFF00003)], layout._parse_srecord_ranges(path))

            path.write_text("S308FFF0000061626300\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "checksum"):
                layout._parse_srecord_ranges(path)

    def test_bootloader_config_comparison_ignores_only_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "parent.h"
            canonical = root / "canonical.h"
            parent.write_bytes(b"#define A 1\r\n#define B 2\r\n")
            canonical.write_bytes(b"#define A 1\n#define B 2\n")
            self.assertTrue(layout._same_text_lines(parent, canonical))

            canonical.write_bytes(b"#define A 1\n#define B 3\n")
            self.assertFalse(layout._same_text_lines(parent, canonical))


class GateTests(unittest.TestCase):
    def test_runtime_default_stays_linear_until_ota_profile_is_applied(self):
        repo_root = Path(__file__).resolve().parents[3]
        project_dir = repo_root / "Projects/aws_wifi_rx671_ek/e2studio_ccrx"
        with tempfile.TemporaryDirectory() as empty_build:
            gates = layout.analyze(project_dir, Path(empty_build))
        by_name = {gate.name: gate for gate in gates}

        self.assertEqual("UNKNOWN", by_name["bootloader_layout"].status)
        self.assertEqual("FAIL", by_name["mqtt_ota_buffer_fit"].status)
        self.assertEqual("FAIL", by_name["ota_sdio_run_clock"].status)
        self.assertEqual("PASS", by_name["rom_capacity"].status)
        self.assertEqual("PASS", by_name["fwup_data_flash_geometry"].status)
        self.assertEqual("PASS", by_name["littlefs_data_flash_geometry"].status)
        self.assertEqual("PASS", by_name["data_flash_ownership_contract"].status)
        self.assertEqual("PASS", by_name["data_flash_non_overlap"].status)
        self.assertEqual("PASS", by_name["fwup_partition"].status)
        self.assertEqual("FAIL", by_name["dual_bank_mode"].status)
        self.assertEqual("FAIL", by_name["application_in_main_area"].status)
        self.assertEqual("FAIL", by_name["static_image_single_area"].status)
        self.assertEqual("FAIL", by_name["whd_resources_follow_application"].status)
        self.assertEqual("PASS", by_name["sdio_resource_addressing"].status)
        self.assertEqual("FAIL", by_name["fwup_code_flash_layout"].status)
        self.assertEqual("UNKNOWN", by_name["artifact_provenance"].status)
        self.assertEqual("UNKNOWN", by_name["whd_blob_sizes"].status)
        self.assertEqual("UNKNOWN", by_name["ram_capacity"].status)
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

    def test_ram_capacity_uses_selected_bsp_limit_and_rejects_gap_overflow(self):
        passing = layout._ram_capacity_gate(
            sections={
                "SU": layout.Section("SU", 0x00000004, 0x1000),
                "B": layout.Section("B", 0x0005F000, 0x1000),
                "P": layout.Section("P", 0xFFF00300, 0x1000),
            },
            ram_size=393216,
            data_flash_start=0x00100000,
        )
        overflowing = layout._ram_capacity_gate(
            sections={
                "B": layout.Section("B", 0x0005FF00, 0x200),
                "P": layout.Section("P", 0xFFF00300, 0x1000),
            },
            ram_size=393216,
            data_flash_start=0x00100000,
        )
        gap_overflow = layout._ram_capacity_gate(
            sections={
                "BAD": layout.Section("BAD", 0x00070000, 0x10),
            },
            ram_size=393216,
            data_flash_start=0x00100000,
        )

        self.assertEqual("PASS", passing.status)
        self.assertIn("headroom=0 bytes", passing.detail)
        self.assertEqual("FAIL", overflowing.status)
        self.assertIn("B@0x0005FF00-0x000600FF", overflowing.detail)
        self.assertEqual("FAIL", gap_overflow.status)
        self.assertIn("BAD@0x00070000", gap_overflow.detail)

    def test_mqtt_ota_block_base64_and_overhead_must_fit_exact_profile(self):
        passing = layout._mqtt_ota_buffer_gate(
            block_size=4096,
            network_buffer_size=8192,
            blocks_per_request=1,
        )
        too_small = layout._mqtt_ota_buffer_gate(
            block_size=4096,
            network_buffer_size=6000,
            blocks_per_request=1,
        )
        drifted = layout._mqtt_ota_buffer_gate(
            block_size=2048,
            network_buffer_size=8192,
            blocks_per_request=1,
        )
        burst = layout._mqtt_ota_buffer_gate(
            block_size=4096,
            network_buffer_size=8192,
            blocks_per_request=3,
        )
        missing = layout._mqtt_ota_buffer_gate(
            block_size=None,
            network_buffer_size=8192,
            blocks_per_request=1,
        )

        self.assertEqual("PASS", passing.status)
        self.assertIn("base64=5464", passing.detail)
        self.assertIn("required=6488", passing.detail)
        self.assertEqual("FAIL", too_small.status)
        self.assertEqual("FAIL", drifted.status)
        self.assertEqual("FAIL", burst.status)
        self.assertIn("blocks/request=3", burst.detail)
        self.assertEqual("FAIL", missing.status)

    def test_ota_runtime_memory_profile_is_exact(self):
        passing = layout._ota_runtime_memory_profile_gate(
            heap_size_kb=208,
            data_buffer_count=2,
            max_file_blocks=192,
        )
        stale_heap = layout._ota_runtime_memory_profile_gate(
            heap_size_kb=192,
            data_buffer_count=2,
            max_file_blocks=192,
        )
        stale_buffers = layout._ota_runtime_memory_profile_gate(
            heap_size_kb=208,
            data_buffer_count=3,
            max_file_blocks=192,
        )
        stale_file_blocks = layout._ota_runtime_memory_profile_gate(
            heap_size_kb=208,
            data_buffer_count=2,
            max_file_blocks=128,
        )
        missing = layout._ota_runtime_memory_profile_gate(
            heap_size_kb=208,
            data_buffer_count=None,
            max_file_blocks=192,
        )

        self.assertEqual("PASS", passing.status)
        self.assertIn("heap=208 KiB", passing.detail)
        self.assertEqual("FAIL", stale_heap.status)
        self.assertEqual("FAIL", stale_buffers.status)
        self.assertEqual("FAIL", stale_file_blocks.status)
        self.assertEqual("FAIL", missing.status)

    def test_ota_sdio_run_clock_profile_is_exact(self):
        passing = layout._ota_sdio_run_clock_gate(run_clock_div="SDHI_DIV_8")
        high_speed = layout._ota_sdio_run_clock_gate(run_clock_div="SDHI_DIV_2")
        missing = layout._ota_sdio_run_clock_gate(run_clock_div=None)

        self.assertEqual("PASS", passing.status)
        self.assertIn("required=SDHI_DIV_8", passing.detail)
        self.assertEqual("FAIL", high_speed.status)
        self.assertEqual("FAIL", missing.status)

    def test_parent_bootloader_headers_are_required_provenance_inputs(self):
        self.assertIn(
            layout.BOOTLOADER_PROJECT_RELATIVE / "src/rx671.h",
            layout.BOOTLOADER_PROVENANCE_PATHS,
        )
        self.assertIn(
            layout.BOOTLOADER_PROJECT_RELATIVE / "src/rx_bootloader_config.h",
            layout.BOOTLOADER_PROVENANCE_PATHS,
        )
        parent = (
            ROOT
            / layout.BOOTLOADER_PROJECT_RELATIVE
            / "src/rx671.h"
        ).read_text(encoding="utf-8").splitlines()
        canonical = (
            ROOT
            / layout.BOOTLOADER_SUBMODULE_RELATIVE
            / "config/rx671.h"
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(canonical, parent)

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

    def test_littlefs_can_solely_own_all_data_flash(self):
        gate = layout._data_flash_non_overlap_gate(
            data_flash_start=0x00100000,
            data_flash_size=8192,
            littlefs_start=0x00100000,
            littlefs_block_size=128,
            littlefs_block_count=64,
            consumer_layout_complete=True,
        )
        self.assertEqual("PASS", gate.status)
        self.assertIn("0x00100000-0x00101FFF", gate.detail)
        self.assertIn("consumer所有権証跡が完備", gate.detail)

    def test_linker_anchors_alone_do_not_prove_sole_data_flash_ownership(self):
        gate = layout._data_flash_non_overlap_gate(
            data_flash_start=0x00100000,
            data_flash_size=8192,
            littlefs_start=0x00100000,
            littlefs_block_size=128,
            littlefs_block_count=64,
            consumer_ranges=(),
            consumer_layout_complete=False,
        )
        self.assertEqual("UNKNOWN", gate.status)
        self.assertIn("所有権証跡が未確定", gate.detail)

    def test_full_littlefs_rejects_raw_data_flash_consumers(self):
        for name in ("raw-df-install", "bootloader-key-store", "ota-payload"):
            with self.subTest(name=name):
                gate = layout._data_flash_non_overlap_gate(
                    data_flash_start=0x00100000,
                    data_flash_size=8192,
                    littlefs_start=0x00100000,
                    littlefs_block_size=128,
                    littlefs_block_count=64,
                    consumer_ranges=(layout.Region(name, 0x00100000, 4),),
                    consumer_layout_complete=True,
                )
                self.assertEqual("FAIL", gate.status)
                self.assertIn(f"LittleFSと{name}が重複", gate.detail)

    def test_data_flash_contract_rejects_bootloader_install(self):
        contract = {
            "schema_version": 1,
            "target": "R5F5671EHxFB",
            "data_flash": {
                "start": "0x00100000",
                "size": 8192,
                "owner": "LittleFS",
                "application_raw_consumers": [],
                "bootloader_install_data_flash": False,
                "ota_payload_data_flash": False,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_path = root / "ota-layout-contract.json"
            bootloader_config = root / "rx671.h"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            bootloader_config.write_text(
                "#define RX_BOOTLOADER_INSTALL_DATA_FLASH (1)\n",
                encoding="utf-8",
            )
            gate = layout._data_flash_ownership_contract_gate(
                contract_path=contract_path,
                bootloader_config_path=bootloader_config,
                data_flash_start=0x00100000,
                data_flash_size=8192,
                littlefs_start=0x00100000,
                littlefs_size=8192,
            )
        self.assertEqual("FAIL", gate.status)
        self.assertIn("RX_BOOTLOADER_INSTALL_DATA_FLASH!=0", gate.detail)

    def test_known_data_flash_overlap_fails_even_if_inventory_is_incomplete(self):
        gate = layout._data_flash_non_overlap_gate(
            data_flash_start=0x00100000,
            data_flash_size=8192,
            littlefs_start=0x00100000,
            littlefs_block_size=128,
            littlefs_block_count=64,
            consumer_ranges=(layout.Region("known-raw-consumer", 0x00100000, 4),),
            consumer_layout_complete=False,
        )
        self.assertEqual("FAIL", gate.status)
        self.assertIn("LittleFSとknown-raw-consumerが重複", gate.detail)

    def test_partial_littlefs_is_unknown_until_real_consumers_are_measured(self):
        gate = layout._data_flash_non_overlap_gate(
            data_flash_start=0x00100000,
            data_flash_size=8192,
            littlefs_start=0x00100800,
            littlefs_block_size=128,
            littlefs_block_count=32,
        )
        self.assertEqual("UNKNOWN", gate.status)
        self.assertIn("所有権証跡が未確定", gate.detail)

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

    def test_fwup_code_flash_layout_uses_real_reserved_addresses(self):
        passing = layout._fwup_code_flash_layout_gate(
            main_start=0xFFF00000,
            buffer_start=0xFFE00000,
            area_size=0x000C0000,
            application_anchor=0xFFF00300,
            except_vector_anchor=0xFFFBFF80,
            reset_vector_anchor=0xFFFBFFFC,
        )
        overlapping = layout._fwup_code_flash_layout_gate(
            main_start=0xFFF00000,
            buffer_start=0xFFE00000,
            area_size=0x000C0000,
            application_anchor=0xFFF00000,
            except_vector_anchor=0xFFFFFF80,
            reset_vector_anchor=0xFFFFFFFC,
        )
        self.assertEqual("PASS", passing.status)
        self.assertIn("main-header=0xFFF00000-0xFFF001FF", passing.detail)
        self.assertIn("main-descriptor=0xFFF00200-0xFFF002FF", passing.detail)
        self.assertEqual("FAIL", overlapping.status)
        self.assertIn("必要値=0xFFF00300", overlapping.detail)
        self.assertIn("必要値=0xFFFBFF80", overlapping.detail)

    def test_fwup_code_flash_layout_rejects_another_reserved_anchor(self):
        gate = layout._fwup_code_flash_layout_gate(
            main_start=0xFFF00000,
            buffer_start=0xFFE00000,
            area_size=0x000C0000,
            application_anchor=0xFFF00300,
            except_vector_anchor=0xFFFBFF80,
            reset_vector_anchor=0xFFFBFFFC,
            code_flash_anchors={
                "PResetPRG": 0xFFF00300,
                "C_BAD": 0xFFF00100,
                "EXCEPTVECT": 0xFFFBFF80,
                "RESETVECT": 0xFFFBFFFC,
            },
        )
        self.assertEqual("FAIL", gate.status)
        self.assertIn("C_BAD@0xFFF00100", gate.detail)

    def test_fwup_partition_allows_symmetric_bootloader_tail(self):
        gate = layout._fwup_partition_gate(
            flash_start=0xFFE00000,
            flash_size=0x00200000,
            main_start=0xFFF00000,
            buffer_start=0xFFE00000,
            area_size=0x000C0000,
        )
        self.assertEqual("PASS", gate.status)
        self.assertIn("予約候補=262144 bytes", gate.detail)

        oversized = layout._fwup_partition_gate(
            flash_start=0xFFE00000,
            flash_size=0x00200000,
            main_start=0xFFF00000,
            buffer_start=0xFFE00000,
            area_size=0x00100001,
        )
        self.assertEqual("FAIL", oversized.status)

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


class RsuGateTests(unittest.TestCase):
    def _fixture(self, root: Path, version: str = "1.2.3"):
        private_key = ec.generate_private_key(ec.SECP256R1())
        payload = bytearray(b"\xFF" * rsu_builder.APPLICATION_SIZE)
        marker = f"RX671_OTA_IMAGE_VERSION={version}".encode("ascii") + b"\x00"
        payload[0x100 : 0x100 + len(marker)] = marker
        payload[-4:] = b"\x00\x03\xF0\xFF"
        image = rsu_builder.build_image(bytes(payload), private_key)

        rsu_path = root / "build/rx671-ota/candidate-1.2.3/aws_wifi_rx671_ek.rsu"
        certificate_path = rsu_path.parent / "rx671-ota-signer.crt.pem"
        rsu_path.parent.mkdir(parents=True)
        rsu_path.write_bytes(image)

        now = datetime.now(timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "RX671 test")])
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(private_key.public_key())
            .serial_number(1)
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .sign(private_key, hashes.SHA256())
        )
        certificate_path.write_bytes(
            certificate.public_bytes(serialization.Encoding.PEM)
        )
        manifest_path = rsu_path.parent / layout.PROVENANCE_MANIFEST_NAME
        manifest = {
            "schema_version": 1,
            "profile": layout.OTA_PROFILE_NAME,
            "ota_image_version": version,
            "sdio_run_clock_div": layout.OTA_SDIO_RUN_CLOCK_DIV,
            "rsu_path": rsu_path.relative_to(root).as_posix(),
            "signer_certificate_path": certificate_path.relative_to(root).as_posix(),
            "sha256": {
                rsu_path.relative_to(root).as_posix(): layout._sha256(rsu_path),
                certificate_path.relative_to(root).as_posix(): layout._sha256(
                    certificate_path
                ),
            },
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return rsu_path, certificate_path, manifest_path

    def _gate(
        self,
        root: Path,
        rsu_path: Path,
        certificate_path: Path,
        manifest_path: Path,
        version: str = "1.2.3",
    ):
        return layout._rsu_image_gate(
            repo_root=root,
            rsu_path=rsu_path,
            signer_certificate_path=certificate_path,
            expected_version=version,
            provenance_manifest_path=manifest_path,
        )

    def test_accepts_strict_signed_single_segment_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rsu_path, certificate_path, manifest_path = self._fixture(root)
            gate = self._gate(
                root, rsu_path, certificate_path, manifest_path
            )
        self.assertEqual("PASS", gate.status)
        self.assertIn("Data Flashなし", gate.detail)
        self.assertIn("version=1.2.3", gate.detail)

    def test_rejects_signed_payload_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rsu_path, certificate_path, manifest_path = self._fixture(root)
            image = bytearray(rsu_path.read_bytes())
            image[layout.FWUP_APPLICATION_OFFSET + 4] ^= 1
            rsu_path.write_bytes(image)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            relative = rsu_path.relative_to(root).as_posix()
            manifest["sha256"][relative] = layout._sha256(rsu_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            gate = self._gate(
                root, rsu_path, certificate_path, manifest_path
            )
        self.assertEqual("FAIL", gate.status)
        self.assertIn("ECDSA署名不一致", gate.detail)

    def test_rejects_wrong_version_and_data_flash_enable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rsu_path, certificate_path, manifest_path = self._fixture(root)
            wrong_version = self._gate(
                root,
                rsu_path,
                certificate_path,
                manifest_path,
                version="1.2.4",
            )
            image = bytearray(rsu_path.read_bytes())
            image[0x12C:0x130] = (1).to_bytes(4, "little")
            rsu_path.write_bytes(image)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            relative = rsu_path.relative_to(root).as_posix()
            manifest["sha256"][relative] = layout._sha256(rsu_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            data_flash = self._gate(
                root, rsu_path, certificate_path, manifest_path
            )
        self.assertEqual("FAIL", wrong_version.status)
        self.assertIn("version marker不一致", wrong_version.detail)
        self.assertEqual("FAIL", data_flash.status)
        self.assertIn("Data Flash payload", data_flash.detail)

    def test_rejects_manifest_path_or_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rsu_path, certificate_path, manifest_path = self._fixture(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rsu_path"] = "wrong.rsu"
            relative = certificate_path.relative_to(root).as_posix()
            manifest["sha256"][relative] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            gate = self._gate(
                root, rsu_path, certificate_path, manifest_path
            )
        self.assertEqual("FAIL", gate.status)
        self.assertIn("manifest rsu_path不一致", gate.detail)
        self.assertIn("manifest hash不一致", gate.detail)


if __name__ == "__main__":
    unittest.main()

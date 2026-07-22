from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

from tools.ci.check_rx671_bootloader_layout import (
    BOOT_START,
    DataRecord,
    validate_records,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT = REPO_ROOT / "Projects" / "boot_loader_rx671_ek" / "e2studio_ccrx"
SUBMODULE = PROJECT / "lib" / "rx_bootloader"
SUBMODULE_SHA = "da8a5c720b5b664cf5ba7fc8cb10ec135593016c"


def read(relative: str) -> str:
    return (PROJECT / relative).read_text(encoding="utf-8", errors="strict")


class Rx671BootloaderContractTests(unittest.TestCase):
    def test_project_targets_dual_bank_rx671(self) -> None:
        cproject = read(".cproject")
        self.assertIn('device="R5F5671E"', cproject)
        self.assertIn('modes="bank.dual"', cproject)
        self.assertIn('option id="board.id" value="EK-RX671"', cproject)
        self.assertIn('value="RX671" valueType="string"', cproject)
        self.assertIn('value="R5F5671EHxFB_DUAL"', cproject)
        self.assertIn('value="R5F5671E_DUAL"', cproject)
        self.assertIn(
            "PResetPRG,C_1,C_2,C,C_8,C$*,D*,W*,L,P/0FFFC0000,"
            "EXCEPTVECT/0FFFFFF80,RESETVECT/0FFFFFFFC",
            cproject,
        )
        self.assertNotIn("DEXRAM", cproject)
        self.assertNotIn("BEXRAM", cproject)

    def test_bsp_is_bare_metal_dual_bank_bootloader(self) -> None:
        config = read("src/smc_gen/r_config/r_bsp_config.h")
        self.assertRegex(config, r"#define BSP_CFG_CODE_FLASH_BANK_MODE\s+\(0\)")
        self.assertRegex(config, r"#define BSP_CFG_RTOS_USED\s+\(0\)")
        self.assertRegex(config, r"#define BSP_CFG_BOOTLOADER_PROJECT\s+\(1\)")
        self.assertRegex(config, r"#define BSP_CFG_SCI_UART_TERMINAL_BITRATE\s+\(921600\)")

    def test_only_sci6_is_enabled(self) -> None:
        sci_config = read("src/smc_gen/r_config/r_sci_rx_config.h")
        channel_settings = dict(
            re.findall(r"#define SCI_CFG_CH(\d+)_INCLUDED\s+\((\d)\)", sci_config)
        )
        self.assertEqual("1", channel_settings.pop("6"))
        self.assertTrue(channel_settings)
        self.assertEqual({"0"}, set(channel_settings.values()))

        scfg = read("boot_loader_rx671_ek.scfg")
        used = set(re.findall(r'<Item[^>]+id="([^"]+)"[^>]+usedState="使用中"', scfg))
        self.assertEqual(set(), used)
        self.assertIn('<gridItem id="BSP_CFG_SCI_UART_TERMINAL_BITRATE" selectedIndex="921600"', scfg)
        self.assertIn('<gridItem id="SCI6" selectedIndex="1"', scfg)

        pin_source = read("src/smc_gen/r_pincfg/Pin.c")
        self.assertIn("Set RXD6 pin", pin_source)
        self.assertIn("Set TXD6 pin", pin_source)
        self.assertNotIn("Set SDHI_", pin_source)
        self.assertNotRegex(pin_source, r"Set AN00[0-5] pin")

    def test_smart_configurator_component_set_is_minimal(self) -> None:
        scfg = read("boot_loader_rx671_ek.scfg")
        displays = set(re.findall(r'<component[^>]+display="([^"]+)"', scfg))
        self.assertEqual(
            {
                "r_bsp",
                "r_byteq",
                "r_cmt_rx",
                "r_flash_rx",
                "r_sci_rx",
                "rm_littlefs_rx",
                "rm_rtos_abstraction_rx",
            },
            displays,
        )

    def test_data_flash_is_preserved_and_public_key_uses_littlefs(self) -> None:
        target = read("src/rx671.h")
        config = read("src/rx_bootloader_config.h")
        self.assertRegex(target, r"#define RX_BOOTLOADER_INSTALL_DATA_FLASH\s+\(0\)")
        self.assertRegex(config, r"#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE\s+\(0\)")
        self.assertRegex(config, r"#define RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE\s+\(1\)")
        self.assertRegex(
            config,
            r"#define RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK\s+\(0\)",
        )
        self.assertRegex(config, r"#define RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE\s+\(1\)")
        self.assertRegex(config, r"#define RX_BOOTLOADER_SCI_INT_PRIORITY\s+\(15\)")
        self.assertIn('"code_signer_public_key"', config)
        self.assertIn('"code_sign_cert_id"', config)

    def test_no_private_key_material_is_stored_in_parent_project(self) -> None:
        forbidden_suffixes = {".key", ".pem", ".privatekey"}
        candidates = [
            path
            for path in PROJECT.rglob("*")
            if path.is_file()
            and SUBMODULE not in path.parents
            and path.suffix.lower() in forbidden_suffixes
        ]
        self.assertEqual([], candidates)
        for path in PROJECT.rglob("*"):
            if not path.is_file() or SUBMODULE in path.parents:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            self.assertNotRegex(text, r"-----BEGIN (?:EC |RSA )?PRIVATE KEY-----")

    def test_no_builtin_code_signer_key_is_stored_in_parent_project(self) -> None:
        self.assertFalse((PROJECT / "src" / "key" / "code_signer_public_key.h").exists())

    def test_uart_smoke_rejects_unsafe_key_fallback(self) -> None:
        monitor = (REPO_ROOT / "tools" / "ci" / "test_rx671_bootloader_uart.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"found": "Loading user code signer public key from LittleFS: found."', monitor)
        self.assertIn('"missing-fail-closed"', monitor)
        self.assertIn('UNSAFE_FALLBACK_MARKER = "not found; using built-in key."', monitor)

    def test_manual_smoke_releases_reset_and_selects_key_state(self) -> None:
        ci = (REPO_ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        job = ci.split("smoke_rx671_bootloader_manual:", 1)[1].split(
            "\nflash_rx72n_ether:", 1
        )[0]
        self.assertIn("-p -v -run -noquery", job)
        self.assertNotIn("-p -v -reset -noquery", job)
        self.assertIn('--expected-key-state "$RX671_BOOTLOADER_EXPECTED_KEY_STATE"', job)

    def test_build_cleanup_is_limited_to_named_child_directories(self) -> None:
        helper = (REPO_ROOT / "tools" / "build_headless_rx671_bootloader.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("[string]$AllowedRoot", helper)
        self.assertIn("[string]$ExpectedLeaf", helper)
        self.assertIn("OrdinalIgnoreCase", helper)
        self.assertIn('ExpectedLeaf "e2ws_iot_ref_rx671_bootloader_2026_04_2"', helper)
        self.assertIn('ExpectedLeaf "HardwareDebug"', helper)

    def test_bootloader_submodule_contract(self) -> None:
        gitmodules = (REPO_ROOT / ".gitmodules").read_text(encoding="utf-8")
        relative = "Projects/boot_loader_rx671_ek/e2studio_ccrx/lib/rx_bootloader"
        self.assertIn(f'[submodule "{relative}"]', gitmodules)
        self.assertIn(f"\tpath = {relative}", gitmodules)
        self.assertIn(
            "\turl = ../../../../experiment/embedded/mcu/renesas/rx/bootloader/submodule.git",
            gitmodules,
        )
        head = subprocess.check_output(
            ["git", "-C", str(SUBMODULE), "rev-parse", "HEAD"], text=True
        ).strip()
        self.assertEqual(SUBMODULE_SHA, head)

        staged = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--stage", "--", relative],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        if staged:
            mode, sha, _stage_and_path = staged.split(maxsplit=2)
            self.assertEqual("160000", mode)
            self.assertEqual(SUBMODULE_SHA, sha)


class Rx671BootloaderLayoutUnitTests(unittest.TestCase):
    def test_rejects_payload_below_reserved_boot_window(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside RX671 boot/option ranges"):
            validate_records([DataRecord(0xFFE00000, b"x")])

    def test_accepts_entry_and_complete_vector_window(self) -> None:
        records = [
            DataRecord(BOOT_START, b"entry"),
            DataRecord(0xFFFFFF80, bytes(0x80)),
        ]
        used, option_count = validate_records(records)
        self.assertEqual(0x85, used)
        self.assertEqual(0, option_count)


if __name__ == "__main__":
    unittest.main()

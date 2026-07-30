import csv
import re
import tempfile
import unittest
from pathlib import Path

from tools import build_fwup_v2_rsu as rsu_builder


class Rx72nFwupPrmContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.prm_relative = Path("tools/fwup/rx72n_envision_kit_dual_bank.prm.csv")
        cls.prm_path = cls.repo_root / cls.prm_relative
        cls.boot_loader_cproject = (
            cls.repo_root
            / "Projects"
            / "boot_loader_rx72n_envision_kit"
            / "e2studio_ccrx"
            / ".cproject"
        )

    def test_board_specific_layout_matches_existing_boot_loader(self):
        with self.prm_path.open(newline="", encoding="utf-8") as handle:
            values = dict(csv.reader(handle))

        self.assertEqual(values["device Type"], "Dual Mode")
        self.assertEqual(values["Code Flash Size(Dual Mode Only)"], "0x00400000")
        self.assertEqual(values["Bootloader Start Address"], "0xFFFC0000")
        self.assertEqual(values["Bootloader End Address"], "0xFFFFFFFF")
        self.assertEqual(values["User Program Start Address"], "0xFFE00000")
        self.assertEqual(values["User Program End Address"], "0xFFFBFFFF")
        self.assertEqual(values["Flash Write Size"], "128")

    def test_prm_builder_and_boot_loader_linker_layouts_match(self):
        layout = rsu_builder.load_prm_layout(self.prm_path)
        rsu_builder.validate_prm_layout(layout)

        self.assertEqual(
            rsu_builder.USER_PROGRAM_TOP,
            layout.user_program_start
            + rsu_builder.RSU_HEADER_SIZE
            + rsu_builder.RSU_DESCRIPTOR_SIZE,
        )
        self.assertEqual(rsu_builder.USER_PROGRAM_BOTTOM, layout.user_program_end)
        self.assertEqual(rsu_builder.BOOTLOADER_TOP, layout.bootloader_start)
        self.assertEqual(rsu_builder.BOOTLOADER_BOTTOM, layout.bootloader_end)
        self.assertEqual(rsu_builder.FLASH_WRITE_SIZE, layout.flash_write_size)

        cproject = self.boot_loader_cproject.read_text(encoding="utf-8")
        linker_starts = {
            int(match, 16)
            for match in re.findall(
                r"(?:^|,)P(?:\*)?/0([0-9A-Fa-f]{8})(?:,|$)",
                cproject,
            )
        }
        self.assertEqual({layout.bootloader_start}, linker_starts)
        self.assertIn("P*/0FFFC0000", cproject)

    def test_builder_rejects_incompatible_prm(self):
        prm_text = self.prm_path.read_text(encoding="utf-8")
        incompatible_text = prm_text.replace(
            "Flash Write Size,128",
            "Flash Write Size,256",
        )
        self.assertNotEqual(prm_text, incompatible_text)

        with tempfile.TemporaryDirectory() as temp_dir:
            prm_path = Path(temp_dir) / "incompatible.csv"
            prm_path.write_text(incompatible_text, encoding="utf-8")
            layout = rsu_builder.load_prm_layout(prm_path)

        with self.assertRaisesRegex(RuntimeError, r"Flash Write Size=256"):
            rsu_builder.validate_prm_layout(layout)

    def test_all_rx72n_rsu_consumers_use_board_specific_prm(self):
        powershell_reference = r"tools\fwup\rx72n_envision_kit_dual_bank.prm.csv"
        consumers = {
            ".gitlab-ci.yml": powershell_reference,
            "tools/generate_rx72n_rsu.ps1": powershell_reference,
            "tools/run_rx72n_local_baseline.ps1": powershell_reference,
            "tools/build_ota_candidate.py": (
                'tools_dir / "fwup" / "rx72n_envision_kit_dual_bank.prm.csv"'
            ),
        }

        for relative_path, expected_reference in consumers.items():
            with self.subTest(relative_path=relative_path):
                text = (self.repo_root / relative_path).read_text(encoding="utf-8")
                self.assertIn(expected_reference, text)
                self.assertNotIn(
                    r"src\smc_gen\r_fwup\tool\RX72N_DualBank_ImageGenerator_PRM.csv",
                    text,
                )


if __name__ == "__main__":
    unittest.main()

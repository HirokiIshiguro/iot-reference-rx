import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FlashLayoutTests(unittest.TestCase):
    def test_app_vectors_and_ota_area_match_boot_boundary(self):
        for name, size in (("aws_bg96_ck_rx65n", "0xE0000U"),
                           ("aws_bg96_ck_rx65n_tsip", "0xE0000U"),
                           ("aws_ether_rx72n_envision_kit", "0x1E0000U"),
                           ("aws_ether_rx72n_envision_kit_tsip", "0x1E0000U")):
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                self.assertIn("EXCEPTVECT/0FFFDFF80,RESETVECT/0FFFDFFFC", (project / ".cproject").read_text(encoding="utf-8"))
                self.assertIn(size, (project / "src/frtos_config/rx_ota_config.h").read_text(encoding="utf-8"))
                self.assertIn(size, (project / ".settings/com.renesas.smc.e2studio.qe.xml").read_text(encoding="utf-8"))

    def test_bootloader_block_map_and_project_override(self):
        for name, header, mirror, temporary in (("boot_loader_ck_rx65n", "rx65n.h", 47, 48),
                                                 ("boot_loader_rx72n_envision_kit", "rx72n.h", 79, 80)):
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                text = (project / "src" / header).read_text(encoding="utf-8")
                for key, value in (("LOW_ADDRESS", 9), ("MIRROR_LOW_ADDRESS", mirror),
                                   ("UPDATE_TEMPORARY_AREA_HIGH_ADDRESS", temporary)):
                    self.assertRegex(text, rf"RX_BOOTLOADER_{key}\s+FLASH_CF_BLOCK_{value}\b")
                self.assertRegex(text, r"RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM\s+\(2\)")
                self.assertIn("0FFFE0000", (project / ".cproject").read_text(encoding="utf-8"))
                self.assertIn(f'#include "{header}"', (project / "src/rx_bootloader_config.h").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FlashLayoutTests(unittest.TestCase):
    def test_app_vectors_and_ota_area_match_boot_boundary(self):
        for name, size in (("aws_bg96_ck_rx65n", "0xF0000U"),
                           ("aws_bg96_ck_rx65n_tsip", "0xF0000U"),
                           ("aws_ether_rx72n_envision_kit", "0x1F0000U"),
                           ("aws_ether_rx72n_envision_kit_tsip", "0x1F0000U")):
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                self.assertIn("EXCEPTVECT/0FFFEFF80,RESETVECT/0FFFEFFFC", (project / ".cproject").read_text(encoding="utf-8"))
                ota_config = (project / "src/frtos_config/rx_ota_config.h").read_text(encoding="utf-8")
                self.assertRegex(ota_config, rf"(?m)^#define\s+RX_OTA_CFG_AREA_SIZE\s+\({size}\)")
                if name.startswith("aws_bg96_"):
                    self.assertIn(size, (project / ".settings/com.renesas.smc.e2studio.qe.xml").read_text(encoding="utf-8"))

    def test_ota_block_bitmap_covers_the_whole_signed_image(self):
        import re
        # (project, OTA area size, MQTT block size, bitmap size when the project does not define one)
        for name, area, block, default in (("aws_bg96_ck_rx65n", 0xF0000, 7168, 128),
                                           ("aws_bg96_ck_rx65n_tsip", 0xF0000, 7168, 128),
                                           ("aws_ether_rx72n_envision_kit", 0x1F0000, 16384, 128),
                                           ("aws_ether_rx72n_envision_kit_tsip", 0x1F0000, 16384, 128)):
            with self.subTest(project=name):
                text = (ROOT / "Projects" / name / "e2studio_ccrx/src/frtos_config/MQTTFileDownloader_config.h").read_text(encoding="utf-8")
                match = re.search(r"#define\s+OTA_MAX_NUM_FILE_BLOCKS\s+\((\d+)U\)", text)
                blocks = int(match.group(1)) if match else default
                needed = -(-(area - 0x200) // block)
                self.assertGreaterEqual(blocks, needed)

    def test_bootloader_block_map_comes_from_the_shared_submodule(self):
        for name, header in (("boot_loader_rx671_ek", "rx671.h"),
                             ("boot_loader_ck_rx65n", "rx65n.h"),
                             ("boot_loader_rx72n_envision_kit", "rx72n.h")):
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                # A copy under src/ would shadow lib/rx_bootloader/config on the include path.
                self.assertFalse((project / "src" / header).exists())
                self.assertIn("0FFFF0000", (project / ".cproject").read_text(encoding="utf-8"))
                self.assertIn(f'#include "{header}"', (project / "src/rx_bootloader_config.h").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

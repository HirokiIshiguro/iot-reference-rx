"""Keep RX72N Trace enabled through its common startup and original RTT port."""
from pathlib import Path
import re
import unittest

from tools.ci.tests.test_trace_recorder import selected_recorder_sources


ROOT = Path(__file__).resolve().parents[3]
PROJECTS = ("aws_ether_rx72n_envision_kit", "aws_ether_rx72n_envision_kit_tsip")


class Rx72nTsipTraceInitTests(unittest.TestCase):
    def test_board_initialization_has_no_unselected_spi_transport_dependency(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                source = (ROOT / "Projects" / name / "e2studio_ccrx/src/application_code/user_init.c").read_text(encoding="utf-8")
                self.assertNotIn('"trace_spi_transport.h"', source)
                self.assertNotRegex(source, r"\bTraceSpiTransport_\w+\s*\(")
                self.assertEqual(len(re.findall(r"\bR_Pins_Create\s*\(", source)), 1)
                self.assertEqual(len(re.findall(r"\bpvPortMalloc\s*\(", source)), 1)

    def test_common_startup_keeps_one_initialize_and_start_with_original_jlink_port(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                startup = (project / "src/frtos_startup/freertos_start.c").read_text(encoding="utf-8")
                main = (project / "src/application_code/main.c").read_text(encoding="utf-8")
                config = (project / "src/frtos_config/FreeRTOSConfig.h").read_text(encoding="utf-8")
                self.assertEqual(len(re.findall(r"\bxTraceInitialize\s*\(\s*\)", startup)), 1)
                self.assertEqual(len(re.findall(r"\bxTraceEnable\s*\(\s*TRC_START\s*\)", main)), 1)
                self.assertRegex(config, r"#define\s+CONFIG_USE_PERCEPIO_TRACE_RECORDER\s+1\b")
                selected = selected_recorder_sources(project)
                self.assertEqual(len(selected), len(set(selected)))
                self.assertIn("streamports/Jlink_RTT/trcStreamPort.c", selected)
                self.assertIn("streamports/Jlink_RTT/SEGGER_RTT.c", selected)


if __name__ == "__main__":
    unittest.main()

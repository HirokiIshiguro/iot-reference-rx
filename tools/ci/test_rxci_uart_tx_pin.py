"""The application owns TX routing even when it starts with PMR cleared."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERIAL = ROOT / "Demos/cli/serial.c"

# Board, console channel, and the TX port bit left to user code by Smart Configurator.
TARGETS = (
    ("aws_ether_rx72n_envision_kit", "RX72N", 7, "PORT9.PMR.BIT.B0"),
    ("aws_ether_rx72n_envision_kit_tsip", "RX72N", 7, "PORT9.PMR.BIT.B0"),
    ("aws_bg96_ck_rx65n", "RX65N", 0, "PORT3.PMR.BIT.B2"),
    ("aws_bg96_ck_rx65n_tsip", "RX65N", 0, "PORT3.PMR.BIT.B2"),
)


class UartTxPinTests(unittest.TestCase):
    def test_routes_generated_tx_pin_only_after_successful_open(self):
        source = SERIAL.read_text(encoding="utf-8")
        opening = source.split("static sci_err_t prvEnsureSerialPortOpen( void )", 1)[1]
        opening = opening.split("void CLI_Support_Settings(void)", 1)[0]
        self.assertLess(opening.index("U_SCI_UART_CLI_PINSET();"), opening.index("R_SCI_Open("))
        enabled = re.search(
            r"R_SCI_Open\([^;]+;\s*if\( SCI_SUCCESS == xOpenResult \)\s*\{([^}]+)\}",
            opening,
        )
        self.assertIsNotNone(enabled, "TX pin must be routed after a successful SCI open")
        for project, mcu, sci, pin in TARGETS:
            with self.subTest(project=project):
                generated = ROOT / "Projects" / project / "e2studio_ccrx/src/smc_gen"
                bsp = (generated / "r_config/r_bsp_config.h").read_text(encoding="utf-8")
                pins = (generated / "r_pincfg/Pin.c").read_text(encoding="utf-8")
                self.assertRegex(bsp, rf"#define BSP_CFG_SCI_UART_TERMINAL_CHANNEL\s+\({sci}\)")
                self.assertIn(f"// {pin} = 1U; // Please set the PMR bit after TE bit is set to 1.", pins)
                self.assertRegex(
                    enabled[1],
                    rf"defined\(BSP_MCU_{mcu}\) && \(BSP_CFG_SCI_UART_TERMINAL_CHANNEL == {sci}\)"
                    rf"\s+{re.escape(pin)} = 1U;",
                )
        self.assertNotIn("BSP_MCU_RX671", enabled[1])

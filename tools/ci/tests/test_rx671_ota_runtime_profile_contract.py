from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "Projects/aws_wifi_rx671_ek/e2studio_ccrx"


class Rx671OtaRuntimeProfileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = (PROJECT / "src/aws_wifi_rx671_ek.c").read_text(
            encoding="utf-8"
        )
        cls.demo = (PROJECT / "src/frtos_config/demo_config.h").read_text(
            encoding="utf-8"
        )

    def test_checked_in_defaults_preserve_normal_runtime(self) -> None:
        self.assertIn(
            "#define RX671_OTA_RUNTIME_ENABLE            (0)",
            self.demo,
        )
        self.assertIn(
            "#define RX671_OTA_PROVISIONER_ENABLE        (0)",
            self.demo,
        )
        self.assertIn(
            "#define ENABLE_OTA_UPDATE_DEMO              "
            "RX671_OTA_RUNTIME_ENABLE",
            self.demo,
        )
        self.assertIn(
            "#define ENABLE_CREDENTIAL_BY_CLI            "
            "RX671_OTA_PROVISIONER_ENABLE",
            self.demo,
        )

    def test_provisioner_owns_cli_without_network_start(self) -> None:
        self.assertIn(
            "#if (RX671_OTA_PROVISIONER_ENABLE == 1)",
            self.main,
        )
        self.assertIn("CLI_Support_Settings();", self.main)
        self.assertIn("littlFs_init()", self.main)
        self.assertIn("vprvCacheInit()", self.main)
        self.assertIn("vRegisterSampleCLICommands();", self.main)
        self.assertIn("vUARTCommandConsoleStart(", self.main)
        self.assertIn(
            "#define configCLI_BAUD_RATE                    (921600)",
            self.demo,
        )
        self.assertIn(
            "SCI6 belongs exclusively to the common CLI",
            self.main,
        )

    def test_ota_runtime_uses_persistent_kvs_and_starts_automatically(self) -> None:
        self.assertIn("static BaseType_t ota_runtime_prepare(void)", self.main)
        self.assertIn("pdPASS != xMQTTAgentInit()", self.main)
        self.assertIn(
            "xSetMQTTAgentState(MQTT_AGENT_STATE_INITIALIZED);",
            self.main,
        )
        self.assertIn("vStartMQTTAgent(", self.main)
        self.assertIn("vStartOtaDemo();", self.main)
        self.assertIn(
            "#if (RX671_OTA_RUNTIME_ENABLE == 1)\n"
            "        result = xTaskCreate(ota_start_task,",
            self.main,
        )


if __name__ == "__main__":
    unittest.main()

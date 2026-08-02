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
        cls.aws_iot_config = (
            PROJECT / "src/frtos_config/aws_iot_config.h"
        ).read_text(encoding="utf-8")
        cls.freertos_config = (
            PROJECT / "src/frtos_config/FreeRTOSConfig.h"
        ).read_text(encoding="utf-8")
        cls.scfg = (PROJECT / "aws_wifi_rx671_ek.scfg").read_text(
            encoding="utf-8"
        )
        cls.whd = (PROJECT / "src/whd_bringup.c").read_text(
            encoding="utf-8"
        )
        cls.whd_config = (PROJECT / "src/whd_join_config.h").read_text(
            encoding="utf-8"
        )
        cls.ip_config = (
            PROJECT / "src/frtos_config/FreeRTOSIPConfig.h"
        ).read_text(encoding="utf-8")
        cls.ip_hooks = (PROJECT / "src/freertos_tcp_hooks.c").read_text(
            encoding="utf-8"
        )
        cls.sdio_host = (PROJECT / "src/sdio_host.c").read_text(
            encoding="utf-8"
        )
        cls.ota_host = (ROOT / "tools/test_rx671_ota.py").read_text(
            encoding="utf-8"
        )
        cls.store_header = (ROOT / "Demos/cli/store.h").read_text(
            encoding="utf-8"
        )
        cls.store = (ROOT / "Demos/cli/store.c").read_text(
            encoding="utf-8"
        )
        cls.dev_mode_provisioning = (
            ROOT
            / "Demos/dev_mode_key_provisioning/src/aws_dev_mode_key_provisioning.c"
        ).read_text(encoding="utf-8")
        cls.cli = (ROOT / "Demos/cli/CLIcommands.c").read_text(
            encoding="utf-8"
        )
        cls.console = (ROOT / "Demos/cli/UARTCommandConsole.c").read_text(
            encoding="utf-8"
        )
        cls.freertos_cli = (
            ROOT / "Middleware/FreeRTOS-Plus-CLI/FreeRTOS_CLI.c"
        ).read_text(encoding="utf-8")
        cls.freertos_helper = (
            PROJECT / "src/application/startup/freertos_helper.c"
        ).read_text(encoding="utf-8")
        cls.freertos_user_port = (
            PROJECT / "src/application/startup/freertos_user_port.c"
        ).read_text(encoding="utf-8")
        cls.software_tls_transport = (
            ROOT
            / "Middleware/network_transport/using_mbedtls_pkcs11/transport_mbedtls_pkcs11.c"
        ).read_text(encoding="utf-8")
        cls.mqtt_wrapper = (
            ROOT / "Demos/common/mqtt-wrapper/mqtt_wrapper.c"
        ).read_text(encoding="utf-8")
        cls.mqtt_agent_task = (
            ROOT / "Demos/mqtt_agent/mqtt_agent_task.c"
        ).read_text(encoding="utf-8")
        cls.ota_demo = (
            ROOT / "Demos/OtaOverMqtt/OtaOverMqttDemo.c"
        ).read_text(encoding="utf-8")
        cls.mqtt_file_downloader_config = (
            PROJECT / "src/frtos_config/MQTTFileDownloader_config.h"
        ).read_text(encoding="utf-8")
        cls.ota_image_builder = (
            ROOT / "tools/build_rx671_ota_images.py"
        ).read_text(encoding="utf-8")
        cls.builder = (ROOT / "tools/build_headless_rx671_wifi.ps1").read_text(
            encoding="utf-8"
        )
        cls.cproject = (PROJECT / ".cproject").read_text(encoding="utf-8")

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
        self.assertIn('#include "r_sci_rx_pinset.h"', self.main)
        self.assertIn("R_SCI_PinSet_SCI6();", self.main)
        self.assertLess(
            self.main.index("CLI_Support_Settings();"),
            self.main.index("R_SCI_PinSet_SCI6();"),
        )
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

    def test_provisioner_cli_has_private_key_import_stack_headroom(self) -> None:
        self.assertIn(
            "#define OTA_PROVISIONER_CLI_STACK_DEPTH     (2048U)",
            self.main,
        )
        self.assertNotIn(
            "OTA_PROVISIONER_CLI_STACK_SIZE      "
            "(configMINIMAL_STACK_SIZE * 6U)",
            self.main,
        )
        self.assertIn(
            "vUARTCommandConsoleStart(OTA_PROVISIONER_CLI_STACK_DEPTH,",
            self.main,
        )

    def test_dev_mode_keystore_is_not_copied_onto_cli_stack(self) -> None:
        self.assertIn(
            "vDevModeKeyPreProvisioning( const KeyValueStore_t * pKeystore,",
            self.store,
        )
        self.assertIn(
            "vDevModeKeyPreProvisioning(&gKeyValueStore,",
            self.store,
        )
        self.assertIn(
            "vDevModeKeyPreProvisioning(const KeyValueStore_t * pKeystore,",
            self.dev_mode_provisioning,
        )
        self.assertIn(
            "pKeystore->table[ID].valueLength",
            self.dev_mode_provisioning,
        )
        self.assertNotIn(
            "vDevModeKeyPreProvisioning(KeyValueStore_t Keystore,",
            self.dev_mode_provisioning,
        )
        self.assertNotIn(
            "vDevModeKeyPreProvisioning (KeyValueStore_t Keystore,",
            self.dev_mode_provisioning,
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

    def test_ota_requires_real_station_mac_and_dhcp_lease(self) -> None:
        self.assertIn("whd_mac_is_valid", self.whd)
        self.assertIn(
            "WHD station MAC unavailable; refusing network start",
            self.whd,
        )
        self.assertNotIn("local_admin_mac", self.main)
        self.assertIn("iptraceDHCP_SUCCEEDED", self.ip_config)
        self.assertIn(
            "iptraceDHCP_REQUESTS_FAILED_USING_DEFAULT_IP_ADDRESS",
            self.ip_config,
        )
        self.assertIn("g_freertos_tcp_dhcp_lease_acquired = 1U", self.ip_hooks)
        self.assertIn("g_freertos_tcp_dhcp_static_fallback = 1U", self.ip_hooks)
        self.assertIn(
            "RX671 OTA startup retry: DHCP lease not acquired",
            self.main,
        )
        self.assertIn(
            "RX671 OTA startup ready: WHD and DHCP lease verified",
            self.main,
        )
        self.assertLess(
            self.main.index(
                "RX671 OTA startup ready: WHD and DHCP lease verified"
            ),
            self.main.index("vStartOtaDemo();"),
        )

    def test_startup_recovery_uses_bounded_reset_and_type1yn_power_cycle(self) -> None:
        self.assertIn("RX671 OTA startup retry: WHD bring-up failed", self.main)
        self.assertIn("--startup-reset-retries", self.ota_host)
        self.assertIn("for attempt in range(reset_limit + 1)", self.ota_host)
        self.assertIn("rfp.run_command()", self.ota_host)
        self.assertIn("sd_slot_power_on();", self.sdio_host)
        self.assertIn("PORT5.PODR.BIT.B1 = 0U", self.sdio_host)
        self.assertIn("PORT5.PODR.BIT.B1 = 1U", self.sdio_host)

    def test_ota_runtime_reports_scheduler_fatal_hooks(self) -> None:
        self.assertIn(
            "RX671 OTA fatal: FreeRTOS malloc failed",
            self.freertos_helper,
        )
        self.assertIn(
            "RX671 OTA heap at malloc failure: free=",
            self.freertos_helper,
        )
        self.assertIn("xPortGetMinimumEverFreeHeapSize()", self.freertos_helper)
        self.assertIn(
            "RX671 OTA fatal: FreeRTOS stack overflow",
            self.freertos_helper,
        )
        self.assertIn(
            "RX671 OTA fatal: FreeRTOS assert failed",
            self.freertos_user_port,
        )

    def test_ota_profile_serializes_stream_blocks_and_bounds_static_buffers(self) -> None:
        self.assertIn(
            "#define mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST   (1U)",
            self.mqtt_file_downloader_config,
        )
        self.assertIn(
            "-define=mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST=1",
            self.ota_image_builder,
        )
        self.assertIn(
            "-define=OTA_MAX_NUM_DATA_BUFFERS=2",
            self.ota_image_builder,
        )
        self.assertIn(
            "-define=OTA_MAX_NUM_FILE_BLOCKS=192",
            self.ota_image_builder,
        )
        self.assertIn(
            "#define OTA_MAX_NUM_FILE_BLOCKS                  (192U)",
            self.mqtt_file_downloader_config,
        )
        self.assertIn("#ifndef OTA_MAX_NUM_DATA_BUFFERS", self.ota_demo)
        self.assertIn("#ifndef OTA_MAX_NUM_FILE_BLOCKS", self.ota_demo)
        self.assertIn(
            "messageLength > sizeof(dataBuffers[0].data)", self.ota_demo
        )

    def test_software_transport_can_pin_the_ota_proof_to_tls_1_2_or_1_3(
        self,
    ) -> None:
        self.assertIn(
            "AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_2",
            self.aws_iot_config,
        )
        self.assertIn(
            "AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3",
            self.aws_iot_config,
        )
        self.assertIn(
            "MBEDTLS_SSL_VERSION_TLS1_2",
            self.software_tls_transport,
        )
        self.assertIn(
            "MBEDTLS_SSL_VERSION_TLS1_3",
            self.software_tls_transport,
        )
        self.assertIn(
            "expected TLSv1.2",
            self.software_tls_transport,
        )
        self.assertIn(
            "expected TLSv1.3",
            self.software_tls_transport,
        )

    def test_mqtt_agent_notification_index_exists_in_every_task_tcb(self) -> None:
        self.assertIn(
            "#define MQTT_AGENT_NOTIFY_IDX    (2)",
            self.mqtt_wrapper,
        )
        self.assertIn(
            "xTaskNotifyStateClearIndexed(NULL, MQTT_AGENT_NOTIFY_IDX)",
            self.mqtt_wrapper,
        )
        self.assertIn(
            "#define configTASK_NOTIFICATION_ARRAY_ENTRIES      4",
            self.freertos_config,
        )
        self.assertIn(
            '<gridItem id="configTASK_NOTIFICATION_ARRAY_ENTRIES" '
            'selectedIndex="4"/>',
            self.scfg,
        )
        self.assertIn(
            "configTASK_NOTIFICATION_ARRAY_ENTRIES <= "
            "MQTT_AGENT_NOTIFY_IDX",
            self.mqtt_wrapper,
        )
        self.assertIn(
            "#define MQTT_AGENT_NOTIFY_IDX (3U)",
            self.mqtt_agent_task,
        )
        self.assertIn(
            "configTASK_NOTIFICATION_ARRAY_ENTRIES <= "
            "MQTT_AGENT_NOTIFY_IDX",
            self.mqtt_agent_task,
        )

    def test_wifi_credentials_are_runtime_provisioned_and_passphrase_is_forgotten(
        self,
    ) -> None:
        self.assertIn("KVS_WIFI_SSID", self.store_header)
        self.assertIn("KVS_WIFI_PASSPHRASE", self.store_header)
        self.assertIn("conf sethex {wifissid|wifipass}", self.cli)
        self.assertIn('"Wi-Fi SSID"', self.cli)
        self.assertIn('"Wi-Fi passphrase"', self.cli)
        self.assertIn("configured; readback disabled", self.cli)
        self.assertIn('"conf sethex wifissid "', self.console)
        self.assertIn('"conf sethex wifipass "', self.console)
        self.assertIn("A blank line must never repeat a credential command", self.console)
        self.assertIn("prvSecureZero(cInputString", self.console)
        self.assertIn("xWriteBufferLen - 1U", self.freertos_cli)
        self.assertIn("pcWriteBuffer[xWriteBufferLen - 1U] = '\\0'", self.freertos_cli)
        self.assertIn("WHD_JOIN_USE_KVS", self.whd_config)
        self.assertIn("xReadEntry(KVS_WIFI_SSID", self.whd)
        self.assertIn("xReadEntry(KVS_WIFI_PASSPHRASE", self.whd)
        self.assertIn("KVStore_vClearCachedValue(KVS_WIFI_SSID)", self.whd)
        self.assertIn("KVStore_vClearCachedValue(KVS_WIFI_PASSPHRASE)", self.whd)
        self.assertIn("whd_secure_zero(g_whd_join_ssid", self.whd)
        self.assertIn("whd_secure_zero(g_whd_join_passphrase", self.whd)
        self.assertIn("-UseKvsJoinConfig", self.builder)
        self.assertIn("$generatedLocalJoinConfig = $true", self.builder)
        self.assertIn("$generatedLocalAwsIotConfig = $true", self.builder)
        self.assertLess(
            self.builder.index("$generatedLocalJoinConfig = $true"),
            self.builder.index("Write-LocalJoinConfig -Path"),
        )
        self.assertLess(
            self.builder.index("$generatedLocalAwsIotConfig = $true"),
            self.builder.index("Write-LocalAwsIotConfig -Path"),
        )
        self.assertIn(
            "Failed to restore or remove a generated local credential header",
            self.builder,
        )
        self.assertLess(
            self.main.index("ota_runtime_prepare()"),
            self.main.index("whd_bringup_run()"),
        )

    def test_wifi_credential_code_is_isolated_from_normal_network_profile(
        self,
    ) -> None:
        self.assertNotIn("-define=RX671_OTA_PROVISIONER_ENABLE=1", self.cproject)
        self.assertNotIn("-define=WHD_JOIN_USE_KVS=1", self.cproject)
        self.assertIn("#define WHD_JOIN_USE_KVS                  (0)", self.store_header)
        self.assertIn(
            "#define RX671_OTA_PROVISIONER_ENABLE      (0)",
            self.store_header,
        )
        self.assertIn(
            "#if (WHD_JOIN_USE_KVS == 1) || "
            "(RX671_OTA_PROVISIONER_ENABLE == 1)",
            self.store_header,
        )
        self.assertIn(
            "#define RX671_WIFI_CREDENTIAL_KVS_ENABLE  (1)",
            self.store_header,
        )
        self.assertIn(
            "#if RX671_WIFI_CREDENTIAL_KVS_ENABLE == 1\n"
            "    KVS_WIFI_SSID,",
            self.store_header,
        )
        self.assertIn(
            "#if RX671_WIFI_CREDENTIAL_KVS_ENABLE == 1",
            self.store,
        )
        self.assertIn(
            "#if RX671_WIFI_CREDENTIAL_KVS_ENABLE == 1",
            self.cli,
        )
        self.assertIn(
            "#if RX671_OTA_PROVISIONER_ENABLE == 1",
            self.console,
        )
        self.assertIn(
            "#if RX671_OTA_PROVISIONER_ENABLE == 1",
            self.freertos_cli,
        )


if __name__ == "__main__":
    unittest.main()

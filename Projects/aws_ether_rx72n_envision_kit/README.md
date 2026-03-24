# aws_ether_rx72n_envision_kit

RX72N application seed project on top of the `iot-reference-rx` Ethernet baseline.

Imported seed:
- source project: `iot-reference-rx/Projects/aws_ether_ck_rx65n_v2/e2studio_ccrx/`
- extra reference files: `flash_project/`, `ether_ota_information.md`,
  `ether_pubsub_information.md`

Current status:
- directory name is already the RX72N target name
- internal project metadata still contains RX65N-oriented names and settings
- no RX72N build claim is made in this step

Expected RX72N-specific adaptation areas:
- RXv3 + DPFPU FreeRTOS port assumptions
- RX72N Ethernet PHY and pin configuration
- UART / CLI port selection
- credential storage and littlefs path
- OTA PAL and `r_fwup` integration

Migration guardrail:
- first target is headless AWS / MQTT / OTA baseline
- GUI and SD update reintegration are follow-up work

# aws_wifi_rx671_ek

This project is the EK-RX671 + Murata Type 1YN Wi-Fi staging project for the
`iot-reference-rx` FreeRTOS/AWS middleware baseline.

The first committed state intentionally starts from the proven WHD bring-up
tree:

- EK-RX671 SDHI + in-house `r_sdio_rx`
- Infineon WHD v1.70.0 through a project-local submodule
- Type 1YN firmware boot, MAC read, AP scan, and WPA2-PSK JOIN verified on
  hardware in the source experiment repository
- No AP credentials or firmware blobs committed

The e2 studio project name is `aws_wifi_rx671_ek`.

## Layout

| Path | Purpose |
|---|---|
| `e2studio_ccrx/` | EK-RX671 e2 studio CCRX application project |
| `external/wifi-host-driver/` | WHD v1.70.0 submodule |
| `external/patches/whd-v1.70.0-ccrx-portability.patch` | Required WHD CC-RX/SDIO patch |
| `apply_whd_patch.ps1` | Helper to re-apply the WHD patch after submodule checkout |

## Current Status

The project is the current EK-RX671 + Type 1YN Wi-Fi baseline branch. It keeps
the boot-loader and TSIP variants out of scope for now and focuses on one
plain CCRX/e2 studio project that can be debugged from J-Link Commander.

Known verified baseline:

- e2 studio headless build: `aws_wifi_rx671_ek/HardwareDebug`
- Target image: `e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.mot`
- Hardware: EK-RX671 + Murata Type 1YN over SDIO
- Probe: SEGGER J-Link Compact PLUS over JTAG
- Serial console: SCI6 on COM5 at 921600 bps
- WHD bring-up: `whd_wifi_on`, AP scan, WPA2-PSK JOIN, and MAC read succeeded
- FreeRTOS+TCP: PC-to-board ping succeeded after Wi-Fi JOIN
- J-Link Commander observation:
  - SDHI SDIO in-band interrupt counters increased during traffic
  - WHD RX counters increased during ping traffic
  - ICMP RX counter reached 4 for a 4-packet ping run
  - RX network buffers were allocated and submitted to the FreeRTOS+TCP IP task

The baseline is intended to remain on a dedicated development branch until the
Wi-Fi stack, throughput measurement, provisioning, TSIP, and boot-loader
variants are separated into reviewable milestones.

## Build

Initialize submodules and apply the WHD patch before building:

```powershell
git submodule update --init --recursive Projects/aws_wifi_rx671_ek/external/wifi-host-driver
pwsh -File Projects/aws_wifi_rx671_ek/apply_whd_patch.ps1
pwsh -File tools/build_headless_rx671_wifi.ps1
```

Expected outputs:

- `e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.mot`
- `e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.abs`
- `e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.x`

## FreeRTOS+TCP Integration Plan

The first network goal is DHCP over Wi-Fi after WHD JOIN.

Implementation steps:

1. Keep WHD source unmodified except for the tracked external patch.
2. Add a project-local FreeRTOS+TCP `NetworkInterface` implementation for WHD.
3. Map WHD RX packet callbacks into `eNetworkRxEvent`.
4. Map `xNetworkInterfaceOutput()` into WHD packet TX.
5. Add IP task startup and DHCP logging.
6. Reuse existing MQTT/mbed TLS/coreMQTT project pieces only after IP bring-up
   is stable.

TSIP and boot loader variants are future sibling projects, not part of this
initial import.

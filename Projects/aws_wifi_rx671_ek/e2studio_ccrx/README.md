# e2 studio CCRX FreeRTOS WHD host project

`aws_wifi_rx671_ek` e2 studio project for EK-RX671 + Murata Type 1YN
(CYW43439). This is the host tree for integrating the Infineon Wi-Fi Host
Driver (WHD) on top of the SDIO bus layer (`r_sdhi_rx` + the in-house
`r_sdio_rx`), targeting WHD init -> chip up -> scan -> join -> FreeRTOS+TCP ->
AWS IoT MQTT smoke.

It carries forward the SDIO bring-up and RF-proof work from the
`ek-rx671-sdio-type1yn` experiment repository: sustained WLAN operation
(scan completion / join / data) is left to WHD core flow control rather than
hand-written, per the
[Issue #30](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/elemental/protocol/sd/sdio/murata/type-1yn/host/renesas/ek-rx671/-/issues/30)
WHD-integration decision.

Current state: WHD bring-up, FreeRTOS+TCP, and a minimal AWS IoT MQTT smoke path
are compiled into the project. The project now contains:

- SCI6 debug console (`src/debug_uart.*`, board USB-serial path at 921600 8N1).
- Minimal WHD resource, packet-buffer and network glue in `src/whd_port`.
- `cyhal_sdio` backend on top of the proven `sdio_host.c` / `r_sdio_rx` path.
- A `whd_bringup_run()` sequence that calls `whd_init`,
  `whd_bus_sdio_attach`, `whd_wifi_on`, reads the STA MAC address, scans APs,
  and can optionally join an AP.
- A FreeRTOS+TCP network interface bridge for WHD, plus a small AWS IoT MQTT
  smoke task that connects, performs TLS/MQTT setup, disconnects, and reports
  `AWS MQTT=0` on success.

The WHD core itself is kept as an external submodule. Firmware/NVRAM/CLM blobs
are not committed to this repository. Apply
`../external/patches/whd-v1.70.0-ccrx-portability.patch` to the WHD submodule
before building; the patch carries CC-RX packing fixes plus the SDIO CMD52/CMD53
argument and Function 2 FIFO handling needed for WHD scan/JOIN.

## Build-time bring-up switches

`src/whd_join_config.h` carries the local WHD bring-up switches.

| Macro | Default | Purpose |
|---|---:|---|
| `WHD_BRINGUP_ENABLE` | `1` | Run the WHD bring-up path from `main_task`. Set to `0` to return to the older primitive SDIO probe path. |
| `WHD_JOIN_ENABLE` | `0` | Enable AP JOIN after `whd_wifi_on`. Keep disabled for firmware-download/MAC-address smoke tests. |
| `WHD_SCAN_ENABLE` | `1` | Run a synchronous AP scan after MAC address readback. |
| `WHD_SCAN_RESULT_LIMIT` | `32` | Maximum number of scan results printed to the SCI6 debug console. |
| `WHD_JOIN_SSID` | `""` | AP SSID. Do not commit real credentials. |
| `WHD_JOIN_PASSPHRASE` | `""` | AP passphrase. Do not commit real credentials. |
| `WHD_JOIN_SECURITY` | `WHD_SECURITY_WPA2_AES_PSK` | Initial security mode for AP JOIN testing. |
| `WHD_SDIO_SOFTIRQ_POLL_MS` | `0` | Temporary SDIO soft-IRQ poll period for WHD event wakeups. Use `1` for the current AP JOIN / ping baseline when the SDHI in-band interrupt path is being isolated. |
| `WHD_SDIO_DIAG_FAIL_LIMIT` | `16` | Maximum CMD52/CMD53 failure diagnostics printed per command class. |
| `WHD_SDIO_PRE_CMD53_CLOCKS` | `1` | Force the CYW43439 backplane clocks and KSO once before the first F1 CMD53, matching the proven primitive backplane-read sequence without modifying WHD core code. |

For a real AP JOIN run, do not edit this tracked header with real credentials.
Use the headless build helper from the repository root instead:

```powershell
pwsh -File tools/build_headless_rx671_wifi.ps1 `
  -WifiConfigFile C:\ai\codex\ref\wifi.txt `
  -AwsIotConfigDir C:\ai\codex\secrets\aws-iot\rx671-ek-type1yn-01 `
  -SoftIrqPollMs 1 `
  -WlanAllowBusSleepDelayMs 600000
```

The helper generates ignored `src/whd_join_config_local.h` and temporarily
injects `WHD_JOIN_USE_LOCAL_CONFIG` into `.cproject` for that build only. A
local header by itself is not enough; the compiler define is what makes
`whd_join_config.h` include it. The repository default intentionally leaves
JOIN disabled.

For AWS IoT smoke testing, pass `-AwsIotConfigDir` or the equivalent
environment variables consumed by `tools/build_headless_rx671_wifi.ps1`. The
helper generates ignored `src/frtos_config/aws_iot_config_local.h` and injects
`AWS_IOT_USE_LOCAL_CONFIG` only for the build. Do not commit local endpoint,
certificate, or private-key material.

For the current PC-to-board ping baseline, the same helper also temporarily
injects `PLATFORM_WLAN_ALLOW_BUS_TO_SLEEP_DELAY_MS=600000`. The WHD v1.70.0
upstream default is 10 ms; the ping-success run kept the WLAN bus awake because
the 10 ms sleep timing prevented ARP/ICMP traffic from reaching the SDIO
Function 2 CMD53 data path reliably on the RX671 bring-up stack. The project
patch only makes this WHD macro overrideable; the tracked e2 studio project is
restored after the headless build.

## WHD resource flash layout

The Type 1YN / CYW43439 WHD resources are loaded separately into code flash:

| Resource | Local source artifact | Flash address |
|---|---|---:|
| WLAN firmware | `artifacts/fw/43439A0.bin` | `0xFFF00000` |
| NVRAM | `artifacts/fw/nvram_1yn.bin` | `0xFFF80000` |
| CLM blob | `artifacts/fw/43439A0.clm_blob` | `0xFFF90000` |

The resource provider in `src/whd_port/whd_port_resource.c` reads those fixed
addresses through the WHD resource callback API. If erased flash is present at
those locations, `whd_wifi_on` will fail during firmware/resource handling.

Example J-Link Commander flow:

```text
device R5F5671E
si JTAG
speed 4000
jtagconf -1 -1
connect
loadfile <repo_root>\Projects\aws_wifi_rx671_ek\e2studio_ccrx\HardwareDebug\aws_wifi_rx671_ek.mot
loadbin C:\path\to\local\type1yn-fw\43439A0.bin 0xFFF00000
loadbin C:\path\to\local\type1yn-fw\nvram_1yn.bin 0xFFF80000
loadbin C:\path\to\local\type1yn-fw\43439A0.clm_blob 0xFFF90000
r
g
q
```

Use `-SelectEmuBySN 853004952` when both the external J-Link Compact PLUS and
another SEGGER probe are connected.

The repository root also provides a thin helper that emits the same Commander
script into a temporary file:

```powershell
pwsh -File tools/load_rx671_wifi_jlink.ps1 `
  -FirmwareBin C:\path\to\local\type1yn-fw\43439A0.bin `
  -NvramBin C:\path\to\local\type1yn-fw\nvram_1yn.bin `
  -ClmBlob C:\path\to\local\type1yn-fw\43439A0.clm_blob `
  -Run
```

## Temporary interrupt model

The current WHD SDIO backend is still synchronous and mostly polled. WHD expects
an SDIO card-interrupt callback to wake its internal thread for control/event
traffic, so `src/whd_port/cyhal_sdhc.c` can provide a FreeRTOS software timer
that periodically calls the registered `CYHAL_SDIO_CARD_INTERRUPT` handler.
The bridge is disabled by default in the tracked project so the SDHI in-band
interrupt path remains visible during bring-up. Set
`WHD_SDIO_SOFTIRQ_POLL_MS=1` through the local JOIN config when reproducing the
current AP JOIN / ping baseline with software wakeups.

The RX671 + Type 1YN bench also needs the Broadcom backplane clock/KSO sequence
that was proven in the primitive SDIO project before the first F1 CMD53. WHD
requests ALP during `whd_bus_sdio_init`, but the current board path has required
`FORCE_HT` and `SLEEPCSR KEEP_WL_KSO` before the chip-common backplane read will
clock data. `WHD_SDIO_PRE_CMD53_CLOCKS=1` keeps that quirk contained in the
`cyhal_sdio` backend rather than forking WHD.

This is intentionally a bring-up bridge:

- It keeps the RX671-specific WHD core edits in one external patch instead of
  copying WHD sources into this repository.
- It keeps AP JOIN testing possible before the real SDHI interrupt path is
  fully connected.
- It must be replaced by SDHI `SDACI` / in-band SDIO interrupt handling for the
  performance-focused driver path.

## FreeRTOS+TCP integration boundary

The WHD packet network callback currently counts incoming Ethernet frames and
releases them immediately. The next integration step is to replace this with a
FreeRTOS+TCP `NetworkInterface` bridge:

```text
WHD packet RX callback
  -> allocate/copy or loan a FreeRTOS+TCP NetworkBufferDescriptor_t
  -> set pxInterface / pxEndPoint
  -> send eNetworkRxEvent to the IP task

FreeRTOS+TCP xNetworkInterfaceOutput
  -> hand pxNetworkBuffer->pucEthernetBuffer to WHD
  -> release the NetworkBufferDescriptor_t according to xReleaseAfterSend
```

The bridge should live under `src/network/` first, while the WHD SDIO/RTOS
port stays under `src/whd_port/`. Keep WHD itself unmodified except for the
tracked external patch.

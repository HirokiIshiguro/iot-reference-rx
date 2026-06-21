# e2 studio CCRX FreeRTOS WHD host project

`aws_wifi_rx671_ek` e2 studio project for EK-RX671 + Murata Type 1YN
(CYW43439). This is the host tree for integrating the Infineon Wi-Fi Host
Driver (WHD) on top of the SDIO bus layer (`r_sdhi_rx` + the in-house
`r_sdio_rx`), targeting WHD init → chip up → scan → join.

It carries forward the SDIO bring-up and RF-proof work from the
`ek-rx671-sdio-type1yn` experiment repository: sustained WLAN operation
(scan completion / join / data) is left to WHD core flow control rather than
hand-written, per the
[Issue #30](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/elemental/protocol/sd/sdio/murata/type-1yn/host/renesas/ek-rx671/-/issues/30)
WHD-integration decision.

Current state: WHD bring-up path is compiled into the project. The project now
contains:

- SCI6 debug console (`src/debug_uart.*`, board USB-serial path at 921600 8N1).
- Minimal WHD resource, packet-buffer and network glue in `src/whd_port`.
- `cyhal_sdio` backend on top of the proven `sdio_host.c` / `r_sdio_rx` path.
- A `whd_bringup_run()` sequence that calls `whd_init`,
  `whd_bus_sdio_attach`, `whd_wifi_on`, reads the STA MAC address, scans APs,
  and can optionally join an AP.

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
| `WHD_SDIO_SOFTIRQ_POLL_MS` | `1` | Temporary SDIO soft-IRQ poll period for WHD event wakeups. `0` disables the bridge for low-level isolation. |
| `WHD_SDIO_DIAG_FAIL_LIMIT` | `16` | Maximum CMD52/CMD53 failure diagnostics printed per command class. |
| `WHD_SDIO_PRE_CMD53_CLOCKS` | `1` | Force the CYW43439 backplane clocks and KSO once before the first F1 CMD53, matching the proven primitive backplane-read sequence without modifying WHD core code. |

For a real AP JOIN run, pass the credential macros as local compiler defines or
temporarily edit `whd_join_config.h` in the working tree only. The repository
default intentionally leaves JOIN disabled.

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

## Temporary interrupt model

The current WHD SDIO backend is still synchronous and mostly polled. WHD expects
an SDIO card-interrupt callback to wake its internal thread for control/event
traffic, so `src/whd_port/cyhal_sdhc.c` can provide a FreeRTOS software timer
that periodically calls the registered `CYHAL_SDIO_CARD_INTERRUPT` handler.
The bridge is enabled by default at a conservative 1 ms period. Set
`WHD_SDIO_SOFTIRQ_POLL_MS=0` only when isolating lower-level SDIO bring-up,
because scan/JOIN need WHD's internal thread to observe firmware events.

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

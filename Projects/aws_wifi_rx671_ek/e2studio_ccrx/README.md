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

The WHD core itself is kept as an external submodule. The Type 1YN
firmware/NVRAM/CLM source revisions are pinned under
`../external/type1yn-blobs/sources`, while generated staging files are ignored
by git and linked into the firmware image. Apply
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
  -WlanAllowBusSleepDelayMs 600000 `
  -SdioRunClockDiv SDHI_DIV_2 `
  -SdioCmd53XferEngine SDIO_HOST_CMD53_XFER_DTC
```

The helper generates ignored `src/whd_join_config_local.h` and temporarily
injects `WHD_JOIN_USE_LOCAL_CONFIG` into `.cproject` for that build only. A
local header by itself is not enough; the compiler define is what makes
`whd_join_config.h` include it. The repository default intentionally leaves
JOIN disabled.

e2 studio 2026.04.2 regenerates Smart Configurator output while importing this
project. The helper snapshots every tracked project file except the temporarily
patched `.cproject`, restores the checked-out bytes after import, and performs a
parallel forced make. This keeps the CI image on the reviewed source instead of
silently compiling regenerated defaults such as a different FreeRTOS heap size.
The CI build fails if any tracked project diff remains afterward.

For AWS IoT smoke testing, pass `-AwsIotConfigDir` or the equivalent
environment variables consumed by `tools/build_headless_rx671_wifi.ps1`. The
helper generates ignored `src/frtos_config/aws_iot_config_local.h` and injects
`AWS_IOT_USE_LOCAL_CONFIG` only for the build. Do not commit local endpoint,
certificate, or private-key material.

## GitLab hardware CI

The repository pipeline treats the RPi#1 EK-RX671 bench as the `rx671_wifi`
environment. The jobs are serialized by the
`ek-rx671-rpi1-hardware` resource group and routed with the
`dev-ek-rx671` runner tag:

| Job | Host | Purpose |
|---|---|---|
| `build_rx671_wifi` | Windows CC-RX runner | Generate ignored Wi-Fi/AWS headers, run the e2 studio headless build, and publish `.mot`, `.abs`, and `.map` artifacts. |
| `flash_rx671_wifi` | RPi#1 | Verify the exact onboard E2OB and SCI6 devices, then program and verify the image while leaving the target reset for observation. |
| `test_rx671_wifi` | RPi#1 | Open SCI6 first, release the target with RFP CLI, and evaluate startup markers into raw UART and JUnit artifacts. |

`RX671_WIFI_TEST_SCOPE=network` checks `whd_wifi_join=00000000`,
`WHD bring-up done`, and `FreeRTOS+TCP network up`. The optional `mqtt` scope
also checks `AWS TLS=0` and `AWS MQTT=0`. Feature-branch push pipelines remain
build-only; RX671-related merge requests and `main` use the network hardware
scope, while the nightly matrix has separate network and conditional MQTT rows.

The hardware identifiers are maintained in
[hardware-config](https://gitlab.saffti.jp/oss/infra/hardware-config): onboard
E2OB `OBE110024` on J25 USB DEBUG and SCI6 at 921600 bps through
`/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DK0EOSDX-if00-port0`. CI reads
these values from the non-secret group variables
`E2L_SERIAL_EK_RX671_E2OB_RPI1` and `UART_PORT_EK_RX671_SCI6_RPI1`; Wi-Fi and
AWS credentials remain CI/CD inputs and are never committed.

For the current PC-to-board ping baseline, the same helper also temporarily
injects `PLATFORM_WLAN_ALLOW_BUS_TO_SLEEP_DELAY_MS=600000`. The WHD v1.70.0
upstream default is 10 ms; the ping-success run kept the WLAN bus awake because
the 10 ms sleep timing prevented ARP/ICMP traffic from reaching the SDIO
Function 2 CMD53 data path reliably on the RX671 bring-up stack. The project
patch only makes this WHD macro overrideable; the tracked e2 studio project is
restored after the headless build.

## Performance tuning knobs

The tracked SDIO host raises the post-enumeration SDHI clock to the Smart
Configurator high-speed divider (`SDHI_CFG_DIV_HIGH_SPEED`). In the current
RX671 clock profile the SDHI peripheral is derived from PCLKB=60 MHz, so the
tracked high-speed divider is `SDHI_DIV_2` and the measured SDCLK is 30 MHz.
This is the fastest verified in-spec baseline in this project. `SDHI_DIV_1`
would select PCLKB directly and drive SDCLK at 60 MHz; keep that for explicit
overclock experiments only because SDIO High-Speed / Type 1YN and RX671 SDHI
timing limit this interface to 50 MHz. The headless build helper can
temporarily override the divider without editing the project:

```powershell
pwsh -File tools/build_headless_rx671_wifi.ps1 `
  -WifiConfigFile C:\ai\codex\ref\wifi.txt `
  -AwsIotConfigDir C:\ai\codex\secrets\aws-iot\rx671-ek-type1yn-01 `
  -SdioRunClockDiv SDHI_DIV_8
```

`SDHI_DIV_8` is useful as a low-speed fallback and signal-integrity reference.
`SDHI_DIV_4`, `-SdioUseHighSpeedClock`, and `-SdioHighSpeedDrive` remain
measurement settings for A/B tests. The current source exposes
`g_sdio_host_run_clock_div` and `g_sdio_host_run_clock_status` as J-Link-visible
diagnostics; a healthy DIV2 throughput run logs `clkdiv=00000000`.

FreeRTOS+TCP sliding windows are enabled for Wi-Fi throughput work. The current
defaults use 16 MSS for both RX and TX stream buffers, 128 TCP window segment
descriptors, and 48 network buffer descriptors. This is intended to prevent the
TCP layer from becoming the first bottleneck while SDHI clocking and SDIO
transfer CPU cost are measured.

The SDIO CMD53 data path can be built with CPU copy, DTC, or DMACA transfer.
The tracked default is DTC because it completes WHD bring-up, AP JOIN, DHCP,
and the AWS IoT MQTT smoke path on EK-RX671 + Type 1YN. DMACA support is kept
as an experimental build option for the next tuning pass; current DMACA smoke
runs stop during WHD bring-up immediately after `sdio pre-cmd53 ok`, before the
WLAN MAC/firmware strings are printed.

| Build-time value | Meaning | Current status |
|---|---|---|
| `SDIO_HOST_CMD53_XFER_CPU` | PIO copy through `SDBUFR` | Fallback / comparison path |
| `SDIO_HOST_CMD53_XFER_DTC` | DTC transfers between memory and SDHI `SDBUFR` | Default stable path |
| `SDIO_HOST_CMD53_XFER_DMACA` | DMACA transfers between memory and SDHI `SDBUFR` | Experimental, not the default |

The helper exposes the selector through `-SdioCmd53XferEngine` or
`RX671_EK_SDIO_CMD53_XFER_ENGINE`. Direction and threshold overrides are also
available for targeted experiments:
`-SdioCmd53DtcReadEnable`, `-SdioCmd53DtcWriteEnable`,
`-SdioCmd53DtcMinBytes`, `-SdioCmd53DmacaReadEnable`,
`-SdioCmd53DmacaWriteEnable`, `-SdioCmd53DmacaMinBytes`, and
`-SdioCmd53DmacaBlockMode`. The helper waits for e2 studio child build
processes before restoring `.cproject`, so these temporary defines remain in
effect until `make` / `ccrx` / `rlink` finish.

The tracked DTC threshold is 64 bytes. This matches the WHD-programmed Function
2 block size for Type 1YN and avoids falling back to CPU copies for ordinary
64-byte SDIO block transfers. A 10 MiB TCP smoke run with
`SDIO_HOST_CMD53_DTC_MIN_BYTES=64` completed with zero DTC failures and only the
non-Function/bring-up fallback counters remaining.

## Tracealyzer over J-Link RTT

The project links Percepio's official TraceRecorderSource as a submodule at
`../external/TraceRecorderSource`. Project-local configuration lives in
`src/tracealyzer_config`; `src/tracealyzer_freertos_wrap` installs the
Tracealyzer hooks after the RX FreeRTOS port types are visible to CC-RX.
Small wrappers in `src/tracealyzer_recorder` compile only the Recorder core,
FreeRTOS kernel port, and J-Link RTT stream port needed by this project.

`main_task()` starts the recorder with `TRC_START`. This target-start mode is
intentional for the EK-RX671 automation path: the first CLI bring-up confirmed
that the RTT control channel was visible and Tracealyzer CLI could write start
commands to down-buffer 1, but `TRC_START_FROM_HOST` produced 0-byte PSF files
on this integration. With `TRC_START`, both `JLinkRTTLogger` and Tracealyzer
CLI capture recorder data from up-buffer 1 (`TzData`). Use `reset=true` when a
capture should begin from reset/boot; use `reset=false` only when attaching to
an already running image.

The CC-RX map contains `__SEGGER_RTT`; use that address as the Tracealyzer CLI
RTT block address for deterministic connection.

After a headless build, confirm the address with:

```powershell
Select-String `
  -Path Projects\aws_wifi_rx671_ek\e2studio_ccrx\HardwareDebug\aws_wifi_rx671_ek.map `
  -Pattern '__SEGGER_RTT'
```

Example CLI capture:

```powershell
$tracealyzer = 'C:\Program Files\Percepio\Tracealyzer 4\Tracealyzer.exe'
$work = Split-Path $tracealyzer
$out = 'C:\ai\codex\ek-rx671-iot-reference-rx\artifacts\tracealyzer-cli\rx671-wifi-capture.psf'
$conn = 'connection=SEGGER RTT;serial=853004952;usb=true;speed=4000;upbuffer=1;downbuffer=1;debuggerinterface=0;device=R5F5671E;debugger=JLink;blockaddress=0x00043cfc;ti=false;reset=true;sbs=true;numcores=1'

Start-Process -FilePath $tracealyzer `
  -ArgumentList @('stream', '-t', '10', '-c', ('"' + $conn + '"'), '-o', ('"' + $out + '"')) `
  -WorkingDirectory $work -Wait -PassThru

Start-Process -FilePath $tracealyzer `
  -ArgumentList @('export-log', ('"' + $out + '"'), ('"' + $out + '.log.txt"')) `
  -WorkingDirectory $work -Wait -PassThru

Start-Process -FilePath $tracealyzer `
  -ArgumentList @('export-actors', ('"' + $out + '"'), ('"' + $out + '.actors.txt"')) `
  -WorkingDirectory $work -Wait -PassThru
```

The checked value `0x00043cfc` is the `__SEGGER_RTT` address from the verified
2026-06-26 build; always refresh it from the current `.map` file after changing
the project or linker layout. The same bring-up produced valid PSF captures
with both `reset=true` (boot-aligned trace) and `reset=false` (attach to a
running self-start trace). The Tracealyzer analysis commands use positional
arguments (`export-log <input.psf> <output.txt>`), not `-i` / `-o` options.

## WHD linked resource layout

The Type 1YN / CYW43439 WHD resources are staged from pinned source
submodules by `../external/type1yn-blobs/stage_type1yn_blobs.ps1`, then linked
into code flash by CC-RX `-binary` options:

| Resource | Staged file | Linker section | C symbol | Flash address |
|---|---|---|---|---:|
| WLAN firmware | `../external/type1yn-blobs/staging/43439A0.bin` | `TYPE1YN_FW_BLOB` | `g_type1yn_firmware_bin` | `0xFFF00000` |
| NVRAM | `../external/type1yn-blobs/staging/nvram_1yn.bin` | `TYPE1YN_NVRAM_BLOB` | `g_type1yn_nvram_bin` | `0xFFF80000` |
| CLM blob | `../external/type1yn-blobs/staging/43439A0.clm_blob` | `TYPE1YN_CLM_BLOB` | `g_type1yn_clm_blob` | `0xFFF90000` |

The resource provider in `src/whd_port/whd_port_resource.c` exposes those
symbols through the WHD resource callback API. The fixed section addresses keep
the layout compatible with earlier primitive SDIO experiments, but the normal
J-Link load path now only needs the generated `.mot` file.

These fixed addresses are not safe for dual-bank OTA as-is. See
[`OTA_FLASH_LAYOUT.md`](OTA_FLASH_LAYOUT.md) for the deterministic
PASS/FAIL/UNKNOWN gate and the unresolved bootloader/layout conditions.

Example J-Link Commander flow:

```text
device R5F5671E
si JTAG
speed 4000
jtagconf -1 -1
connect
loadfile <repo_root>\Projects\aws_wifi_rx671_ek\e2studio_ccrx\HardwareDebug\aws_wifi_rx671_ek.mot
r
g
q
```

Use `-SelectEmuBySN 853004952` when both the external J-Link Compact PLUS and
another SEGGER probe are connected.

The repository root also provides a thin helper that emits the same Commander
script into a temporary file:

```powershell
pwsh -File tools/load_rx671_wifi_jlink.ps1 -Run
```

The optional `-FirmwareBin`, `-NvramBin`, and `-ClmBlob` arguments remain
available for manual override/debug loads, but the normal project image already
contains the staged resources.

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

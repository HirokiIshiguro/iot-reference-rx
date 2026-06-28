# aws_wifi_rx671_ek

This project is the EK-RX671 + Murata Type 1YN Wi-Fi staging project for the
`iot-reference-rx` FreeRTOS/AWS middleware baseline.

The first committed state intentionally starts from the proven WHD bring-up
tree:

- EK-RX671 SDHI + in-house `r_sdio_rx`
- Infineon WHD v1.70.0 through a project-local submodule
- Type 1YN firmware boot, MAC read, AP scan, WPA2-PSK JOIN, FreeRTOS+TCP, and
  AWS IoT MQTT smoke verified on hardware
- No AP credentials committed; Type 1YN WHD blob source revisions are pinned as
  submodules and generated staging files are ignored

The e2 studio project name is `aws_wifi_rx671_ek`.

## Layout

| Path | Purpose |
|---|---|
| `e2studio_ccrx/` | EK-RX671 e2 studio CCRX application project |
| `external/wifi-host-driver/` | WHD v1.70.0 submodule |
| `external/type1yn-blobs/` | Pinned source submodules and ignored staging for Type 1YN firmware/NVRAM/CLM blobs |
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
  - COM3 was identified as the SEGGER CDC interface (`VID_1366/PID_1024`) on
    the tested host and did not receive the RX671 SCI6 boot log.
  - COM5 was identified as the EK-RX671 FTDI USB-serial path
    (`VID_0403/PID_6015`) and received the SCI6 boot/WHD/FreeRTOS log.
- WHD WLAN bus sleep delay: kept awake for the bring-up run
  (`PLATFORM_WLAN_ALLOW_BUS_TO_SLEEP_DELAY_MS=600000`)
- WHD bring-up: `whd_wifi_on`, AP scan, WPA2-PSK JOIN, and MAC read succeeded
- FreeRTOS+TCP: DHCP/network-up reached after Wi-Fi JOIN; PC-to-board ping was
  verified on the earlier RX671 Wi-Fi baseline
- AWS IoT smoke: TLS connection to AWS IoT Core succeeded and the MQTT smoke
  task completed with `AWS MQTT=0`
- J-Link Commander observation:
  - SDHI SDIO in-band interrupt counters increased during traffic
  - WHD RX counters increased during ping traffic
  - ICMP RX counter reached 4 for a 4-packet ping run
  - RX network buffers were allocated and submitted to the FreeRTOS+TCP IP task

The baseline is intended to remain on a dedicated development branch until the
Wi-Fi throughput path, provisioning, TSIP, and boot-loader variants are
separated into reviewable milestones.

## TCP Throughput Tuning Notes

The current throughput tuning baseline uses the interrupt-driven WHD path and
the SDIO CMD53 DTC transfer engine. With the SD sniffer board installed, the
most stable high-speed measurement starts WHD bring-up at `SDHI_DIV_4` and
raises the SDHI clock to `SDHI_DIV_2` after WHD JOIN/control-plane setup.
With the current RX671 clock tree, SDHI is derived from PCLKB=60 MHz, so
`SDHI_DIV_2` means SDCLK=30 MHz. `SDHI_DIV_1` would drive SDCLK at 60 MHz and
is kept out of the tracked baseline because SDIO High-Speed / Type 1YN and the
RX671 SDHI AC timing all cap this path at 50 MHz. Reaching the top of the spec
should be a separate clock-profile experiment, for example PCLKB near 48-50 MHz
with the PCLKB/1 divider.

The headless build helper can also generate an ignored TCP smoke-test header so
these parameters are reproducible without committing local network settings.
Dedicated TCP/TLS benchmark projects and measurement write-ups should be kept
under the EK-RX671 benchmark repository, starting with
`oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls`.

Representative hardware settings used during the first tuning pass:

- `-SoftIrqPollMs 0`
- `-SdioRunClockDiv SDHI_DIV_4`
- `-SdioPostWifiOnClockDiv 0`
- `-SdioCmd53XferEngine 1`
- `-SdioCmd53DtcMinBytes 64` (tracked default)
- `-FreeRtosHeapSizeKb 256`
- `-TcpWinSegCount 128`
- `-NetworkBufferDescriptors 48`
- `-WhdPortBufferCount 4`
- `-WhdNetworkProtocolDiag 0`
- `-WhdNetworkReadyCheckEachTx 0`
- `-IpTraceProtocolDiag 0`
- `-TcpThroughputTxBufferBytes 65536`
- `-TcpThroughputRxBufferBytes 65536`
- `-TcpThroughputTxWindowMss 44`
- `-TcpThroughputRxWindowMss 44`
- `-TcpThroughputSinkFillPattern 0`

The FreeRTOS heap default is 256 KiB for this project. A 224 KiB heap was
rejected for the throughput baseline because the 64 KiB socket-buffer / 44-MSS
window SOURCE run exhausted the heap around 40 KiB of received payload and
entered `vApplicationMallocFailedHook`. With 256 KiB, the same 10 MiB SOURCE
run completed and left about 18 KiB minimum free heap in the measured run.
For larger TCP buffer/window A/B tests, build SINK and SOURCE as separate
throughput images. Packing both directions plus 64 KiB socket buffers, 44-MSS
windows, more than 48 network buffers, and the 256 KiB heap into one image can
overflow RX671 RAM.

Earlier 10 MiB plain TCP results with DTC-backed CMD53 transfers before the
SDHI clock tuning:

| Application chunk setting | RX671 to PC | PC to RX671 | Notes |
|---|---:|---:|---|
| shared `5840` bytes | 22.9 Mbps | 23.8 Mbps | Balanced baseline |
| shared `8760` bytes | 23.1 Mbps | 23.2 Mbps | Larger TX request without RX regression |
| TX `14600` bytes / RX `5840` bytes | 23.1-23.2 Mbps | 23.5-24.0 Mbps | Earlier stable split-chunk baseline |

The split TX/RX chunk setting is useful because the RX671-to-PC send path
benefits from larger `FreeRTOS_send()` requests, while the PC-to-RX671 receive
path stayed more stable with a smaller `FreeRTOS_recv()` request size. Static
buffers above the current split-chunk baseline need a separate RAM placement or
allocation strategy before they can be treated as a stable tuning point.

Follow-up measurements on 2026-06-23 rechecked the lower SDIO layers after the
WHD buffer allocator change. With the direct EK-RX671 to Type 1YN SDIO wiring
used for this run, `SDHI_DIV_2` completed AP JOIN, DHCP, and the TCP smoke test
with no DTC failures. Earlier DIV4 failures were tied to an experimental
PORTD high-speed-drive run and are not treated as the baseline result.

SDHI divider mapping for the current clock profile:

| Setting | SDCLK with PCLKB=60 MHz | Use |
|---|---:|---|
| `SDHI_DIV_8` | 7.5 MHz | Low-speed fallback and signal-integrity reference |
| `SDHI_DIV_4` | 15 MHz | Intermediate A/B point |
| `SDHI_DIV_2` | 30 MHz | Verified high-speed run clock after WHD bring-up |
| `SDHI_DIV_1` / PCLKB | 60 MHz | Out of SDIO/Type 1YN/RX671 50 MHz limit; overclock experiment only |

Representative 10 MiB plain TCP results:

| SDIO setting | Peer | RX671 to host | Host to RX671 | CPU load | Status |
|---|---|---:|---:|---|---|
| CPU copy, `SDHI_DIV_8` | PC | 14.48 Mbps | 15.03 Mbps | n/a | Stable low-speed reference |
| DTC, `SDHI_DIV_8`, 512-byte threshold | PC | 14.40 Mbps | 14.11 Mbps | n/a | Stable, but many small-transfer fallbacks |
| DTC, `SDHI_DIV_8`, 64-byte threshold | PC | 14.47 Mbps | 15.43 Mbps | n/a | Stable low-speed fallback; small-transfer fallback removed |
| DTC, `SDHI_DIV_2`, 64-byte threshold | PC | 38.2-38.5 Mbps | 30.2-32.0 Mbps | n/a | PC-facing reference; do not mix with RPi baseline |
| DTC, `SDHI_DIV_4` bring-up then `SDHI_DIV_2`, 64-byte threshold | RPi#2 wired | 35.231 Mbps | 32.338 Mbps | SINK about 100%; SOURCE about 88.6% | Current SDHI IRQ + sniffer-board baseline |
| DMACA, `SDHI_DIV_8`, 64-byte threshold | n/a | n/a | n/a | n/a | Experimental; stalled before WLAN firmware/MAC log |

Tracealyzer CLI diagnostic runs on 2026-06-28, with the SD sniffer board
installed and the two-stage SDHI clock described above:

| Direction | LANBENCH peer | Chunk / buffer condition | Throughput | Transfer-window CPU load | Dominant actor |
|---|---|---|---:|---:|---|
| RX671 to host | RPi#2 wired `192.168.10.203:5001` | TX chunk 14600 bytes, 64 KiB socket buffers, 44-MSS windows, source verification disabled | 35.231 Mbps board-side / 35.191 Mbps pcap | about 100% busy | WHD 62.6%, IP-Task 35.2%, TCPTHR 2.1% |
| Host to RX671 | RPi#2 wired `192.168.10.203:5001` | RX chunk 5840 bytes, 64 KiB socket buffers, 44-MSS windows, source verification disabled | 32.338 Mbps board-side / 32.365 Mbps pcap dedup | about 88.6% busy | WHD 60.1%, IP-Task 25.1%, TCPTHR 3.5%, IDLE 11.3% |

The 2026-06-28 run shows that the current SDHI IRQ path is usable as the main
performance path. RX671-to-host traffic is CPU-saturated by the combined WHD
SDIO TX and FreeRTOS+TCP path. Host-to-RX671 traffic still has CPU headroom, but
the pcap shows bursty delivery and occasional receive-window pressure, so the
next tuning pass should focus on WHD/SDPCM packet handling and FreeRTOS+TCP
buffer pressure before changing the SDHI clock again.

The 64-byte DTC threshold is now the default because Type 1YN/WHD programs a
64-byte Function 2 block size and this setting moved nearly all Function 2
block transfers out of the CPU fallback path without introducing DTC errors.
`SDHI_DIV_4`, `-SdioUseHighSpeedClock`, and `-SdioHighSpeedDrive` remain useful
signal-margin experiments. `SDHI_DIV_1` should not be used as a normal tuning
target with PCLKB=60 MHz; it exceeds the 50 MHz SDIO/Type 1YN/RX671 limit.
If more SDIO clock margin is needed after `SDHI_DIV_2`, introduce a separate
clock profile that keeps SDCLK at or below the specification limit.

Clock-limit references checked for this decision:

- SDIO Simplified Specification Version 3.00: SDIO High-Speed mode is up to
  50 MHz at 3.3 V signaling.
- Murata Type 1YN data sheet: SDIO High Speed Mode `fPP` is specified up to
  50 MHz.
- RX671 hardware manual `r01uh0899jj0120-rx671.pdf`: SDHI clock is generated
  from PCLKB, `SDCLKCR=0xFF` selects PCLKB directly, and SDHI_CLK output cycle
  time `tPP(SD)` is 20 ns minimum.

The WHD port buffer pool now uses an O(1) free-stack allocator instead of a
linear slot search. Keep these J-Link/Tracealyzer symbols in the measurement
notes when changing TCP window, network-buffer, and SDIO transfer settings:

- `g_whd_port_buffer_max_in_use`
- `g_whd_port_buffer_current_in_use`
- `g_whd_port_buffer_alloc_temp_fail_count`
- `g_whd_port_buffer_alloc_perm_fail_count`
- `g_whd_port_buffer_wait_loop_count`

The TCP throughput smoke task also emits these values on COM5 as
`[TCPTHR] whdbuf ...` lines before and after each direction test.

When Tracealyzer is enabled, the same task also emits the compact `TCPTHR` User
Event channel. The result line uses `res m=<mode> b=<bytes> ms=<elapsed>
k=<Mbps_x1000>` so `export-log` can be parsed without relying on UART output.
The payload-transfer window is bounded by `phase=12` and `res m=2` for SOURCE
tests, which makes CPU-load attribution from Tracealyzer CLI repeatable.

If the temporary failure or wait counters increase during a throughput run,
repeat the build with a larger `-WhdPortBufferCount` before changing the
FreeRTOS+TCP window again. The WHD source remains unmodified; these knobs only
change the RX671 project-local WHD port layer.

## Build

Use the headless build helper from the repository root. It initializes the
required submodules, applies the WHD CC-RX patch if needed, validates/stages the
Type 1YN firmware/NVRAM/CLM blobs, and builds the e2 studio project:

```powershell
pwsh -File tools/build_headless_rx671_wifi.ps1
```

For the hardware-verified AP JOIN / ping baseline, keep the credentials outside
git and let the headless build script generate the ignored local header:

```powershell
pwsh -File tools/build_headless_rx671_wifi.ps1 `
  -WifiConfigFile C:\ai\codex\ref\wifi.txt `
  -AwsIotConfigDir C:\ai\codex\secrets\aws-iot\rx671-ek-type1yn-01 `
  -SoftIrqPollMs 0 `
  -WlanAllowBusSleepDelayMs 600000
```

Use `-SoftIrqPollMs 0` for the performance baseline so WHD is woken by the
SDHI in-band IOIRQ path. A non-zero SoftIRQ poll period is useful only as a
bring-up fallback or for A/B comparison against the interrupt-driven path.

The Wi-Fi config file can be either a single whitespace-separated line:

```text
<ssid> <passphrase>
```

or key/value lines:

```text
SSID=<ssid>
PASS=<passphrase>
```

The script writes
`e2studio_ccrx/src/whd_join_config_local.h`, which is ignored by git, and
temporarily injects `WHD_JOIN_USE_LOCAL_CONFIG` into `.cproject` only for the
headless build. The tracked e2 studio project is restored after the build, so
re-run this command after a clean checkout or clean workspace.

When `-AwsIotConfigDir` is supplied, the script also writes ignored
`e2studio_ccrx/src/frtos_config/aws_iot_config_local.h` and temporarily injects
`AWS_IOT_USE_LOCAL_CONFIG`. The directory is expected to contain the local AWS
IoT endpoint/thing metadata plus the device certificate and private key. These
credentials must remain outside git.

The same helper also temporarily injects
`PLATFORM_WLAN_ALLOW_BUS_TO_SLEEP_DELAY_MS=600000`, matching the hardware run
where PC-to-board ping succeeded. The upstream WHD default is 10 ms, and that
allowed the WLAN bus to sleep before ARP/ICMP traffic reached the SDIO Function
2 data path on this bring-up branch. Pass `-WlanAllowBusSleepDelayMs -1` only
when intentionally testing the unmodified WHD sleep timing.

For a local plain TCP throughput smoke test, start the common Go LANBENCH
server on the wired RPi#2 path, then add the TCP options to the same headless
build invocation. The generated
`e2studio_ccrx/src/frtos_config/tcp_throughput_config_local.h` is ignored by
git. The smoke task speaks the LANBENCH command protocol: `SINK <bytes>` sends
the deterministic LANBENCH payload to the host and reads the host `OK` line,
while `SOURCE <bytes>` reads the host `DATA <bytes>` header, receives the
payload, then reads the host `OK` line.

```powershell
pwsh -File tools/build_headless_rx671_wifi.ps1 `
  -WifiConfigFile C:\ai\codex\ref\wifi.txt `
  -SkipAwsIotConfig `
  -SoftIrqPollMs 0 `
  -WlanAllowBusSleepDelayMs 600000 `
  -WlanDisablePowersave `
  -FreeRtosHeapSizeKb 256 `
  -TcpWinSegCount 128 `
  -NetworkBufferDescriptors 48 `
  -WhdPortBufferCount 4 `
  -WhdNetworkProtocolDiag 0 `
  -WhdNetworkReadyCheckEachTx 0 `
  -IpTraceProtocolDiag 0 `
  -SdioRunClockDiv SDHI_DIV_4 `
  -SdioPostWifiOnClockDiv 0 `
  -SdioCmd53XferEngine 1 `
  -SdioCmd53DtcMinBytes 64 `
  -TcpThroughputEnable `
  -TcpThroughputHost 192.168.10.203 `
  -TcpThroughputPort 5001 `
  -TcpThroughputMode both `
  -TcpThroughputBytes 10485760 `
  -TcpThroughputChunkBytes 5840 `
  -TcpThroughputTxChunkBytes 14600 `
  -TcpThroughputRxChunkBytes 5840 `
  -TcpThroughputTxBufferBytes 65536 `
  -TcpThroughputRxBufferBytes 65536 `
  -TcpThroughputTxWindowMss 44 `
  -TcpThroughputRxWindowMss 44 `
  -TcpThroughputSinkFillPattern 0
```

Expected outputs:

- `e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.mot`
- `e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.abs`
- `e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.x`

The generated `.mot` includes the Type 1YN WHD resources linked into code flash
by CC-RX `-binary` options. Load the image with J-Link Commander:

```powershell
pwsh -File tools/load_rx671_wifi_jlink.ps1 -Run
```

The loader still accepts `-FirmwareBin`, `-NvramBin`, and `-ClmBlob` for
manual override/debug runs, but they are not required for the normal build.

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

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

The current throughput tuning baseline uses the interrupt-driven WHD path,
SDHI high-speed clock, and the SDIO CMD53 DTC transfer engine. The headless
build helper can also generate an ignored TCP smoke-test header so these
parameters are reproducible without committing local network settings.

Representative hardware settings used during the first tuning pass:

- `-SoftIrqPollMs 0`
- `-SdioUseHighSpeedClock`
- `-SdioCmd53XferEngine 1`
- `-FreeRtosHeapSizeKb 256`
- `-TcpWinSegCount 240`
- `-NetworkBufferDescriptors 64`
- `-TcpThroughputTxBufferBytes 65536`
- `-TcpThroughputRxBufferBytes 65536`
- `-TcpThroughputTxWindowMss 44`
- `-TcpThroughputRxWindowMss 44`

Representative 10 MiB plain TCP results with DTC-backed CMD53 transfers:

| Application chunk setting | RX671 to PC | PC to RX671 | Notes |
|---|---:|---:|---|
| shared `5840` bytes | 22.9 Mbps | 23.8 Mbps | Balanced baseline |
| shared `8760` bytes | 23.1 Mbps | 23.2 Mbps | Larger TX request without RX regression |
| TX `14600` bytes / RX `5840` bytes | 23.1-23.2 Mbps | 23.5-24.0 Mbps | Current stable split-chunk baseline |

The split TX/RX chunk setting is useful because the RX671-to-PC send path
benefits from larger `FreeRTOS_send()` requests, while the PC-to-RX671 receive
path stayed more stable with a smaller `FreeRTOS_recv()` request size. Static
buffers above the current split-chunk baseline need a separate RAM placement or
allocation strategy before they can be treated as a stable tuning point.

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

For a local plain TCP throughput smoke test, add the TCP options to the same
headless build invocation. The generated
`e2studio_ccrx/src/frtos_config/tcp_throughput_config_local.h` is ignored by
git:

```powershell
pwsh -File tools/build_headless_rx671_wifi.ps1 `
  -WifiConfigFile C:\ai\codex\ref\wifi.txt `
  -SkipAwsIotConfig `
  -SoftIrqPollMs 0 `
  -WlanAllowBusSleepDelayMs 600000 `
  -WlanDisablePowersave `
  -FreeRtosHeapSizeKb 256 `
  -TcpWinSegCount 240 `
  -NetworkBufferDescriptors 64 `
  -SdioUseHighSpeedClock `
  -SdioCmd53XferEngine 1 `
  -TcpThroughputEnable `
  -TcpThroughputHost 192.168.10.105 `
  -TcpThroughputPort 5004 `
  -TcpThroughputMode both `
  -TcpThroughputBytes 10485760 `
  -TcpThroughputChunkBytes 5840 `
  -TcpThroughputTxChunkBytes 14600 `
  -TcpThroughputRxChunkBytes 5840 `
  -TcpThroughputTxBufferBytes 65536 `
  -TcpThroughputRxBufferBytes 65536 `
  -TcpThroughputTxWindowMss 44 `
  -TcpThroughputRxWindowMss 44
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

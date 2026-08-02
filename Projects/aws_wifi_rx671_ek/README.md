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

The project is the maintained EK-RX671 + Type 1YN Wi-Fi software baseline.
The checked-in e2 studio project remains a normal linear `bank.single`
application, while the OTA helper temporarily produces a credential-only
provisioner and signed dual-bank baseline/candidate images. TSIP and TLS 1.3
OTA remain separate milestones.

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
- Software TLS 1.2 AWS IoT OTA: blank Data Flash initialization, SCI6 runtime
  provisioning, baseline `0.1.0` installation, candidate `0.1.1` download,
  activation, bank swap, reboot, self-test, image acceptance, OTA success
  reporting, and AWS cleanup were verified by pipeline #9584 at source SHA
  `d505b3fd`
- Formal firmware is built without Wi-Fi credential inputs and passes the
  configured-value artifact scan. AWS IoT endpoint/Thing/certificate/private
  key inputs are supplied only to the later hardware provisioner job; runtime
  values reside in LittleFS on Data Flash and survive code-flash update and
  bank swap
- J-Link Commander observation:
  - SDHI SDIO in-band interrupt counters increased during traffic
  - WHD RX counters increased during ping traffic
  - ICMP RX counter reached 4 for a 4-packet ping run
  - RX network buffers were allocated and submitted to the FreeRTOS+TCP IP task

The baseline is intended to remain on a dedicated development branch until the
Wi-Fi throughput path, provisioning, TSIP, and boot-loader variants are
separated into reviewable milestones.

## Tracealyzer Capture Policy

The RX671 Wi-Fi project defaults Tracealyzer to a CPU-load low-noise profile:

- `TRACEALYZER_CPU_LOAD_LOW_NOISE = 1`
- scheduling-only recorder mode
- user, ISR, ready, memory, and OS tick events disabled
- J-Link RTT up-buffer kept at 8 KiB
- RTT write mode remains `SEGGER_RTT_MODE_NO_BLOCK_SKIP`

The goal is to make high-throughput TCP captures usable only when the
Tracealyzer Live Stream "Missed Events" counter stays at zero for the full
measurement interval. Keep `NO_BLOCK_SKIP` so an unattached Tracealyzer host
cannot stall the target firmware. For SDIO or WHD event-flow debugging, build
with `TRACEALYZER_CPU_LOAD_LOW_NOISE=0` and treat the resulting CPU-load graph
as diagnostic-only unless missed events still remain zero.

Do not increase the RTT up-buffer casually on RX671. 12 KiB, 16 KiB, and 32 KiB
all overflowed the current linker RAM layout in this project; the default
low-noise profile therefore reduces recorder event volume instead of spending
additional RAM on a larger RTT FIFO.

## TCP Throughput Tuning Notes

The current throughput tuning baseline uses the interrupt-driven WHD path, the
Smart Configurator high-speed SDHI run clock (`SDHI_CFG_DIV_HIGH_SPEED`, which
maps to `SDHI_DIV_2` in this project), and the SDIO CMD53 DTC transfer engine.
With the current RX671 clock tree, SDHI is derived from PCLKB=60 MHz, so this
means SDCLK=30 MHz. `SDHI_DIV_1` would drive SDCLK at 60 MHz and is kept out of
the tracked baseline because SDIO High-Speed / Type 1YN and the RX671 SDHI AC
timing all cap this path at 50 MHz. Reaching the top of the spec should be a
separate clock-profile experiment, for example PCLKB near 48-50 MHz with the
PCLKB/1 divider.

The headless build helper can also generate an ignored TCP smoke-test header so
these parameters are reproducible without committing local network settings.

Representative hardware settings used during the first tuning pass:

- `-SoftIrqPollMs 0`
- `-SdioRunClockDiv SDHI_DIV_2` (or omit this option and use the tracked default)
- `-SdioCmd53XferEngine 1`
- `-SdioCmd53DtcMinBytes 64` (tracked default)
- `-FreeRtosHeapSizeKb 256`
- `-TcpWinSegCount 128`
- `-NetworkBufferDescriptors 48`
- `-WhdPortBufferCount 16` (default; increase for buffer-pressure A/B tests)
- `-TcpThroughputTxBufferBytes 65536`
- `-TcpThroughputRxBufferBytes 65536`
- `-TcpThroughputTxWindowMss 44`
- `-TcpThroughputRxWindowMss 44`

The FreeRTOS heap default is 256 KiB for this project. A 224 KiB heap was
rejected for the throughput baseline because the 64 KiB socket-buffer / 44-MSS
window SOURCE run exhausted the heap around 40 KiB of received payload and
entered `vApplicationMallocFailedHook`. With 256 KiB, the same 10 MiB SOURCE
run completed and left about 18 KiB minimum free heap in the measured run.
For larger TCP buffer/window A/B tests, build SINK and SOURCE as separate
throughput images. Packing both directions plus 64 KiB socket buffers, 44-MSS
windows, more than 48 network buffers, and the 256 KiB heap into one image can
overflow RX671 RAM.

Representative 10 MiB plain TCP results with DTC-backed CMD53 transfers before
the SDHI clock increase:

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
| `SDHI_DIV_2` | 30 MHz | Current tracked default and verified throughput baseline |
| `SDHI_DIV_1` / PCLKB | 60 MHz | Out of SDIO/Type 1YN/RX671 50 MHz limit; overclock experiment only |

Representative 10 MiB plain TCP results:

| SDIO setting | RX671 to PC | PC to RX671 | Status |
|---|---:|---:|---|
| CPU copy, `SDHI_DIV_8` | 14.48 Mbps | 15.03 Mbps | Stable reference |
| DTC, `SDHI_DIV_8`, 512-byte threshold | 14.40 Mbps | 14.11 Mbps | Stable, but many small-transfer fallbacks |
| DTC, `SDHI_DIV_8`, 64-byte threshold | 14.47 Mbps | 15.43 Mbps | Stable low-speed fallback; small-transfer fallback removed |
| DTC, `SDHI_DIV_2`, 64-byte threshold | 38.2-38.5 Mbps | 30.2-32.0 Mbps | Current tracked default; `clkdiv=0`, DTC failures 0 |
| DMACA, `SDHI_DIV_8`, 64-byte threshold | n/a | n/a | Experimental; stalled before WLAN firmware/MAC log |
| CPU copy, `SDHI_DIV_4`, PORTD high-speed drive | n/a | n/a | Failed in `whd_wifi_on()`; `clkdiv=1`, `dscr2=FC`, `f2retry=2` |
| DTC, `SDHI_DIV_4`, PORTD high-speed drive | n/a | n/a | Failed in `whd_wifi_on()`; `clkdiv=1`, `xfer=1`, `dscr2=FC`, `f2retry=6` |

Tracealyzer CLI diagnostic run on 2026-06-27:

| Direction | LANBENCH peer | Chunk / buffer condition | Throughput | Transfer-window CPU load | Dominant actor |
|---|---|---|---:|---:|---|
| Host to RX671 | RPi#2 wired `192.168.10.203:5001` | host source chunk 4096 bytes, RX chunk 4096 bytes, 64 KiB socket buffers, 44-MSS windows | 15.857 Mbps board-side / 16.631 Mbps host-side | 96.96% busy | WHD 85.59%, IP-Task 9.57% |

The 2026-06-27 run was taken with J-Link and the SD sniffer board restored, so
it is a diagnostic point for CPU-load attribution rather than a replacement for
the direct-wiring high-speed baseline above. It confirmed that the current
SOURCE receive path is CPU-bound mainly in the WHD task while the application
throughput task itself consumes only about 1.6% of the transfer window. This
points the next tuning pass toward WHD/SDPCM packet handling, FreeRTOS+TCP
buffer pressure, and LANBENCH chunk/window alignment before changing the SDHI
clock again.

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
  -WhdPortBufferCount 16 `
  -SdioRunClockDiv SDHI_DIV_2 `
  -SdioCmd53XferEngine 1 `
  -SdioCmd53DtcMinBytes 64 `
  -TcpThroughputEnable `
  -TcpThroughputHost 192.168.10.203 `
  -TcpThroughputPort 5001 `
  -TcpThroughputMode source `
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

## RX671 OTA artifact build

The checked-in e2 studio project remains the normal linear,
`bank.single` application. A normal build therefore keeps its existing
1 MiB FWUP area and linker layout; do not save the OTA-only settings into the
project.

The dedicated artifact helper temporarily applies the following OTA profile:

- a credential-only `bank.single` provisioner with
  `RX671_OTA_PROVISIONER_ENABLE=1`; this image initializes LittleFS/KVS and
  leaves SCI6 exclusively in the shared `conf set` / `commit` CLI;
- `bank.dual` and `BSP_CFG_CODE_FLASH_BANK_MODE=0`;
- a 768 KiB (`0x000C0000`) install area;
- the application and all Type 1YN resources at main-bank offset `+0x300`
  (`0xFFF00300`), after the FWUP header and v2 descriptor;
- `PFRAM2=RPFRAM2`, with `PFRAM2` in the main image group; and
- explicit `APP_VERSION_*` defines for baseline `0.1.0` and candidate `0.1.1`;
  and
- `RX671_OTA_RUNTIME_ENABLE=1`, which starts the MQTT Agent and OTA demo after
  WHD JOIN and FreeRTOS+TCP network-up, using credentials already committed to
  LittleFS/KVS.

### Provisioner first-boot logging boundary

Blank Data Flash is a normal first-boot state. `lfs_mount()` reports its
all-`0xFF` metadata as `LFS_ERR_CORRUPT`, and LittleFS emits
`LFS_ERROR("Corrupted dir pair ...")`. The later `conf commit` path also uses
the dev-mode PKCS #11 helper, whose convenience messages use `configPRINTF`.
In the one-shot provisioner both outputs would otherwise route to
`vLoggingPrint()` before `xLoggingTaskInitialize()` has created its queue,
reaching `configASSERT(xQueue)` at
`iot_logging_task_dynamic_buffers.c:587`.

The temporary provisioner `.cproject` therefore adds `LFS_NO_DEBUG`,
`LFS_NO_WARN`, `LFS_NO_ERROR`, and `LIBRARY_LOG_LEVEL=LOG_NONE` together with
`RX671_OTA_PROVISIONER_ENABLE=1`. The same provisioner define suppresses the
dev-mode key helper's `configPRINTF` messages. These settings apply only to the
provisioner build and are restored byte-for-byte afterwards; the checked-in
project and baseline/candidate profiles retain their normal logging. LittleFS
still returns `LFS_ERR_CORRUPT`, allowing `littlFs_init()` to format and mount
blank Data Flash before SCI6 writes and commits the runtime CSPs to
LittleFS/KVS.

### Provisioner CLI stack boundary

The RX671 `configMINIMAL_STACK_SIZE` is 140 `StackType_t` words. The former
`configMINIMAL_STACK_SIZE * 6U` CLI setting therefore allocated only 840 words,
or 3360 bytes on the RX600v2 port. CC-RX frame data for the private-key commit
path already totals at least 3392 bytes before return addresses and indirect
calls are counted. One avoidable contributor was the 884-byte
`KeyValueStore_t` being passed by value into `vDevModeKeyPreProvisioning()`.

Hardware A/B testing with the same provisioner source reproduced the boundary:
the 3360-byte task stopped while importing the device private key, while a
6720-byte task completed the same certificate/private-key commit. The
provisioner now passes the key store as `const KeyValueStore_t *` and uses an
explicit 2048-word (8192-byte) CLI stack. This dynamic stack is allocated only
when `RX671_OTA_PROVISIONER_ENABLE=1`; normal network and OTA runtime profiles
do not create the provisioner CLI task.

### Provisioner-to-boot-loader handoff boundary

The credential-only provisioner is a normal `bank.single` image, so its code
occupies the same two Code Flash install areas whose first bytes the dual-bank
boot loader interprets as lifecycle state. Programming only the boot-loader MOT
does not erase provisioner records outside the MOT. Without an explicit handoff,
the boot loader therefore sees non-blank, unknown lifecycle bytes and attempts
an integrity check on the provisioner instead of requesting the baseline RSU.

After the LittleFS/KVS commit and before programming the boot loader, the host
uses RFP `-range` with `-erase` for exactly these two 768 KiB install areas:

- `0xFFE00000-0xFFEBFFFF` (temporary install area); and
- `0xFFF00000-0xFFFBFFFF` (execute install area).

This is not `-erase-chip`. It preserves Data Flash/LittleFS, flash options, the
boot-loader mirror at `0xFFEC0000-0xFFEFFFFF`, and the boot loader at
`0xFFFC0000-0xFFFFFFFF`. The following boot-loader MOT programming leaves the
target in reset so the test can open SCI6 before release.

The boot loader prints the LittleFS key-load prefix before calling LittleFS, so
LittleFS diagnostics can appear before its trailing `found.`. The HIL monitor
requires the key-load prefix and `found.` as two ordered markers and still
fails immediately on the `not found; refusing to boot.` marker. This preserves
the key-loading proof without assuming that a blocking operation produces one
atomic UART line.

### Baseline UART transfer flow-control boundary

The boot loader receives and programs the 768 KiB baseline RSU in 32 KiB Code
Flash units using two 32 KiB SCI buffers. An unrestricted 921600-bps host
stream can lap that flash state machine: hardware diagnosis reproduced 23 of
24 completed writes, stopping at `736/768KB` while the final receive buffer
remained incomplete.

RX671 runs this path at ICLK 120 MHz / PCLKB 60 MHz, whereas the RX72N
reference uses ICLK 240 MHz / PCLKB 60 MHz with the same 921600-bps UART,
SCI priority 15, Code Flash BGO, and double-buffer design. RX671 therefore has
half as many CPU cycles per received byte; the RX72N continuous-stream timing
is not a safe cross-target contract.

The host therefore sends one 32 KiB block, waits for the boot loader's
`(N/768KB)` progress line, and only then sends the next block. That line is
emitted after the corresponding flash callback completes, so it acts as an
explicit application-level ACK rather than an arbitrary timing delay. The last
block must reach `(768/768KB)`, after which the independent `completed
installing firmware`, ECDSA scheme, integrity `OK`, lifecycle update, reset,
and application-jump markers remain mandatory.

The OTA-only memory profile uses a 208 KiB FreeRTOS heap, a 32 KiB TCP receive
stream, 24 network buffer descriptors, an 8 KiB MQTT Agent network buffer,
eight WHD port buffers, and a 4 KiB `mqttFileDownloader` block. It requests one
block at a time, uses two 8 KiB static OTA event buffers, and tracks all 192
blocks needed by the maximum 785,920-byte transfer payload. The TCP stream
is intentionally smaller than the benchmark-oriented 64 KiB default: the
128 KiB heap profile reached AWS IoT TCP establishment, then exhausted its
allocator while entering TLS and stopped the scheduler. The larger heap and
OTA-sized stream preserve RAM headroom for mbedTLS, PKCS #11, and the OTA Agent.
The formal software OTA profile also pins both the mbedTLS minimum and maximum
to TLS 1.2, matching the focused CI contract instead of merely asking the host
analyzer to expect that version.

The shared MQTT wrapper uses task-notification index 2 and the synchronous
MQTT Agent subscribe path uses index 3. RX671 therefore fixes
`configTASK_NOTIFICATION_ARRAY_ENTRIES` at 4 in both `FreeRTOSConfig.h` and the
Smart Configurator `.scfg` source of truth, with compile-time guards in the
shared MQTT sources. This is a shared MQTT contract rather than an OTA-only
override; the failure evidence and RAM boundary are recorded in
[`OTA_FLASH_LAYOUT.md`](e2studio_ccrx/OTA_FLASH_LAYOUT.md).

The OTA demo also subscribes to the AWS-managed cancellation event
`$aws/events/job/<jobId>/cancellation_in_progress`. The normal device policy is
left unchanged: the focused pipeline creates a short-lived policy that grants
only `iot:Subscribe` on that exact `topicfilter` ARN and `iot:Receive` on the
matching exact `topic` ARN, attaches it to the already selected certificate,
verifies the document and attachment, and then detaches and deletes it in the
independent cleanup job. No `#` or `*` wildcard is used, and no publish right is
added. The policy name and Job ID are deterministic parts of the preflight
journal, so a name collision or ownership mismatch fails closed. CI waits the
documented upper policy-propagation bound of 480 seconds before starting HIL.
Cleanup accepts only `DeleteConflictException` as a transient detach condition,
retries it for at most 300 seconds, and finally requires policy absence.

Pipelines #9577 and #9578 at source SHA `0d879d37` exposed a separate startup
boundary and are retained as failure diagnostics, not success evidence. #9577
continued with a fallback MAC and FreeRTOS+TCP static fallback after the real
station MAC/DHCP path failed, then repeated DNS failures. #9578 stopped in
`whd_wifi_on` after the F2 retry/recovery path. Source SHA `8d22109f` therefore
requires a nonzero unicast WHD station MAC and a real DHCP lease; static fallback
never makes OTA ready. Firmware emits the exact
`RX671 OTA startup ready: WHD and DHCP lease verified` marker before starting
MQTT/OTA. A named startup failure permits a global budget of at most two
additional whole-MCU resets shared by the baseline and candidate phases; their
normal boots do not consume that budget. Each reset boots through
`sdio_host_init()` and power-cycles Type 1YN through P51 (off 1 s, then on and
settle 500 ms), avoiding an unsafe in-process unwind of partially initialized
WHD state. Exhaustion or a silent hang fails closed.

The 4 KiB block is small enough for both the CBOR response and the larger
JSON/Base64 response to fit in the 8 KiB MQTT buffer. Pipeline #9580 at source
SHA `8d22109f` proved that leaving the request count at its default of three
could exhaust FreeRTOS heap in the lower RX/TCP/MQTT path immediately after the
first request, before the application PUBLISH callback. The OTA profile now
serializes requests at one block, reduces the static event pool from three to
two buffers, and moves the reclaimed RAM into the 208 KiB FreeRTOS heap. It
also raises the received-block bitmap from 128 to 192 entries; otherwise the
785,920-byte payload would be rejected from block 128 onward. Incoming stream
messages are bounds-checked before copying into an event buffer, and the layout
analyzer rejects drift in all of these effective defines. The block size changes
transfer granularity only; it does not change the 768 KiB signed RSU layout.
At source SHA `ef69d76c`, pipeline #9581 / package job #61342 recorded a
208 KiB heap, two OTA event buffers, a 192-byte received-block bitmap, RAM
high-water `0x00058A5B`, and 30,116 bytes of static RAM headroom; both the MQTT
buffer-fit and OTA runtime-memory-profile gates passed.

Run the same command used by the package job:

```powershell
python tools/build_rx671_ota_images.py `
  --baseline-version 0.1.0 `
  --candidate-version 0.1.1 `
  --e2studio $env:E2STUDIO_CLI `
  --workspace-root $env:E2STUDIO_WORKSPACE_RX671_OTA
```

The command above always creates formal firmware without Wi-Fi credentials.
Both baseline and candidate are compiled with the LittleFS KVS JOIN profile;
their manifests record `formal=true`, `credentials_embedded=false`, and
`wifi_credentials_source=littlefs_kvs_runtime_provisioning`. The focused
hardware job passes only the names of `RX671_EK_WIFI_SSID` and
`RX671_EK_WIFI_PASSPHRASE` to the host provisioner. It hex-encodes the values,
sends them over SCI6 with `conf sethex`, and commits them to LittleFS before the
credential-free baseline is installed. The host uses mutable value/command
buffers, never logs their contents, and zeroes them after SCI6 transfer.
Neither Wi-Fi value can be read back by the CLI; both are zeroed from the WHD
buffers and KVS RAM cache after JOIN. During the transaction, LittleFS/KVS is
the only intended persistent destination on the device. Proven zeroization is
limited to the host mutable value/command buffers, project-local WHD buffers,
the KVS Wi-Fi RAM cache, and the `.rx671-ota-secrets` job directory. It does not
claim zeroization of every transient copy internal to Python, the serial driver,
WHD, mbedTLS, or PKCS #11. Data Flash is preserved while the boot loader,
baseline, and candidate are
programmed or bank-swapped, so both OTA images use the same provisioned values.
The final full-chip erase and normal claim-free image program/verify are the
mandatory device postcondition, independently of AWS resource cleanup. Because
CI does not byte-read all erased Data Flash, this does not claim direct proof
that every persistent CSP byte is absent.

The OTA artifact therefore needs neither a credential-bearing firmware variant
nor `RX671_OTA_ARTIFACT_KEY`: `build/rx671-ota/` is passed directly between CI
jobs. The preflight job records the pipeline-owned Thing ARN, OTA update ID,
and exact S3 key before any AWS mutation. The final cleanup job downloads only
that preflight journal, derives missing live Job/S3 metadata from the exact OTA
ID, captures the success state, and then verifies deletion of the OTA update,
IoT Job, S3 object versions, and temporary Thing. A force-cancel or runner power
loss can still prevent the cleanup job itself from running; in that case retry
`cleanup_rx671_wifi_ota` while the 30-day preflight artifact is retained.

CI sets that workspace to
`C:/ai/codex/ws/iot-reference-rx-rx671-ota-2026-04-2`. The short,
repository-independent path keeps generated e2 studio metadata outside
OneDrive and avoids Windows path-length sensitivity.

The helper snapshots `.cproject`, the FWUP configuration, and both generated
BSP bank-mode files before applying the profile. It restores every snapshot
byte-for-byte after success or failure and rejects a formal provenance build
from a dirty source tree or a dirty/mismatched input submodule. OTA builds
enable KVS-backed WHD JOIN without compiling a value, explicitly disable local
Wi-Fi/AWS configuration, remove Wi-Fi credential variables from the child
build environment, and reject outputs containing a configured Wi-Fi
credential. Outputs are confined to `build/rx671-ota/` and
include the boot loader, baseline/candidate MOT, ABS, MAP and signed RSU files,
the bank.single provisioner MOT/ABS/MAP, signer certificate and public key,
effective configuration snapshots, SHA-256 provenance, and layout-analysis
reports. The candidate directory also contains
`aws_wifi_rx671_ek.ota.bin` (the full RSU after its 0x200-byte header) and
`aws_wifi_rx671_ek.ota-signature.der`, whose ECDSA P-256 signature is verified
against that exact OTA transfer payload before publication.

The package job alone does not prove hardware OTA success; it proves only
artifact generation, flash-layout conformance, provenance, and signature
self-verification. The fixed-SHA focused hardware
pipeline #9584 additionally proves blank-Data-Flash provisioning and the full
software TLS 1.2 AWS OTA transaction from `0.1.0` to `0.1.1`, including
self-test, image acceptance, OTA success reporting, board parking, and AWS
cleanup. The primary-image path does not emit the optional
`Accepted and committed final image.` PAL log; pipeline #9584 instead combines
the required image-acceptance marker with the post-activation TLS/capacity
proof and the independent AWS Job execution `SUCCEEDED` snapshot. This evidence
promotes only the RX671 software OTA cell to `○`; TSIP and TLS 1.3 OTA remain
unverified.
Promotion to `○` requires both the hardware job and cleanup job to succeed on
the same source SHA as the package artifacts.

The fixed evidence is
[pipeline #9584](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9584):
[package #61361](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/61361),
[create #61362](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/61362),
[hardware #61363](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/61363),
and [cleanup #61364](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/61364).
The hardware summary records all 192 blocks, TLS 1.2 before and after
activation, minimum-ever-free heap 25,584 bytes, minimum 16 network buffers,
WHD maximum use 1/8, zero WHD failures/wait loops, and zero recovery resets.
Cleanup records AWS IoT Job `COMPLETED`, execution `SUCCEEDED`, acceptance
PASS, and absence of all pipeline-owned resources.
See [OTA_FLASH_LAYOUT.md](e2studio_ccrx/OTA_FLASH_LAYOUT.md) for the formal
layout and evidence boundary.

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

TSIP remains a separate sibling project. The existing RX671 boot-loader sibling
is consumed by the OTA artifact and hardware flow, while the checked-in Wi-Fi
application itself remains a linear `bank.single` project.

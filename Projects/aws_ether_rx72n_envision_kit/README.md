# RX72N Envision Kit Ethernet Bring-Up

This project is the staging area for porting RX72N Envision Kit board support
onto the [iot-reference-rx] FreeRTOS/AWS middleware baseline.

## Rationale

The previous migration direction updated [rx72n-envision-kit] in place by
copying newer middleware into the older RX72N tree. That exposed fragile
OS/driver/SMC boundary issues, especially around the CN8/SCI2 command UART
path. This track reverses the direction: keep the modern [iot-reference-rx]
middleware baseline intact, then migrate RX72N Envision Kit board features in
small steps.

## Starting Point

- Baseline project pattern: `Projects/aws_ether_ck_rx65n_v2`
- Board feature source: [rx72n-envision-kit]
- Initial runtime gate: boot, log UART, command/provisioning UART, Ethernet,
  MQTT connect/publish/subscribe
- Boot path: keep the existing custom RX72N boot loader contract for now

## Staged Bring-Up

1. Create the RX72N Envision Kit project skeleton and document the ownership
   boundary.
2. Add RX72N BSP, Smart Configurator output, linker sections, startup, and
   board configuration while preserving the iot-reference-rx middleware layout.
3. Validate headless build and boot/log UART on RX72N set #2.
4. Add the command/provisioning UART only after the boot/log/Ethernet path is
   stable.
5. Port board features from [rx72n-envision-kit] in separate MRs: GUI/touch,
   SD card, serial flash, audio, and firmware update UI.

## CC-RX linker optimization

アプリ 3 版では、タスクのスタックを復元する処理をインラインのまま保ちます。
`BSR` は復元後のスタックに戻り先を書き込むため、リンカーの同一コード抽出は
`-samecode_forbid=_xPortStartScheduler,_vSoftwareInterruptISR,_vTickISR` で禁止します。

## Tracealyzer SPI Output Experiment

Tracealyzer over RTT/FINE is not the preferred transport for this workload.
The SPI output experiment is tracked in
`tracealyzer_spi_output_experiment.md`. The first implementation path is to
use one RX72N Envision Kit PMOD as SCI simple SPI master and forward recorder
bytes to a GR-ROSE SPI/Ethernet bridge.

## Non-Goals For The First Bring-Up

- No Fleet Provisioning rollout.
- No MCUboot adoption.
- No custom boot loader replacement.
- No bulk copy of all RX72N Envision Kit application tasks before the base
  project boots and reaches the MQTT runtime gate.

[iot-reference-rx]: https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx
[rx72n-envision-kit]: https://gitlab.saffti.jp/oss/import/github/renesas/rx72n-envision-kit

## OTA flash layout

The application area is 0xFFE00000–0xFFFEFFFF (1,984 KiB (0x1F0000)); the exception and reset vectors are 0xFFFEFF80 and 0xFFFEFFFC. The 64 KiB bootloader occupies 0xFFFF0000–0xFFFFFFFF and its bank 1 copy starts at 0xFFDF0000. The OTA payload is 2,031,104 bytes.

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

## Non-Goals For The First Bring-Up

- No Fleet Provisioning rollout.
- No MCUboot adoption.
- No custom boot loader replacement.
- No bulk copy of all RX72N Envision Kit application tasks before the base
  project boots and reaches the MQTT runtime gate.

[iot-reference-rx]: https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx
[rx72n-envision-kit]: https://gitlab.saffti.jp/oss/import/github/renesas/rx72n-envision-kit

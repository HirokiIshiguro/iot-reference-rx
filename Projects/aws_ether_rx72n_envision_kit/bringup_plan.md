# RX72N Envision Kit Bring-Up Plan

## Source Repositories

- Modern middleware baseline: [iot-reference-rx]
- RX72N board feature source: [rx72n-envision-kit]

## Project Boundary

The RX72N Envision Kit project should follow the [iot-reference-rx] layout:

- `Common/`, `Configuration/`, `Demos/`, and `Middleware/` remain shared.
- RX72N-specific code lives under `Projects/aws_ether_rx72n_envision_kit`.
- Board-specific generated code, linker settings, and startup settings are
  copied from [rx72n-envision-kit] only when needed for a concrete validation
  step.

## First Hardware Target

- Board: RX72N Envision Kit set #2
- Device ID: `rx72n-02`
- Runner tags: `dev-rx72n-02`, `exec-shell`, `hw-raspi`, `os-linux`
- Device resource group: `rx72n-device-02`
- CN6 log UART: `UART_PORT_ENVISION_KIT_RX72N_CN6_RPI2`
- CN8 command/provisioning UART: `UART_PORT_ENVISION_KIT_RX72N_CN8_RPI2`

## Step 1: Project Skeleton

Add this directory and record the migration boundary. Do not copy the full
RX72N application yet.

Expected result:

- The repository has an explicit RX72N Envision Kit project entry point.
- Follow-up MRs can be scoped to boot, UART, Ethernet, and board feature slices.

## Step 2: Bootable RX72N Base

Start from `Projects/aws_ether_ck_rx65n_v2/e2studio_ccrx` and add the minimum
RX72N-specific pieces:

- RX72N BSP and Smart Configurator output
- RX72N linker section layout compatible with the custom boot loader
- RX72N clock, pin, Ethernet, and flash configuration
- startup hooks needed by the [iot-reference-rx] FreeRTOS baseline

Expected result:

- CCRX build succeeds for the RX72N project.
- The image boots through the existing custom boot loader.
- CN6 log output confirms FreeRTOS startup.

## Step 3: Network/MQTT Gate

Bring up Ethernet first, before UI and storage features.

Expected result:

- Ethernet link and DHCP/static address handling are visible in logs.
- MQTT connect, publish, and subscribe pass on RX72N set #2.

## Step 4: Provisioning Command Path

Add the command/provisioning UART only after boot/log/Ethernet are stable.

Expected result:

- CN8 command UART can issue simple commands.
- Credential write/readback works on the selected storage backend.
- The manual credential path remains available until Fleet Provisioning is a
  separate validated track.

## Deferred Board Features

Port these as separate MRs after the runtime gate is stable:

- GUI and touch navigation
- SD card and firmware update UI
- serial flash utilities
- audio task
- OTA UI integration on the existing custom boot path

[iot-reference-rx]: https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx
[rx72n-envision-kit]: https://gitlab.saffti.jp/oss/import/github/renesas/rx72n-envision-kit

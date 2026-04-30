# boot_loader_ck_rx65n

This project is the CK-RX65N dual-bank boot loader used by the BG96 cellular OTA reference.

The implementation was ported from:

https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-ota/bootloader

## Hardware

| Item | Setting |
|------|---------|
| Board | CK-RX65N V1 |
| MCU | RX65N dual-bank device |
| Debug/power | J14 E2 Lite |
| Download UART | J20 |

## Project

Import `e2studio_ccrx/` as an existing e2 studio project.

The e2 studio project name is `boot_loader_ck_rx65n` and the default build configuration is `HardwareDebug`.

Expected boot loader output:

- `e2studio_ccrx/HardwareDebug/boot_loader_ck_rx65n.mot`

## Notes

The boot loader receives a signed RSU image over UART and starts the application from the RX65N OTA bank after signature validation. It is paired with `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/`.

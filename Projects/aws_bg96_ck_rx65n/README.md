# aws_bg96_ck_rx65n

This project is a CK-RX65N cellular AWS IoT reference using the Quectel BG96 modem.

The implementation was ported from the stable OTA reference at:

https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-ota/bg96

## Hardware

| Item | Setting |
|------|---------|
| Board | CK-RX65N V1 |
| MCU | RX65N dual-bank device |
| Modem | Quectel BG96 |
| Debug/power | J14 E2 Lite |
| Log/provisioning UART | J20 |
| Cellular stack | Renesas `r_cellular` BG96 FIT fork (`1.13.saffti-custom.6`), pinned as `Middleware/Renesas/r_cellular` |

## Project

Import `e2studio_ccrx/` as an existing e2 studio project.

The e2 studio project name is `aws_bg96_ck_rx65n` and the default build configuration is `HardwareDebug`.

## Build

The repository-level headless build imports and builds both the boot loader and this application:

```powershell
pwsh -File tools/build_headless_rx65n_bg96.ps1 `
  -ProjectRoot <repo_root> `
  -E2Studio C:\Renesas\e2_studio_2026_04_2\eclipse\e2studio-cli.exe `
  -Workspace C:\ai\codex\ws\rx65n_bg96
```

Expected application outputs:

- `e2studio_ccrx/HardwareDebug/aws_bg96_ck_rx65n.mot`
- `e2studio_ccrx/HardwareDebug/aws_bg96_ck_rx65n.abs`
- `e2studio_ccrx/HardwareDebug/aws_bg96_ck_rx65n.x`

## OTA

Use `tools/create_bg96_rsu.py` to package the `.mot` file as the contiguous RSU image consumed by the CK-RX65N boot loader, or use `tools/build_bg96_ota_candidate.py` to create the AWS IoT OTA payload.

The application uses the shared FreeRTOS Kernel V11.3.0 and libraries. The modem
and TCP socket path use `r_cellular`; the FreeRTOS Cellular Interface and its
Quectel reference port are not used. Product configuration stays in the project,
while the unmodified driver checkout is a submodule. See the
[cellular integration policy](../../docs/rx65n-cellular.md) for its pin and scope.

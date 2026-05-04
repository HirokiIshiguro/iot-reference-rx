# RX72N Envision Kit Ethernet TSIP Profile

This project is the RX72N Envision Kit Ethernet AWS IoT reference built with the TSIP-enabled Mbed TLS backend.

The e2 studio project name is `aws_ether_rx72n_envision_kit_tsip`. It keeps the same board, boot loader, OTA, and MQTT behavior as `aws_ether_rx72n_envision_kit`, but links `mbedtls_with_TSIP` and `using_mbedtls_pkcs11_with_tsip`.

## Provisioning

The TSIP profile keeps the AWS IoT private key out of the application image. Use the standard UART credential flow for endpoint, thing name, client certificate, root CA, and code-signing certificate, then use the `tsipprov` CLI command to write the TSIP wrapped key material and run `tsipprov prepare`.

## Build

```powershell
pwsh -File tools/build_headless_rx72n.ps1 `
  -ProjectRoot <repo_root> `
  -E2Studio C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe `
  -Workspace C:\Temp\e2ws_iot_ref_rx72n_tsip `
  -TlsBackend tsip
```

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

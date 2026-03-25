# boot_loader_rx72n_envision_kit

Legacy RX72N Envision Kit bootloader project imported from:
- `rx72n-envision-kit/projects/renesas/rx72n_envision_kit/e2studio/boot_loader`

Current intent:
- keep the folder name `boot_loader_rx72n_envision_kit` inside `iot-reference-rx`
- use the legacy `rx72n_boot_loader` implementation for initial image download and reset handoff
- keep the latest FreeRTOS app track in `Projects/aws_ether_rx72n_envision_kit`

Notes:
- the e2studio metadata is aligned so the imported project builds as `boot_loader_rx72n_envision_kit`
- RSU generation for local bring-up now uses the app-side PRM CSV because the legacy bootloader does not carry the `r_fwup` sample tool tree
- MCUboot remains out of scope for this issue

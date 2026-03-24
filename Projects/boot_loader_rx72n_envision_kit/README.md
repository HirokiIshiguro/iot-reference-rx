# boot_loader_rx72n_envision_kit

RX72N boot loader seed project on top of the `iot-reference-rx` boot loader baseline.

Imported seed:
- source project: `iot-reference-rx/Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/`
- extra reference file: `bootloader_information.md`

Current status:
- directory name is already the RX72N target name
- internal project metadata still contains RX65N-oriented names and settings
- no RX72N build claim is made in this step

Expected RX72N-specific adaptation areas:
- dual-bank memory layout
- boot area ROM budget
- RX72N flash / SCI / pin configuration
- `r_fwup` configuration for RX72N

Important:
- MCUboot migration is not part of this initial step
- first goal is to recover a buildable `r_fwup`-based boot path

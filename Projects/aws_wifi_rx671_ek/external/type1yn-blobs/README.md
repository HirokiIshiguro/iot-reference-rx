# Type 1YN WHD Blobs

This directory pins the external source repositories for the Murata Type 1YN
WLAN resources used by the EK-RX671 Wi-Fi project.

The WHD driver source used by the application remains in
`../wifi-host-driver`. These submodules are only the source of the runtime
firmware/NVRAM/CLM data downloaded to the CYW43439 during Type 1YN
initialization.

## Layout

| Path | Purpose |
|---|---|
| `sources/firmware-wifi-host-driver/` | Infineon WHD resource repository revision containing `43439A0.bin` |
| `sources/wifi-resources/` | Infineon resource repository revision containing the Murata 1YN CLM blob |
| `sources/cyw-fmac-nvram/` | Murata NVRAM repository revision containing `cyfmac43439-sdio.1YN.txt` |
| `staging/` | Generated/copy output consumed by the e2 studio linker; ignored by git |
| `manifest.json` | Expected source paths, revisions, SHA256 values, and license references |
| `stage_type1yn_blobs.ps1` | Validates source blobs and prepares the ignored `staging/` files |

## Prepare Staging Files

From the repository root:

```powershell
git submodule update --init --recursive `
  Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/firmware-wifi-host-driver `
  Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/wifi-resources `
  Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/cyw-fmac-nvram

pwsh -File Projects/aws_wifi_rx671_ek/external/type1yn-blobs/stage_type1yn_blobs.ps1
```

The script creates:

| File | SHA256 |
|---|---|
| `staging/43439A0.bin` | `BF545B5E5796E7F9348EC4A77F87D25E557AB97378DC2046A99E70997D2E1CA8` |
| `staging/43439A0.clm_blob` | `07BC4851449DB809CE154FF79194A36CC6A2F7015C8B80B4073B5AA6F862CCB6` |
| `staging/nvram_1yn.bin` | `F8824E0D6F36B5FCA8B36986140733A63F43BBC19293F6DEF40DEC2FD78F055E` |

`nvram_1yn.bin` is generated from Murata's text NVRAM file by removing blank
and comment lines, encoding each key/value line as ASCII, separating entries
with NUL bytes, appending a final NUL terminator, and padding to a 4-byte
boundary.

The e2 studio project links the staged files with CC-RX `-binary` options and
defines the C symbols:

| Resource | Linker section | C symbol |
|---|---|---|
| WLAN firmware | `TYPE1YN_FW_BLOB` | `g_type1yn_firmware_bin` |
| NVRAM | `TYPE1YN_NVRAM_BLOB` | `g_type1yn_nvram_bin` |
| CLM blob | `TYPE1YN_CLM_BLOB` | `g_type1yn_clm_blob` |

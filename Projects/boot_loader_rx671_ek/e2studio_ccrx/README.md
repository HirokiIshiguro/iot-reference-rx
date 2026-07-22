# boot_loader_rx671_ek e2 studio プロジェクト

EK-RX671 のデュアルバンク Code Flash 用 CC-RX プロジェクトです。このディレクトリを既存プロジェクトとして import し、`boot_loader_rx671_ek/HardwareDebug` をビルドしてください。

主な固定条件は次のとおりです。

- Device: `R5F5671EHxFB_DUAL`
- Boot-loader window: `0xFFFC0000` - `0xFFFFFFFF`（256 KiB）
- UART: SCI6、921600 bps
- RTOS: なし
- Data Flash の RSU インストール: 無効（既存 LittleFS/KVS を保持）
- 公開鍵: LittleFS の `code_signer_public_key`

生成物は `HardwareDebug/boot_loader_rx671_ek.mot`、`.abs`、`.map` です。headless build、配置検証、RPi#1 manual smoke の手順は上位の [README](../README.md) を参照してください。

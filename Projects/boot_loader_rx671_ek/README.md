# EK-RX671 スタンドアロン・ブートローダー

EK-RX671（R5F5671EHxFB）のデュアルバンク Code Flash 用セキュアブートローダーです。Issue #119 の第1段階として、アプリケーションから独立してビルド、書き込み、SCI6 起動確認を行える最小構成を提供します。

## 対象範囲

この段階で提供するものは次のとおりです。

- CC-RX / e2 studio の `HardwareDebug` ビルド
- 上位 256 KiB に固定したブートローダー配置
- SCI6、921600 bps のダウンロード／診断 UART
- Data Flash を消去しない RSU 更新設定
- アプリケーションと共有する LittleFS からの署名検証用公開鍵読み込み
- LittleFS 鍵が取得できない場合の fail-closed（組み込み鍵へのフォールバックなし）
- hash-only image の拒否と ECDSA P-256/SHA-256 署名の必須化
- Windows runner の自動ビルドと、RPi#1 実機の明示的な manual smoke gate

アプリケーションの再配置、WHD/Type 1YN、AWS IoT OTA/Fleet の結合は、この第1段階には含めません。

この段階は OTA 機能試験の土台です。Data Flash の LittleFS 鍵はアプリケーションから
変更可能であり、不変な root of trust ではありません。また `sequence_number` を使った
anti-rollback も未実装です。production 化には Code Flash / TSIP の root key による鍵更新認証と、
改ざん・巻き戻しできない単調カウンタが必要です。実機 smoke の成功だけで OTA 対応表を
`○` には更新しません。

## ハードウェアと設定

| 項目 | 設定 |
|---|---|
| ボード | Renesas EK-RX671 |
| MCU | R5F5671EHxFB、Dual Bank mode |
| デバッガ／書き込み | オンボード E2OB（RPi#1 では hardware-config の割り当てを使用） |
| UART | SCI6、921600 bps |
| RTOS | なし（bare metal） |
| 公開鍵 | Data Flash 上の LittleFS ファイル `code_signer_public_key` |
| 証明書 ID | LittleFS ファイル `code_sign_cert_id` |
| 組み込み公開鍵／秘密鍵 | ファームウェアおよび親プロジェクトには格納しない |

`RX_BOOTLOADER_INSTALL_DATA_FLASH=0` のため、RSU インストール時にも 8 KiB の Data Flash 全体を保持します。ブートローダー自身の公開鍵設定は `RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE=0`、`RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE=1`、`RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK=0` です。`RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE=1` により hash-only FWUP image も拒否します。

## Code Flash 配置

| 領域 | アドレス | サイズ |
|---|---:|---:|
| ブートローダー予約領域 | `0xFFFC0000` - `0xFFFFFFFF` | 256 KiB |
| `PResetPRG` | `0xFFFC0000` | エントリ |
| `EXCEPTVECT` | `0xFFFFFF80` | 固定ベクタ |
| `RESETVECT` | `0xFFFFFFFC` | リセットベクタ |

`tools/ci/check_rx671_bootloader_layout.py` は `.mot` の全データレコードが予約領域または RX671 の Option-Setting Memory 内にあること、および linker map の3つの固定位置を検証します。

## 依存ブートローダー

`e2studio_ccrx/lib/rx_bootloader` は次の submodule commit に固定しています。

```text
c31bac703e1406e7a94d398b7bcad108b5e8fdce
```

clone 後は親リポジトリで `git submodule update --init --recursive` を実行してください。

## ビルド

e2 studio へ `e2studio_ccrx/` を既存プロジェクトとして import し、`boot_loader_rx671_ek/HardwareDebug` をビルドします。Windows の headless build はリポジトリルートで次を実行します。

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_headless_rx671_bootloader.ps1
python .\tools\ci\check_rx671_bootloader_layout.py `
  --mot .\Projects\boot_loader_rx671_ek\e2studio_ccrx\HardwareDebug\boot_loader_rx671_ek.mot `
  --map .\Projects\boot_loader_rx671_ek\e2studio_ccrx\HardwareDebug\boot_loader_rx671_ek.map
```

生成物は次の3ファイルです。

- `e2studio_ccrx/HardwareDebug/boot_loader_rx671_ek.mot`
- `e2studio_ccrx/HardwareDebug/boot_loader_rx671_ek.abs`
- `e2studio_ccrx/HardwareDebug/boot_loader_rx671_ek.map`

## CI と実機 smoke

`build_rx671_bootloader` は CC-RX build、契約テスト、配置検証だけを自動実行し、実機を書き換えません。

RPi#1 の EK-RX671 を使う場合だけ、pipeline variable `RUN_RX671_BOOTLOADER_SMOKE=true` を指定し、表示された `smoke_rx671_bootloader_manual` を手動開始します。この job は共有ハードウェア lock を取得して E2OB から `.mot` を書き込み、SCI6 で起動と鍵ポリシーを確認します。既定の `RX671_BOOTLOADER_EXPECTED_KEY_STATE=missing-fail-closed` では次を要求します。

```text
RX secure boot program
Loading user code signer public key from LittleFS: not found; refusing to boot.
```

事前に production 公開鍵を LittleFS へ登録した実機では `RX671_BOOTLOADER_EXPECTED_KEY_STATE=found` を指定し、完全な `...: found.` 行を要求します。どちらのモードでも `not found; using built-in key.` を検出すると失敗します。

この manual job は現在の RX671 アプリケーションをブートローダー単体イメージで置き換えるため、自動起動させません。

## 現在のビルド証跡

2026-07-22 に e2 studio 2026-04.2 / CC-RX V3.07.00 で headless clean build を実行し、0 error で `.mot/.abs/.map` を生成しました。配置検証結果は次のとおりです。

```text
RX671_BOOTLOADER_LAYOUT_PASS window=0xFFFC0000-0xFFFFFFFF reserved=262144 payload=68978 option_records=8
```

`payload=68978` は Code Flash に実データとして格納されるバイト数です。予約領域 262144 byte の 26.3% であり、上位 256 KiB の契約内に収まっています。RPi#1 実機 smoke は manual gate を明示的に起動した pipeline の artifact を正式証跡とします。

# RX Bootloader (submodule)

RXファミリ共通のセキュアブートローダ コアロジックです。サブモジュールとして組み込むプロジェクトで、FIT モジュール群と組み合わせて使用します。

- RX65N-RSK の amazon-freertos `boot_loader` をベースに、RX72N Envision Kit 拡張 (LCD, 10us タイマ, DataFlash 鍵ストレージ) をオプション化
- MCU グループ別の Flash アドレスマップをヘッダで切替
- ECDSA (P-256) + SHA-256 によるファームウェア署名検証
- デュアルバンク Code Flash の bank-swap を用いた A/B アップデート

## 構成

```
.
├── rx_bootloader.c / .h        コア状態遷移マシンと公開API
├── rx_bootloader_private.h     内部型 (FIRMWARE_UPDATE_CONTROL_BLOCK 等)
├── base64_decode.c / .h        PEM 公開鍵パース
├── sfd/                        Simple Filesystem on DataFlash (オプション)
├── config/
│   ├── rx_bootloader_config.h  ユーザ設定テンプレート (include先を選択)
│   ├── rx72n.h                 RX72N (4MB) Flash マップ
│   └── rx65n.h                 RX65N (2MB) Flash マップ
└── ref/
    └── code_signer_public_key.h  公開鍵テンプレート
```

## 使い方

### 1. サブモジュールとして追加

```sh
git submodule add git@gitlab-claude:oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule.git \
    lib/rx_bootloader
```

### 2. 外部依存を用意

プロジェクト側に以下の FIT モジュール / ライブラリを配置:

| 依存 | 用途 |
|------|------|
| `r_bsp`         | `R_BSP_SoftwareDelay`, `R_BSP_InterruptsDisable`, レジスタ定義 |
| `r_flash_rx`    | `R_FLASH_Open/Write/Erase/Control` |
| `r_sci_rx`      | `R_SCI_Open/Send/Receive/Control/Close` |
| `r_byteq`       | `r_sci_rx` 内部利用 |
| `r_cmt_rx`      | 10us 性能カウンタ (PERF_COUNTER 有効時のみ) |
| `r_simple_graphic_rx`, `r_simple_glcdc_config_rx`, `r_glcdc_rx` | LCD 出力 (USE_LCD 有効時のみ) |
| tinycrypt       | SHA-256, ECC (P-256), ECDSA 検証 |

Smart Configurator の BSP UART terminal 設定で、`r_bsp_config.h` に以下が生成されることを確認:

```c
#define BSP_CFG_SCI_UART_TERMINAL_CHANNEL             (8)       /* UART チャネル */
#define BSP_CFG_SCI_UART_TERMINAL_BITRATE             (115200)
#define BSP_CFG_SCI_UART_TERMINAL_INTERRUPT_PRIORITY  (15)
```

### 3. コンフィグをコピーして編集

```sh
cp lib/rx_bootloader/config/rx_bootloader_config.h  src/
cp lib/rx_bootloader/ref/code_signer_public_key.h   src/key/
```

`src/rx_bootloader_config.h` を編集し、対象 MCU とオプション機能を選択:

```c
#include "rx72n.h"                      /* または "rx65n.h" */

#define RX_BOOTLOADER_USE_LCD                  (0)  /* 1: Envision Kit 等 LCD 付き */
#define RX_BOOTLOADER_USE_DUAL_BANK            (1)
#define RX_BOOTLOADER_USE_PERF_COUNTER         (0)
#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE  (0)
#define RX_BOOTLOADER_USE_TINYCRYPT            (1)
```

`src/key/code_signer_public_key.h` の `<REPLACE_WITH_YOUR_PUBLIC_KEY>` を、実際の ECDSA 公開鍵 (PEM) に差し替え。

### 4. main から呼び出す

```c
#include "rx_bootloader.h"

void main(void)
{
    rx_bootloader_main();    /* 通常は戻らない */
}
```

## ブートローダとアプリケーションの結合

ブートローダ単体ビルドでは `boot_loader.mot` が生成されます。アプリケーション (`aws_demos.mot` 等) と結合してファクトリ書込み用 MOT / UART ダウンロード用 RSU を生成するには、
[mot_to_rsu.py](https://gitlab.saffti.jp/oss/experiment/generic/scripts/python/mcu-tool/renesas/rx) を使用します。

```bash
# ファクトリ MOT 生成 (rfp-cli で一括書込み)
python mot_to_rsu.py --factory \
    --bootloader boot_loader.mot \
    --mot aws_demos.mot \
    --key secp256r1.privatekey \
    -o userprog.mot

# UART ダウンロード用 RSU 生成
python mot_to_rsu.py \
    --mot aws_demos.mot \
    --key secp256r1.privatekey \
    -o userprog.rsu

# 既存 RSU の検証
python mot_to_rsu.py --verify userprog.rsu --key secp256r1.privatekey
```

依存: `pip install cryptography`

公開鍵の PEM は、`--key` に指定した秘密鍵から `openssl ec -in secp256r1.privatekey -pubout` で取得し、`code_signer_public_key.h` に貼り付けます。

## MCU 対応を追加する

新しい MCU グループに対応する場合:

1. `config/<mcu>.h` を作成 (`rx72n.h` を雛形に)
2. 以下の値を MCU のデータシート / 既存ブートローダ実装から決定:
   - `RX_BOOTLOADER_LOW_ADDRESS` — ブートローダを配置する先頭ブロック
   - `RX_BOOTLOADER_MIRROR_LOW_ADDRESS` — バンク1ミラーの配置先頭
   - `RX_BOOTLOADER_MIRROR_HIGH_ADDRESS` — ミラー領域の erase 起点
   - `RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_HIGH_ADDRESS` — 更新領域 erase 起点
   - `RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL/MEDIUM` — ミラーのブロック数
   - `RX_BOOTLOADER_SMALL_BLOCK_SRC/DST` — 小ブロック領域のミラーコピー元/先
   - `RX_BOOTLOADER_USER_CONST_DATA_LOW_ADDRESS` — ユーザ const data 配置先頭 (DF)
   - `RX_BOOTLOADER_USER_CONST_DATA_BLOCK_NUM` — const data ブロック数
   - `RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER` — DF install 領域ブロック数の計算式
3. SFD を使う場合、`sfd/r_simple_filesystem_on_dataflash.c` の `#if defined(BSP_MCU_RX72N)` ガードに新 MCU の分岐を追加

## 出典

- RX65N-RSK boot_loader: <https://github.com/renesas/amazon-freertos/tree/master/projects/renesas/rx65n-rsk/e2studio/boot_loader>
- RX72N Envision Kit boot_loader: <https://github.com/renesas/rx72n-envision-kit/tree/master/projects/renesas/rx72n_envision_kit/e2studio/boot_loader>

## ライセンス

元のRenesasコードのライセンスに従います。各ファイル先頭の Disclaimer を参照。

## 実機検証

このサブモジュール単体ではビルド不可 (FIT / r_bsp_config / tinycrypt が必要)。動作検証は、本サブモジュールを組み込む側のプロジェクトで行ってください。

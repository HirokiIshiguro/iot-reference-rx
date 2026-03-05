# CLAUDE.md — iot-reference-rx

## Background / 背景

[iot-reference-rx](https://github.com/renesas/iot-reference-rx) は Renesas が提供する
RX ファミリ向け FreeRTOS LTS IoT リファレンス実装。
公式サポートボードは CK-RX65N v2 のみだが、FIT モジュール・r_fwup・NetworkInterface 等の
内部実装は RX72N を含む複数の RX MCU に対応済み。

本リポジトリは upstream を GitLab にインポートしたもので、以下の目的で運用する:

1. **CK-RX65N (V1) で CI/CD パイプラインを先行構築**（rx72n-envision-kit Phase 8a）
2. **RX72N Envision Kit への移植**（Phase 8b）
3. 移植完了後、rx72n-envision-kit の FreeRTOS 基盤を本リポジトリベースに置き換え

### CK-RX65N V1 と V2 の違い

本プロジェクトでは CK-RX65N **V1** を使用。V2 との主な違い:
- Ethernet 回路は同一（V2 のコードがそのまま V1 で動作）
- V2 で追加された Cellular (RYZ014A) / Wi-Fi (DA16600) モジュールは V1 では未搭載
- **本プロジェクトでは Ethernet 接続のみを対象とするため、V1 で問題なし**

## Goals / 目標

| # | Goal | Status |
|---|------|--------|
| 1 | CK-RX65N (V1) で aws_ether プロジェクトのビルド・フラッシュ・テスト自動化 | Planned |
| 2 | AWS IoT Core 接続テスト（MQTT PubSub） | Planned |
| 3 | OTA テスト自動化 | Planned |
| 4 | RX72N Envision Kit への移植 | Planned |

## Repository Locations / リポジトリ

| Role | URL |
|------|-----|
| GitLab (primary) | https://shelty2.servegame.com/oss/import/github/renesas/iot-reference-rx |
| GitHub (mirror) | https://github.com/HirokiIshiguro/iot-reference-rx |
| GitHub (upstream) | https://github.com/renesas/iot-reference-rx |

- GitLab プロジェクト ID: **38**
- ベースバージョン: **v202406.01-LTS-rx-1.1.1**（FreeRTOS 202406.01 LTS）
- デフォルトブランチ: `main`（protected）

## Version Information / バージョン情報

| Component | Version | LTS Until |
|-----------|---------|-----------|
| FreeRTOS Kernel | 11.1.0 | 2026/06/30 |
| FreeRTOS-Plus-TCP | 4.2.2 | 2026/06/30 |
| coreMQTT | 2.3.1 | 2026/06/30 |
| coreMQTT-Agent | 1.3.1 | -- |
| corePKCS11 | 3.6.1 | 2026/06/30 |
| coreJSON | 3.3.0 | 2026/06/30 |
| AWS IoT Jobs | 1.5.1 | 2026/06/30 |
| AWS IoT MQTT File Streams | 1.1.0 | 2026/06/30 |
| Fleet Provisioning | 1.2.1 | -- |
| mbedTLS | 3.6.3 | -- |
| littlefs | 2.5.1 | -- |
| r_fwup | 2.04 | -- |

**注意:** v202406.01-LTS-rx-1.1.1 では Fleet Provisioning デモは未サポート。
ただし SDK (1.2.1) は含まれており、将来のリリースまたは独自実装で対応可能。

## Build Environment / ビルド環境

### Software Requirements

| Tool | Version | Path (Runner) |
|------|---------|---------------|
| e2studio-cli | e2 studio 2025-12 | `C:\Renesas\e2_studio_2025_12\eclipse\e2studio-cli.exe` |
| CC-RX | V3.07.00 (evaluation) | `C:\Program Files (x86)\Renesas\RX\3_7_0\bin\ccrx.exe` |
| rfp-cli | V1.15 (Package V3.22) | `C:\Program Files (x86)\Renesas Electronics\Programming Tools\Renesas Flash Programmer V3.22\rfp-cli.exe` |
| GCC (alternative) | GCC for Renesas RX v8.3.0.202411 | — |
| Code generator | RX Smart Configurator（e2 studio 同梱） | — |

**注意:** CC-RX は評価版（残り51日）。期限切れ後はリンクサイズ制限 (128KB) が適用される。

### Git Submodules

このリポジトリは多数の Git サブモジュール（FreeRTOS-Kernel, mbedtls, coreMQTT 等）を含む。
**クローン・チェックアウト時は必ず `--recursive` を使うこと。**

```bash
git clone --recursive <url>
# 既存クローンでサブモジュール未初期化の場合:
git submodule update --init --recursive
```

サブモジュール未初期化の場合、headless ビルドで `FreeRTOS.h` が見つからないエラーになる。

### Build Targets

| Project | Directory | Output | Description |
|---------|-----------|--------|-------------|
| aws_ether_ck_rx65n_v2 | `Projects/aws_ether_ck_rx65n_v2/e2studio_ccrx/` | `.mot` (1.0MB) | Ethernet + AWS IoT デモ（PubSub, OTA） |
| boot_loader_ck_rx65n_v2 | `Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/` | `.mot` (92KB) | OTA 用デュアルバンクブートローダ |

### Headless Build（CLI）

```bash
# 前提: サブモジュール初期化済み
e2studio-cli.exe -nosplash \
  -application org.eclipse.cdt.managedbuilder.core.headlessbuild \
  -data <workspace> \
  -import <app_project_dir> \
  -import <bl_project_dir> \
  -cleanBuild "boot_loader_ck_rx65n_v2/HardwareDebug" \
  -cleanBuild "aws_ether_ck_rx65n_v2/HardwareDebug" \
  -no-indexer
```

- ビルドスクリプト: `tools/build_headless.bat`
- ワークスペースは一時ディレクトリ（`%TEMP%\e2ws_iot_ref`）を使用
- リンクリソース (`AWS_IOT_MCU_ROOT = ${PARENT-3-PROJECT_LOC}`) はサブモジュール初期化後に正常解決

### Demo Configuration

デモの切り替えは `src/frtos_config/demo_config.h` のマクロで制御:

| Macro | Value | Effect |
|-------|-------|--------|
| `ENABLE_FLEET_PROVISIONING_DEMO` | 0 | Fleet Provisioning 無効（現時点では常に 0） |
| `ENABLE_OTA_UPDATE_DEMO` | 0 | PubSub のみ |
| `ENABLE_OTA_UPDATE_DEMO` | 1 | PubSub + OTA |

## Hardware / ハードウェア

### CK-RX65N (V1)

- MCU: RX65N (RXv2 コア, 2MB コードフラッシュ, 640KB RAM)
- Ethernet: オンボード（LAN8720, RMII）
- デバッガ: E2 emulator Lite（オンボード）
- UART: COM6（USB シリアル デバイス、VID:045B PID:8111 SER=0000000000001）
- ボーレート: 115200bps（V1 はオンボード USB シリアルチップ。V2 以降で FTDI に置換され 921600bps 対応）
- E2 Lite: 「Renesas USB Development Tools」として認識（COM ポートとしては表示されない）

### Runner 接続情報

> 詳細なハードウェア構成は [hardware-config](https://shelty2.servegame.com/oss/infra/hardware-config/-/blob/main/CLAUDE.md) を参照。

| Item | Value |
|------|-------|
| E2 Lite USB | **J14** (USB DEBUG, Micro-B) |
| E2 Lite S/N | **OBE110020** |
| UART USB | **J20** (USB SER, Micro-B) |
| UART COM port | COM6 (115200bps) |
| Runner tag | run_ishiguro_machine, hw-ck-rx65n-v1 |
| Ethernet | Runner マシンと同一 LAN に接続済み |

### rfp-cli フラッシュ書き込み

E2 Lite 経由で FINE インタフェースを使用。J14 (USB DEBUG) に USB ケーブルを接続。
E2L_SERIAL (`OBE110020`) は `/oss` グループ CI/CD Variables (`E2L_SERIAL_CK_RX65N_J14`) に設定済み。

```bash
RFP_CLI="C:\Program Files (x86)\Renesas Electronics\Programming Tools\Renesas Flash Programmer V3.22\rfp-cli.exe"

# チップ全消去（BANKSEL リセット + データフラッシュ消去）
rfp-cli -d RX65x -t "e2l:OBE110020" -if fine -s 500K \
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -erase-chip -noquery

# boot_loader 書き込み
rfp-cli -d RX65x -t "e2l:OBE110020" -if fine -s 500K \
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF \
  -p boot_loader_ck_rx65n_v2.mot -run -noquery

# app 書き込み（boot_loader 領域を保持）
rfp-cli -d RX65x -t "e2l:OBE110020" -if fine -s 500K \
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF \
  -file aws_ether_ck_rx65n_v2.mot -auto -noerase -run -noquery
```

**注意:**
- `-erase-chip` はデータフラッシュも消去 → プロビジョニング済みの場合は `-range-exclude` を検討
- E2 Lite 接続時は `-run` 必須（RES# ホールド問題回避）
- 速度は 500K で安定動作確認後、1500K に上げることも可能

## AWS IoT Core

### Thing 情報

| Item | Value |
|------|-------|
| Thing name | ck-rx65n-01 |
| Policy | ck-rx65n-policy |
| Endpoint | プロジェクト CI/CD Variables `AWS_IOT_ENDPOINT` に設定 |
| Certificate | プロジェクト CI/CD Variables `AWS_IOT_CERT` (File 型) に設定 |
| Private Key | プロジェクト CI/CD Variables `AWS_IOT_PRIVKEY` (File 型) に設定 |

### AWS リソース作成

```bash
# AWS CLI で Thing + 証明書 + ポリシーを一括作成
./tools/aws_setup.sh [THING_NAME] [POLICY_NAME]
# デフォルト: ck-rx65n-01, ck-rx65n-policy
```

出力ファイル: `certs/ck-rx65n-01-cert.pem`, `certs/ck-rx65n-01-privkey.pem`

### Credential Provisioning

iot-reference-rx では littlefs + データフラッシュにクレデンシャルを格納する方式を採用。
UART CLI 経由でプロビジョニングする。

```bash
# 手動（Tera Term）: Getting_Started_Guide.md Step 3 を参照
# 自動（Python スクリプト）:
python tools/provision.py \
  --port COM6 --baud 115200 \
  --thing-name ck-rx65n-01 \
  --endpoint <endpoint> \
  --cert certs/ck-rx65n-01-cert.pem \
  --key certs/ck-rx65n-01-privkey.pem
```

**注意:** `flash_boot_loader` は `-erase-chip` でデータフラッシュも消去するため、
フラッシュ書き込みの度に再プロビジョニングが必要。CI/CD では provision ステージで自動実行。

### CI/CD Variables（プロジェクトレベル）

AWS クレデンシャルは **iot-reference-rx プロジェクト** の CI/CD Variables に設定。
`/oss` グループレベルではなくプロジェクトレベルに限定し、他プロジェクトへの漏洩を防止。

**Protected は全て No** — Protected 変数はフィーチャーブランチ（非Protected ブランチ）の
パイプラインで参照できないため。代わりに **Project-based pipeline visibility を OFF** にして
パイプラインログをプロジェクトメンバーのみに制限することで秘密情報を保護する。

| Variable | Type | Description | Masked | Protected |
|----------|------|-------------|--------|-----------|
| `AWS_IOT_ENDPOINT` | Variable | AWS IoT Data-ATS エンドポイント | Yes | No |
| `AWS_IOT_THING_NAME` | Variable | Thing 名 | No | No |
| `AWS_IOT_CERT` | File | デバイス証明書 (PEM) | No | No |
| `AWS_IOT_PRIVKEY` | File | 秘密鍵 (PEM) | No | No |

## CI/CD Pipeline

### Phase 8a: CK-RX65N (V1) パイプライン構築

| Step | Goal | Status |
|------|------|--------|
| 1 | GitLab リポジトリ作成・初期セットアップ | Done (MR !1) |
| 2 | ハードウェアセットアップ（人間作業） | Done (COM6 確定) |
| 3 | ビルド環境構築（headless build） | Done |
| 4 | フラッシュ書き込み自動化（rfp-cli） | Done |
| 5 | AWS IoT Core セットアップ | Done |
| 6 | MQTT PubSub 動作確認 | Planned |
| 7 | OTA テスト | Planned |
| 8 | CI/CD パイプライン統合 | Planned |

### Phase 8b: RX72N Envision Kit 移植

| Item | CK-RX65N (V1) | RX72N Envision Kit | 対応方針 |
|------|---------------|-------------------|----------|
| CPU コア | RXv2 | RXv3 + DPFPU | `-cpu=rxv3 -dpfpu` |
| コードフラッシュ | 2MB (1MB x 2) | 4MB (2MB x 2) | リンカスクリプト変更 |
| RAM | 640KB | 1MB | リンカスクリプト変更 |
| Ethernet PHY | LAN8720 (RMII) | KSZ8041NL (MII) | r_ether_rx 設定・MPC 変更 |
| デバッガ | E2 emulator Lite | J-Link OB | rfp-cli 設定変更 |
| FreeRTOS ポート | RX600v2 | RX700v3_DPFPU | ポートレイヤー切替 |
| r_fwup | RX65N_DualBank | RX72N_DualBank | ImageGenerator パラメータ変更 |

## Git Rules / Git ルール

- `main` ブランチは protected。直接 push 不可
- ブランチを切って MR 経由でマージ
- MR は `Draft:` プレフィックス付きで作成、assignee: @HirokiIshiguro
- コミット author:

| Operator | git author |
|----------|-----------|
| HirokiIshiguro（人間） | `HirokiIshiguro <ishiguro.hiroki@globe.ocn.ne.jp>` |
| Claude Code | `Claude Code <claude-code@noreply.anthropic.com>` |

```bash
git commit --author="Claude Code <claude-code@noreply.anthropic.com>" -m "..."
```

## Related Projects / 関連プロジェクト

| Project | Relation |
|---------|----------|
| [rx72n-envision-kit](https://shelty2.servegame.com/oss/import/github/renesas/rx72n-envision-kit) | Phase 8 の親プロジェクト。移植先 |
| [OTA ナレッジベース](https://shelty2.servegame.com/oss/experiment/embedded/mcu/elemental/ota) | MCU OTA 技術全般のナレッジ |
| [AWS IoT Core ナレッジ](https://shelty2.servegame.com/oss/experiment/cloud/aws/iot-core/claude) | AWS IoT OTA 実装ナレッジ |
| [hardware-config](https://shelty2.servegame.com/oss/infra/hardware-config) | Runner 接続ハードウェア構成一元管理 |

## Known Pitfalls / 既知の注意事項

### Smart Configurator 再生成時のベクタアドレス巻き戻り

**重要:** Smart Configurator でコード再生成すると `.cproject` のリンカセクション設定が
デフォルト値に上書きされる。デュアルバンクブートローダ使用時は以下のアドレスが必須:

| Section | Default (NG) | Dual Bank (正) |
|---------|-------------|----------------|
| EXCEPTVECT | 0xFFFFFF80 | **0xFFFEFF80** |
| RESETVECT | 0xFFFFFFFC | **0xFFFEFFFC** |

SC 再生成後は **必ず** `.cproject` の `-start` オプションで上記アドレスを確認すること。
参照: R01AN7662JJ0100 Section 4.2.3(1)

### CK-RX65N J16 ジャンパ

| 設定 | 用途 |
|------|------|
| 1-2 (DEBUG) | E2 Lite デバッグ・rfp-cli フラッシュ書き込み |
| 2-3 (RUN) | ファームウェア単独実行 |

CI/CD では flash (J16=DEBUG) → test (J16=RUN?) の切り替えが課題。要検討。

## Changelog / 変更履歴

### 2026-03-05: Vector address fix

- SC 再生成 (4851f3fa) で巻き戻されたベクタアドレスを再修正
- UART COM ポートを COM9 → COM6 に修正（J20 抜き差しで確認）
- R01AN7662JJ0100 マニュアル精査で J16 ジャンパ設定の重要性を確認

### 2026-03-03: Step 5 — AWS IoT Core setup

- tools/aws_setup.sh 作成（AWS CLI で Thing + 証明書 + ポリシーを一括作成）
- tools/iot_policy.json 作成（開発用 IoT ポリシー）
- tools/provision.py 作成（pyserial で UART CLI 経由の自動プロビジョニング）
- .gitlab-ci.yml に provision ステージ追加（flash → provision → test）
- AWS クレデンシャルをプロジェクトレベル CI/CD Variables で管理する方針を確定
- CLAUDE.md に AWS IoT Core セクション・プロビジョニング手順を追記

### 2026-03-03: Step 4 — Flash automation

- rfp-cli V3.22 で E2 Lite 2台 (OBE110008, OBE110020) を検出
- .gitlab-ci.yml の flash_boot_loader / flash_app ジョブを rfp-cli コマンドで実装
- E2L_SERIAL を CI/CD Variables から参照する方式に変更
- CLAUDE.md に rfp-cli フラッシュ手順を追記
- hardware-config プロジェクトへの参照リンクを追加
- CI/CD Variables にコネクタ名サフィックスを追加 (E2L_SERIAL_CK_RX65N_J14, UART_PORT_CK_RX65N_J20)
- Runner 接続情報に USB コネクタ名 (J14, J20) を追記

### 2026-03-03: Initial setup

- GitLab にリポジトリ作成（GitHub upstream からインポート）
- GitHub fork (HirokiIshiguro/iot-reference-rx) からのミラー設定
- タグ v202406.01-LTS-rx-1.1.1 を GitLab に push
- CLAUDE.md 作成
- .gitlab-ci.yml スケルトン作成

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

| Tool | Version |
|------|---------|
| IDE | e2 studio 2025-04 以降 |
| CC-RX | V3.07.00 |
| GCC (alternative) | GCC for Renesas RX v8.3.0.202411 |
| Code generator | RX Smart Configurator（e2 studio 同梱） |

### Build Targets

| Project | Directory | Output | Description |
|---------|-----------|--------|-------------|
| aws_ether_ck_rx65n_v2 | `Projects/aws_ether_ck_rx65n_v2/e2studio_ccrx/` | `.mot` | Ethernet + AWS IoT デモ（PubSub, OTA） |
| boot_loader_ck_rx65n_v2 | `Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/` | `.mot` | OTA 用デュアルバンクブートローダ |

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
- UART: SCI チャネル（要確認: COM ポート番号は接続後に特定）

### Runner 接続情報（未確定 — Step 2 で更新）

| Item | Value |
|------|-------|
| E2 Lite COM port | TBD |
| UART COM port | TBD |
| UART baud rate | TBD |
| Runner tag | TBD |
| Ethernet | Runner マシンと同一 LAN |

## AWS IoT Core

### Thing 情報（未確定 — Step 5 で更新）

| Item | Value |
|------|-------|
| Thing name | ck-rx65n-01（予定） |
| Endpoint | TBD |
| Certificate | TBD |
| Policy | TBD |

### Credential Provisioning

iot-reference-rx では littlefs + データフラッシュにクレデンシャルを格納する方式を採用。
初回書き込み時に CLI 経由でプロビジョニングする手順は Getting_Started_Guide.md Step 3 を参照。

## CI/CD Pipeline

### Phase 8a: CK-RX65N (V1) パイプライン構築

| Step | Goal | Status |
|------|------|--------|
| 1 | GitLab リポジトリ作成・初期セットアップ | In progress |
| 2 | ハードウェアセットアップ（人間作業） | Planned |
| 3 | ビルド環境構築（headless build） | Planned |
| 4 | フラッシュ書き込み自動化（rfp-cli） | Planned |
| 5 | AWS IoT Core セットアップ | Planned |
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

## Changelog / 変更履歴

### 2026-03-03: Initial setup

- GitLab にリポジトリ作成（GitHub upstream からインポート）
- GitHub fork (HirokiIshiguro/iot-reference-rx) からのミラー設定
- タグ v202406.01-LTS-rx-1.1.1 を GitLab に push
- CLAUDE.md 作成
- .gitlab-ci.yml スケルトン作成

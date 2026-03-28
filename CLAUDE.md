# CLAUDE.md — iot-reference-rx

> Current scope note:
> This fork now retains only the RX72N Envision Kit projects under `Projects/`.
> Historical CK-RX65N / DA16600 / RYZ014A notes below are preserved as reference and may not match the current repository layout.

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
- シリアル配線が異なる
  - V1 (`CK-RX65N_V1.03.bdf`): `SERIAL (J20) = SCI5` (`TXD5=pin67/PC3`, `RXD5=pin70/PC2`)
  - V2 (`CK-RX65N-V2_V1.01.bdf`): `SERIAL = SCI1` (`TXD1=pin31`, `RXD1=pin29`), `USBC = SCI5`
  - 現在の `aws_ether_ck_rx65n_v2` / `boot_loader_ck_rx65n_v2` の CCRX 設定は
    `BSP_CFG_SCI_UART_TERMINAL_CHANNEL=5` を使用するため、**V1 実機では CLI は J20 に出る**
- **本プロジェクトでは Ethernet 接続のみを対象とするため、V1 で問題なし**

## Goals / 目標

| # | Goal | Status |
|---|------|--------|
| 1 | CK-RX65N (V1) で aws_ether プロジェクトのビルド・フラッシュ・テスト自動化 | Done |
| 2 | AWS IoT Core 接続テスト（MQTT PubSub） | Done |
| 3 | OTA テスト自動化 | Done (known stabilization follow-up: issue #9) |
| 4 | RX72N Envision Kit への移植 | Planned |

## Repository Locations / リポジトリ

| Role | URL |
|------|-----|
| GitLab (primary) | https://shelty2.servegame.com/oss/import/github/renesas/iot-reference-rx |
| GitHub (mirror) | https://github.com/HirokiIshiguro/iot-reference-rx |
| GitHub (upstream) | https://github.com/renesas/iot-reference-rx |

- GitLab プロジェクト ID: **38**
- ベースバージョン: **v202406.04-LTS-rx-1.2.0**（FreeRTOS 202406.04 LTS）
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

**注意:** v202406.04-LTS-rx-1.2.0 より Fleet Provisioning デモが正式サポート（`Demos/Fleet_Provisioning_With_CSR_Demo/`）。
SBOM (`sbom.spdx`) および Wi-Fi OTA (DA16600) 対応も追加（DA16600 は本 fork 非対象）。

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
| aws_ether_rx72n_envision_kit | `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/` | `.mot`, `.abs`, `.x` | RX72N Ethernet + AWS IoT デモ（local bring-up / MQTT / OTA task startup） |
| boot_loader_rx72n_envision_kit | `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/` | `.mot` | RX72N OTA 用デュアルバンクブートローダ |

### Headless Build（CLI）

```bash
# 前提: サブモジュール初期化済み
pwsh -File tools/build_headless_rx72n.ps1 \
  -ProjectRoot <repo_root> \
  -E2Studio <e2studio_exe> \
  -Workspace <workspace>
```

- 現行ビルドスクリプト: `tools/build_headless_rx72n.ps1`
- 互換 wrapper: `tools/build_headless.bat`
- `tools/build_headless_rx72n.ps1` は `boot_loader_rx72n_envision_kit` と `aws_ether_rx72n_envision_kit` を import/build し、`.mot` / `.abs` / `.x` を確認する

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
- E2 Lite の接続先シリアルは運用中に変わり得るため、**現在値は**
  `rfp-cli -d RX65x -t e2l -if fine -list-tools` **で毎回確認すること**

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

OTA 署名用の追加入力:
- `OTA_SIGNING_KEY` (File 型, 任意) — `image-gen.py` が使う OTA 署名秘密鍵。
  未設定時は repo 内の `tools/test_keys/secp256r1.privatekey` を使うが、**開発用のみ**。
  CI/CD 常用時は project-level CI/CD Variables へ移すこと。

manual OTA job 用の追加入力 / 既定値:
- `RUN_OTA_TEST` (Variable, 任意) — `true` のとき branch pipeline で `test_ota` を自動実行。
  未設定時は manual job のみ。
- `OTA_S3_BUCKET` (Variable, 任意) — 既定値 `rx65n-ota`
- `OTA_SERVICE_ROLE_ARN` (Variable, 任意) — 既定値
  `arn:aws:iam::094025684215:role/rx72n-ota-service-role`
- `OTA_SIGNING_PROFILE` (Variable, 任意) — 既定値 `rx65n_ota_profile_testkey`
- `OTA_CANDIDATE_VERSION` (Variable, 任意) — 既定値 `0.9.3`
- `AWS_DEFAULT_REGION` (Variable, 任意) — 既定値 `ap-northeast-1`
- `E2STUDIO_WORKSPACE_OTA` (Variable, 任意) — OTA candidate 再build用の一時 workspace

## CI/CD Pipeline

### Phase 8a: CK-RX65N (V1) パイプライン構築

| Step | Goal | Status |
|------|------|--------|
| 1 | GitLab リポジトリ作成・初期セットアップ | Done (MR !1) |
| 2 | ハードウェアセットアップ（人間作業） | Done (COM6 確定) |
| 3 | ビルド環境構築（headless build） | Done |
| 4 | フラッシュ書き込み自動化（rfp-cli） | Done |
| 5 | AWS IoT Core セットアップ | Done |
| 6 | MQTT PubSub 動作確認 | Done |
| 7 | OTA テスト | Done (auto-run integrated; warning follow-up in issue #9) |
| 8 | CI/CD パイプライン統合 | Done |

### Step 7-3: OTA observability contract

`tools/test_ota.py` を Step 7-4 / Step 7-5 の正本アナライザとして扱う。
用途は 2 つ:

- live UART monitor: `--port COMx --raw-log artifacts/test_ota/ota_uart_raw.log --summary-json artifacts/test_ota/ota_summary.json`
- offline analysis: `--input-log <uart_log>`

#### Progress markers / 進捗マーカー

| Stage | Representative UART log | Required for success |
|------|--------------------------|----------------------|
| boot | `OTA over MQTT demo, Application version x.y.z`, `---------Start OTA Update Task---------` | No |
| waiting_for_job | `Request Job Document event Received`, `Waiting for OTA job...` | No |
| job_received | `Received OTA Job.` | **Yes** |
| download_started | `Request File Block event Received`, `Starting The Download.` | `Starting The Download.` が **Yes** |
| downloading | `Received File Block event Received`, `Downloaded block N of M.` | `Downloaded block N of M.` が **Yes** |
| close_file | `Close file event Received` | No |
| activate_image | `Activate Image event Received` | No |
| reboot | `software reset...`, boot loader banner (`BootLoader`) | No |
| self_test | `OTA image is in selfcheck mode.` | No |
| accepted | `New image has higher version than current image, accepted!` | **Yes** |
| accepted (optional) | `Accepted and committed final image.`, `Successful to erase the buffer area` | No |

#### Failure classes / 失敗分類

`tools/test_ota.py` の `ERROR_PATTERNS` が正本。分類は以下の 2 系統に分ける:

- 明示的エラーログあり:
  `resource_init_failed`, `mqtt_not_connected`, `missing_thing_name`,
  `job_document_error`, `create_file_failed`, `download_data_error`,
  `flash_write_failed`, `missing_codesigncert`, `codesigncert_load_failed`,
  `signature_verification_failed`, `close_file_failed`,
  `activate_or_boot_failed`, `self_test_failed`, `version_invalid`,
  `commit_state_invalid`, `image_rejected`, `image_aborted`,
  `ota_job_marked_failed`, `bootloader_error`
- タイムアウト由来:
  `no_uart_output`, `waiting_for_ota_job`, `download_not_started`,
  `download_incomplete`, `close_or_signature_phase`,
  `reboot_or_selfcheck_missing`, `acceptance_not_observed`,
  `new_version_not_observed`, `expected_version_not_observed`

#### Success rule / 成功判定

- required marker を全て観測する
  - `job_received`, `download_started`, `block_downloaded`, `image_accepted`
- `close_file`, `activate_image`, `selfcheck_mode` は観測できれば progress 補助情報として扱う
  - live UART では欠落するケースがあり、単独では失敗条件にしない
- fatal な error classification を 1 件も出さない
- `--expected-version` を指定した場合は、その version が `Application version` に出る
- `--expected-version` 未指定の場合は、OTA 前後で **2 つの異なる version** を観測する

#### CI artifacts / 保存物

`test_ota` job は Step 7-3 時点で以下の保存先を予約し、artifact として回収する:

| Path | Producer | Purpose |
|------|----------|---------|
| `artifacts/test_ota/ota_uart_raw.log` | `tools/test_ota.py --raw-log` | 1 行ごとの UTC wallclock + relative seconds を残す UART 正本ログ |
| `artifacts/test_ota/ota_summary.json` | `tools/test_ota.py --summary-json` | success / classification / marker hit / versions を機械判定用に保存 |
| `artifacts/test_ota/serial_ports.txt` | CI job | 実行前 COM port inventory |
| `artifacts/test_ota/ota_job_meta.json` | CI job | `started_at_utc`, `ended_at_utc`, commit/job/pipeline ID, UART 設定 |
| `artifacts/test_ota/test_ota_help.txt` | CI job | 実行時 CLI surface の固定 |

補足:
- `ota_uart_raw.log` の prefix 形式は `[UTC][+elapsed] ...` とする
- offline analysis はこの prefix を再利用して停止位置の相対秒を復元する
- Step 7-3 は観測点定義まで。AWS OTA Job 作成・実機実行・manual job 化は issue #6 / #7 で続行

### Step 7-5: manual CI OTA job

`.gitlab-ci.yml` の `test_ota` は Step 7-5 で **manual live job** として実装する。
現時点では `allow_failure: true` を維持し、安定化までは段階導入とする。

実行フロー:

1. `tools/build_ota_candidate.py` で baseline より高い version の OTA candidate を生成
2. `tools/create_ota_update.py` で S3 upload / `create-ota-update` / create status poll
3. `tools/test_ota.py --reset-cmd ...` で live UART を観測
4. `aws iot describe-job-execution` を artifact に保存

保存物:

- `artifacts/test_ota/create_ota_input.json`
- `artifacts/test_ota/create_ota_output.json`
- `artifacts/test_ota/ota_s3_put_output.json`
- `artifacts/test_ota/ota_update_status.json`
- `artifacts/test_ota/signing_job.json`
- `artifacts/test_ota/ota_job_meta.json`
- `artifacts/test_ota/ota_uart_raw.log`
- `artifacts/test_ota/ota_summary.json`
- `artifacts/test_ota/test_ota_console.log`
- `artifacts/test_ota/job_execution.json`

happy path 判定メモ:

- 2026-03-08 の実機成功ログでは `OTA image is in selfcheck mode.` は出なかった
- その代わり UART では `BootLoader` -> `Application version 0.9.3` ->
  `New image has higher version than current image, accepted!` ->
  `OTA Completed successfully!` を確認
- AWS `describe-job-execution` も `SUCCEEDED`
- したがって Step 7-5 以降の success 判定では `selfcheck_mode` を必須にしない

前提:

- `test_mqtt` まで成功していること
- boot loader trust anchor と一致する AWS Signer profile
  `rx65n_ota_profile_testkey` が利用可能であること
- OTA source bucket `rx65n-ota` と service role
  `arn:aws:iam::094025684215:role/rx72n-ota-service-role` が利用可能であること
- 実機は `OBE110020` / `COM6` の CK-RX65N V1

自動実行へ広げる条件メモ:

- manual run で連続成功実績を積む
  - 目安: 3 回以上、追加の人手 recovery なしで success
- issue #8 系の UART / power-cycle 問題が routine recovery に落ち着く
- AWS の bucket / signer profile / service role の前提が安定している
- `allow_failure: true` を外しても branch pipeline の信頼性を下げない

### Step 8: CI/CD pipeline integration

> Historical note:
> The detailed Step 8 notes below describe the earlier CK-RX65N pipeline track.
> In the current RX72N-only branch, `.gitlab-ci.yml` now covers the RX72N baseline path
> `build_rx72n -> flash_rx72n -> provision_rx72n -> test_mqtt_rx72n`,
> while the rendered-credential candidate path remains
> `build_rx72n_mqtt_candidate -> package_rx72n_mqtt_candidate_rsu`.

2026-03-08 時点の実装状態:

- `.gitlab-ci.yml` は `build -> flash -> provision -> test_mqtt -> test_ota` を 1 本に統合済み
- `provision`, `test_mqtt` は `main` で blocking job として運用開始済み
- `test_ota` は `main` / branch pipeline 上で **既定 auto 実行** に切り替え済み
  - `RUN_OTA_TEST=false` を与えた場合のみ manual fallback
- `test_ota` は引き続き `allow_failure: true` とし、安定化期間中は warning 扱いで運用する
- issue `#9` は Step 8 完了後の OTA auto-run 安定化フォローとして継続する
- project-based pipeline visibility を OFF にしているため、外部 API / 非メンバーから pipeline/job の状態は公開確認できない

観測済み証跡:

- `main` pipeline `#416`
  - commit `4e49551f`
  - `build` job `#1720` success
  - `flash` job `#1721` success
  - `provision` job `#1722` success (`allow_failure: true`)
  - `test_mqtt` job `#1723` success (`allow_failure: true`)
- branch `codex/step8-pipeline-integration` pipeline `#417`
  - commit `b51d1f3`
  - `build` job `#1725` success
  - `flash` job `#1726` success
  - `provision` job `#1727` success (`allow_failure: true`)
  - `test_mqtt` job `#1728` success (`allow_failure: true`)
- branch `codex/step8-pipeline-integration` pipeline `#418`
  - commit `acb7e16`
  - `build` job `#1730` success
  - `flash` job `#1731` success
  - `provision` job `#1732` success (`allow_failure: false`)
  - `test_mqtt` job `#1733` success (`allow_failure: false`)
- branch `codex/step8-pipeline-integration` pipeline `#419`
  - commit `d452dc9`
  - `build` job `#1735` success
  - `flash` job `#1736` success
  - `provision` job `#1737` success (`allow_failure: false`)
  - `test_mqtt` job `#1738` success (`allow_failure: false`)
- branch `codex/step8-pipeline-integration` pipeline `#420`
  - commit `001c374`
  - `build` job `#1740` success
  - `flash` job `#1741` success
  - `provision` job `#1742` success (`allow_failure: false`)
  - `test_mqtt` job `#1743` success (`allow_failure: false`)
  - `test_ota` job `#1744` success (`allow_failure: true`, auto-run)
- branch `codex/step8-pipeline-integration` pipeline `#421`
  - commit `8913586`
  - `build` job `#1745` success
  - `flash` job `#1746` success
  - `provision` job `#1747` success (`allow_failure: false`)
  - `test_mqtt` job `#1748` success (`allow_failure: false`)
  - `test_ota` job `#1749` success (`allow_failure: true`, auto-run)
- `main` pipeline `#422`
  - commit `07354ca4`
  - `build` job `#1750` success
  - `flash` job `#1751` success
  - `provision` job `#1752` success (`allow_failure: false`)
  - `test_mqtt` job `#1753` success (`allow_failure: false`)
  - `test_ota` job `#1754` failed (`allow_failure: true`, auto-run)
  - pipeline 全体は success。`test_ota` は `download_incomplete` で終了し、issue `#9` で継続観察する
- `main` pipeline `#440`
  - commit `d57044f5`
  - `build` job `#1880` success
  - `flash` job `#1881` success
  - `provision` job `#1882` success (`allow_failure: false`)
  - `test_mqtt` job `#1883` success (`allow_failure: false`)
  - `test_ota` job `#1884` failed (`allow_failure: true`, auto-run)
  - pipeline 全体は success。MR `!15` で post-reboot 観測時間を延長した後も、
    安定化 follow-up は issue `#9` で継続する

補足:

- Step 8 の完了判定そのものは、MR `!13` を protected `main` へ反映した最初の統合証跡である
  pipeline `#422` を正本とする
- pipeline `#440` は Step 8 完了後の安定化観測として扱い、issue `#9` 側の追跡対象に置く

Step 8 の完了判定:

1. blocking 化した `provision` / `test_mqtt` が `main` pipeline `#422` で success
2. `test_ota` の auto-run が `main` でも配線され、branch では `#420` / `#421` で連続 success を確認済み
3. `test_ota` の `allow_failure: true` は意図した段階導入設定であり、issue `#9` は post-completion follow-up として扱う
4. 以上より、**Phase 8a / Step 8 は完了** とし、次の主対象は **Phase 8b: RX72N Envision Kit 移植** へ移す

次フェーズ開始メモ:

1. CK-RX65N V1 上で確立した `iot-reference-rx` の build / flash / provision / MQTT / OTA の運用手順を移植元ベースラインとして固定する
2. Phase 8b では RX72N Envision Kit 側で CPU / memory map / Ethernet PHY / debugger / FreeRTOS port / r_fwup dual-bank 条件の差分を順に潰す
3. `test_ota` の安定化 issue `#9` は並走で追うが、Phase 8b 着手自体の blocker とはみなさない

### Phase 8b: RX72N Envision Kit 移植

| Item | CK-RX65N (V1) | RX72N Envision Kit | 対応方針 |
|------|---------------|-------------------|----------|
| CPU コア | RXv2 | RXv3 + DPFPU | `-cpu=rxv3 -dpfpu` |
| コードフラッシュ | 2MB (1MB x 2) | 4MB (2MB x 2) | リンカスクリプト変更 |
| RAM | 640KB | 1MB | リンカスクリプト変更 |
| Ethernet PHY | LAN8720 (RMII) | KSZ8041NL (MII) | r_ether_rx 設定・MPC 変更 |
| デバッガ | E2 emulator Lite | E2OB (FINE) | rfp-cli 設定変更 |
| FreeRTOS ポート | RX600v2 | RX700v3_DPFPU | ポートレイヤー切替 |
| r_fwup | RX65N_DualBank | RX72N_DualBank | ImageGenerator パラメータ変更 |

#### 2026-03-24: RX72N トラックを `iot-reference-rx` 側へ再集約

- `rx72n-envision-kit` の MR `!52` は論点が build / flash / provision / MQTT / OTA まで広がりすぎたためクローズし、RX72N Envision Kit project 追加の正本トラックは Issue `#11` へ切り直した
- 初手の完了条件は OTA まで広げず、`Projects/boot_loader_rx72n_envision_kit` と `Projects/aws_ether_rx72n_envision_kit` を追加したうえで `build -> flash -> provision -> MQTT` の baseline を通すことに絞る
- 細かなデバッグを優先するため、RX72N Envision Kit #1 は Raspberry Pi からローカル PC へ付け替えた
  - デバッガ: ローカル PC 直結
  - `iot-reference-rx` 側では terminal/UART は `COM7` の 1 本前提で扱う

#### 2026-03-25: local #1 で build / boot_loader / RSU handoff を再確認

- branch `codex/11-add-rx72n-envision-projects` / MR `!17` 上で、`tools/build_headless_rx72n.ps1` により `boot_loader_rx72n_envision_kit` と `aws_ether_rx72n_envision_kit` の headless build が成功した
- local RX72N #1 では `rfp-cli -list-tools` から `e2l:OBE110008` が見え、boot_loader banner は `COM7` に出ることを確認した
  - `iot-reference-rx` の RX72N app 設定も `BSP_CFG_SCI_UART_TERMINAL_CHANNEL=7`, `BSP_CFG_SCI_UART_TERMINAL_BITRATE=921600` であり、現段階では `COM7` の single-UART 前提で追う
  - one-shot banner は flash 後にポートを開くと取り逃がしやすく、先に COM を開いたまま `rfp-cli -sig -run -noquery` を叩く観測が有効
- RSU 生成では鍵 mismatch に注意
  - `tools/test_keys/secp256r1.privatekey` で作った RSU は `verify install area buffer [sig-sha256-ecdsa]...NG`
  - `sample_keys/secp256r1.privatekey` は RX72N boot_loader に埋め込まれた `src/key/code_signer_public_key.h` と対応しており、これで生成した RSU は `verify ... OK` と `activating image ... OK` まで進んだ
- direct-flash でも app handoff の鬼門は残っている
  - `aws_ether_rx72n_envision_kit.mot` を `rfp-cli -p ... -v -run -noquery` で直接書いたあとに COM を先開きで観測しても、復帰してくるのは `COM7` の boot_loader banner (`==== RX72N : BootLoader [dual bank] ==== / send image(*.rsu) via UART.`) だけだった
  - したがって現段階では「RSU verify / activate までは進むが app の UART 生存確認はまだ取れていない」「direct-flash でも app 側へ制御が渡り切っていないか、渡った直後に落ちている」可能性が高い
- app linker vector の不整合も修正した
  - `aws_ether_rx72n_envision_kit` の `EXCEPTVECT/RESETVECT` は当初 `0xFFFBFF80/0xFFFBFFFC` だったが、bootloader の `R_FWUP_ExecImage()` は `FWUP_CFG_MAIN_AREA_ADDR_L + FWUP_CFG_AREA_SIZE - 4` (= `0xFFFEFFFC`) を reset vector として参照する
  - そのため app linker を `0xFFFEFF80/0xFFFEFFFC` へ修正し、build 後の map と RSU segment もこの新アドレスへ揃えた
  - ただし vector 修正後も local 実機では `verify ... OK` / `activating image ... OK` の先が無音で、追加の source-level debug がまだ必要
- local bring-up helper として以下を追加した
  - `tools/build_headless_rx72n.ps1`
  - `tools/monitor_rx72n_boot.py`
  - `tools/build_fwup_v2_rsu.py`
  - `tools/test_uart_download_rx72n.py`
  - `tools/run_rx72n_local_baseline.ps1`

#### 2026-03-25: Issue #12 で legacy bootloader トラックへ切り替え

- `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx` は `r_fwup` sample 系 bootloader ではなく、
  `rx72n-envision-kit/projects/renesas/rx72n_envision_kit/e2studio/boot_loader`
  由来の legacy `rx72n_boot_loader` ベースへ差し替える方針に切り替えた
- 置換後も `iot-reference-rx` 側では folder 名を `boot_loader_rx72n_envision_kit` に維持し、
  build 出力名も `boot_loader_rx72n_envision_kit.*` に揃える
- app 側 handoff は legacy bootloader 前提へ戻す
  - `EXCEPTVECT/RESETVECT`: `0xFFFBFF80 / 0xFFFBFFFC`
  - terminal UART: `SCI7 / 921600`
- local baseline helper は legacy bootloader banner
  `send "userprog.rsu" via UART.` を待ち受ける
- RSU 生成時の PRM CSV は bootloader project ではなく
  `Projects/aws_ether_rx72n_envision_kit/.../RX72N_DualBank_ImageGenerator_PRM.csv`
  を使う
- ここでの切り替えは「source / metadata / local helper の整合」までであり、
  local 実機での initial image download -> reset -> app 起動の再確認は引き続き Issue #12 の検証項目

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

### Smart Configurator / FIT モジュール運用

- RX FIT モジュールはローカルの FIT module cache
  `%USERPROFILE%\\.eclipse\\com.renesas.platform_download\\FITModules\\`
  から解決される
- 必要バージョンの FIT モジュールが欠けていると、Smart Configurator が
  一部コードを生成しないまま通ることがある
- CK-RX65N V1/V2 を切り替える場合は、少なくとも以下の board metadata を揃える
  - `.scfg`
  - `.settings/com.renesas.smc.e2studio.qe.xml`
  - `.cproject`
- 2026-03-07 時点で CCRX の `aws_ether_ck_rx65n_v2` と
  `boot_loader_ck_rx65n_v2` は V1 (`CK-RX65N`) に揃えて管理する

### CK-RX65N J16 ジャンパ

| 設定 | 用途 |
|------|------|
| 1-2 (DEBUG) | E2 Lite デバッグ・rfp-cli フラッシュ書き込み |
| 2-3 (RUN) | ファームウェア単独実行（マニュアル記載） |

**実測結果:** J16=DEBUG (1-2) のまま rfp-cli `-run` でアプリが正常起動する。
ただしこれは **flash 直後に E2 Lite が release した条件での実測** であり、
**cold boot / power cycle 後の通常実行条件を保証するものではない**。

**2026-03-07 の再整理:**
- 公式資料では、初回書き込みは `J16=DEBUG (1-2)`、初回起動・通常実行は
  `J16=RUN (2-3)` が前提
- CK-RX65N V1 では `J14` が **E2 Lite + 電源供給**、`J20` が UART
- ただし公式 getting started guide では、**board は `J20` (Communication port) からも給電可能**
  とされている（供給電流は 100 mA max）
- 従って **`J14` だけ抜く操作は true power-off とは限らない**
- `DEBUG` のまま `rfp-cli -run` で起動できるケースはあるが、
  **通常運用の前提としては扱わない**

以後の手動試験では、**書き込み時は `DEBUG`、実行確認は `RUN`** を基本とする。

### UART 0-byte after flash/test boundary

- 既知 issue: #8
- 症状:
  - COM ポート列挙・open 自体は成功する
  - CLI 応答なし
  - 監視を 30-120 秒続けても UART 受信 `0 byte`
- 2026-03-07 の Step 7-4 試行では、`userprog.mot` 書き込みでも boot_loader/app 別書き込みでも
  同じ症状になり、provision / OTA 実行前に停止した
- さらに `boot_loader` 単体書き込み + `miniterm COM6 115200` + J16=`RUN` + 物理 reset でも
  文字は一切出なかった
- ただし後続の切り分けで、CK-RX65N V1 の E2 Lite は `OBE110020`、`OBE110008` は
  RX72N Envision Kit 側であることを hardware inventory / `rfp-cli -list-tools` で再確認した
- よって Step 7-4 の手動試験で `OBE110008` を使っていた場合、その UART 無応答は
  **CK-RX65N の有効な観測とはみなさない**。`OBE110020` で再試行してから issue #8 系へ進むこと
- `OBE110020` で `boot_loader_ck_rx65n_v2.mot` を書き込み直すと、`miniterm COM6 115200`
  で `==== RX65N : BootLoader [dual bank] ==== / send image(*.rsu) via UART.` を確認できた
- よって Step 7-4 の active blocker は「UART dead」ではなく、**正しい target で app path を
  再度通すこと** に更新する
- さらに切り分けた結果、`aws_ether_ck_rx65n_v2.mot` 単体は raw app image であり、
  boot loader が初回起動に必要とする FWUP metadata / signed image までは含まない。
  初回投入は `image-gen.py` で作る `userprog.mot` を正本とする
- `userprog.mot` を書き込んだ後は `tools/provision.py` が通り、`tools/test_mqtt.py` も
  PASS。UART 上で `Waiting for OTA job...` まで確認できた
- 2026-03-08 の OTA rerun では signer / version の 2 段階で blocker が分離した
  - `codesigncert` mismatch:
    AWS Signer profile `rx65n_ota_profile20` は ACM certificate
    `arn:aws:acm:ap-northeast-1:094025684215:certificate/f7bf6fc9-4f70-4c5c-a09e-724f81c677cb`
    を使っていた。device に別の公開証明書を入れると
    `otaPal_CheckFileSignature: R_FWUP_VerifyImage ...` で close-file phase が失敗する
  - same-version OTA candidate:
    ACM 公開証明書を `codesigncert` に入れると signature verification は通るが、
    app binary 自体が `0.9.2` のままだと
    `Version of new image is identical, or application has rolled-back to initial version.`
    -> `Image self-test passed!` -> `OTA is failed!` になる
  - したがって OTA candidate は `fileVersion` だけでなく app binary の
    `APP_VERSION_BUILD` も baseline より大きくして生成する必要がある
- `tools/build_ota_candidate.py`
  - `APP_VERSION_{MAJOR,MINOR,BUILD}` を一時的に差し替えて headless build
  - `image-gen.py` で OTA candidate `.rsu` を生成
  - 終了時に `demo_config.h` を元へ戻すので baseline source を汚さない
- `tools/provision.py --reset-cmd`
  - flash 直後に app がすでに起動して CLI の 10 秒 window を過ぎている場合がある
  - 外部 reset/run コマンドを先に実行し、その直後に UART を開いて
    CLI へ入るための option を追加
  - 実運用では `rfp-cli -v <baseline-userprog.mot> -run -noquery` を reset-cmd に
    使うと、再書き込みなしで fresh boot を取りやすい
- 2026-03-08 の final rerun では、boot loader が信頼する test key 系の cert を
  ACM に import し、AWS Signer profile `rx65n_ota_profile_testkey` を新設
  - imported ACM certificate:
    `arn:aws:acm:ap-northeast-1:094025684215:certificate/fb9f57c0-71d6-464a-ac7e-4ec1b7aab3bc`
  - signing profile:
    `rx65n_ota_profile_testkey`
  - 理由:
    app-side `codesigncert` だけ合わせても、boot loader 側の埋め込み公開鍵
    (`src/key/code_signer_public_key.h`) が別鍵のままだと reboot-time verify で rollback する
- 成功した OTA rerun:
  - OTA update: `ck-rx65n-ota-1772905631`
  - job: `AFR_OTA-ck-rx65n-ota-1772905631`
  - signer job: `bf055aed-52d8-459c-8c7c-386c79d6aebc`
  - AWS state:
    - `get-ota-update`: `CREATE_COMPLETE`
    - `describe-job-execution --thing-name ck-rx65n-01`: `SUCCEEDED`
  - UART 観測:
    - baseline app version `0.9.2`
    - close-file verification passed
    - self-test / bank swap 実行
    - boot loader `verify install area main [sig-sha256-ecdsa]...OK`
    - post-OTA app version `0.9.3`
    - `New image has higher version than current image, accepted!`
  - artifact:
    `C:\codex\step7_4_run\ota_093\run_20260308_024711\ota_summary.json`
    classification=`success`, versions_seen=`0.9.2`,`0.9.3`
- 暫定 workaround:
  - J14 / J20 を含む board power cycle
  - 管理者権限があるなら host 側 USB serial bridge restart を試す
- retry 順序:
  1. `rfp-cli -d RX65x -t e2l -if fine -list-tools` で `OBE110020` を確認
  2. `OBE110020` で `userprog.mot` を書き込み
  3. `provision.py --reset-cmd ...` で fresh boot の CLI window を取りながら再プロビジョニング
  4. `test_mqtt.py --reset-cmd ...` で CLI / MQTT baseline 復旧確認
  5. `Waiting for OTA job...` を確認したら、boot loader trust anchor と同じ cert の
     Signer profile で OTA Job 作成へ進む

## Changelog / 変更履歴

### 2026-03-07: Step 7-4 attempt — blocked before OTA by UART 0-byte state

- `main` merge commit `ddac254` で headless build を再確認
- baseline image 生成を確認
  - `tools/generate_signer_cert.py` success
  - `image-gen.py -ibp` で `userprog.mot` success
- AWS 側 preflight は通過
  - AWS CLI v2 default identity OK
  - OTA 用 bucket / signing profile / service role は既存資材を確認
- ただし UART が復旧せず、実機 OTA 本体には進めなかった
  - `rfp-cli` の combined flash (`userprog.mot`) success
  - `rfp-cli` の separate flash (boot_loader + app) success
  - `tools/test_mqtt.py` on `COM6` / `COM7` は両方 `0 byte`
  - `boot_loader` 単体 + `miniterm COM6 115200` + J16=`RUN` + 物理 reset でも無音
- ただし後続切り分けで `OBE110020 = CK-RX65N V1`, `OBE110008 = RX72N Envision Kit`
  を再確認。`OBE110008` を使った試験結果は CK-RX65N の有効観測としては扱わない
- 停止点はいったん `correct E2 Lite selection -> flash -> UART observation` に修正
- さらに `OBE110020` + `boot_loader_ck_rx65n_v2.mot` + `miniterm COM6 115200` で
  boot loader banner を確認
- `aws_ether_ck_rx65n_v2.mot` 単体では boot loader が main image と見なせず、
  初回投入は `userprog.mot` が必要であることを確認
- `userprog.mot -> provision.py -> test_mqtt.py` の順で baseline を再構築し、
  OTA task が `Waiting for OTA job...` へ到達することを確認
- `tools/flash.bat` は `Program Files (x86)` を含む `%RFP_CLI%` を `if (...)` で評価して
  batch parse error を起こしていたため、前提チェックを単純な `goto` 形式へ修正
- さらに host 環境では `flash.bat` が Step 1 後に復帰してしまう症状が残ったため、
  現在は `flash.bat` を薄い wrapper にし、実処理は `tools/flash.ps1` で順次実行する
  - 詳細ログと実行コマンドは `docs/ja/step7_4_ota_attempt.md`
  - 次の論点は `OBE110020` で app path を再試行し、`test_mqtt.py` と provisioning へ戻すこと

### 2026-03-08: Step 7-4 final rerun — OTA happy path success

- signer trust mismatch を修正
  - boot loader の埋め込み公開鍵は repo test key 系
  - ACM import:
    `arn:aws:acm:ap-northeast-1:094025684215:certificate/fb9f57c0-71d6-464a-ac7e-4ec1b7aab3bc`
  - AWS Signer profile:
    `rx65n_ota_profile_testkey`
- `tools/provision.py` に `--reset-cmd` を追加
  - flash 後に boot window を取り逃がしても、`rfp-cli -v userprog.mot -run -noquery`
    を先に実行してから UART を開くことで確実に CLI へ入れる
- baseline 再確認
  - `flash.bat OBE110020 ... userprog.mot` success
  - `provision.py --reset-cmd ... --code-sign-cert userprog_codesign_cert.pem` success
  - `test_mqtt.py --reset-cmd ...` success
- OTA happy path success
  - OTA update: `ck-rx65n-ota-1772905631`
  - job: `AFR_OTA-ck-rx65n-ota-1772905631`
  - `test_ota.py` summary: `success`
  - `get-ota-update`: `CREATE_COMPLETE`
  - `describe-job-execution`: `SUCCEEDED`
  - observed app versions: `0.9.2 -> 0.9.3`

### 2026-03-08: Step 7-5 — manual CI OTA job integration

- `.gitlab-ci.yml` の `test_ota` を observability contract から live manual job へ更新
  - OTA candidate build
  - S3 upload / `create-ota-update`
  - live UART observation
  - AWS job execution artifact 保存
- `tools/create_ota_update.py` を追加
  - S3 upload
  - `create-ota-update`
  - `get-ota-update` poll
  - `signer describe-signing-job` / `ota_job_meta.json` 保存
- `provision` / `test_mqtt` の reset 経路を `rfp-cli -v userprog.mot -run -noquery`
  ベースへ揃え、re-flash せずに fresh boot window を取る構成へ変更
- `test_ota.py` に cp932 console 向け `stdout.reconfigure(errors="backslashreplace")`
  を追加

### 2026-03-08: Step 8 follow-up — OTA auto-run on branch pipelines

- `claude-index/DEVELOPMENT.md` を参照し、follow-up 用 issue `#9`
  (`Step 8 follow-up: OTA auto-run の安定化（branch/main pipeline）`) を起票
- `.gitlab-ci.yml` の `RUN_OTA_TEST` 既定値を `true` へ変更
  - `RUN_OTA_TEST=false` のときだけ `test_ota` を manual fallback にする
  - `allow_failure: true` は維持し、安定化期間中は warning 扱いで運用
- branch `codex/step8-pipeline-integration` pipeline `#420` で auto-run を確認
  - `test_ota` job `#1744` success
  - `build` / `flash` / `provision` / `test_mqtt` も success
- これにより branch 上では
  `build -> flash -> provision -> test_mqtt -> test_ota(auto)` の一連成功を確認済み

### 2026-03-09: Step 8 follow-up — main pipeline observation after !15

- MR `!15` を `main` へマージし、`test_ota` の post-reboot 観測時間を延長
- `main` pipeline `#440` で follow-up 観測を実施
  - `build` `#1880` success
  - `flash` `#1881` success
  - `provision` `#1882` success
  - `test_mqtt` `#1883` success
  - `test_ota` `#1884` は `allow_failure: true` の warning failure
- pipeline 全体は success のままで、OTA auto-run の安定化課題は issue `#9` に集約
- Step 8 の完了判定は維持し、完了証跡の正本は引き続き protected `main`
  反映直後の pipeline `#422` とする

### 2026-03-08: Step 8 complete — main pipeline integration confirmed

- MR `!13` を `main` へマージ
- `main` pipeline `#422` で protected branch 上の統合状態を確認
  - `build` `#1750` success
  - `flash` `#1751` success
  - `provision` `#1752` success
  - `test_mqtt` `#1753` success
  - `test_ota` `#1754` は `allow_failure: true` の warning failure
- `test_ota` `#1754` は `download_incomplete` classification で終了し、AWS job execution も
  job 終了時点では `IN_PROGRESS`
- ただし Step 8 の観点では、`main` 上で
  `build -> flash -> provision -> test_mqtt -> test_ota(auto)` の wiring 自体は確認できたため、
  issue `#9` を post-completion stabilization として分離し、**Step 8 は完了** と判断する
- 次の主対象は `Phase 8b: RX72N Envision Kit 移植`

### 2026-03-08: Step 7-5 follow-up — live success criteria adjustment

- pipeline `#413` / `test_ota` job `#1699` で live OTA 自体は成功
  - UART: `BootLoader` -> `Application version 0.9.3` -> `accepted!`
  - AWS job execution: `SUCCEEDED`
- ただし `test_ota.py` が `selfcheck_mode` を必須にしていたため false negative になった
- `selfcheck_mode` を optional に変更し、`job_execution.json` も
  stray text を除去して JSON として保存するよう修正
- あわせて `ota_uart_raw.log` は chunk 単位ではなく **完成した UART 行単位** で
  timestamp prefix を付けるよう修正し、offline analysis で marker を再検出しやすくした

### 2026-03-08: Step 7-5 follow-up 2 — intermediate marker relaxation

- rerun pipeline `#414` の `test_ota` job `#1709` では、live OTA / AWS job execution は成功
  - UART: `BootLoader` -> `Application version 0.9.3` -> `accepted!`
  - AWS `describe-job-execution`: `SUCCEEDED`
- ただし `Close file event Received` / `Activate Image event Received` は観測できず、
  これも false negative の原因になった
- `tools/test_ota.py` ではこの 2 つも required から外し、成功判定は
  より安定して観測できる marker 群へ寄せた

### 2026-03-07: Step 7-3 — OTA observability markers and failure classification

- `tools/test_ota.py` を追加
  - live UART monitor と offline log analysis の 2 モード
  - `job_received` から `image_accepted` までの required marker を固定
  - `missing_codesigncert`, `signature_verification_failed`, `self_test_failed` など
    OTA 特有の failure class を実装
  - raw log の `[UTC][+elapsed]` prefix を offline analysis でも再利用できるようにした
- `.gitlab-ci.yml` の `test_ota` に observability artifact 契約を追加
  - `artifacts/test_ota/` を `when: always` で保存
  - `ota_job_meta.json`, `serial_ports.txt`, `test_ota_help.txt`, `README.txt` を生成
  - live OTA 本体は未実装のまま issue #7 で継続
- CLAUDE.md に進捗マーカー・失敗分類・成功条件・CI 保存物の方針を反映

### 2026-03-07: Step 7-2 — OTA enabled build and static prerequisites

- `Projects/aws_ether_ck_rx65n_v2/e2studio_ccrx/src/frtos_config/demo_config.h` で
  `ENABLE_OTA_UPDATE_DEMO=1` を有効化し、2026-03-07 JST に headless build を確認
  - `tools/build_headless.bat` success
  - 生成物: `aws_ether_ck_rx65n_v2.mot`, `boot_loader_ck_rx65n_v2.mot`
  - `image-gen.py` を逐次実行し、`userprog.mot` (1406672 bytes) と
    `userprog.rsu` (404224 bytes) を生成
- dual bank / vector / image generation 前提を確認
  - app / boot loader とも `FWUP_CFG_UPDATE_MODE=0` (dual bank),
    `FWUP_CFG_SIGNATURE_VERIFICATION=0` (ECDSA)
  - `BSP_CFG_CODE_FLASH_BANK_MODE=0`, `BSP_CFG_CODE_FLASH_START_BANK=0`
  - app linker vectors: `EXCEPTVECT=0xFFFEFF80`, `RESETVECT=0xFFFEFFFC`
  - boot loader linker vectors: `EXCEPTVECT=0xFFFFFF80`, `RESETVECT=0xFFFFFFFC`
  - image generation parameter: `RX65N_DualBank_ImageGenerator_PRM.csv`
- OTA 実行前の必要入力を整理
  - group vars: `E2L_SERIAL_CK_RX65N_J14`, `UART_PORT_CK_RX65N_J20`, `MAC_ADDR_CK_RX65N`
  - project vars: `AWS_IOT_ENDPOINT`, `AWS_IOT_THING_NAME`, `AWS_IOT_CERT`, `AWS_IOT_PRIVKEY`
  - OTA signing key: `OTA_SIGNING_KEY` (任意 override)
- 既知リスク / 対応
  - 旧 `tools/provision.py` は `codesigncert` を投入せず、OTA 署名検証が
    `No certificate stored in DF!` で失敗し得た
  - build で signing key から `userprog_codesign_cert.pem` を自動生成し、
    provision で `codesigncert` に書き込むよう修正
  - repo 内 test key は開発専用。継続運用するなら `OTA_SIGNING_KEY` を
    project-level CI/CD Variables へ移す
  - `test_ota` job 本体は未実装のまま issue #7 で継続

### 2026-03-07: Step 7-1 — Baseline success state and OTA success criteria

- Issue #3 の完了条件を CLAUDE.md に反映
- Step 6 の基準成功状態を固定
  - 正本コード: `main` merge commit `23712d32`
  - 実装差分の参照元: MR !7, head commit `7400bbed`
  - 観測済み成功証拠: pipeline #379 の `test_mqtt` job #1629 success (68.1s)
  - `.gitlab-ci.yml` の `test_mqtt` は `allow_failure: true` のため、pipeline 成功だけでなく job #1629 成功を記録対象とする
  - 成功マーカー: `Successfully connected to MQTT broker`, `Successfully subscribed to topic`, `Successfully sent QoS`
  - 失敗マーカー不在も条件: `DHCP failed`, `TLS connection failed`, `Failed to subscribe to topic` など
- OTA 成功条件をチェックリスト化
  - `ENABLE_OTA_UPDATE_DEMO=1` でビルド成功
  - AWS IoT OTA Job を受信
  - `userprog.rsu` のダウンロード完了
  - alternate bank への書き込み完了
  - bank 切り替え後に再起動
  - boot_loader の検証を通って新イメージで起動
  - 再起動後に Step 6 の MQTT 成功マーカーを再度満たす
  - ロールバックが発生しない
- 未解決事項を明文化
  - OTA 後に「新バージョンで起動した」と識別するログ / バージョン文字列は未固定
  - OTA Job 作成を手動にするか CI で自動化するかは未決
  - 署名鍵をテスト鍵のまま進めるか、本番鍵戦略を別 issue に切るかは未決
  - `ENABLE_OTA_UPDATE_DEMO=1` の静的確認は issue #4 で対応
  - `test_ota` CI ジョブ実装は issue #7 で対応
  - Tera Term と CI の COM ポート競合は既知制約として継続管理
  - AI エージェント運用差の詳細計測は別目的化せず、関連 issue コメントに軽く記録する方針
  - 本プロジェクトの第一目標は RX MCU で Fleet Provisioning / OTA が動作する環境を早期に成立させること
  - 安定稼働のための運用傾向は Step 7 系 issue のコメントで継続観察する

### 2026-03-06: Step 6 — MQTT PubSub connectivity test

- tools/test_mqtt.py 実装（MQTT 接続テスト自動化）
  - UART モニタリング で MQTT broker 接続・Topic subscribe・Publish の成功検出
  - 外部コマンド (rfp-cli) による デバイスリセット対応
  - USB サスペンド問題の対策（port open 前に rfp-cli 実行）
  - CLI 準備完了確認（リトライ付き）
  - エラーパターン検出（DHCP failure、TLS error 等）
- .gitlab-ci.yml に test_mqtt ジョブを統合
  - Stage: test（flash・build 後）
  - Manual trigger または RUN_AWS_TESTS フラグで実行
  - 120秒タイムアウト、resource group ロック機構
- tools/uart_download.py 追加（UART 診断ユーティリティ）
- MR !7 作成: Step 6 — MQTT PubSub connectivity test

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

# CI/CD運用

本リポジトリのCIは、WindowsでCC-RXビルドとAWS操作を行い、Raspberry Piに接続した
実機でflash、UART監視、MQTT、OTA、Fleet Provisioningを検証します。
job定義の正本は[`.gitlab-ci.yml`](../.gitlab-ci.yml)、接続構成とツールの現行値は
[hardware-config](https://gitlab.saffti.jp/oss/infra/hardware-config)です。

## 実機環境

| ID | 実機 | 接続 | Runner |
|---|---|---|---|
| `rx72n_ether` | RX72N Envision Kit | Ethernet | RPi #1 |
| `rx65n_bg96` | CK-RX65N V1 + BG96 | Cellular | RPi #3 |
| `rx671_wifi` | EK-RX671 + Type 1YN | Wi-Fi / SDIO | RPi #1 |

## Pipeline profile

| Profile | 起動元 | 用途 |
|---|---|---|
| `branch` | feature push | buildのみ |
| `mr` | merge request | RX72N / RX65Nの代表MQTT実機確認 |
| `mr-rx671` | RX671関連MR | RX671 network実機確認 |
| `main` | default branch push | RX72N / RX65N MQTTとRX671 network smoke |
| `release` | tag | RX72N / RX65N software TLS regressionとRX671 network smoke |
| `focused` | manual / API | 指定したターゲット・機能だけを実行 |
| `nightly_matrix` | schedule | 複数projectを含む重い回帰matrix |

## Focused pipelineの主な変数

| 目的 | 変数 |
|---|---|
| ターゲット別scope | `RX72N_TEST_SCOPE` / `RX65N_BG96_TEST_SCOPE` / `RX671_WIFI_TEST_SCOPE` |
| scope値 | `build` / `network` / `mqtt` / `ota` / `fleet` / `full` |
| TLS backend | `RX72N_TLS_BACKEND` / `RX65N_BG96_TLS_BACKEND` = `software`または`tsip` |
| TLS version gate | `*_REQUIRE_TLS_VERSION=TLSv1.3` |

未指定ターゲットは`build`へ明示的に絞ってください。秘密情報の値はpipeline引数やjob logへ
直接書かず、project CI/CD Variablesを使用します。

## 実機とAWSの安全境界

- feature pushはbuild-onlyとし、実機jobをMR / main / tag / focused / scheduleへ集約します。
- RX72NとRX671はcross-project lockを使用し、flashからtestまでの割り込みを防ぎます。
- OTA / Fleetはpipeline専用Thing、certificate、policy、Job、Stream、S3 prefixを使用します。
- cleanup jobは成功・失敗にかかわらず実行し、pipeline専用AWS資源の不存在をartifactへ記録します。
- one-shot OTA observer jobだけをretryしません。再検証は新しいpipelineで作成からcleanupまで一巡させます。
- 実機操作後はRunner、UART、lock、firmware、AWS資源の終了状態を確認します。

## Schedule #5

| 項目 | 現在値 |
|---|---|
| 名前 | Nightly focused test matrix |
| 状態 | **Inactive** |
| 時刻 | 02:20 JST（active時） |
| ref | `main` |
| 変数 | `PIPELINE_PROFILE=nightly_matrix` / `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true` |

Schedule再開、変数変更、追加playはMaintainer / Ownerの承認後に行います。

## 代表証跡

- release tag pipeline: [#11140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140)
- RX671 fixed-SHA 5-run campaign: [Issue #140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/140)
- 機能別の代表pipeline: [validation-evidence.md](validation-evidence.md)

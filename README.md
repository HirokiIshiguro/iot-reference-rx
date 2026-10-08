# FreeRTOS LTS IoT Reference for Renesas RX

[Renesas公式版](https://github.com/renesas/iot-reference-rx)を、RX72N、RX65N、RX671へ
展開したFreeRTOS / AWS IoT実機検証用フォークです。MQTT、OTA、Fleet Provisioning、
TSIP（ハードウェア暗号）をGitLab CIで検証します。

ベースはFreeRTOS `202604.00-LTS-rx`、最新リリースは
[`v202604.00-LTS-rx-1.0.0-saffti-1.4.0`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.4.0)です。
変更点は[Changelog](Changelog.md)を参照してください。

## 対応ターゲット

| ターゲット | 接続 | 主なプロジェクト |
|---|---|---|
| RX72N Envision Kit | Ethernet | [software](Projects/aws_ether_rx72n_envision_kit/) / [TSIP](Projects/aws_ether_rx72n_envision_kit_tsip/) |
| CK-RX65N V1 | BG96 Cellular | [software](Projects/aws_bg96_ck_rx65n/) / [TSIP](Projects/aws_bg96_ck_rx65n_tsip/) |
| EK-RX671 | Murata Type 1YN Wi-Fi | [software](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls) / [TSIP](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls) |

## 代表性能

### 通信

`SINK`はMCUから対向への送信、`SOURCE`は対向からMCUへの受信です。
TLSは1.2の測定値で、`software`はソフトウェア暗号、`TSIP hardware`はMCU内蔵暗号を示します。

| ターゲット | 接続 | 方式 | SINK | SOURCE | 固定測定 |
|---|---|---|---:|---:|---|
| RX72N Envision Kit | Ethernet | TCP | 84.373 Mbps | 94.154 Mbps | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#merged-main-ether-transport) |
| RX72N Envision Kit | Ethernet | TLS（software） | 4.189 Mbps | 4.434 Mbps | 同上 |
| RX72N Envision Kit | Ethernet | TLS（TSIP hardware） | 43.113 Mbps | 54.448 Mbps | 同上 |
| EK-RX671 | Murata Type 1YN Wi-Fi | TCP | 平均42.5 Mbps | 平均46.2 Mbps | [`RX671@e247d8fe`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/readme/-/blob/e247d8fe81e89731062cbf321e5fd12668f397ae/README.md#単一セッション正式性能) |
| EK-RX671 | Murata Type 1YN Wi-Fi | TLS（software） | 2.250 Mbps | 2.110 Mbps | 同上 |
| EK-RX671 | Murata Type 1YN Wi-Fi | TLS（TSIP hardware） | 38.633 Mbps | 33.428 Mbps | 同上 |
| CK-RX65N V1 | BG96 Cellular | TCP | 0.124 Mbps | 0.144 Mbps | [`RX65N@1b9ea826`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-bench/-/blob/1b9ea82608efcd4bffcfb2991d4f507faea200fe/README.md#最新性能) |
| CK-RX65N V1 | BG96 Cellular | TLS（software） | 未測定 | 未測定 | 同上 |
| CK-RX65N V1 | BG96 Cellular | TLS（TSIP hardware） | 未測定 | 未測定 | 同上 |

接続媒体、payload、対向、統計方法が異なるため、媒体間の直接比較には使えません。
RX65N/BG96のTLS throughputとCPU負荷率は未測定で、TCP値から推定していません。

### OTA

AWS IoT MQTT OTA / software TLS 1.2の単発実測です。時間はダウンロード開始を起点とし、転送・flash書込みを含みます。

| ターゲット | 接続 | payload | ダウンロード | 更新確定まで | 固定測定 |
|---|---|---:|---:|---:|---|
| RX72N Envision Kit | Ethernet | 1,834,496 B | 23.68秒 | 75.11秒 | [job #70280](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70280) |
| EK-RX671 | Murata Type 1YN Wi-Fi | 785,920 B | 20.45秒 | 53.12秒 | [job #62156](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/62156) |
| CK-RX65N V1 | BG96 Cellular | 785,920 B | 143.51秒 | 204.96秒 | [job #70279](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70279) |

測定区間・SHA・条件は[OTA性能](docs/ota-performance.md)を参照してください。TSIP構成の時間は未測定です。

## 現在の検証状態

最終更新: 2026-09-01 JST。

| 項目 | 状態 |
|---|---|
| AWS IoT MQTT / OTA / Fleet Provisioning | 3ターゲット × software / TSIP × TLS 1.2 / 1.3を実機確認済み |
| TLS 1.3 resumption / 0-RTT | LANBENCH対向で全6環境を5回連続確認済み |
| release tag pipeline | [`#11140`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140) が35/35 job success |

個別セルは[検証結果](docs/validation-evidence.md)を参照してください。AWS IoT Coreは
SessionTicketを発行しないため、resumption / 0-RTTはLANBENCHで確認しています。

## IoT Device Tester（IDT）

IDTの明示CI入口は3ターゲットに対応します。`RUN_RX_IDT=true`、`IDT_TARGET`、`IDT_SCOPE`で選択します。
通常push / MRではnative IDTを起動しません。MRでは単体検査、3ターゲットの実行計画、15構成のソース選択を確認します。

| 環境 | `IDT_TARGET` | native CI job | 実機IDTの証跡 |
|---|---|---|---|
| RX72N Envision Kit / Ethernet | `rx72n-ethernet` | `test_rx72n_idt` | 以下の限定試験 |
| CK-RX65N V1 / BG96 | `rx65n-bg96` | `test_rx65n_bg96_idt` | [限定試験実施済み（NG・残件あり）](docs/idt-validation.md#rx65nrx671の実測) |
| EK-RX671 / Type 1YN Wi-Fi | `rx671-wifi` | `test_rx671_wifi_idt` | [Transport一部実施（未完走）](docs/idt-validation.md#rx65nrx671の実測) |

`IDT_SCOPE=plan`は機器・AWSを操作しない計画確認です。`preflight`はnativeの版照合で、現行LTSとの不一致はNGとして記録します。
実機scopeの準備条件と終了状態は[IDT検証](docs/idt-validation.md)を参照してください。
追加2環境は各試験に記載したSHAでの部分試験であり、全IDT合格には扱いません。
3環境のファイル構成・依存参照・版数の差と改定順は[共通基盤監査](docs/common-core-audit/README.md)を参照してください。
旧`RUN_RX72N_IDT` / `RX72N_IDT_SCOPE`によるRX72N選択も保持します。

以下の実測環境: **RX72N Envision Kit / Ethernet / software TLS**、ishiguro-pc（Windows x86_64でビルド、
Ubuntu WSL 2 / x86_64でIDT実行）、RPi #1（書込み・UART中継）、AWS東京リージョン。
IDT **4.9.0 / FRQ_2.5.0**での結果（2026-09-28まで）です。

| 主要項目 | 結果 |
|---|---|
| FreeRTOS版照合 | FAIL（202604.00-LTS未対応） |
| TLS transport | 14/14 PASS |
| MQTT | 6 FAIL（IDT: MQTT 3.1.1 / 実装: MQTT 5） |
| PKCS #11 | 基本API 10 PASS、ECC object / signは未実行 |
| OTA PAL | 14 assertions PASS、対象外1件のIGNOREをIDTがFAILと判定 |
| OTA MQTT E2E | 新版更新・同版・信頼されない証明書の3ケースPASS、全13ケースは未完了 |
| 全IDT | **未合格**（異なるSHA・試作を含む部分試験） |

実行方法、運用・リリース要件、各結果の証跡は[IDT検証](docs/idt-validation.md)を参照してください。

## 最短の開始方法

```bash
git clone --recursive https://github.com/HirokiIshiguro/iot-reference-rx.git
```

[Getting Started Guide](Getting_Started_Guide.md)と対象Project READMEから開始してください。
認証情報はリポジトリへ保存しません。

## 詳細資料

[CI/CD運用](docs/ci-pipeline.md) / [検証証跡](docs/validation-evidence.md) /
[TSIP構成](docs/tsip-integration-plan.md) / [変更履歴](Changelog.md) /
[ハードウェア・ツール現行値](https://gitlab.saffti.jp/oss/infra/hardware-config)

## ライセンス

本体は[MIT License](LICENSE)です。依存ライブラリには各ソース記載のライセンスが適用されます。

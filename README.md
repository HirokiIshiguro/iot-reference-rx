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

## 代表通信性能（TCP）

`SINK`はMCUから対向への送信、`SOURCE`は対向からMCUへの受信です。

| ターゲット | 接続 | SINK | SOURCE | 固定測定 |
|---|---|---:|---:|---|
| RX72N Envision Kit | Ethernet | 84.373 Mbps | 94.154 Mbps | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#merged-main-ether-transport) |
| EK-RX671 | Murata Type 1YN Wi-Fi | 平均42.5 Mbps | 平均46.2 Mbps | [`RX671@e247d8fe`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/readme/-/blob/e247d8fe81e89731062cbf321e5fd12668f397ae/README.md#単一セッション正式性能) |
| CK-RX65N V1 | BG96 Cellular | 0.124 Mbps | 0.144 Mbps | [`RX65N@1b9ea826`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-bench/-/blob/1b9ea82608efcd4bffcfb2991d4f507faea200fe/README.md#最新性能) |

接続媒体、payload、対向、統計方法が異なるため、媒体間の直接比較には使えません。
RX65N/BG96のTLS throughputとCPU負荷率は未測定で、TCP値から推定していません。

## 現在の検証状態

最終更新: 2026-09-01 JST。

| 項目 | 状態 |
|---|---|
| AWS IoT MQTT / OTA / Fleet Provisioning | 3ターゲット × software / TSIP × TLS 1.2 / 1.3を実機確認済み |
| TLS 1.3 resumption / 0-RTT | LANBENCH対向で全6環境を5回連続確認済み |
| release tag pipeline | [`#11140`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140) が35/35 job success |

個別セルは[検証結果](docs/validation-evidence.md)を参照してください。AWS IoT Coreは
SessionTicketを発行しないため、resumption / 0-RTTはLANBENCHで確認しています。

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

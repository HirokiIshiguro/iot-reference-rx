# FreeRTOS LTS IoT Reference for Renesas RX

[Renesas公式版](https://github.com/renesas/iot-reference-rx)を、RX72N、RX65N、RX671へ
展開したFreeRTOS / AWS IoT実機検証用フォークです。MQTT、OTA、Fleet Provisioning、
TSIP（ハードウェア暗号）をGitLab CIで検証します。

ベースはFreeRTOS `202604.00-LTS-rx`、最新リリースは
[`v202604.00-LTS-rx-1.0.0-saffti-1.4.0`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.4.0)です。

## 対応ターゲット

| ターゲット | 接続 | 主なプロジェクト |
|---|---|---|
| RX72N Envision Kit | Ethernet | [software](Projects/aws_ether_rx72n_envision_kit/) / [TSIP](Projects/aws_ether_rx72n_envision_kit_tsip/) |
| CK-RX65N V1 | BG96 Cellular | [software](Projects/aws_bg96_ck_rx65n/) / [TSIP](Projects/aws_bg96_ck_rx65n_tsip/) |
| EK-RX671 | Murata Type 1YN Wi-Fi | [application](Projects/aws_wifi_rx671_ek/) / [boot loader](Projects/boot_loader_rx671_ek/) |

## 現在の検証状態

最終更新: 2026-09-01 JST。

| 項目 | 状態 |
|---|---|
| AWS IoT MQTT / OTA / Fleet | 3ターゲット × software / TSIP × TLS 1.2 / 1.3を実機確認済み |
| TLS 1.3 resumption / 0-RTT | LANBENCH対向で全6環境を5回連続確認済み |
| RX671 AWS IoT full matrix | 固定SHAで5回連続strict PASS、各Run 48/48 child・253/253 job・cleanup 42/42・AWS/S3残留0 |
| release tag pipeline | [`#11140`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140) が35/35 job success |
| Nightly Schedule #5 | **Inactive**。再開は人間承認が必要 |

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

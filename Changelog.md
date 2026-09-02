# Changelog

safftiリリースで利用者から見える変更を、新しい順にまとめます。
最初のsafftiタグは対応するRenesas公式タグとの差分、それ以降は直前のsafftiタグとの差分です。
個別pipelineの一覧は[実機検証マトリクス](docs/validation-evidence.md)へ集約します。

## リリース一覧

| Tag | 主な内容 |
|---|---|
| [v202604.00-LTS-rx-1.0.0-saffti-1.4.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.4.0) | EK-RX671 + Type 1YN、横断性能、fixed-SHA AWS IoT 5-run |
| [v202604.00-LTS-rx-1.0.0-saffti-1.3.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.3.0) | TLS 1.3 session resumption / 0-RTTとnightly matrix |
| [v202604.00-LTS-rx-1.0.0-saffti-1.2.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.2.0) | TSIP + TLS 1.3 MQTT / OTA / Fleet Provisioning |
| [v202604.00-LTS-rx-1.0.0-saffti-1.1.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.1.0) | TSIP基盤、TLS 1.3、実機focused matrix |
| [v202604.00-LTS-rx-1.0.0-saffti-1.0.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.0.0) | FreeRTOS 202604.00 LTS-rxとBG96リファレンス |
| `v202406.01-LTS-rx-1.1.1-saffti-1.0.0` | 最初のsafftiタグ、RX72N実機CIリファレンス |

## 未リリース

### 文書

- root READMEを1分で概況把握できる構成へ再編し、Changelog、対応ターゲット、検証状態、
  固定SHAの代表通信性能へ直接移動できるようにしました。
- 代表通信性能はRX72N Ethernet、RX671 Wi-Fi、RX65N/BG96 Cellularについて、
  TCP、software TLS、TSIP hardware TLSのSINK / SOURCEを同じ形式で示します。
- `Getting_Started_Guide.md`を日本語化し、GitLabが生成する日本語見出しanchorへ
  同一repository内の参照を追従させました。
- CI運用と個別の実機証跡を、それぞれ`docs/ci-pipeline.md`と
  `docs/validation-evidence.md`へ分離しました。

### 今後の課題

- RX Ethernet TXのbusy pollをTX complete IRQ待機へ変更し、有限timeoutと
  EDMAC異常時の復帰を実機確認します。
- SDIO / WHD / FreeRTOS+TCP境界の待ち時間を追加分析します。
- RX72N経由でセカンダリMCUを更新するOTAリファレンスを追加します。

## v202604.00-LTS-rx-1.0.0-saffti-1.4.0

### 追加

- EK-RX671 + Murata Type 1YN Wi-Fiを、software / TSIPのAWS IoTリファレンスとして
  統合しました。WHD / SDIO、FreeRTOS+TCP、MQTT、OTA、Fleet Provisioning、
  boot loader、実機CIを含みます。
- TSIP network transportへ、接続単位でMaximum Fragment Length拡張を制御する
  `disableMaxFragmentLengthExtension`を追加しました。

### 改善

- RX Ethernet送信へ複数descriptorを使うTX pipelineと診断counterを追加しました。
  RX72Nの代表測定は固定SHAの[benchmark README](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md)に集約しています。
- RX671でTracealyzer / J-Link RTTによるpayload区間のCPU負荷測定と、
  software / TSIPの性能比較を再現できるようにしました。

### 検証

- RX671 software / TSIPのMQTT、OTA、Fleet ProvisioningをTLS 1.2 / 1.3で含む
  fixed-SHA full matrixが5回連続strict PASSしました。
- 各Runで48/48 child、253/253 job、cleanup 42/42、AWS IoT / S3一時資源残留0、
  base資源保全、全host safe idleを確認しました。詳細は
  [Issue #140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/140)を参照してください。
- release tag pipeline [#11140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140)は35/35 job successです。

## v202604.00-LTS-rx-1.0.0-saffti-1.3.0

### 追加・検証

- RX72N/EtherとRX65N/BG96のsoftware / TSIP 4環境で、SessionTicket対応LANBENCH対向の
  TLS 1.3 session resumptionと96-byte 0-RTT early dataを実機確認しました。
- 各環境は同一構成で5回確認済みです。代表実装はMR
  [!121](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/121)、
  [!122](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/122)、
  [!123](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/123)を参照してください。
- AWS IoT CoreはSessionTicketを発行しないため、AWS接続はTLS 1.3 full handshake、
  resumption / 0-RTTはLANBENCHで役割を分けています。

### 運用

- 重い回帰試験をnightly parentからfocused childへ展開し、board別resource groupと
  cross-project lockで実機シーケンスを直列化しました。

## v202604.00-LTS-rx-1.0.0-saffti-1.2.0

### 追加・改善

- RX72N/EtherとRX65N/BG96で、TSIP backend + TLS 1.3のMQTT、OTA、
  Fleet Provisioningを実機CIへ追加しました。
- OTAは更新前後、Fleet Provisioningはclaim / provisionedの両接続で、
  指定TLS versionをCIが確認します。
- TSIP key indexではないFleet生成鍵をsoftware DRBG / PKCS #11 fallbackで
  扱えるようにし、TSIP秘密鍵との責務を分離しました。

### 検証

- software / TSIP 4環境 × MQTT / OTA / Fleet Provisioning × TLS 1.2 / 1.3の
  24セルを5回確認しました。代表結果は
  [MQTT #6049](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6049)、
  [OTA #6063](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6063)、
  [Fleet #6076](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6076)です。
- このタグ時点ではTLS 1.3 session resumption / 0-RTTは未収録です。

## v202604.00-LTS-rx-1.0.0-saffti-1.1.0

### 追加

- RX72NとRX65N/BG96へTSIP application、UART `tsipprov`、runtime provisioning
  payloadを使うTLS backendを追加しました。
- 両ターゲットのsoftware TLSでAWS IoT TLS 1.3 MQTT / OTA / Fleet Provisioningを
  実機確認できるようにしました。
- 1本のnightly parentからfocused childを起動する実機matrixへ移行しました。

### 改善・修正

- BG96のPWRKEY / RESET_N、QIRD受信、OTA / Fleetの待ち時間を調整しました。
- boot loaderからapplicationへ渡す前のPLL状態を整理し、BSP初期化を安定化しました。
- RX72N TSIP transport headerの選択順、OTA欠落block復旧、Fleet生成鍵の保存、
  PKCS #11 RSA署名fallbackを修正しました。

### タグ時点の状態

- RX72N/EtherとRX65N/BG96のsoftware / TSIPでMQTT、OTA、Fleet Provisioningを確認済みです。
- software TLS 1.3は確認済み、TSIP + TLS 1.3は次タグで完了しました。

## v202604.00-LTS-rx-1.0.0-saffti-1.0.0

### 変更・追加

- 保守ベースをFreeRTOS 202604.00-LTS-rxへ更新しました。
- CK-RX65N V1 + Quectel BG96のapplication、dual-bank boot loader、credential provisioning、
  MQTT、OTA、Fleet Provisioningを標準セルラーリファレンスとして追加しました。
- RX72N EthernetとRX65N/BG96を同一repositoryのGitLab実機CIで検証できるようにしました。

### 改善

- BG96 OTAのresetをまたぐ観測とimage acceptance判定を安定化しました。
- RX72N / RX65Nのflash、provision、test、cleanupをboard別に直列化しました。

## v202406.01-LTS-rx-1.1.1-saffti-1.0.0

### 最初のsafftiリリース

- Renesas公式`v202406.01-LTS-rx-1.1.1`を基に、RX72N Envision Kit Ethernetの
  application、dual-bank boot loader、Smart Configurator出力を追加しました。
- headless build、RFP flash、credential provisioning、MQTT、OTA、Fleet Provisioningを
  RX72N実機Runnerから実行できるようにしました。
- RX72N 2 MiB dual-bank OTAの転送とflash処理を調整し、約26秒級を確認しました。
- UART観測、provisioning retry、OTA Job観測、memory配置、Runner選択の初期問題を修正しました。

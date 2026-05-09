# Changelog

このファイルは、saffti名義のリリースタグで利用者から見える変更点をまとめます。
最初のsafftiタグは、対応するルネサス公式タグからの差分です。
それ以降のsafftiタグは、直前のsafftiタグからの差分です。

## Coming Soon

### 予定

- TSIP連携のFleet Provisioningはジョブ経路を用意済みですが、
  `RX72N_TSIP_FLEET_ENABLE=false`、`RX65N_BG96_TSIP_FLEET_ENABLE=false` を
  既定としているため、まだ標準の定期検証には含めていません。
  RX72NとRX65N/BG96を別々のfocused pipelineで確認してから、scheduleへ昇格する予定です。

- TSIP + TLS 1.3の同時有効化は、TSIP TLS 1.2経路とsoftware TLS 1.3経路を
  別々に安定化した後に扱います。

## v202604.00-LTS-rx-1.0.0-saffti-1.1.0

### 追加

- RX72N Envision Kit EthernetとCK-RX65N + BG96 Cellularに、TSIP連携TLS backendを
  選択して実機CIへ流すための基盤を追加しています。
  TSIP用アプリケーションプロジェクト、UART経由の`tsipprov` provisioning、
  masked CI/CD Variablesまたは初期セットアップ時のローカル入力からの
  runtime provisioning payload投入に対応しました。
  RX72N TSIP OTA/MQTTはpipeline
  [#4718](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4718)、
  RX65N/BG96 TSIP OTA/MQTTはpipeline
  [#4791](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4791)で
  実機完走を確認しています。

- RX72N Envision Kit Ethernetで、AWS IoT CoreへのTLS 1.3 MQTT接続に対応しました。
  実機スコープパイプラインでは、RX72N実機ログに
  `TLS handshake successful: version TLSv1.3` が出ることを確認しています。
  通常のMRパイプラインでは既定エンドポイントによるTLS 1.2経路も継続確認しています。

- CK-RX65N + BG96 Cellularでも、AWS IoT CoreへのTLS 1.3 MQTT接続に対応しました。
  この構成ではTLS層はRX65N上のmbedTLSで処理し、TCP接続管理はソケットラッパー経由で
  BG96内部TCP/IPにATコマンドで委託します。
  実機スコープパイプラインでは、BG96経由のMQTTログに
  `TLS handshake successful: version TLSv1.3` と
  `[PASS] Required TLS version: TLSv1.3` が出ることを確認しています。
  TLS 1.3のRSA-PSS CertificateVerifyに必要なRSA秘密鍵処理は、BG96プロジェクト内蔵の
  mbedTLS/PKCS #11連携にも反映しました。

### 改善

- CK-RX65N + BG96のOTA性能チューニングを進めています。
  ロジアナ波形観測で見えたセルラー特有の待ち時間をもとに、MQTT受信待ち時間と
  OTAブロックサイズを調整し、実機CIで安定して再現できる保守的な設定に寄せました。

### 実機フルテスト結果

このタグ候補では、重い直積テストを通常MR pipelineへ載せず、schedule / focused pipelineの
組み合わせで確認しています。2026-05-09時点の直近結果は **4/4 pipelines success、
61/61 jobs success** です。

| Scope | Pipeline | Tested commit | Result | Jobs |
|-------|----------|---------------|--------|------|
| Full software TLS regression (RX72N/Ether + RX65N/BG96 MQTT/OTA/Fleet) | [#4709](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4709) | `91f2d6b5` | success | 33/33 |
| Focused RX72N TSIP OTA/MQTT | [#4718](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4718) | `91f2d6b5` | success | 9/9 |
| Focused RX72N software TLS 1.3 MQTT | [#4717](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4717) | `91f2d6b5` | success | 5/5 |
| Focused RX65N/BG96 TSIP OTA/MQTT | [#4791](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4791) | `f06e977f` | success | 14/14 |

### 注記

- TSIP OTA/MQTTのscopeは、OTA実行前にMQTT接続確認とcredential provisioningを通過するため
  OTA/MQTTとして記載しています。
- RX72N software TLS 1.3は、現在の定期結果ではMQTT接続確認までです。
  既存OTAジョブをTLS 1.3必須条件で実行できるよう、Issue #43でOTAログ側のTLS version判定を
  追加しています。
- TSIP Fleet Provisioningはこのタグ候補の標準検証範囲外です。

## v202604.00-LTS-rx-1.0.0-saffti-1.0.0

### 変更

- safftiの保守ベースをFreeRTOS 202406.01-LTS-rxから
  FreeRTOS 202604.00-LTS-rxへ更新しました。

- RX65N BG96のフリートプロビジョニング試験をOTA後のクリーンアップ後に直列化し、
  長時間のセルラーテスト同士が同じ実機状態を奪い合わないようにしました。

- FreeRTOS LTS更新にあわせ、RXリファレンスで必要な互換差分を整理しました。
  coreMQTT-AgentやAWS IoT Jobsの差分を、RX72N/RX65Nの実機リファレンスで動作する形に
  調整しています。

### 追加

- CK-RX65N V1 + Quectel BG96を、safftiの標準セルラーリファレンスとして追加しました。
  アプリケーションプロジェクト、デュアルバンクブートローダ、BG96向け認証情報プロビジョニング、
  AWS IoT OTA連携を含みます。

- GitLab実機パイプラインを拡張し、RX72N EthernetとRX65N BG96 Cellularを
  同じリポジトリで検証できるようにしました。
  セルラー経路は、ビルド、フラッシュ、アプリ起動、プロビジョニング、MQTT、OTA、
  フリートプロビジョニングまでを対象にしています。

### 改善

- BG96 OTAの観測処理を、リセットをまたぐケースに強くしました。
  OTA後の新イメージ受理状態を成功として扱えるようにし、最終アクティベーション中の
  再起動で誤判定しにくくしています。

### 注記

- このタグでは、高速なEthernet OTAリファレンスと、低速だが実運用に近い
  Cellular OTAリファレンスを、どちらも実機CIで維持できることを確認しました。

## v202406.01-LTS-rx-1.1.1-saffti-1.0.0

### 注記

- 最初のsafftiリリースタグです。
  この項目は、ルネサス公式 `v202406.01-LTS-rx-1.1.1` からの差分を説明します。

- このリリースでは、上流のRenesas RX LTSツリーを、単にビルドできるソースではなく、
  RX72N Ethernet実機をフラッシュ、プロビジョニング、MQTT検証、OTA検証、
  フリートプロビジョニング検証までパイプラインで回せるリファレンスへ育てました。

### 追加

- RX72N Envision Kit Ethernetを、safftiの保守対象リファレンスとして追加しました。
  アプリケーションプロジェクト、デュアルバンクブートローダ連携、ボード固有の
  Smart Configurator出力、実機bring-up記録を含みます。

- RX72N Envision Kit向けの実機GitLab CIジョブを追加しました。
  headless e2 studioビルド、RFPフラッシュ、プロビジョニング、MQTT publish/subscribe、
  OTA、フリートプロビジョニングをパイプラインから実行できます。

- AWS IoTセットアップとテスト用ツールを追加し、RX72N実機を手作業ではなく
  CIからプロビジョニング、検証できるようにしました。

### 改善

- RX72N Ethernet OTAの性能をチューニングしました。
  MQTTブロック転送とフラッシュ書き込み中の受信継続を調整し、RX72N Envision Kit実機で
  2 MBデュアルバンクOTAが約26秒級まで到達することを確認しました。

### 変更

- RXブートローダを再利用しやすいサブモジュール指向の構成へ整理し、
  RX72Nアプリケーションとブートローダの契約を明確化しました。

- リポジトリ運用メモ、MRテンプレート、実機ランナー情報を追加しました。
  Codex/Claude支援で保守するときに、ボード識別、UART、runner割り当てを毎回
  再調査しなくて済むようにしています。

### 修正

- RX72N初期bring-upで見つかった、UART観測、プロビジョニングretry、OTAジョブ観測、
  LCD/framebuffer配置、CI実機runner選択まわりの問題を修正しました。

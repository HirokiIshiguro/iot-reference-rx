# Changelog

このファイルは、saffti名義のリリースタグで利用者から見える変更点をまとめます。
最初のsafftiタグは、対応するルネサス公式タグからの差分です。
それ以降のsafftiタグは、直前のsafftiタグからの差分です。

## Coming Soon

### 追加

- RX72N Envision Kit EthernetとCK-RX65N + BG96 Cellularに、TSIP連携TLS backendを
  選択して実機CIへ流すための基盤を追加しています。
  TSIP用アプリケーションプロジェクト、UART経由の`tsipprov` provisioning、
  公開可能なRoot CA素材を固定する`tsip_provisioning_data` submodule、
  masked CI/CD Variablesからのwrapped key blob投入に対応しました。

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

### 予定

- 次のsafftiタグでは、202604ベース以降のBG96 OTA性能チューニング、RX72N TLS 1.3対応、
  RX65N BG96 TLS 1.3対応、TSIP連携TLS backend、実機CI運用の改善をまとめる予定です。

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

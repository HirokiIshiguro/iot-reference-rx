# Changelog

このファイルは、saffti名義のリリースタグで利用者から見える変更点をまとめます。
最初のsafftiタグは、対応するルネサス公式タグからの差分です。
それ以降のsafftiタグは、直前のsafftiタグからの差分です。

## Coming Soon

### 予定

- TSIP backend と TLS 1.3 の組み合わせで、RX72N Envision Kit Ethernet と
  CK-RX65N + BG96 Cellular の MQTT 接続、OTA、Fleet Provisioning を実機CIで検証できるようにしました。
  `tsip_tls13` / `tsip_mbedtls13` 実験で確認した結果をもとに、
  現在の TSIP 連携ベースである Mbed TLS 3.2.1 系では
  TLS 1.3 full handshake と MQTT/TLS 接続、OTA、Fleet Provisioning の安定動作を固めています。
  OTAでは、更新前のダウンロード経路だけでなく、更新後アプリの再接続でも
  TLSv1.3 が観測されることをCIで要求するようにしました。
  Fleet Provisioning では、claim certificate 接続と provisioned certificate 接続の両方で
  TLSv1.3 が観測されることをCIで要求するようにしました。
  この段階では TLS 1.3 の CertificateVerify に TSIP ドライバ API を使い、
  鍵スケジュール、record path、resumption、0-RTT は software path として扱います。
  次に、`iot-reference-rx` 本体で通常 TLS backend が参照している
  Mbed TLS 3.6.4 以降へ TSIP 連携を移植し、TLS 1.3 session resumption と
  0-RTT を LANBENCH や AWS IoT Core 接続で検証する計画です。

- Tracealyzer を用いた CPU 負荷率とタスク挙動の可視化を導入し、TSIP offload 時の
  性能変化を処理時間だけでなく CPU 使用率でも確認できるようにします。

- RX72N 経由でセカンダリ MCU を更新する OTA リファレンスを追加する予定です。

## v202604.00-LTS-rx-1.0.0-saffti-1.1.0

### 追加

- RX72N Envision Kit EthernetとCK-RX65N + BG96 Cellularに、TSIP連携TLS backendを
  選択して実機CIへ流すための基盤を追加しています。
  TSIP用アプリケーションプロジェクト、UART経由の`tsipprov` provisioning、
  masked CI/CD Variablesまたは初期セットアップ時のローカル入力からの
  runtime provisioning payload投入に対応しました。
  RX72N TSIP MQTT / OTA / Fleet Provisioning と、RX65N/BG96 TSIP MQTT / OTA /
  Fleet Provisioning は、READMEの最新テスト結果に示す通り5回確認済みです。

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

- 実機スケジューラを、Full regressionという大きな単位ではなく、
  READMEのFocused Test Matrixに対応する1本のnightly parent pipelineから
  focused child pipelineへ展開する形へ整理しています。
  各child pipelineはボード別に直列化し、RX72NとRX65N/BG96の並列性は保ちつつ、
  同一ボード上のflash/provision/testシーケンスが割り込まれないようにします。
  TSIP TLS 1.3系は未実装/未検証のため、README上では空欄として扱います。

### 改善

- CK-RX65N + BG96のOTA性能チューニングを進めています。
  ロジアナ波形観測で見えたセルラー特有の待ち時間をもとに、MQTT受信待ち時間と
  OTAブロックサイズを調整し、実機CIで安定して再現できる保守的な設定に寄せました。

- RX72N/RX65N共通のブートローダハンドオフ処理を整理し、ブートローダから
  アプリケーションへジャンプする直前にPLL系クロックをリセット直後に近い状態へ
  戻すことで、アプリ側BSPのクロック初期化を安定化しました。

- CK-RX65N + BG96の初期化と受信経路を見直し、BG96のPWRKEY/RESET_N制御、
  QIRD受信、OTA/Fleetをまたぐ実機CIの安定性を改善しました。

- READMEの実機検証結果を、MCU環境、TLS backend、機能のマトリクスとして整理しました。
  `✓` のセルは5回テストOKを確認した証跡へ直接リンクしています。

### 修正

- RX72N TSIPアプリで、TSIP transport実装をリンクしているにもかかわらず
  非TSIP transportヘッダが先に選択され、`TlsTransportParams_t` のABIがずれる問題を
  修正しました。この不一致により、TLS handshake成功後にMQTTの
  `pNetworkContext` が壊れる可能性がありました。

- OTAの欠落ブロック復旧後に次のブロック要求を再開できないケースを補正しました。

- Fleet Provisioningで生成したEC秘密鍵をPKCS #11 PAL経由で保存する経路を整理し、
  TSIP backendでもFleet Provisioningが動作するようにしました。

- mbedTLS 3.6系のPKコールバックABIに合わせ、PKCS #11経由のRSA署名と
  software fallbackの接続を修正しました。

### 検証

- RX72N/Ether software / TSIP、RX65N/BG96 software / TSIP の各環境で、
  MQTT、OTA、Fleet Provisioningを実機CIで確認しました。

- software TLS backendでは、RX72N/EtherとRX65N/BG96の両方で
  TLS 1.3 MQTT、TLS 1.3 OTA、TLS 1.3 Fleet Provisioningを確認しました。

- TSIP + TLS 1.3の6セルは意図的に未検証として残しています。

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

# Changelog

このファイルは、saffti名義のリリースタグで利用者から見える変更点をまとめます。
最初のsafftiタグは、対応するルネサス公式タグからの差分です。
それ以降のsafftiタグは、直前のsafftiタグからの差分です。

## リリース一覧 / Release Overview

| Tag | 主な内容 |
|---|---|
| [v202604.00-LTS-rx-1.0.0-saffti-1.3.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.3.0) | LANBENCH TLS 1.3 session resumption / 0-RTT の4経路5回成功と夜間 matrix 整備 |
| [v202604.00-LTS-rx-1.0.0-saffti-1.2.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.2.0) | TSIP backend + TLS 1.3 の MQTT / OTA / Fleet Provisioning 実機CI確認 |
| [v202604.00-LTS-rx-1.0.0-saffti-1.1.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.1.0) | RX72N/RX65N の OTA・Fleet Provisioning 実機CI整備 |
| [v202604.00-LTS-rx-1.0.0-saffti-1.0.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.0.0) | FreeRTOS 202604.00 LTS-rx ベースの初回 saffti タグ |

## 予定

以降は今後のリリース候補です。

### RX Ethernet TX pipeline

- RX向けFreeRTOS+TCP `NetworkInterface.c`に、複数EMAC TX descriptorを使う送信pipelineを追加します。
  `RX_NETWORK_INTERFACE_TX_PIPELINE_ENABLE=1`では、各frame後の`R_ETHER_CheckWrite()`によるring全体の
  完了待ちを省略し、次descriptorが`ETHER_ERR_TACT`のときだけ待ちます。既定値は従来互換の`0`です。
- RX72N Envision Kitの10MiB TCP SINK実機比較では、descriptorを1から4へ増やすだけでは
  47.745Mbpsから変化せず、descriptor 4とpipelineを組み合わせて84.744Mbpsへ改善しました
  （5回中央値、+77.5%、EMAC error 0）。測定条件と全A/B結果は
  [tsip_mbedtls benchmark job #51762](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls/-/jobs/51762)
  を参照してください。
- `RX_NETWORK_INTERFACE_TX_STATS_ENABLE=1`ではdescriptor wait、busy poll、frame、error、
  TX complete IRQの診断counterを有効にできます。通常製品buildへの実行コストを避けるため既定値は`0`です。
- 現在のpipeline待ちはbusy pollなので、RX72Nの測定CPU busy中央値は100%のままです。
  TX complete IRQでtaskを停止する方式は、throughputを維持できるかを実機確認する次段候補として残します。
  EDMAC異常でdescriptor所有権が戻らない場合の有限timeoutも未実装で、従来の
  `R_ETHER_CheckWrite()`と同じ無期限待ち特性を持つため、IRQ待ち化と合わせてfail-safeを検討します。
- 複数descriptor pipelineの連続受信試験で、通常のIPv4 ID系列から外れた旧header断片を含むRSTが
  送出される事象を確認しました。外部SDRAMへのcopy完了をvolatile readbackで確認してからEDMACへ
  所有権を渡し、descriptor数ごとにring全体をdrainしてから再利用する安全化を追加します。
  4 descriptorのbatch内ではframe送信と次frame準備のoverlapを維持します。

### EK-RX671 + Murata Type 1YN Wi-Fi

- `Projects/aws_wifi_rx671_ek/e2studio_ccrx` を EK-RX671 + Type 1YN の AWS Wi-Fi 基準プロジェクトとして整備中です。
- 現在はヘッドレスビルド、COM5/SCI6ログ、WHD経由のAP JOIN、FreeRTOS+TCP、AWS IoT MQTT smoke まで確認済みです。
- SDIO CMD53のDTC転送を安定版として採用し、DMACAは次回以降の比較候補として残しています。
- Wi-Fi認証情報、AWS IoT認証情報、TCPスループット試験設定はgit管理外のローカルヘッダで注入します。
- SDCLK 48MHz実験は規格内で動作しましたが、ICLK低下の影響もあり効果が小さいため、現時点の基準は `ICLK=120MHz / PCLKB=60MHz / SDCLK=30MHz` に戻します。
- Percepio公式TraceRecorderSourceをサブモジュール化し、J-Link RTT経由のTracealyzer CLI取得を確認済みです。
- SDHI IRQ本格実装の差分観測用として、`WHD_SDIO_USE_SDHI_IRQ=0`、`WHD_SDIO_SOFTIRQ_POLL_MS=1` のsoftirq-only基準を固定します。
- 最終目標はSDHI IRQ全面ONの割り込み駆動実装です。softirq-onlyは安定動作と性能差分を測る比較用基準として扱います。
- 最終的な速度チューニングは、TLS、OTA、TSIPによるTLS加速が安定した後に、SDHIクロック、DTC/DMAC、FreeRTOS+TCPバッファ、WHD結合部をまとめて再評価します。

#### 現在の通信速度

10MiBの平文TCPスモーク試験で確認した代表値です。`RX671 -> Host` はRX671からLANBENCHホストへの送信、`Host -> RX671` はLANBENCHホストからRX671への受信を示します。現在の再現用基準は、mbedTLS benchmarkと同じRPi#2上の共通Go LANBENCHを使い、SOURCE側はRX671でペイロード検証を行わない条件に揃えます。

| 条件 | ホスト | SDCLK | CMD53転送 | 主なTCP/バッファ条件 | RX671 -> Host | Host -> RX671 | 状態 |
|---|---|---:|---|---|---:|---:|---|
| 低速基準 | PC | 7.5MHz | CPU copy | 初期比較用 | 14.48Mbps | 15.03Mbps | 参考 |
| DTC低速 | PC | 7.5MHz | DTC、512byte閾値 | 小転送のCPU fallbackが多い | 14.40Mbps | 14.11Mbps | 参考 |
| DTC低速改善 | PC | 7.5MHz | DTC、64byte閾値 | Type 1YN Function 2 block sizeに合わせる | 14.47Mbps | 15.43Mbps | 参考 |
| PC対向最速値 | PC | 30MHz | DTC、64byte閾値 | TX 14600byte / RX 5840byte、socket 64KiB、44-MSS window | 38.2-38.5Mbps | 30.2-32.0Mbps | 参考、RPi基準とは混在しない |
| 48MHz実験 | PC | 48MHz | DTC、64byte閾値 | `PLL=192MHz`、`ICLK=96MHz`、同じTCP条件 | 39.6-39.9Mbps | 31.8-32.3Mbps | 効果限定、未採用 |
| RPi#2統一基準 | RPi#2 / 共通Go LANBENCH | 30MHz | DTC、64byte閾値 | TX 14600byte / RX 5840byte、socket 64KiB、44-MSS window、SOURCE verifyなし | 32.476Mbps | 19.288Mbps | 採用中、mbedTLS benchmarkと同条件 |
| softirq-only比較基準 | PC | 30MHz | DTC、64byte閾値 | `WHD_SDIO_USE_SDHI_IRQ=0`、softirq 1ms、スニファなし | 未測定 | 31.524Mbps | SDHI IRQ実装前の差分観測用 |
| softirq-only + スニファ | PC | 30MHz | DTC、64byte閾値 | `WHD_SDIO_USE_SDHI_IRQ=0`、softirq 1ms、スニファあり | 未測定 | 31.149Mbps | 波形観測ありの差分観測用 |

### 共通の今後作業

- TracealyzerでCPU負荷率、タスク挙動、SDIO/WHD/FreeRTOS+TCP境界の待ち時間を可視化します。
- `aws_wifi_rx671_ek` は map の `__SEGGER_RTT` をTracealyzer CLI用のRTT block addressとして使い、`reset=true` の有界取得を標準手順にします。
- TSIP offload時の性能変化を、処理時間だけでなくCPU使用率でも確認します。
- RX72N経由でセカンダリMCUを更新するOTAリファレンスを追加します。

## v202604.00-LTS-rx-1.0.0-saffti-1.3.0

### 追加

- Mbed TLS 3.6.4 の software TLS 1.3 path では、SessionTicket を発行できる
  LANBENCH 対向で TLS 1.3 session resumption と 0-RTT early data 受理まで確認しました。
  実績は [tsip_mbedtls13 MR !4](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/merge_requests/4)
  および [pipeline #6135](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6135)
  で参照できます。この成果は `iot-reference-rx` 側の RX72N/Ether TSIP backend にも横展開し、
  [MR !121](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/121) と
  [pipeline #6175](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6175)
  で TLS 1.3 session resumption と 0-RTT early data 送信まで確認しました。さらに
  RX65N/BG96 software backend へも横展開し、
  [MR !122](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/122) と
  [pipeline #6191](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6191)
  で initial TLS 1.3 接続、NewSessionTicket 受信、session ticket 保存、96 bytes の
  0-RTT early data 送信、resumed TLS 1.3 接続、PASS まで確認しました。
  RX65N/BG96 TSIP backend へも横展開し、
  [MR !123](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/123) と
  [pipeline #6204](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6204)
  で同じ LANBENCH TLS 1.3 resumption / 0-RTT smoke の PASS まで確認しています。
  RX72N/Ether TSIP backend については、main merge commit `5aefbb4d` 上の
  `nightly_matrix` [#6355](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6355) /
  [#6388](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6388) /
  [#6406](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6406) /
  [#6424](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6424) /
  [#6442](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6442)
  で5回通過したため、README の LANBENCH 表では5回目の child pipeline
  [#6454](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6454)
  を証跡にして `✓` へ昇格しました。RX65N/BG96 software backend も同じ
  main merge commit `5aefbb4d` 上の focused/API
  [#6466](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6466) /
  [#6482](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6482) /
  [#6484](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6484) /
  [#6486](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6486) /
  [#6488](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6488)
  で5回通過し、TSIP backend も
  [#6469](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6469) /
  [#6483](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6483) /
  [#6485](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6485) /
  [#6487](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6487) /
  [#6489](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6489)
  で5回通過したため、README の RX65N/BG96 software / TSIP LANBENCH 行も `✓` へ昇格しました。
  RX72N/Ether software も benchmark project main commit `fa057a02` 上の focused/API
  [#6492](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6492) /
  [#6493](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6493) /
  [#6494](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6494) /
  [#6495](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6495) /
  [#6496](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6496)
  で5回通過したため、README の RX72N/Ether software LANBENCH 行も `✓` へ昇格しました。
  BG96経路では、セルラー網から到達できる一時的なEC2上の Mbed TLS `ssl_server2` を
  GitLab CI から起動して対向にしています。
  前リリース `v202604.00-LTS-rx-1.0.0-saffti-1.2.0` では TLS 1.3 full handshake を
  TSIP backend と組み合わせて実機CIで確認済みで、本リリースでは LANBENCH 対向の
  resumption と 0-RTT も RX72N/Ether software / TSIP と RX65N/BG96 software / TSIP で5回成功済みです。
  AWS IoT Core は
  [SessionTicket TLS extension をサポートしていない](https://docs.aws.amazon.com/iot/latest/developerguide/transport-security.html)
  ため、AWS IoT Core 接続での TLS 1.3 resumption / 0-RTT はサービス側対応待ちです。

- 夜間スケジューラは `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true` を前提に、
  README の AWS IoT Core / LANBENCH 表で `✓` とした全パタンを1日1回回す方針へ更新しました。
  RX72N/Ether software LANBENCH は `tsip_mbedtls13` benchmark project への downstream bridge で
  同じ nightly matrix 起点から実行します。

## v202604.00-LTS-rx-1.0.0-saffti-1.2.0

### 追加

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

### 改善

- TSIP backend 用 Mbed TLS submodule を
  `v3.2.1-renesas-tsip-custom-0.1.5` 相当へ進めました。
  TSIPで安全に扱うべきデバイス秘密鍵はTSIP経路を維持しつつ、Fleet Provisioningで生成される
  一時的なプロビジョニング鍵など、TSIP key indexではない鍵はsoftware DRBG / PKCS #11 fallbackで
  扱えるようにしています。

- READMEの最新テスト結果マトリクスを更新し、RX72N/Ether software、RX72N/Ether TSIP、
  RX65N/BG96 software、RX65N/BG96 TSIP の4環境について、MQTT、OTA、Fleet Provisioning、
  TLS 1.3 MQTT、TLS 1.3 OTA、TLS 1.3 Fleet Provisioning までの24セルすべてを
  `✓` に昇格しました。TLS 1.3 session resumption と 0-RTT は次段階の検証列として
  READMEに先行追加しています。

### 検証

- TSIP backend + TLS 1.3 MQTT は、main merge commit `7ed373c9` 上の
  [focused pipeline #6045](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6045) から
  [#6049](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6049) まで
  5回連続成功しています。

- TSIP backend + TLS 1.3 OTA は、commit `2e687700` 上の
  [focused pipeline #6059](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6059) から
  [#6063](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6063) まで
  5回連続成功しています。

- TSIP backend + TLS 1.3 Fleet Provisioning は、commit `d91f2271` 上の
  [focused pipeline #6072](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6072) から
  [#6076](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6076) まで
  5回連続成功しています。

### 注記

- このリリースでは、TSIP backend と TLS 1.3 の full handshake を使う実機経路を
  RX72N/Ether と RX65N/BG96 の両方で揃えました。
  TLS 1.3 session resumption と 0-RTT は次段階の検証対象です。

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

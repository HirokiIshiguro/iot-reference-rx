# MQTT（AWS IoT Core への接続）の実装仕様

[[_TOC_]]

この文書は、[機能仕様書](../architecture.md#2-機能と実装仕様書)の機能「AWS IoT Core への接続」の実装仕様書です。仕様書キーは `MQTT` で、試験は `IREF-MQTT-001`〜`IREF-MQTT-012` です（[試験仕様](../test-specification.md)）。

## 1. 決まり

| 番号 | 決まり | 対象 |
|---|---|---|
| 1 | 基板の通信路（Ethernet・Cellular・Wi-Fi）を上げ、IP で通信できる状態にする | 全基板 |
| 2 | 接続先（AWS IoT Core の endpoint）へ、要求した版（TLS 1.2 か 1.3）で TLS の handshake をする。ほかの版でつながない（[共通の決まり](../architecture.md#22-機能に共通の決まり)） | 全基板 |
| 3 | 基板の証明書と鍵で、MQTT の接続をする | 全基板 |
| 4 | topic を購読する | RX72N・RX65N |
| 5 | topic へ publish する | RX72N・RX65N・RX671 の software |
| 6 | AWS IoT から届いた publish を受け取る | RX72N |
| 7 | OTA の task が、最初の job の要求を出すまで進む | RX671 の TSIP |
| 8 | TSIP の構成では、TLS の秘密鍵を平文で基板へ送らない。TSIP 用に包んだ鍵を、基板の固定の証明書と組で送る | 全基板の TSIP |

決まり 4〜7 は基板で違います。理由は [3 節](#3-基板ごとの流れ)のとおり、RX671 の MQTT の試験に使うアプリが、PubSub の demo を持たないためです。

## 2. 共通の流れ

1. 認証情報（接続先、thing の名前、証明書、鍵）を基板に入れる。入れ方は 3 節。
2. アプリを起動する（boot loader が署名を確かめて起動する。[起動シーケンス](../architecture.md#5-起動シーケンス)）。
3. 通信路を上げる（決まり 1）。
4. MQTT agent（`CP-10`）が、TLS（`CP-06` か `CP-07`）で AWS IoT Core につなぎ、MQTT の接続をする（決まり 2・3）。
5. PubSub の demo（`CP-11`）が購読と publish をする（決まり 4・5）。OTA の demo（`CP-12`）も同じ接続で job の topic を購読する（決まり 6・7）。

## 3. 基板ごとの流れ

### 3.1 RX72N Envision Kit（Ethernet）

- アプリ: `aws_ether_rx72n_envision_kit`（software）、`aws_ether_rx72n_envision_kit_tsip`（TSIP）。`demo_config.h` で OTA の demo と、複数の TLS 接続の demo（`ENABLE_MULTI_TLS_DEMO`）が有効です。
- 認証情報: アプリの起動直後の UART の CLI（`conf set`・`conf commit`）で、thing の名前、接続先、証明書を入れる。software は秘密鍵も CLI で入れる。TSIP は秘密鍵を送らず、包んだ鍵を `tsipprov` で送る（決まり 8）。
- 通信路: FreeRTOS+TCP と `r_ether_rx`。DHCP で address を得る。
- MQTT: PubSub の demo は 2 つの task で、topic `pubsub_demo/<thing の名前>/task_<番号>` を購読し、同じ topic へ 2 秒ごとに publish する（各 task 10 回。`Demos/SimplePubSub/simple_pub_sub_task.c`）。OTA の demo が、`$aws/things/` で始まる job の topic の publish を受け取る。
- 複数の TLS 接続の demo も TLS の接続を張ります。その接続も、決まり 2 の版の決まりに従います。

### 3.2 CK-RX65N V1（BG96 の Cellular）

- アプリ: `aws_bg96_ck_rx65n`（software）、`aws_bg96_ck_rx65n_tsip`（TSIP）。OTA の demo が有効です。
- 認証情報: UART の CLI で、Cellular の APN と、接続先・thing の名前・証明書を入れる（[`tools/bg96_bootloader_integration.py`](../../tools/bg96_bootloader_integration.py)）。software は試験ごとの thing と証明書、TSIP は基板に固定の thing と証明書を使い、包んだ鍵を `tsipprov` で送る（決まり 8）。
- 通信路: `r_cellular` の BG96 対応 fork で、携帯網につなぐ（[RX65N の Cellular](cellular/rx65n-cellular.md)）。
- MQTT: PubSub の demo は RX72N と同じ。

### 3.3 EK-RX671（Type 1YN の Wi-Fi）の software

- アプリ: `aws_wifi_rx671_ek` を、MQTT の smoke のアプリとして build したもの。TLS の版ごとに build が分かれます。
- 認証情報: Wi-Fi の情報と AWS の認証情報を build に入れる。認証情報を含む image は、CI の中で暗号化して受け渡す（[CI/CD 運用](ci-pipeline.md)）。
- 通信路: SDIO で Type 1YN を起こし、WHD でアクセスポイントに join し、FreeRTOS+TCP を上げる。
- MQTT: smoke のアプリ（`src/application_code/aws_iot_mqtt_smoke.c`）が、TLS でつなぎ、MQTT の接続をして、topic `<thing の名前>/smoke` へ QoS 0 で 1 回 publish する。購読はしない。

### 3.4 EK-RX671 の TSIP

- アプリ: MQTT 専用の build を持たない。OTA 用の束（provisioner、boot loader、基準のアプリ）を使う（[OTA の実装仕様](ota.md)）。
- 認証情報: provisioner の CLI で、Wi-Fi の情報、接続先、基板に固定の thing と証明書、署名者の公開鍵を入れ、包んだ鍵を `tsipprov` で送る（決まり 8）。そのあと、基準のアプリを UART で boot loader へ送る。
- 通信路: software と同じ。
- MQTT: MQTT agent が接続し、OTA の task が最初の job の要求を出す。基準のアプリは PubSub の demo を持たないので、購読と publish はしない。

## 4. UART に出す行

試験の合否は、次の行で決めます（[試験仕様](../test-specification.md#合否の基準)）。行の文字列を変える時は、この表と試験の道具を同じ MR で直します。

| 決まり | 行の文字列 | 出す基板 | 出す所 |
|---|---|---|---|
| 1 | `IP Address:` | RX72N | network が上がった時の hook（`Common/FreeRTOS_common/network_support/onchip_rx_ether/freertos_ip_hook.c`） |
| 1 | `whd_wifi_join=00000000`、`WHD bring-up done`、`FreeRTOS+TCP network up` | RX671 | `src/whd_bringup.c`、`src/freertos_tcp_hooks.c` |
| 1 | `AWS MQTT smoke: network ready` | RX671 の software | smoke のアプリ |
| 2 | `TLS handshake successful: version <版>` | 全基板 | `transport_mbedtls_pkcs11.c`、`transport_mbedtls_pkcs11_with_tsip.c` |
| 2 | `AWS TLS version=<版>`、`AWS TLS=0` | RX671 の software | smoke のアプリ |
| 3 | `Successfully connected to MQTT broker.` | RX671 の TSIP | `Demos/mqtt_agent/mqtt_agent_task.c` |
| 3・5 | `AWS MQTT=0` | RX671 の software | smoke のアプリ（接続と publish の結果） |
| 4 | `Successfully subscribed to topic` | RX72N・RX65N | PubSub の demo |
| 5 | `Successfully sent QoS` | RX72N・RX65N | PubSub の demo |
| 5 | `---------Finish PubSub Demo Task` | RX65N | PubSub の demo の終わり |
| 6 | `Incoming PUBLISH received on topic $aws/things/` | RX72N | `Demos/common/mqtt-wrapper/mqtt_wrapper.c` |
| 7 | `Request Job Document event Received` | RX671 の TSIP | `Demos/OtaOverMqtt/OtaOverMqttDemo.c` |

## 5. 決まりと試験の対応

| 決まり | 確かめるテスト番号 | 確かめない所 |
|---|---|---|
| 1 | `IREF-MQTT-001`〜`012` | RX65N は通信路の上がった行を見ず、MQTT の行で代える |
| 2 | `IREF-MQTT-001`〜`012` | 版の指定と食い違う接続を、相手が拒む事 |
| 3 | `IREF-MQTT-001`〜`012` | RX72N・RX65N は接続の行を見ず、購読・publish の行で代える |
| 4 | `IREF-MQTT-001`〜`008` | RX65N は、購読の行か PubSub の終わりの行のどちらかでよい |
| 5 | `IREF-MQTT-001`〜`010` | publish が AWS IoT に届いた事（AWS 側は見ない） |
| 6 | `IREF-MQTT-001`〜`004` | 受け取った publish の中身 |
| 7 | `IREF-MQTT-011`・`012` | — |
| 8 | `IREF-MQTT-003`・`004`・`007`・`008`・`011`・`012` | CI の道具が平文の鍵を送らない事で守る。基板の側で平文の鍵を拒む事は見ない |

## 6. 確かめていない事

- RX671 は、購読をしません。[要求](../architecture.md#1-要求の一覧) `REQ-04`（3 基板が購読し publish する）のうち、RX671 の購読と、RX671 の TSIP の publish は、満たすアプリが CI にありません。
- RX72N の複数の TLS 接続の demo の、接続の結果（`ENABLE_MULTI_TLS_DEMO`）は、合否に使っていません。

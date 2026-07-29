# FreeRTOS LTS IoT Reference for Renesas RX

## 最新リリース

最新のsafftiリリースタグは
[v202604.00-LTS-rx-1.0.0-saffti-1.3.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.3.0)
です。変更点は [Changelog.md](Changelog.md) を参照してください。

## 最新の実機検証・性能

最終更新: 2026-07-29 JST。

この節は本リポジトリで再現する実機テストの要約です。`✓` は同一コミットで
5回連続成功、`○` は最新ベースラインを1回以上確認済み、`—` は未実装または
対象外を示します。詳細なCI証跡は
[Hardware CI Validation / 最新テスト結果](#hardware-ci-validation--最新テスト結果)、
性能値と測定条件は
[RX72N/Ether集約@840c6451](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md)、
[RX65N/BG96@1b9ea826](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-bench/-/blob/1b9ea82608efcd4bffcfb2991d4f507faea200fe/README.md)
を固定参照とします。

### AWS IoT Core 接続テスト結果

| <small>MCU環境</small> | <small>MQTT</small> | <small>OTA</small> | <small>Fleet</small> | <small>TLS1.3 MQTT</small> | <small>TLS1.3 OTA</small> | <small>TLS1.3 Fleet</small> |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| <small>RX72N/Ether<br>software</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5951)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5959)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5953)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5961)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5955)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5956)</small> |
| <small>RX72N/Ether<br>TSIP</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5958)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5963)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5964)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6049)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6063)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6076)</small> |
| <small>RX65N/BG96<br>software</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5952)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5954)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5957)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5960)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5962)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5965)</small> |
| <small>RX65N/BG96<br>TSIP</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5966)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5967)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5969)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6049)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6063)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6076)</small> |
| <small>RX671/Type 1YN<br>software</small> | <small>[○](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8169)</small> | <small>—</small> | <small>[○](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8570)</small> | <small>[○](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8647)</small> | <small>—</small> | <small>[○](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8726)</small> |
| <small>RX671/Type 1YN<br>TSIP</small> | <small>[○](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8619)</small> | <small>—</small> | <small>[○](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9032)</small> | <small>[○](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8674)</small> | <small>—</small> | <small>[○](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9163)</small> |

<small>AWS IoT Core は [SessionTicket TLS extension をサポートしていません](https://docs.aws.amazon.com/iot/latest/developerguide/transport-security.html)。RX72N/Ether software では [pipeline #6087](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6087) で TLSv1.3 full handshake は2回成功する一方、NewSessionTicket が得られず resumption 不成立であることを確認しています。</small>

<small>RX671/Type 1YN TSIP の AWS IoT MQTT は、device certificateのPKCS #11 provisioning、TSIP KeyIndex、WHD JOIN / DHCP、TLS / MQTT publishを [benchmark pipeline #8619](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8619) で実機確認しています。LANBENCHで成功しているTSIP TLSをAWS IoT MQTT成功として流用していません。</small>

<small>RX671/Type 1YN TSIP の TLS 1.3 AWS IoT MQTT は、[benchmark pipeline #8674](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8674) で `TLSv1.3`、TSIP CertificateVerify `attempts=1 / calls=1 / failures=0 / status=0 / bytes=260`、TLS / MQTT終了コード0を実機確認しています。この構成でTSIPが担当するTLS 1.3処理はクライアントCertificateVerifyであり、record protectionとkey scheduleはsoftware実装です。`○`は単発の実機証跡で、nightly matrixで継続確認します。</small>

<small>RX671/Type 1YN TSIP の Fleet Provisioning は、親 [pipeline #9032](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9032) から [bridge #58087](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/58087) を介して起動した [benchmark pipeline #9033](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/9033) で、claim/provisionedのTLS 1.2接続、CSR、証明書とThing作成、MQTT、claim-free imageへのpark、AWS上の一時policy・生成証明書・Thingの削除まで成功しました。現行構成でTSIPを使用するのはclaim接続の秘密鍵演算（TSIP KeyIndex）であり、Fleetが生成するdevice鍵とprovisioned接続はsoftware PKCS #11です。`○`は単発の実機証跡で、nightly stabilizing行で継続確認します。</small>

<small>RX671/Type 1YN software Fleet は [pipeline #8570](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8570) で、claim/provisioned MQTT、証明書とThing作成、TLS 1.2、claim-free imageへのpark、AWS上の生成証明書とThingの削除まで一巡して成功しました。CSR、証明書PEM、ownership token、秘密鍵はUART/job traceへ出さず、Fleet MOTはpipeline/commitに結び付けた暗号化artifactだけを受け渡します。`○`は単発の実機証跡であり、nightly stabilizing行で継続確認します。</small>

<small>RX671/Type 1YN software の TLS 1.3 Fleet は [pipeline #8726](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8726) で、claim/provisioned の2接続がともに `TLSv1.3`、Fleet 5/5 marker、claim-free imageへのpark、AWS上の生成証明書とThingの不存在確認まで成功しました。TLS 1.3 min/max固定に加えて、実際のnegotiated versionとハンドシェイク回数2回をCIで検査します。`○`は単発の実機証跡であり、TLS 1.3専用のnightly stabilizing行で継続確認します。</small>

<small>RX671/Type 1YN TSIP の TLS 1.3 Fleet は、親 [pipeline #9163](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9163) の [bridge #58821](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/58821) から起動した [benchmark pipeline #9164](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/9164) で、claim側のTSIP KeyIndex / TSIP CertificateVerifyとprovisioned側のsoftware PKCS #11を使い、2接続とも `TLSv1.3` で成功しました。Fleet 5/5 marker、claim-free imageへのpark、一時claim policy・生成証明書・Thingの削除まで確認しています。`○`は単発の実機証跡であり、nightly stabilizing行で継続確認します。</small>

### LANBENCH / TLSエンドポイント基礎テスト結果

#### TLS 1.3 Resumption / 0-RTT

| <small>MCU環境</small> | <small>TLS1.3 Resumption</small> | <small>TLS1.3 0-RTT</small> |
|---|:-:|:-:|
| <small>RX72N/Ether<br>software</small> | <small>[✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6496)</small> | <small>[✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6496)</small> |
| <small>RX72N/Ether<br>TSIP</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6454)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6454)</small> |
| <small>RX65N/BG96<br>software</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6488)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6488)</small> |
| <small>RX65N/BG96<br>TSIP</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6489)</small> | <small>[✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6489)</small> |
| <small>RX671/Type 1YN<br>software</small> | <small>[✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8525)</small> | <small>[✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8525)</small> |
| <small>RX671/Type 1YN<br>TSIP</small> | <small>[✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8533)</small> | <small>[✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8533)</small> |

<small>この表は AWS IoT Core ではなく、SessionTicket を発行できる LANBENCH / Mbed TLS `ssl_server2` などのTLSエンドポイントに対する基礎実験結果です。</small>

### TCP・TLS性能（ターゲット横断）

`SINK`はMCUから対向へ送信、`SOURCE`は対向からMCUが受信する方向です。
各ターゲットの接続媒体、payload、対向、統計方法が異なるため、表は現在値を同じ形式で
探すための索引であり、媒体間の直接的な優劣を示すものではありません。

| MCU環境 | 接続 | 通信 | TLS加速 | SINK | SOURCE | CPU指標 (SINK / SOURCE) | 測定条件 | 固定参照 |
|---|---|---|---|---:|---:|---|---|---|
| RX72N Envision Kit | Ethernet | TCP | - | 84.373 [84.330-84.417] Mbps | 94.154 [93.813-95.581] Mbps | busy proxy 100.00 / 83.54 % | 10 MiB、warm-up 1 + measured 5 | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#merged-main-ether-transport) |
| RX72N Envision Kit | Ethernet | TLS 1.2 | none | 4.189 [4.188-4.189] Mbps | 4.434 [4.337-4.470] Mbps | busy proxy 100.00 / 99.60 % | 10 MiB、warm-up 1 + measured 5 | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#merged-main-ether-transport) |
| RX72N Envision Kit | Ethernet | TLS 1.2 | TSIP | **43.113 [43.091-43.259] Mbps** | **54.448 [53.654-55.534] Mbps** | busy proxy 100.00 / 93.56 % | 10 MiB、16 KiB record、1 + 5 | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#merged-main-ether-transport) |
| RX72N Envision Kit | Ethernet | TLS 1.3 | TSIP | **49.991 [49.965-50.002] Mbps** | **70.569 [69.503-71.029] Mbps** | busy proxy 100.00 / 96.47 % | 10 MiB、full TSIP record、1 + 5 | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#merged-main-ether-transport) |
| CK-RX65N V1 | BG96 Cellular | TCP | - | **0.124 Mbps** | **0.144 Mbps** | 未測定 / 未測定 | 768 KiB、Cat-M1、AT/QIRD、EC2対向 | [`RX65N@1b9ea826`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-bench/-/blob/1b9ea82608efcd4bffcfb2991d4f507faea200fe/README.md#最新性能) |

RX72Nのbusy proxyは絶対CPU使用率ではありません。RX65N/BG96のTLS throughputと
CPU負荷率は未測定であり、TCP値から推定していません。

### 2セッション同時TLS性能（ターゲット横断）

| MCU環境 | 接続 | TLS | 同時通信 | 合計中央値 | 公平性・重複条件 | 測定条件 | 固定参照 |
|---|---|---|---|---:|---|---|---|
| RX72N Envision Kit | Ethernet | TLS 1.2 + TSIP | SINK + SINK | **43.251 Mbps** | overlap 99.96 %以上、fairness 99.99 %以上 | 2 session、各方向5回 | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#supporting-packet-evidence) |
| RX72N Envision Kit | Ethernet | TLS 1.2 + TSIP | SOURCE + SOURCE | **56.584 Mbps** | overlap 99.96 %以上、fairness 99.99 %以上 | 2 session、各方向5回 | [`RX72N@840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md#supporting-packet-evidence) |
| CK-RX65N V1 | BG96 Cellular | - | 全モード | 未測定 | 未測定 | TLS同時throughput未評価 | [`RX65N@1b9ea826`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-bench/-/blob/1b9ea82608efcd4bffcfb2991d4f507faea200fe/README.md) |

## About This Fork / このフォークについて

This repository is a fork of [renesas/iot-reference-rx](https://github.com/renesas/iot-reference-rx), modified and maintained for Renesas RX IoT reference work.

The upstream repository officially supports only the CK-RX65N v2 board and does **not** include RX72N projects. This fork extends the original by:

1. **Adding RX72N Envision Kit support** — porting the FreeRTOS + AWS IoT demo (Ethernet, MQTT PubSub, OTA) to the RX72N Envision Kit, which is not covered upstream
2. **Adding CK-RX65N + BG96 cellular support** — carrying the proven OSS CK-RX65N/BG96 OTA reference into this tree as the recommended cellular modem path for this fork
3. **Adding EK-RX671 + Type 1YN Wi-Fi support** — carrying the WHD/SDIO bring-up into this tree and extending it to FreeRTOS+TCP plus an AWS IoT MQTT smoke baseline over Wi-Fi
4. **Improving the boot loader** — replacing the upstream's simple dual-bank boot loader with a production-grade design, with the ultimate goal of integrating [MCUboot](https://www.mcuboot.com/) as the secure boot loader
5. **CI/CD integration** — automated build, flash, provisioning, and MQTT/OTA testing via GitLab CI with hardware-in-the-loop

本リポジトリは [renesas/iot-reference-rx](https://github.com/renesas/iot-reference-rx) のフォークです。
upstream は CK-RX65N v2 のみを公式サポートしており、**RX72N には対応していません**。
本フォークでは以下の改造を行っています:

1. **RX72N Envision Kit 対応の追加** — upstream にない RX72N 向け FreeRTOS + AWS IoT デモ（Ethernet / MQTT PubSub / OTA）の移植
2. **CK-RX65N + BG96 Cellular 対応の追加** — 安定してOTA可能なOSS版CK-RX65N/BG96構成を、このフォークの推奨セルラー構成として取り込み
3. **EK-RX671 + Type 1YN Wi-Fi 対応の追加** — WHD/SDIO bring-up を `iot-reference-rx` の FreeRTOS/AWS IoT baseline へ統合し、FreeRTOS+TCP と AWS IoT MQTT smoke まで到達
4. **ブートローダの本格化** — upstream の簡易デュアルバンクブートローダを本格仕様に変更。最終的には [MCUboot](https://www.mcuboot.com/) への換装を予定
5. **CI/CD 統合** — GitLab CI による自動ビルド・フラッシュ・プロビジョニング・MQTT/OTA テスト（実機接続 Runner）

### Upstream

| Role | URL |
|------|-----|
| Upstream (Renesas) | https://github.com/renesas/iot-reference-rx |
| This fork (GitLab) | https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx |
| This fork (GitHub mirror) | https://github.com/HirokiIshiguro/iot-reference-rx |

Base version: **202604.00-LTS-rx** (FreeRTOS 202604.00 LTS)

Latest saffti release:
**[v202604.00-LTS-rx-1.0.0-saffti-1.3.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.3.0)**

## Supported Board / 対応ボード

| Board | MCU | Core | Code Flash | RAM | Connectivity |
|-------|-----|------|------------|-----|--------------|
| **RX72N Envision Kit** | RX72N (R5F572NN) | RXv3 | 4 MB (dual-bank) | 1 MB + 512 KB | Ethernet (on-board) |
| **CK-RX65N V1 + BG96** | RX65N dual-bank | RXv2 | 2 MB (dual-bank) | 640 KB | Cellular Cat-M1/NB-IoT (Quectel BG96) |
| **EK-RX671 + Type 1YN** | RX671 (R5F5671E) | RXv3 | 2 MB | 384 KB + 8 KB E2 data flash | Wi-Fi over SDIO (Murata Type 1YN / CYW43439) |

> **Note:** The upstream RYZ014A cellular project is obsolete in practice. This fork keeps BG96 as the maintained cellular reference path.

## Projects / e2 studio プロジェクト

The following e2 studio projects are maintained under `Projects/`:

| Project | Path | Description |
|---------|------|-------------|
| Boot Loader | `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/` | RX72N dual-bank boot loader for OTA firmware update |
| AWS Ether Demo | `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/` | FreeRTOS + AWS IoT demo (MQTT PubSub, OTA) over Ethernet |
| AWS Ether Demo with TSIP | `Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx/` | RX72N Ethernet demo using the TSIP-enabled TLS backend |
| CK-RX65N BG96 Boot Loader | `Projects/boot_loader_ck_rx65n/e2studio_ccrx/` | RX65N dual-bank boot loader for BG96 OTA |
| CK-RX65N BG96 AWS Demo | `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/` | FreeRTOS + AWS IoT demo (MQTT PubSub, OTA) over BG96 cellular |
| CK-RX65N BG96 AWS Demo with TSIP | `Projects/aws_bg96_ck_rx65n_tsip/e2studio_ccrx/` | BG96 cellular demo using the TSIP-enabled TLS backend; hardware validation requires RX65N-specific TSIP wrapped blobs |
| EK-RX671 Boot Loader | `Projects/boot_loader_rx671_ek/e2studio_ccrx/` | Standalone RX671 dual-bank secure boot loader; build-only CI with an opt-in RPi#1 flash/UART smoke gate |
| EK-RX671 Type 1YN Wi-Fi | `Projects/aws_wifi_rx671_ek/e2studio_ccrx/` | WHD/SDIO Wi-Fi bring-up project with FreeRTOS+TCP and AWS IoT MQTT smoke baseline |

### Boot Loader Architecture / ブートローダ構成

The current boot loader uses the RX dual-bank flash mechanism with r_fwup (Firmware Update module) for OTA:

- Validates new firmware image signature (ECDSA-P256)
- Performs bank swap on successful verification
- Supports rollback on signature verification failure

#### Boot Loader / Application Clock Handoff

RX72N / RX65N のブートローダはアプリケーションのリセットハンドラへ直接ジャンプします。アプリケーションは
電源リセット直後に近いクロック状態を前提に BSP の `mcu_clock_setup()` を実行するため、
ブートローダとアプリケーションのクロック設定は同一にしてください。クロック設定を変更する場合は、
対象 MCU のブートローダ、software app、TSIP app の e2 studio/Smart Configurator 設定を同時に更新します。

ブートローダはジャンプ直前に使用中の PLL 系クロックを停止し、アプリケーション側 BSP が安全に
再初期化できる状態へ戻します。現時点では RX72N は PLL/PPLL、RX65N は PLL を MCU 別分岐で扱います。
この処理はブートローダ側のハンドオフ処理に閉じ込め、
生成された BSP 内部ファイルは原則として純正のまま維持します。

**Roadmap:** The current r_fwup-based boot loader will be replaced with [MCUboot](https://www.mcuboot.com/) to provide a production-grade secure boot chain with swap/revert, encrypted images, and hardware root of trust.

## Development Environment / 開発環境

### Required Tools

| Tool | Version | Notes |
|------|---------|-------|
| [e2 studio](https://www.renesas.com/software-tool/e-studio) | 2025-12 | Renesas IDE (includes Smart Configurator) |
| CC-RX Compiler | V3.07.00 | Renesas C/C++ compiler for RX family |
| [Renesas Flash Programmer](https://www.renesas.com/software-tool/renesas-flash-programmer-programming-gui) (rfp-cli) | V3.22 | CLI flash writer |
| Git | 2.x+ | With submodule support |

### Getting the Source / ソースコード取得

This repository uses Git submodules (FreeRTOS-Kernel, mbedTLS, coreMQTT, etc.). Always clone with `--recursive`:

```bash
git clone --recursive https://github.com/HirokiIshiguro/iot-reference-rx.git

# If already cloned without --recursive:
git submodule update --init --recursive
```

> **Warning:** Without initialized submodules, the build will fail with missing header errors (e.g., `FreeRTOS.h` not found).

### Build / ビルド方法

#### Using e2 studio IDE

1. Open e2 studio
2. **File > Import > General > Existing Projects into Workspace**
3. Set root directory to `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/` or `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/`
4. Build the project (Ctrl+B)

#### Headless Build (CLI)

```bash
# Build both boot_loader and aws_ether projects headlessly
pwsh -File tools/build_headless_rx72n.ps1 \
  -ProjectRoot <repo_root> \
  -E2Studio <path_to_e2studio.exe> \
  -Workspace <temp_workspace>
```

The script imports and builds both `boot_loader_rx72n_envision_kit` and `aws_ether_rx72n_envision_kit`, then verifies `.mot` / `.abs` / `.x` outputs.

For the CK-RX65N + BG96 cellular reference:

```bash
pwsh -File tools/build_headless_rx65n_bg96.ps1 \
  -ProjectRoot <repo_root> \
  -E2Studio C:/Renesas/e2_studio_2025_12/eclipse/e2studio-cli.exe \
  -Workspace <temp_workspace>
```

The script imports and builds both `boot_loader_ck_rx65n` and `aws_bg96_ck_rx65n`, then verifies `.mot` / `.abs` / `.x` outputs.

For the EK-RX671 + Type 1YN Wi-Fi baseline:

```bash
pwsh -File tools/build_headless_rx671_wifi.ps1 \
  -ProjectRoot <repo_root> \
  -E2Studio C:/Renesas/e2_studio_2026_04_2/eclipse/e2studioc.exe \
  -Workspace <temp_workspace> \
  -WifiConfigFile <local_wifi_config> \
  -AwsIotConfigDir <local_aws_iot_credential_dir>
```

The script imports and builds `Projects/aws_wifi_rx671_ek/e2studio_ccrx`,
initializes required submodules, applies the project-local WHD patch, and
generates ignored local headers for Wi-Fi and AWS IoT credentials. The local
Windows baseline uses SCI6 on COM5 at 921600 bps and reaches `AWS MQTT=0`
after WHD JOIN, DHCP, TLS, and MQTT connect/disconnect. GitLab CI uses the same
SCI6 stream through RPi#1's stable `/dev/serial/by-id/...` path.

For the standalone EK-RX671 boot loader:

```bash
pwsh -File tools/build_headless_rx671_bootloader.ps1 \
  -ProjectRoot <repo_root> \
  -E2Studio C:/Renesas/e2_studio_2026_04_2/eclipse/e2studioc.exe \
  -Workspace C:/Temp/e2ws_iot_ref_rx671_bootloader_2026_04_2
```

The project fixes the boot loader to `0xFFFC0000`-`0xFFFFFFFF`, preserves the
application's Data Flash, and reads the verification public key from shared
LittleFS. It has no compiled-in key fallback and rejects hash-only firmware.
See `Projects/boot_loader_rx671_ek/README.md` for the layout check and
the explicit `RUN_RX671_BOOTLOADER_SMOKE=true` RPi#1 manual gate.

### Flash / 書き込み方法

Connect the RX72N Envision Kit via USB and use rfp-cli:

```bash
# Write boot_loader
rfp-cli -d RX72N -t jlink -if swd -p boot_loader_rx72n_envision_kit.mot -run -noquery

# Write application (preserving boot_loader region)
rfp-cli -d RX72N -t jlink -if swd -file aws_ether_rx72n_envision_kit.mot -auto -noerase -run -noquery
```

### Demo Configuration / デモ設定

Demo selection is controlled by macros in `src/frtos_config/demo_config.h`:

| Macro | Value | Effect |
|-------|-------|--------|
| `ENABLE_OTA_UPDATE_DEMO` | 0 | MQTT PubSub only |
| `ENABLE_OTA_UPDATE_DEMO` | 1 | MQTT PubSub + OTA |

## Software Stack / ソフトウェア構成

### Key OSS Components

| Library | Version | LTS Until |
|---------|---------|-----------|
| FreeRTOS Kernel | 11.3.0 | 2028/06/30 |
| FreeRTOS-Plus-TCP | 4.4.1 | 2028/06/30 |
| coreMQTT | 5.0.2 | 2028/06/30 |
| coreMQTT Agent | 1.3.1 + local coreMQTT v5 adapter | -- |
| corePKCS11 | 3.6.4 | 2028/06/30 |
| coreJSON | 3.3.1 | 2028/06/30 |
| AWS IoT Jobs | 2.0.1 | 2028/06/30 |
| AWS IoT MQTT File Streams | 1.2.0 | 2028/06/30 |
| mbedTLS | 3.6.4 | -- |
| littlefs | 2.5.1 | -- |
| r_fwup | 2.06 | -- |

### FIT Modules (RX Driver Package)

| FIT module | Revision | RX Driver Package |
|------------|----------|-------------------|
| r_bsp | 7.52 | 1.46 |
| r_ether_rx | 1.23 | 1.36 - 1.46 |
| r_flash_rx | 5.22 | [1.47 (`2c85d94a9b8b3e7f7bec94663bce0d79b5a17162`)](https://gitlab.saffti.jp/oss/import/github/renesas/rx-driver-package/-/commit/2c85d94a9b8b3e7f7bec94663bce0d79b5a17162) |
| r_sci_rx | 5.40 | 1.46 |
| r_s12ad_rx | 5.40 | 1.45 - 1.46 |
| r_byteq | 2.10 | 1.37 - 1.46 |
| r_irq_rx | 4.60 | 1.46 |
| r_fwup | 2.06 | [1.49 (`14a0b1bdd47b870cee294604eb7d4501d59ed07d`)](https://gitlab.saffti.jp/oss/import/github/renesas/rx-driver-package/-/commit/14a0b1bdd47b870cee294604eb7d4501d59ed07d) |
| r_tsip_rx (RX72N TSIP project) | 1.23.saffti-custom | Renesas 1.23 / RX Driver Package 1.49 base + SAFFTI optional wait hook |

The generated `r_fwup` trees are kept identical to the Renesas 2.06 module.
RX72N Envision Kit OTA image generation uses
`tools/fwup/rx72n_envision_kit_dual_bank.prm.csv` so that the signed RSU layout
matches the existing boot loader reservation at `0xFFFC0000`–`0xFFFFFFFF`.

## CI/CD Pipeline

The GitLab CI pipeline is organized by MCU environment. Job names use
`<action>_<mcu_env>_<feature>` where possible.

| MCU environment | Hardware | Connectivity | Standard runner |
|-----------------|----------|--------------|-----------------|
| `rx72n_ether` | RX72N Envision Kit | Ethernet | RPi #1 / `dev-ek-rx72n-set1` |
| `rx65n_bg96` | CK-RX65N V1 + Quectel BG96 | Cellular Cat-M1/NB-IoT | RPi #3 / `dev-ck-rx65n-bg96` |
| `rx671_wifi` | EK-RX671 + Murata Type 1YN | Wi-Fi over SDIO | RPi #1 / `dev-ek-rx671` |

Core hardware jobs:

| Function | RX72N Ethernet job | RX65N/BG96 job | RX671/Type 1YN job |
|----------|--------------------|----------------|---------------------|
| Build boot loader and app | `build_rx72n_ether` | `build_rx65n_bg96` | `build_rx671_wifi` (app only) |
| Flash boot loader / initial app | included in `test_rx72n_ether_mqtt` for MQTT/OTA/full (`flash_rx72n_ether` for legacy 0-RTT) | `flash_rx65n_bg96` | `flash_rx671_wifi` (E2OB) |
| Download app via boot loader | included in `test_rx72n_ether_mqtt` | `download_rx65n_bg96_app` | not yet implemented |
| Verify app startup | included in MQTT/OTA observation | `run_rx65n_bg96_app` | `test_rx671_wifi` (`network`) |
| Provision MQTT credentials | included in `test_rx72n_ether_mqtt` for MQTT/OTA/full (`provision_rx72n_ether_mqtt` for legacy 0-RTT) | `provision_rx65n_bg96_mqtt` | compile-time CI variables |
| Test MQTT | `test_rx72n_ether_mqtt` | `test_rx65n_bg96_mqtt` | `test_rx671_wifi` (`mqtt`) |
| Build OTA candidate | `build_rx72n_ether_ota` | `build_rx65n_bg96_ota` | not yet implemented |
| Create pipeline-owned AWS IoT Thing / OTA job | `create_rx72n_ether_ota` | `create_rx65n_bg96_ota` | not yet implemented |
| Restore, provision, and observe OTA under hardware lock | `test_rx72n_ether_ota` | `test_rx65n_bg96_ota` | not yet implemented |
| Build Fleet Provisioning image | `build_rx72n_ether_fleet` | `build_rx65n_bg96_fleet` | `build_rx671_wifi_fleet` |
| Test Fleet Provisioning | `test_rx72n_ether_fleet` | `test_rx65n_bg96_fleet` | `test_rx671_wifi_fleet` + `cleanup_rx671_wifi_fleet` |

RX72N の `mqtt` / `ota` / `full` scope では、`test_rx72n_ether_mqtt` が
正確なpipeline成果物のflash、AWS IoT credential provisioning、MQTT確認を
1つの実機jobとして連続実行します。このjobを含むRPi#1のRX72N実機jobは
`RX72N_RPI1_HARDWARE_LOCK_PATH=/tmp/e2lite-rfp-cli.lock.d/rx72n-device-01.lock`
を `flock` し、
project内だけで有効な `resource_group` では防げないcross-project書換えを防止します。
[TLS 1.3 benchmark側の同じlock](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/merge_requests/16)
も同じpathを使用します。この外側のtransaction lockはvenv/pip準備後、最初の
RFP/UART操作前に取得します。`tools/rfp_cli_locked.sh` は従来どおり別pathの
`/tmp/rx72n-e2lite-rfp-cli.lock.d/rfp-cli.lock` を個々のRFP呼び出しに使用するため、
二層のlockは相互に自己デッドロックしません。

RX671/Type 1YN のRPi#1実機jobも、standalone software benchmarkと同じ
`RX671_RPI1_HARDWARE_LOCK_PATH=/tmp/ek-rx671-rpi1-hardware.lock` を `flock` します。
`flash_rx671_wifi` と `test_rx671_wifi` の両方がcross-project lockを取得し、後者は
lock保持中に正確なpipeline成果物を再flashしてからUARTを観測します。これにより、
分割job間にdownstream benchmarkが実行されても別firmwareを誤って評価しません。
競合投入したparent [#8276](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8276)
とsoftware benchmark [#8277](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8277)
では、software実機jobが78.680秒待って同じlockを取得し、両pipelineが成功しました。

通常のMR pipelineはRX72N MQTTを実機確認しますが、default branch pipelineは
RX72Nをbuild-onlyとします。post-merge直後の重複実機実行を避け、全実機coverageは
共通lockを用いるnightly focused matrixで取得します。

OTA経路のAWS操作は、資格情報を持つWindows `aws-cli-ishiguro` Runner上の
`create_*_ota` / `cleanup_*_ota`だけで実行します。`create_*_ota`は
`<base Thing>-ota-<pipeline ID>-<job ID>`というpipeline専用Thingを作り、
project / pipeline / job IDをThing attributeへ作成と同時に記録します。base Thingと
同じ証明書を`NON_EXCLUSIVE_THING`として追加attachし、そのThingだけを対象とする
UUID付きone-shot AWS IoT OTA Jobを作成します（RX65N software TLSは既存の
pipeline専用dynamic Thingを使用）。RPi RunnerへAWS資格情報は配置しません。

各`test_*_ota`は実機lockを保持したまま、正確なbaselineの再書込み、
pipeline専用Thing名を含むcredential / TSIP key / code signer設定、
download・activation・commit観測までを連続実行します。別pipelineは異なる
Thing名を使うため、先にAWS Jobを作成していてもone-shot Jobを横取りできません。
作成helperは最初のAWS変更より前にS3/OTA識別子をjournalへ保存します。
cleanupはOTA update / IoT Job / S3 source objectに加え、OTA ID単位の専用prefixへ
AWS Signerが生成した全object version / delete markerの不在を確認します。
Signer出力は遅延生成される場合があるため、既定60秒の監視枠内で再列挙と削除を
続けます。さらに専用Thingから
記録済み証明書だけをdetachしてThingを削除した後、base Thingと証明書attachの
残存および専用Thingの不在を確認します。S3 VersionIdがjournalへ反映される前に
作成jobが停止した場合も、pipeline固有keyの全version / delete markerを列挙して
削除し、current objectと全versionの不在を確認します。

任意のmulti-TLS後段と旧0-RTT分割経路に残るstate gapは
[Issue #112](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/112)
で追跡します。

The RX671 hardware lane builds on the Windows CC-RX runner, then flashes the
application through the EK-RX671 onboard E2OB on RPi#1. The UART monitor opens
SCI6 before issuing `rfp-cli -run`, so the one-shot WHD startup messages are not
lost. `network` scope requires successful AP JOIN, WHD bring-up, and a
FreeRTOS+TCP network-up event. `mqtt` additionally requires successful TLS and
MQTT status markers. Raw UART and RFP logs plus a JUnit report are retained as
job artifacts.

`fleet` scope builds a separate image with a 2304-byte MQTT network buffer,
250 KiB FreeRTOS heap, and SDHI `SDHI_DIV_8` DTC transfer. The claim-bearing MOT
is encrypted with a pipeline/commit-bound context before artifact upload; the
RPi#1 job verifies that context and digest before flashing. Its shell trap and
`after_script` both restore the claim-free network image. A final Windows job
deletes the generated AWS IoT certificate and Thing and verifies that both are
absent. Fleet MQTT payload contents are never persisted to UART/CI logs; the
firmware records only payload length and the monitor fails closed if it sees a
CSR, certificate, ownership token, or private-key PEM block.

Current hardware validation status is summarized in
**Hardware CI Validation / 最新テスト結果** later in this README. As of
[v202604.00-LTS-rx-1.0.0-saffti-1.1.0](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tags/v202604.00-LTS-rx-1.0.0-saffti-1.1.0),
MQTT / OTA / Fleet Provisioning are validated on both RX72N/Ether and
RX65N/BG96 for software TLS and TSIP TLS backends. TSIP + TLS 1.3 MQTT is also
validated on both boards; TSIP + TLS 1.3 OTA and Fleet Provisioning are also
validated on both boards.

RX65N/BG96 TSIP hardware validation uses RX65N-specific UFPK-derived runtime
provisioning payloads and the matching static AWS IoT certificate documented in
`docs/tsip-integration-plan.md`.

### Pipeline Profiles

This project is treated as an advanced hardware CI pipeline: the full matrix spans multiple boards and configurations, so merge request pipelines run representative hardware paths and scheduled pipelines run the heavier regression set.

| Profile | Pipeline source | Default scope |
|---------|-----------------|---------------|
| `branch` | Feature branch push | Build only. Hardware jobs are kept out of push pipelines to avoid interleaving board state with MR pipelines. |
| `mr` | Merge request | `RX72N_TEST_SCOPE=mqtt`, `RX65N_BG96_TEST_SCOPE=mqtt`. This covers both transports while keeping review feedback short; OTA coverage is delegated to the focused matrix. |
| `mr-rx671` | Merge request changing the RX671 project or its UART test | `RX671_WIFI_TEST_SCOPE=network`; RX72N and RX65N stay build-only so the RX671 hardware result is isolated. |
| `mr-rx671-bootloader` | Merge request changing only the standalone RX671 boot loader | Runs the RX671 boot-loader CC-RX build/layout contract; all board test scopes stay build-only. |
| `focused` | Manual/API | Build only unless the caller sets `RX72N_TEST_SCOPE`, `RX65N_BG96_TEST_SCOPE`, `RX671_WIFI_TEST_SCOPE`, TLS backends, or TLS version variables explicitly. |
| `main` | Default branch push | RX72N/RX65N MQTT plus RX671 network smoke; full matrix coverage is delegated to the schedule. |
| `release` | Tag | Full software-TLS regression for RX72N and RX65N/BG96 plus RX671 network smoke. |
| `nightly_matrix` | GitLab pipeline schedule | Parent pipeline that fans out the focused matrix rows. The active nightly schedule keeps `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true` so promoted table cells continue to run daily. RX72N/Ether software LANBENCH is covered through a downstream bridge to the benchmark project. |

Focused examples:

```bash
# RX72N TSIP OTA only
PIPELINE_PROFILE=focused RX72N_TEST_SCOPE=ota RX65N_BG96_TEST_SCOPE=build RX72N_TLS_BACKEND=tsip

# RX65N/BG96 TSIP OTA only
PIPELINE_PROFILE=focused RX65N_BG96_TEST_SCOPE=ota RUN_RX72N_BUILD=false RX72N_SKIP_HW_TESTS=true RX65N_BG96_TLS_BACKEND=tsip

# EK-RX671 + Type 1YN AP JOIN and FreeRTOS+TCP startup
PIPELINE_PROFILE=focused RX671_WIFI_TEST_SCOPE=network RX72N_TEST_SCOPE=build RX65N_BG96_TEST_SCOPE=build

# EK-RX671 + Type 1YN AWS IoT TLS/MQTT smoke
PIPELINE_PROFILE=focused RX671_WIFI_TEST_SCOPE=mqtt RX72N_TEST_SCOPE=build RX65N_BG96_TEST_SCOPE=build

# EK-RX671 + Type 1YN software Fleet Provisioning + AWS cleanup
PIPELINE_PROFILE=focused RX671_WIFI_TEST_SCOPE=fleet RX72N_TEST_SCOPE=build RX65N_BG96_TEST_SCOPE=build

# EK-RX671 + Type 1YN software Fleet Provisioning over TLS 1.3 + AWS cleanup
PIPELINE_PROFILE=focused RX671_WIFI_TEST_SCOPE=fleet RX671_WIFI_REQUIRE_TLS_VERSION=TLSv1.3 RX72N_TEST_SCOPE=build RX65N_BG96_TEST_SCOPE=build

# EK-RX671 + Type 1YN TSIP AWS IoT TLS/MQTT smoke (downstream benchmark)
PIPELINE_PROFILE=focused RUN_RX671_TSIP_AWS_MQTT_TEST=true RX671_BENCHMARK_PROJECT_REF=main RUN_RX671_WIFI_BUILD=false RUN_RX72N_BUILD=false RUN_RX65N_BG96_BUILD=false

# EK-RX671 + Type 1YN TSIP AWS IoT TLS 1.3/MQTT smoke (downstream benchmark)
PIPELINE_PROFILE=focused RUN_RX671_TSIP_AWS_MQTT_TLS13_TEST=true RX671_BENCHMARK_PROJECT_REF=main RUN_RX671_WIFI_BUILD=false RUN_RX72N_BUILD=false RUN_RX65N_BG96_BUILD=false

# EK-RX671 + Type 1YN TSIP Fleet Provisioning TLS 1.2 (downstream benchmark)
PIPELINE_PROFILE=focused RUN_RX671_TSIP_FLEET_TEST=true RX671_BENCHMARK_PROJECT_REF=main RUN_RX671_WIFI_BUILD=false RUN_RX72N_BUILD=false RUN_RX65N_BG96_BUILD=false

# Manual/API software TLS 1.3 MQTT on both boards
PIPELINE_PROFILE=focused RX72N_TEST_SCOPE=mqtt RX65N_BG96_TEST_SCOPE=mqtt AWS_IOT_ENDPOINT=d095604912rj95htx1mal-ats.iot.ap-northeast-1.amazonaws.com RX72N_REQUIRE_TLS_VERSION=TLSv1.3 RX65N_BG96_REQUIRE_TLS_VERSION=TLSv1.3

# Manual/API TSIP TLS 1.3 MQTT on both boards
PIPELINE_PROFILE=focused RX72N_TEST_SCOPE=mqtt RX65N_BG96_TEST_SCOPE=mqtt RX72N_TLS_BACKEND=tsip RX65N_BG96_TLS_BACKEND=tsip AWS_IOT_ENDPOINT=d095604912rj95htx1mal-ats.iot.ap-northeast-1.amazonaws.com RX72N_REQUIRE_TLS_VERSION=TLSv1.3 RX65N_BG96_REQUIRE_TLS_VERSION=TLSv1.3 RX65N_BG96_AWS_IOT_ENDPOINT_OVERRIDE=d095604912rj95htx1mal-ats.iot.ap-northeast-1.amazonaws.com
```

### Scheduled Hardware Regressions

The project-level GitLab pipeline schedule is part of the reference pipeline design. Keep the merge request pipeline short, and move matrix coverage that is useful but not review-blocking into the nightly matrix schedule. The active schedule is a single parent pipeline; child pipelines are serialized per board by matrix resource groups, so RX72N and RX65N/BG96 rows can run in parallel without interleaving state on the same physical board.
Scheduler policy and cross-project guidance are documented in [development.md](development.md).

| Schedule | Status | Time (JST) | Scope | Purpose |
|----------|--------|------------|-------|---------|
| Nightly focused test matrix (schedule #5) | Active | 02:20 daily | `PIPELINE_PROFILE=nightly_matrix`, `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true` | 条件を満たすnightly matrix行を1回ずつ実行します。RX671/Type 1YNはnetwork、software / TSIP MQTT（TLS 1.2 / TLS 1.3）、software Fleet（TLS 1.2 / TLS 1.3）とTSIP Fleet（TLS 1.2）のstabilizing（AWS cleanup込み）、software / TSIP TLS 1.3 resumption / 0-RTT、および各benchmark projectの性能回帰をdownstream bridgeで実行します。 |

Creating or updating project pipeline schedules requires Maintainer/Owner permissions on this GitLab project. Keep the active GitLab schedules and this table in sync so the scheduled regression set remains reviewable in Git.

`test_rx72n_ether_ota` と `test_rx65n_bg96_ota` はpipeline専用Thingを対象とする
one-shot AWS IoT OTA Jobを消費するため、observerジョブ単体では再試行できません。
再検証時は新しいfocused pipelineまたはnightly matrix rowを開始し、
pipeline専用Thing / OTA Job作成、実機lock内のrestore・provision・observe、
cleanupを一巡させてください。

「nightly matrix」はリポジトリ内の全jobを無条件に実行する意味ではありません。明示的なopt-inであるRX72N software dual AWS MQTT (`RUN_RX72N_MULTI_TLS_TEST=false`) や、必要なgateを満たさない行は起動しません。2026-07-18の [scheduled parent #8168](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8168) は34行を生成し、そのうちRX671の8行はすべて実機成功しました。現在はRX671 TSIP AWS MQTT（TLS 1.2 / TLS 1.3）、software / TSIP TLS 1.3 resumption / 0-RTTに加え、必要なWi-Fi/Fleet/AWS cleanup変数が揃う場合だけsoftware FleetのTLS 1.2 / TLS 1.3とTSIP FleetのTLS 1.2 stabilizing行も対象です。

## Hardware CI Validation / 最新テスト結果

最終更新: 2026-07-27 JST。

`✓` はセルごとに同一コミット上で5回テストOKを確認済みであることを示します。
表中のリンクは5回目確認時の子パイプライン、または補完確認パイプラインを示します。
昇格後に対象セル起因の失敗が1回でも出た場合は、該当セルを再度 stabilizing 扱いへ戻します。
停電、配線作業、Runner 障害など対象セルの実装品質と無関係な外乱は連続成功/失敗判定から除外します。

### Validation Summary

| Area | Current status |
|------|----------------|
| AWS IoT Core MQTT / OTA / Fleet | RX72N/Ether と RX65N/BG96 の software / TSIP 全セルを5回成功確認済み。TLS 1.3 full handshake までの 24/24 セルも5回成功済み。 |
| LANBENCH TLS 1.3 Resumption / 0-RTT | RX72N/Ether software / TSIP と RX65N/BG96 software / TSIP の全セルを5回成功確認済み。 |
| RX671/Type 1YN TLS 1.3 Resumption / 0-RTT | 親`main` `9ca442b8`上でsoftware / TSIPとも5回連続実機成功を確認し、全セルを`✓`へ昇格済み。softwareは`50770dd3`、TSIPは`6d6054e0`を使用。 |
| RX671/Type 1YN AWS IoT | software / TSIP MQTTをTLS 1.2 / TLS 1.3、software FleetをTLS 1.2 / TLS 1.3、TSIP FleetをTLS 1.2でRPi#1実機Runner検証。Fleetはいずれもclaim/provisioned MQTT、claim-free park、AWS certificate/Thing cleanupまで成功し`○`。TSIP Fleetはclaim接続だけがTSIP KeyIndexで、provisioned接続はsoftware PKCS #11。software / TSIP OTAとTSIP Fleet TLS 1.3は未完了。 |
| Nightly schedule | schedule #5をActiveとして02:20 JSTに毎日実行。`PIPELINE_PROFILE=nightly_matrix`, `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true` でgateを満たすパタンを1回ずつ実行し、RX671 software FleetはTLS 1.2 / TLS 1.3、TSIP FleetはTLS 1.2のstabilizing行、RX671 software / TSIP MQTT（TLS 1.2 / TLS 1.3）、RX72N/Ether・RX671/Type 1YNのsoftware / TSIP TLS 1.3 resumption / 0-RTTは各対応経路で実行。 |
| AWS IoT Core resumption / 0-RTT | AWS IoT Core が SessionTicket TLS extension をサポートしていないため、AWS IoT Core 接続表には TLS 1.3 Resumption / 0-RTT 列を置きません。 |

### Evidence Index

| Scope | Commit / condition | Evidence |
|-------|--------------------|----------|
| RX671/Type 1YN network-up | scheduled parent `#8168`, `main` `638117f3`; RPi#1 E2OB/SCI6、WHD JOIN、DHCP | [pipeline #8172](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8172) / [test job #53387](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/53387) |
| RX671/Type 1YN software AWS IoT MQTT | scheduled parent `#8168`, `main` `638117f3`; AWS IoT TLS、MQTT connect | [pipeline #8169](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8169) / [test job #53370](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/53370) |
| RX671/Type 1YN software Fleet Provisioning | `49264e0a`; 2304-byte MQTT buffer、250 KiB heap、SDHI PCLK/8 + DTC。claim/provisioned MQTT、TLS 1.2 x2、5/5 markerを初回成功。Fleet mapのRAM最終割当`0x0005FBB7`、残り1,096 bytes。claim-free park、AWS certificate/Thing absent、trace/artifactのCSR・ownership token・certificate/private-key PEM 0件 | [pipeline #8570](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8570) / [network build #55571](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/55571) / [Fleet build #55572](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/55572) / [hardware #55573](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/55573) / [cleanup #55574](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/55574) |
| RX671/Type 1YN software Fleet Provisioning over TLS 1.3 | `f7e69eff`; TLS 1.3 min/max固定とnegotiated-version検査、2304-byte MQTT buffer、250 KiB heap、SDHI PCLK/8。claim/provisioned MQTTのTLS 1.3 x2、5/5 markerを実機成功。Fleet mapのRAM最終割当`0x0005FBB7`、残り1,096 bytes。pipeline/SHA bind暗号化MOTのみ受け渡し、plaintext/secret build products cleanup、claim-free park、AWS certificate/Thing absentを確認 | [pipeline #8726](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8726) / [Fleet build #56369](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/56369) / [hardware #56371](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/56371) / [cleanup #56372](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/56372) |
| RX671/Type 1YN TSIP AWS IoT MQTT | benchmark `293b1e0b`; PKCS #11 certificate provisioning、TSIP KeyIndex、WHD JOIN / DHCP、TLS / MQTT publish 11/11 checks | [pipeline #8619](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8619) / [build #55829](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/55829) / [hardware #55830](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/55830) |
| RX671/Type 1YN TSIP Fleet Provisioning | parent `c77e232d`、benchmark `33e4a1bf`; 親bridgeから現行子`main`を起動。claim接続はTSIP KeyIndex、provisioned接続はsoftware PKCS #11。TLS 1.2 x2、Fleet 7/7 marker、JUnit 8/8、claim-free park、一時claim policyと生成AWS certificate/Thingの不存在確認 | [parent #9032](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9032) / [bridge #58087](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/58087) / [downstream #9033](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/9033) / [build #58088](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/58088) / [hardware #58090](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/58090) / [claim policy cleanup #58091](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/58091) / [resource cleanup #58092](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/58092) |
| RX671/Type 1YN TSIP AWS IoT MQTT over TLS 1.3 | benchmark feature `fd25232e`、merged `main` `92044199`; TLSv1.3、TSIP CertificateVerify `attempts=1 / calls=1 / failures=0 / status=0 / bytes=260`、TLS / MQTT終了コード0。TSIP境界はクライアントCertificateVerifyで、record protection / key scheduleはsoftware | [pipeline #8674](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8674) / [build #56068](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/56068) / [hardware #56069](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/56069) |
| RX671/Type 1YN software AWS IoT MQTT over TLS 1.3 | `785d9f30`; CI変数のendpoint/certificate/private keyをrunnerローカル設定より優先、TLS 1.3固定。RPi#1 E2OB/SCI6でWHD JOIN、DHCP、`AWS TLS version=TLSv1.3`、`AWS TLS=0`、`AWS MQTT=0`、terminal PASS | [pipeline #8647](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8647) / [build #55936](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/55936) / [flash #55937](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/55937) / [test #55938](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/55938) |
| RX671/Type 1YN TLS 1.3 resumption / 0-RTT 5-run parent | 親`main` `9ca442b8`; 全5回で37/37 downstream bridge success | [P1 #8356](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8356) / [P2 #8394](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8394) / [P3 #8432](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8432) / [P4 #8470](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8470) / [P5 #8508](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8508) |
| RX671/Type 1YN software LANBENCH TLS 1.3 resumption / 0-RTT | benchmark `50770dd3`; 全5回でTLS 1.3 / AES-128-GCM、NewSessionTicket保存、再開、96 byte early data、`early_status=1`、terminal PASS | [S1 #8365](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8365) / [S2 #8398](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8398) / [S3 #8442](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8442) / [S4 #8485](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8485) / [S5 #8525](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8525); 5回目 [build #55328](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/jobs/55328) / [peer #55329](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/jobs/55329) / [target #55330](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/jobs/55330) |
| RX671/Type 1YN TSIP LANBENCH TLS 1.3 resumption / 0-RTT | benchmark `6d6054e0`; 全5回でbuild gateの必須3シンボル、CertificateVerify `calls=1`、`failures=0`、`status=0`、再開TLS 1.3、96 byte early data、`early_status=1`、terminal PASS | [T1 #8381](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8381) / [T2 #8419](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8419) / [T3 #8457](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8457) / [T4 #8494](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8494) / [T5 #8533](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8533); 5回目 [build #55369](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/55369) / [peer #55370](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/55370) / [target #55371](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/jobs/55371) |
| RX671/Type 1YN cross-project transaction lock | parent `e8b21197`がflash/testを共通lock内で実行。software main `3a96ef79`を競合投入し、test jobが78.680秒待機後に取得。両pipeline success | parent [#8276 / test #53895](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/53895) / software [#8277 / test #53897](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/jobs/53897) |
| RX72N TSIP transport include order durability | RX72N TSIP transport include order 修正後 | [#5858](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5858) / [#5877](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5877) / [#5896](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5896) / [#5915](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5915) / [#5950](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5950)。#5950 は 17/18 行成功後に RX65N/BG96 TSIP Fleet 行だけキャンセルされたため、[focused #5969](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5969) で補完。 |
| TSIP backend + TLS 1.3 MQTT | main merge commit `7ed373c9` | [#6045](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6045) / [#6046](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6046) / [#6047](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6047) / [#6048](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6048) / [#6049](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6049) |
| TSIP backend + TLS 1.3 OTA | commit `2e687700`; RX65N/BG96 OTA candidate も TLS 1.3 設定でビルド | [#6059](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6059) / [#6060](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6060) / [#6061](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6061) / [#6062](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6062) / [#6063](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6063) |
| TSIP backend + TLS 1.3 Fleet Provisioning | commit `d91f2271` | [#6072](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6072) / [#6073](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6073) / [#6074](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6074) / [#6075](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6075) / [#6076](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6076) |
| RX72N/Ether TSIP LANBENCH TLS 1.3 resumption / 0-RTT | main merge commit `5aefbb4d`; initial confirmation in [MR !121](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/121), [#6175](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6175) | [#6355](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6355) / [#6388](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6388) / [#6406](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6406) / [#6424](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6424) / [#6442](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6442); 5回目 child [#6454](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6454) |
| RX65N/BG96 software LANBENCH TLS 1.3 resumption / 0-RTT | main merge commit `5aefbb4d`; initial confirmation in [MR !122](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/122), [#6191](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6191) | [#6466](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6466) / [#6482](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6482) / [#6484](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6484) / [#6486](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6486) / [#6488](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6488); 5回目 [job #44770](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/44770) で `early_status=1` と PASS |
| RX65N/BG96 TSIP LANBENCH TLS 1.3 resumption / 0-RTT | main merge commit `5aefbb4d`; initial confirmation in [MR !123](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/123), [#6204](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6204) | [#6469](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6469) / [#6483](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6483) / [#6485](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6485) / [#6487](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6487) / [#6489](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6489); 5回目 [job #44779](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/44779) で `early_status=1` と PASS |
| RX72N/Ether software LANBENCH TLS 1.3 resumption / 0-RTT | benchmark project `tsip_mbedtls13` main commit `fa057a02`; initial confirmation in [MR !3](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/merge_requests/3) and [MR !4](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/merge_requests/4) | [#6492](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6492) / [#6493](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6493) / [#6494](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6494) / [#6495](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6495) / [#6496](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6496); 5回目 [job #44818](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/jobs/44818) で `early_status=1` と PASS |

AWS IoT CoreとLANBENCHの最新表は
[README冒頭](#最新の実機検証性能)へ移動しました。この位置には長期証跡の索引だけを残します。

## Limitations

<details>
<summary>Click to expand</summary>

- CLI task cannot run after starting the demo (SCI conflict)
- `mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST` must be set to `1` for OTA
- LittleFS is not thread-safe; do not call its API from multiple tasks
- Custom `printf` is not thread-safe; use `configPRINTF` instead
- After Smart Configurator code generation, verify linker section addresses for dual-bank configuration
- For RX72N, LittleFS is shifted to `0x00100800` to avoid overlap with the boot loader signer-key storage

</details>

## FreeRTOS-Kernel Patch / FreeRTOS カーネルパッチ

This fork uses the upstream FreeRTOS-Kernel submodule and applies the RX72N CCRX context-restore workaround from `Common/patches/FreeRTOS-Kernel/portable/Renesas/RX700v3_DPFPU/port.c` in the e2 studio project.

本フォークでは FreeRTOS-Kernel サブモジュールは upstream 公式を参照し、RX72N/CCRX 固有のコンテキスト復帰対策だけを `Common/patches/FreeRTOS-Kernel/portable/Renesas/RX700v3_DPFPU/port.c` から e2 studio プロジェクトに組み込んでいます。

- Issue: https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/13
- Patch: https://gitlab.saffti.jp/oss/import/github/freertos/FreeRTOS-Kernel/-/merge_requests/1

## License

- Source code in `Projects/`, `Common/`, `Middleware/AWS/`, and `Middleware/FreeRTOS/` is available under the MIT License. See [LICENSE](LICENSE).
- Other libraries in `Middleware/` are available under terms specified in each source file.
- Renesas FIT Modules in `Projects/xxx/xxx/src/smc_gen/` are available under the BSD 3-Clause License. See [rx-driver-package](https://github.com/renesas/rx-driver-package) for details.

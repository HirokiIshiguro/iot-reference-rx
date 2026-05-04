# TSIP連携取り込み計画

## 目的

RX72N Envision Kit と CK-RX65N + BG96 のリファレンスアプリで、TLS backend を
ビルド時に選択できるようにする。

- software mbedTLS / PKCS #11
- TSIP連携 mbedTLS / TSIP鍵素材

ブートローダは共有のままとし、アプリケーション側だけ backend 別の e2 studio
プロジェクトに分ける。これにより、e2 studio 利用者がプロジェクト選択だけで
システム構成を把握でき、CIで `.cproject` を都度書き換える必要もなくなる。

## プロジェクト構成

アプリケーションプロジェクトは次の4種へ増やす。

| Board | Connectivity | Software TLS | TSIP TLS |
|-------|--------------|--------------|----------|
| RX72N Envision Kit | Ethernet | `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/` | `Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx/` |
| CK-RX65N V1 | BG96 cellular | `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/` | `Projects/aws_bg96_ck_rx65n_tsip/e2studio_ccrx/` |

ブートローダプロジェクトは変更しない。

- `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/`
- `Projects/boot_loader_ck_rx65n/e2studio_ccrx/`

ただし、ブートローダ実装そのものは次の共通ブートローダプロジェクトを
Git submoduleとして参照する構成へ寄せる。

`https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule`

アプリケーション側はTSIP有無で4プロジェクトへ分けるが、ブートローダは
TSIP有無では分けない。RX72N / RX65N のボード差分だけを保ち、OTA署名検証や
dual bank制御の実装は共通ブートローダsubmoduleへ集約する。

## 共通プロビジョニング方針

クレデンシャルのプロビジョニング方式は software TLS / TSIP TLS で共通化する。
どちらも、デバイス秘密情報をアプリケーションイメージへビルド時に埋め込まず、
UART CLI経由でデバイスローカルストレージへ投入する。

software TLSでは平文のAWS IoT接続情報を投入する。

- AWS IoT endpoint
- thing name
- Root CA
- client certificate
- client private key PEM

TSIP TLSでは、同じ非秘密メタデータに加えてTSIP用wrapped素材を投入する。

- AWS IoT endpoint
- thing name
- Root CA / TSIP検証に必要なRoot CA signer metadata
- client certificate
- TSIP wrapped Root CA signer public key blob
- TSIP wrapped client public key blob
- TSIP wrapped client private key blob
- デバイス上で生成したTSIP KeyIndexレコード

ホスト側スクリプトとデバイス側CLIは、可能な限り同じコマンドフローに揃える。
backendの違いは、投入するpayload形式と最後のprepare処理だけに閉じ込める。

## TSIP実装の参照元

初期実装は次のTSIPベンチマークプロジェクトをベースにする。

`https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls`

再利用する主な部品は以下。

- `Middleware/3rdparty/mbedtls_with_TSIP/` のTSIP版Mbed TLS
- `Middleware/network_transport/using_mbedtls_pkcs11_with_tsip/` のTSIP版TLS transport
- `aws_mbedtls_config_with_tsip.h`
- `Demos/key_flash_wr_with_tsip/` のTSIP鍵書き込み補助
- TSIPベンチマーク側のUART provisioning store / CLIモデル
- CIホスト側のTSIP provisioningフロー

通常版transportとTSIP版transportは同じtransport APIシンボルを提供するため、
同一アプリケーション構成へ同時リンクしない。

## CI設定

CIではsoftware TLSをデフォルトとし、TSIPは明示的なpipeline variableで選択する。
候補名は以下。

- `RX72N_TLS_BACKEND=software|tsip`
- `RX65N_BG96_TLS_BACKEND=software|tsip`

TSIP jobではwrapped provisioning blob用のmasked CI/CD Variablesを追加で要求する。
software TLS jobでは既存のAWS IoT証明書・秘密鍵変数を継続利用する。

## 初期検証範囲

最初のTSIP取り込みでは、次の順に検証する。

1. software TLS版プロジェクトが既存どおりビルド・実機テストを通る
2. TSIP版アプリケーションプロジェクトがビルドできる
3. RX72N TSIP版firmwareへUARTでprovisioningできる
4. RX72N TSIP版firmwareがTLS 1.2でAWS IoT Coreへ接続できる
5. RX72N TSIP版firmwareで既存のMQTT / OTAフローが動く
6. CK-RX65N + BG96 TSIP版は別途feasibility確認する

CK-RX65N + BG96はBG96内部TCP/IPへソケット処理を委譲するため、Ethernet版と
同じtransport切り替えだけで成立するかは実機で確認する。

## スコープ外

TSIPとTLS 1.3の連携は、この変更のスコープ外とする。今回のTSIP構成はまず
TLS 1.2 backendとして安定化させる。TLS 1.3 + TSIPは、TLS 1.2のTSIP経路が
安定した後に別issue / merge requestで扱う。

ブートローダが使用するOTA署名検証用公開鍵のプロビジョニングも、この変更の
スコープ外とする。初期実装では従来どおり公開鍵をソースコードへ埋め込む。
公開鍵をデバイスへ後段プロビジョニングする方式は、共通ブートローダsubmodule化
とTSIP連携が安定した後の将来課題として扱う。

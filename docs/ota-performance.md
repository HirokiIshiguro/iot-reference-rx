# OTAの代表性能と測定根拠

READMEのOTA値は、成功したAWS IoT MQTT OTA実機CIのUARTログから算出した単発値です。
平均値や純粋なネットワーク速度を示すものではありません。

## 測定区間

UARTログの`[+...s]`は、ホストのobserver開始からの相対受信時刻です。
下の2区間を同じobserverの時刻差で計算し、READMEでは小数第2位に丸めます。

| 指標 | 起点 | 終点 | 含む処理 |
|---|---|---|---|
| ダウンロード | `Starting The Download.` | `Close file event Received` | MQTT転送と受信データのflash書込み |
| 更新確定まで | 同上 | `New image has higher version than current image, accepted!` | 上記、署名検査、bank切替・再起動、新版起動後の受入れ |

ビルド、初期書込み、provision、AWS job作成、ダウンロード前の接続待ち、cleanupは区間外です。
UARTのバッファリング・ホストの読取り周期を含む観測時間で、MCU内の高精度タイマ測定ではありません。
payloadはUARTの`fileSize=...`またはCI packagerの`rtos-ota-payload`のbyte数を使い、partition容量やブロック数から推定しません。

## 固定ログからの算出値

| ターゲット / 構成 | payload (B) | 開始 (s) | close (s) | accepted (s) | 差分: download / accepted (s) |
|---|---:|---:|---:|---:|---:|
| RX72N Ethernet / software TLS 1.2 | 1,834,496 | 24.621 | 48.302 | 99.734 | 23.681 / 75.113 |
| RX671 Type 1YN / software TLS 1.2 | 785,920 | 42.494 | 62.945 | 95.618 | 20.451 / 53.124 |
| RX65N BG96 / software TLS 1.2 | 785,920 | 49.839 | 193.352 | 254.796 | 143.513 / 204.957 |

RX72Nの測定は[release pipeline #11140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140)の
[job #70280](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70280)（2026-09-01、success）です。
source SHAは[`26f09adfa3ae74dafc260d814f7dba03dfd58546`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/commit/26f09adfa3ae74dafc260d814f7dba03dfd58546)。
同じログでTLS 1.2の接続とApplication version 0.9.2 → 0.9.3の起動を確認しました。

RX65Nも同じrelease pipeline / source SHAの[job #70279](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70279)（success）です。
trace末尾のsummary JSONに記録された`download_started` / `close_file` / `image_accepted`の`seen_at`を使い、TLS 1.2の接続もログで確認しました。
payloadは同pipelineの[build job #70273](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70273)の`format=rtos-ota-payload, size=785920`で確認しました。
署名付きRSUファイル全体の786,432 bytesとは区別しています。

RX671は[pipeline #9733](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9733)の
[job #62156](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/62156)（success）です。
source SHAは[`11fc797f034c34faf295f7db6352736230da5223`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/commit/11fc797f034c34faf295f7db6352736230da5223)。
保存済みの`ota_summary.json` / `ota_uart_raw.log`でTLS 1.2、`fileSize=785920`（block size 4,096 bytes）、Application version 0.1.0 → 0.1.1を確認しました。
期限切れのartifact全体は再公開せず、公開用の時刻・payload・job情報だけを別途保存します。

## 適用範囲

ターゲットごとのpayload・媒体・firmware・測定日が異なるため、媒体間の速度比較には使いません。
成功したOTAの実行時間とIDTの合格は別の指標です。[IDT結果](idt-validation.md)を参照してください。
TSIP構成の時間は未測定です。

# RX72N EthernetのIDT検証

RX72N Envision Kitのsoftware TLSで、**IDT `FullTransportInterfaceTLS`の14件すべてが実機PASS**しました。
ただし、現行のFreeRTOS `202604.00-LTS`はIDT 4.9.0の版照合に通らず、**全IDT合格・リリース要件充足ではありません**。
通常CIにはIDTを追加せず、明示したパイプラインだけで実行します。

## 実行するコンピュータ

| 場所 | 役割 |
|---|---|
| ishiguro-pc / Windows | IDT版照合、CC-RXによるテストfirmwareのビルド |
| ishiguro-pc / Ubuntu WSL（x86_64） | IDT TLS suite、UART用PTY、AWS試験制御 |
| RPi #1 | RX72NへのRFP書込み、CN6 / SCI7 UART転送、共有ベンチlock |
| RX72N Envision Kit / Ethernet | production software TLS transportとupstream試験コードの実行 |
| AWS / ap-northeast-1 | IDTが作成するEC2 TLS echo server |

IDTの配布Linux実行ファイルはx86_64用です。RPiのARM64上では直接動かさず、既存CIと同じRPi #1を実機接続係にします。
接続個体とツールの正本は[hardware-config](https://gitlab.saffti.jp/oss/infra/hardware-config)です。

## 明示実行

GitLabのRun pipelineまたはPipelines APIで、次の引数を指定します。

| 引数 | 値・意味 |
|---|---|
| `RUN_RX72N_IDT` | `true`の場合だけ専用jobを作成。既定は`false` |
| `RX72N_IDT_SCOPE` | `preflight`（既定）は版照合のみ、`transport`は実機TLS通信14件 |

IDT用引数と既存のboard build / hardware / OTA / nightly引数は同時指定しません。
web / API以外のpush、MR、main更新、schedule、tag作成ではIDT jobを生成しません。
CIはWindowsのAWS / CC-RX runnerで[run_idt.py](../tools/idt/run_idt.py)を実行します。
ホストの前提はUbuntu WSL、PowerShell 7、Windows OpenSSHの`rpi1` alias、CC-RX / e2 studio、AWS権限です。
build callbackは`C:\Program Files\PowerShell\7\pwsh.exe`を使用します。別配置の場合のみ`RX72N_IDT_POWERSHELL`で指定します。
Windows PowerShell 5.1ではe2 studio終了コードが取得できない事象を確認したため、使用しません。
Pythonの`boto3`、`requests`、`cryptography`と、WSL側のPython `cryptography`を使用します。

IDT本体が未配置なら、[AWS公式の署名付きダウンロードAPI](https://docs.aws.amazon.com/freertos/latest/userguide/idt-programmatic-download-process.html)から固定版を取得します。
ドキュメントのWindows ZIPリンクは調査時に403でしたが、このAPIでは4.9.0を取得できました。

## 判定と証跡

IDT 4.9.0は試験不合格でもプロセス終了コード0を返しました。
[結果判定](../tools/idt/check_idt_report.py)では、JUnitに必須groupと1件以上のtestcaseが存在し、件数が整合し、failure / error / skipped / disabledがすべて0であることを確認します。
`preflight`または`transport`の合格は選択したgroupだけの結果であり、全IDT合格にはしません。

公開するCI artifactは、診断本文を除いた`FRQ_Report.xml`、`summary.json`、`metadata.json`だけです。
試験用秘密鍵、証明書を注入したソース、firmware、元のIDTログは、アクセスを制限したrunnerの一時ディレクトリに保持し、公開artifactに含めません。
ビルド時には元checkoutのSHA・試験ライブラリSHA・dirty状態をprovenanceとして渡し、IDTのソースコピー内で壊れる`.git`相対参照には依存しません。

## 実測結果

2026-09-27の初回検証結果です。

| 試験 | 結果 | 確認できた範囲 |
|---|---|---|
| IDT起動 | PASS | Windows / WSLで4.9.0、FRQ_2.5.0を確認 |
| `FreeRTOS_Version` | ERROR | `202604.00-LTS`はIDT 4.9.0の対応対象外 |
| `Library_Version` | FAIL | 通常ライブラリの版は一致。試験ライブラリ202406.00との対応表に202604.00-LTSなし |
| `FullTransportInterfaceTLS` | **14 PASS / 0 FAIL / 0 ERROR / 0 SKIP** | NULL引数、送受信、2接続での並行通信、切断、受信再試行。TLS 1.3で実通信 |
| MQTT / PKCS11 / Device Advisor / OTA PAL / OTA E2E | 未検証 | 今回の専用buildには含めていません |

[初回TLS試験のJUnit](https://gitlab.saffti.jp/-/project/38/uploads/24dd240b620cd68e6fba073c5054ce3a/rx72n-idt-transport-20260927.xml)は14件PASSです。
実行IDは`e505d98f-ba30-11f1-8ef5-00155d6b17e6`、IDT所要時間は9分8秒でした。
main `5f8dd55733816533537ae5613b2d0ec39473858c`に実装中の差分を加えた試作で、`source_tree_dirty=true`です。
この初回証跡をリリースタグの対象SHAに一致する証跡として流用してはいけません。
app MOTのSHA-256は`87c515d96fe2e07dc0671261fbe66083da7c79933839d47114d23e39ecb0e851`でした。

試験終了時はRFPのリセット保持操作が成功し、UARTを1秒観測して0 bytesを確認しました。
試験用EC2は`terminated`、専用security groupとkeypairはAWS APIで不存在を確認し、RPiの一時firmwareファイルとlock所有情報も削除しました。
RX72Nには試験firmwareが残るため、通常運用へ戻す際は既存のflash / provision CIで通常firmwareと認証情報を再設定します。

## 残る制約

- [AWSの対応版](https://docs.aws.amazon.com/freertos/latest/userguide/dev-test-versions-afr.html)と実CLIは202210-LTSまでを示しています。版を偽装したり、mainを古いLTSへ戻したりはしていません。
- 試験ライブラリ202406.00のMQTT試験はcoreMQTT 5とAPI・callback・再送制御が異なり、追加の移植が必要です。
- TLS groupは一時host生成EC鍵をimportする開発用構成です。IDTへ公開鍵を渡し、発行されたclient証明書と秘密鍵の一致を必ず検査します。オンボード鍵生成の認定実績ではありません。
- [AWSの正式認定](https://docs.aws.amazon.com/freertos/latest/qualificationguide/freertos-qualification.html)と、本フォークの機能検証を区別します。リリース前の必須試験範囲を満たすまではREADMEのタグ保留方針を維持します。

portとbuildの詳細は[Test/ports](../Test/ports/README.md)、通常CIは[CI/CD運用](ci-pipeline.md)を参照してください。

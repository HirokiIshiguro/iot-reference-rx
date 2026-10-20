# CI/CD運用

本リポジトリのCIは、WindowsでCC-RXビルドとAWS操作を行い、Raspberry Piに接続した
実機でflash、UART監視、MQTT、OTA、Fleet Provisioningを検証します。
job定義の正本は[`.gitlab-ci.yml`](../.gitlab-ci.yml)、接続構成とツールの現行値は
[hardware-config](https://gitlab.saffti.jp/oss/infra/hardware-config)です。

## 実機環境

| ID | 実機 | 接続 | Runner |
|---|---|---|---|
| `rx72n_ether` | RX72N Envision Kit | Ethernet | RPi #1 |
| `rx65n_bg96` | CK-RX65N V1 + BG96 | Cellular | RPi #3 |
| `rx671_wifi` | EK-RX671 + Type 1YN | Wi-Fi / SDIO | RPi #1 |

## Pipeline profile

| Profile | 起動元 | 用途 |
|---|---|---|
| `branch` | feature push | buildのみ |
| `mr` | merge request | RX72N / RX65Nの代表MQTT実機確認 |
| `mr-rx671` | RX671関連MR | RX671 network実機確認 |
| `main` | default branch push | RX72N / RX65N MQTTとRX671 network smoke |
| `release` | tag | RX72N / RX65N software TLS regressionとRX671 network smoke |
| `focused` | manual / API | 指定したターゲット・機能だけを実行 |
| `idt` | web / APIで明示指定 | RX72NのIDT版照合、または開発用TLS通信試験 |
| `nightly_matrix` | schedule | 複数projectを含む重い回帰matrix |

## Focused pipelineの主な変数

| 目的 | 変数 |
|---|---|
| ターゲット別scope | `RX72N_TEST_SCOPE` / `RX65N_BG96_TEST_SCOPE` / `RX671_WIFI_TEST_SCOPE` |
| scope値 | `build` / `network` / `mqtt` / `ota` / `fleet` / `tls13_0rtt` / `full`（対象別） |
| TLS backend | `RX72N_TLS_BACKEND` / `RX65N_BG96_TLS_BACKEND` = `software`または`tsip` |
| TLS version gate | `*_REQUIRE_TLS_VERSION=TLSv1.3` |

未指定ターゲットは`build`へ明示的に絞ってください。秘密情報の値はpipeline引数やjob logへ
直接書かず、project CI/CD Variablesを使用します。

RX65Nの旧`flash`／`download`／`app`／`provision` scopeは廃止しました。指定すると実機jobを起動せず、説明付きのエラーになります。`mqtt`／`ota`／`tls13_0rtt`の各試験jobは、同じbench lock内で公開鍵投入・dual boot・署名付きapp導入・APN／証明書投入から観測までを一括実行します。`full`は従来どおりOTAとFleetを対象にします。

Fleetも3環境とも試験job内で署名付きの専用appを一括導入し、資格情報を投入してから観測します。RX72NのTLS 1.3 0-RTT試験も同じ導入経路を使います。RX671 Fleetはclaim資格情報をfirmwareに含むため、一括導入bundle全体を暗号化して受け渡し、RPiのcheckout外に作る専用一時領域だけで復号します。終了時は同じbench lock内で通常appへ復元し、復元に成功してから一時領域を削除します。所有権が残留している場合や復元に失敗した場合は再書込み・削除を停止し、復旧用の一時領域と失敗記録を残します。

RX671 Fleetの時間上限は全体3時間、主処理140分、`after_script`の復元30分です。復元時のbench lock待ちは60秒で打ち切り、一括導入の共通時間予算を別に確保します。[GitLabの時間上限設定](https://docs.gitlab.com/ci/runners/configure_runners/#set-script-and-after_script-timeouts)に従い、主処理と復元の合計をjob全体の上限より短くしています。

IDTは通常の`full`やnightlyには含めません。専用引数・対応範囲・証跡の扱いは[IDT検証](idt-validation.md)を参照してください。

共通基盤MRのbuild-only profileでは、RX72Nの通常software appに加え、通常TSIP appも専用jobでビルドします。TSIP側のdescriptor・buffer変更後のリンク容量を確認するため、MAPもartifactへ保存します。実機scopeは追加しません。

## CC-RXのビルド並列数

RX65N・RX72N・RX671のE2 studio projectは、`parallelBuildOn=true`と
`parallelizationNumber=optimal`で実行環境に応じた並列数を選びます。
通常RX65NとBG96 OTA候補の直接Makeも、実行環境の論理CPU数を取得して
具体的な`-jN`を指定します。CPU数を取得できない場合の下限は1です。
normal package、OTA、Fleetの派生profileは元projectの並列設定を引き継ぎます。

これは1ジョブ内のcompiler並列化です。Windows host lease、`resource_group`、
ジョブ専用workspaceによるビルドジョブ間の排他は維持します。
並列数を増やした場合の短縮率はprojectによって異なるため、全体の所要時間は別に測定します。

## ビルド失敗時の扱い

e2studio-cliの異常終了、CC-RXのC／E／F診断、予期しないproject入力の追加・削除・変更を検出したら停止します。呼出側が宣言した必要出力について、欠落・空・当該build開始前の古いファイルも拒否します。W／M診断だけでは失敗にしません。

RX671では、失敗後の救済make、強制再試行、生成変更を復元した後に再buildして成功扱いにする経路を廃止しました。ビルド前に意図して適用した一時profileは入力検査の基準に含め、終了時のfinallyで元に戻します。入力変更の診断はpathと変更前後のSHA-256を残し、header本文や秘密値はlogへ出しません。

RX65Nの通常appにある、CLI成功後のリンカ設定調整と明示makeは予定された二段階処理です。CLI失敗後には進みません。native IDTの専用CDT経路も維持します。

## 実機とAWSの安全境界

- feature pushはbuild-onlyとし、実機jobをMR / main / tag / focused / scheduleへ集約します。
- RX72NとRX671はcross-project lockを使用し、flashからtestまでの割り込みを防ぎます。
- OTA / Fleetはpipeline専用Thing、certificate、policy、Job、Stream、S3 prefixを使用します。
- cleanup jobは成功・失敗にかかわらず実行し、pipeline専用AWS資源の不存在をartifactへ記録します。
- one-shot OTA observer jobだけをretryしません。再検証は新しいpipelineで作成からcleanupまで一巡させます。
- 実機操作後はRunner、UART、lock、firmware、AWS資源の終了状態を確認します。

## Schedule #5

| 項目 | 現在値 |
|---|---|
| 名前 | Nightly focused test matrix |
| 状態 | **Inactive** |
| 時刻 | 02:20 JST（active時） |
| ref | `main` |
| 変数 | `PIPELINE_PROFILE=nightly_matrix` / `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true` |

Schedule再開、変数変更、追加playはMaintainer / Ownerの承認後に行います。

## 代表証跡

- release tag pipeline: [#11140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140)
- RX671 fixed-SHA 5-run campaign: [Issue #140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/140)
- 機能別の代表pipeline: [validation-evidence.md](validation-evidence.md)

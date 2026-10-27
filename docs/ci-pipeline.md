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
| `idt` | web / APIで明示指定 | 選択した1ターゲットのnative IDT |
| `nightly_matrix` | schedule / web / API | 50回帰rowと3ターゲットのIDT TLS transport |

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

通常の`full`はIDTを含みません。nightlyは50回帰rowの完了後に、3ターゲットの`IDT_SCOPE=transport`を実行します。既存のCC-RX resource groupと実機lockで直列化し、各native結果と終了状態を判定します。これは全IDT認定ではありません。専用引数・対応範囲・証跡の扱いは[IDT検証](idt-validation.md)を参照してください。

nightlyのRX72N MQTT 4構成では、`NIGHTLY_RX72N_MULTI_TLS_TEST=true`（既定）を子pipelineへ渡し、通常MQTTの後に複数TLS接続を検証します。`false`で狙った実験から除外できますが、完全回帰の合格には含めません。focusedの`RUN_RX72N_MULTI_TLS_TEST`は従来どおり既定`false`です。

共通基盤MRのbuild-only profileでは、RX72Nの通常software appに加え、通常TSIP appも専用jobでビルドします。TSIP側のdescriptor・buffer変更後のリンク容量を確認するため、MAPもartifactへ保存します。実機scopeは追加しません。

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
今回承認された単発検証でも定期実行はInactiveを維持します。成功判定は必要な50回帰rowと3つのIDT transportの実jobを確認し、未生成・未実行・skipを合格へ数えません。build・cleanupなどの補助jobは別に確認します。

全50行を実行するには`NIGHTLY_MATRIX_INCLUDE_STABILIZING=true`が必要です。親bridgeのsuccessだけでなく、各子pipelineに必要な実機jobが生成され、実行SHAと成功が一致することを確認します。IDTは各ターゲットで必須14ケースすべての成功、複数TLS接続は上記4構成で実行件数が0件ではないことを確認します。

タグ・リリースは、対象main SHAの全必須jobと所有AWS資源の後始末が成功し、各実機の通常FWへの復帰と、その後のreset／UART静止を別々に確認した後に行います。未実行・skip・manual・cancel・許容された失敗を合格に数えません。リリースには子projectのSHAと`IDT_SCOPE=transport`／`qualification=not-established`を記載し、全IDT認定と区別します。タグ時の既存release profileも維持します。

LANBENCH用EC2とRX72N／RX65N Fleetのcleanupも、失敗を許容しません。成功・失敗にかかわらず後始末を実行する既存の条件は維持します。
自動EC2対向はproject／pipeline／作成jobと実行IDを記録し、同じ記録・client token・AWSタグを照合して終了します。記録が欠けたときに同名のinstanceを探して停止しません。既存の設定済みsecurity groupは検証して読み取り専用で利用し、新規作成したものだけを同じ所有記録で後始末します。

## 代表証跡

- release tag pipeline: [#11140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140)
- RX671 fixed-SHA 5-run campaign: [Issue #140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/140)
- 機能別の代表pipeline: [validation-evidence.md](validation-evidence.md)

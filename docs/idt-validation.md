# RX72N EthernetのIDT検証

## 3ターゲットのCI入口

GitLabのRun pipeline / Pipelines APIで、次の3入力を指定します。

| 入力 | 値 |
|---|---|
| `RUN_RX_IDT` | `true`（既定は`false`） |
| `IDT_TARGET` | `rx72n-ethernet` / `rx65n-bg96` / `rx671-wifi` |
| `IDT_SCOPE` | `plan` / `preflight` / `transport` / `mqtt` / `pkcs11` / `ota-pal` / `ota-mqtt` |

選択した1ターゲットだけのnative jobを生成し、通常のboard / OTA / nightly jobは起動しません。
RX72Nの旧入力`RUN_RX72N_IDT=true` / `RX72N_IDT_SCOPE`も保持します。新旧入力を同時に指定した場合は新入力を優先します。
任意のOTA case選択は`IDT_TEST_ID`（旧`RX72N_IDT_TEST_ID`も可）で指定します。

| ターゲット | native job | MCU側の接続 |
|---|---|---|
| `rx72n-ethernet` | `test_rx72n_idt` | RX72N Envision Kit Ethernet、RPi #1 |
| `rx65n-bg96` | `test_rx65n_bg96_idt` | CK-RX65N V1 / BG96、RPi #3 |
| `rx671-wifi` | `test_rx671_wifi_idt` | EK-RX671 / Type 1YN Wi-Fi、RPi #1 |

同じWindows / WSL / CC-RX / AWSホストを使い、host preflightは選択したRPiのhostnameを確認します。
共有ホスト設定は既存の`RX72N_IDT_RUNNER_TAG` / `RX72N_IDT_PYTHON` / `RX72N_IDT_HOST_PROFILE`を継承します。
Wi-Fi / APNは既存のターゲット専用CI変数からprivate runtimeへ渡し、source・firmware・値を公開artifactに含めません。

`plan`はホストの版・依存と固定されたboard identityを計画へ記録するだけで、AWS、compiler、UART、flashを操作しません。
`preflight`はnative `FreeRTOSVersion`を実行します。FreeRTOS `202604.00-LTS`とIDT 4.9.0 / FRQ_2.5.0の不一致はNGとして保持し、環境整備の失敗と区別します。
MQTTもRX72N/RX671のcoreMQTT 5.0.2（MQTT 5）がsuiteのMQTT 3.1.1期待値と不一致です。RX65N/BG96はcoreMQTT 2.3.1（MQTT 3.1.1）ですが、protocol一致だけではnative合格とは判断しません。
失敗・ERROR・SKIPをPASSへ書き換えず、LTS / manifest / vendor suiteを変更しません。

MRの`idt_ci_contract`は共有host・target・終了処理・報告の単体検査、`idt_target_plans`は3ターゲットの計画を保存します。
`idt_source_matrix`はWindows runnerで3ターゲット×5groupの実project/source URI・依存pin・metadata復元を確認します。続いて3ターゲットのTransportをplaceholderのみでcompile/linkします。実機・native試験は実行せず、生成imageは書き込めません。
過去のローカル15構成compile成功は保存されたsourceに対する結果として保持し、このMRのclean SHA・runner・実機の合格へ流用しません。

### 実機scopeの準備条件

固定target identityがapplication、bootloader、packager、UART、debugger、bench lockを選びます。
共有CC-RX resource groupに加え、実機の既存lockと通常CIとの排他を確認します。
RX671の初期secure bootは、同じsourceで確認したlinear provisionerと対応するP-256公開signerをLittleFSへ用意し、Data Flashを保持して両bankへ書き込みます。built-in fallbackは有効にしません。
OTAのbuild ledger / 起動witnessはターゲットとfingerprintを照合します。通常firmwareの復帰は既存flash / provision経路で確認します。

終了時は既存RX72N CIと同じresetコマンド成功と、freshな1秒間のUART静止を確認します。
RESET端子の電圧測定は実行条件に含めません。物理RESET Lowを測定したという記録は作りません。
reset失敗、UART出力継続、privileged子processの終了が不明な場合は不合格とし、所有記録を保持して再利用を止めます。
これは全IDT合格の条件緩和ではなく、終了時に実際に観測できる事実の記録です。

## RX72Nの既存実測

以下はそれぞれに記載された過去SHAの結果です。今回の追加2ターゲットや変更後sourceの合格として扱いません。

RX72N Envision Kit / Ethernet / software TLSで、**TLS transportの14件が実機PASS**しました。
OTA E2Eの**新しいバージョンへの更新と、1.9.1 → 1.9.2の起動識別子を、clean SHA `c9fcadb1`の実機CIで確認**しました。
同版・非信頼証明書の試験もclean SHA `2e0c7a5b`でPASSしましたが、全13ケースは未完了です。
MQTTのnative IDT試験は完走しましたが、IDT側のMQTT 3.1.1期待値と本実装のMQTT 5が一致せず、6件がFAILです。
FreeRTOS `202604.00-LTS`の版照合も不合格で、**全IDT合格・リリース要件充足には達していません**。
新規リリースタグの保留方針を維持し、IDTは明示したパイプラインだけで実行します。

## 試験範囲と現在の結果

2026-09-28時点。IDT 4.9.0 / FRQ_2.5.0を使用しています。

| `RX72N_IDT_SCOPE` | native IDT group | 結果・確認範囲 |
|---|---|---|
| `preflight`（既定） | `FreeRTOSVersion` | Version ERROR / Library FAIL。202604.00-LTS未対応 |
| `transport` | `FullTransportInterfaceTLS` | **14/14 PASS**。[clean SHAのpipeline #11247](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11247)で確認 |
| `mqtt` | `FullCloudIoT` | native MQTT03: 10件完走、TLS 3 PASS・cipher 1 PASS_WITH_WARNINGS・MQTT 6 FAIL |
| `pkcs11` | `FullPKCS11_Core` | **10件PASS / 0 FAIL / 0 ERROR / 0 SKIP**。capabilities、digest、random、初期化 / session |
| `ota-pal` | `OTACore` | **14件のassertion PASS**、filesystem専用1件はIGNORE。native IDTはこのIGNOREをFAILと記録し、全体NG |
| `ota-mqtt` | `OTADataplaneMQTT` | **GreaterVersion、SameVersion、UntrustedCertificateの3ケースPASS**。GreaterVersionは独立した起動判定もPASS。全13ケースは未完了。SHAと証跡は以下を参照 |

TLSの確定証跡は[`9cadbfeb0a10a51a1f2953127346a58bd38805bf`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/commit/9cadbfeb0a10a51a1f2953127346a58bd38805bf)のclean checkoutによるものです。
他のscopeや対象SHAに、この14件の合格を流用しません。
PKCS11 Coreの10件は基本APIの結果です。ECC object / signを検査する別group `FullPKCS11_Import_ECC`は未実行です。
この10件の後でlabel設定をproductionと同じ`pkcs11configLABEL_*`参照へ統一しました。この変更後の実機再試験は未実施です。
PKCS11試験終了時はreset保持成功とUART 0 bytesを確認しました。

[MQTT03の証跡](https://gitlab.saffti.jp/-/project/38/uploads/de289e072658138a255bf5a54a1062b2/pilot-mqtt-03-sanitized-evidence.zip)と
[PKCS11 Coreの証跡](https://gitlab.saffti.jp/-/project/38/uploads/814c9055ccc191fa8b63cabb5bdc564c/pilot-pkcs11-02-sanitized-evidence.zip)は、
main `0dc57833`に実装中の差分を加えた試作の結果（`source_dirty=true`）です。リリース対象SHAの証跡には流用しません。
[OTA PALの証跡](https://gitlab.saffti.jp/-/project/38/uploads/c40a51ac23d6972d57beb71b3d924dbb/pilot-otapal-01-sanitized-evidence.zip)では、
実機Unity出力が`15 Tests 0 Failures 1 Ignored`、native JUnitが14 PASS / 1 FAILでした。これも`source_dirty=true`の試作結果です。署名検証、異常署名拒否、inactive bankへの書込み・状態APIのassertionを確認し、終了時のreset保持とUART 0 bytesも確認しました。

**OTA E2E（最新）:** [job #70703](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70703)は未変更の`c9fcadb1d733e7116d6641661c3e94fe25264c78`で、native 3 PASS / 0 FAIL / 0 ERROR / 0 SKIPでした。UARTで初期image `3b0a915e…`（1.9.1）→更新image `5cedbf7d…`（1.9.2）を順に確認し、`native_junit_passed=true`と`ota_boot_verified=true`を別々に記録しています。各imageはbuild ledgerのpayload hash・source SHAと一致します。
IDT終了時はreset保持 / UART 1秒0 bytesでした。AWS APIでもThing / job / OTA update / S3 bucketの不存在、実行時間帯のIDT用IAM role / policyと一致証明書の残存0、一時ACM証明書2件の不存在を確認しました。

[#11262・#11264・#11265のsanitized証跡](https://gitlab.saffti.jp/-/project/38/uploads/539031949e04d575e3cc0e0ef84248ee/idt-ota-witness-11262-11265-sanitized-evidence.zip)は公開用JSON/XMLと説明だけを含みます。SHA-256は`2ba4766587b60b504a79021369df84bcc530bbd7b221b9ddf5d216e69cc4e3ba`です。raw UART、注入済みsource/firmware、秘密鍵は含めていません。

**OTA E2E（同版・非信頼証明書）:** clean SHA `2e0c7a5bd6d990d364f20ccb7d7691f874d60689`の[pipeline #11272](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11272)は、setup / SameVersion / UntrustedCertificate / cleanupの4件がPASSしました。
同版では同一imageの1.9.1 → 1.9.1、非信頼証明書では署名検証エラーと1.9.1の維持を実機で確認し、両ケースのAWS jobは期待どおり`FAILED`でした。
新版1.9.2は起動していません。これらの起動観測はGreaterVersion単独実行の必須gateとは区別します。
[sanitized証跡](https://gitlab.saffti.jp/-/project/38/uploads/53441e5d51c146715b283e80c9f3c628/idt-ota-negative-11272-sanitized-evidence.zip)のSHA-256は`4767ee5ae6a8ca333aae0ce72458aac99a8105835da03e84a5e4f236163892a2`です。
GreaterVersionの`c9fcadb1`と異なるSHAの部分試験であり、合算してリリース対象SHAの全IDT合格にはしません。

**異常系の途中結果:** 同じ`c9fcadb1`の[pipeline #11265](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11265)は、PreviousVersion → SameVersion → UntrustedCertificateの選択実行中に停止しました。

| case | 確認結果 |
|---|---|
| PreviousVersion | 実機で1.9.1 → 1.9.0の起動と、AWS jobの`FAILED`を確認。このcase内で1.9.1への自律復帰は未観測 |
| SameVersion | 初期firmwareのUART書込みでconst data 7/28KBまで進んだ後、bootloaderが`system error`。試験成立に至らず |
| UntrustedCertificate | このrunでは未実行 |

nativeは失敗したflash callbackの後も試験を継続しました。所有するsupervisorへ停止を要求したところ、IDTのCancel処理がnil-pointer panicで終了し、最終JUnitは生成されませんでした。従ってこのrunを合格件数に加えません。MCUはreset保持 / UART 1秒0 bytesで停止しました。CloudTrail作成履歴、IAMの不変ID・専用参照、試験用公開鍵との一致を確認して残存資源を回収し、Thing・証明書・S3 bucket・IAM role/policy等の残存0をAPIで確認しています。
UART downloaderはCRの進捗行とCRLFのエラー行を個別に扱い、`R_FLASH_*`エラーや`system error`を即時不合格にします。flash callbackの失敗もprivate runtimeへ保持し、nativeが無視してもsupervisorが停止・不合格にするようにしています。これはconst-data書込み不具合や旧版rollback自体を修正したものではありません。
旧版拒否・自律rollbackの設計と実機検証は[Issue #158](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/158)で追跡します。

残る2ケースを指定した#11267は、native開始前のACM準備でWindowsの記録ファイル保存が`PermissionError`となり停止しました。ready状態の一時ファイルが残り、同じ権限で後処理時の保存は成功したため、一時的な置換拒否が疑われます。MCU書込みは行わず、ACM証明書2件は削除しました。対策としてWindowsの該当エラーだけ、同じ一時ファイルの置換を最大5回・合計0.75秒の待ち時間で試みます。AWS importや実機試験は再試行せず、恒久的な拒否は不合格のまま記録を保持します。

**OTA E2E（旧記録）:** [job #70643](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70643)は未変更の`97e6c070bd51aa11f0a93cc3d4fbf50070554e01`で実行し、1.9.1と1.9.2のpayload（各1,834,496 bytes）を生成しました。
nativeはAWS OTAジョブの`SUCCEEDED`を確認し、JUnitは3 PASS / 0 FAIL / 0 ERROR / 0 SKIPです。これは1つの更新ケースとsetup / cleanupの結果で、3種類の更新試験やgroup全体の合格を意味しません。
[sanitized証跡](https://gitlab.saffti.jp/-/project/38/uploads/ebf169ff93dc2c741d3c88467abc937c/ota-greater-version-11255-sanitized-evidence.zip)のSHA-256は`681ab46a68bae10d77a49cd684a2e4fb463f58d20acebad4e70c88f954b70b60`です。payload hashと版数はmetadataに保持しています。
bankの整合性検査・切替ログは得られましたが、更新後の`Application version 1.9.2`というUARTバナーはこのcaptureでは得られていません。nativeのPASSと、独立した起動版確認を区別します。
IDT終了時はreset保持 / UART 0 bytes、AWSのThing / job / OTA updateの不存在、公開鍵が一致する証明書0件、一時ACM証明書2件削除を確認しました。その後、通常MR CIのjob #70641が通常firmwareを再書込み・provisionし、MQTT試験に成功しています。

<details>
<summary>OTA認証情報の接続方法と立上げ時の切り分け</summary>

OTA setupでは`KeyProvisioning=Import`、ECC公開鍵を設定しても、対象ThingのprincipalはACTIVEなRSA証明書でした。
既存EC証明書を指定する診断でも同じ不一致になったため、この追加証明書を作る試作コードは採用していません。
その後、OTAスコープだけnativeの`KeyProvisioning=Onboard`で公開鍵を渡すと、ACTIVEなEC証明書1件と試験用秘密鍵の一致を確認できました。
これはホスト生成鍵を試験firmwareへimportする開発用の接続方法です。マイコン上の鍵生成・secure elementの認定試験結果には扱いません。PKCS11スコープは`Import`のままです。
証明書と秘密鍵の一致検査は維持し、診断だけでは更新成功・署名検証成功・復帰成功の証跡には扱いません。
各試行の一時ACM証明書2件と、既存証明書指定の診断用IoT証明書は削除を確認しました。
19:05頃の診断中にはRPi #1へのSSH接続も切れ、native cleanupがERRORになりました。CloudTrailで所有を確認して残存資源を回収しました。[診断・回収証跡](https://gitlab.saffti.jp/-/project/38/uploads/3902f283dfdc894cfc895060ce5d4d7e/ota-setup-sanitized-evidence.zip)はこの失敗を維持しています。
再接続後のreset操作は成功しましたが、直後のUART2 bytesで静止検査はNGでした。その後、共有lock下の観測で3秒連続0 bytesを確認しました。

</details>

## 明示実行

GitLabのRun pipelineまたはPipelines APIで、`RUN_RX72N_IDT=true`と上表の`RX72N_IDT_SCOPE`を指定します。
`RUN_RX72N_IDT`の既定は`false`です。
IDT用引数と既存のboard build / hardware / OTA / nightly引数は同時指定しません。
通常のpush、MR、main更新、schedule、tag作成ではIDT jobを生成しません。

<details>
<summary>OTAケースの選択と起動版の確認</summary>

`RX72N_IDT_SCOPE=ota-mqtt`に限り、`RX72N_IDT_TEST_ID=OTAE2EGreaterVersion`で単一caseを選べます。
カンマ区切りで複数caseを選べます。例えば`OTAE2ESameVersion,OTAE2EPreviousVersion,OTAE2EUntrustedCertificate`です。空要素、重複、固定suiteにないcaseは実行前に拒否します。
通常は指定せず、選択group全体を実行します。
選択caseは`metadata.json`と`summary.json`の`selected_test_ids`に部分実行として記録し、group全体の合格には扱いません。
OTA imageごとに異なる識別子を埋め込み、実起動時に`[IDT_BOOT] image=... version=...`を出力します。build ledgerで識別子・コンパイル版・payload hash・source SHAを対応付けます。
GreaterVersion単独実行では、native JUnitの合格に加え、初期imageと新版imageの起動を順に観測することを追加条件にします。`native_junit_passed`と`ota_boot_verified`は別々に保存し、起動証跡が欠けた場合はjobを不合格にします。native JUnit自体は書き換えません。
この追加条件を導入した[pipeline #11262](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11262)ではnative 3件PASSでも新版のUART起動情報がなく、jobを不合格にしました。実機フラッシュのreadbackは新版payloadのSHA-256と一致しましたが、これをUART起動確認の代用にはしていません。新版ではCLI案内文が途中で停止していました。IDT起動で対話CLIタスクを作らずUARTを同期初期化し、CLI削除による送信mutexの取り残しを避ける修正後、#11264で両imageの起動情報と追加判定PASSを確認しました。
他case・group全体では観測したimageを記録しますが、GreaterVersion単独と同じ起動版判定を行ったとは扱いません。
認証情報の切り分け用にlocal CLIの`--diagnostic-only`を指定すると、秘密情報を含む診断資料をprivate runtime内へ保存し、compiler / flash前に必ず停止します。これは合格試験ではなく、通常のpipeline引数には加えません。

</details>

## 運用・リリース要件

IDTは専用のパイプライン引数を明示した場合だけ実行します。
新規リリースタグの作成前に、タグ対象commit SHAの対象構成で必須試験がすべてPASSしていることを確認します。
未実行・失敗・必須試験のskip・一部試験のみの成功はOKとして扱いません。通常のMQTT / OTA CI成功もIDT合格の代用にはなりません。
自動gate整備まではOwner / Maintainerが証跡を確認し、要件を満たせない間は新規リリースタグを保留します。

証跡はcommit / submodule SHA、ボード・TLS構成、firmware hash、IDT / suite版、pipeline、reportを対応付けて保存します。
対象SHAや構成が変わった場合、以前の合格結果は流用しません。
IDTによる検証と[AWSの正式認定](https://docs.aws.amazon.com/freertos/latest/qualificationguide/freertos-qualification.html)は区別します。

実装時は動作検証を進め、通常運用ではコード変更ごとのIDT実行と無制限の自動再試行は行いません。
[OTAにはIoT Device Management、接続・MQTTにはIoT Coreの料金](https://aws.amazon.com/freertos/pricing/)が発生します。
1実行75分のhost timeoutを設け、中断・異常終了時は実機の停止と試験用AWS資源の回収を試みます。
回収・終了状態の確認に失敗した場合は不合格とし、記録を保持して個別に復旧します。
通常運用時は利用量・費用上限・停止条件を定めます。

## 実行するコンピュータ

| 場所 | 役割 |
|---|---|
| Windows x86_64（現在はishiguro-pc） | IDT版照合、CC-RXによるfirmwareビルド、AWS認証の引渡し |
| 同ホストのUbuntu WSL 2 / x86_64 | native IDT suite、UART用PTY、AWS試験制御 |
| RPi #1 | RX72NへのRFP書込み、CN6 / SCI7 UART転送、共有ベンチlock |
| RX72N Envision Kit / Ethernet | production transport、MQTT / OTA、および選択した試験コード |
| AWS / ap-northeast-1 | TLS echo server、IoT Core / Device Advisor、OTA試験資源 |

Linux版IDTはx86_64用のため、RPiのARM64上では直接動かしません。
Windowsホストはprofileとrunner設定で移設可能にし、接続個体とツールの正本は[hardware-config](https://gitlab.saffti.jp/oss/infra/hardware-config)に従います。
**既存PCの新規Windows / WSL venvでhost検査17項目PASS**を確認しました。e2 studioのproduct / release metadataとCC-RXの版も照合しています。新規PCでの再構築・実機完走は未検証です。

<details>
<summary>ホストを再構築する手順と固定版の検査</summary>

ホスト固有の配置は[非secret profile](../tools/idt/host-profile.example.json)で管理し、`RX72N_IDT_HOST_PROFILE`で選びます。
別PCでもworkspace規約に合わせて`C:\ai\codex`配下を使用します。任意driveへの移設を保証する構成ではありません。
Windows / WSLのPython依存は[Windows](../tools/idt/requirements-windows.txt)と[WSL](../tools/idt/requirements-wsl.txt)の固定版から専用venvへ導入します。
PowerShell 7、Windows OpenSSH、WSL 2のx86_64 Linux、Python 3.11以降、e2 studio 2026-04.2 / CC-RX 3.07.00を事前に導入してください。
検証ホストはWSL 2.6.3.0、Ubuntu 24.04.4 LTS、Linux Python 3.12.3です。
Ubuntuで`python3-venv`が未導入の場合は、別途`sudo apt-get update && sudo apt-get install python3-venv`を実行します。

```powershell
python tools/idt/setup_host.py --profile tools/idt/host-profile.example.json `
  --wsl-venv /mnt/c/ai/codex/tools/venvs/rx72n-idt-linux
$env:RX72N_IDT_HOST_PROFILE = 'C:\ai\codex\tools\venvs\rx72n-idt-windows\host-profile.json'
$idtPython = 'C:\ai\codex\tools\venvs\rx72n-idt-windows\Scripts\python.exe'
& $idtPython tools/idt/check_host.py --check-aws --output artifacts/idt-host-check.json
```

[setup_host.py](../tools/idt/setup_host.py)は専用venvとprofileを作り、OS、Renesas製品、AWS認証、SSH鍵、既存Python環境を変更しません。
[check_host.py](../tools/idt/check_host.py)は選択profileで実行ユーザー、ツール配置・版、Python依存、WSL / Linux版、SSH接続先hostnameを記録します。
`--check-aws`はread-onlyのSTS照会です。UART、flash、試験用AWS資源には触れません。
WSL、SSH、AWSはWindowsユーザーごとの設定なので、GitLab Runnerサービスの実行ユーザーでも検査します。
CC-RXライセンスとリンク可能サイズは実際のfirmwareビルドで確認します。

CIでは`RX72N_IDT_RUNNER_TAG`と`AWS_CLI_RUNNER_TAG`を配備先tagへ、`RX72N_IDT_PYTHON`を専用venvの`python.exe`へ設定します。
CC-RXのresource groupは同ホストの既存ビルドとの排他を維持します。
`RX72N_IDT_POWERSHELL`と`E2STUDIO_CLI`はprofileより優先し、buildにはPowerShell 7と`e2studioc.exe`を使用します。
Windows PowerShell 5.1はe2 studio終了コードを取得できなかったため対象外です。
ホストを変えても、RPi #1のhostname、UART by-id、E2 Lite serial、共有lockは変更しません。

IDTは[AWS公式署名付きAPI](https://docs.aws.amazon.com/freertos/latest/userguide/idt-programmatic-download-process.html)から固定版を取得します。
[manifest](../tools/idt/bundle-manifest.json)と[検証コード](../tools/idt/idt_bundle.py)でZIPのSHA-256および各OSの静的74ファイルを確認します。
公式ZIPを再取得して既知hashと照合済みです。cached binaryの存在だけでは成功にせず、追加・欠落・改変された実行ファイルや試験定義を拒否します。
可変のconfigs / logs / resultsはhash対象から除きます。
`latestidt`が別版へ更新された場合は自動で追従せず停止します。固定版を再構築する場合は、保管した公式ZIPのhashをmanifestと照合してprofileの`install_root`へ展開し、`verify_install`で検査します。
版を更新するときは公式bundleの版・suite・対応FreeRTOSを確認し、両OSのZIP hashと静的file一覧を再生成してMRでレビューし、実機scopeを再検証します。既存のPASSを新しいtoolへ流用しません。

</details>

## 判定と証跡

IDT 4.9.0は試験不合格でもプロセス終了コード0を返します。
[結果判定](../tools/idt/check_idt_report.py)は必須group、1件以上のtestcase、件数整合を確認し、failure / error / skipped / disabledのいずれかがあれば不合格とします。
実行や終了処理の失敗も合格にしません。scope単位のPASSは全IDT合格ではありません。
OTA PALのfilesystem専用IGNOREはnative IDTがFAILへ変換しました。これをPASSへ書き換えず、full groupの合格には扱いません。

公開CI artifactは、診断本文を除いた`FRQ_Report.xml`、`summary.json`、`metadata.json`だけです。
commit / submodule SHA、dirty状態、firmwareと試験設定のhash、IDT / suite版、部分実行の有無を対応付けます。
UARTはnativeへの転送前にprivate runtimeの`uart-witness/uart.bin`へ保存します。nativeの読み取り終了後もSSH出力をEOFまで回収し、末尾の起動情報を残します。公開metadataにはrawのbyte数 / SHA-256と、識別子・版数・hash等の限定した観測情報だけを載せます。
raw captureは128 MiBを上限とし、書込みエラー・上限超過は不合格にします。解析できない起動markerはカウントとして残し、native試験を途中で打ち切りません。GreaterVersion単独の追加判定では、欠落・不完全なmarkerを正常な起動証跡として扱いません。rawと`events.jsonl`はprivate runtimeと同じ保持・削除対象です。

private runtimeと`<workspace_root>\idt-private-<run>`は、失敗解析とレビューのため保持します。MRの確認後、必要なsanitized証跡を保存し、当該runのプロセス終了・AWS cleanup・実機停止を確認してから両ディレクトリを削除対象にします。自動世代削除は行わず、調査中のrunや別runを一括削除しません。
private runtime内の`diagnostic-*`資料も同じ保持・削除対象です。

試験用秘密鍵、注入済みsource / firmware、元のIDTログ、e2 studio workspaceはアクセスを制限したcheckout外の領域に保持します。
試験後は共有lockを保持したままreset保持とUART静止を確認し、試験用AWS資源とRPiの一時firmwareを片付けます。
通常運用へ戻す際は既存のflash / provision CIで通常firmwareと認証情報を再設定します。

<details>
<summary>MQTT / OTAの制約と部分結果の解釈</summary>

**MQTT:** native FRQはDevice Advisor suiteにprotocolを指定せず、定義version 1で実行します。userdataにprotocolのoverrideはありません。
MQTT03の6件はすべて`ExpectedMqttV3_1_1`に対して`MqttV5`を受けた失敗です。
MQTT 3.1.1へのdowngradeや試験経路の置換は行っていません。
TLS cipherの`PASS_WITH_WARNINGS`もそのまま保持します。
警告中の8 cipher suiteは[AWS IoTの現行対応表](https://docs.aws.amazon.com/iot/latest/developerguide/transport-security.html)にあり、`0x00FF`はSCSVです。警告を危険な暗号方式の使用確定として扱いません。

**OTA署名:** 文書化された`customSignCommand`の波括弧placeholderがnative IDTの`GetUserData`による先行展開と衝突し、その経路では試験開始に至りませんでした。
[AWS Signer用の準備・cleanup](../tools/idt/ota_aws_signers.py)を実装しています。初期のOTA02は認証情報の不一致でbuild前に停止しましたが、公開鍵の受渡し経路を修正したpipeline #11255ではGreaterVersionの単一ケースがPASSしました。署名不正・旧版・同版等を含むgroup全体は未実行です。
一時ACM証明書は実行固有のtagとjournalで所有を確認し、IDT終了・native cleanup後に削除します。

**OTA PAL:** inactive bankの実flashに対する既存assertionを実行するportです。
15 nominal caseのうち14件がassertion可能で、`otaPal_CloseFile_NonexistingCodeSignerCertificate`はfilesystem専用のためIGNOREです。
実機では14件のassertionが通り、1件がIGNOREでした。nativeがFAILとして記録したIGNOREをPASSへ置き換えません。

**版照合と認定:** [AWS対応版](https://docs.aws.amazon.com/freertos/latest/userguide/dev-test-versions-afr.html)と実CLIは202210-LTSまでを示し、現行202604.00-LTSは未対応です。
manifestの偽装や古いLTSへの巻戻しは行っていません。
[AWS正式認定](https://docs.aws.amazon.com/freertos/latest/qualificationguide/freertos-qualification.html)と、本フォークの個別機能検証は区別します。
[初期のTLS試作JUnit](https://gitlab.saffti.jp/-/project/38/uploads/24dd240b620cd68e6fba073c5054ce3a/rx72n-idt-transport-20260927.xml)は`source_tree_dirty=true`のため、clean SHAの証跡には使いません。

</details>

port / buildの詳細は[Test/ports](../Test/ports/README.md)、通常CIは[CI/CD運用](ci-pipeline.md)を参照してください。

# RX72N EthernetのIDT検証

RX72N Envision Kit / Ethernet / software TLSで、**TLS transportの14件が実機PASS**しました。
MQTTのnative IDT試験は完走しましたが、IDT側のMQTT 3.1.1期待値と本実装のMQTT 5が一致せず、6件がFAILです。
FreeRTOS `202604.00-LTS`の版照合も不合格で、**全IDT合格・リリース要件充足には達していません**。
新規リリースタグの保留方針を維持し、IDTは明示したパイプラインだけで実行します。

## 試験範囲と現在の結果

2026-09-27時点。IDT 4.9.0 / FRQ_2.5.0を使用しています。

| `RX72N_IDT_SCOPE` | native IDT group | 結果・確認範囲 |
|---|---|---|
| `preflight`（既定） | `FreeRTOSVersion` | Version ERROR / Library FAIL。202604.00-LTS未対応 |
| `transport` | `FullTransportInterfaceTLS` | **14/14 PASS**。[clean SHAのpipeline #11247](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11247)で確認 |
| `mqtt` | `FullCloudIoT` | native MQTT03: 10件完走、TLS 3 PASS・cipher 1 PASS_WITH_WARNINGS・MQTT 6 FAIL |
| `pkcs11` | `FullPKCS11_Core` | **10件PASS / 0 FAIL / 0 ERROR / 0 SKIP**。capabilities、digest、random、初期化 / session |
| `ota-pal` | `OTACore` | **14件のassertion PASS**、filesystem専用1件はIGNORE。native IDTはこのIGNOREをFAILと記録し、全体NG |
| `ota-mqtt` | `OTADataplaneMQTT` | setupの認証情報検査でERROR。nativeが生成したRSA証明書と設定したEC鍵が不一致のため、compiler / flash前に停止。実際のOTA更新は未確認 |

TLSの確定証跡は[`9cadbfeb0a10a51a1f2953127346a58bd38805bf`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/commit/9cadbfeb0a10a51a1f2953127346a58bd38805bf)のclean checkoutによるものです。
他のscopeや対象SHAに、この14件の合格を流用しません。
PKCS11 Coreの10件は基本APIの結果です。ECC object / signを検査する別group `FullPKCS11_Import_ECC`は未実行です。
PKCS11試験終了時はreset保持成功とUART 0 bytesを確認しました。

[MQTT03の証跡](https://gitlab.saffti.jp/-/project/38/uploads/de289e072658138a255bf5a54a1062b2/pilot-mqtt-03-sanitized-evidence.zip)と
[PKCS11 Coreの証跡](https://gitlab.saffti.jp/-/project/38/uploads/814c9055ccc191fa8b63cabb5bdc564c/pilot-pkcs11-02-sanitized-evidence.zip)は、
main `0dc57833`に実装中の差分を加えた試作の結果（`source_dirty=true`）です。リリース対象SHAの証跡には流用しません。
[OTA PALの証跡](https://gitlab.saffti.jp/-/project/38/uploads/c40a51ac23d6972d57beb71b3d924dbb/pilot-otapal-01-sanitized-evidence.zip)では、
実機Unity出力が`15 Tests 0 Failures 1 Ignored`、native JUnitが14 PASS / 1 FAILでした。これも`source_dirty=true`の試作結果です。署名検証、異常署名拒否、inactive bankへの書込み・状態APIのassertionを確認し、終了時のreset保持とUART 0 bytesも確認しました。

OTA setupでは`KeyProvisioning=Import`、ECC公開鍵を設定しても、対象ThingのprincipalはACTIVEなRSA証明書でした。
既存EC証明書を指定する診断でも同じ不一致になったため、この追加証明書を作る試作コードは採用していません。
証明書と秘密鍵の一致検査は維持し、更新成功・署名検証成功・復帰成功の証跡には扱いません。
各試行の一時ACM証明書2件と、既存証明書指定の診断用IoT証明書は削除を確認しました。
19:05頃の診断中にはRPi #1へのSSH接続も切れました。compiler / flash前でしたが、この試行の終了状態の確認に失敗したため、接続とベンチ状態の復旧確認後に再試験します。

## 明示実行

GitLabのRun pipelineまたはPipelines APIで、`RUN_RX72N_IDT=true`と上表の`RX72N_IDT_SCOPE`を指定します。
`RUN_RX72N_IDT`の既定は`false`です。
IDT用引数と既存のboard build / hardware / OTA / nightly引数は同時指定しません。
通常のpush、MR、main更新、schedule、tag作成ではIDT jobを生成しません。

<details>
<summary>単一OTA caseによる立上げ</summary>

`RX72N_IDT_SCOPE=ota-mqtt`に限り、`RX72N_IDT_TEST_ID=OTAE2EGreaterVersion`で単一caseを選べます。
通常は指定せず、選択group全体を実行します。
単一caseは`metadata.json`と`summary.json`に部分実行として記録し、group全体の合格には扱いません。
認証情報の切り分け用にlocal CLIの`--diagnostic-only`を指定すると、秘密情報を含む診断資料をprivate runtime内へ保存し、compiler / flash前に必ず停止します。これは合格試験ではなく、通常のpipeline引数には加えません。

</details>

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

private runtimeと`<workspace_root>\idt-private-<run>`は、失敗解析とレビューのため保持します。MRの確認後、必要なsanitized証跡を保存し、当該runのプロセス終了・AWS cleanup・実機停止を確認してから両ディレクトリを削除対象にします。自動世代削除は行わず、調査中のrunや別runを一括削除しません。
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
[AWS Signer用の準備・cleanup](../tools/idt/ota_aws_signers.py)を実装し、native OTA02で実行専用ACM証明書2件のimportと終了時の削除確認に成功しました。setup時に一致する有効なデバイス証明書を取得できず、更新用firmwareのbuild前で停止しました。OTA更新はまだ未確認です。
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

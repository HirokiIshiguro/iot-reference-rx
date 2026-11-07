# AWS OIDC移行の初期段階

まずAWSへの読取りだけでOIDCを確認する。既存IDT・OTA・benchmarkと製品リリースは別の検証段階とする。**この変更だけでは移行完了にならない。**

| 段階 | この変更の状態 |
|---|---|
| 固定/動的credentialの利用整理 | 下表。秘密値は取得しない |
| OIDC-onlyの任意profile | rootへ分離して追加。AWS上の成功は未検証 |
| CSR発行・異常終了時の回収 | 設計候補。未実装・未検証 |
| 既存経路の切替・固定キー撤去 | 未実施。利用先と回帰成功を確認後に判断 |

短い疎通の流れは `GitLab ID token → unsigned STS → identity照合 → IoT endpoint読取り`。
誤audienceと未許可refはSTSで拒否される必要がある。

人間の判断が必要な残件は、専用role/変数の設定とmain限定probeの実行時期、CSR発行/削除の権限境界、独立回収の責任者・期限・通知先である。
以下は実装・監査担当向けの根拠と未検証事項である。

<details>
<summary>既存の利用経路とアカウント境界</summary>

調査基点はmain `0d0a2457f3839c7c97ba63e018896a1a436844ab`。
project 38のCI/CD Variables 31件をGraphQL `ciVariables`でkey/type/scope/flagsのみ取得した。`value`を要求していない。groupからの継承変数・runnerのcredential fileの内容は調査していない。

| 利用経路 | 確認したsource / metadata | 移行で扱うこと |
|---|---|---|
| RX72N通常MQTT | root CIの`AWS_CLIENT_CERT_RX72N_02` / `AWS_PRIVATE_KEY_RX72N_02`、`tools/build_headless_rx72n_with_client_credentials.ps1` | legacy credential-injected buildが存在。現在の通常hardware経路はUART provisioning。両経路を分けて追跡 |
| RX671通常MQTT | `RX671_EK_AWS_IOT_CERT_PEM` / `RX671_EK_AWS_IOT_PRIVATE_KEY_PEM`、root CIのnightly規則 | 固定file変数のmetadataが存在。切替前にtrigger側とconsumer側を照合 |
| BG96 software動的credential | `tools/create_bg96_iot_credentials.py` | 既にCreateKeysAndCertificate。ローカルCSR生成、private保存先、結果不明時の回収へ改める候補 |
| native IDT | `tools/idt/run_idt.py`、`prepare_transport_key.py` | AWS認証は`boto3.Session()`のchain。disposable keyとIDT生成certificateをprivate source copyで照合。外部native IDTの発行経路を無断でCSR発行へ置換しない |
| 一時Thing alias / OTA | `tools/manage_ephemeral_iot_thing.py`、`tools/idt/ota_aws_signers.py` | owned journal・cleanupを利用する経路がある。証明書署名用とdevice認証用を区別 |
| Fleet Provisioning | `AWS_FLEET_CLAIM_CERT_RX72N_02` / `AWS_FLEET_CLAIM_PRIVATE_KEY_RX72N_02` | claim鍵は接続後のdevice鍵と別。OIDCで置換したと判定しない |
| TSIP | `RENESAS_*_SECURITY_IP_PROVISION_BLOB_TLS_CLIENT_*`等、対応するcertificate変数 | wrapped private blobとcertificateの対応が必要。host CSRだけで全TSIP対応と判定しない |
| Runner AWS認証 | root CI `AWS_CLI_RUNNER_TAG=aws-cli-ishiguro`、IDTのdefault Session | runner 3のtagに一致。profile/credential chainの内容は未取得。既存キーは撤去しない |

対象AWSアカウントの入口は[hardware-config operations](https://gitlab.saffti.jp/oss/infra/hardware-config/-/blob/main/docs/operations.md)の`AWS_ACCESS_KEY_ID_ISHIGURO` / `AWS_SECRET_ACCESS_KEY_ISHIGURO`。
正規SDK内部で取得した個人アカウントのcaller identityは、root CIの既存OTA service roleのaccountと一致した。
会社用アカウントをOSSへ流用しない。共有`gitlab.saffti.jp` providerの準備は別担当が行う。RX74M role、別GitLab用providerおよびha1 roleは変更しない。

</details>

<details>
<summary>独立したOIDC-only疎通と最小role</summary>

構成は[jobだけのinclude](../.gitlab/ci/aws-oidc-probe.yml)。rootは`RUN_RX_IOT_OIDC_PROBE=true`のapi/webだけを`oidc_probe` profileへ分離する。global defaults/stages/workflowをincludeから上書きしない。新flagの既定値はfalseで、既存profileの定義は変えない。
通常push/MR/既存pipelineではOIDC jobを生成しない。`CI_CONFIG_PATH`というpipeline変数を渡すだけで別構成を選べるとは扱わない。
[GitLabのcustom config設定](https://docs.gitlab.com/ci/pipelines/settings/#specify-a-custom-cicd-configuration-file)はproject設定であり、既存CIに影響するため変更しない。
新規pipelineへの入力は`RUN_RX_IOT_OIDC_PROBE=true`、`RX_IOT_OIDC_MODE=source|live|denied_ref`だけを基本とする。既存のbuild/IDT/OTA/nightly selectorや`PIPELINE_PROFILE`を同時指定しない。pipeline変数がworkflowのoff/build既定値を上書きできるため、**実行前に正確なpayloadと生成job一覧を照合する**。
`source`は`aws_oidc_source_check`だけで、AWSを呼ばない。`live`はprotected mainでsource checkと`aws_oidc_read_probe`、`denied_ref`は`200-*`でsource checkと`aws_oidc_denial_observation`を生成する。
main以外の正試験をscript（`configuration()`）でも拒否する。許可refやpipeline種別を変更する場合は、script、CI規則、trustを一緒にレビューする。trustだけを変えない。
compiler/UART、certificate発行、EC2/S3/Signer、artifact/cacheは使用しない。新jobはcompiler共有leaseを取得しない。

専用role名は`saffti-iot-reference-rx-oidc-probe`。[trust template](../tools/aws/oidc-probe-trust.template.json)の`${ACCOUNT_ID}`を、正本metadataとcaller identityで照合した個人accountに置換する。
`aud=sts.amazonaws.com`、`sub=project_path:oss/import/github/renesas/iot-reference-rx:ref_type:branch:ref:main`の完全一致とし、wildcard refやRX74M projectを追加しない。
Self-ManagedではAWS条件キーにgitlab.com専用の`project_id`や`ref_protected`を用いない。
[permission policy](../tools/aws/oidc-probe-policy.json)は東京リージョンの`iot:DescribeEndpoint`のみ。STS GetCallerIdentityに追加Allowは不要。
このroleにIoT発行/変更/削除権限を追加しない。
`sub`だけでは構成file/job/保護状態を制限できないため、mainの他jobも同じaudのID tokenを要求できる。発行/回収用roleはこのtrustだけを流用して有効化しない。

設定候補の名前は`RX_IOT_OIDC_ACCOUNT_ID` / `RX_IOT_OIDC_ROLE_ARN`。値の登録は今回未実施。
main用の非secret設定をprotectedかつenvironment scope `aws-oidc-probe`に置く。未許可ref確認では、同じ非secret設定を当該pipelineに明示指定する。
登録した場合はhardware-configに**変数名のみ**記録し、値・JWT・STS credentialsは載せない。
`RX_IOT_OIDC_TOKEN` / `RX_IOT_OIDC_WRONG_AUDIENCE_TOKEN`は`id_tokens`が発行するため、固定変数へ登録しない。
pipeline変数はproject変数を上書きできる。実証の記録では、起動者とoverride権限設定を確認し、正本account/専用roleから独立に計算した`SHA256(account + "|" + role ARN)`と出力`configured_target_sha256`を照合する。
2026-11-07のproject API確認では`ci_pipeline_variables_minimum_override_role=developer`だった。今回この設定は変更していない。
この照合なしに「個人accountで成功」「同一roleの正/負試験」と判定しない。scriptのidentity照合は入力されたtargetとの一致を示すだけである。

probeはambient `AWS_*` / Boto設定を除去し、config/credentialsの読取り先を空deviceに固定する。
unsigned STSにtokenをmemoryで渡す。応答の短期keysだけをidentityとIoT clientへ明示し、環境変数・file・process argumentsへ書かない。
有効期間900秒、SDK再試行なし、通信timeoutは接続5秒・応答15秒。ログは成功booleanか固定失敗booleanだけ。SDK debugも抑止する。
誤audienceが`InvalidIdentityToken`、未許可refが`AccessDenied`以外なら成功と扱わない。
誤audience試験はprovider側のclient ID一覧が`sts.amazonaws.com`のみであることを前提にする。共有providerの管理者はRX74M親であり、一覧が変わった場合は判定根拠を再評価する。追加audienceをprobeから登録しない。
未許可refの出力は`sts_access_denied`であり、ref拒否の証明ではない。同一targetでmain正試験が直近に成功し、source SHA/実際のref/role設定/監査記録を突き合わせて初めてref制限を評価する。
CloudTrailの該当AssumeRoleWithWebIdentityイベントでsub・失敗理由を確認できない場合は、その証拠が未取得と記録する。別branchが出すbooleanだけを承認根拠にしない。
job cancel時にcloud側の変更資源はない。進行中のSTS sessionは最大900秒で失効する。

debug設定は、配備Runner 18.9.0（revision `07e534ba`）の[build_settings.go](https://gitlab.com/gitlab-org/gitlab-runner/-/blob/v18.9.0/common/build_settings.go)を確認した。bool検査は[Go ParseBool](https://pkg.go.dev/strconv#ParseBool)で、真値は`1/t/T/TRUE/true/True`。CI規則とscriptはこれらを拒否し、追加で混合大小文字や`+1/01/+0001`も拒否する。job開始後のdebug変数上書きは禁止する。script側の拒否は既にRunnerへ出たログを取り消す機能ではない。
ローカル確認: `python -m unittest tools.ci.tests.test_aws_oidc_probe`。source profileも同じ9件を実行する。
実際のAWSでの正/負試験、GitLabの実token claim、runner配備botocore版は別途確認が必要。共有providerは別担当が作成し、個人account/URL/client IDを読取り確認済み。専用roleは未作成。
既存pipelineと共有host leaseへの非干渉を調整してから実行する。

</details>

<details>
<summary>次段階: CSR・最小権限・正常/異常終了時の回収案</summary>

次段階の候補は `OIDC → run所有権記録 → private key/CSR → INACTIVE certificate → 関連付け/ACTIVE → 試験 → INACTIVE/解除/削除 → private領域消去`。
secretを含まないpublic buildとprivate provision/runtimeを分離する。RSA2048以上または対応ECCの選択は、native IDT/各TLS backend/TSIPの要件と照合する。
STS期限切れはIoT certificateを失効させない。

| 区分 | 候補となる最小操作 | 制限・確認すべき点 |
|---|---|---|
| 発行 | `iot:CreateCertificateFromCsr` | resource指定に対応しないため`Resource:*`が必要。発行roleと回収roleを安易にまとめない |
| 証明書管理 | `DescribeCertificate`, `UpdateCertificate`, `DeleteCertificate` | 証明書ARNを所有journalに固定。cert resourceにはtag ABACがないので、Thingタグだけではcert管理権限を限定できない |
| 関連付け | `AttachPolicy`, `DetachPolicy`, `AttachThingPrincipal`, `DetachThingPrincipal`、必要な一覧read | exact policy / runごとのThingとcertを対象にAPIごとのresource対応を確認。既存Thing/principalへfallbackしない |
| MQTT | 必要な`Connect/Publish/Subscribe/Receive`だけ | `project38/pipeline/job/target`のclient/topicと試験要件を照合。管理用IAMとdevice IoT policyを分ける |
| OTA/IDT/benchmark | 既存の必要なS3/Signer/Jobs/EC2等 | probe roleには含めない。native suiteが実際に使うoperationとcleanupを別途抽出 |

**未解決の権限境界:** 直接CI roleへaccount内`cert/*`の変更/削除を与えると、ローカルjournal検査だけではIAM側の所有権制限にならない。
credential発行/回収を検証する仲介service、または明示的に限定した試験account等の境界を選ぶ必要がある。
新しいserviceや広いcert管理権限をこの初期変更で導入しない。対象・必要操作・終了条件を提示して人間が選ぶ。

| 終了条件 | 回収案と成功判定 |
|---|---|
| 通常終了/試験失敗 | `finally`で新規通信停止→INACTIVE→owned policy/Thing関連解除→DeleteCertificate→Describeで不存在確認→private key/CSR/FW/source copy消去。どれか未完了なら移行gate失敗 |
| cancel/timeout | job自身のfinallyだけに頼らず、別の回収実行者がsecretなしjournalを読む。正規のOIDCで新しいSTS sessionを取得し、元job/pipelineのterminal状態と所有権を照合してから回収 |
| host停止/応答欠落 | CreateCertificateFromCsrにidempotency tokenはなく、同じCSRの再送でも別certificateになる。発行intent/CSR公開鍵hashを永続化し、結果不明なら再発行せずreconciliationへ。response保存前の孤児を独立回収できる証拠基盤が未実装 |
| 回収権限不足/証拠不一致 | 既存資源を推測で削除しない。secretなしresource ID/状態を保持し、責任者へ具体的な未回収対象を報告。次の同一対象試験を止める |

回収実行者の候補は定期janitorとon-demand recovery。周期、最大残存時間、所有journalの保存場所、CloudTrail等との照合、担当者、通知先を決定してからenableする。
Thingの名前とattributesにproject/pipeline/job/target/expiryを記録する案は、所有journalとの照合用でありIAM tag ABACではない。Thing/certificateにThing group等と同じタグ制限を適用できるとは扱わない。
発行結果不明時のreconciliationには、永続intentに保存したCSRのSPKI公開鍵hashと、候補certificateのDescribeCertificate結果との一致確認が必要になる。候補を発見するread範囲と証跡基盤は未設計である。
公開journalにprivate key/CSR本文/JWT/STS keysを含めない。kill直後にprivate file消去を保証できないため、private領域のACLと再起動時清掃も確認する。

既存固定credentialの撤去条件は、利用先一覧・OIDC-only正/負試験・CSR/回収試験・別担当と調整したIDT/OTA/benchmark回帰がそろうこと。
製品リリースの成功とOIDC移行の成功は別に記録する。

</details>

## 公式根拠

- [GitLab AWS OIDC / Self-Managedのaud・sub](https://docs.gitlab.com/ci/cloud_services/aws/)
- [STS WebIdentity API / AWS keys不要・900秒以上](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
- [IoT CSR API / key条件・CSR再送で別certificate](https://docs.aws.amazon.com/iot/latest/apireference/API_CreateCertificateFromCsr.html)
- [IoT certificate削除条件](https://docs.aws.amazon.com/iot/latest/apireference/API_DeleteCertificate.html)
- [IoT IAM operation/resource/condition対応](https://docs.aws.amazon.com/service-authorization/latest/reference/list_iot.html)

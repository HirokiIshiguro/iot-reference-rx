# RX72N EthernetのOIDC実機検証

最初に通常OTAとIDT Transportを個別に実証する。native OTAは回収担当を決め、`OTAE2EGreaterVersion` だけを試す。各試験でAWS資源の回収と通常FWへの復帰を確認してから次へ進む。

## IAMの設定

GitLabの保護mainは、既存のグループ変数 `AWS_ROLE_ARN` から `saffti-oss-gitlab-oidc` を使用する。既存のtrustと `rx72n-baseline-read` を保持する。AWSで追加するCI権限には `StringEquals` の `gitlab.saffti.jp:sub` として `project_path:oss/import/github/renesas/iot-reference-rx:ref_type:branch:ref:main` を指定する。これは同一project/refの境界であり、ジョブ単位の権限制御はできない。[AWSのOIDC条件キー](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html)

| 対象 | 追加権限の候補と対象範囲 |
|---|---|
| 通常OTAのThing | `iot:DescribeThing` / `ListThingPrincipalsV2` を既存RX72N Thingと実行ごとの `<device>-ota-*` Thingに許可。作成・削除は後者のThing ARN。principalのattach/detachは設定済み証明書ARNと `iot:thingArn` で後者に限定。 |
| 通常OTAの更新と配信 | `iot:CreateOTAUpdate` / `GetOTAUpdate` / `DeleteOTAUpdate` を `otaupdate/<device>-ota-*` に限定。 `DescribeJob` / `DeleteJob` / `DescribeJobExecution` はAWSが返すjob ARNを対象とし、ARNのパターンを実証跡で確認する。 `signer:DescribeSigningJob` は同一region/accountの署名job ARN。 `iam:PassRole` は既存OTA service roleのARNと `iam:PassedToService=iot.amazonaws.com` に限定。 |
| 通常OTAのS3 | 既存OTA bucketの `ota/<device>-ota-*/source/*` と `ota/<device>-ota-*/signed/*` を対象に、Put/Get/DeleteObjectとGet/DeleteObjectVersion。ListBucket/ListBucketVersionsは同じbucket ARNとprefix条件。AWS IoTが引き受けるOTA service role側の権限も別に確認する。 |
| IDT Transportの参照 | AWSのIDT版照合・試験定義参照、登録済みIoT証明書の `iot:DescribeCertificate`、東京リージョンの `ec2:DescribeInstances`、SSMの公開パラメータ `/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2` の `ssm:GetParameters`。ローカルbundle欠落時の署名付き `LatestIdt` は `us-west-2` を使用する。 |
| IDT TransportのEC2対向 | 旧 #70574 と同じ時刻・操作者のCloudTrailでは `t2.micro` 1台、既定VPC/サブネット、`Owner=IoTDeviceTester` のinstance/SG、`idt-ec2-ssh-key-*` のkey pair、TCP 80/9000が観測された。東京、同じVPC/サブネットと取得したAMI、instance type、作成時タグに限定したRunInstances/CreateSecurityGroup/CreateTagsと、対象のSGルール・instance・key pairの回収を照合する。key pairに作成時タグはなかった。 |

旧Transportと同じ時刻のCloudTrailは資源と権限の候補。現行jobへの帰属や全APIの証明は次の試験で行う。既定サブネットの現在の `MapPublicIpOnLaunch` は有効なので、実行前の費用にはIPv4を含める。IAM管理者が実ARNを埋め、対象mainの許可、別project/タグ・別資源の拒否を確認してから、`IAM → Roles → saffti-oss-gitlab-oidc → Permissions` で用途別の差分を適用する。IDTの固定sessionを有効にする際は、同じロールの `Maximum session duration` も1時間から3時間へ変更する。この上限変更は共通ロール全体に及ぶ。通常OTAの試行には3時間化は不要。[AWS IoT](https://docs.aws.amazon.com/service-authorization/latest/reference/list_iot.html) · [AWS Signer](https://docs.aws.amazon.com/service-authorization/latest/reference/list_signer.html) · [IDTの権限例](https://docs.aws.amazon.com/freertos/latest/userguide/lts-idt-dev-tester-prereqs.html)

IDT Transportの実行予算には `idt_source_matrix` が生成する `artifacts/idt-bootstrap/rx72n-bootstrap-seconds.txt` の実測と、既存のnative 75分および回収枠を使う。実測1回は時間上限の証明にならないため、準備の上限と余裕は別に確認する。

native OTAが内部で行うIAM role/policy作成・attachは、通常OTAの `PassRole` と分ける。固定suiteで既存roleを指定する設定や、作成時にpermissions boundaryを強制できることを確認できていない。native OTAは独立した試験アカウント、または同等の制約でその操作を許可できる構成を決めてから実行する。

## Native OTAの回収手順

1. RX72N Ethernetの `test_rx72n_idt` に `RUN_RX_IDT=true`、`IDT_TARGET=rx72n-ethernet`、`IDT_SCOPE=ota-mqtt`、`IDT_TEST_ID=OTAE2EGreaterVersion` を指定する。起動前にrun ID、時刻、job、account/region、回収担当を固定する。実行前のSigner profile一覧と、今回のACM証明書ARN・所有タグを、Windows runner停止後も読める版管理付きS3に記録し読み戻す。
2. 過去の #70703と#70704 のCloudTrailで、`PutSigningProfile` 3/3件がそれぞれ `ImportCertificate` の証明書ARN、`CreateOTAUpdate` のprofile名と証明書ARN、`StartSigningJob` のprofile名と署名job IDに一意に対応した。Put/Startは `iot.amazonaws.com` が引き受けたservice roleから記録される。初回実行では、作成イベントID、OTA ID、profile ARN/version ARN、署名job IDを個別に保存する。稼働中に `GetOTAUpdate` でIoT job IDと署名job ID、`DescribeSigningJob` でprofile versionと証明書を照合する。旧CloudTrailのCreateOTAUpdate応答だけではIoT job IDを得られなかった。[CloudTrail LookupEvents](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html) · [GetOTAUpdate](https://docs.aws.amazon.com/iot/latest/apireference/API_GetOTAUpdate.html) · [DescribeSigningJob](https://docs.aws.amazon.com/signer/latest/api/API_DescribeSigningJob.html)
3. 失敗・取消・runner喪失時は、元のnativeプロセスと子プロセスが停止したことを確認し、別の認証セッションで手順1の記録とサービス側の現在値を読み直す。所有を確認したOTA update/jobを終了し、署名jobが終端であることを確認してから、関連streamとS3の対象object version/delete markerを回収する。今回専用のbucketのみ空を確認して削除する。
4. Thing・IoT証明書・policyとIAM role/policyは、作成記録と識別子を照合し、attachmentを解除して回収する。残ったEC2も作成記録で今回の所有を確認してから回収する。Signer profileは作成前に同名がなく、作成時と現在のARN・version・証明書が一致し、他の利用がないことを確認した場合だけ取り消す。 `CancelSigningProfile` は名前指定なので、照合と取消の間に別の書込みがないことが必要。 `Canceled` を読み戻し、証明書の所有と参照解消を確認してからACMを回収する。[CancelSigningProfile](https://docs.aws.amazon.com/signer/latest/api/API_CancelSigningProfile.html)
5. 通常FW復帰、reset、UART静穏、ロック解放、各AWS資源の終了状態、GreaterVersionの起動証跡を記録する。取得できない証拠や所有が曖昧な資源は保留し、次の実行を止める。中断 #70704 の手動回収を参照し、元job喪失時の独立回収を別に検証する。[過去の公開証跡](https://gitlab.saffti.jp/-/project/38/uploads/539031949e04d575e3cc0e0ef84248ee/idt-ota-witness-11262-11265-sanitized-evidence.zip)

`ota_profile_evidence.match_created_profile` は回収候補ごとに、元runのcaller ARN、所有確認済み証明書ARN、対象OTAのprofile名、事前一覧、収集済みイベントから照合する。中断runでは同じ証明書を使うprofileが2件あったため、証明書とprofile名を組にする。過去3件に対する照合と単体試験を確認済み。過去の事前一覧は得られていないため、履歴で照合したのはイベント間の関係まで。

`verify_live_profile` は、対象Thingが1件だけのOTA更新と、それに紐付く署名ジョブを読み取り、CloudTrailで特定したプロファイルのバージョンと証明書を照合する。IoT Job IDは元runの記録から渡す。AWS応答を模した単体試験で、対象や署名ジョブが違う場合は照合を拒否することを確認している。

`ota_recovery_evidence.inspect_candidate` は、版管理された `AdmissionStore` で元runと記録の世代を確認し、同runの証明書と事前一覧からイベント照合と現在値の読取りをつなぐ。対象Thing・IoT JobとCloudTrailの収集範囲は、別の認証セッションで元runの記録に基づいて確定する。独立ジョブでの証拠収集・回収・終了照合が接続されるまで、native OTAの起動は保留する。

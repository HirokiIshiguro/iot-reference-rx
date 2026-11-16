# AWS OIDC移行の準備

この変更はGitLab ID tokenから短期STS sessionを得る共通部品と読取りprobe、RX671 Windows IDTの明示選択pilotを含む。既存3機種のWindows IDT、通常OTA、RX72N RPi4 pilotの既定入口は変更しない。pilotは既存Runner #3のprofile・予算・共通roleを照合し、限定refの認証許可を確認したうえでRX671の非実機preflightを実行する候補である。Transportとnative OTAは未接続である。通常OTAのOIDC切替とnative OTAの独立recovery接続は後続である。AWS role/trust、CI/CD Variables、実機および共有operatorの固定キーは変更しない。

## 固定sessionの境界

`tools/aws/oidc_session.py`は、呼出し側が明示したproject・account・role・ref・source SHAと、protected refのID token claimを照合する。claimの読取りは事前検査であり、JWT署名の検証と最終的な認可はSTSとAWS trust policyが行う。unsigned STSに対して1回だけ `AssumeRoleWithWebIdentity` を実行し、返された固定credentialでcallerのaccount・assumed roleを確認する。任意のrunner profile・endpoint設定・EC2 metadataにfallbackしない。

GitLab Self-ManagedのAWS trustで使うaud/subは、同じtrust条件を満たす別jobをjob単位で分離しない。SHA・job ID・runner ID等の署名claim照合はこの呼出し側の検査であり、AWS IAMによるjob単位の強制ではない。実行を許すsource/refと同SID主体は別途管理する。

sessionの長さは呼出し側が明示する。IDTの候補は10800秒で、jobの残り時間、scriptの保守的な残り時間、実際のSTS expirationの最小値が、残準備・native・cleanup・保存と安全余裕の合計を覆わなければ停止する。安全余裕には時刻ずれを含める。ID tokenはSTS交換時に時刻ずれと通信の余裕を含めて有効性を検査し、交換後の残時間判定には含めない。交換後にID tokenが失効しても、発行済みcredentialの期限はSTS expirationである。credentialはjob終了後もその期限まで有効な場合がある。自動更新は行わない。budgetの確定とnative直前の再判定は既存IDT supervisorへの接続時に検証する。`CI_JOB_STARTED_AT`、`CI_JOB_TIMEOUT`やdeadlineが利用できないときもfail closedとする。

`FixedSession.expiration` はSTS credentialの期限である。後続の再判定は `ensure_session_budget`、転送後の環境では `ensure_child_budget` を使う。WSL側での再判定は呼出し側が実施する。署名URLを使う場合は、さらにそのURL自体の期限を呼出し側が判定する。

STS交換時はprocess全体のambient AWS環境を一時的に退避するため、並行AWS処理、環境変数を使う処理、子process起動を始める前に呼び出す。`quiet_aws_logging` は呼出しthreadの同期SDK処理の診断を対象に既存logging handlerをfilterし、UART等の無関係なloggingを停止しない。loggingのthread ID記録が無効なら開始せず、対象scope中のlogging設定変更やSDK worker threadは対象外である。対象はbotocore、boto3、s3transfer、urllib3のPython loggerであり、その他のlibrary、`warnings`、直接の標準出力、別processは抑止しない。後続のS3 presignは `FixedSession` のcredentialをclientへ明示し、このscopeとログ境界を検証する。URLやcredentialを記録しない責任は呼出し側にある。

`child_environment`は許可リストで入力を選び、固定session以外のAWS設定とOIDC tokenを渡さない。WindowsからWSLへの受渡しは `wsl_bridge_environment` と `wsl_child_environment` の2段階で、Linux側のprofileやmetadataを無効化してから利用する設計である。IDTのsource接続案はhost preflightより前に一度だけSTSを取得し、Windows/WSL/native開始前に期限を再判定する。実際のAWS CLI署名とWindows→Ubuntu WSLの受渡しは合成credentialで確認した。実role、監督processのsignal伝播・子孫停止、全入力とartifactの秘匿、実機は未検証である。JWT、STS credential、変換済みの署名URL、鍵や子processの出力・artifactの秘匿は呼出し側の責任であり、環境変数の除外だけでは保証されない。

IDTの `oidc_job.py` は、`/oss` から継承する `AWS_ROLE_ARN` をレビュー済みのARNに照合する。期待account、runner ID、host profile、実行パス、bootstrap・native準備・報告・余裕の予算もレビュー済みsource設定を使う。`REVIEWED_CONFIGS` はtransportを含む他scopeでは空のままにし、明示pilotだけsource固定のpreflight設定を使う。この停止より前にGitLabはJWTを発行し、jobはプロジェクト内resource groupを取得する。共有shell runnerのPython環境や実行ファイルを信頼できないjobが書き換えられる場合、`-I` やsource上のpath固定だけではJWTを守れないため、実配備前にrunnerの信頼・書込み境界を確認する。明示pilotのsourceは一回用の保護refを固定する。現在のtrustはmain向けであるため、このrefの短期trust追加と完了後の復元は別途必要である。OTA scopeはowner journalと独立recoveryが未接続のため開始しない。

native OTA向けSignerの所有証拠と独立回収は未接続である。既存の通常経路のSigner処理はこのpilotでは切り替えない。`ota_admission.py` はversioned S3の条件付きwriteと元run／回収jobの区別をofflineで検討する部品で、実job、所有証拠の取得、独立recovery、IAM境界には未接続である。snapshotのページングは原子的ではなく、管理外主体による変更を防止するものではない。S3のETag条件とversion照合は、管理外主体による旧versionのcopy復元やdelete markerを使う競合を原子的に防止しない。journalのwriter・履歴保護と運用上の管理外変更検出は実適用前の前提である。

BG96の既存APN入力は `AWS_IOT_CELLULAR_APN_*_CK_RX65N_01` などのAWS接頭辞を持つが、AWS SDKの認証設定ではない。呼出し側が既存の4変数を個別に許可した場合だけ、これらのdevice通信入力を引き継ぐ。`AWS_PROFILE` やAWS endpoint overrideは許可できない。

## probeと後続

RX72N Ethernet通常OTAのOIDC wrapperは準備コードとして残すが、現在の通常OTA jobには接続していない。初回実行には対象のIoT Thing／OTA、S3 object、Signer参照とOTA service roleの `iam:PassRole` の許可が必要で、ref・tagのtrustと回収も別途確認する。

初回の [IAM権限とnative OTAの回収手順](idt-oidc-pilot.md) に、通常OTA・IDT Transport・native OTAそれぞれの権限と実行前に確認する項目を記載する。

`tools/aws/oidc_probe.py`とそのread-only policy/trustの候補は、[MR !251](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/251)から再利用した。probeのlive jobはこの変更では追加・実行していない。policyは候補であり、!251単体のsource CI成功はlive OIDC成功を意味しない。

[Issue #202の設計](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/202#note_63778)には対象job・権限候補・独立cleanupを記載している。Schedule #5の過去pipeline #12263は50 bridge中8 childが未生成のfailed runだった。main `a80863b9`のCI定義には同じ50行と3-target IDT matrixが存在するが、名前の照合は現行expanded graphや試験成功の証明ではない。利用側project142のS3 presignは一時session tokenを含み得るURLをfirmwareに組み込み得るため、安全な受渡しと期限・URL長を確認する前にOIDCで実行しない。

実際のrole/trust・変数名とscopeの適用、native APIの最小権限、Windows/WSLの実動作、所有資源の独立回収、全対象でのOIDC実証は未完了である。共有operatorのkey本体の無効化・削除・rotateは、この変更の対象外である。

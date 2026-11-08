# AWS OIDC移行の準備

この変更はGitLab ID tokenから短期STS sessionを得る共通部品と、既存の読取りprobeを追加する。**通常CI、IDT、OTA、利用側への接続は未実装であり、OIDC移行の完了ではない。** AWS role/trust、CI/CD Variables、実機および共有operatorの固定キーは変更しない。

## 固定sessionの境界

`tools/aws/oidc_session.py`は、呼出し側が明示したproject・account・role・ref・source SHAと、protected refのID token claimを照合する。claimの読取りは事前検査であり、JWT署名の検証と最終的な認可はSTSとAWS trust policyが行う。unsigned STSに対して1回だけ `AssumeRoleWithWebIdentity` を実行し、返された固定credentialでcallerのaccount・assumed roleを確認する。任意のrunner profile・endpoint設定・EC2 metadataにfallbackしない。

sessionの長さは呼出し側が明示する。IDTの候補は10800秒で、jobの残り時間、scriptの保守的な残り時間、実際のSTS expiration、および保守的上限としてのID token expirationの最小値が、残準備・native・cleanup・保存と安全余裕の合計を覆わなければ停止する。ID tokenの失効で発行済みSTS credentialが直ちに失効するという意味ではない。budgetの確定とnative直前の再判定は既存IDT supervisorへの接続時に検証する。`CI_JOB_STARTED_AT`、`CI_JOB_TIMEOUT`やdeadlineが利用できないときもfail closedとする。

`FixedSession.expiration` と `FixedSession.token_deadline` は再判定に必要な期限であり、どちらもcredential値ではない。後続の再判定は `ensure_session_budget`、転送後の環境では `ensure_child_budget` を使い、両期限を欠落させない。WSL側での再判定は呼出し側が実施する。

STS交換時はambient AWS環境を一時的に退避し、SDKの診断ログを抑止してから元に戻すため、複数threadを開始する前に呼び出す。`quiet_aws_logging` はprocess全体のPython loggingを一時停止するが、`warnings` や直接の標準出力は対象外である。後続のS3 presignでもtokenを含むURLやSDK診断を記録しないよう、呼出し側でこの制約とログ境界を検証する。

`child_environment`は許可リストで入力を選び、固定session以外のAWS設定とOIDC tokenを渡さない。WindowsからWSLへの受渡しは `wsl_bridge_environment` と `wsl_child_environment` の2段階で、Linux側のprofileやmetadataを無効化してから利用する設計である。合成credentialを用いたWindows→Ubuntu WSLの受渡しは確認したが、既存IDT supervisorへの接続、signal伝播、子孫process停止と実機確認は未実施であり、それまでは実機jobに接続しない。JWT、STS credential、変換済みの署名URL、鍵や子processの出力・artifactの秘匿は呼出し側の責任であり、環境変数の除外だけでは保証されない。

BG96の既存APN入力は `AWS_IOT_CELLULAR_APN_*_CK_RX65N_01` などのAWS接頭辞を持つが、AWS SDKの認証設定ではない。呼出し側が既存の4変数を個別に許可した場合だけ、これらのdevice通信入力を引き継ぐ。`AWS_PROFILE` やAWS endpoint overrideは許可できない。

## probeと後続

`tools/aws/oidc_probe.py`とそのread-only policy/trustの候補は、[MR !251](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/251)から再利用した。probeのlive jobはこの変更では追加・実行していない。policyは候補であり、!251単体のsource CI成功はlive OIDC成功を意味しない。

[Issue #202の設計](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/202#note_63778)には対象job・権限候補・独立cleanupを記載している。Schedule #5の過去pipeline #12263は50 bridge中8 childが未生成のfailed runだった。main `a80863b9`のCI定義には同じ50行と3-target IDT matrixが存在するが、名前の照合は現行expanded graphや試験成功の証明ではない。利用側project142のS3 presignは一時session tokenを含み得るURLをfirmwareに組み込み得るため、安全な受渡しと期限・URL長を確認する前にOIDCで実行しない。

実際のrole/trust・変数名とscopeの適用、native APIの最小権限、Windows/WSLの実動作、所有資源の独立回収、全対象でのOIDC実証は未完了である。共有operatorのkey本体の無効化・削除・rotateは、この変更の対象外である。

# RPi #4 からの RX72N Transport 起動

RPi #4 の専用 Runner から Linux 版 IDT を起動し、RPi #1 の RX72N Ethernet を既存の UART bridge と書込み処理で使うための統合用経路です。この変更だけでは実機・AWS・CI を起動しません。IDT 4.9.0 / FRQ 2.5.0 の配布 suite のテスト定義は変更せず、x86-64 実行には Runner 側の QEMU/binfmt と必要な実行環境を使います。

## 入力と実行順

1. 専用の `gitlab-runner-idt-rx` ユーザー、保護ref、Runnerのtag `project38-idt-rpi4-protected` を使う。GitLabの現在ジョブ情報・署名付きID token・CI環境を、host設定のRunner ID（候補 #28）・project・ref・source SHAと照合する。
2. `/etc/idt-rx/runtime.json` のみから非秘密のレビュー済み設定を読む。directoryはroot所有0755、fileはroot:gitlab-runner-idt-rx 0640とし、symlinkを受け付けない。CI変数による設定pathの上書きはできない。未配置・未レビューなら停止する。
3. 保護refの手動pipelineで `IDT_PAIR_MODE=transport-controller` を指定する。`rpi4_prepare_build` を手動開始すると、`rpi4_prepare_package` が同一SHAの通常復帰bundleと公開signerを作り、`rpi4_snapshot_verify` がWindowsとRPiの実ファイルを照合する。これらはAWSや実機を使わない。
4. `rpi4_transport_preflight` を手動開始し、共通roleの一時セッションでAMI読取りとEC2鍵のDryRunを確認する。成功後だけ `rpi4_transport_controller` を手動開始できる。各jobは独自の一時セッションを取得し、ジョブ・処理・回収時間の予算を確認する。元checkoutと依存gitlinkのSHAを記録する。
5. checkoutはWindowsと揃えて `core.symlinks=false` とし、RPi側でもWindowsと同じ対象のnested依存を固定された参照先へ初期化する。除外対象は既存Windows helperから読み、取得後にrecursive pinを確認する。`rpi4_pair.snapshot` でIDTに渡す前のsource snapshotをprivate runtimeに保存する。結果の一時出力もcheckoutの外へ置き、IDTのsource copy後にredacted reportだけをCI用の `artifacts/idt` へ移す。build callbackはprivate socketへ要求し、RPi側の仲介がその時点でWindows jobを起動する。親jobのtokenは仲介が保持し、IDT・Windowsへ渡さない。Windows側自身のjob tokenはcheckoutとjob確認後、build処理に渡さない。Windowsは同じsource SHAを確認し、受け取ったヘッダだけをprivate copyへ適用してビルド結果を返す。
6. 既存 `run_transport.py` のbridge、`flash_transport.py` のtarget/manifest/hash検証、redacted JUnit checker、停止・回収処理を使う。Linux側は通常のSSH/SCPを使い、WSLのpath変換を呼ばない。対象はRX72N Ethernet / Transport groupだけ。

Linux版の配布元は使用前に検証し、各実行のprivate runtime内に書込み可能なコピーを作る。コピーも検証してから使うため、配布元の設定やテスト定義を書き換えない。コピーは実行記録と同じprivate runtimeに残し、安全な停止を確認する前には削除しない。

Windows jobの共有枠待ちは、job開始後の接続確立待ちと分けて数える。親jobの既存tokenで下流jobの状態だけを確認し、接続が先に成立した場合はすぐ進む。枠待ち・接続待ち・ビルドの合計は既存のnative実行時間内に収め、回収用の時間は使わない。停止や期限超過では一時sessionを保持し、下流jobを確認してから回収する。
nativeでは `pair_build_seconds` に、接続確立600秒と応答・終了30秒を加えても既存のnative実行上限4500秒未満とし、その残りを最大の共有枠待ちに充てる。待機の上限はコントローラー開始時から減り、処理前の準備時間も含めて保守的に扱う。

host設定の `runtime.json` は `schema_version`、`account`、`role_arn`、`ref`、`source_sha`、`expected_ami`、`runner_id`、`job_timeout_seconds`、`budget`、`runtime_root`、`idt_root`、`ssh`、`scp`、`git`、`python`、`home`、`search_path`、`pair_build_seconds`、`qemu_sysroot` を持つ。CIのLinux入口は `/opt/idt-rx/venv/bin/python3` を使用し、レビュー済み設定・必要な依存を事前に用意する。build callbackは同じsource SHAの `tools/idt/rpi4_build_callback.py` をPythonで実行する。`budget` は `bootstrap_seconds`、`native_prepare_seconds`、`report_seconds`、`margin_seconds` を持つ。値は実測・レビューしてhost側で配置し、この文書の存在を設定済みの証拠にはしない。

## 未実施と開始条件

- #15691はdevice不要の公式sample、#15694はFRQの実行確認、#15701は実行しない準備確認であり、RX72N実機Transportの成功ではない。#15701のテスト定義を書き換えるoverlayは本経路では使わない。
- `rpi4_transport_preflight` と `rpi4_transport_controller` は保護ref上の手動jobであり、通常CIでは生成されない。前者のAMI読取りと鍵作成DryRunが成功しない限り、後者を実行しない。`rpi4_windows_worker` は同一ref/SHAの親から起動される専用下流jobで、通常CIでは生成されない。
- 以前の実機job #86371はAWS事前確認後、依存ソース検査で停止した。native IDT・実機書込み・Transport判定は未実施である。修正後の実機再確認と、試験後の回収・通常FW復帰は別々に記録する。
- 実機起動前にRPi #1の固定書込み器・UART・占有を確認し、同一sourceの通常FW復帰bundleを用意する。中断時を含め、当該OIDC sessionが作ったAWS資源をCloudTrailの記録と照合して回収し、通常FW復帰・reset/UART静穏・lock解放を別々に確認する。これらの実行と最終判断は統合担当が行う。
- IDTのprivate runtimeには注入source・一時鍵・UART記録が残り得る。安全な停止を確認するまで所有者が保持し、出力するJUnitは既存のredacted reportに限る。完全なTransport合格や製品releaseは、このオフライン検証からは判断できない。

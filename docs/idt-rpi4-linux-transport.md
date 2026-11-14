# RPi #4 からの RX72N Transport 起動

RPi #4 の専用 Runner から Linux 版 IDT を起動し、RPi #1 の RX72N Ethernet を既存の UART bridge と書込み処理で使うための統合用経路です。この変更だけでは実機・AWS・CI を起動しません。IDT 4.9.0 / FRQ 2.5.0 の配布 suite のテスト定義は変更せず、x86-64 実行には Runner 側の QEMU/binfmt と必要な実行環境を使います。

## 入力と実行順

1. 専用の `gitlab-runner-idt-rx` ユーザー、保護ref、Runnerのtag `project38-idt-rpi4-protected` を使う。GitLabの現在ジョブ情報・署名付きID token・CI環境を、host設定のRunner ID（候補 #28）・project・ref・source SHAと照合する。
2. `/etc/idt-rx/runtime.json` のみから非秘密のレビュー済み設定を読む。directoryはroot所有0755、fileはroot:gitlab-runner-idt-rx 0640とし、symlinkを受け付けない。CI変数による設定pathの上書きはできない。未配置・未レビューなら停止する。
3. 同一sourceの公開signer provisioner、manifest、公開証明書と公開鍵の４入力を事前に用意する。既存の `public_signer_bootstrap_environment` が一致を確認してprivate runtimeに取り込む。
4. 共通roleから更新しない一時セッションを１回取得し、既存のジョブ・処理・回収時間の予算を確認する。元checkoutと依存gitlinkのSHAを記録する。
5. `rpi4_pair.snapshot` でIDTに渡す前のsource snapshotをprivate runtimeに保存する。結果の一時出力もcheckoutの外へ置き、IDTのsource copy後にredacted reportだけをCI用の `artifacts/idt` へ移す。build callbackはprivate socketへ要求し、RPi側の仲介がその時点でWindows jobを起動する。親jobのtokenは仲介が保持し、IDT・Windowsへ渡さない。Windows側自身のjob tokenはcheckoutとjob確認後、build処理に渡さない。Windowsは同じsource SHAを確認し、受け取ったヘッダだけをprivate copyへ適用してビルド結果を返す。
6. 既存 `run_transport.py` のbridge、`flash_transport.py` のtarget/manifest/hash検証、redacted JUnit checker、停止・回収処理を使う。Linux側は通常のSSH/SCPを使い、WSLのpath変換を呼ばない。対象はRX72N Ethernet / Transport groupだけ。

Linux版の配布元は使用前に検証し、各実行のprivate runtime内に書込み可能なコピーを作る。コピーも検証してから使うため、配布元の設定やテスト定義を書き換えない。コピーは実行記録と同じprivate runtimeに残し、安全な停止を確認する前には削除しない。

host設定の `runtime.json` は `schema_version`、`account`、`role_arn`、`ref`、`runner_id`、`job_timeout_seconds`、`budget`、`runtime_root`、`idt_root`、`build_callback`、`ssh`、`scp`、`git`、`python`、`home`、`search_path`、`pair_build_seconds`、`qemu_sysroot` を持つ。`qemu_sysroot` は管理者が固定したQEMU用sysrootで、Linux子プロセスの `QEMU_LD_PREFIX` に設定する。`budget` は既存 `Budget` の `bootstrap_seconds`、`native_prepare_seconds`、`report_seconds`、`margin_seconds` を持つ。値は統合時に実測・レビューしてhost側で配置し、この文書の存在を設定済みの証拠にはしない。

## 未実施と開始条件

- #15691はdevice不要の公式sample、#15694はFRQの実行確認、#15701は実行しない準備確認であり、RX72N実機Transportの成功ではない。#15701のテスト定義を書き換えるoverlayは本経路では使わない。
- Windows callback・private socketの立上げ、両hostの同一source snapshot、QEMU/binfmtとloader、公開signerの４入力は実環境で確認する。`tools/ci/rpi4_transport_pilot.yml` は実行を禁止したまま、通常CIからも読み込まない。`tools/ci/rpi4_pair_public_smoke.yml` は公開データ専用の接続・ビルド試験で、別の保護refからの明示起動を前提とする。
- 実機起動前にRPi #1の固定書込み器・UART・占有を確認し、同一sourceの通常FW復帰bundleを用意する。中断時を含め、当該OIDC sessionが作ったAWS資源をCloudTrailの記録と照合して回収し、通常FW復帰・reset/UART静穏・lock解放を別々に確認する。これらの実行と最終判断は統合担当が行う。
- IDTのprivate runtimeには注入source・一時鍵・UART記録が残り得る。安全な停止を確認するまで所有者が保持し、出力するJUnitは既存のredacted reportに限る。完全なTransport合格や製品releaseは、このオフライン検証からは判断できない。

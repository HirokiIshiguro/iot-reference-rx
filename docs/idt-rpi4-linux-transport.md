# RPi #4 からの RX72N Transport 起動

RPi #4 の専用 Runner から Linux 版 IDT を起動し、RPi #1 の RX72N Ethernet を既存の UART bridge と書込み処理で使うための統合用経路です。この変更だけでは実機・AWS・CI を起動しません。IDT 4.9.0 / FRQ 2.5.0 の配布 suite のテスト定義は変更せず、x86-64 実行には Runner 側の QEMU/binfmt と必要な実行環境を使います。

## 入力と実行順

1. 専用の `gitlab-runner-idt-rx` ユーザー、保護ref、Runnerのtag `project38-idt-rpi4-protected` を使う。GitLabの現在ジョブ情報・署名付きID token・CI環境を、host設定のRunner ID（候補 #28）・project・ref・source SHAと照合する。
2. `/etc/idt-rx/runtime.json` のみから非秘密のレビュー済み設定を読む。directoryはroot所有0755、fileはroot:gitlab-runner-idt-rx 0640とし、symlinkを受け付けない。CI変数による設定pathの上書きはできない。未配置・未レビューなら停止する。
3. 同一sourceの公開signer provisioner、manifest、公開証明書と公開鍵の４入力を事前に用意する。既存の `public_signer_bootstrap_environment` が一致を確認してprivate runtimeに取り込む。
4. 共通roleから更新しない一時セッションを１回取得し、既存のジョブ・処理・回収時間の予算を確認する。元checkoutと依存gitlinkのSHAを記録する。
5. Windows担当が提供する `rpi4_pair.snapshot` で、IDTに渡す前のsource snapshotをprivate runtimeに保存する。結果の一時出力もcheckoutの外へ置き、IDTのsource copy後にredacted reportだけをCI用の `artifacts/idt` へ移す。IDTのbuild callbackは `callback <IDTが生成したsource path>` で呼ばれ、`IDT_PAIR_BASELINE`、`IDT_PAIR_BUILD_SECONDS`、`IDT_PAIR_SOCKET=$HOME/.cache/idt-rx72n-pair/<pipeline ID>/build.sock` と既存 `IDT_PROVENANCE_FILE` を受け取る。callbackと対向workerの実装・統合は別担当。
6. 既存 `run_transport.py` のbridge、`flash_transport.py` のtarget/manifest/hash検証、redacted JUnit checker、停止・回収処理を使う。Linux側は通常のSSH/SCPを使い、WSLのpath変換を呼ばない。対象はRX72N Ethernet / Transport groupだけ。

host設定の `runtime.json` は `schema_version`、`account`、`role_arn`、`ref`、`runner_id`、`job_timeout_seconds`、`budget`、`runtime_root`、`idt_root`、`build_callback`、`ssh`、`scp`、`git`、`python`、`home`、`search_path`、`pair_build_seconds` を持つ。`budget` は既存 `Budget` の `bootstrap_seconds`、`native_prepare_seconds`、`report_seconds`、`margin_seconds` を持つ。値は統合時に実測・レビューしてhost側で配置し、この文書の存在を設定済みの証拠にはしない。

## 未実施と開始条件

- #15691はdevice不要の公式sample、#15694はFRQの実行確認、#15701は実行しない準備確認であり、RX72N実機Transportの成功ではない。#15701のテスト定義を書き換えるoverlayは本経路では使わない。
- Windows callback・private socketの立上げ、両hostの同一source snapshot、QEMU/binfmtとloader、公開signerの４入力は統合時に実環境で確認する。CI YAMLとRunner設定はこの差分に含めない。
- 実機起動前にRPi #1の固定書込み器・UART・占有を確認し、同一sourceの通常FW復帰bundleを用意する。中断時を含め、当該OIDC sessionが作ったAWS資源をCloudTrailの記録と照合して回収し、通常FW復帰・reset/UART静穏・lock解放を別々に確認する。これらの実行と最終判断は統合担当が行う。
- IDTのprivate runtimeには注入source・一時鍵・UART記録が残り得る。安全な停止を確認するまで所有者が保持し、出力するJUnitは既存のredacted reportに限る。完全なTransport合格や製品releaseは、このオフライン検証からは判断できない。

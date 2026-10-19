# RX65N/BG96の通信実装

RX65N通常版・TSIP版・native IDTとBG96 benchmarkは、Renesas `r_cellular`の
BG96対応forkを使用します。FreeRTOS Cellular Interfaceへの移行は行いません。
2026-10-18のユーザー指示による方針です。Kernel V11.3.0、BSP/Flash、dual-bank、
bootloaderの信頼設定、コンパイラ・リンカの共通化は維持します。

| 項目 | 参照 |
|---|---|
| ドライバ | [`r_cellular` BG96 fork](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/fitmodules/r_cellular/r_cellular) |
| 固定版 | `1.13.saffti-custom.4` / `e129c6dd730e1029440fd4b977862b0a9c6ed1f3` |
| submodule | `Middleware/Renesas/r_cellular` |
| forkの目的 | Renesas v1.13へのBG96のATコマンド・電源・UART・socket対応 |
| 製品側 | APNのKVS設定、接続・socketアダプタ、ボードの設定header |

ドライバ本体を利用側でコピー・修正・ビルド時パッチしません。
設定headerと公開APIによる組込みを、fork本体の変更と区別します。
SCで利用するFIT版も同じ`1.13.saffti-custom.4`です。

この構成への復帰は、過去のOTAや性能測定の再現成功を意味しません。
CK-RX65N/BG96は別作業へ引き渡し中のため、実機検証は返却後に行います。
SC生成物のGit管理除外も別工程です。

[Issue #173](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/173)

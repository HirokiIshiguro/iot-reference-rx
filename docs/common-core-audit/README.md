# RX671・RX65N・RX72Nの共通基盤監査

**共通基盤は現在揃っていません。** RX65Nはproject内の古いMiddlewareコピーを参照し、RX671・RX72Nが参照する共通submoduleとFreeRTOS／ライブラリの版が異なります。Flash FIT・BSP・bootloader pin・e2 studioの参照階層にも差があります。

基準はGitLab main `44232ef62ea5be65161b95ae9741c6da555c7f3b`、確認日は2026-10-07です。[Issue #169](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/169)の依頼に基づく読み取り監査で、3環境の設定・依存を変更した結果ではありません。

| 項目 | RX671 | RX65N | RX72N |
|---|---|---|---|
| FreeRTOS Kernel | 11.3.0 | 11.1.0 | 11.3.0 |
| coreMQTT | 5.0.2 | 2.3.1 | 5.0.2 |
| Middleware参照 | repo rootへのリンク | project内の通常treeコピー | repo rootへのリンク |
| app Flash FIT / BSP | 5.30 / 7.70 | 5.22 / 7.52 | 5.22 / 7.52 |
| boot Flash FIT / BSP | 5.30 / 7.70 | 5.30 / 7.70 | 4.50 / 5.52 |
| normal / native bank設定 | linear / dual | BSP dual・IDE single / dual想定 | dual / dual |
| Code/Data Flash BGO宣言 | 全app/bootで1 | 同左 | 同左 |
| native bank切替関数の実MAP | SRAM配置 | **Flashに残る** | SRAM配置の旧試作参考・現main MAP未取得 |

RX65N native appでは `PFRAM2` が0x12B bytesなのに `RPFRAM2` はsize0で、bank切替関数がFlashの `FFF5E9B0` に残っています。配置差は実MAPで確認しましたが、実PC・RAMコピー内容・暴走・静的section重複を観測した結果ではありません。通常RX65NのMAPはCI artifactに収録されず、追跡した現在workspaceにも残存していないため、生成時に補正されるかは未確定です。

RX65Nの通常OTAはbank切替をbootloaderへ委譲する経路です。app内にbank切替関数が存在することだけで、その経路から実行されたとはしません。driverのRAMコピー条件と予約不足は確認事項として残し、実際の呼出し経路に沿って検証します。

## 共通化の優先事項

1. 通常／native／bootのMAPと実効コマンドをCI artifactに残す。呼出し経路と全RAM sectionを根拠に、配置差と実動作の検証対象を確定する。
2. CIでeffective source/pin・mode/BGO・RAM section/symbolを検査し、移行前に構成差の再発を検出する安全網を用意する。
3. RX65NのRAM写像を明示したビルドを確認し、実際の呼出し経路に合わせてRAMコピー・bank操作を実機検証する。
4. FreeRTOS／ライブラリの正本とpinを1組へ揃える。RX65Nのflat copyを共通参照へ移す際は、coreMQTT 2→5、coreSNTP 1→2、Plus-TCP 4.2→4.4を含むAPI・protocol差を移行検証する。
5. Flash FIT／BSP／bootloaderの版と方針、e2 studioのlinkedResources・include・macro・ROM/RAMコピーを揃え、生成による暗黙の補正へ依存しない。

これは実装順の提案です。MCUのROM/RAM範囲、通信・clock・peripheralは仕様に基づく差として維持します。RX671/RX72NはRXv3・倍精度FPU、RX65NはRXv2・単精度FPUで、ISA／DPFPUの現設定差はハードウェア能力に対応する許容差です。使用する命令subsetや最適化方針まで必須の差としたわけではありません。根拠は[RX671 datasheet](https://www.renesas.com/en/document/dst/rx671-group-datasheet-rev100)、[RX72N仕様](https://www.renesas.com/en/products/rx72n)、[RX65N仕様](https://www.renesas.com/en/products/rx65n)です。BGOや版数の文字列が同じことだけで実動作の同一性を保証しません。

## 詳細と確認境界

- [版数・bank/BGO/割込み・コピー条件](core-versions-config.md)
- [e2 studio階層・compiler/linker宣言と実MAP](project-options.md)
- [gitlink親repo・位置・pin・再帰leaf・flat copy内容差](submodule-graph.md)

Project Explorerの階層は `.project` とGit treeからの再構成です。GUI表示そのものは未観測です。宣言、生成後のeffective options、過去試作MAP、現在mainの実機結果を区別して記録しました。

固定pinの再帰構造は、IDT親71 edges／通常RX671 child72 edges、各45 leafまで確認しました。ここでのchildは[EK-RX671 software benchmark](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls)がouter gitlinkとして保持するiot-reference-rx経路です。upstream latestとのdriftやmain ancestryをすべて検証したとはしていません。outer親commitはIDT親と異なりますが、direct31 gitlink pinは一致します。

RX671のRFP初期状態問題は[Issue #168](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/168)で別に実機検証・対策しています。本監査で見つかったRX65Nの配置差を、そのRX671起動不良の原因へ置き換えません。各JSONは宣言・pin・限定symbol/section等の証跡であり、raw firmware／credential／実RAM dumpを含みません。

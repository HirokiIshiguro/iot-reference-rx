# CC-RX未使用関数除去の比較ビルド（2026-10-15）

ユーザー指定の`C:\workspace\12345\rx72n_ether_t4`を実際に再ビルドし、未使用関数除去が働くことを確認しました。元projectはGit管理外のため、441 source/config fileのSHA-256を保存して別々の作業コピーを作り、終了後に原本の一致を確認しました。実機への書込みは行っていません。

## 比較条件

- e2 studio 2026-04.2の`e2studio-cli.exe`、CC-RX V3.07.00を使用。各caseは新規workspace・生成物なしでimport/buildしました。
- Aは元projectの「リンカ最適化all」を保持しました。Bは追加link optionを1か所だけ変更し、`-optimize=same_code,short_format,branch`として`symbol_delete`だけを除外しました。改行を含む他のmetadata bytesは一致します。
- コンパイラ設定は両方同じです。最適化levelの個別指定はなく既定2、実コマンドには`-goptimize`があります。`PowerON_Reset_PC`は両ABSにentryとして残ります。
- 全最適化は`symbol_delete,same_code,short_format,branch`を含みます。リンカの`-optimize`省略時も全最適化であり、除去には`-goptimize`とentryの指定が必要です。[Renesas公式リンカ仕様](https://tool-support.renesas.com/autoupdate/support/onlinehelp/csp/V8.16.00/CS%2B.chm/Compiler-CCRX.chm/Output/ccrx02c0503y0401.html)

## 実結果

| 確認 | A: 元projectのall | B: symbol_deleteのみ除外 |
|---|---|---|
| build時刻（JST） | 16:41:15–16:41:56 | 16:41:56–16:42:35 |
| build exit | 0 | 0 |
| mapの`Delete Symbols`件数 | 209 | 0 |
| `_my_sw_charget_function` | map削除表にあり、ABSに不在 | ABS `0xFFC027B0`、3B |
| `_deadSpace` | map削除表にあり、ABSに不在 | ABS `0xFFC02678`、4B |
| `_charget` | map削除表にあり、ABSに不在 | ABS `0xFFC02B00`、3B |
| `_PowerON_Reset_PC` | ABS `0xFFC00000`、entry | 同左 |
| MOT file bytes | 169,468 | 855,780 |

ABSのシンボル有無はGNU RX objdumpでも照合しました。MOTのfile bytesはS-recordの文字列表現の大きさであり、実行codeのROM占有量と同一ではありません。

| fingerprint | A | B |
|---|---|---|
| 入力`.cproject` SHA-256 | `484b10f3e4e0ce5f23fef542294039161445a524b55e52c1be944bfe072b5910` | `06d7a41206da3b522601ed062056167ab575011d2e2ca0e5109f92d4da1ca18d` |
| 出力ABS SHA-256 | `4b2cd3e81882a9db5185b02626df42984898da4a8ad404411da09c77fd90b47f` | `1b5b4851e6ee206a6c49beab47984eb6c24f8bfeeeccdacae00970ad434543df` |

raw log、map、ABS、生成command、比較JSONは`C:\ai\codex\tmp\ccrx-symbol-delete-rx72n-t4-20261015`に保存しています。既存CI終了後にWindows Runner ID 3の新規受け付けを一時停止して比較を行い、16:42:39に元の`paused=false`へ戻したことをAPIで確認しました。

## 適用範囲

この結果は指定projectでの除去動作の再現です。`iot-reference-rx`の全8 projectと5 benchmark repositoryについては、同じ条件に加え、実生成option・entry・map・最終ABSを個別に照合します。現在の「all」宣言だけで全対象の除去結果を検証済みとは扱いません。

同日の[CI job #71145](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/71145)も成功し、source witness `559f82f305403e37f3ef980b5a5d3c92ed1b909b`のnative Transport 3環境の実mapで、RX72N 2,616件、RX65N 2,581件、RX671 2,199件の`Delete Symbols`を確認しました。これはnative placeholder firmwareのlink結果であり、通常app・全boot・実機IDTの合格とは区別します。private保存先は`C:\ai\codex\tmp\idt-source-matrix-71145\compile`です。

## RX72N通常software appとbootの追加確認

17:46:31–17:49:27 JSTに、同じHEADに本MRの一般BSS低位RAM配置変更を加えたソースから、通常software appとbootを生成物なしで再ビルドし、両方成功しました。e2studio-cliへ標準CDTの`-application ...headlessbuild`・`-cleanBuild`を渡す比較実験用driverを使っています。共有build adapterの変更や、従来CIで断続的に出る`No Config matched`の原因解消を示す結果ではありません。

実MAPの`Delete Symbols`は通常app 1,957件、boot 150件でした。appはFreeRTOS heap 320KiB、追加TLS heap 248KiB、framebuffer `0x85E000–0x87FFFF`を維持し、一般BSSを`0x703EC–0x7C5FB`へ移した結果、低位RAM末尾14,852B・追加heapとframebuffer間45,752Bを確保しています。MAP SHA-256は`432fa61261e6a5fe358554a664c0ea00518f1182e22387392da968212d1a0d58`です。実機での起動・性能は未確認です。

build前のapp `.cproject` SHA-256は`bf852ffafca41d069b31ec09d77fd6b7c1daa6f0640299de8471999793e5e38f`、出力app ABSは`692b8245e537932df74d2f5889c746baea2e137739f0f98588ccd5c99fdf4484`、boot ABSは`c0dea2701bd6a0e3094b603e65e45d78f506676101b178b1386d1e4e61e5186a`です。

privateログ・全入力metadata hash・生成物manifest・RAM照合JSONは`C:\ai\codex\tmp\common170-rx72sw-cold-cdt-20261015\run-20261015-174631`に保存しました。開始前のmetadataとRunner ID 3の`paused=false`へ復元したことも確認しました。

## RX65N通常software appとbootの起動経路比較

CI #11380のnative job #71155は、RX72N成功後にRX65N bootの`No Config matched`で停止しました。同じログにはRCCorePluginの初期化例外もあります。host共通排他を使用した状態でも再発しており、根本原因は未確定です。一方、通常RX65Nのjob #71161と署名付きnormal bundleのjob #71158は成功しました。

続いて通常RX65Nの同じソース・6 metadataを使い、旧Renesas `project import/build`分離経路と、同じe2studio-cliから標準CDTを1 JVMで呼ぶ経路をcold buildで比較しました。結果は両方ともapp／bootのABS・MAP・MOT生成成功でした。今回は構成認識エラーを再現できていないため、nativeの停止原因を解消したとは判断しません。

| 通常RX65N比較 | Renesas分離経路 | 標準CDT 1 JVM |
|---|---|---|
| 返却code／生成物 | 0／両project成功 | 0／両project成功 |
| MAP削除symbol: app／boot | 2,019／147 | 2,019／147 |
| No Config／plugin null | いずれもなし | いずれもなし |
| workspace保存警告 | あり | なし |

比較は旧helper `ce8d3cdd`と、標準CDT試作helper SHA-256 `a468c5813bc6a97a52d42c472223e3158b7ad4c667d68881635df659b3e4b5f6`を使用しました。後続のstream待機上限・timeout時の厳格停止処理は、この比較後の修正であり別のmock試験・CIで検証します。比較前の標準CDT試作版ではWindows host cohort 399件成功（39 skip）。その後の待機上限修正を含むcohortは400件成功（39 skip）で、追加したcallerの例外・metadata復元・入力拒否試験も確認しています。

全ログ・metadata hash・生成物manifestは`C:\ai\codex\tmp\common170-rx65-cli-route-ab-20261015\run-20261015-185048`に保存し、19:07:13 JSTにmetadataとRunner ID 3の受付状態を復元しました。実機I/Oは行っていません。

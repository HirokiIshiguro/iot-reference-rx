# 共通化後のlinked image確認（2026-10-15）

実CI／ローカル出力のABS・MAP・生成commandを保存し、ELF symbol/sectionと逆アセンブルを照合しました。最初の表はplaceholder credentialsを含むsource-only診断imageの証拠であり、実機へ書き込む正式成果物には使用しません。後半に、clean sourceからのgeneric public-signer正式生成を区別して記載します。

| 対象 | source / job | 実linked imageの確認 |
|---|---|---|
| native Transport 3環境 | `353151236ada48ff4d925b9d94270e09c9900bef` / [#71102](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/71102) | 全3 compile/link成功。保存configはheap clear=1、実`vPortFree`にzero＋`SSTR.B`。`xRecorderData`は各12,932B |
| boot 3環境 | `233d3377efa4ff1aba5f44e83f38c3c863f36ddc` / [#71111](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/71111) | 全3 compile/link成功。BSP libc heap各1,024B、hardware reset vector `FFFFFFFC→FFFC0000`。compiler/library generatorにgoptimize、branch指定なし＝default24 |
| native 18構成のmetadata | 同上 / #71111 | 全18構成の生成・source selection検査成功 |
| RX671 standalone OTA provisioner | 同上 / #71111 | `e2studio-cli.exe`経由の実build成功。3環境generic public-signerの正式生成とは別の証拠 |

native appのreset slotは3環境とも`FFFBFFFC`です。FreeRTOS heapの実予約はRX72N=320KiB、RX65N=256KiB、RX671=208KiB。RX671の208KiBはnative/OTA profile専用の既存overrideで、通常appの256KiBと区別します。

| image | ROM `PFRAM2` | SRAM `RPFRAM2` | copy size |
|---|---|---|---|
| RX72N native | `FFE63CCB` | `0005325C` | 304B |
| RX65N native | `FFF60EBE` | `000031F4` | 303B |
| RX671 native | `FFF6CC83` | `0004BE98` | 308B |
| RX72N boot | `FFFD0789` | `0001BB20` | 308B |
| RX65N boot | `FFFCE3CA` | `0001B480` | 308B |
| RX671 boot | `FFFCE6D8` | `0001A620` | 308B |

全6 imageでFAW／bank selectのbusy wait helperはSRAM側に配置されています。`R_FLASH_Open`先頭のcallからcopy helperへ到達し、ROM source・SRAM destination・実sizeをregisterへ渡す`SMOVF`まで確認しました。実機でcopyが実行されたことや、現在のbank／RAM内容を測定した証拠ではありません。

SCについては、現在の生成pluginが既存headerのMDF propertyだけをASTで更新することと、選択済みLTS MDFにheap-clearを0へ戻すpropertyがないことを確認しました。GUI Generateの実行は未観測です。Kernelの実解放領域が消去されることも、コード生成確認と実機観測を分けて扱います。

通常5 appとnativeの最終候補build、実機IDT、OTA MQTT 3ケース、終了reset/quiet確認は引き続き残件です。旧snapshotの結果をこれらの合格へ流用しません。generic public-signerの正式生成は、後述の`4b3fa449`で3環境とも完了しました。

## Generic maintenance profileの実build追跡

`d6352a6d` のRX72N保守用profileは、appがCDT projectとして認識されず停止しました。import前後に保存したmetadataは同一でしたが、生成profileに`<?fileVersion 4.0.0?>`がありませんでした。インストール済みCDTの`XmlProjectDescriptionStorage.createStorage()`は最初のDOM nodeにprocessing instructionを要求します。Python XML serializerで失われたprologを保持した`2cf0ce05`では、同じRX72Nのbootと保守用appが実際にcompile/link成功しました。他の経路で観測したbootの構成未検出まで解決した証拠にはしません。

この実imageで後段の旧秘密鍵marker検査が停止しました。MOT再構成とABSの7箇所はすべて、Mbed TLS原本の`pkparse.c`／`pkwrite.c`が使用するヘッダだけの文字列で、直後はNUL（4箇所）または改行＋NUL（3箇所）でした。鍵本体・END markerは含みません。製品側の検査はこの形だけを許可し、payload付き・非終端・途中で切れたmarkerは拒否します。manifestも「marker不在」から「PEM payload不在と検査policy」へ変更し、consumerが実MOTを再検査します。credential header空化、local override除去、注入用環境変数除去は維持します。

`2cf0ce05`の保存済みMOT／ABSは修正後のoffline検査を通過しました。その旧成果物を流用せず、clean source `4b3fa449f194c3df67c84bc4050303de7f85464e`から3環境を改めて正式生成しました。

| standalone保守用app | 正式生成完了（JST） | actual reset vector | MDE / 初期bank |
|---|---|---|---|
| RX72N | 2026-10-15 14:37 | `FFE00300` | `FFFFFF8F` / 0 |
| RX65N | 2026-10-15 14:43 | `FFF00300` | `FFFFFF8F` / 0 |
| RX671 | 2026-10-15 14:45 | `FFF00300` | `FFFFFF8F` / 0 |

全3環境で`formal=true`、`source_tree_dirty=false`、credential注入なし、standalone vector／Flash RAM mappingの実効command、MOT内source witnessと許可address範囲を検証しました。MOT・manifest・公開証明書・公開鍵の4入力が揃い、開発用signerの公開鍵も3環境で一致しました。実機I/Oは行っていません。後続CI変更を含む最終候補の成果物と、実機での公開鍵投入・署名検証成功は別途確認します。

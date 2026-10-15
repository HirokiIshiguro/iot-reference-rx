# 共通化後のlinked image確認（2026-10-15）

実CI出力のABS・MAP・生成commandを保存し、ELF symbol/sectionと逆アセンブルを照合しました。以下はsource-only buildの証拠です。placeholder credentialsを含む診断imageであり、実機へ書き込む正式成果物には使用しません。

| 対象 | source / job | 実linked imageの確認 |
|---|---|---|
| native Transport 3環境 | `353151236ada48ff4d925b9d94270e09c9900bef` / [#71102](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/71102) | 全3 compile/link成功。保存configはheap clear=1、実`vPortFree`にzero＋`SSTR.B`。TraceRecorderは各12,932B |
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

通常5 appの最終build、generic public-signer 3環境の正式成果物、実機IDT、OTA MQTT 3ケース、終了reset/quiet確認は引き続き残件です。旧snapshotの結果をこれらの合格へ流用しません。

## Generic maintenance profileの実build追跡

`d6352a6d` のRX72N保守用profileは、appがCDT projectとして認識されず停止しました。import前後に保存したmetadataは同一でしたが、生成profileに`<?fileVersion 4.0.0?>`がありませんでした。インストール済みCDTの`XmlProjectDescriptionStorage.createStorage()`は最初のDOM nodeにprocessing instructionを要求します。Python XML serializerで失われたprologを保持した`2cf0ce05`では、同じRX72Nのbootと保守用appが実際にcompile/link成功しました。他の経路で観測したbootの構成未検出まで解決した証拠にはしません。

この実imageで後段の旧秘密鍵marker検査が停止しました。MOT再構成とABSの7箇所はすべて、Mbed TLS原本の`pkparse.c`／`pkwrite.c`が使用するヘッダだけの文字列で、直後はNUL（4箇所）または改行＋NUL（3箇所）でした。鍵本体・END markerは含みません。製品側の検査はこの形だけを許可し、payload付き・非終端・途中で切れたmarkerは拒否します。manifestも「marker不在」から「PEM payload不在と検査policy」へ変更し、consumerが実MOTを再検査します。credential header空化、local override除去、注入用環境変数除去は維持します。

`2cf0ce05`の保存済みMOT／ABSは修正後のoffline検査を通過しました。ただし、その旧成果物を新sourceの正式生成として扱いません。変更後のclean sourceからの再生成と、3環境の実機確認は引き続き必要です。

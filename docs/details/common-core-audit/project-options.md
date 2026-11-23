# e2 studio project / compiler-linker comparison

3環境のプロジェクト構造・設定は完全には共通化されていません。RX65N native IDTの実ビルドではbank選択処理のRAM写像が欠落していることを確認しました。実機のPC・書込み先・暴走は未測定です。

**証拠の範囲:** 宣言は正本 `44232ef62ea5be65161b95ae9741c6da555c7f3b` の `git show`、実効設定は保存済みCC-RXコマンド/MAPです。GUIのProject Explorerは操作・観測していないため、下記階層は `.project` とGit treeからの再構成です。新しいビルド・実機操作・コード変更は行っていません。全宣言・include/macro/exclude・metadata SHA・MAP section/symbolの詳細は [project-options.json](project-options.json) に保存しています。

## 共通点と差

| 項目 | RX671 app | RX65N app | RX72N app | 判定 |
|---|---|---|---|---|
| e2 studio構成 | CCRX / HardwareDebug 1構成 | 同左 | 同左 | 共通 |
| CI既定e2 studio | 2026-04.2 / e2studioc | 2026-04.2 / e2studio-cli | 2026-04.2 / e2studioc | 同版、入口が異なる |
| app実compiler flags（既存IDT） | rxv3 / fpu / dpfpu / c99 / debug / goptimize | rxv2 / fpu / c99 / debug / goptimize | rxv3 / fpu / dpfpu / c99 / debug / goptimize | ISA・DPFPUは観測差。DPFPUの必要性・共通化範囲は要確認。RX72Nは旧試作の証拠 |
| Common/Demos/Middleware | repo rootへのlinked folder | project内の通常Git tree | repo rootへのlinked folder | 共通ソース参照方法が異なる |
| include宣言数 | 93 | 83 | 88 | 表示pathとして66項目共通。実体一致を意味しない |
| SC RTOS選択 | freertos.kernel | freertoslts | freertoslts | 宣言差 |
| SC / CDT bank宣言 | single | single | dual | RX65NのBSP dual宣言と不一致 |
| baseline code / app reset vector | FFE00000 / FFFFFFFC | FFF00300 / FFFBFFFC | FFE00300 / FFFBFFFC | RX671 baselineがlinear、他appはbootloader併用 |
| compiler macro | 共通6種＋__FUNCTION__ / little=1 | 共通6種＋little | 共通6種＋little | mbedTLS/LittleFS/assert/memory等は概ね共通 |

`MBEDTLS_CONFIG_FILE`, `LFS_THREADSAFE`, `CONFIG_FREERTOS_ASSERT_FAIL_ABORT`, `CONFIG_MEDTLS_USE_AFR_MEMORY`, `MBEDTLS_ERROR_C`, `MBEDTLS_ALLOW_PRIVATE_ACCESS` は3app共通です。little endianを示すmacroはありますが、抽出した実compilerコマンドには明示的な `-endian` 指定がありません。ABI全項目やcompiler継承defaultの完全同一性までは確定していません。DSP用のbig endian属性はDSP assemblerの設定であり、CPU appのendianとは区別します。

bootloaderはRX671/RX65Nがrxv2・単精度FPU、RX72Nがrxv3・DPFPUを宣言しています。RX671 appとbootのISA宣言は異なりますが、これだけで不具合とは判定しません。RX72N bootだけcompiler optimize level2を明示、appはgoptimize、RX671/RX65N bootは同項目未明示です。実コマンドの継承defaultまで同じかは未確認です。

## Project Explorer階層の再構成

- RX671/RX72N: project直下の `src` は実folder、`Common` / `Demos` / `Middleware` は `AWS_IOT_MCU_ROOT=PARENT-3-PROJECT_LOC` 経由のrepo root linked folder。`src/application_code/include` はroot Demos/include、`ports` はroot Common/portsへリンクします。
- RX65N: project直下に `Common` / `Demos` / `Middleware` の実treeを持ち、`AWS_IOT_MCU_ROOT=PROJECT_LOC`。`src/application_code/include` はproject内Demos/includeですが、`ports` は `AWS_IOT_MCU_REPO_ROOT=PARENT-3-PROJECT_LOC` でroot Common/portsを参照します。共通部をproject内コピーとrootリンクで混在させています。
- RX671: WHDとTraceRecorderのリンクはboard projectの `external` 配下を参照。通信・計測依存としての追加階層です。
- RX671/RX65N boot: `src` と `lib/rx_bootloader` がsource entry。RX72N bootは `src` のみで、旧 `AFR_HOME=PARENT-5-PROJECT_LOC` と `src/src/tinycrypt→AFR_HOME/libraries/3rdparty/tinycrypt` が残っています。現在のrepo配置でAFR_HOMEはrepo rootを指しません。GUIでの解決・表示は未確認です。

`sourceEntries` と `.project` resource filterにも差があります。RX671/RX72Nはroot FreeRTOS port.c / coreMQTT-Agentの一部を除外してCommon patchesを使用する一方、RX65Nには同じsource exclusionがありません。submoduleのpinと実compile対象の比較は [submodule-graph.md](submodule-graph.md) の監査と合わせて判断します。

## IDTの変換と既存実ビルド

RX671 baselineは意図的にlinearです。`build_rx671_ota_images.py:205–306` が一時的にdual-bankへ変換し、`PFRAM2=RPFRAM2`、app先頭FFF00300、app vector FFFBFF80/FFFBFFFC、version / OTA / heap / network-buffer等のmacroを追加します。IDTはこのproduction OTA変換を使い、OTAE2E以外では `RX671_OTA_RUNTIME_ENABLE=0` にします。provisionerは別のlinear profileで、通常FWと同じFFE00000/FFFFFFFCです。

| 既存ビルド | PFRAM2（ROM） | RPFRAM2（RAM） | flash_toggle_banksel_reg | 証拠条件 |
|---|---|---|---|---|
| RX671 IDT app / job70882 | FFF6C349..FFF6C47C / 0x134 | 0004F4B8..0004F5EB / 0x134 | 0004F552 | source44232 / clean |
| RX671 IDT boot / job70882 | FFFD0BB5..FFFD0CEC / 0x138 | 000222B8..000223EF / 0x138 | 00022354 | source44232 / clean |
| RX65N IDT app / job70856 | FFF5E91A..FFF5EA44 / 0x12B | 00003208 / size0 | FFF5E9B0 | source7536258a / clean、mainとtree同一 |
| RX65N IDT boot / job70856 | FFFC974F..FFFC9886 / 0x138 | 000231AC..000232E3 / 0x138 | 00023248 | 同上 |
| RX72N IDT app / run-12jc03pz | FFE6ED56..FFE6EE91 / 0x13C | 00053254..0005338F / 0x13C | 000532F2 | source232300f0 / dirty、旧試作参考 |
| RX72N IDT boot / run-12jc03pz | FFFD3443..FFFD357C / 0x13A | 000240B0..000241E9 / 0x13A | 000240B0 | 同上、Flash FIT4.50系 |

CC-RX linkerは上記全MAPでV3.07.00です。RX671通常CI [job70875](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70875) のMAPはsource44232、PResetPRG=FFE00000、RESETVECT=FFFFFFFC、PFRAM2/RPFRAM2なしでlinear baselineに一致しました。RX65N [job70874](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70874) はsource44232で成功ですが、CI artifact宣言にMAPがなくMAP単体GETは404です。通常CIの実RAM写像との差はまだ確定していません。追跡補足として通常CI [job70956](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70956)（pipeline11335 / sourceec7522a9 / software / Windows runner / 13:38–13:44成功）のtraceから実workspaceを特定しました。同workspaceのHEADはec7522a9でしたが、software app・TSIP app・bootのHardwareDebug directoryはいずれも既に存在せず、MAPは残存していません。ec7522a9とmain44232のProjects/Common/MiddlewareのGit tree差はありません。**通常MAP artifact未収録・追跡先の現残存なし**として終了し、再生成によるRAM写像補完を推測で確定しません。RX72Nの現在mainの実MAPも未取得です。

## 確定した配置差と未確認事項

RX65N appの宣言には `RPFRAM2` sectionはありますが `PFRAM2=RPFRAM2` がありません。native IDTは `-PreserveLinkerLayout` を指定してこの宣言を実linkerコマンドへ反映します。実MAPでもRAM size0、bank選択symbolはCF内です。PKCS11のsource6caa2a2bでもRPFRAM2 size0、PFRAM2 size0x12Bを確認しました。

Flash FIT5.22はCF_ENABLE=1で `R_FLASH_Open→R_FlashCodeCopy` を実行し、Type4/APP_SWAP/dual設定から `FLASH_IN_DUAL_BANK_MODE=1` となり、PFRAM2のサイズを基準にRPFRAM2へcopyする実効条件です（`r_flash_rx_if.h:260,284–285`, `r_flash_rx.c:117–118,172–181`）。job70856の想定copy先は00003208..00003332です。予約サイズは0ですが、MAP Mapping Listの全44 sectionを抽出し、size>0の全intervalと想定copy範囲を照合した結果、**静的sectionとの重複はありません**。SU/SI/B_n/R_nおよびゼロ長sectionを含む全RAM 15項目と判定式・全section一覧をJSONへ記録しました。直前Rは00001578..00003207、次のBは00800000..00807B2Fです。runtime heap・stack・PC・実メモリ書込みは未測定であり、overwriteや暴走を観測したとは扱いません。

RX671 bootは逆に、宣言 `.cproject` にPFRAM2写像がない一方、既存実linkerコマンドに `PFRAM2=RPFRAM2` とPFRAM2/RPFRAM2 sectionが追加され、MAPでもRAMに置かれています。production helperはappにPFRAM2写像を明示追加し、IDTはbootの元rom/startを読み `.cproject` と `.rcpc` を一時書込みするため、scriptによる変更も確認対象です。調べたboot経路にはPFRAM2を明示追加するpatchはありませんでしたが、最終コマンドだけで追加段階は特定できません。IDT/helperの一時書込み・既存生成metadata・e2 studio/SC再生成の前後差を未採取なので、SC/importだけに原因を限定しません。RX65N通常CIはPreserveLinkerLayoutを指定しないため同じ補完の可能性はありますが、通常MAP取得前に断定しません。

RX72N旧Flash FIT4.50 bootでも `R_FLASH_Open→R_FlashCodeCopy`、CF_ENABLE/dual条件でPFRAM2サイズのRAM copyという原則は同じです（現main `r_flash_rx.c:89,112,145–151`）。その旧実MAPではRAM写像が成立しています。MCU差・driver版差・リンク段階での補完を混ぜず、次の検証対象を決める必要があります。

RX65Nの**通常OTA経路でappが直接BANK_TOGGLEすることは確認できません**。共通OTA PALのRX65N分岐はbootloaderへ切替を委譲します。旧FWUP経路もuser swap callbackを選び、RX65N callbackは成功を返すだけです。driver内にcommand/symbolが存在しても実呼出しを示しません。経路と正本行はJSONの `source_references` と `rx65n_OTA_bank_toggle_static_paths` に集約しています。

[ユーザー提示のRenesas公式type4コメント](https://github.com/renesas/rx-driver-package/blob/bcc409d331b0bff68d4b09bf6fc41376f75d42bc/source/r_flash_rx/r_flash_rx_vx.xx/r_flash_rx/src/flash_type_4/r_flash_type4.c#L507)では、BANKSELはbank0に関連し、BGO/interrupt使用時もRAM上の処理が完了までpollしてから戻ることで、bank0書込み中のbank0実行を避ける必要性を説明しています。これはRAM配置の要件であり、RX65N appが今回その処理を実行してfaultした証拠ではありません。

優先確認は、RX65N通常CIのeffective MAP保存、appからのbank操作呼出し有無とR_FlashCodeCopy先の実測、宣言/SC/実linkerの差の再現性です。配置差は確定していますが、本監査では修正や新しい実機実験を行っていません。

## 参照

- [正本source44232ef6](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/tree/44232ef62ea5be65161b95ae9741c6da555c7f3b)、[IDT builder](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/blob/44232ef62ea5be65161b95ae9741c6da555c7f3b/tools/build_rx72n_idt_transport.ps1)、[RX671 OTA profile](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/blob/44232ef62ea5be65161b95ae9741c6da555c7f3b/tools/build_rx671_ota_images.py)
- [RX65N native job70856](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70856)、[RX671 native job70882](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70882)
- [rules source6dda26f2](https://gitlab.saffti.jp/oss/claude-codex-gemini-index/-/blob/6dda26f21872602a6f448ac39ddba5ddd274d04c/docs/development/renesas-e2studio-cli.md)、[hardware-config Tool Paths](https://gitlab.saffti.jp/oss/infra/hardware-config/-/blob/56fdb925e8e8b0cc5c2272c688d923423727d04c/README.md#tool-paths--ツールパス)

## MCU能力の仕様確認

[RX671 datasheet](https://www.renesas.com/en/document/dst/rx671-group-datasheet-rev100)はRXv3と64-bit倍精度FPUを記載し、[RX72N仕様](https://www.renesas.com/en/products/rx72n)もRXv3・倍精度FPU、[RX65N仕様](https://www.renesas.com/en/products/rx65n)はRXv2・単精度FPUです。現ISA/DPFPU差は能力に対応する許容差ですが、その命令subset使用が全profileで必須という主張ではありません。統一設定の選択は対象MCUと検証結果で判断します。

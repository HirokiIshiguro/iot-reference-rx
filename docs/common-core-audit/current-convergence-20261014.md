# 共通化WIPの3環境比較（2026-10-14）

版・共通app設定・OSS参照は3環境の共通rootへ移行しました。**共通化WIPであり、全環境のqualification完了を示しません。** 10月15日にnative Transport 3環境とboot 3環境の実link・Flash RAM copy・heap clear生成codeを確認しました。[最新linked image証拠](linked-image-evidence-20261015.md)を参照してください。本表内の旧imageや変更前flagsは記録時点のsnapshotです。通常5 appの最終build、正式保守provisioner、実機IDTには残件があります。

対象は[Issue #170](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/170)、[Draft MR !223](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/223)の作業中treeです。公開済み基準は[WIP `65c59407`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/commit/65c59407b0a4b0c9048ba8ed8c700b3841090b3d)で、本表にはその後のRX65N cold生成・Cellular include・TSIP key adapter選択、boot最適化、全8 branch／link順／診断出力統一の修正も含みます。後続commitで固定するまで、公開基準と作業中変更を区別します。

移行前の「揃っていない」一覧は[2026-10-07監査](README.md)です。本表は現ファイルの設定、静的model、生成されたcompiler/linker入力、実linked image、未観測の実機を分けています。

## 版・管理・共通設定

RX671はsoftware app 1個、RX65N／RX72Nはsoftware・TSIP app各2個です。これら5 appと各MCUのbootloader 3個、計8 project metadataを確認しました。bootloaderはbare-metalで、FreeRTOS Kernelを実行するprojectではありません。

| 項目 | RX671 | RX65N／BG96 | RX72N／Ethernet | 根拠・範囲 |
|---|---|---|---|---|
| FreeRTOS Kernel | V11.3.0 | V11.3.0 | V11.3.0 | [manifest](../../manifest.yml)、共通Kernel `task.h`、5 appのSC selector/backup guard |
| Plus-TCP / coreMQTT / Agent | 4.4.1 / 5.0.2 / 2.0.0 | 同じroot pin | 同じroot pin | 版は共通。通信方式に必要なsourceだけを選択 |
| corePKCS11 / coreJSON / coreSNTP | 3.6.4 / 3.3.1 / 2.0.0 | 同じroot pin | 同じroot pin | 版と利用の有無を混同しない。その他AWS librariesはmanifest・[原本照合](submodule-conformance-20261014.md)参照 |
| Mbed TLS software | 3.6.4 | 3.6.4 | 3.6.4 | 共通submodule `Middleware/3rdparty/mbedtls` |
| Mbed TLS TSIP | 共通rootには3.2.1派生を保持、TSIP appなし | 3.2.1派生 | 3.2.1派生 | backendごとの統一。software/TSIPを同版にはしていない |
| Flash FIT / BSP | 5.31 / 7.71 | 5.31 / 7.71 | 5.31 / 7.71 | app/bootともRDP 1.50原本をVendor link参照。設定headerは製品側 |
| TSIP FIT | 通常appでは未使用（共通RDP内は1.24） | 1.24 | 1.24 | 同じ公式RDP pin。RX72Nの旧custom hook selectorを撤去しSC/QEの72設定を同期。原本1010 file bytesを照合 |
| bootloader pin | `231a0cc680525be3530a7bb64862d099e5a401ec` | 同左 | 同左 | 今回確認したmain pinを固定。「将来もlatest」を意味しない |
| bootloader格納先 | `lib/rx_bootloader` | `lib/rx_bootloader` | `lib/rx_bootloader` | 各boot projectのsubmodule。同じpin、旧配置の本体コピーなし |
| LittleFS | v2.11.3 / disk 2.1 | 同左 | 同左 | app/bootが同じroot submoduleを参照 |
| 共有store geometry | base `0x00100000`、8192B、read/prog=4、block=128、count=64、cache=64、lookahead=16、cycles=500 | 同左 | 同左 | 5 app製品config、3 boot公開config、8 RM config。実機の既存volume互換は未検証 |
| OS interrupt priority | Kernel=1 / MAX_SYSCALL=4 | 同左 | 同左 | 5 app `FreeRTOSConfig.h`／SC。Flash BGO製品callback priority=3 |
| boot interrupt priority | Flash=14 / SCI=15 | 同左 | 同左 | 3 bare-metal boot config。appのOS priorityとは役割を分ける |
| OS共通値 | minimal stack=768、TLS slots=3、32bit tick、daemon startup hook=0 | 同左 | 同左 | heap/CPU port等の許容差は後表 |
| FreeRTOS heap / SC表示 | 256KiB | software/TSIPとも256KiB | software320KiB / TSIP368KiB | 実heapを維持し、5 appの保存SC selectorと一致。MCU容量／backendによる許容差 |
| FreeRTOS assert | 常時有効 | 同左 | 同左 | 非unit製品appは`vAssertCalled`経由のcritical-loop。unitの既存`TEST_ABORT`優先は維持 |
| FreeRTOS解放時zero clear | 1 | software／TSIPとも1 | software／TSIPとも1 | 全5 appの`configHEAP_CLEAR_MEMORY_ON_FREE=1`を静的照合。bootはFreeRTOS未使用のため対象外。実解放後のbyte消去は未観測 |
| BSP標準library heap | app=8KiB / boot=1KiB | 同左 | 同左 | ユーザー決定。全8 BSP config・SC selector・QE metadataが一致。FreeRTOS heapは別枠 |
| CF / DF BGO | 1 / 1 | 1 / 1 | 1 / 1 | 全8 Flash config／SC宣言。実機BGO完了は未観測 |
| ROM命令cache | 1 | 1 | 1 | ユーザー決定。全8 BSP configとSCが一致。実registerは未読取り |
| normal app bank | dual、app vectors `FFFBFF80/FFFBFFFC` | 同左 | 同左 | 5 app BSP/SC/IDE device設定。`BSP_CFG_CODE_FLASH_BANK_MODE=0`はdual選択 |
| boot bank | dual、hardware vectors `FFFFFF80/FFFFFFFC` | 同左 | 同左 | 3 boot公開config、BSP/SC/device設定 |
| native bank方針 | dual | dual | dual | native helper/profileは通常projectのdual layout/RAM mappingを継承。共通化後の全native image/IDTは未完 |
| 保守provisioner方針 | dual | dual | dual | 共通public signer helper/profileがstandalone hardware vectorsを使う。host guard確認と各実image/実機を区別 |
| 通常OTA bank切替 | appが担当 | appが担当へ変更 | appが担当 | 製品OTA PALの`FLASH_CMD_BANK_TOGGLE`呼出し。RX671通常診断profileはOTA既定0 |
| boot信頼設定 | LittleFS公開鍵、ECDSA必須、組込鍵fallback=0、raw DataFlash install=0 | 同左 | 同左 | 3公開boot config。実鍵投入／署名OTA試験は未完 |
| OSS管理 | git submodule | git submodule | git submodule | [`.gitmodules`](../../.gitmodules)。RX65N project内コピーをroot linkへ移行 |
| 原本一致と例外 | fixed pinに利用側body差なし。WHD CC-RX forkを参照 | TSIP forkを参照 | TSIP forkを参照 | [全root／再帰参照の照合と限界](submodule-conformance-20261014.md)。forkとの一致はstock upstreamとの無改造一致ではない |
| e2 studio起動 | `e2studio-cli.exe` | 同左 | 同左 | 共通launcher。RX65Nも毎回metadataからcold生成、古いmake cache再利用を撤去 |
| SC RTOS選択 | `freertoslts` / Kernel 11.3.0 | 同左 | 同左 | 製品descriptor `202604.00-LTS-saffti-1.0.0`は設定header専用。Renesas公式package名とは区別。model parse/guard確認済み、GUI Generate未観測 |
| SC / QE Kernel入口 | `FreeRTOS_Kernel202604.00-LTS-saffti-1.0.0` | 同左 | 同左 | 全5 appでSC component idとQE Segment.componentを同期。旧11.1／202406LTS参照を解消 |

主要固定参照はKernel `9b777ae5c5b8e9e456065a00294d1e5f5f9facf5`、software Mbed TLS `c765c831e5c2a0971410692f92f7a81d6ec65ec2`、TSIP `6d8fb19d71cfdf17acbdf7382d65ec899e750118`、RDP `bcc409d331b0bff68d4b09bf6fc41376f75d42bc`、LittleFS `6cb4e86540eca0d9ba62500a298385c9d863c8be`です。WHDは[承認済みCC-RX目的のfork](https://gitlab.saffti.jp/oss/import/github/infineon/wifi-host-driver/-/merge_requests/1)のmerge pin `d5de9ee04e103d727d7ed529a008c24b9332c4e8`を参照します。41 rootの完全な一覧・最新refs取得時刻・未checkout nestedの確認境界は[原本照合表](submodule-conformance-20261014.md)にあります。

## compiler/linkerの共通値と差

宣言だけで一致を判断せず、取得済みの実compiler response・linker optionとも照合しました。差をすべて「MCU差」として自動承認したわけではありません。

| 項目 | 現値・差 | 判断 |
|---|---|---|
| toolchain / C言語 | CC-RX V3.07.00、C99が8 project共通 | 実buildのtool/response確認 |
| compiler最適化level | 全8でlevel2。3 bootで明示、5 appは公式plugin既定2 | 明示／既定の違いを有効値と分ける |
| compiler/assembler global最適化 | 全8で`-goptimize`有効へ統一 | 2026-10-14のユーザー決定。3 boot metadataをappと同値へ変更 |
| linker最適化 | 全8でoptimize allへ統一 | 3 bootの旧`-nooptimize`をmetadataで解除。変更後の実生成／再linkと配置確認は別段階 |
| endian | compiler Commonは既定little、実linked5 imageもlittle/MDE=FFFFFF8F | `.cproject`の`dsp.option.endian.big`はDSP Assembler用。旧監査のcompiler bigという集計と区別 |
| ABI / bit order / packing | 8 metadataに個別overrideなし、同compiler既定 | 必要WHD pack対応は目的限定fork内。実wire layout試験と全ABI qualificationは別 |
| TraceRecorder | 全5 appで共通`Middleware/3rdparty/TraceRecorderSource`、v4.11.0/pin`2f888cb9`、原本29 C source＋製品共通config/FreeRTOS include facade | task生成前initialize、全main profileで`TRC_START`。実Kernel hook・RXv2/v3 mask・原本sourceのhost前処理を確認。新MAP/RAM/stack余裕と実streamは未確認 |
| IRQ / assert / threading設定 | app IRQ1/MAX4、共通assert/allocator定義、LFS_THREADSAFE無効 | adapterの公開API＋製品mutex。TSIP用configとtransportだけbackend差 |
| Flash RAM写像 | 全8に`PFRAM2=RPFRAM2`、CF_RUN_FROM_ROM=1/dualでもconfig busy wait専用helperをRAM配置 | 宣言8と実image5を分ける。一般Flash関数が全部RAMにあるという意味ではない |
| vector / Code Flash開始 | app vectorはFFFBFF80/FFFBFFFC、bootはFFFFFF80/FFFFFFFC。app開始RX671/RX65N=FFF00300、RX72N=FFE00300、boot=FFFC0000 | roleとMCUのbank容量による配置差。通常appとstandalone provisionerを混同しない |
| RAM / heap / buffer配置 | FreeRTOS app heap RX671=256KiB、RX65N=256KiB、RX72N software=320KiB/TSIP=368KiB。BSP library heapはapp=8KiB/boot=1KiB。RX65N／RX72Nは内蔵拡張RAMを使用し、RX72NにはLCD/Ethernet buffer sections | FreeRTOS heap等はRAM容量・backend・周辺機能に対応する許容差。BSP heapの役割別値は3 MCUで共通 |
| ISA / FPU / TFU | app/bootともRX671/RX72N=RXv3/DPFPU、RX65N=RXv2/single FPU。RX72NだけTFU | RX671 bootの旧RXv2 subsetを同MCU appと同値へ変更。MCU能力差を保持 |
| branch width | 全8 branch=24へ統一 | ユーザーの最終決定。公式default24を正式Common enumで明示し、compilerと標準library generatorの共通optionを1か所で指定 |
| link input order | 全8 e2 studio標準自動順（`useCustomLinkageOrder=false`）へ統一 | ユーザー決定。旧manual object/library listを撤去。source selection・生成標準library・明示section配置を使用 |
| 診断出力 | 全8 `show=all`、console MULTIへ統一 | 個別show overrideを撤去し、実subcommandを複数行で記録。section checkと全warning出力は保持 |
| 通信source / include | RX671=WHD/SDIO、RX65N=公式BG96＋Cellular private dirs、RX72N=Ethernet/Plus-TCP。PKCS11 key adapterは共通1source、transportはbackend別1source | 機能差として必要。不要な別通信sourceを混入させない |
| 共通tinyCBOR source | 原本Makefileのfreestanding 5source、hosted JSON/stdio/open_memstream等を除外 | 実caller2種のAPI closureをHost link/roundtripで確認、OSS body改変なし |
| boot/Flash driver参照 | provider本体はVendor link、製品configとpinsのみlocal | Project Explorer階層はmetadataから再構成。GUI表示自体は未観測 |
| CC-RX compatibility定義 | RX671だけ`__FUNCTION__=__func__`を持つ | WHDのcompiler対応用途。無関係なprojectに定義を追加していない |
| warning設定 | `nomessage`追加なし、link warning2220のinformation downgradeを撤去 | warning残件は分類して保持。警告ゼロやOSS改造を合格条件に置き換えない |

最適化の役割差とRX671 bootのISA subset差は、ユーザーの「bootloaderもappと同じ最適化へ統一」の決定により解消する設定へ変更しました。`.cproject`を情報源とし、ignored生成物の`.rcpc`やmakefileへ別の値を手書きしません。変更後の生成入力・再link・実機動作を順に確認します。

| boot project | 変更後のmetadata | 今回変更前に取得した実compiler flags | MCU能力に必要な差 |
|---|---|---|---|
| RX65N | RXv2 / FPU / DPFPU無効 / TFUなし / gopt有効 / linkall | `-isa=rxv2 -fpu` | RXv2・single FPUを保持 |
| RX671 | RXv3 / FPU / DPFPU有効 / TFUなし / gopt有効 / linkall | `-isa=rxv2 -fpu` | TFUなしを保持。旧ISA subsetとDPFPU無効はMCU能力による必須差ではない |
| RX72N | RXv3 / FPU / DPFPU有効 / TFU intrinsic / gopt有効 / linkall | `-isa=rxv3 -fpu -dpfpu -tfu=intrinsic` | RX72NのTFUを使用 |

全8の有効値と明示／plugin既定の区別は[公開option matrix](current-convergence-20261014.json)に収録しています。branch／入力順／診断出力の統一も設定へ反映しました。ignored生成物に残る過去の値と、新metadataの指定を区別し、cold生成でcompilerとlibrary generatorの両入力を確認します。

2026-10-15のユーザー決定により、FreeRTOS解放時zero clearを全5 appで有効（`configHEAP_CLEAR_MEMORY_ON_FREE=1`）へ変更しました。3環境nativeの変更後buildと実`vPortFree`のzero／`SSTR.B`を確認しました。実機での解放領域のbyte消去は未観測です。保存済みSC 8 file・MDF 14 file・QE 8 fileに同flagの別selector定義はありません。生成pluginが既存headerのMDF propertyだけを更新することも確認しましたが、実GUI Generateは未観測です。

BSP library heapはRX671 appの32KiBを8KiB、RX671 bootの32KiBを1KiBへ変更し、他MCUと同値にしました。製品headerだけでなくSC selectorとQE metadataを更新しました。これらは予約設定値であり、実link後のheap section・RAM余裕やmalloc動作は再検証します。FreeRTOS heapはこの変更では増減していません。

FreeRTOS heapはRX671のSC表示224KiBを実設定256KiB、RX72N TSIPの表示320KiBを実設定368KiBへ同期しました。QEに独立したheap値はなく、保存SC selectorが値の情報源です。5 appのQE Kernel入口も現SC/local descriptorへ揃えました。Mdfの初期default値と保存済みのMCU別selectorを区別して照合し、実GUI Generateは別の未観測段階として残します。Kernelが参照しない旧INCLUDE名5種を除去し、RX671の有効なtimer pend／task abort delay設定も他appと揃えています。

branchの未指定defaultは24です。[公式option説明](https://tool-support.renesas.com/autoupdate/support/onlinehelp/csp/V8.13.00/CS%2B.chm/Compiler-CCRX.chm/Output/ccrx02c0501y0520.html)と、V3.07同梱Manual `R20UT3248EJ0114 Rev.1.14` p148で確認しました。同Manual p1024 §11.3と[公式Notes on Options](https://tool-support.renesas.com/autoupdate/support/onlinehelp/csp/V8.13.00/CS%2B.chm/Compiler-CCRX.chm/Output/ccrx11c0300y.html)は、branchを含むMicrocontroller Optionsをcompiler/library generatorで揃えるよう要求しています。全8 metadataには正式enum `common.option.branch.24bit`を明示しました。このdefault enumはcommandを出さないため、cold生成では両toolから旧branch32 overrideが消えたことも確認します。過去の特定エラーがbranch混在に起因したとの記録は、今回の公式資料確認だけでは確定していません。

`branch=32`は距離前提を置かない指定であり、32bit PC-relative命令を一律に使う設定ではありません。[公式Programming Techniques](https://www.renesas.cn/zh/document/apn/rx-family-cc-compiler-package-cc-rx-v3-programming-techniques) `R20AN0643EJ0101 Rev.1.01` p47の外部関数call例では、branch24は4B/6cycles、branch32は8B/7cyclesです。今回は公式default24とcompiler/libraryの同値指定へ統一しました。この例を全imageのsize・性能差へ外挿せず、linkallの短縮を含め最終imageで確認します。

標準自動順へ変更する前の実input 7 projectでは、`PowerON_Reset_PC`／`_DTBL`／`_BTBL`／`abort`のdirect providerは各1個、重複object inputは0でした。BSPは`PResetPRG`・entry symbol・固定vector sectionを持ち、初期化tableは`__sectop`／`__secend`を参照します。inputの隣接順へ依存する前提は確認されませんでした。ただし、Manual p277のとおり同名section内とwildcard sectionの配置はinput順に依存するため、再link後のentry/vector/RAM写像を確認し、旧addressやhashを流用しません。

## 静的model・実build・実機の境界

| 確認段階 | RX671 | RX65N | RX72N |
|---|---|---|---|
| 8 metadata XML、link/include、BSP/Flash/SC共通値 | 確認 | 確認 | 確認 |
| 実Eclipse CDT source選択 | 通信別選択、重複／test-tool類混入なし | 同左。fresh generated compiler inputsも照合 | 同左。両TSIP key adapterとtransport分離も確認 |
| 通常app compile/link | software診断image取得。最終option変更前 | software診断build成功、TSIP／最終option変更後は未完 | software/TSIP image取得。最終option変更前 |
| boot compile/link | 最適化変更前のimage取得。最終option変更後は再link待ち | 最適化統一後の診断build成功、branch／順／診断統一後は再link待ち | 最適化変更前のimage取得。最終option変更後は再link待ち |
| 実MAP/ABSのconfig busy wait helper SRAM配置 | 2helper実配置確認、通常診断profileのcopy initは未選択 | app link未完のため未確認 | 2app＋bootで実配置／copy routine確認 |
| normal/native/provisionerの全variant | OTA-enabled app/native/provisionerは未完 | native/provisionerを含め未完 | native/provisionerは未完 |
| 共通化WIPの実機／IDT | 未実施 | 未実施 | 未実施 |

取得した5 imageの`flash_toggle_banksel_reg`と`flash_write_faw_reg`は、実ABSのSRAM `RPFRAM2`にあり、ROM `PFRAM2`とsizeが一致します。**以下のboot 2 imageは最適化／ISA統一前のsnapshotです。** 変更後の生成・再linkではsize/addressを再確認するため、旧配置を変更後のPASS証拠には流用しません。

| linked image | RPFRAM2 (SRAM) | BANKSEL helper | FAW helper | copy初期化の実code |
|---|---|---|---|---|
| RX72N software app | `000702B4`, 316B | `00070352` | `000702B4` | Open→Copy call、ROM→SRAM `smovf`確認 |
| RX72N TSIP app | `0007CA78`, 316B | `0007CB16` | `0007CA78` | 同上 |
| RX72N boot | `0001BBB8`, 312B | `0001BC54` | `0001BBB8` | 同上 |
| RX671 software診断app | `0005E100`, 308B | `0005E19A` | `0005E100` | 現profileはOTA/provisioner/native既定0、初期化call chainは削除 |
| RX671 boot | `000222B4`, 312B | `00022350` | `000222B4` | Open→Copy call、ROM→SRAM `smovf`確認 |

4 imageではactual disasmで`R_FLASH_Open`からcopy routineへのcallと、実ROM source・SRAM destination・sizeをロードする`smovf`を確認しました。RX671診断appはOTA/provisioner/native overrideがなく、関連init/open/copy symbolはdelete記録、BSP `_DTBL`にはData4行だけがありPFRAM2 copy rowはありません。symbol不在をinlineコピー成功に置き換えていません。OTA有効／native／provisioner imageでの確認が必要です。

5 imageの実option dataはMDE=`FFFFFF8F`（dual/little）、BANKSEL=`FFFFFFFF`（imageのinitial bank0）、reset vector値は各ELF entryと一致します。これは実機の現在bank状態やコピー済みRAM内容の測定ではありません。

RX65Nのfresh生成ではsoftware 74/74・TSIP 76/76 compiler responseに公式Cellular `source/include/private`が入り、`cellular_internal.h`／`cellular_common_internal.h`欠落は解消しました。その後のsoftware診断buildはlinkまで成功しましたが、最新のbranch／入力順／診断統一後の結果はまだありません。build成功を正常起動・通信・OTA・IDT完了と扱いません。

旧main／旧native imageのIDT結果、既知MQTT version不一致のNG、今回WIPの結果は別のsource snapshotです。現WIPを「全環境検証済み」へ変更するには、残るimage build、保守鍵投入、native groups、OTA MQTT 3case、試験終了処理を各実機で確認する必要があります。

### 内蔵RAM照合（2026-10-15追補）

`00800000`から始まる領域の呼称を内蔵拡張RAMへ訂正しました。通常RAMと内蔵拡張RAMの容量・範囲は次のとおりです。standby RAMやECC RAMはこの容量表の集計に含めていません。

| MCU | 低位の内蔵RAM | 内蔵拡張RAM | 合計 |
|---|---|---|---|
| RX671 | `00000000–0005FFFF`、384KiB | — | 384KiB |
| RX65N | `00000000–0003FFFF`、256KiB | `00800000–0085FFFF`、384KiB | 640KiB |
| RX72N | `00000000–0007FFFF`、512KiB | `00800000–0087FFFF`、512KiB | 1MiB |

CK-RX65N V1の搭載MCU・640KiB SRAMは[公式board manual](https://www.renesas.com/en/document/mat/ck-rx65n-v1-users-manual) `R20UT5100EG0110 Rev.1.10` p5、RX65Nの非連続なRAM範囲は[公式memory map](https://www.renesas.cn/zh/document/apn/rx65n-group-target-board-rx65n-led-blink-control-program) `R20AN0464EJ0100 Rev.1.00` p5/Fig.4-1で照合しました。RX72Nは[公式datasheet](https://www.renesas.com/en/document/dst/rx72n-group-datasheet) `R01DS0343EJ0120 Rev.1.20` p1/p3、RX671の容量は[公式datasheet](https://www.renesas.com/en/document/dst/rx671-group-datasheet-rev100) `R01DS0373EJ0120 Rev.1.20`で確認しています。

[CI job #71061](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/71061)のRX65N software appは、source [`edf8d844`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/commit/edf8d844dc0f4ed68b6350f43e063fd87d97832c)による新しい静的配置のsnapshotです。ABS SHA-256は`9aa5ba2a92bbf0284cfe33753b65eb5631b438c73dcba937a68e2185f183252e`です。以下の数値は実ABSのsectionから算出しました。

| RX65N appの領域 | sectionの最大終端（exclusive） | 領域終端（exclusive） | 終端までの静的未配置領域 |
|---|---|---|---|
| 低位の内蔵RAM | `000106DC` | `00040000` | 194,852B |
| 内蔵拡張RAM | `0085B194` | `00860000` | **20,076B** |

TraceRecorder本体12,932B、control task stack2,048B、BSP library heap8,192B、FreeRTOS heap262,144Bは、このappの内蔵拡張RAM内に配置されています。20,076Bはsection配置後の末尾余白です。予約heap内の動的な使用余裕・stack high-water markは未測定で、実機でのRAMアクセス動作も未検証です。従来の5 image証跡とは取得source・option・addressを分けて扱います。

### 参照する現ファイル

- [manifest](../../manifest.yml)、[`.gitmodules`](../../.gitmodules)、[submodule照合](submodule-conformance-20261014.md)
- app/bootの`.project`・`.cproject`・`.scfg`、各`FreeRTOSConfig.h`・`r_bsp_config.h`・`r_flash_rx_config.h`・公開`rx_bootloader_config.h`
- [Kernel/SC guard](../../tools/ci/check_common_kernel.py)、[共通CLI adapter](../../tools/rx_e2studio_cli.ps1)、[RX65N cold生成helper](../../tools/build_headless_rx65n_bg96.ps1)
- [通常OTA PAL](../../Common/ports/ota_pal/ota_pal.c)、[native profile/helper](../../tools/build_rx72n_idt_transport.ps1)、[public signer provisioner helper](../../tools/build_public_signer_provisioner.py)
- [現WIP比較の公開証拠](current-convergence-20261014.json)。raw firmware、private絶対パス、credential、RAM dumpは収録しない

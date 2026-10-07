# RX671 / RX65N / RX72N submodule・参照階層監査

**共通基盤は現状揃っていません。** RX671/RX72Nのroot gitlinkはKernel **11.3.0** / coreMQTT **5.0.2**、RX65Nが参照するproject内flat copyはKernel **11.1.0** / coreMQTT **2.3.1**です。bootloaderも同一URLながらRX671とRX65N/RX72Nでpin・treeが異なります。

基準: `iot-reference-rx@44232ef62ea5be65161b95ae9741c6da555c7f3b`。dirtyなworking treeは使わず、固定commitのruntime/library内容は既存Git object storeから `git show` / `ls-tree` で読みました。別経路として、通常RX671 benchmarkリポジトリのmain確認に既存remoteへのfetch、host unit-test側CMockのrecursive leaf確認にpublic GitHub APIのreadを使っています。clone / init / update / checkout / reset、ハード操作、API書込みは行っていません。

本稿の「通常RX671 software benchmark child」は、通常CIが参照する別リポジトリ [`oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls) を指します。ここにある `Projects/aws_wifi_rx671_ek/e2studio_ccrx` は、`external/iot-reference-rx` gitlinkを経由して共通コードへリンクします。native IDTは `iot-reference-rx` 内の同名projectを直接使うため、経路を分けて記録します。

## 証拠取得方法・時刻

local/APIの数はpin/treeを確認した **graph entryの延べ数** です。canonical checkoutで初期化されているcomponent数や、新しくdownloadしたobject数ではありません。IDT親の44 entryは既存local object cache、27 entryはpublic APIで確認しています。27 API entryは4つのrepo/pin snapshotへdedupされます。

Cellular/coreHTTP/coreSNTPのcanonical working directoryが未初期化でも、登録済み別worktreeの `.git/worktrees/126-rx671-marker-guard/modules/Middleware/FreeRTOS/<component>` に今回のpinが残っていました。本監査はこのcacheから内容比較とversion照合を行いました。core-versions監査のpublic固定manifest照合と取得経路が異なるだけで、読み取るpinは同じです。実際のobject-store絶対パス、manifest blob SHAはJSONに記録しています。

| 確認 | 時刻（JST） | 範囲 |
|---|---|---|
| 既存通常RX671 childのfetch | 2026-10-07 13:31:19 | child main refの鮮度確認。componentのfetch/initなし |
| 初回graph保存 | 2026-10-07 13:32:46 | 固定pinと既存object cache |
| public API leaf監査完了 | 2026-10-07 13:50:41 | host unit-test側CMock/CException/Unityのみ |
| 3 componentのlocal manifest再照合 | 2026-10-07 14:15:16 | 同じpinと上記cacheを再読取り |

cacheの元のdownload時刻は未確認です。この監査でcomponent objectを新規fetch/initしたとは記録しません。

## 実際のproject参照位置

| 経路 | Common / Demos / Middleware | gitlinkを持つ親・位置 |
|---|---|---|
| RX671 native IDT / RX72N | `.project` の `AWS_IOT_MCU_ROOT=PARENT-3-PROJECT_LOC`、3 root directoryをlinkedResourcesとして表示 | `iot-reference-rx` rootの `Middleware/...` |
| RX65N native IDT / 通常project | `AWS_IOT_MCU_ROOT=PROJECT_LOC`、project内の通常treeを参照。Common/portsだけ `AWS_IOT_MCU_REPO_ROOT` でrootへlink | `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/Middleware/...` は **gitlinkではなくflat copy**。内包 `.gitmodules` が残るlibraryもあるが、このcopyには依存SHAを固定する160000 entryがない |
| 通常RX671 software benchmark child | `${PARENT-3-PROJECT_LOC}/external/iot-reference-rx` を参照 | `benchmark/mbedtls` → `external/iot-reference-rx` → `Middleware/...` と2段の親 |

[root .gitmodules](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/blob/44232ef62ea5be65161b95ae9741c6da555c7f3b/.gitmodules)、[RX671 .project](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/blob/44232ef62ea5be65161b95ae9741c6da555c7f3b/Projects/aws_wifi_rx671_ek/e2studio_ccrx/.project)、[RX65N .project](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/blob/44232ef62ea5be65161b95ae9741c6da555c7f3b/Projects/aws_bg96_ck_rx65n/e2studio_ccrx/.project)、[RX72N .project](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/blob/44232ef62ea5be65161b95ae9741c6da555c7f3b/Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/.project)。

## 共通libraryの内容差

RX65N flat treeとrootのpinを再帰展開したファイルをblob SHAで比較し、相違blobはCRLFをLFへ正規化して再比較しました。下表の相違は改行だけではありません。不要なtest/docの省略もあるため、missing/extra数をすべて実装差とは扱いません。全パス・SHA・未取得境界はJSONへ記録しています。

| library | RX671/RX72Nのroot pin | RX65N flat copyの確認 | 内容差のある同じpath数（うちC/H） |
|---|---|---|---|
| FreeRTOS-Kernel | `9b777ae5c5b8` | V11.1.0（root V11.3.0） | 685（555） |
| FreeRTOS-Plus-TCP | `c12361095aca` | 通常tree copy。root全体と同一ではない | 176（166） |
| coreMQTT | `04845c6a8e5f` | v2.3.1（root v5.0.2） | 19（8） |
| coreMQTT-Agent | `e977d70ee68c` | 保持する50 blobsは同一。test等321 blobs省略 | 0（0） |
| corePKCS11 | `ccc78afee171` | 通常tree copy。root全体と同一ではない | 20（13） |
| coreHTTP | `3c4a5838658c` | v3.1.1（root v3.1.3、manifest） | 18（9） |
| coreSNTP | `50f5f96f4c33` | v1.3.1（root v2.0.0、manifest） | 10（5） |
| coreJSON | `cffa492da18c` | 通常tree copy。root全体と同一ではない | 8（2） |
| backoffAlgorithm | `14f4c88b33dd` | 通常tree copy。root全体と同一ではない | 7（2） |
| FreeRTOS-Cellular-Interface | `5d76e3b3099c` | v1.4.0（root v1.4.2、manifest） | 26（19） |
| mbedtls | `c765c831e5c2` | 通常tree copy。root全体と同一ではない | 46（44） |
| littlefs | `6a53d76e90af` | 通常tree copy。root全体と同一ではない | 0（0） |

比較は19のMiddleware component全てに実施しています。MD表は共通kernel/FreeRTOS/TLSの12 componentへ圧縮し、AWS SDK系6 componentと `mbedtls_with_TSIP` の全blob/path比較はJSONへ記録しています。coreHTTP/coreSNTPは当初のcompact表から落ちていたため追加しました。**coreSNTPはroot v2.0.0とRX65N v1.3.1でmajor版も異なります。** libraryを保持することと、各buildでコンパイル対象になることは別途照合します。

root coreMQTT-Agentが持つ nested `source/dependency/coreMQTT@2beef047...` はv2.3.1です。root選択coreMQTT v5.0.2と区別します。`.project`のAgent/source filterはdependencyを除外しており、nestedの存在だけでcompile対象と断定しません。

RX671のWHD実装 `external/wifi-host-driver@769c8555...` とfirmware素材 `external/type1yn-blobs/sources/firmware-wifi-host-driver@31247470...` は同じInfineon upstream URLですが用途別の別pinです。これを共通基盤の未同期と自動判定しません。Renesas FITの `r_flash_rx` 等は3 targetそれぞれの `src/smc_gen` 通常treeであり、Git submoduleのpinがないためversion/生成設定を別途照合する必要があります。

## bootloaderのpinと格納場所

| board | 親repo内gitlink位置 | pin |
|---|---|---|
| RX671 | `Projects/boot_loader_rx671_ek/e2studio_ccrx/lib/rx_bootloader` | `c31bac703e1406e7a94d398b7bcad108b5e8fdce` |
| RX65N | `Projects/boot_loader_ck_rx65n/e2studio_ccrx/lib/rx_bootloader` | `4968ad7d5fc942a38b312a6847c60f281f16cc50` |
| RX72N | `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/src/rx_bootloader` | 同上 |

3リンクのdeclared URLはいずれも `../../../../experiment/embedded/mcu/renesas/rx/bootloader/submodule.git`、解決先は `https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule.git` です。RX671 tree `a7d6c5a...` とRX65N/RX72N tree `bc16b62b...` は異なり、`rx_bootloader.c`、`rx_bootloader_private.h`、config等にも差があります。MCU追加による必要差か、共通処理の不統一かは別のコード監査対象です。

## 通常RX671 software benchmarkリポジトリ経路の重要な例外

既存childを2026-10-07 13:31 JSTに `fetch origin` してcurrent main `90ea186bcdc42d239b80b8a8f6170b1d69460abb` を確認しました。outer `external/iot-reference-rx` は `666d97f64eecc2451ec3b54ee101b5b53a603c51` で、IDT親 `44232ef6` とはcommitが異なります。

**ただし、そのouter pinが持つdirect31 gitlinkは、IDT親44232ef6の31 gitlinkとすべて同じpinです。** 親commit/階層が異なることと、現基準のmiddleware pinが異なることは同義ではありません。childの `.project` が `external/iot-reference-rx` を指すことも確認しました。current childと過去の通常pipelineのresolved SHAの一致はこの監査の対象外です。

## 再帰leafまでの走査と参照鮮度

**CMockの未取得9境界もpublic GitHub APIで解消し、固定pinの構造は全leafまで確認しました。** ローカルにclone/init/updateせず、登録済み `.gitmodules` URLとpinからGit Commit APIでcommit/treeを照合し、Git Trees APIの `truncated=false` と `.gitmodules` blob hash/pathの対応を確認しました。

| 経路 | 全edges | local objectで確認 | API treeで確認 | leaf | 未確認境界 |
|---|---:|---:|---:|---:|---:|
| IDT親44232ef6 | 71 | 44 | 27 | 45 | 0 |
| 通常RX671 child90ea → outer666d | 72 | 45 | 27 | 45 | 0 |

IDT親のdepth別edgesは0:31 / 1:19 / 2:19 / 3:2。通常RX671 childはouter分が加わり0:1 / 1:31 / 2:19 / 3:19 / 4:2です。API追加分は **host unit-test側のCMock/CException/Unity** であり、firmwareが使用するruntime libraryと分けています。

同じrepo/pinの反復はdedupし、追加の取得対象は4 snapshotでした。最終収集scriptのHTTP readは10回（予備確認4回を別記）。全tree応答はtruncated=falseでした。URL・取得UTC時刻・HTTP status・ETag・response SHA256をJSONに保存しています。

| 追加確認repo | 固定commit | Git tree SHA | gitlinks / truncated |
|---|---|---|---|
| throwtheswitch/cmock | `9d092898ef26ece140d9225e037274b64d4f851e` | `169fdefd91d872e9fc44ba283b08971c075d6418` | 2 / false |
| throwtheswitch/cexception | `71b47be7c950f1bf5f7e5303779fa99a16224bb6` | `a8759af697611e061a87eea7c440792ced67aefc` | 0 / false |
| throwtheswitch/unity | `cf949f45ca6d172a177b00da21310607b97bc7a7` | `cca28689fefa74d2cfc364d6b79e0d8a4e10a571` | 0 / false |
| throwtheswitch/cmock | `afa294982e8a28bc06f341cc77fd4276641b42bd` | `cac91f2a27184540c9527dbc639a0fd66bc8a7ac` | 2 / false |

CMockの2つのpinはいずれも `vendor/c_exception@71b47be7...` と `vendor/unity@cf949f45...` を持ちます。CExceptionとUnityのpinにはさらにgitlinkがありません。CMockの `.gitmodules` に記載されたchild URLは `https://github.com/throwtheswitch/cexception.git` / `https://github.com/throwtheswitch/unity.git`、branch指定はmasterです。branch指定があってもこの監査の依存identityは固定gitlink SHAです。

元のdirect31と取得済みruntime graphにはbranch指定がなく、今回APIで確認したCMock childにmaster指定があることを区別しています。**fixed-pinのrecursive構造は確認済みですが、upstream main/latestとのdrift・main ancestryは未照合なのでrecursive-latestとは宣言しません。**

RX65N flat copyのblob比較はlocalで取得済みのsubtreeに限定しています。今回APIでpin/treeを追加確認したhost-test vendor subtreeはblob-by-blob比較へ含めていません。JSONの `uncompared_remote_only_nested_trees` として記録しています。

<details>
<summary>GitHub API参照証拠</summary>

- [throwtheswitch/cmock@9d092898ef26ece140d9225e037274b64d4f851e Git Trees API](https://api.github.com/repos/ThrowTheSwitch/CMock/git/trees/169fdefd91d872e9fc44ba283b08971c075d6418?recursive=1) / [固定commit検証](https://api.github.com/repos/ThrowTheSwitch/CMock/git/commits/9d092898ef26ece140d9225e037274b64d4f851e)。
- [throwtheswitch/cexception@71b47be7c950f1bf5f7e5303779fa99a16224bb6 Git Trees API](https://api.github.com/repos/throwtheswitch/cexception/git/trees/a8759af697611e061a87eea7c440792ced67aefc?recursive=1) / [固定commit検証](https://api.github.com/repos/throwtheswitch/cexception/git/commits/71b47be7c950f1bf5f7e5303779fa99a16224bb6)。
- [throwtheswitch/unity@cf949f45ca6d172a177b00da21310607b97bc7a7 Git Trees API](https://api.github.com/repos/throwtheswitch/unity/git/trees/cca28689fefa74d2cfc364d6b79e0d8a4e10a571?recursive=1) / [固定commit検証](https://api.github.com/repos/throwtheswitch/unity/git/commits/cf949f45ca6d172a177b00da21310607b97bc7a7)。
- [throwtheswitch/cmock@afa294982e8a28bc06f341cc77fd4276641b42bd Git Trees API](https://api.github.com/repos/ThrowTheSwitch/CMock/git/trees/cac91f2a27184540c9527dbc639a0fd66bc8a7ac?recursive=1) / [固定commit検証](https://api.github.com/repos/ThrowTheSwitch/CMock/git/commits/afa294982e8a28bc06f341cc77fd4276641b42bd)。

</details>

<details>
<summary>direct31の宣言URL・pin</summary>

| path | pin | declared URL |
|---|---|---|
| `Middleware/3rdparty/littlefs` | `6a53d76e90af33f0656333c1db09bd337fa75d23` | `https://github.com/littlefs-project/littlefs.git` |
| `Middleware/3rdparty/mbedtls` | `c765c831e5c2a0971410692f92f7a81d6ec65ec2` | `https://github.com/Mbed-TLS/mbedtls.git` |
| `Middleware/3rdparty/mbedtls_with_TSIP` | `6d8fb19d71cfdf17acbdf7382d65ec899e750118` | `../../mbed-tls/mbedtls.git` |
| `Middleware/AWS/Device-Defender-for-AWS-IoT-embedded-sdk` | `86582e258907e762948547c1826d44704908b403` | `https://github.com/aws/Device-Defender-for-AWS-IoT-embedded-sdk.git` |
| `Middleware/AWS/Device-Shadow-for-AWS-IoT-embedded-sdk` | `a0cbd6e5ea4b4615f0d7f801be24e552a9658b42` | `https://github.com/aws/Device-Shadow-for-AWS-IoT-embedded-sdk.git` |
| `Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk` | `7691e8af27bd0a42b7fe2f21c8b3289fa037df17` | `https://github.com/aws/Fleet-Provisioning-for-AWS-IoT-embedded-sdk.git` |
| `Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk` | `f09232966a558916253537fed68c07e529cd8f39` | `https://github.com/aws/Jobs-for-AWS-IoT-embedded-sdk.git` |
| `Middleware/AWS/SigV4-for-AWS-IoT-embedded-sdk` | `b4ac78a0d5d4cff9b28a44f665067057e07be09f` | `https://github.com/aws/SigV4-for-AWS-IoT-embedded-sdk.git` |
| `Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c` | `383ffeff43a80123e07cf8ca613d12ce680527b0` | `https://github.com/aws/aws-iot-core-mqtt-file-streams-embedded-c.git` |
| `Middleware/FreeRTOS/FreeRTOS-Cellular-Interface` | `5d76e3b3099c3693f98ecc6e15bc62cca140f13f` | `https://github.com/FreeRTOS/FreeRTOS-Cellular-Interface.git` |
| `Middleware/FreeRTOS/FreeRTOS-Kernel` | `9b777ae5c5b8e9e456065a00294d1e5f5f9facf5` | `https://github.com/FreeRTOS/FreeRTOS-Kernel.git` |
| `Middleware/FreeRTOS/FreeRTOS-Plus-TCP` | `c12361095aca68aeed858f45d14395fbffa92c0d` | `https://github.com/FreeRTOS/FreeRTOS-Plus-TCP.git` |
| `Middleware/FreeRTOS/backoffAlgorithm` | `14f4c88b33dd554be30a00a312c88d3986d457d0` | `https://github.com/FreeRTOS/backoffAlgorithm.git` |
| `Middleware/FreeRTOS/coreHTTP` | `3c4a5838658cd6d0ff8fb7c3a14e30baafcbcd28` | `https://github.com/FreeRTOS/coreHTTP.git` |
| `Middleware/FreeRTOS/coreJSON` | `cffa492da18c890181d64462f8af63992a69d3b0` | `https://github.com/FreeRTOS/coreJSON.git` |
| `Middleware/FreeRTOS/coreMQTT` | `04845c6a8e5f9cf2d232f1c6e80baeb81302e690` | `https://github.com/FreeRTOS/coreMQTT.git` |
| `Middleware/FreeRTOS/coreMQTT-Agent` | `e977d70ee68c95f94d967ea18feadfffe5c7a584` | `https://github.com/FreeRTOS/coreMQTT-Agent.git` |
| `Middleware/FreeRTOS/corePKCS11` | `ccc78afee1716436cca832dd3d9388ead2ba05b0` | `https://github.com/FreeRTOS/corePKCS11.git` |
| `Middleware/FreeRTOS/coreSNTP` | `50f5f96f4c33b14c0358f404ff4ff2a29d422ad7` | `https://github.com/FreeRTOS/coreSNTP.git` |
| `Projects/aws_bg96_ck_rx65n_tsip/e2studio_ccrx/Middleware/3rdparty/mbedtls_with_TSIP` | `6d8fb19d71cfdf17acbdf7382d65ec899e750118` | `../../mbed-tls/mbedtls.git` |
| `Projects/aws_wifi_rx671_ek/external/TraceRecorderSource` | `2f888cb9e6240c88e33eacd5acd50555fb13fbf5` | `https://github.com/percepio/TraceRecorderSource.git` |
| `Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/cyw-fmac-nvram` | `40a917f1a50f9e4df44a7ec63901771791d53f09` | `https://github.com/murata-wireless/cyw-fmac-nvram.git` |
| `Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/firmware-wifi-host-driver` | `31247470af5b7d79b53458f51d06a89aa5fd41f6` | `https://github.com/Infineon/wifi-host-driver.git` |
| `Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/wifi-resources` | `e9b4a5bf07cb62736f1d420a75d27b45bc49d7bd` | `https://github.com/Infineon/wifi-resources.git` |
| `Projects/aws_wifi_rx671_ek/external/wifi-host-driver` | `769c855507365e9828b02c81f1590d671f49661d` | `https://github.com/Infineon/wifi-host-driver.git` |
| `Projects/boot_loader_ck_rx65n/e2studio_ccrx/lib/rx_bootloader` | `4968ad7d5fc942a38b312a6847c60f281f16cc50` | `../../../../experiment/embedded/mcu/renesas/rx/bootloader/submodule.git` |
| `Projects/boot_loader_rx671_ek/e2studio_ccrx/lib/rx_bootloader` | `c31bac703e1406e7a94d398b7bcad108b5e8fdce` | `../../../../experiment/embedded/mcu/renesas/rx/bootloader/submodule.git` |
| `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/src/rx_bootloader` | `4968ad7d5fc942a38b312a6847c60f281f16cc50` | `../../../../experiment/embedded/mcu/renesas/rx/bootloader/submodule.git` |
| `Test/FreeRTOS-Libraries-Integration-Tests` | `0a0a92160a81c5cba008e472203513bd0cfb4c7a` | `https://github.com/FreeRTOS/FreeRTOS-Libraries-Integration-Tests.git` |
| `Test/Unity` | `22777c4810de3e3a4cb521a05eca2752fccd00ea` | `https://github.com/ThrowTheSwitch/Unity.git` |
| `tools/provisioning` | `1fadbdf0a6da41166a844e64b925dcaa56fe7593` | `https://gitlab.saffti.jp/oss/experiment/generic/scripts/python/provisioning.git` |

</details>

工程上はproject/source treeの参照監査です。コンパイルmap、実機で動いたimageの版、RX671起動問題との因果はそれぞれ別に照合します。

証拠: [submodule-graph.json](./submodule-graph.json)。公開repoのソース/metadataと既存Git objectから取得し、credential値は取得・記録していません。

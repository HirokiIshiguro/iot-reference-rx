# 共通基盤の版数・設定監査

正本: `44232ef62ea5be65161b95ae9741c6da555c7f3b`。dirtyなworking treeを使わずGit objectとgitlink固定版を参照した。対象は主3applicationと対応3bootloader。

**結論:** SDK/FIT/BSP/FreeRTOSを全target共通版として扱えない。RX65Nのapplicationは独立したflat importを使用し、RX671/RX72Nのrootライブラリと版が異なる。以下は実ソースの版数・設定であり、全6構成の実ビルド・実機状態を検証した結果ではない。

## 6構成の比較

|構成|Kernel|Flash FIT|BSP|BSP bank mode|start bank|.cproject device mode|
|---|---|---|---|---|---|---|
|RX671 app|V11.3.0|5.30|7.70|linear|0|bank.single|
|RX65N app|V11.1.0|5.22|7.52|dual|0|bank.single|
|RX72N app|V11.3.0|5.22|7.52|dual|0|bank.dual|
|RX671 boot|対象外（bare metal）|5.30|7.70|dual|0|bank.dual|
|RX65N boot|対象外（bare metal）|5.30|7.70|dual|0|bank.dual|
|RX72N boot|対象外（bare metal）|4.50|5.52|dual|0|宣言なし|

全6構成で `FLASH_CFG_CODE_FLASH_ENABLE=1`、`FLASH_CFG_CODE_FLASH_BGO=1`、`FLASH_CFG_DATA_FLASH_BGO=1`、`FLASH_CFG_CODE_FLASH_RUN_FROM_ROM=1`。全3applicationで `configKERNEL_INTERRUPT_PRIORITY=1`、`configMAX_SYSCALL_INTERRUPT_PRIORITY=4`、tick 1000 Hz。全3bootloaderのFlash割込み優先度は14、bare metal。

## FreeRTOSライブラリの参照元と版

RX671/RX72Nは `.project` の `Middleware` と `Common` をrootへリンクする。RX65Nにはこのリンクがなく、`Projects/aws_bg96_ck_rx65n/e2studio_ccrx/Middleware/FreeRTOS/` のflat sourceを使う。native RX65N builderにもroot Kernelへ置換する処理は確認されない。

|ライブラリ|root版 (RX671/RX72N)|RX65N flat版|root gitlink|
|---|---|---|---|
|FreeRTOS-Cellular-Interface|v1.4.2|v1.4.0|`5d76e3b3099c3693f98ecc6e15bc62cca140f13f`|
|FreeRTOS-Kernel|V11.3.0|V11.1.0|`9b777ae5c5b8e9e456065a00294d1e5f5f9facf5`|
|FreeRTOS-Plus-TCP|V4.4.1|V4.2.2|`c12361095aca68aeed858f45d14395fbffa92c0d`|
|backoffAlgorithm|v1.4.2|v1.4.1|`14f4c88b33dd554be30a00a312c88d3986d457d0`|
|coreHTTP|v3.1.3|v3.1.1|`3c4a5838658cd6d0ff8fb7c3a14e30baafcbcd28`|
|coreJSON|v3.3.1|v3.3.0|`cffa492da18c890181d64462f8af63992a69d3b0`|
|coreMQTT|v5.0.2|v2.3.1|`04845c6a8e5f9cf2d232f1c6e80baeb81302e690`|
|coreMQTT-Agent|v1.3.1|v1.3.1|`e977d70ee68c95f94d967ea18feadfffe5c7a584`|
|corePKCS11|v3.6.4|v3.6.1|`ccc78afee1716436cca832dd3d9388ead2ba05b0`|
|coreSNTP|v2.0.0|v1.3.1|`50f5f96f4c33b14c0358f404ff4ff2a29d422ad7`|

版数根拠はKernelの `include/task.h` と各ライブラリ `manifest.yml` のトップレベルversion。manifest内の依存library versionを混同していない。root coreMQTT-Agentは同じv1.3.1表記でもRX671/RX72Nで `Common/patches/coreMQTT-Agent/source` を選択するため、RX65N flat実装と同一とはしない。ライブラリ一覧は参照候補のinventoryであり、全libraryが全test groupで実行されたことは意味しない。

この版数抽出で参照したGit storeではFreeRTOS-Cellular-Interface・coreHTTP・coreSNTPのsubmoduleが未初期化で、固定pinのobjectを参照できなかった。その3件の版数は、正本のgitlink SHAを指定した公開manifestから確認した。これは、このPCの別の既存storeにもobjectがないという意味ではない。別storeを用いたblob比較と、再帰edgeごとのlocal/API取得件数は [submodule・参照階層監査](submodule-graph.md) に記録している。本節の「版数を読んだ経路」と同文書の「内容比較・依存構造を確認した経路」を区別する。

## normal/nativeの差

- **RX671:** 通常applicationの登録設定はlinear。native IDTとOTAのbuild profileはdualへ変換する。dual bootloaderの書込み前には、別のlinear provisionerを使う。
- **RX65N:** BSPの登録設定はdualだが、`.cproject` のdevice modeは`bank.single`。native IDTは選択済みのlinker layoutを保持する。この設定差だけでは実行時linearの証拠にならない。
- **RX72N:** 通常applicationの登録設定とnative IDTのlayoutはいずれもdual。native IDTでは試験sourceとdefineを追加する。
- **bootloader:** 3構成ともBSPはdual、start-bankは0。いずれもbare metalである。

RX65NのBSP dualとIDE device metadata singleの差は確認事実。実効modeはMOT option/MAP/生成設定で評価し、この文字列差だけで実機linearと断定しない。

## RAMコピーと割込み条件

全targetのFIT選択はFlash Type 4。RAMコピーの有効条件・コピー量・版ごとのコード行・実MAPとの比較は [project / compiler-linker比較](project-options.md) に集約する。RX65N applicationのRAM写像についても同文書の確定事項と未確認事項を参照する。

bootloaderのbank切替は、固定pinの `rx_bootloader.c` で割込み禁止→BANK_TOGGLE→software resetの順になっている。Flash割込みの設定値は上の6構成比較に示した。配置やコード上の条件から、実行時のRAMコピー成功・PC・故障を観測済みとは扱わない。

## 出典と確認境界

<details>
<summary>版数・設定値・normal/native変換の出典</summary>

- RX671 app: `Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/smc_gen/` 配下の `r_flash_rx/r_flash_rx_if.h`, `r_bsp/mcu/all/r_bsp_common.h`, `r_config/r_bsp_config.h`, `r_config/r_flash_rx_config.h`。正確なdefine行はJSONに記録。
- RX65N app: `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/src/smc_gen/` 配下の `r_flash_rx/r_flash_rx_if.h`, `r_bsp/mcu/all/r_bsp_common.h`, `r_config/r_bsp_config.h`, `r_config/r_flash_rx_config.h`。正確なdefine行はJSONに記録。
- RX72N app: `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/src/smc_gen/` 配下の `r_flash_rx/r_flash_rx_if.h`, `r_bsp/mcu/all/r_bsp_common.h`, `r_config/r_bsp_config.h`, `r_config/r_flash_rx_config.h`。正確なdefine行はJSONに記録。
- RX671 boot: `Projects/boot_loader_rx671_ek/e2studio_ccrx/src/smc_gen/` 配下の `r_flash_rx/r_flash_rx_if.h`, `r_bsp/mcu/all/r_bsp_common.h`, `r_config/r_bsp_config.h`, `r_config/r_flash_rx_config.h`。正確なdefine行はJSONに記録。
- RX65N boot: `Projects/boot_loader_ck_rx65n/e2studio_ccrx/src/smc_gen/` 配下の `r_flash_rx/r_flash_rx_if.h`, `r_bsp/mcu/all/r_bsp_common.h`, `r_config/r_bsp_config.h`, `r_config/r_flash_rx_config.h`。正確なdefine行はJSONに記録。
- RX72N boot: `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/src/smc_gen/` 配下の `r_flash_rx/r_flash_rx_if.h`, `r_bsp/mcu/all/r_bsp_common.h`, `r_config/r_bsp_config.h`, `r_config/r_flash_rx_config.h`。正確なdefine行はJSONに記録。
- `tools/idt_rx671_build_profile.py:28`: RX671 native profileで`make_ota_cproject`を適用し、40行で`make_ota_bank_config`を適用する。
- `tools/build_rx671_ota_images.py:230`: native/OTA profileのdevice modeを`bank.single`から`bank.dual`へ変更し、340–341行でBSP bank modeを1から0へ変更する。RAM写像の追加は [project-options.md](project-options.md) を参照。
- `tools/build_rx72n_idt_transport.ps1:373`: native buildでdual bank設定を検査する。
- `tools/build_rx72n_idt_transport.ps1:547`: RX65N native helperはsoftware TLSと`PreserveLinkerLayout`を指定する。project内flat Middlewareをroot FreeRTOS sourceへ置換する処理はない。
- `tools/idt/rpi_flash.py:214`: RX671はprovisioning経路、RX72N/RX65Nは221–224行のchip erase→bootloader→UART経路を使う。
- RX671 bootloader: [c31bac703e14](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule/-/blob/c31bac703e1406e7a94d398b7bcad108b5e8fdce/rx_bootloader.c)。固定pinのGitLab rawを読取り確認。
- RX65N/RX72N bootloader: [4968ad7d5fc9](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule/-/blob/4968ad7d5fc942a38b312a6847c60f281f16cc50/rx_bootloader.c)。固定pinのGitLab rawを読取り確認。
- FreeRTOS-Cellular-Interfaceの版数: [固定commit manifest](https://raw.githubusercontent.com/FreeRTOS/FreeRTOS-Cellular-Interface/5d76e3b3099c3693f98ecc6e15bc62cca140f13f/manifest.yml)。
- coreHTTPの版数: [固定commit manifest](https://raw.githubusercontent.com/FreeRTOS/coreHTTP/3c4a5838658cd6d0ff8fb7c3a14e30baafcbcd28/manifest.yml)。
- coreSNTPの版数: [固定commit manifest](https://raw.githubusercontent.com/FreeRTOS/coreSNTP/50f5f96f4c33b14c0358f404ff4ff2a29d422ad7/manifest.yml)。

</details>

TSIP専用projectはRX65N/RX72Nに存在する。RX671には別名のTSIP projectなし（同projectのbuild profile有無とは別）。本表は主3targetのみ。新規build、実機操作、API書込みは行っていない。ソースが同じ箇所でも実ビルド・実行時状態が同じとは扱わない。

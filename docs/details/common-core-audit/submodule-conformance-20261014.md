# 共通基盤のsubmodule原本照合（2026-10-14）

共通化WIPの固定参照を284 node・198 leafまで辿り、参照先commit/treeの未解決は0件でした。
ソースのbyte照合は、存在する41 rootと7 nested checkoutについて完了しています。
この結果は全体ビルド、実機動作、IDT qualificationの合格を示しません。

対象は[WIP commit `65c59407`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/commit/65c59407b0a4b0c9048ba8ed8c700b3841090b3d)（[Draft MR !223](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/223)）です。
[同commitの`.gitmodules`](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/blob/65c59407b0a4b0c9048ba8ed8c700b3841090b3d/.gitmodules)とGit treeの41 gitlinkが、監査した固定SHAに一致することを確認しました。
前段の[2026-10-07基準監査](README.md)から共通submoduleへ移行したWIPの記録です。

## 確認結果と限界

| 確認対象 | 結果 |
|---|---|
| 固定参照の再帰列挙 | 41 root＋243 nested＝284 node、198 leaf |
| 固定commit/tree | 全284 nodeを解決、未解決0 |
| 公開source URLの最新refs | 107/107 URLを取得 |
| 固定SHAと公開tag/branch refとの完全一致 | 178 node |
| 最新branchへの祖先所属 | 106 nodeは未確定 |
| root own tracked blobsのbyte照合 | 35,912通常files＋13 symlink target、全byte一致・欠落0 |
| initialized nestedのbyte照合 | 7 node、1,508 files全byte一致・欠落0 |
| 未checkout nested | 236 nodeは固定tree参照のみ確認、bodyのbyte照合は未実施 |

最新refsの取得時刻は2026-10-14 14:49:41～14:50:10 JSTです。
root pinは21件が取得時点のdefault HEADと一致し、18件が固定tag/refと一致してdefault HEADとは異なります。
残るUnityとprovisioningの2件は、公開refとの完全一致を確認できていません。
固定commit/treeが存在すること、公開tag/refとの一致、checkoutのbyte一致を区別しています。
祖先所属未確定の106件を「branch外」や「すべてlatest」とは扱いません。

## 固定版と改造の境界

Kernel V11.3.0、software Mbed TLS 3.6.4、TSIP 3.2.1派生は合意済みの版を維持します。
CLIの202411.00、旧cryptoの202107.00、native assertion SDKの202406.00も、選択した原本snapshotを参照します。
親OSSが持つnested gitlinkはそのsnapshotのまま保持し、子だけを独立にlatestへ変更していません。

byte比較の基準は各submoduleの固定commitです。
比較した41 rootと7 nestedの固定本体に、利用側によるbyte改変は見つかりませんでした。
次の2種類は目的を限定して認めたforkの固定commitを基準とし、stock upstreamとの無改造一致を意味しません。

- [WHDのCC-RX対応fork](https://gitlab.saffti.jp/oss/import/github/infineon/wifi-host-driver/-/merge_requests/1)：pack構文とSDIO wire配置の対応。利用側はmerge済み`d5de9ee0`をsubmodule参照。
- [Mbed TLSのTSIP対応fork](https://gitlab.saffti.jp/oss/import/github/mbed-tls/mbedtls/-/commit/6d8fb19d71cfdf17acbdf7382d65ec899e750118)：Renesas暗号IP連携。software backendの3.6.4と分け、TSIP backendの版を揃える。

CLI/cryptoのmonorepo内に残る別SDK、demo、host test等のnested treeは、通常8 projectの選択source setと分けて記録しました。
その202 nodeは現在のMCU build inputとして選択されていません。
236 nodeの未checkout bodyを展開・照合したという記録にはしていません。
設定値と公開APIによる製品portは、OSS本体の改造と区別します。管理原則は[OSS流用規則](https://gitlab.saffti.jp/oss/claude-codex-gemini-index/-/blob/58f390254bf4aad69e65879482b885d2be2e1de1/rules/oss-reuse.md)に従います。

## Root 41 pin

各SHAのリンクは固定commitを指します。**HEAD一致は上記取得時刻の記録**で、将来のlatestを保証しません。
「未選択」は通常8 projectの選択source setに含まれないことを示します。
firmware resourceの由来、native test、host toolは通常C sourceと分けています。

<details>
<summary>41参照の固定SHA・公開ref・用途を開く</summary>

| 利用側のgitlink位置 | 固定commit | 公開refとの関係 | 用途 |
|---|---|---|---|
| `Middleware/3rdparty/littlefs` | [6cb4e86540ec](https://github.com/littlefs-project/littlefs/commit/6cb4e86540eca0d9ba62500a298385c9d863c8be) | default HEAD一致 | 通常source |
| `Middleware/3rdparty/mbedtls` | [c765c831e5c2](https://github.com/Mbed-TLS/mbedtls/commit/c765c831e5c2a0971410692f92f7a81d6ec65ec2) | tag `mbedtls-3.6.4`, `v3.6.4` | 通常source |
| `Middleware/3rdparty/mbedtls_with_TSIP` | [6d8fb19d71cf](https://gitlab.saffti.jp/oss/import/github/mbed-tls/mbedtls/-/commit/6d8fb19d71cfdf17acbdf7382d65ec899e750118) | tag `v3.2.1-renesas-tsip-custom-0.1.5` | 通常source |
| `Middleware/3rdparty/tinycbor` | [d94ca09aa91f](https://github.com/intel/tinycbor/commit/d94ca09aa91f5b3c581527aa8bca179a82b79874) | tag `v0.5.2` | 通常source |
| `Middleware/3rdparty/tinycrypt` | [cf24c907a61c](https://github.com/intel/tinycrypt/commit/cf24c907a61c01bc2c4e1ee0ae24457c27a840a2) | default HEAD一致 | 通常source |
| `Middleware/AWS/Device-Defender-for-AWS-IoT-embedded-sdk` | [86582e258907](https://github.com/aws/Device-Defender-for-AWS-IoT-embedded-sdk/commit/86582e258907e762948547c1826d44704908b403) | default HEAD一致 | 通常未選択 |
| `Middleware/AWS/Device-Shadow-for-AWS-IoT-embedded-sdk` | [a0cbd6e5ea4b](https://github.com/aws/Device-Shadow-for-AWS-IoT-embedded-sdk/commit/a0cbd6e5ea4b4615f0d7f801be24e552a9658b42) | default HEAD一致 | 通常未選択 |
| `Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk` | [7691e8af27bd](https://github.com/aws/Fleet-Provisioning-for-AWS-IoT-embedded-sdk/commit/7691e8af27bd0a42b7fe2f21c8b3289fa037df17) | default HEAD一致 | 通常source |
| `Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk` | [f09232966a55](https://github.com/aws/Jobs-for-AWS-IoT-embedded-sdk/commit/f09232966a558916253537fed68c07e529cd8f39) | default HEAD一致 | 通常source |
| `Middleware/AWS/SigV4-for-AWS-IoT-embedded-sdk` | [b4ac78a0d5d4](https://github.com/aws/SigV4-for-AWS-IoT-embedded-sdk/commit/b4ac78a0d5d4cff9b28a44f665067057e07be09f) | tag `v1.3.1` | 通常未選択 |
| `Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c` | [383ffeff43a8](https://github.com/aws/aws-iot-core-mqtt-file-streams-embedded-c/commit/383ffeff43a80123e07cf8ca613d12ce680527b0) | default HEAD一致 | 通常source |
| `Middleware/FreeRTOS-Plus-CLI` | [152cf36d6775](https://github.com/FreeRTOS/FreeRTOS/commit/152cf36d6775bce6026a791845af12201aae703d) | tag `202411.00` | 通常source |
| `Middleware/FreeRTOS/FreeRTOS-Cellular-Interface` | [5d76e3b3099c](https://github.com/FreeRTOS/FreeRTOS-Cellular-Interface/commit/5d76e3b3099c3693f98ecc6e15bc62cca140f13f) | tag `v1.4.2` | 通常source |
| `Middleware/FreeRTOS/FreeRTOS-Cellular-Interface-Reference-Quectel-BG96` | [d2176422d367](https://github.com/FreeRTOS/FreeRTOS-Cellular-Interface-Reference-Quectel-BG96/commit/d2176422d3678cef0d7e7f983f2a491e61db492e) | default HEAD一致 | 通常source |
| `Middleware/FreeRTOS/FreeRTOS-Kernel` | [9b777ae5c5b8](https://github.com/FreeRTOS/FreeRTOS-Kernel/commit/9b777ae5c5b8e9e456065a00294d1e5f5f9facf5) | tag `V11.3.0` | 通常source |
| `Middleware/FreeRTOS/FreeRTOS-Plus-TCP` | [c12361095aca](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/commit/c12361095aca68aeed858f45d14395fbffa92c0d) | tag `V4.4.1` | 通常source |
| `Middleware/FreeRTOS/backoffAlgorithm` | [14f4c88b33dd](https://github.com/FreeRTOS/backoffAlgorithm/commit/14f4c88b33dd554be30a00a312c88d3986d457d0) | tag `v1.4.2` | 通常source |
| `Middleware/FreeRTOS/coreHTTP` | [3c4a5838658c](https://github.com/FreeRTOS/coreHTTP/commit/3c4a5838658cd6d0ff8fb7c3a14e30baafcbcd28) | tag `v3.1.3` | 通常未選択 |
| `Middleware/FreeRTOS/coreJSON` | [cffa492da18c](https://github.com/FreeRTOS/coreJSON/commit/cffa492da18c890181d64462f8af63992a69d3b0) | default HEAD一致 | 通常source |
| `Middleware/FreeRTOS/coreMQTT` | [04845c6a8e5f](https://github.com/FreeRTOS/coreMQTT/commit/04845c6a8e5f9cf2d232f1c6e80baeb81302e690) | tag `v5.0.2` | 通常source |
| `Middleware/FreeRTOS/coreMQTT-Agent` | [2338d00db411](https://github.com/FreeRTOS/coreMQTT-Agent/commit/2338d00db41196e4a1fce4bc3ab32f907e77f871) | tag `v2.0.0` | 通常source |
| `Middleware/FreeRTOS/corePKCS11` | [ccc78afee171](https://github.com/FreeRTOS/corePKCS11/commit/ccc78afee1716436cca832dd3d9388ead2ba05b0) | tag `v3.6.4` | 通常source |
| `Middleware/FreeRTOS/coreSNTP` | [50f5f96f4c33](https://github.com/FreeRTOS/coreSNTP/commit/50f5f96f4c33b14c0358f404ff4ff2a29d422ad7) | tag `v2.0.0` | 通常未選択 |
| `Middleware/Renesas/r_sdio_rx` | [cc94efa0a37d](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/fitmodules/r_sdio_rx/r_sdio_rx/-/commit/cc94efa0a37db72a6fede1bc651a891a0a6e8bec) | default HEAD一致 | 通常source |
| `Middleware/Renesas/r_simple_glcdc_config_rx` | [ade52ca9b386](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/fitmodules/r_simple_glcdc_config_rx/r_simple_glcdc_config_rx/-/commit/ade52ca9b3869c4d80855ee41a1bf63db70695db) | default HEAD一致 | 通常source |
| `Middleware/Renesas/r_simple_graphic_rx` | [a7c3d736eab5](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/fitmodules/r_simple_graphic_rx/r_simple_graphic_rx/-/commit/a7c3d736eab56aa622caabe0715ba290e1136f49) | default HEAD一致 | 通常source |
| `Middleware/Renesas/rm_littlefs_rx` | [60f93c8427ce](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/fitmodules/rm_littlefs_rx/rm_littlefs_rx/-/commit/60f93c8427ce88f70ea26aae7abc641f577a7765) | default HEAD一致 | 通常source |
| `Middleware/Renesas/rm_rtos_abstraction_rx` | [5818cdfbda66](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/fitmodules/rm_rtos_abstraction_rx/rm_rtos_abstraction_rx/-/commit/5818cdfbda661d098fd028bf6975847d5af2c491) | default HEAD一致 | 通常source |
| `Middleware/Renesas/rx-driver-package` | [bcc409d331b0](https://github.com/renesas/rx-driver-package/commit/bcc409d331b0bff68d4b09bf6fc41376f75d42bc) | default HEAD一致 | 通常source |
| `Middleware/freertos_plus` | [a038063c3b02](https://github.com/aws/amazon-freertos/commit/a038063c3b0216e0b4d46d72425388a0c2938b13) | tag `202107.00` | 通常source |
| `Projects/aws_wifi_rx671_ek/external/TraceRecorderSource` | [2f888cb9e624](https://github.com/percepio/TraceRecorderSource/commit/2f888cb9e6240c88e33eacd5acd50555fb13fbf5) | default HEAD一致 | include path |
| `Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/cyw-fmac-nvram` | [40a917f1a50f](https://github.com/murata-wireless/cyw-fmac-nvram/commit/40a917f1a50f9e4df44a7ec63901771791d53f09) | default HEAD一致 | firmware resource |
| `Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/firmware-wifi-host-driver` | [31247470af5b](https://github.com/Infineon/wifi-host-driver/commit/31247470af5b7d79b53458f51d06a89aa5fd41f6) | tag `latest-v4.X`, `release-v4.3.0` | firmware resource |
| `Projects/aws_wifi_rx671_ek/external/type1yn-blobs/sources/wifi-resources` | [e9b4a5bf07cb](https://github.com/Infineon/wifi-resources/commit/e9b4a5bf07cb62736f1d420a75d27b45bc49d7bd) | tag `release-v2.0.0` | firmware resource |
| `Projects/aws_wifi_rx671_ek/external/wifi-host-driver` | [d5de9ee04e10](https://gitlab.saffti.jp/oss/import/github/infineon/wifi-host-driver/-/commit/d5de9ee04e103d727d7ed529a008c24b9332c4e8) | default HEAD一致 | 通常source |
| `Projects/boot_loader_ck_rx65n/e2studio_ccrx/lib/rx_bootloader` | [231a0cc68052](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule/-/commit/231a0cc680525be3530a7bb64862d099e5a401ec) | default HEAD一致 | 通常source |
| `Projects/boot_loader_rx671_ek/e2studio_ccrx/lib/rx_bootloader` | [231a0cc68052](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule/-/commit/231a0cc680525be3530a7bb64862d099e5a401ec) | default HEAD一致 | 通常source |
| `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/lib/rx_bootloader` | [231a0cc68052](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/bootloader/submodule/-/commit/231a0cc680525be3530a7bb64862d099e5a401ec) | default HEAD一致 | 通常source |
| `Test/FreeRTOS-Libraries-Integration-Tests` | [0a0a92160a81](https://github.com/FreeRTOS/FreeRTOS-Libraries-Integration-Tests/commit/0a0a92160a81c5cba008e472203513bd0cfb4c7a) | tag `202406.00` | native test |
| `Test/Unity` | [22777c4810de](https://github.com/ThrowTheSwitch/Unity/commit/22777c4810de3e3a4cb521a05eca2752fccd00ea) | ref完全一致なし・祖先所属未確認 | native test |
| `tools/provisioning` | [1fadbdf0a6da](https://gitlab.saffti.jp/oss/experiment/generic/scripts/python/provisioning/-/commit/1fadbdf0a6da41166a844e64b925dcaa56fe7593) | ref完全一致なし・祖先所属未確認 | host tool |

</details>

WHDとLittleFS v2.11.3は、取得時点の各参照先default HEADとの一致を確認しました。
通常OTA・native IDTのbank方針、RAM写像、API移行の実効ビルドと実機結果は、別の検証結果として扱います。

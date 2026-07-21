# RX671 / Type 1YN OTAフラッシュ配置ゲート

## 結論

現行配置のままOTAを有効化してはならない。

ソース`8e3363d00da13c5c6095e77cf1559031409c2d5b`では、アプリ本体を`0xFFE00000`側、WHD資材と固定ベクタを`0xFFF00000`側へ配置しており、1個のイメージが2個の1 MiB領域をまたぐ。
さらに、BSPはLinear mode、CC-RXは`bank.single`であり、`sdio_host.c`はWLAN firmwareとNVRAMを絶対アドレスで参照している。
data flashでは、FWUP設定の全8 KiBはaddressable geometryであり、FWUP専用領域ではない。LittleFS設定は`0x00100000`–`0x00101FFF`の全域を使用するため、FWUP header/descriptorをcode flash、bootloader署名公開鍵をbootloader code flashへ置く単独所有構成を候補にできる。ただし、linker anchorがないことだけではraw install/key-store/OTA payloadの不在を証明できない。

OTA実装へ進むには、アプリ、WHD資材、ベクタを1個の論理main領域へまとめ、bank swap後も同じlinker symbolでWHD資材を参照できる構成へ変更する必要がある。
bootloader予約量は実装物がないため未確定であり、数値を推定で埋めない。FWUP header/descriptorについては、存在しないlinker section名ではなく、main/buffer先頭の予約rangeと、その直後にある実linker objectのaddressで検証する。

## 正本から確定できる容量と配置

| 対象 | 値 | 根拠 | 現在の判定 |
|---|---:|---|---|
| RX671 code flash | 2,097,152 bytes (`0xFFE00000`–`0xFFFFFFFF`) | `r_bsp_config.h`のmemory code `0xE`と`mcu_info.h`の`BSP_ROM_SIZE_BYTES` | PASS |
| FWUP main | 1,048,576 bytes (`0xFFF00000`–`0xFFFFFFFF`) | `r_fwup_config.h` | PASS（領域定義のみ） |
| FWUP buffer | 1,048,576 bytes (`0xFFE00000`–`0xFFEFFFFF`) | `r_fwup_config.h` | PASS（領域定義のみ） |
| RX671 data flash geometry | 8,192 bytes (`0x00100000`から64 bytes×128 blocks) | BSP、`r_fwup_config.h`、r_flash RX671 FIT定義 | PASS（start/block-size/block-count一致） |
| FWUP data flash addressable geometry | `0x00100000`–`0x00101FFF` | `r_fwup_config.h` | PASS（専有割当を意味しない） |
| LittleFS data flash割当 | `0x00100000`–`0x00101FFF`（128 bytes×64 blocks） | `rm_littlefs_flash_config.h` | PASS（geometryのみ。単独owner証跡はUNKNOWN） |
| WLAN firmware | 249,066 bytes | `whd_port_resource.c`の宣言値 | 実ファイル不在時はUNKNOWN |
| NVRAM | 816 bytes | `whd_port_resource.c`の宣言値 | 実ファイル不在時はUNKNOWN |
| CLM | 4,752 bytes | `whd_port_resource.c`の宣言値 | 実ファイル不在時はUNKNOWN |
| 3資材合計 | 254,634 bytes | 上記宣言値の合計 | 実ファイルで一致確認が必要 |
| bootloader予約量 | 未確定 | RX671 bootloader project / mapなし | UNKNOWN |
| FWUP header/descriptor予約 | main/buffer先頭から`0x200`/`0x100` bytes | `Common/ports/ota_pal/ota_pal.c`と`tools/build_fwup_v2_rsu.py` | FAIL（現行app anchorが予約域直後ではない） |

WHDの3サイズはソースに記載された期待値であり、実バイナリの測定値ではない。
ゲートはstaging済みファイルを`stat`し、期待値と一致し、さらに同一buildのprovenance manifestでSHA-256が一致したときだけ`whd_blob_sizes=PASS`にする。

## 現行衝突

| 要素 | 現行anchor | FWUP領域 | 問題 |
|---|---:|---|---|
| `PResetPRG,...,P` | `0xFFE00000` | buffer | main向けアプリとしてリンクされていない |
| `TYPE1YN_FW_BLOB` | `0xFFF00000` | main | アプリ本体と別領域 |
| `TYPE1YN_NVRAM_BLOB` | `0xFFF80000` | main | アプリ本体と別領域 |
| `TYPE1YN_CLM_BLOB` | `0xFFF90000` | main | アプリ本体と別領域 |
| `EXCEPTVECT` / `RESETVECT` | `0xFFFFFF80` / `0xFFFFFFFC` | main | アプリ本体と別領域 |

`sdio_host.c`は`0xFFF00000`と`0xFFF80000`を直接参照する。
一方、`whd_port_resource.c`には`g_type1yn_*` linker symbolを使う経路がある。
OTA対応では直接参照を廃止し、資材の配置と参照をbank相対のlinker symbolへ統一する。

data flashでは、FWUPの64 bytes×128 blocksはアクセス可能な全体geometryであり、FWUPだけの専有範囲ではない。
LittleFSの128 bytes×64 blocksはRX671 FITのerase unit 64 bytes、program unit 4 bytesと整合し、全8 KiBを単独ownerとして使える候補である。
`data_flash_non_overlap=PASS`はLittleFS以外のraw consumerがないことを、linker、OTA packer、bootloader、runtime flash writerの全経路で証明した場合に限る。bootloaderのraw Data Flash install、Data Flash/LittleFSから上書き可能なbootloader key-store、OTA payloadのData Flash segment、LittleFS以外のData Flash linker anchorのいずれかがあればFAILとする。現行ゲートはlinker anchorしか列挙できないためUNKNOWNとし、FWUP header/descriptorとuser-app metadataをcode flashへ置く実装と明示的な所有権証跡が揃ってからPASSへ進める。

固定SHAを結び付けられない既存の非追跡map/MOTを参考入力として解析すると、code flash loadは671,618 bytesで、mainとbufferの両方を占有した。
これは衝突の再現には使えるが、現行mainの容量証跡には採用しない。
現行mainをビルドしたmap/MOTを同じpipeline artifactとして残し、再度ゲートを通す必要がある。

## 必要なdual-bank構成

次の条件をすべて満たすことを候補レイアウトの成立条件とする。

1. Smart Configurator/BSPをDual mode (`BSP_CFG_CODE_FLASH_BANK_MODE=0`)にし、CC-RX device modeを`bank.dual`にする。
2. mainとdownload bufferを各1 MiB bankの先頭`0xFFF00000` / `0xFFE00000`へ置き、同じinstall area sizeを使う。各bank末尾のbootloader予約量はRX671 bootloader mapで確定する。
3. アプリ、WHD firmware、NVRAM、CLM、例外・リセットベクタを、main向けの1個の署名イメージへ含める。
4. WHD資材をmain内のbank相対sectionへ置き、Cコードは絶対アドレスではなくlinker symbolを参照する。
5. FWUPが同じイメージをbufferへ書き、bank swap後にmainの論理アドレスから起動・参照できることを実機確認する。
6. bootloaderの実測sectionと予約範囲をRX671専用mapで確定し、アプリ/WHD/FWUP領域との非重複を確認する。
7. main/buffer先頭の`0x200` bytesをFWUP header、続く`0x100` bytesをFWUP v2 descriptorとして予約し、実アプリanchorを`main+0x300`へ置く。例外・reset vectorは`main+area_size-0x80` / `main+area_size-0x04`へ置く。
8. Data FlashはLittleFS単独所有とし、bootloader raw install/key-storeおよびOTA payloadからのraw Data Flash書き込みを無効にする。

bootloaderの開始アドレスや予約量は、RX72N/RX65Nの値を流用しない。
RX671専用projectの生成、build、map確認が終わるまでは`UNKNOWN`とする。

## 自動ゲート

`tools/ci/analyze_rx671_ota_layout.py`は、設定、実ファイル、map、MOTを別々に判定する。

```powershell
python tools/ci/analyze_rx671_ota_layout.py
python tools/ci/analyze_rx671_ota_layout.py `
  --build-dir Projects/aws_wifi_rx671_ek/e2studio_ccrx/HardwareDebug
```

map/MOTが存在しても、それだけでは現行sourceの証跡にしない。
build directoryに`ota-layout-provenance.json`を置き、次をすべて現在入力と照合できた場合だけ`artifact_provenance=PASS`とする。

- `schema_version=1`
- 40桁の`source_sha`が解析時のGit HEADと一致
- build時の`dirty=false`
- `project_path=Projects/aws_wifi_rx671_ek/e2studio_ccrx`
- `sha256` tableに`.cproject`、BSP、FWUP、LittleFS、`sdio_host.c`、`whd_port_resource.c`、map、MOT、WHD 3 blobのSHA-256を記録

manifestなしは`UNKNOWN`、SHA/source/config不一致は`FAIL`とする。
したがって、固定SHAと構成を結び付けられない古いmap/MOTは構造解析のdetailには表示できるが、`map_image_single_area`または`mot_image_single_area`をPASSにはしない。

| gate | PASS条件 | 現行clean tree |
|---|---|---|
| `source_inputs` | 必須設定をすべて解析できる | PASS |
| `bootloader_layout` | RX671専用bootloader map、明示予約range、source provenanceを確認し、アプリ/WHDと非重複かつ両bankの必要配置を確認 | UNKNOWN |
| `rom_capacity` | 選択MCUのROM容量をBSP生成物から導出できる | PASS |
| `fwup_data_flash_geometry` | FWUPのstart/block-size/block-countがBSPとRX671 FITに完全一致する | PASS |
| `littlefs_data_flash_geometry` | LittleFSのrange/erase/program geometryがBSPとRX671 FITに整合する | PASS |
| `data_flash_non_overlap` | LittleFSが全8 KiBの唯一のownerで、LittleFS以外のlinker consumer、raw install/key-store/OTA payloadがないことを全経路で証明 | UNKNOWN |
| `fwup_partition` | 各1 MiB bankの先頭に同じinstall area sizeを置き、bank容量を超えない。末尾予約はbootloader gateで別途検証 | PASS |
| `dual_bank_mode` | `.cproject=bank.dual`かつBSP=Dual mode | FAIL |
| `application_in_main_area` | アプリanchorがmain内にある | FAIL |
| `static_image_single_area` | code-flash anchorが1領域だけにある | FAIL |
| `whd_resources_follow_application` | WHD 3 section anchorがすべて存在し、アプリanchorと同じ領域にある | FAIL |
| `sdio_resource_addressing` | primitive pathとWHD providerが`g_type1yn_*` linker symbolを実参照し、code flash固定値を含まない | FAIL |
| `fwup_code_flash_layout` | main/bufferのheader/descriptor予約range、`main+0x300`の実app anchor、area末尾の実vector anchorが一致 | FAIL |
| `artifact_provenance` | 現行source/configとmap/MOT/WHD blobをmanifestのSHA-256で結び付ける | UNKNOWN |
| `whd_blob_sizes` | provenance済み3実ファイルの測定サイズが宣言値と一致する | UNKNOWN |
| `map_image_single_area` | provenance済みmapの全code-flash sectionが1領域に収まる | UNKNOWN |
| `mot_image_single_area` | provenance済みMOTの全code-flash load byteが1領域に収まる | UNKNOWN |

終了コードは、全PASSが`0`、1個以上のFAILが`1`、FAILなしでUNKNOWNありの場合が`2`である。
bootloader、map/MOT、WHD実ファイル、provenance manifestのいずれかがない場合も成功扱いにしない。

## 次の判断点

現在の阻害要因はWHD資材そのものの254,634 bytesではなく、Linear mode、2領域に分散したlinker配置、code flash上のFWUP header/descriptor予約、Data Flash単独所有の全経路証跡、bootloader実装がないことである。
ただし、選択したmain領域へ収まるという最終判断には、OTA/Fleetを含む現行mainのmap、WHD実ファイル、FWUP v2 packed image、RX671 bootloaderを同じ構成で測定する必要がある。
これらの証跡が揃うまで、software OTAの実機結合へ進めない。

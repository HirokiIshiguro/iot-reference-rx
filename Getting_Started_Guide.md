# スタートガイド

* 本書では、各デモの概要と実行方法を説明します。
* これらのデモは FreeRTOS 202406.04 LTS ライブラリに対応しています。
* 本書のアップストリーム版では、主に CK-RX65N v2 について説明しています。
* このフォークでは、`Projects/aws_bg96_ck_rx65n/` に CK-RX65N V1 + Quectel BG96 セルラー OTA リファレンスも用意しています。

## デモの概要

デモが正常に動作しない場合は、[トラブルシューティング](#トラブルシューティング)を参照してください。

次の表に、利用できるデモの組み合わせを示します。

|デモ名|参照する AWS IoT コンテンツ|概要|関連情報|
| ---- | ---- | ---- | ---- |
|PubSub/MQTT|[coreMQTT デモ](https://docs.aws.amazon.com/freertos/latest/userguide/mqtt-demo.html)|デバイスと AWS サーバー間の基本的な MQTT 通信を実演します。|- [Ethernet プロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ether_ck_rx65n_v2/ether_pubsub_information.md)<BR>- [セルラープロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_pubsub_information.md)<BR>- [Wi-Fi プロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_pubsub_information.md)|
|Fleet Provisioning 対応 PubSub/MQTT|[Fleet Provisioning を使用して、デバイス証明書なしでデバイスをプロビジョニングする](https://docs.aws.amazon.com/iot/latest/developerguide/provision-wo-cert.html)|Fleet Provisioning を実行した後、AWS サービスを使用して PubSub を行います。|- [Ethernet プロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ether_ck_rx65n_v2/ether_fleet_information.md)<BR>- [セルラープロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_fleet_information.md)<BR>- [Wi-Fi プロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_fleet_information.md)|
|Over-the-air（OTA）対応 PubSub/MQTT|[OTA チュートリアル](https://docs.aws.amazon.com/freertos/latest/userguide/dev-guide-ota-workflow.html)|デバイスのファームウェアを更新する手順を示します。|- [Ethernet プロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ether_ck_rx65n_v2/ether_ota_information.md)<BR>- [セルラープロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_ota_information.md)<BR>- [Wi-Fi プロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_ota_information.md)<BR>- [ブートローダープロジェクト](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/boot_loader_ck_rx65n_v2/bootloader_information.md)|

各デモは独立した FreeRTOS タスクとして動作するため、複数のデモを同時に実行できます。

各デモは [coreMQTT-Agent](https://github.com/FreeRTOS/coreMQTT-Agent) ライブラリを使用し、複数のタスクで1つの MQTT 接続を共有します。Ethernet、セルラー、または Wi-Fi を介して AWS IoT Core に MQTT プロトコルで接続します。
各タスクは、サーバー認証とクライアント認証を使用する TLS 接続を確立し、MQTT のサブスクライブ／パブリッシュ処理を実行します。

> **注記**:
>
> * TCP minimal は、新規プロジェクト（PG）として作成した場合にのみ生成されます。使用方法は [minimal_tcp/README.md](https://github.com/renesas/iot-reference-rx/blob/accf243603b068bf6e8d88be76c433f8b9125da5/Configuration/samples/minimal_tcp/README.md) を参照してください。

## デモの実行方法

<details>
<summary>手順を開く</summary>

この章では、プロジェクトを e2 studio にインポートしてデモを実行する手順を順番に説明します。
次の FAQ に従って新規プロジェクト（PG）として作成する場合は、ステップ1とステップ3を省略できます。
<https://github.com/renesas/iot-reference-rx/wiki/Creating-and-importing-a-FreeRTOS-project#create-a-new-freertos-project>

### 前提条件

#### ハードウェア要件

* [CK-RX65N v2](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/ck-rx65n-cloud-kit-based-rx65n-mcu-group)
  * Ethernet
  * セルラー通信を使用する場合は、Cellular（CAT-M1）モジュールとして [RYZ014A](https://www.renesas.com/br/en/products/wireless-connectivity/cellular-iot-modules/ryz014a-lte-cat-m1-cellular-iot-module)[（廃止済み）](https://www.renesas.com/document/eln/plc-240004-end-life-eol-process-select-part-numbers?r=1503996)
    * この製品は生産終了済みであり、テクニカルサポートが制限される場合があります。
  * Wi-Fi 通信を使用する場合は、Wi-Fi モジュールとして [DA16600](https://www.renesas.com/us/en/products/wireless-connectivity/wi-fi/low-power-wi-fi/da16600mod-ultra-low-power-wi-fi-bluetooth-low-energy-combo-modules-battery-powered-iot-devices)
* このフォークで保守しているセルラーリファレンス用の CK-RX65N V1 + BG96
  * アプリケーション: `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/`
  * ブートローダー: `Projects/boot_loader_ck_rx65n/e2studio_ccrx/`

#### ソフトウェア要件

* IDE: [e2 studio](https://www.renesas.com/software-tool/e-studio#download) 2025-12
* コンパイラ:
  * [CC-RX](https://www.renesas.com/software-tool/cc-compiler-package-rx-family) V3.07.00
  * [GCC](https://llvm-gcc-renesas.com/rx-download-toolchains/) for Renesas RX v14.2.0.202505
* コード生成ツール: [RX Smart Configurator](https://www.renesas.com/software-tool/rx-smart-configurator)
  * e2 studio と同時にインストールされます。
* シリアル端末アプリケーション: Tera Term など
  * [Tera Term v5.5.0](https://github.com/TeraTermProject/teraterm/releases/tag/v5.5.0) の使用を推奨します。

#### サンプルプロジェクトの選択

接続方式ごとに、次の表に示すサンプルプロジェクトがあります。

| RX MCU／ボード | 接続方式 | プロジェクト名 | ブートローダー | コンパイラ | 備考 |
|:-----------------|:-------------|:-------------|:------------|:---------|:-------|
| CK-RX65N v2 | Ethernet | aws_ether_ck_rx65n_v2 | boot_loader_ck_rx65n_v2 | CC-RX/GCC |
| CK-RX65N v2 | Cellular（Cat-M1、廃止済み） | aws_ryz014a_ck_rx65n_v2 | boot_loader_ck_rx65n_v2 |CC-RX/GCC|   |
| CK-RX65N v2 | Wi-Fi（DA16600） | aws_da16600_ck_rx65n_v2 | boot_loader_ck_rx65n_v2 | CC-RX/GCC |  |
| CK-RX65N V1 | Cellular（BG96） | aws_bg96_ck_rx65n | boot_loader_ck_rx65n | CC-RX | このフォークで保守しているセルラーリファレンス |

手順ごとに実行できるデモの組み合わせを次に示します。

|操作手順|マクロ設定|PubSub|Fleet Provisioning|OTA|
|---|---|---|---|---|
|[ステップ4-1:<BR>PubSub/MQTT サンプルプロジェクトの実行](#ステップ4-1-pubsubmqtt-サンプルプロジェクトの実行)|`ENABLE_FLEET_PROVISIONING_DEMO (0)`<BR>`ENABLE_OTA_UPDATE_DEMO (0)`|✓|-|-|
|[ステップ4-2:<BR>Fleet Provisioning 対応 PubSub/MQTT サンプルプロジェクトの実行](#ステップ4-2-fleet-provisioning-対応-pubsubmqtt-サンプルプロジェクトの実行)|`ENABLE_FLEET_PROVISIONING_DEMO (1)`<BR>`ENABLE_OTA_UPDATE_DEMO (0)`|✓|✓|-|
|[ステップ4-3:<BR>Over-the-air（OTA）更新対応 PubSub/MQTT サンプルプロジェクトの実行](#ステップ4-3-over-the-airota更新対応-pubsubmqtt-サンプルプロジェクトの実行)|`ENABLE_FLEET_PROVISIONING_DEMO (0)`<BR>`ENABLE_OTA_UPDATE_DEMO (1)`|✓|-|✓|

* マクロは `\src\frtos_config\demo_config.h` で設定します。
* 上の表のステップ4を実行する前に、必ずステップ1～3を完了してください。

---

### ステップ1: 本製品のダウンロード

[ステップ3](#ステップ3-e2-studio-へのプロジェクトのインポート)では、e2 studio を使用して GitHub からプロジェクトをダウンロードし、インポートする手順を説明します。
GitHub からプロジェクトを直接取得することもできます。
その場合は、次のコマンドでこのリポジトリをクローンします。

* 長いパス名を有効にする場合:

  ```text
  git config --global core.longpaths true
  ```

* 環境に応じたクローンコマンドを実行します。
  * HTTPS を使用してクローンする場合:

    ```text
    git clone https://github.com/renesas/iot-reference-rx.git -b v202406.04-LTS-rx-1.2.0 --recurse-submodules
    ```

  * SSH を使用してクローンする場合:

    ```text
    git clone git@github.com:renesas/iot-reference-rx -b v202406.04-LTS-rx-1.2.0 --recurse-submodules
    ```

> **注記**:
>
> GitHub からプロジェクトを直接クローンした場合は、e2 studio で **Import** -> **Existing Projects into Workspace** を選択してプロジェクトをインポートしてください。

### ステップ2: ハードウェアのセットアップ

#### 通信用の接続

1. Ethernet を使用する場合のハードウェアセットアップ
    * インターネットに接続された Ethernet ケーブルを、デバイスボードの Ethernet ポートに接続します。
2. セルラーを使用する場合のハードウェアセットアップ
    * [**RYZ014A のハードウェアセットアップ**](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_pubsub_information.md#hardware-setup)
3. Wi-Fi を使用する場合のハードウェアセットアップ
    * [**DA16600 のハードウェアセットアップ**](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_pubsub_information.md#hardware-setup)

#### 電源供給、デバッグ、ログ取得用の接続

詳細は、[CK-RX65N v2 ユーザーズマニュアル](https://www.renesas.com/document/mat/ck-rx65n-v2-users-manual?r=1611756)を参照してください。

1. デバイスボードのジャンパーを次のように設定します。
    * MCU 電流測定ポイントを無効にするため、J2 をショートします。
    * MCU のブートオプションをシングルチップモードにするため、J11 をオープンにします。
    * デバッグ用に J16 の1-2間をショートします。
2. 電源供給とデバッグのため、CK-RX65N v2 のデバッグコネクター（J14）と、e2 studio をインストールした PC を USB ケーブルで接続します。
    このコネクターは、電源供給とデバッグの両方に使用します。
3. デバッグログを受信するため、CK-RX65N v2 の USB シリアルコネクター（J10）と、シリアル端末アプリケーションをインストールした PC を USB ケーブルで接続します。

> **注記**: ここでいうデバッグログは、デモプログラムと Renesas ドライバーソフトウェアに実装されたシリアル出力データです。
> e2 studio 上で行うデバッグとは直接関係ありません。

* Ethernet 使用時のボード設定図:
![2](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step2_v2_ether.png?raw=true)
* [セルラー使用時のボード設定図](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_pubsub_information.md#board-settings-image)
* [Wi-Fi 使用時のボード設定図](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_pubsub_information.md#board-settings-image)

### ステップ3: e2 studio へのプロジェクトのインポート

デモプロジェクトを IDE である e2 studio にインポートします。

1. e2 studio を起動します。
1. ワークスペースを選択し、**Launch** をクリックします。
1. **File** -> **Import...** -> **Renesas GitHub FreeRTOS (with IoT libraries) Project** の順に選択します。
1. プロジェクトのインポート先フォルダーを指定します。
   次に、**RTOS version setting** で `v202406.04-LTS-rx-1.2.0` を選択し、**Next** ボタンをクリックします。
   ![step3-1](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step3_1_project_import1_l3_s3.png?raw=true)
1. 指定したバージョンが見つからない場合は、**Manage RTOS** をクリックして、必要な FreeRTOS Module をダウンロードします。
   * **Download Configuration** 画面で `FreeRTOS (with IoT libraries) for RX` を選択し、**OK** ボタンをクリックします。
   * 必要なバージョンの **FreeRTOS (with IoT libraries)** をチェックします。
     このとき、**Module Folder Path** には10文字以下の短いパスを設定してください。
     **Download** ボタンをクリックします。
     ![step3-2](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step3_2_project_import2_l3_s3.png?raw=true)
1. GitHub から指定したフォルダーにプロジェクトがダウンロードされます。
1. **Import Projects** 画面で `aws_ether_ck_rx65n_v2` をチェックし、**Finish** ボタンをクリックしてプロジェクトをインポートします。
 ![step3-3](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step3_3_project_import3_l3_s3.png?raw=true)
   この画面では、次のプロジェクトを選択できます。
   必要なプロジェクトをチェックしてインポートしてください。

   | プロジェクト名                       | コンパイラ | 接続方式     |
   |--------------------------------------|------------|--------------|
   |aws_ether_ck_rx65n_v2\e2studio_ccrx   | CC-RX    | Ethernet     |
   |aws_ether_ck_rx65n_v2\e2studio_gcc    | GCC      | Ethernet     |
   |aws_ryz014a _ck_rx65n_v2\e2studio_ccrx| CC-RX    | Cellular     |
   |aws_ryz014a _ck_rx65n_v2\e2studio_gcc | GCC      | Cellular     |
   |aws_da16600_ck_rx65n_v2\e2studio_ccrx | CC-RX    | Wi-Fi        |
   |aws_da16600_ck_rx65n_v2\e2studio_gcc  | GCC      | Wi-Fi        |
   |boot_loader_ck_rx65n_v2\e2studio_ccrx | CC-RX    | -            |
   |boot_loader_ck_rx65n_v2\e2studio_gcc  | GCC      | -            |

    > **注記**:
    > 同じ接続方式の `CC-RX` プロジェクトと `GCC` プロジェクトを同時にインポートすることはできません。

### ステップ4: デモの実行

#### ステップ4-1: PubSub/MQTT サンプルプロジェクトの実行

以降、この節では「PubSub/MQTT サンプルプロジェクト」を「PubSub デモ」と呼びます。

##### ステップ4-1-1: PubSub デモ用ソフトウェアのセットアップ

###### PubSub デモで実行するデモの組み合わせの設定

実行するデモの組み合わせを選択します。
`Projects\<project_name>\e2studio_ccrx\src\frtos_config\demo_config.h` で `ENABLE_FLEET_PROVISIONING_DEMO` と `ENABLE_OTA_UPDATE_DEMO` の両方を設定すると、対応しているデモの組み合わせを選択できます。

> **注記**:
>
> * 上記の *<project_name>* は、「サンプルプロジェクトの選択」で説明したプロジェクト名です。
> * 既定のデモアプリケーションは「PubSub デモ」です。PubSub デモのみを実行するには、OTA デモと Fleet Provisioning デモを無効にします。

* `ENABLE_FLEET_PROVISIONING_DEMO`: (0)
* `ENABLE_OTA_UPDATE_DEMO`: (0)
![4-1-1](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_1config_l3_2.png?raw=true)

###### FIT モジュールのダウンロード

FIT モジュールは RX Smart Configurator を使用してダウンロードできます。
Smart Configurator のコンポーネントツリーに灰色のアイコンが表示される場合、該当するコンポーネントが環境に存在しないため、必要なコンポーネントをダウンロードする必要があります。
すでにインストールされている場合は、ダウンロード手順を省略してください。
灰色のアイコンが付いたモジュールをクリックし、**Downloading it** を選択して不足しているモジュールをダウンロードします。
![4-1-1](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/Step4_1_1_download_FIT_2.png?raw=true)

##### 接続方式ごとの設定

###### 1. セルラーを使用する場合

* [フック関数の設定](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_pubsub_information.md#settings-of-the-hook-function)
* [アクセスポイントの設定](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_pubsub_information.md#settings-of-access-point)
* [バンドの設定](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_pubsub_information.md#settings-of-bands)

###### 2. Wi-Fi を使用する場合

* [フック関数の設定](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_pubsub_information.md#settings-of-the-hook-function)
* [国コードと GMT タイムゾーンの設定](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_pubsub_information.md#settings-of-country-code-and-gmt-timezone)
* [Wi-Fi ネットワークの設定](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_pubsub_information.md#settings-of-wi-fi-network)

##### ステップ4-1-2: PubSub デモのビルド

e2 studio のビルダーでファームウェアイメージをビルドします。
e2 studio の **Project Explorer** ペインでプロジェクトを右クリックし、**Build Project** を選択します。ビルドが完了するまで待ちます。

> **注記**: **Project** -> **Build Project** メニューを選択してビルドすることもできます。

![4-1-1](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/4_1_3_build_l3_2.png?raw=true)

##### ステップ4-1-3: PubSub デモ用 RSA キーペアとデバイス証明書の作成

新しい IoT Thing を作成するときに、AWS コンソールで RSA キーペアとデバイス証明書を生成できます。
**Auto-generate a new certificate** を使用して IoT Thing を作成する方法の詳細は、次のページを参照してください。
<https://github.com/renesas/iot-reference-rx/wiki/Register-device-to-AWS-IoT>

リンク先の手順に従うと、次の3つのファイルが生成されます。

* xxxx-certificate.pem.crt
* xxxx-public.pem.key
* xxxx-private.pem.key

##### ステップ4-1-4: PubSub デモ用シリアル端末アプリケーションのセットアップ

Tera Term を使用する場合は、次のように設定します。

* 改行設定: **Setup** -> **Terminal** -> **New-line**
  * **Receive**: AUTO
  * **Transmit**: CR+LF

  ![4-1-4](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_4_teraterm_setting1_l3_s3.png?raw=true)
* シリアルポート設定: **Setup** -> **Serial port**
  * **Port**: 使用する COM ポート
* **Speed**: 115200
* **Data**: 8 bit
* **Parity**: none
* **Stop bits**: 1 bit
* **Flow control**: none
  ![4-1-4](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_4_teraterm_setting2_l3_s3.png?raw=true)

##### ステップ4-1-5: AWS MQTT テストクライアントの設定

PubSub デモを実行すると、AWS 上で通信メッセージを確認できます。
その前に、**MQTT test client** を設定する必要があります。

* AWS マネジメントコンソールで IoT Core の **MQTT Test Client** ページを開きます。
  <https://us-east-2.console.aws.amazon.com/iot/home?region=us-east-2#/test>

> **注記**: 上記の URL は例です。使用するリージョンに対応する AWS のページに変更してください。

* **Subscribe to a topic** をクリックし、**Topic filter** に `#` を入力します。
* **Additional configuration** をクリックし、**MQTT payload display** で **Display payloads as strings (more accurate)** を選択します。
* **Subscribe** ボタンをクリックします。
  ![4-1-5](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_5_l3_s3.png?raw=true)
* デモを実行すると、通信メッセージを確認できます。
  メッセージの確認方法は、[ステップ4-1-9](#ステップ4-1-9-aws-mqtt-テストクライアントでのメッセージ確認)を参照してください。

##### ステップ4-1-6: PubSub デモの書き込み

e2 studio の **Project Explorer** パネルでプロジェクトを右クリックし、**Debug As** --> **Renesas GDB Hardware Debugging** を選択します。
 ![4-1-5](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_5debug_start_l3_2.png?raw=true)

次の画面が表示された場合は、**Switch** を押します。
 ![4-1-5](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_5debug_message.PNG?raw=true)

次のボタンを押してデバッグを開始します。
デバッグ開始後10秒以内に、[ステップ4-1-7](#ステップ4-1-7-pubsub-デモの-cli-入力)の最初のコマンドを Tera Term から入力する必要があります。
すぐに入力できるよう、あらかじめ Tera Term を準備しておくことを推奨します。
 ![4-1-5](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_5_press_start_l3_2.png?raw=true)

##### ステップ4-1-7: PubSub デモの CLI 入力

デモの起動時に、シリアル端末アプリケーション上で CLI が動作します。
AWS との通信を開始するため、シリアル端末アプリケーションから次のコマンドを入力します。

コマンド入力の流れは次のとおりです。

1. CLI モードに切り替えます。
1. IoT 情報（Thing 名と MQTT エンドポイント）を設定します。
1. セキュリティ情報（デバイス証明書と秘密鍵）を設定します。
1. ここまでの変更をコミットします。
1. リセットしてデモを再起動します。

###### CLI モードへの切り替え

デモを起動すると、すぐに CLI が自動的に動作します。
最初に、次のコマンドを入力して CLI モードに切り替えます。

```text
> CLI
Going to FreeRTOS-CLI !
```

 ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_1_l3_2.PNG?raw=true)

> **注記**:
>
> * CLI コマンドでは大文字と小文字が区別されるため、正しい表記で入力してください。
> * CLI は数秒後にタイムアウトします。タイムアウト後、デモのユーザーアプリケーションが動作します。

###### IoT 情報の設定

次に、データフラッシュをフォーマットします。

```text
> format
Format OK !
```

 ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_2.PNG?raw=true)

次に、使用する Thing 名／MQTT デバイス識別子を設定します。

```text
> conf set thingname <iot-thing name>
OK.
```

 ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_3thingname.PNG?raw=true)

次に、使用するアカウントの MQTT エンドポイントを設定します。

```text
> conf set endpoint <endpoint for your account>
OK.
```

 ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_4endpoint_l3_2.PNG?raw=true)

> **注記**: AWS アカウントのエンドポイントは、`aws iot describe-endpoint` コマンド、または AWS IoT Core コンソールの *Domain configurations* ページで確認できます。

###### 対象デバイスのセキュリティ情報の設定

次に、デバイス証明書を設定します。
[ステップ4-1-3: PubSub デモ用 RSA キーペアとデバイス証明書の作成](#ステップ4-1-3-pubsub-デモ用-rsa-キーペアとデバイス証明書の作成)で生成した "xxxx-certificate.pem.crt" を Tera Term にドラッグ＆ドロップします。

```text
> conf set cert <Drag and drop crt file>
```

 ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_5cert_l3_2.PNG?raw=true)

> **注記1**:
>
> * Tera Term を使用して `\<device certificate\>` を入力する場合は、`conf set cert` と入力した後、証明書ファイルを端末画面にドラッグ＆ドロップします。表示された画面で `Send File (Paste content of file)` を選択し、`OK` を押します。
>   証明書ファイルの内容が入力されます。
> * ファイルをドロップした後に表示される **File Drag and Drop** 画面で、`Binary` チェックボックスを選択します。
  ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_9_binary_l3_s3.png?raw=true)

次に、デバイスの秘密鍵を設定します。
[ステップ4-1-3: PubSub デモ用 RSA キーペアとデバイス証明書の作成](#ステップ4-1-3-pubsub-デモ用-rsa-キーペアとデバイス証明書の作成)で生成した "xxxx-private.pem.key" を Tera Term にドラッグ＆ドロップします。

```text
> conf set key <Drag and drop key file>
```

 ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_6key_l3_2.PNG?raw=true)

> **注記**:
>
> * Tera Term を使用して `\<private key\>` を入力する場合は、`conf set key` と入力した後、秘密鍵ファイルを端末画面にドラッグ＆ドロップします。表示された画面で `Send File (Paste content of file)` を選択し、`OK` を押します。
>   秘密鍵ファイルの内容が入力されます。
> * ファイルをドロップした後に表示される **File Drag and Drop** 画面で、`Binary` チェックボックスを選択します。
  ![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_9_binary_l3_s3.png?raw=true)

###### 設定変更のコミット

次に、ステージされている設定変更をデータフラッシュにコミットします。

```text
> conf commit
```

![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_7.PNG?raw=true)

###### 対象デバイスのリセットとデモの再起動

最後に、次のコマンドで対象デバイスをリセットし、デモを再起動します。

```text
> reset
```

![4-1-6](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_6_8reset_l3_2.png?raw=true)

##### ステップ4-1-8: PubSub デモの想定出力

デモが再起動したら、何も入力せずに CLI がタイムアウトするまで待ちます。
その後、デモが実行され、次の出力が表示されます。

* **PubSub Demo Task 0** と **PubSub Demo Task 1** が正常に完了します。
![4-1-7](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_7_1_l3_1.png?raw=true)

> **注記**: PubSub Demo Task 0 と PubSub Demo Task 1 は、それぞれデモメッセージを10回パブリッシュした後、デモトピックのサブスクライブを解除します。

##### ステップ4-1-9: AWS MQTT テストクライアントでのメッセージ確認

[ステップ4-1-5](#ステップ4-1-5-aws-mqtt-テストクライアントの設定)で MQTT テストクライアントを設定すると、PubSub デモから送信されたメッセージを AWS 上で確認できます。

* [ステップ4-1-5](#ステップ4-1-5-aws-mqtt-テストクライアントの設定)で設定した MQTT テストクライアントのページを表示します。
* **MQTT test client** コンソールにパブリッシュされたメッセージ "*Task x publishing message x*" を確認できます。
正常に動作すると、次の図のように AWS コンソールに表示されます。![4-1-9](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/step4_1_9_l3_s3.png?raw=true)

---

#### ステップ4-2: Fleet Provisioning 対応 PubSub/MQTT サンプルプロジェクトの実行

* 以降、この節では「Fleet Provisioning 対応 PubSub/MQTT サンプルプロジェクト」を「Fleet Provisioning 対応 PubSub デモ」と呼びます。
* *Fleet Provisioning 対応 PubSub デモ* の詳細は、アプリケーションノート（文書番号: **R01AN8016**）に記載されています。
  次のページを参照してください。
  * <https://www.renesas.com/document/apn/rx-family-how-implement-aws-iot-fleet-provisioning-202406-lts-version?r=1471546>
  このアプリケーションノートは Ethernet プロジェクトを対象としていますが、セルラープロジェクトと Wi-Fi プロジェクトも記載された手順で動作します。
* このデモを実行するときは、RX Smart Configurator の設定を確認してください。
  Smart Configurator のコンポーネントツリーに灰色のアイコンが表示される場合、該当するコンポーネントが環境に存在しません。
  必要なモジュールをダウンロードする方法は、「[**FIT モジュールのダウンロード**](#fit-モジュールのダウンロード)」を参照してください。

##### Fleet Provisioning 対応 PubSub デモの注意事項

* 必ず前述のアプリケーションノートに記載された手順に従ってください。
* *通常フロー* から外れた場合のデータフラッシュ使用量は保証されません。
* 次に、*異常フロー* で Fleet Provisioning を実行する例を示します。
  1. デモプログラムが初めて CLI モードに入ったときにデータフラッシュをフォーマットし、通常どおりエンドポイント、テンプレート、クレーム証明書、クレーム秘密鍵を設定してコミットします。
  1. Fleet Provisioning と PubSub デモが完了した後、デバイスをリセットします。
  1. リセット後にデモプログラムが再度 CLI モードに入ったときに、新しいデバイスクレデンシャル一式を設定してコミットします。
* *通常フロー* では、Fleet Provisioning 後のデータフラッシュ使用量は約7808バイトです。
* *異常フロー* では、Fleet Provisioning でプロビジョニングされた既存のクレデンシャルを、新しいデバイスクレデンシャルが上書きします。
  * この場合、さらに1408バイトを使用します。
* 現在、AWS とデバイス間の最大応答レイテンシーは5000 ms に設定されています。
誤差の余裕を確保できるよう、十分に長い値を設定しています。
レイテンシーを短縮する場合は、使用環境に合わせて調整してください。
`Demos\common\Mqtt_Demo_Helpers\mqtt_pkcs11_demo_helper.c`
`mqttexamplePROCESS_LOOP_TIMEOUT_MS (5000U)`

---

#### ステップ4-3: Over-the-air（OTA）更新対応 PubSub/MQTT サンプルプロジェクトの実行

* *Over-the-air（OTA）更新対応 PubSub/MQTT サンプルプロジェクト* の詳細は、アプリケーションノート（文書番号: **R01AN7662**）に記載されています。
  次のページを参照してください。
  * <https://www.renesas.com/document/apn/rx-family-how-implement-freertos-ota-using-amazon-web-services-202406-lts-version-rev110?r=1471546>
* このデモの実行方法は、前述のアプリケーションノートの「*2. Prerequisites*」以降を参照してください。
* このアプリケーションノートは Ethernet プロジェクトを対象としていますが、セルラープロジェクトと Wi-Fi プロジェクトも記載された手順で動作します。
* このデモを実行するときは、RX Smart Configurator の設定を確認してください。
  Smart Configurator のコンポーネントツリーに灰色のアイコンが表示される場合、該当するコンポーネントが環境に存在しません。
  必要なモジュールをダウンロードする方法は、「[**FIT モジュールのダウンロード**](#fit-モジュールのダウンロード)」を参照してください。
* OTA で使用するブートローダーの詳細は、次を参照してください。
  [**bootloader_information.md**](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/boot_loader_ck_rx65n_v2/bootloader_information.md)

---
</details>

## トラブルシューティング

<details>
<summary>詳細を開く</summary>

### 1. OTA 更新の転送速度の改善

* OTA の実行時間を短縮するには、`mqttexampleTRANSPORT_RECV_TIMEOUT_MS` を150以上に設定します。
* 送信と受信のタイムアウト値を個別に設定したうえで、既定値を150以上に設定してください。

### 2. 接続エラー発生時のタイムアウトの改善

通信環境が原因で通信中にエラーが発生する場合は、各定義を次の「修正値」に変更すると改善することがあります。

|定義名|説明|既定値|修正値|パス|
| ---- | ---- | ---- | ---- | ---- |
|mqttexampleTRANSPORT_RECV_TIMEOUT_MS|トランスポート層でデータを受信するときのタイムアウト時間（ミリ秒）です。TLS ハンドシェイクエラーが発生する場合は、この値を大きくしてみてください。この値を変更すると MQTT 通信時間に影響するため、通信環境に合わせて調整してください。|450|`750`|Demos\mqtt_agent\mqtt_agent_task.c|
|MQTT_AGENT_MAX_EVENT_QUEUE_WAIT_TIME|MQTT エージェントタスクが、コマンドキューにコマンドが到着するまで Blocked 状態（CPU 時間を消費しない状態）で待機する時間（ミリ秒）です。この時間を超えると Blocked 状態を終了し、`MQTT_ProcessLoop()` を呼び出します。|50U|`1000U`|src\frtos_config\core_mqtt_agent_config.h|

ただし、各定義はデモの実行時間に影響します。
上記の値を設定すると、デモの実行時間が長くなる場合があります。

### 3. MAC アドレスの変更方法

サンプルプロジェクトで使用する MAC アドレスは、Smart Configurator で変更できます。
ボードに割り当てられた MAC アドレスは、ボードの Ethernet コネクターに貼られたステッカーで確認できます。
ステッカーが貼られていない場合は、[ツールニュース](https://www.renesas.com/document/tnn/notification-information-about-ck-rx65n-mac-address?r=1611756)を確認してください。
![TroubleShooting_0_1_MAC_Address_Board](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/TroubleShooting_0_1_MAC_Address_Board_v2.png)
MAC アドレスは、Smart Configurator の FreeRTOS Kernel から変更できます。
**Components** -> **FreeRTOS Kernel** -> **MAC address X**（X = 0～5）を変更します。
設定を変更した後は、必ず **Generate Code** と **Build** を実行してください。
![TroubleShooting_0_2_MAC_Address](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/TroubleShooting_0_2_MAC_Address.png)

### 4. 初回のファームウェア書き込み後、実行時に LittleFS エラーメッセージが表示される場合

ファームウェアを書き込んでプログラムを実行すると、CLI メニューの表示後に次のエラーメッセージが表示される場合があります。

```log
/xxxx/iot-reference-rx/Middleware/3rdparty/littlefs/lfs.c:1225:error: Corrupted dir pair at {0x1, 0x0}
```

ファームウェアの書き込み直後に表示されるこのメッセージは、問題を示すものではありません。そのまま処理を続行してください。
> **注記**:
> このメッセージは、データフラッシュ上のファイルシステムがまだ初期化されていない場合に表示されます。
> メッセージの表示後、データフラッシュが初期化され、ファイルシステムがマウントされます。

### 5. セルラープロジェクトのトラブルシューティング

* [セルラーのトラブルシューティング](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ryz014a_ck_rx65n_v2/ryz014a_pubsub_information.md#troubleshooting)

### 6. Wi-Fi プロジェクトのトラブルシューティング

* [Wi-Fi のトラブルシューティング](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_da16600_ck_rx65n_v2/da16600_pubsub_information.md#troubleshooting)

### 7. OTA プロジェクトのトラブルシューティング

* [OTA のトラブルシューティング](https://github.com/renesas/iot-reference-rx/blob/v202406.04-LTS-rx-1.2.0/Projects/aws_ether_ck_rx65n_v2/ether_ota_information.md#troubleshooting)

</details>

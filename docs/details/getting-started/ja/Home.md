# Welcome to the AWS IoT Reference for Renesas RX MCUs
[English](../en/Home.md) / [日本語(本ページ)](Home.md)  
1. [チュートリアル](#チュートリアル)
1. [トラブルシューティング](#トラブルシューティング)

## はじめに
RXファミリでは、AWSデバイス認定を取得した評価キットおよびFree RTOSプロジェクトで、IoT機器開発をサポートいたします。  
RXファミリが提供するAWSクラウドと連携した各種ソリューションは、以下の図を参照ください。  

```mermaid
flowchart TB
classDef blue fill:#06418c,stroke:#fff,stroke-width:2px,color:#fff
    Start(Development of IoT devices using RX)
    Start -->|Step1|CK
subgraph CK[Trial connection to AWS]
direction TB
    KitPage[Learn about and purchase<br>the CK-RX65N<br> - Wi-Fi and Ethernet -]:::blue
        click KitPage "https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/ck-rx65n-cloud-kit-based-rx65n-mcu-group"
    KitPage --> Step1[Trial connecting to AWS<br>with a dashboard demo for CK-RX65N]:::blue
        click Step1 "https://www.renesas.com/document/qsg/aws-cloud-connectivity-ck-rx65n-v2-wi-fi-da16600-getting-started-guide"
end
    CK --> |Step2|FreeRTOS
subgraph FreeRTOS[IoT device development]
direction TB
subgraph iotref[ ]
direction TB
style iotref fill-opacity:0, stroke-opacity:0;
    GSG[Getting Start Guide]:::blue
        click GSG "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md"
end
subgraph with[Demo projects that connected to AWS cloud using AWS libraries]
direction TB
subgraph dummy[ ]
style dummy fill-opacity:0, stroke-opacity:0;
    GSG --- MQTT[MQTT]:::blue-.-MQTT_Video[Video]:::blue
        click MQTT "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-run-demos"
        click MQTT_Video "https://www.renesas.com/ajax/show-video/25570839"
    GSG --- OTA[OTA]:::blue-.-OTA_Video[Video]:::blue
        click OTA "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-3-run-pubsubmqtt-with-over-the-airota-update-sample-project"
        click OTA_Video "https://www.renesas.com/video/freertos-ota-tutorial-ck-rx65n-13-cloud-operation"
    GSG --- Fleet[Fleet<br>Provisioning]:::blue-.-Fleet_Video[Video]:::blue
        click Fleet "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-2-run-pubsubmqtt-with-fleet-provisioning-sample-project"
        click Fleet_Video "https://www.renesas.com/video/freertos-fleet-provisioning-tutorial-ck-rx65n-12-iot-devices-cloud-operation"
    GSG --- TSIP[TLS with<br>TSIP]:::blue-.-TSIP_Video[Video]:::blue
        click TSIP "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-4-run-pubsubmqtt-with-over-the-airota-update-sample-project-tls-with-tsip"
        click TSIP_Video "https://www.renesas.com/ajax/show-video/25566619"
end
end

subgraph minimalproject[Demo project that does not include AWS libraries]
direction TB
style Comment fill-opacity:0, stroke-opacity:0;
style portingmemo fill-opacity:0, stroke-opacity:0;
    Comment[Provides basic TCP/IP<br>functionaly using<br>Free RTOS Kernel<br>and FreeRTOS-Plus-TCP]-.-portingmemo[How to create FreeRTOS-Plus-TCP minimal sample project on the other MCUs other than RX65N]
    GSG --- minimal[Free RTOS TCP minimal]:::blue-.-porting[Porting Guide]:::blue
    click minimal "https://github.com/renesas/iot-reference-rx/blob/accf243603b068bf6e8d88be76c433f8b9125da5/Configuration/samples/minimal_tcp/README.md"
    click porting "../en/FreeRTOS-Plus-TCP-Porting-Guide.md"
end
end
    FreeRTOS --- |Various solutions to support development|items

subgraph items[Collateral]
direction RL
    subgraph APN
        2nd[2ndry Device<br>Update]:::blue
            click 2nd "https://www.renesas.com/document/scd/rx65n-group-sample-code-ota-update-secondary-device-amazon-web-services-use-freertos-rev200"
        FWUP[FW Update FIT]:::blue
            click FWUP "https://www.renesas.com/document/apn/rx-family-firmware-update-module-using-firmware-integration-technology-application-notes"
    end
    subgraph Tool
        QE[QE for OTA]:::blue
            click QE "https://www.renesas.com/software-tool/qe-ota-development-assistance-cloud"
    end
    subgraph Wiki[This Wiki]
        Tutorial
        TroubleShooting
        info[Useful Information]
    end
end
```

## 最新情報
  最新のAPN・セミナ情報は、[＜Renesas公式ページ＞](https://www.renesas.com/jp/ja/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/cloudsolutions)をご参照ください  

## チュートリアル
MQTT通信やOTA、Fleet Provisioning機能を搭載したデモプロジェクトに関する最新の使用方法は、[Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md)を参照ください。  
AWSでの各種設定方法や、e² studioでの操作手順などの詳細を確認したい場合は、以下のチュートリアルも併せてご確認ください。  
1. [デバイスをAWS-IoTに登録する](デバイスをAWS-IoTに登録する.md)
1. [FreeRTOSプロジェクトの入手](FreeRTOSプロジェクトの新規作成・インポート.md)  
 [FreeRTOSプロジェクトをインポートする(zip)](FreeRTOSプロジェクトの新規作成・インポート.md#freertosプロジェクトのインポート)  
 [FreeRTOSプロジェクトをe2studioで新規作成する](FreeRTOSプロジェクトの新規作成・インポート.md#freertosプロジェクトの新規作成) 
1. [FreeRTOSプロジェクトでAWS IoT Coreへの接続に必要な設定を行う](FreeRTOSプロジェクトでAWS-IoT-Coreへの接続に必要な設定.md) 
1. [Amazon FreeRTOSを実行し、RXデバイスをAWS IoTに接続する](FreeRTOSプログラムを実行し、AWS-IoTに接続する.md)

## トラブルシューティング
[トラブルシューティング](トラブルシューティング.md)ページをご確認ください。

## FreeRTOS 関連外部リンク集
1. [Amazon FreeRTOS](https://aws.amazon.com/freertos/)
1. [Amazon FreeRTOS の使用開始](https://docs.aws.amazon.com/freertos/latest/userguide/freertos-getting-started.html)
1. [Amazon FreeRTOS ドキュメント](https://docs.aws.amazon.com/freertos/)
	1. [Amazon FreeRTOS ユーザーガイド](https://docs.aws.amazon.com/freertos/latest/userguide/index.html)
	1. [Amazon FreeRTOS API リファレンス](https://docs.aws.amazon.com/freertos/latest/lib-ref/index.html)
	1. [FreeRTOS カーネルの基礎](https://docs.aws.amazon.com/ja_jp/freertos/latest/userguide/dev-guide-freertos-kernel.html)
## リアルタイムOS解説動画
1. [RTOSチュートリアル（1/7）：なぜRTOSは必要なのか](https://www.youtube.com/watch?v=1emOuolz4ZA)
2. [RTOSチュートリアル（2/7）：タスク](https://www.youtube.com/watch?v=GIw7vFGxAb4)
3. [RTOSチュートリアル（3/7）：ハンドラ](https://www.youtube.com/watch?v=FuYVv410cvo&t=788s)
4. [RTOSチュートリアル（4/7）：システムコール その1](https://www.youtube.com/watch?v=9DlphuPJmv8&t=40s)
5. [RTOSチュートリアル（5/7）：システムコール その2](https://www.youtube.com/watch?v=G9IiFfhLxG4&t=10s)
6. [RTOSチュートリアル（6/7）：構造と性能](https://www.youtube.com/watch?v=Xo4kfilMs_g)
7. [RTOSチュートリアル（7/7）：マルチコアとRTOS](https://www.youtube.com/watch?v=DBa25wjrVoo)

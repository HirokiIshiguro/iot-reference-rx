# Getting Start Guide
下表のデバイスでは、AWS Partner Device認定を取得しています。  
Getting Start Guideやアプリケーションノート(APN)を使用し、すぐにIoT機器開発に着手いただけます。  
※各デバイス毎に対応するFreeRTOSのバージョンは異なります。  
　最新のRX向けFreeRTOSプログラムは、[Renesas GitHub](https://github.com/renesas/iot-reference-rx)に掲載されます。  
　上記にご利用のデバイス向けFreeRTOSが掲載されていない場合、[こちらの旧GitHubリポジトリ](https://github.com/renesas/amazon-freertos/releases)をご確認ください。

| MCU | Boards | Wi-Fi | Ether | LTE CAT-M1 | AWS Partner Device Catalog | Getting Start Guide | Startup APN for IoT development |
| ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| RX65N | [CK-RX65N v1](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/ck-rx65n-cloud-kit-based-rx65n-mcu-group) | - | Supported | Supported | [Link](https://devices.amazonaws.com/detail/a3G8a00000Et8xUEAR/Renesas-CK-RX65N) | [Link](https://www.renesas.com/document/qsg/rx65n-connecting-aws-cloud-freertos-getting-started-guide-ck-rx65n) | [Link](https://www.renesas.com/document/qsg/sim-activation-creating-trial-account-and-using-dashboard-ryz014a-or-ethernet-application-aws) 
| RX65N | [CK-RX65N v2](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/ck-rx65n-cloud-kit-based-rx65n-mcu-group) | Supported | Supported | - | - | - | [Link](https://www.renesas.com/document/qsg/aws-cloud-connectivity-ck-rx65n-v2-wi-fi-da16600-getting-started-guide?r=1471546) |
| RX65N | [RX65N CloudKit](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx65n-cloud-kit-renesas-rx65n-cloud-kit) | Supported | - | - | [Link](https://devices.amazonaws.com/detail/a3G0h000000P0lFEAS/RX65N-Cloud-Kit) |  [Link](https://www.renesas.com/document/qsg/connecting-aws-cloud-freertos-getting-started-guide-renesas-rx65n-cloud-kit-rev100) | <- |
| RX65N | [Renesas Starter Kit+ for RX65N-2MB](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx65n-2mb-starter-kit-plus-renesas-starter-kit-rx65n-2mb) | - | Supported | - | [Link](https://devices.amazonaws.com/detail/a3G0L00000AAOkeUAH/Renesas-Starter-Kit-for-RX65N-2MB) |  [Link](https://www.renesas.com/document/qsg/connecting-aws-cloud-freertos-getting-started-guide-renesas-starter-kit-rx65n-2mb-rev100) | <- |
| RX72N | [RX72N Envision Kit](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx72n-envision-kit-rx72n-envision-kit) | Supported(*) | - | - | [Link](https://devices.amazonaws.com/detail/a3G0h00000E1zpfEAB/RX72N-Envision-Kit) |  [Link](https://www.renesas.com/document/qsg/connecting-aws-cloud-freertos-getting-started-guide-renesas-rx72n-envision-kit-rev100) | <- |
| RX671 | [Renesas Starter Kit+ for RX671](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx671-starter-kit-plus-renesas-starter-kit-rx671) | Supported(*) | - | - | [Link](https://devices.amazonaws.com/detail/a3G0h00000E20zqEAB/Renesas-Starter-Kit-for-RX671) |  [Link](https://www.renesas.com/document/qsg/getting-started-renesas-starter-kit-rx671) | <- |

※別売りの[Wi-Fi Pmod拡張ボード](https://www.renesas.com/products/microcontrollers-microprocessors/ra-cortex-m-mcus/wi-fi-pmod-expansion-board-80211bgn-24g-wi-fi-pmod-expansion-board)が必要です
# Data visualization in the cloud
RXファミリでは、デバイスで収集したセンサデータをAWSクラウドサービスに送信しグラフとして可視化するAPNをご用意しています。  
- [CK-RX65N(Cellular / Ethernet)](https://www.renesas.com/document/scd/ck-rx65n-sim-activation-creating-trial-account-and-using-dashboard-getting-started-guide-ck-rx65n?r=1471546)
- [CK-RX65N(Wi-Fi)](https://www.renesas.com/document/scd/ck-rx65n-sim-activation-creating-trial-account-and-using-dashboard-getting-started-guide-ck-rx65n?r=1471546)
- [RX65N CloudKit(Wi-Fi)](RX65N-Cloud-Kitでセンサデータを可視化する.md)
- [RX72N EnvisionKit(Wi-Fi)](https://www.renesas.com/document/apn/rx72n-group-using-quick-connect-iot-send-sensor-information-amazon-web-services-rx72n-envision-kit?r=1471546)
※別売り[Wi-Fi Pmod拡張ボード](https://www.renesas.com/products/microcontrollers-microprocessors/ra-cortex-m-mcus/wi-fi-pmod-expansion-board-80211bgn-24g-wi-fi-pmod-expansion-board)使用

# Remote firmware update via OTA
RXファミリでは、AWSクラウドサービスを利用した遠隔からのOTAファームウェアアップデートを実現するソリューションを提供しています。
- [FW Updateの設計方針](https://www.renesas.com/jp/ja/document/apn/renesas-mcu-firmware-update-design-policy-rev100?r=1471546&r=1471546)  
ルネサスMCUにおけるファームウェアアップデートの設計方針を掲載したAPN。  
FW Updateのセキュリティおよびメカニズム、ブートローダの実装などを理解いただけます。
- [FW Update Fitモジュール v1.06](https://www.renesas.com/document/scd/rx-family-firmware-update-module-using-firmware-integration-technology-sample-code?r=1499716&r=1471546) / [FW Update Fitモジュール v2.01](https://www.renesas.com/document/scd/rx-family-firmware-update-module-using-firmware-integration-technology-application-notes-rev200)  
FW Updateの実装を支援するFitモジュール。  
e² studioをご利用の場合、IDEから直接ダウンロードすることが可能です。
- [AWS FreeRTOS OTAの実現方法](https://www.renesas.com/document/apn/rx-family-how-implement-freertos-ota-using-amazon-web-services-rx65n-rev102?r=1471546&r=1471546)  
RXファミリ向けにポーティングしたFreeRTOSプロジェクトを使い、AWSクラウドサービスと連携してOTAを行う手順を解説したAPN。
- [開発支援ツール QE for OTA](https://www.renesas.com/software-tool/qe-ota-development-assistance-cloud-technical-preview-edition)  
e² studioのGUIでOTAを容易に実現する開発支援ツール。  
AWSコンソールでの煩雑な操作をe² studio上ですべて設定することができ、OTAを簡単にお試しいただけます。
- [セカンダリデバイスのOTA FW Update](https://www.renesas.com/document/scd/rx65n-group-sample-code-ota-update-secondary-device-amazon-web-service-using-freertos-rev110-sample?r=1471546)  
ゲートウェイデバイスに接続されたデバイス（2ndryデバイス）のOTAを実現するAPN。
本APNを活用することで、直接ネットワークに接続していないデバイスのOTAファームウェアアップデートを実現できます。
<img src="https://github.com/renesas/iot-reference-rx/assets/121073232/45db0efb-1578-4fd7-a3c7-303b583f8cac" width="600">

# Fleet Provisioning
- [IoT デバイスのためのプロビジョニング手法](https://www.renesas.com/document/apn/rx-family-provisioning-procedure-iot-devices-rev100)  
量産時に課題となる複数デバイスのプロビジョニングを自動で処理するAWS Fleet Provisioningを簡単に実行できるサンプルプログラムです。  
Fleet Provisioningのサンプルプログラムは、e² studioのプロジェクト生成機能からもご利用いただけます。
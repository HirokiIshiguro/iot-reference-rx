# はじめに
RX65N-Cloud-Kitでは、AWSのサービスを使用してセンサデータを可視化することが可能です。  
※「Renesas web dashboard」は、AWSのサービスで代替できることから、2022年に提供を終了いたしました。  
# センサデータの可視化方法
センサデータの可視化をお試しいただく場合は、以下のAPNをご利用ください。  
1. ドキュメント：  
[RX65N Cloud Kit でFreeRTOS を用いてAmazon Web Servicesでセンサー情報を可視化および制御する方法](https://www.renesas.com/document/apn/visualizing-and-controlling-sensor-information-using-amazon-web-services-rx65n-cloud-kit-and?r=1471546)  
サンプルプログラム：  
[Visualizing and Controlling Sensor Information Using Amazon Web Services with RX65N Cloud Kit and FreeRTOS](https://www.renesas.com/document/scd/visualizing-and-controlling-sensor-information-using-amazon-web-services-rx65n-cloud-kit-and?r=1471546)
1. [Quick-Connect IoT を活用してFreeRTOS を搭載したRX72N Envision Kit からセンサ情報をAmazon Web Services に送信する方法](https://www.renesas.com/document/apn/rx72n-group-using-quick-connect-iot-send-sensor-information-amazon-web-services-rx72n-envision-kit?r=1471546)
1. [デバイスをAWS IoTに登録する(github.com)](デバイスをAWS-IoTに登録する.md)  
  
「1」で使用しております「Amazon Elasticsearch Service」というサービスは、現在「Amazon OpenSearch Service」としてAWSより提供されております。  
一部UIも変更されておりますので、「Amazon OpenSearch Service」については、「2」の資料で使用方法をご確認ください。  
また、デバイスの登録については、「3」のGitHubにて最新のAWSコンソールに合わせた情報を掲載しております。  
APNの情報が古い場合は、「3」も併せてご確認ください。
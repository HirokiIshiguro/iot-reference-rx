# はじめに
本項では、RXファミリ向けFreeRTOSプロジェクトでAWS IoT Coreに接続し、トピックをサブスクライブする方法を紹介します。  
事前に以下の設定を行ってください。  
また、RX向けFree RTOSプロジェクトの最新の利用方法は[Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md)を参照ください。  
1. [デバイスをAWS-IoTに登録する](デバイスをAWS-IoTに登録する.md)
1. [FreeRTOSプロジェクトの入手](FreeRTOSプロジェクトの新規作成・インポート.md)  
 [FreeRTOSプロジェクトをインポートする(zip)](FreeRTOSプロジェクトの新規作成・インポート.md)  
 [FreeRTOSプロジェクトをe2studioで新規作成する](FreeRTOSプロジェクトの新規作成・インポート.md) 
1. [FreeRTOSプロジェクトでAWS IoT Coreへの接続に必要な設定を行う](FreeRTOSプロジェクトでAWS-IoT-Coreへの接続に必要な設定.md) 

本項は、AWSに登録したモノの証明書情報を含んだFreeRTOSプロジェクトが、正常にビルドできている状態を前提とします。

# IoT Core コントロールパネルでデバイスからのメッセージを待ち受ける設定を行う

* IoT Core コントロールパネルで トピックへのサブスクライブを行う
	* [IoT Core のコントロールパネルに移動](デバイスをAWS-IoTに登録する.md#awsマネジメントコンソールにログイン)
	* テスト -> MQTTテストクライアント -> トピックをサブスクライブする  
-> トピックのフィルターに「#」を指定(ワイルドカード) -> サブスクライブ

![01_AWSIoTCoreへの接続_MQTTクライアント](https://user-images.githubusercontent.com/121073232/217982904-599ac24d-449f-45e4-8b2a-d7d14ec812df.png)

# デバッグログを表示する
AWS Partner Device認定を取得したRenesas製評価ボード用サンプルプログラムでは、デバッグログを出力します。  
デバッグログの出力先は、評価ボードによって異なります。  
詳細は評価ボードのGettingStartGudeを参照ください。
* 評価ボードとPCをUSBケーブルで接続する（接続するUSBポートは各ボードのGettingStartGude参照）
* PC上でTeraTermを起動し、シリアルポートの設定を以下にする
    * ボーレート：115200 bps
    * データ：8 bit
    * パリティ：none
    * ストップ：1 bit
    * フロー制御：none

# FreeRTOSプロジェクトをRX MCUにダウンロード
* e2 studio 画面左上の 虫 アイコンを押す

![02_AWSIoTCoreへの接続_e2デバッガ接続](https://user-images.githubusercontent.com/121073232/217982928-98235440-00d6-4c17-98d3-fdada0b4b587.png)

* パースペクティブの切り替えの確認は「はい」を選択

![03_AWSIoTCoreへの接続_e2パースペクティブ](https://user-images.githubusercontent.com/121073232/217982946-4dc68830-0a3d-4ad6-a90d-b0933a5d0682.png)

# プログラムを実行

* Restart ボタンを押す

![04_AWSIoTCoreへの接続_e2リスタート](https://user-images.githubusercontent.com/121073232/217982961-3e3636f8-6bf1-409e-b0b9-0bc78cd1faca.png)

* main() にブレークすることを確認

![05_AWSIoTCoreへの接続_e2main](https://user-images.githubusercontent.com/121073232/217982989-839527f2-6c27-4436-a542-4ceec013767c.png)

* 再開 ボタンを押す

![06_AWSIoTCoreへの接続_e2再開](https://user-images.githubusercontent.com/121073232/217983008-ca39c930-fe47-4714-bef1-18f097176f6b.png)

# IoT Core コントロールパネル で デバイスからの メッセージを確認する
* FreeRTOSプロジェクトで定義されたメッセージが表示されることを確認  
※定義されているメッセージはプロジェクトによって異なります  
（例：「Hello World」「Task X publishing message XX」）

![07_AWSIoTCoreへの接続_MQTT_getmesse](https://user-images.githubusercontent.com/121073232/217983034-75c18c77-86df-46a0-947e-36940ab1b621.png)

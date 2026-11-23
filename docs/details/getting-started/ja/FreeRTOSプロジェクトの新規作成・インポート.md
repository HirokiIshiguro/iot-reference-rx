# はじめに
本項では、RXファミリ向けにポーティングされたFreeRTOSプロジェクトをe² studioで使用するための方法を解説します。  
FreeRTOSプロジェクトは、e² studioのプロジェクト新規作成機能を使用し作成することができます。  
また、サンプルプログラムやアプリケーションノート（APN）同梱のzipファイルや、本リポジトリからクローンしたプロジェクトをインポートすることも可能です。  

# e² studioでFreeRTOSプロジェクトの開発を行う方法
以下いずれかの方法で、e² studioを使用したFreeRTOSプロジェクトの開発が可能です。  
一からFreeRTOSプロジェクトでの開発をはじめる場合は、[新規作成機能を使用する方法](#freertosプロジェクトの新規作成)を推奨します。  
RX向けFree RTOSプロジェクトの最新の利用方法は[Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md)を参照ください。
* [FreeRTOSプロジェクトの新規作成機能を使用する方法](#freertosプロジェクトの新規作成)
	* e² studioで新規作成する＜推奨＞
* [FreeRTOSプロジェクトをe² studioにインポートする方法](#freertosプロジェクトのインポート)
	* GitHubからクローンしてインポート
	* サンプルプログラム・APNのzipファイルを解凍してインポート

# FreeRTOSプロジェクトの新規作成
1.	e² studioでCC-RXまたはGCC for Renesas RX用Executableプロジェクトを作成してください。<br>
1.	「RTOS」欄で「FreeRTOS (with IoT libraries)」を選択してください。<br>
    ![JP-1-STEP2-SelectRTOS](https://github.com/user-attachments/assets/185162d0-144d-4b58-8748-610d9efb0670)

    ※1：「RTOS」欄の「FreeRTOS (with IoT libraries)(deprecated structure)」は互換性のために残してあります。新規開発の場合は「FreeRTOS (with IoT libraries)」を選択することを推奨します。<br>
    ※2：「RTOS version」欄に何も表示されていない場合、「Manage RTOS versions」を選択して最新バージョンをダウンロードしてください。 <br>
    ※3：「Target Board」欄で対応していないボードを選択するとプロジェクト作成できません。「Target Board」欄の選択肢に"CK-RX65N-V2"がない場合は「Download additional boards...」をクリックしてボード定義ファイルダウンロードしてください。<br>
    ![JP-2-STEP2-Note3-TargetBoard](https://github.com/user-attachments/assets/7c2a3773-9971-4947-af76-76d2027970e9)


1.	サンプルプロジェクトの選択画面に遷移します(下記の例は 202406-LTS-rx-1.0.1)。<br>
サンプルプロジェクトの詳細はそれぞれ以下のドキュメントを参照してください。<br>
    - (Ethernet) Minimal sample project:<br>
    FreeRTOS KernelとFreeRTOS-Plus-TCPを使用したTCP/IP通信を行います。<br>
    RX65N以外のRXファミリマイコンでご利用の場合は、[ポーティングガイド（英語）](../en/FreeRTOS-Plus-TCP-Porting-Guide.md)をご確認ください。<br>
    - (Ethernet) PubSub/MQTT sample project:<br>
    AWS IoT Core に対してPubSubメッセージを送信します。<br>
    ![JP-3-STEP3-SlectMinimalSampleProject](https://github.com/user-attachments/assets/765c95b2-24b9-42f4-8a5e-179d0ebf617b)

# FreeRTOSプロジェクトのインポート
以降の項目では、ダウンロードしたFreeRTOSプロジェクトをe² studioにインポートする手順を紹介します。  
* 主にアプリケーションノート（APN）・サンプルプログラムなどのZipファイルや、  
GitHubからクローンしたプロジェクトのインポートを想定しています
* ダウンロードしたプロジェクトによっては、一部フォルダ名・フォルダ構成が異なる場合があります
* 図・説明中にあるボード名等お客様環境特有の言葉は、適宜ご利用の環境に合わせ読み替えてください

# ベースフォルダの定義
* ダウンロード後解凍またはgitでクローンした Amazon FreeRTOS のルートフォルダを ${base_folder} と表記します
* ${base_folder} には demos や tests フォルダが存在します
* **ベースフォルダは、Cドライブ直下等浅いパスにしてください**  
パス全長が256文字を超えるとe² studioはビルド時にエラーを出力します
* 下図は、C直下ws2というフォルダにGitHubからクローンしたamazon-freertosを配置した場合の例です  
C:\ws2\amazon-freertosが${base_folder}になります  
※APNなどの場合、フォルダ名がamazon-freertosと異なる場合があります
![01_FreeRTOSプロジェクトインポート_ルートフォルダ](https://user-images.githubusercontent.com/121073232/217969394-262ff642-0740-4c34-98dd-76abac98ef0d.png)

# e² studio 起動 / プロジェクトインポート
* e² studio のアイコンをダブルクリックして起動
![02_FreeRTOSプロジェクトインポート_e2起動](https://user-images.githubusercontent.com/121073232/217969435-a934d9b9-d65a-4cd4-90af-9a3132ba6f55.png)

* ワークスペースを指定 -> 起動
![03_FreeRTOSプロジェクトインポート_ルートフォルダ](https://user-images.githubusercontent.com/121073232/217969451-c6a6436e-1287-4bec-a892-b2050d0d58a5.png)

* e² studio起動確認
![04_FreeRTOSプロジェクトインポート_e2初期画面](https://user-images.githubusercontent.com/121073232/217969471-90b40fe4-bab8-4b23-8c3a-529cbfa0cfb5.png)

* ファイル -> インポート  
![05_FreeRTOSプロジェクトインポート_インポート](https://user-images.githubusercontent.com/121073232/217969493-0eb7df1b-8ec8-4425-8c9f-81337b7a406f.png)

* 既存プロジェクトをワークスペースへ  
![06_FreeRTOSプロジェクトインポート_既存プロジェクトをワークスペースへ](https://user-images.githubusercontent.com/121073232/217969523-f116621e-f6c9-4437-9601-6aff89755c12.png)

* 参照ボタンでインポートするフォルダーを指定 -> フォルダーの選択
	* CC-RXを使用する場合
		* ${base_folder}/projects/renesas/使用ボード名/e2studio/ を指定
	* GCCを使用する場合
		* ${base_folder}/projects/renesas/使用ボード名/e2studio-gcc/を指定
* 画像は、以下のプロジェクトを使用する場合の例  
ボード　　　：CK-RX65N（CAT.M1モジュールRYZ014A使用）  
コンパイラ　：GCC
![07_FreeRTOSプロジェクトインポート_フォルダーの選択](https://user-images.githubusercontent.com/121073232/217969551-8b44198f-92e0-43f8-9bd8-8e8f2067bfb1.png)

* インポートするプロジェクトにチェック -> 終了
	* AWSクラウドサービスへの接続のみの場合：aws_demosにチェック
	* OTA FW Updateを行う場合：aws_demos, boot_loaderの2つにチェック
	* 「プロジェクトをワークスペースにコピー」にチェックが入っていないことを確認
* 下図はOTA FW Updateを行う場合の例です
![08_FreeRTOSプロジェクトインポート_プロジェクトの選択](https://user-images.githubusercontent.com/121073232/217969576-27542d6d-114e-456b-88d7-5f6b359aa689.png)

* 隠すボタンで「Welcome to e² studio」画面を閉じ、プロジェクトエクスプローラを表示させる

![09_FreeRTOSプロジェクトインポート_隠すボタン](https://user-images.githubusercontent.com/121073232/217969592-d9f12173-ecb0-4389-9200-a53f8396ff41.png)<br>
↓<br>
![10_FreeRTOSプロジェクトインポート_プロジェクトエクスプローラ](https://user-images.githubusercontent.com/121073232/217969654-a2ff15bf-3150-4972-804d-47c38b6f43d9.png)

* プロジェクト -> クリーン
	* 複数のプロジェクトをインポートしている場合は、「すべてのプロジェクトをクリーン」にチェック
	* ビルドを即時に開始 -> ワークスペース全体をビルド　-> クリーン

![11_FreeRTOSプロジェクトインポート_クリーン](https://user-images.githubusercontent.com/121073232/217969673-dc8d2a50-6062-4cea-8db0-549dba53a357.png)

* ビルドエラーが発生しないことを確認
![12_FreeRTOSプロジェクトインポート_ビルド結果](https://user-images.githubusercontent.com/121073232/217969694-4d2138db-df9a-41bd-b8ea-00e03978bc59.png)

# AWSへの接続
AWSへの接続には、AWS IoT Coreへのモノの登録やFreeRTOSプログラムへの証明書・鍵の登録が必要です。  
ご利用のサンプルプログラム・APNに合わせ各種設定を実施してください。  
  
* サンプルプログラム・APNをご使用の場合、サンプルプログラム・APNのドキュメントをご確認ください
* AWS Partner Device認定済みプログラムをご使用の場合、[Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md)を参照ください
* GettingStartGudeやAPNのドキュメントは、開発当時の画面表示・設定方法を掲載しています  
AWSコンソールの最新表示に対応した情報が必要な場合は、以下を併せて参照ください  
[デバイスをAWS-IoTに登録する](デバイスをAWS-IoTに登録する.md)
# はじめに
本項では、AWS IoT Coreのコンソールからデバイスを新規登録する方法を示します。  
RX向けFree RTOSプロジェクトの最新の利用方法は[Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md)を参照ください。

# AWSアカウントを取得する
* [AWSアカウントを取得する](https://aws.amazon.com/jp/?nc2=h_lg) -> 画面右上の「無料サインアップ」ボタンから。
	* AWS利用検討時には、AWS無料利用枠が使用可能です。
		* [AWS無料利用枠](https://aws.amazon.com/jp/free/?sc_iplace=hero-static-text-link&sc_icontent=awssm-evergreen-1st-visit-text-link&sc_icampaign=acq_aws_takeover-1st-visit&trk=ha_awssm-evergreen-1st-visit-text-link)

# AWSマネジメントコンソールにログイン
* [Amazon Web Services](https://aws.amazon.com/jp/?nc2=h_lg) -> アカウント -> AWSマネジメントコンソール

![01_AWS_アカウント作成](https://user-images.githubusercontent.com/121073232/217968137-97b0978d-5355-49f2-a736-e2ef2fa36ead.png)

# IoT Core のコントロールパネルに移動
* 画面上部の検索窓に`IoT Core`と入力
* 検索結果 -> サービス -> IoT Core

![02_AWS_IoTCore検索](https://user-images.githubusercontent.com/121073232/217968195-4ccf96c0-093a-4a3a-a619-a7bb27c53ad7.png)

# 安全性のポリシーを作成

* セキュリティ -> ポリシー -> ポリシーの作成

![03_AWS_ポリシー作成](https://user-images.githubusercontent.com/121073232/217968227-8a7255df-2e00-438f-aacb-b915843c67a4.png)

* ポリシー名を入力(任意文字列)

![04_AWS_ポリシー名](https://user-images.githubusercontent.com/121073232/217968279-dd347316-27ba-47f1-b1e7-f9a304a0f179.png)

* ポリシーステートメント -> ポリシードキュメント -> ビルダー -> 新しいステートメントを追加  
* 「新しいステートメントを追加」を3回クリックし、ステートメントの枠を4つに増やす
![05_AWS_ポリシーステートメントの追加](https://user-images.githubusercontent.com/121073232/217968321-30d0f010-90bd-4da9-86d9-7981c47fc92c.png)

* 以下のポリシーアクションを許可にし、ポリシーリソースにワイルドカード`*`を設定  

	| ポリシーアクション  　　　　　| 意味  　　　　　　　　　　　　　　　　　　　　　|
	| ------ | ------ |
	| iot:Connect | AWS IoT に接続する |
	| iot:Publish | トピックをパブリッシュ（送信）する |
	| iot:Subscribe | トピックをサブスクライブ（受信）する |
	| iot:Receive| AWS IoT からメッセージを受信する|

![06_AWS_ポリシーステートメントの設定](https://user-images.githubusercontent.com/121073232/217968389-c24bd66b-73d1-468c-b38a-e558eb44b6b6.png)

* 作成
![07_AWS_ポリシーステートメントの作成](https://user-images.githubusercontent.com/121073232/217968420-6d297c3b-d6e9-420c-8316-4ff38568258a.png)

* 作成が完了すると、画面上部に以下のバナーが表示
![08_AWS_ポリシーステートメントの作成完了](https://user-images.githubusercontent.com/121073232/217968452-c6f71bb0-5546-4d4c-87bf-90b78318443c.png)

# デバイス(モノ)をAWS IoTに登録する

* 管理 -> すべてのデバイス -> モノ -> モノを作成
![09_AWS_モノの作成](https://user-images.githubusercontent.com/121073232/217968472-b5451a34-2581-4b82-83ef-1ea3e462c8f6.png)

* モノを作成 -> 1つのモノを作成
![10_AWS_モノの作成_1つのモノを作成](https://user-images.githubusercontent.com/121073232/217968482-8b46a966-9f64-4b3a-a28d-39a24bd348fb.png)

* モノのプロパティ -> モノの名前 に任意の名前を入力 ->「次へ」
* モノの名前をテキストエディタ等にメモ(後で使用します)
![11_AWS_モノの作成_モノのプロパティを指定](https://user-images.githubusercontent.com/121073232/217968494-63f3be56-2b57-4e0d-804d-1768992c3767.png)

* デバイス証明書を設定 - オプション -> 新しい証明書を自動生成（推奨） -> 次へ
![12_AWS_モノの作成_デバイス証明書を設定](https://user-images.githubusercontent.com/121073232/217968524-9303bdb4-72b0-4ca2-a036-4e60038f565f.png)

* 証明書にポリシーをアタッチ – オプション -> 使用するポリシーに☑ ->モノを作成
![13_AWS_モノの作成_証明書にポリシーをアタッチ](https://user-images.githubusercontent.com/121073232/217968548-0107fa6a-d1c8-44a5-9e9c-8ace513eedff.png)

* 証明書とキーをダウンロード -> 完了
	* 以下をダウンロード  
	※必ずダウンロードしてください。この画面以降、キーファイルはダウンロードできません。
		* **デバイス証明書**
		* **パブリックキーファイル**
		* **プライベートキーファイル**  
![14_AWS_モノの作成_キーのダウンロード](https://user-images.githubusercontent.com/121073232/217968571-e15ac3e8-7e44-4a94-8109-9f0402cb2090.png)

* モノの作成が完了すると以下のバナーが表示されます
![16_AWS_モノの作成_完了](https://user-images.githubusercontent.com/121073232/217968640-3163ac47-c0c4-44ea-9303-2403cd218484.png)

# AWS IoTのエンドポイントを確認する

* エンドポイントをテキストエディタ等にメモ(後で使用します)
![15_AWS_エンドポイント](https://user-images.githubusercontent.com/121073232/217968606-66c84635-32ab-4714-9914-9102c0a98f35.png)

# 以降のステップ
本項目でエディタ等にメモした情報は、以降のステップで使用します。  
プロジェクトへの情報登録などの手順は、以下のページ、もしくはご使用のサンプルプログラムのドキュメントをご参照ください。
1. [デバイスをAWS-IoTに登録する（本項）](デバイスをAWS-IoTに登録する.md)
1. [FreeRTOSプロジェクトの入手](FreeRTOSプロジェクトの新規作成・インポート.md)  
 [FreeRTOSプロジェクトをインポートする(zip)](FreeRTOSプロジェクトの新規作成・インポート.md#freertosプロジェクトのインポート)  
 [FreeRTOSプロジェクトをe2studioで新規作成する](FreeRTOSプロジェクトの新規作成・インポート.md#freertosプロジェクトの新規作成) 
1. [FreeRTOSプロジェクトでAWS IoT Coreへの接続に必要な設定を行う](FreeRTOSプロジェクトでAWS-IoT-Coreへの接続に必要な設定.md) 
1. [Amazon FreeRTOSを実行し、RXデバイスをAWS IoTに接続する](FreeRTOSプログラムを実行し、AWS-IoTに接続する.md)

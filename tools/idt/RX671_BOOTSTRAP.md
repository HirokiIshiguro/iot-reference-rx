# RX72N・RX65N・RX671の初期boot trust

3環境の実機IDTは、初回起動の前に公開署名鍵をLittleFSへ保存し、署名付きapplicationをdual-bank bootloaderから起動します。共通基盤の変更後について確認済みなのは部品ビルドとhost検証までです。新基盤の実機IDT PASSはまだ確認していません。

## CIとローカル実行の入力

実機scope（`transport`、`mqtt`、`ota-mqtt`、`pkcs11`、`ota-pal`）では、CIが[prepare_public_signer.py](prepare_public_signer.py)で4資料を自動生成します。`plan`とhost-only `preflight`では生成しません。確認済み資料で置き換える場合は、次の4入力を全て指定してください。部分指定は拒否します。

| 環境変数 | 入力 |
|---|---|
| `IDT_PUBLIC_SIGNER_PROVISIONER_MOT_FILE` | 公開署名鍵投入用のstandalone dual-bank MOT |
| `IDT_PUBLIC_SIGNER_PROVISIONER_MANIFEST_FILE` | 同MOTの正式な`provisioner-manifest.json` |
| `IDT_PUBLIC_SIGNER_CERT_FILE` | P-256署名鍵の公開証明書PEM 1件 |
| `IDT_PUBLIC_SIGNER_PUBLIC_KEY_FILE` | 同じ鍵の公開鍵PEM 1件 |

生成は[共通producer](../build_public_signer_provisioner.py)の`rx-dual-public-signer-provisioner-v1`を使用します。IDT buildと同じsource SHAで、`formal=true`、`source_tree_dirty=false`、`bank.dual`、`credentials_embedded=false`を満たすmanifestが必要です。MOTの実アドレス・MDE・初期bank0・reset vector・コンパイル済みsource識別子も検査します。通常のIDT applicationを保守用MOTの代わりには使えません。

`prepare_public_signer.py`はclean checkoutとcheckout外の新しいprivate outputを要求します。既存outputや設定済み4入力は上書きしません。成功時のstdoutは環境変数名から4つのパスへのJSONだけです。証明書は[正規の生成工具](../generate_signer_cert.py)で作り、対象の開発用署名鍵から同じ公開鍵を取り出します。秘密鍵の値・PEM本文・私有compilerログは公開artifactへ含めません。

公開PEMは4KiB以内の単一オブジェクトとして検査し、private headerや後続オブジェクトは本文を読み込む前に拒否します。[native実行](run_idt.py)は確認済みの公開入力をprivate runtimeの`inputs/public-signer-bootstrap`へコピーします。初期RSUの署名鍵との一致は[共通controller](public_signer_provision.py)で再検査します。

## 実機で行う処理

既存bench lockとglobal RFP lockを保持して、各独立imageの開始状態を揃えます。

1. RFP chip eraseを独立した1コマンドで完了し、Code Flash・Data Flash・flash optionを消去します。
2. 保守用dual-bank MOTを書き込み、対象UARTを開いて起動します。実機のsource SHA識別子とCLI応答を確認します。
3. LittleFSをformatし、`codesigncert`・`codesignpubkey`の2公開PEMを保存してcommitします。
4. 両bankのapplication領域だけを消去し、Data Flashとbootloader領域を保持して、bank0とbank1のbootloaderを書き込みます。
5. 署名付きCode FlashのみのRSUをstrict UART downloaderで導入します。Data Flashは同梱せず、実署名検査と起動成功を必須にします。

bootloaderはLittleFS公開鍵・ECDSA必須・built-in fallback無効・旧Data Flash鍵ストア無効・raw Data Flash install無効です。bank1の画像はbank0の正確なアドレス移動として確認します。ローカルの計画は`runtime_trust=not_established`を記録し、実機署名検査が完了するまで信頼設定済みとは扱いません。

全3環境の共有領域は`0x00100000`から8KiB、littlefsは2.11.3です。RX72Nの旧開始位置とRX65N/RX72Nの旧容量から移行するため、初回formatと再provisionが必要です。既存設定がそのまま残るとは扱わず、実機での移行結果を記録してください。API・geometry・mutexのhost検証は[製品port](../../Common/littlefs_common/README.md)に記載しています。

終了時はresetコマンド成功と、新しい1秒間のUART静止を確認します。RESET端子の電圧測定は実行条件に含めません。reset失敗・UART出力継続・privileged子processの終了不明では所有記録を保持して再利用を止めます。

全3環境のtransaction上限は[cleanup_budget.py](cleanup_budget.py)が算出する1565秒で、公開鍵投入CLIの絶対上限は200秒です。中断時resetの90秒は別枠です。終了を確認できないRFP子processは`<rfp_lock>.unsafe.json`で再利用を停止し、失敗したSSH callbackのprivate stagingも保持します。個別scopeの成功を全IDT合格やAWS正式認定とは扱いません。

RX671で確認した旧linear画像の起動不良は、現在の共通経路とは別の実機調査記録です。

<details>
<summary>過去のRX671調査と開始状態の根拠</summary>

[#168](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/168)では、OTA後の起動bank状態からlinear provisionerを一括書込みすると、verify成功後も旧bootloaderを指す現象を実機で再現しました。同じ通常FWもdual/000からの初回と2回目で配置が変わったため、2回書込みによる収束には依存せず、chip eraseを先に完了する経路を採用しました。

この調査は過去のsourceと画像に対する証拠です。保守用を含む現在のdual-bank統一、新しいLittleFS領域、全3環境の初期trust経路の実機合格には流用しません。過去IDTの対象SHAと結果は[検証記録](../../docs/idt-validation.md)を参照してください。

</details>

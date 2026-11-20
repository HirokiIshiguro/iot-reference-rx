# Fleet Provisioning の実装仕様

[[_TOC_]]

この文書は、[機能仕様書](../architecture.md#2-機能と実装仕様書)の機能「Fleet Provisioning」の実装仕様書です。仕様書キーは `FLEET` で、試験は `IREF-FLEET-001`〜`IREF-FLEET-012` です（[試験仕様](../test-specification.md)）。

## 1. 決まり

| 番号 | 決まり | 対象 |
|---|---|---|
| 1 | 申請用の証明書（claim 証明書）と鍵で、AWS IoT Core につなぐ | 全基板 |
| 2 | CSR を送り、新しい証明書を受け取る | 全基板 |
| 3 | provisioning の template で thing を登録し、thing の名前を受け取る | 全基板 |
| 4 | 受け取った証明書で、AWS IoT Core につなぎ直す | 全基板 |
| 5 | 1〜4 を終えた事を UART に出す | 全基板 |
| 6 | 証明書の要求、証明書、秘密鍵、所有権の token（`certificateOwnershipToken`）を UART に出さない | 全基板 |
| 7 | 1 と 4 の接続は、どちらも要求した版の TLS で張る（[共通の決まり](../architecture.md#22-機能に共通の決まり)） | 全基板 |

## 2. 流れ

1. Fleet Provisioning を有効にしたアプリを書く。このアプリは、MQTT agent と PubSub の task を起こさず、Fleet の task（`Demos/Fleet_Provisioning_With_CSR_Demo`）を起こします（[機能仕様書のアプリの図](../architecture.md#44-アプリの図)）。
2. 接続先、template の名前、claim 証明書と鍵を基板に入れる。
3. claim 証明書で接続し（決まり 1）、CSR を送って証明書を受け取り（決まり 2）、template で thing を登録して名前を受け取る（決まり 3）。
4. 受け取った証明書で接続し直し（決まり 4）、終わりを出す（決まり 5）。
5. 試験の後、CI が基板の作った thing と証明書を削除する。

| 項目 | RX72N | RX65N | RX671 |
|---|---|---|---|
| アプリ | Fleet 用に build したアプリ | 同左 | Wi-Fi と claim 証明書を build に入れたアプリ（CI の中で暗号化して受け渡す） |
| claim 証明書と設定の入れ方 | UART の CLI（`conf set`・`conf commit`）。TSIP でも包んだ鍵は送らない | UART の CLI（専用の道具 [`tools/bg96_bootloader_integration.py`](../../tools/bg96_bootloader_integration.py)） | build に入れる |
| 試験が求める handshake の行の数 | 1 以上 | 1 以上 | 2 以上（claim と受け取った証明書の 2 回の接続を想定した数。行と接続の対応は見ない） |

## 3. UART に出す行

試験の合否は、次の行で決めます（[試験仕様](../test-specification.md#fleet-provisioning)）。行の文字列を変える時は、この表と試験の道具を同じ MR で直します。

| 決まり | 行の文字列 | 出す所 |
|---|---|---|
| 1 | `Established connection with claim credentials.` | `Demos/Fleet_Provisioning_With_CSR_Demo/FleetProvisioningDemoExample.c` |
| 2 | `Received certificate with Id:` | 同上 |
| 3 | `Received AWS IoT Thing name:` | 同上 |
| 4 | `Sucessfully established connection with provisioned credentials.`（`Sucessfully` の綴りは現物のまま） | 同上 |
| 5 | `Demo completed successfully.` | 同上 |
| 7 | `TLS handshake successful: version <版>` | `transport_mbedtls_pkcs11*.c` |

起動の失敗は、`WHD startup failed`（RX671）、`Cellular init failed`・`Cellular Open Failed`（RX65N）の行で出します。

## 4. 決まりと試験の対応

| 決まり | 確かめるテスト番号 | 確かめない所 |
|---|---|---|
| 1〜5 | `IREF-FLEET-001`〜`012` | AWS 側に作られた thing と証明書の中身 |
| 6 | `IREF-FLEET-001`〜`012` | 観測の道具が知っている形（JSON の key の名前など）だけを探す |
| 7 | `IREF-FLEET-001`〜`012` | 観測したすべての handshake の行が要求した版である事と、行の数（RX72N・RX65N は 1 件以上、RX671 は 2 件以上）を見る。行を claim の接続と接続し直しに対応づける事は見ない |

## 5. 確かめていない事

- template の異常、claim 証明書の失効など、異常系の試験はありません（[試験仕様の非対象](../test-specification.md#非対象)）。
- TSIP の構成でも、Fleet Provisioning の claim 証明書の鍵と、受け取った証明書の鍵を、TSIP で包んだ鍵として扱うかは、この文書で確かめていません。CI は、Fleet の試験で包んだ鍵を送りません。

# OTA による更新の実装仕様

[[_TOC_]]

この文書は、[機能仕様書](../architecture.md#2-機能と実装仕様書)の機能「OTA による更新」の実装仕様書です。仕様書キーは `OTA` で、試験は `IREF-OTA-001`〜`IREF-OTA-012` です（[試験仕様](../test-specification.md)）。面の番地と大きさは、[資源の配分](../architecture.md#72-code-flash-の分け方)にあります。

## 1. 決まり

| 番号 | 決まり | 対象 |
|---|---|---|
| 1 | AWS IoT Jobs から、OTA の job を受け取る | 全基板 |
| 2 | MQTT でファームウェアを block ごとに受け取り、反対側の面（buffer 面）に書く | 全基板 |
| 3 | 受け取り終えたら file を閉じ、署名を確かめる | 全基板 |
| 4 | 署名が合えば、面を切り替えて再起動する | 全基板 |
| 5 | boot loader は、data flash の LittleFS にある署名者の公開鍵で、起動する image の署名（`sig-sha256-ecdsa`）を確かめ、合わない image を起動しない。組み込みの鍵へは戻らない | 全基板 |
| 6 | 新しい版で起動し、版を UART に出す | 全基板 |
| 7 | 新しい版が今の版より高い事を確かめて受け入れ、更新を確定する | 全基板 |
| 8 | どこかで失敗した時は、決まった失敗の行を出す。新しい版を確定しない | 全基板 |
| 9 | main 面にアプリが無い時、boot loader は UART でファームウェア（`userprog.rsu`）を受け取り、署名を確かめて書く | RX671 |
| 10 | 更新後のアプリは、資源の余裕（heap の最小の空き、network buffer の最小の空き、Wi-Fi の buffer の最大の使用、失敗の回数）を UART に出す | RX671 |

## 2. 流れ

1. 更新用のファームウェアを、基準より高い版で build し、署名して S3 に置き、OTA の更新（job）を作る。版は `tools/ci/tests.json` の `ota_candidate_version`。
2. 基板は、基準の版のアプリで起動し、AWS IoT Core につなぐ（[MQTT の実装仕様](mqtt.md)）。
3. OTA の demo（`CP-12`）が job を受け取る（決まり 1）。
4. MQTT のファイル転送で block を受け取り、`r_flash_rx` で buffer 面に書く（決まり 2）。
5. 最後の block のあと、file を閉じ、署名を確かめる（決まり 3。`Common/ports/ota_pal/ota_pal.c`）。
6. 面を切り替えて、software reset で再起動する（決まり 4）。
7. boot loader が署名を確かめて、新しい面のアプリを起動する（決まり 5）。
8. 新しい版のアプリが版を出し（決まり 6）、版が高い事を確かめて受け入れ、更新を確定する（決まり 7）。

| 項目 | RX72N | RX65N | RX671 |
|---|---|---|---|
| 基準の版 → 更新の版 | 0.9.2 → 0.9.3 | 0.9.4 → 0.9.99 | 0.1.0 → 0.1.1 |
| 認証情報とコード署名の証明書の入れ方 | UART の CLI。TSIP は包んだ鍵も送る | UART の CLI（専用の道具）。TSIP は包んだ鍵も送る | provisioner の CLI。署名者の公開鍵も入れる。TSIP は包んだ鍵も送る。認証情報は build に入れない |
| 最初のアプリの書き込み | 書き込み器で書く | 書き込み器で書く | boot loader が UART で受け取る（決まり 9） |
| thing | 試験ごとに作る | software は試験ごとに作る。TSIP は基板に固定の thing を元に作る | software は試験ごとに作る。TSIP は基板に固定の thing を使う |

## 3. UART に出す行

試験の合否は、次の行で決めます（[試験仕様](../test-specification.md#ota)）。行の文字列を変える時は、この表と試験の道具を同じ MR で直します。

| 決まり | 行の文字列 |
|---|---|
| 1 | `Received OTA Job.` |
| 2 | `Starting The Download.`、`Downloaded block <N> of <M>.` |
| 3 | `Close file event Received` |
| 4 | `Activate Image event Received`、`software reset...` |
| 5 | boot loader の `integrity check scheme = sig-sha256-ecdsa`、`on code flash integrity check...OK`、`jump to user program`。合わない時は `integrity check...NG`、`not found; refusing to boot.` |
| 6 | `Application version <版>` |
| 7 | `New image has higher version than current image, accepted!`、`Accepted and committed final image.`、`OTA Completed successfully!` |
| 8 | `signature verification failed`、`Failed to decode the image signature`、`Failed to parse the job document`、`Unable to create the OTA file`、`OTA job failed`、`OTA is failed`、`Rejected image.`、`Aborted image.`、`The new image cannot be booted, rollback to old image`、boot loader の `error occurred. please reset your board.` など。全部の一覧は [`tools/test_ota.py`](../../tools/test_ota.py) の `ERROR_PATTERNS` と [`tools/bg96_ota_monitor.py`](../../tools/bg96_ota_monitor.py) |
| 9 | `Loading user code signer public key from LittleFS:`、`start installing user program.`、`send "userprog.rsu" via UART.`、`completed installing firmware.`、`update LIFECYCLE_STATE` |
| 10 | `[RX671_OTA_CAPACITY] minheap=<B> minnbuf=<個> whdmax=<個> tempfail=<回> permfail=<回> waitloop=<回>` |

## 4. 決まりと試験の対応

| 決まり | 確かめるテスト番号 | 確かめない所 |
|---|---|---|
| 1 | `IREF-OTA-001`〜`012` | RX72N・RX671 は、job の行を失った時、後の行の順序で代える証明で合格する事がある（[試験仕様](../test-specification.md#ota-の判定共通)） |
| 2 | `IREF-OTA-001`〜`012` | 同上（ダウンロードの開始の行） |
| 3 | `IREF-OTA-001`〜`012` | RX72N・RX671 は、close の行を要らない証明で合格する事がある。署名が合わない image を拒む事は見ない |
| 4 | `IREF-OTA-001`〜`012` | 同上（activate の行） |
| 5 | `IREF-OTA-001`〜`012` | RX72N・RX65N は boot loader の行を見ず、新しい版で起動した事で代える。署名が合わない image を拒む事は見ない |
| 6 | `IREF-OTA-001`〜`012` | — |
| 7 | `IREF-OTA-001`〜`012` | 同じ版・古い版を拒む事は見ない |
| 8 | `IREF-OTA-001`〜`012` | 失敗の行が出ない事だけを見る。失敗を起こして行が出る事は見ない。RX65N（`005`〜`008`）では、再試行の対象の `Cellular init failed`・`Cellular Open Failed` は不合格に数えない（[O2](../test-specification.md#o2-rx65n-の-ota)） |
| 9 | `IREF-OTA-009`〜`012` | — |
| 10 | `IREF-OTA-009`〜`012` | 合否の閾値は試験仕様にある |

## 5. 確かめていない事

- 異常系（署名が合わない image、古い版、job の文書の異常）を起こして、決まり 3・5・7・8 の拒む働きを確かめる試験はありません（[試験仕様の非対象](../test-specification.md#非対象)）。
- 決まり 10 の閾値（`minheap` 16,384 B 以上など）の根拠は、この repo の文書にありません。
- RX72N・RX65N の更新後の資源の余裕は、出していません。

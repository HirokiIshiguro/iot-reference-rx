# 実機検証マトリクスと証跡

`✓`は同一構成で5回連続成功、`○`は1回以上成功、`—`は対象外または未確認を示します。
詳細な条件と変更履歴は[Changelog](../Changelog.md)、RX671のfixed-SHA監査は
[Issue #140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/140)を参照してください。

## AWS IoT Core

| 環境 | MQTT | OTA | Fleet | TLS 1.3 MQTT | TLS 1.3 OTA | TLS 1.3 Fleet |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| RX72N / software | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5951) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5959) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5953) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5961) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5955) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5956) |
| RX72N / TSIP | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5958) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5963) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5964) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6049) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6063) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6076) |
| RX65N / software | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5952) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5954) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5957) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5960) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5962) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5965) |
| RX65N / TSIP | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5966) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5967) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5969) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6049) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6063) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6076) |
| RX671 / software | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9020) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9584) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8570) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9027) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9589) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/8726) |
| RX671 / TSIP | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8619) | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/9650) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9032) | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8674) | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/9637) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/9163) |

AWS IoT CoreはSessionTicketを発行しないため、TLS 1.3 resumption / 0-RTTは
次のLANBENCH検証で扱います。

## TLS 1.3 resumption / 0-RTT

| 環境 | Resumption | 0-RTT |
|---|:-:|:-:|
| RX72N / software | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6496) | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13/-/pipelines/6496) |
| RX72N / TSIP | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6454) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6454) |
| RX65N / software | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6488) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6488) |
| RX65N / TSIP | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6489) | [✓](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/6489) |
| RX671 / software | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8525) | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls/-/pipelines/8525) |
| RX671 / TSIP | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8533) | [✓](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls/-/pipelines/8533) |

## RX671 fixed-SHA release監査

固定SHAはP38 `666d97f6`、P221 `00f43eb5`、P212 `90ea186b`、P190 `13dba7cf`です。
full Schedule #5は[#10633](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/10633)、
[#10934](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/10934)、
[#10989](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/10989)、
[#11038](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11038)、
[#11088](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11088)の5回をstrict PASSしました。
各Runは48/48 child、253/253 job、cleanup 42/42、AWS IoT/S3残留0です。
release tag pipeline [#11140](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/11140)も35/35 job successです。

## 性能値の正本

- [RX72N/Ether固定測定 `840c6451`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/readme/-/blob/840c64514f2ac55bbe4d7101596f56ae55fde833/README.md)
- [RX65N/BG96固定測定 `1b9ea826`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ck-rx65n/bg96-bench/-/blob/1b9ea82608efcd4bffcfb2991d4f507faea200fe/README.md)
- [RX671/Type 1YN固定測定 `e247d8fe`](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/readme/-/blob/e247d8fe81e89731062cbf321e5fd12668f397ae/README.md)
- [RX671 software benchmark](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/mbedtls)
- [RX671 TSIP benchmark](https://gitlab.saffti.jp/oss/experiment/embedded/mcu/renesas/rx/example/ek-rx671/benchmark/tsip_mbedtls)

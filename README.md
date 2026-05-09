# FreeRTOS LTS IoT Reference for Renesas RX

This repository is a SAFFTI-maintained fork of
[renesas/iot-reference-rx](https://github.com/renesas/iot-reference-rx) for
Renesas RX IoT reference work.

このリポジトリは [renesas/iot-reference-rx](https://github.com/renesas/iot-reference-rx)
をベースに、SAFFTIの実機CI/CD環境でRX72N Ethernet、CK-RX65N + BG96 Cellular、
TSIP連携、AWS IoT OTAを継続検証するためのフォークです。

## Latest Full Test Results / 最新のフルテスト結果

Last updated: 2026-05-09 JST. The latest scheduled hardware regression set is
all green: **4/4 scheduled pipelines passed, 61/61 jobs succeeded**.

| Scope | Pipeline | Tested commit | Result | Jobs |
|-------|----------|---------------|--------|------|
| Full software TLS regression (RX72N/Ether + RX65N/BG96 MQTT/OTA/Fleet) | [#4709](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4709) | `91f2d6b5` | success | 33/33 |
| Focused RX72N TSIP OTA/MQTT | [#4718](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4718) | `91f2d6b5` | success | 9/9 |
| Focused RX72N software TLS 1.3 MQTT | [#4717](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4717) | `91f2d6b5` | success | 5/5 |
| Focused RX65N/BG96 TSIP OTA/MQTT | [#4791](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4791) | `f06e977f` | success | 14/14 |

The release notes in [Changelog.md](Changelog.md) include the same validation
links for the next SAFFTI tag candidate. Scope details, including TLS 1.3 OTA
and TSIP Fleet Provisioning status, are tracked in [CLAUDE.md](CLAUDE.md).

## Documentation / ドキュメント

| Document | Purpose |
|----------|---------|
| [CLAUDE.md](CLAUDE.md) | Detailed project reference, maintained board matrix, build and CI/CD operation notes |
| [Changelog.md](Changelog.md) | SAFFTI release notes and validation links by release tag |
| [LICENSE](LICENSE) | License terms for this fork and bundled components |

## Maintained Targets / 保守対象

| Board | Connectivity | Main application | TSIP application | Boot loader |
|-------|--------------|------------------|------------------|-------------|
| RX72N Envision Kit | Ethernet | `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/` | `Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx/` | `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/` |
| CK-RX65N V1 | Quectel BG96 Cellular | `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/` | `Projects/aws_bg96_ck_rx65n_tsip/e2studio_ccrx/` | `Projects/boot_loader_ck_rx65n/e2studio_ccrx/` |

## Getting the Source / ソースコード取得

This repository uses Git submodules. Clone with `--recursive`:

```bash
git clone --recursive https://github.com/HirokiIshiguro/iot-reference-rx.git

# If already cloned without --recursive:
git submodule update --init --recursive
```

Build, flashing, provisioning, OTA, Fleet Provisioning, scheduled regression,
and hardware-runner details are maintained in [CLAUDE.md](CLAUDE.md).

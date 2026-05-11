# FreeRTOS LTS IoT Reference for Renesas RX

## Latest Focused Test Matrix / 最新のFocusedテスト行列

Last updated: 2026-05-11 JST. The scheduled regression unit is a single
nightly parent pipeline (`PIPELINE_PROFILE=nightly_matrix`) that fans out the
focused rows below as child pipelines. This replaces the older "Full" schedule:
the matrix table is the source of truth, and each row maps to one focused
configuration. Child pipelines are serialized per board so one RX72N row and
one RX65N/BG96 row can run in parallel without interleaving flash/provision/test
sequences on the same physical board. Rows marked `<coming soon>` are
intentionally listed but not enabled until that configuration has hardware
evidence.

| Focused row | Nightly matrix job | Latest evidence | Status |
|-------------|--------------------|-----------------|--------|
| RX72N TSIP MQTT | `matrix_rx72n_ether_tsip_mqtt` | [#4739](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4739) | OK |
| RX72N TSIP OTA | `matrix_rx72n_ether_tsip_ota` | [#4739](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4739) | OK |
| RX72N TSIP Fleet Provisioning | `matrix_rx72n_ether_tsip_fleet` | [#4905](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4905) | Stabilizing, gated by `NIGHTLY_MATRIX_INCLUDE_STABILIZING` |
| RX72N TSIP TLS 1.3 MQTT | `<coming soon>` | `<coming soon>` | `<coming soon>` |
| RX72N TSIP TLS 1.3 OTA | `<coming soon>` | `<coming soon>` | `<coming soon>` |
| RX72N TSIP TLS 1.3 Fleet Provisioning | `<coming soon>` | `<coming soon>` | `<coming soon>` |
| RX65N/BG96 TSIP MQTT | `matrix_rx65n_bg96_tsip_mqtt` | [#4744](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4744) | OK |
| RX65N/BG96 TSIP OTA | `matrix_rx65n_bg96_tsip_ota` | [#4744](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4744) | OK |
| RX65N/BG96 TSIP Fleet Provisioning | `matrix_rx65n_bg96_tsip_fleet` | [#4906](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4906) | Stabilizing, gated by `NIGHTLY_MATRIX_INCLUDE_STABILIZING` |
| RX65N/BG96 TSIP TLS 1.3 MQTT | `<coming soon>` | `<coming soon>` | `<coming soon>` |
| RX65N/BG96 TSIP TLS 1.3 OTA | `<coming soon>` | `<coming soon>` | `<coming soon>` |
| RX65N/BG96 TSIP TLS 1.3 Fleet Provisioning | `<coming soon>` | `<coming soon>` | `<coming soon>` |
| RX72N software MQTT | `matrix_rx72n_ether_software_mqtt` | [#4709](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4709) | OK |
| RX72N software OTA | `matrix_rx72n_ether_software_ota` | [#5002](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/5002) | Stabilizing, gated by `NIGHTLY_MATRIX_INCLUDE_STABILIZING` |
| RX72N software Fleet Provisioning | `matrix_rx72n_ether_software_fleet` | [#4709](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4709) | OK |
| RX72N software TLS 1.3 MQTT | `matrix_rx72n_ether_software_tls13_mqtt` | [#4717](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4717) | OK |
| RX72N software TLS 1.3 OTA | `matrix_rx72n_ether_software_tls13_ota` | [#4989](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4989) | Stabilizing, gated by `NIGHTLY_MATRIX_INCLUDE_STABILIZING` |
| RX72N software TLS 1.3 Fleet Provisioning | `matrix_rx72n_ether_software_tls13_fleet` | scheduled | Evidence pending |
| RX65N/BG96 software MQTT | `matrix_rx65n_bg96_software_mqtt` | [#4709](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4709) | OK |
| RX65N/BG96 software OTA | `matrix_rx65n_bg96_software_ota` | [#4709](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4709) | OK |
| RX65N/BG96 software Fleet Provisioning | `matrix_rx65n_bg96_software_fleet` | [#4709](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4709) | OK |
| RX65N/BG96 software TLS 1.3 MQTT | `matrix_rx65n_bg96_software_tls13_mqtt` | [#4667](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4667) | OK |
| RX65N/BG96 software TLS 1.3 OTA | `matrix_rx65n_bg96_software_tls13_ota` | scheduled | Evidence pending |
| RX65N/BG96 software TLS 1.3 Fleet Provisioning | `matrix_rx65n_bg96_software_tls13_fleet` | scheduled | Evidence pending |

## About This Fork / このフォークについて

This repository is a fork of [renesas/iot-reference-rx](https://github.com/renesas/iot-reference-rx), modified and maintained for Renesas RX IoT reference work.

The upstream repository officially supports only the CK-RX65N v2 board and does **not** include RX72N projects. This fork extends the original by:

1. **Adding RX72N Envision Kit support** — porting the FreeRTOS + AWS IoT demo (Ethernet, MQTT PubSub, OTA) to the RX72N Envision Kit, which is not covered upstream
2. **Adding CK-RX65N + BG96 cellular support** — carrying the proven OSS CK-RX65N/BG96 OTA reference into this tree as the recommended cellular modem path for this fork
3. **Improving the boot loader** — replacing the upstream's simple dual-bank boot loader with a production-grade design, with the ultimate goal of integrating [MCUboot](https://www.mcuboot.com/) as the secure boot loader
4. **CI/CD integration** — automated build, flash, provisioning, and MQTT/OTA testing via GitLab CI with hardware-in-the-loop

本リポジトリは [renesas/iot-reference-rx](https://github.com/renesas/iot-reference-rx) のフォークです。
upstream は CK-RX65N v2 のみを公式サポートしており、**RX72N には対応していません**。
本フォークでは以下の改造を行っています:

1. **RX72N Envision Kit 対応の追加** — upstream にない RX72N 向け FreeRTOS + AWS IoT デモ（Ethernet / MQTT PubSub / OTA）の移植
2. **CK-RX65N + BG96 Cellular 対応の追加** — 安定してOTA可能なOSS版CK-RX65N/BG96構成を、このフォークの推奨セルラー構成として取り込み
3. **ブートローダの本格化** — upstream の簡易デュアルバンクブートローダを本格仕様に変更。最終的には [MCUboot](https://www.mcuboot.com/) への換装を予定
4. **CI/CD 統合** — GitLab CI による自動ビルド・フラッシュ・プロビジョニング・MQTT/OTA テスト（実機接続 Runner）

### Upstream

| Role | URL |
|------|-----|
| Upstream (Renesas) | https://github.com/renesas/iot-reference-rx |
| This fork (GitLab) | https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx |
| This fork (GitHub mirror) | https://github.com/HirokiIshiguro/iot-reference-rx |

Base version: **202604.00-LTS-rx** (FreeRTOS 202604.00 LTS)

## Supported Board / 対応ボード

| Board | MCU | Core | Code Flash | RAM | Connectivity |
|-------|-----|------|------------|-----|--------------|
| **RX72N Envision Kit** | RX72N (R5F572NN) | RXv3 | 4 MB (dual-bank) | 1 MB + 512 KB | Ethernet (on-board) |
| **CK-RX65N V1 + BG96** | RX65N dual-bank | RXv2 | 2 MB (dual-bank) | 640 KB | Cellular Cat-M1/NB-IoT (Quectel BG96) |

> **Note:** The upstream RYZ014A cellular project is obsolete in practice. This fork keeps BG96 as the maintained cellular reference path.

## Projects / e2 studio プロジェクト

The following e2 studio projects are maintained under `Projects/`:

| Project | Path | Description |
|---------|------|-------------|
| Boot Loader | `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/` | RX72N dual-bank boot loader for OTA firmware update |
| AWS Ether Demo | `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/` | FreeRTOS + AWS IoT demo (MQTT PubSub, OTA) over Ethernet |
| AWS Ether Demo with TSIP | `Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx/` | RX72N Ethernet demo using the TSIP-enabled TLS backend |
| CK-RX65N BG96 Boot Loader | `Projects/boot_loader_ck_rx65n/e2studio_ccrx/` | RX65N dual-bank boot loader for BG96 OTA |
| CK-RX65N BG96 AWS Demo | `Projects/aws_bg96_ck_rx65n/e2studio_ccrx/` | FreeRTOS + AWS IoT demo (MQTT PubSub, OTA) over BG96 cellular |
| CK-RX65N BG96 AWS Demo with TSIP | `Projects/aws_bg96_ck_rx65n_tsip/e2studio_ccrx/` | BG96 cellular demo using the TSIP-enabled TLS backend; hardware validation requires RX65N-specific TSIP wrapped blobs |

### Boot Loader Architecture / ブートローダ構成

The current boot loader uses the RX dual-bank flash mechanism with r_fwup (Firmware Update module) for OTA:

- Validates new firmware image signature (ECDSA-P256)
- Performs bank swap on successful verification
- Supports rollback on signature verification failure

**Roadmap:** The current r_fwup-based boot loader will be replaced with [MCUboot](https://www.mcuboot.com/) to provide a production-grade secure boot chain with swap/revert, encrypted images, and hardware root of trust.

## Development Environment / 開発環境

### Required Tools

| Tool | Version | Notes |
|------|---------|-------|
| [e2 studio](https://www.renesas.com/software-tool/e-studio) | 2025-12 | Renesas IDE (includes Smart Configurator) |
| CC-RX Compiler | V3.07.00 | Renesas C/C++ compiler for RX family |
| [Renesas Flash Programmer](https://www.renesas.com/software-tool/renesas-flash-programmer-programming-gui) (rfp-cli) | V3.22 | CLI flash writer |
| Git | 2.x+ | With submodule support |

### Getting the Source / ソースコード取得

This repository uses Git submodules (FreeRTOS-Kernel, mbedTLS, coreMQTT, etc.). Always clone with `--recursive`:

```bash
git clone --recursive https://github.com/HirokiIshiguro/iot-reference-rx.git

# If already cloned without --recursive:
git submodule update --init --recursive
```

> **Warning:** Without initialized submodules, the build will fail with missing header errors (e.g., `FreeRTOS.h` not found).

### Build / ビルド方法

#### Using e2 studio IDE

1. Open e2 studio
2. **File > Import > General > Existing Projects into Workspace**
3. Set root directory to `Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/` or `Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/`
4. Build the project (Ctrl+B)

#### Headless Build (CLI)

```bash
# Build both boot_loader and aws_ether projects headlessly
pwsh -File tools/build_headless_rx72n.ps1 \
  -ProjectRoot <repo_root> \
  -E2Studio <path_to_e2studio.exe> \
  -Workspace <temp_workspace>
```

The script imports and builds both `boot_loader_rx72n_envision_kit` and `aws_ether_rx72n_envision_kit`, then verifies `.mot` / `.abs` / `.x` outputs.

For the CK-RX65N + BG96 cellular reference:

```bash
pwsh -File tools/build_headless_rx65n_bg96.ps1 \
  -ProjectRoot <repo_root> \
  -E2Studio C:/Renesas/e2_studio_2025_12/eclipse/e2studio-cli.exe \
  -Workspace <temp_workspace>
```

The script imports and builds both `boot_loader_ck_rx65n` and `aws_bg96_ck_rx65n`, then verifies `.mot` / `.abs` / `.x` outputs.

### Flash / 書き込み方法

Connect the RX72N Envision Kit via USB and use rfp-cli:

```bash
# Write boot_loader
rfp-cli -d RX72N -t jlink -if swd -p boot_loader_rx72n_envision_kit.mot -run -noquery

# Write application (preserving boot_loader region)
rfp-cli -d RX72N -t jlink -if swd -file aws_ether_rx72n_envision_kit.mot -auto -noerase -run -noquery
```

### Demo Configuration / デモ設定

Demo selection is controlled by macros in `src/frtos_config/demo_config.h`:

| Macro | Value | Effect |
|-------|-------|--------|
| `ENABLE_OTA_UPDATE_DEMO` | 0 | MQTT PubSub only |
| `ENABLE_OTA_UPDATE_DEMO` | 1 | MQTT PubSub + OTA |

## Software Stack / ソフトウェア構成

### Key OSS Components

| Library | Version | LTS Until |
|---------|---------|-----------|
| FreeRTOS Kernel | 11.3.0 | 2028/06/30 |
| FreeRTOS-Plus-TCP | 4.4.1 | 2028/06/30 |
| coreMQTT | 5.0.2 | 2028/06/30 |
| coreMQTT Agent | 1.3.1 + local coreMQTT v5 adapter | -- |
| corePKCS11 | 3.6.4 | 2028/06/30 |
| coreJSON | 3.3.1 | 2028/06/30 |
| AWS IoT Jobs | 2.0.1 | 2028/06/30 |
| AWS IoT MQTT File Streams | 1.2.0 | 2028/06/30 |
| mbedTLS | 3.6.4 | -- |
| littlefs | 2.5.1 | -- |
| r_fwup | 2.04 | -- |

### FIT Modules (RX Driver Package)

| FIT module | Revision | RX Driver Package |
|------------|----------|-------------------|
| r_bsp | 7.52 | 1.46 |
| r_ether_rx | 1.23 | 1.36 - 1.46 |
| r_flash_rx | 5.21 | 1.46 |
| r_sci_rx | 5.40 | 1.46 |
| r_s12ad_rx | 5.40 | 1.45 - 1.46 |
| r_byteq | 2.10 | 1.37 - 1.46 |
| r_irq_rx | 4.60 | 1.46 |
| r_fwup | 2.04 | 1.45 - 1.46 |

## CI/CD Pipeline

The GitLab CI pipeline is organized by MCU environment. Job names use
`<action>_<mcu_env>_<feature>` where possible.

| MCU environment | Hardware | Connectivity | Standard runner |
|-----------------|----------|--------------|-----------------|
| `rx72n_ether` | RX72N Envision Kit | Ethernet | RPi #2 / `dev-ek-rx72n-set2` |
| `rx65n_bg96` | CK-RX65N V1 + Quectel BG96 | Cellular Cat-M1/NB-IoT | RPi #3 / `dev-ck-rx65n-bg96` |

Core hardware jobs:

| Function | RX72N Ethernet job | RX65N/BG96 job |
|----------|--------------------|----------------|
| Build boot loader and app | `build_rx72n_ether` | `build_rx65n_bg96` |
| Flash boot loader / initial app | `flash_rx72n_ether` | `flash_rx65n_bg96` |
| Download app via boot loader | included in `flash_rx72n_ether` | `download_rx65n_bg96_app` |
| Verify app startup | included in MQTT/OTA observation | `run_rx65n_bg96_app` |
| Provision MQTT credentials | `provision_rx72n_ether_mqtt` | `provision_rx65n_bg96_mqtt` |
| Test MQTT | `test_rx72n_ether_mqtt` | `test_rx65n_bg96_mqtt` |
| Build OTA candidate | `build_rx72n_ether_ota` | `build_rx65n_bg96_ota` |
| Create AWS IoT OTA job | `create_rx72n_ether_ota` | `create_rx65n_bg96_ota` |
| Test OTA | `test_rx72n_ether_ota` | `test_rx65n_bg96_ota` |
| Build Fleet Provisioning image | `build_rx72n_ether_fleet` | `build_rx65n_bg96_fleet` |
| Test Fleet Provisioning | `test_rx72n_ether_fleet` | `test_rx65n_bg96_fleet` |

Current hardware validation matrix:

| Feature | `rx72n_ether` software TLS | `rx72n_ether` TSIP TLS | `rx65n_bg96` software TLS | `rx65n_bg96` TSIP TLS |
|---------|----------------------------|------------------------|---------------------------|-----------------------|
| Build | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4739](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4739) | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4744](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4744) |
| Flash / app boot | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4739](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4739) | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4744](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4744) |
| MQTT over TLS 1.2 | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4739](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4739) | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4744](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4744) |
| MQTT over TLS 1.3 | OK, [pipeline #4667](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4667) | Not implemented | OK, [pipeline #4667](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4667) | Not implemented |
| OTA over MQTT | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4739](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4739) | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | OK, [pipeline #4744](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4744) |
| Fleet Provisioning | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | Disabled by default | OK, [pipeline #4737](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/4737) | Disabled by default |

RX65N/BG96 TSIP hardware validation uses RX65N-specific UFPK-derived runtime
provisioning payloads and the matching static AWS IoT certificate documented in
`docs/tsip-integration-plan.md`.

### Pipeline Profiles

This project is treated as an advanced hardware CI pipeline: the full matrix spans multiple boards and configurations, so merge request pipelines run representative hardware paths and scheduled pipelines run the heavier regression set.

| Profile | Pipeline source | Default scope |
|---------|-----------------|---------------|
| `branch` | Feature branch push | Build only. Hardware jobs are kept out of push pipelines to avoid interleaving board state with MR pipelines. |
| `mr` | Merge request | `RX72N_TEST_SCOPE=mqtt`, `RX65N_BG96_TEST_SCOPE=mqtt`. This covers both transports while keeping review feedback short; OTA coverage is delegated to the focused matrix. |
| `focused` | Manual/API | Build only unless the caller sets `RX72N_TEST_SCOPE`, `RX65N_BG96_TEST_SCOPE`, `RX72N_TLS_BACKEND`, `RX65N_BG96_TLS_BACKEND`, or TLS version variables explicitly. |
| `main` | Default branch push | Same representative scope as `mr`; full matrix coverage is delegated to the schedule. |
| `release` | Tag | Full software-TLS regression for RX72N and RX65N/BG96. |
| `nightly_matrix` | GitLab pipeline schedule | Parent pipeline that fans out the focused matrix rows. Stabilizing rows run only when `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true`. |

Focused examples:

```bash
# RX72N TSIP OTA only
PIPELINE_PROFILE=focused RX72N_TEST_SCOPE=ota RX65N_BG96_TEST_SCOPE=build RX72N_TLS_BACKEND=tsip

# RX65N/BG96 TSIP OTA only
PIPELINE_PROFILE=focused RX65N_BG96_TEST_SCOPE=ota RUN_RX72N_BUILD=false RX72N_SKIP_HW_TESTS=true RX65N_BG96_TLS_BACKEND=tsip

# Manual/API software TLS 1.3 MQTT on both boards
PIPELINE_PROFILE=focused RX72N_TEST_SCOPE=mqtt RX65N_BG96_TEST_SCOPE=mqtt AWS_IOT_ENDPOINT=d095604912rj95htx1mal-ats.iot.ap-northeast-1.amazonaws.com RX72N_REQUIRE_TLS_VERSION=TLSv1.3 RX65N_BG96_REQUIRE_TLS_VERSION=TLSv1.3
```

### Scheduled Hardware Regressions

The project-level GitLab pipeline schedule is part of the reference pipeline design. Keep the merge request pipeline short, and move matrix coverage that is useful but not review-blocking into the nightly matrix schedule. The active schedule is a single parent pipeline; child pipelines are serialized per board by matrix resource groups, so RX72N and RX65N/BG96 rows can run in parallel without interleaving state on the same physical board.

| Schedule | Status | Time (JST) | Scope | Purpose |
|----------|--------|------------|-------|---------|
| Nightly focused test matrix (schedule #5) | Active | 02:20 daily | `PIPELINE_PROFILE=nightly_matrix`, `NIGHTLY_MATRIX_INCLUDE_STABILIZING=false` | Runs the stable focused rows listed in the matrix above. TSIP Fleet and RX72N software OTA/TLS 1.3 OTA are gated as stabilizing rows until repeated schedule evidence is available. |

Creating or updating project pipeline schedules requires Maintainer/Owner permissions on this GitLab project. Keep the active GitLab schedules and this table in sync so the scheduled regression set remains reviewable in Git.

## Limitations

<details>
<summary>Click to expand</summary>

- CLI task cannot run after starting the demo (SCI conflict)
- `mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST` must be set to `1` for OTA
- LittleFS is not thread-safe; do not call its API from multiple tasks
- Custom `printf` is not thread-safe; use `configPRINTF` instead
- After Smart Configurator code generation, verify linker section addresses for dual-bank configuration
- For RX72N, LittleFS is shifted to `0x00100800` to avoid overlap with the boot loader signer-key storage

</details>

## FreeRTOS-Kernel Patch / FreeRTOS カーネルパッチ

This fork uses the upstream FreeRTOS-Kernel submodule and applies the RX72N CCRX context-restore workaround from `Common/patches/FreeRTOS-Kernel/portable/Renesas/RX700v3_DPFPU/port.c` in the e2 studio project.

本フォークでは FreeRTOS-Kernel サブモジュールは upstream 公式を参照し、RX72N/CCRX 固有のコンテキスト復帰対策だけを `Common/patches/FreeRTOS-Kernel/portable/Renesas/RX700v3_DPFPU/port.c` から e2 studio プロジェクトに組み込んでいます。

- Issue: https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/13
- Patch: https://gitlab.saffti.jp/oss/import/github/freertos/FreeRTOS-Kernel/-/merge_requests/1

## License

- Source code in `Projects/`, `Common/`, `Middleware/AWS/`, and `Middleware/FreeRTOS/` is available under the MIT License. See [LICENSE](LICENSE).
- Other libraries in `Middleware/` are available under terms specified in each source file.
- Renesas FIT Modules in `Projects/xxx/xxx/src/smc_gen/` are available under the BSD 3-Clause License. See [rx-driver-package](https://github.com/renesas/rx-driver-package) for details.

# Development Notes

## Hardware CI scheduler policy

`iot-reference-rx` treats merge request pipelines and nightly pipelines as
different tools. Merge request pipelines should stay short enough for review,
while the nightly scheduler owns the full hardware regression surface.

Use the following rules when adding or promoting hardware test patterns:

- A result-table cell promoted to `✓` must have one scheduled execution per
  night, unless the table explicitly documents that the cell is external and
  names its companion schedule or downstream bridge.
- Stabilizing rows may start as manual/API `focused` runs while evidence is
  being collected. After a cell is promoted to `✓`, keep it in the active
  nightly schedule instead of leaving it manual-only.
- If the implementation or test harness lives in another GitLab project, prefer
  a downstream bridge from the owning nightly parent pipeline. Use a separate
  companion schedule only when a bridge cannot safely share credentials,
  artifacts, or hardware serialization.
- Keep resource serialization visible in CI. For child pipelines, put the bridge
  job in a board-specific `resource_group` so the parent does not start another
  pattern against the same physical board while the downstream run is active.
- Keep README schedule tables in sync with GitLab schedule variables. The table
  should name the schedule, cron time, important variables, and any external
  downstream project that contributes coverage.

## Current iot-reference-rx nightly map

The active project schedule is GitLab pipeline schedule #5, `Nightly focused
test matrix`, on `main` at 02:20 JST.

Required schedule variables:

```text
PIPELINE_PROFILE=nightly_matrix
NIGHTLY_MATRIX_INCLUDE_STABILIZING=true
```

The parent pipeline fans out `matrix_*` jobs in `.gitlab-ci.yml`. Rows that
extend `.nightly_matrix_rx72n`, `.nightly_matrix_rx65n_bg96`,
`.nightly_matrix_rx72n_stabilizing`, or
`.nightly_matrix_rx65n_bg96_stabilizing` represent the `iot-reference-rx`
hardware patterns. With `NIGHTLY_MATRIX_INCLUDE_STABILIZING=true`, the active
schedule runs both promoted baseline rows and formerly stabilizing rows once per
night.

RX72N/Ether software LANBENCH TLS 1.3 resumption / 0-RTT is built and tested in
the benchmark project
`oss/experiment/embedded/mcu/renesas/rx/example/rx72n_envision_kit/benchmark/tsip_mbedtls13`.
The `iot-reference-rx` nightly parent covers that table cell through the
`matrix_rx72n_ether_software_tls13_resumption_0rtt` downstream bridge. That
bridge pins the validated benchmark variables:

```text
MBEDTLS_BUILD_VARIANT=software-0rtt
RUN_HW_TESTS=true
RUN_LAN_BENCH=true
RUN_LANBENCHD_FROM_TREE=false
RUN_LANBENCH_MBEDTLS_0RTT_SERVER=true
RUN_LANBENCH_TLS13_0RTT_HOST=false
RUN_LANBENCH_TLS13_RESUMPTION_HOST=false
RUN_MQTT_SMOKE=false
RUN_S3_BENCH=false
```

## Multi-project integration-test repositories

Use a dedicated `integration-test` repository when a project group must combine
two or more independently generated projects, such as 「MCUBoot + アプリ」 or
「TrustZone（セキュア）+ TrustZone（ノンセキュア）」. A single component repository
should not own cross-project layout, signing, secure/non-secure boundary, or
hardware download policy by itself.

For these project groups, prefer this configuration-management shape:

- Keep each buildable component in its own sibling repository. For example,
  keep the bootloader, application, secure image, and non-secure image as
  separate projects when e2 studio/FSP generates and builds them separately.
- Pin component repositories from the `integration-test` repository with
  submodules under `deps/`. The submodule SHA is the source of truth for the
  exact combination under test.
- Put cross-project contracts in the `integration-test` repository or in the
  component repository that naturally owns the contract, then copy the contract
  into CI artifacts. Examples include MCUboot slot layout JSON, memory-region
  constraints, signing-key selection for test images, TrustZone SAU/IDAU
  boundaries, NSC header/import-library handoff, and flash download addresses.
- Build, sign, combine, and package in the `integration-test` pipeline. Component
  repositories may prove that each project builds alone, but the
  `integration-test` pipeline proves that the pinned set is coherent.
- Update from leaf to root. First merge component changes in `app`, `mcuboot`,
  `secure`, or `non-secure`; then update the submodule pins and contract checks
  in `integration-test`.
- Gate hardware download or execution jobs with explicit variables and
  board/probe-specific `resource_group` names. Require a debugger serial number
  when multiple probes can be attached to the same host.
- Publish machine-readable and human-readable evidence together, such as JUnit
  XML plus a QC evidence Markdown file listing submodule pins, produced images,
  slot addresses, and hardware download inputs.
- Keep internal runner names, credentials, cloud resource names, and customer or
  company-specific project paths out of OSS repositories. Store secrets only in
  GitLab CI/CD variables and document public variable names instead of values.

## Applying the same pattern elsewhere

For other hardware CI projects, prefer this shape:

- Define a `nightly_matrix` or equivalent profile that only schedule/API/web
  pipelines can use.
- Express each result-table cell as a named matrix job or downstream bridge.
- Keep MR/default-branch pipelines representative, and move long-running
  coverage into the nightly parent.
- Gate pre-promotion patterns with an explicit variable such as
  `NIGHTLY_MATRIX_INCLUDE_STABILIZING`; set that variable to `true` once the
  table marks the cell as `✓`.
- Document external projects in the parent README, not only in the external
  project, so a maintainer can answer "does one nightly run cover the table?"
  from the table owner repository.

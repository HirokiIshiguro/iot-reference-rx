# Isolated historical producer. Candidate only: release its CI hard stop after review.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$oldSource = '666d97f64eecc2451ec3b54ee101b5b53a603c51'
foreach ($id in @($env:CI_PIPELINE_ID, $env:CI_JOB_ID)) {
    if ($id -notmatch '^[1-9][0-9]*$') { throw 'Invalid producer CI identity.' }
}
if ($env:RUN_RX671_KNOWN_GOOD_CONTROL -cne 'true' -or $env:PIPELINE_PROFILE -cne 'focused' -or
    $env:CI_PIPELINE_SOURCE -notin @('api', 'web') -or $env:RX671_WIFI_TEST_SCOPE -cne 'network' -or
    $env:RX671_WIFI_SKIP_HW_TESTS -cne 'true') { throw 'Producer requires the reviewed control-only CI profile.' }
foreach ($name in @('RX671_EK_WIFI_SSID', 'RX671_EK_WIFI_PASSPHRASE',
    'RX671_EK_AWS_IOT_THING_NAME', 'RX671_EK_AWS_IOT_CERT_PEM', 'RX671_EK_AWS_IOT_PRIVATE_KEY_PEM')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Required normal MQTT CI variable is missing: $name"
    }
}
if ([string]::IsNullOrWhiteSpace($env:RX671_EK_AWS_IOT_ENDPOINT) -and
    [string]::IsNullOrWhiteSpace($env:AWS_IOT_ENDPOINT)) { throw 'Missing normal MQTT CI endpoint.' }
# Select the old helper's original normal defaults in this producer process.
# These names are nonsecret build knobs; credentials are left to its normal path.
foreach ($suffix in @('TCP_THROUGHPUT_ENABLE','TCP_THROUGHPUT_HOST','TCP_THROUGHPUT_PORT',
    'TCP_THROUGHPUT_MODE','TCP_THROUGHPUT_BYTES','TCP_THROUGHPUT_CHUNK_BYTES',
    'TCP_THROUGHPUT_TX_CHUNK_BYTES','TCP_THROUGHPUT_RX_CHUNK_BYTES','TCP_THROUGHPUT_ITERATIONS',
    'TCP_THROUGHPUT_TX_BUFFER_BYTES','TCP_THROUGHPUT_RX_BUFFER_BYTES',
    'TCP_THROUGHPUT_TX_WINDOW_MSS','TCP_THROUGHPUT_RX_WINDOW_MSS','TCP_THROUGHPUT_PROGRESS_BYTES',
    'SDIO_RUN_CLOCK_DIV','SDIO_USE_HIGH_SPEED_CLOCK','SDIO_HIGH_SPEED_DRIVE','SDIO_CMD53_XFER_ENGINE',
    'SDIO_CMD53_DTC_READ_ENABLE','SDIO_CMD53_DTC_WRITE_ENABLE','SDIO_CMD53_DTC_MIN_BYTES',
    'SDIO_CMD53_DMACA_READ_ENABLE','SDIO_CMD53_DMACA_WRITE_ENABLE','SDIO_CMD53_DMACA_MIN_BYTES',
    'SDIO_CMD53_DMACA_BLOCK_MODE','WLAN_DISABLE_POWERSAVE')) {
    [Environment]::SetEnvironmentVariable("RX671_EK_$suffix", $null, 'Process')
}
if ($env:RX671_WIFI_F2_FAULT_INJECT_ONCE -eq 'true' -or
    -not [string]::IsNullOrWhiteSpace($env:RX671_WIFI_REQUIRE_TLS_VERSION)) {
    throw 'Historical producer rejects ambient performance/fault/TLS overrides.'
}
if ($env:RX671_WIFI_WLAN_ALLOW_BUS_SLEEP_DELAY_MS -cne '600000') {
    throw 'Historical producer requires the original normal WLAN sleep delay.'
}
$source = [IO.Path]::GetFullPath($env:CI_PROJECT_DIR)
$privateRoot = "C:/ai/codex/tmp/kg-rx671-$env:CI_PIPELINE_ID-$env:CI_JOB_ID"
$oldRoot = Join-Path $privateRoot 'old'
$workspace = "C:/ai/codex/ws/kg-rx671-$env:CI_PIPELINE_ID-$env:CI_JOB_ID"
$artifact = Join-Path $source 'artifacts/kg_old_rx671'
if ((Test-Path -LiteralPath $privateRoot) -or (Test-Path -LiteralPath $workspace) -or
    (Test-Path -LiteralPath $artifact)) { throw 'Producer-owned output already exists.' }
# Validate the absolute owned roots before the original helper can remove a
# build/workspace directory. This script never removes another checkout.
if (-not ([IO.Path]::GetFullPath($privateRoot)).StartsWith('C:\ai\codex\tmp\kg-rx671-', [StringComparison]::OrdinalIgnoreCase) -or
    -not ([IO.Path]::GetFullPath($workspace)).StartsWith('C:\ai\codex\ws\kg-rx671-', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Producer output escaped its dedicated roots.'
}
New-Item -ItemType Directory -Path $privateRoot | Out-Null
$proofHelper = Join-Path $source 'tools/ci/rx671_known_good_producer.py'
try {
    # Existing GitLab Runner origin authentication and URL rewriting are
    # inherited. No credentials, remote URLs, or configuration files are read.
    & git -C $source fetch --no-tags origin $oldSource *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Historical source fetch failed.' }
    & git -C $source worktree add --detach $oldRoot $oldSource *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Historical worktree creation failed.' }
    & git -C $oldRoot submodule update --init --recursive --jobs 4 *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Historical pinned submodule initialization failed.' }
    & python $proofHelper pre --source $oldRoot --output (Join-Path $privateRoot 'public-prebuild-proof.json')
    if ($LASTEXITCODE -ne 0) { throw 'Historical source preflight failed.' }
    $buildArgs = @{
        ProjectRoot = $oldRoot
        E2Studio = $env:E2STUDIO_CLI
        Workspace = $workspace
        LogFile = (Join-Path $privateRoot 'build-private.log')
        UseLocalJoinConfig = $true
        UseAwsIotLocalConfig = $true
        WlanAllowBusSleepDelayMs = 600000
    }
    # The exact old helper and its original 180-second default run unchanged.
    # Every stream stays in normal CI-private staging, outside artifact paths.
    & (Join-Path $oldRoot 'tools/build_headless_rx671_wifi.ps1') @buildArgs *> (Join-Path $privateRoot 'console-private.log')
    if ($LASTEXITCODE -ne 0) { throw 'Historical normal MQTT native build failed.' }
    & python $proofHelper post --source $oldRoot --output (Join-Path $privateRoot 'control_manifest.json')
    if ($LASTEXITCODE -ne 0) { throw 'Historical post-build provenance/profile validation failed.' }
    foreach ($relative in @('src/whd_join_config_local.h', 'src/frtos_config/aws_iot_config_local.h',
        'src/frtos_config/rx671_fleet_config_local.h', 'src/frtos_config/tcp_throughput_config_local.h')) {
        if (Test-Path -LiteralPath (Join-Path $oldRoot "Projects/aws_wifi_rx671_ek/e2studio_ccrx/$relative")) {
            throw 'A generated private header was retained after the build.'
        }
    }
    New-Item -ItemType Directory -Force -Path $artifact | Out-Null
    Copy-Item -LiteralPath (Join-Path $oldRoot 'Projects/aws_wifi_rx671_ek/e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.mot') -Destination (Join-Path $artifact 'aws_wifi_rx671_ek.mot')
    Copy-Item -LiteralPath (Join-Path $privateRoot 'control_manifest.json') -Destination (Join-Path $artifact 'control_manifest.json')
    Write-Host 'Historical normal MQTT producer completed; public provenance and restricted MOT retained.'
} catch {
    # No original exception or native output is copied into the job trace.
    throw 'Historical producer failed; private build diagnostics retained in its dedicated CI staging.'
}

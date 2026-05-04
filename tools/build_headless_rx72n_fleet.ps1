param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx72n-fleet-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx72n_e2studio_build_fleet.log"),
    [string]$FleetDemoId = "rx72n-02-fp",
    [int]$E2StudioTimeoutSeconds = 600,
    [string]$TlsBackend = $(if ($env:RX72N_TLS_BACKEND) { $env:RX72N_TLS_BACKEND } else { "software" })
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
$normalizedTlsBackend = $TlsBackend.ToLowerInvariant()
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_ether_rx72n_envision_kit" }
    "tsip" { $appProjectName = "aws_ether_rx72n_envision_kit_tsip" }
    default { throw "Unsupported RX72N TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$demoConfig = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx\src\frtos_config\demo_config.h"
$buildScript = Join-Path $projectRoot "tools\build_headless_rx72n.ps1"

if (-not (Test-Path $demoConfig)) {
    throw "demo_config.h not found: $demoConfig"
}
if (-not (Test-Path $buildScript)) {
    throw "build script not found: $buildScript"
}

$originalDemoConfig = [System.IO.File]::ReadAllText($demoConfig)

try {
    $updated = $originalDemoConfig
    $updated = $updated -replace '#define\s+ENABLE_FLEET_PROVISIONING_DEMO\s+\([01]\)', '#define ENABLE_FLEET_PROVISIONING_DEMO      (1)'
    $updated = $updated -replace '#define\s+ENABLE_OTA_UPDATE_DEMO\s+\([01]\)', '#define ENABLE_OTA_UPDATE_DEMO              (0)'
    $updated = $updated -replace '#define\s+democonfigFP_DEMO_ID\s+"[^"]+"', ('#define democonfigFP_DEMO_ID    "' + $FleetDemoId + '"')
    $updated = $updated -replace '#define\s+MQTT_AGENT_NETWORK_BUFFER_SIZE\s+\(\s*\d+\s*\)', '#define MQTT_AGENT_NETWORK_BUFFER_SIZE          ( 10000 )'

    [System.IO.File]::WriteAllText(
        $demoConfig,
        $updated,
        [System.Text.UTF8Encoding]::new($false)
    )

    & $buildScript `
        -ProjectRoot $projectRoot `
        -E2Studio $E2Studio `
        -Workspace $Workspace `
        -LogFile $LogFile `
        -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds `
        -TlsBackend $normalizedTlsBackend
}
finally {
    [System.IO.File]::WriteAllText(
        $demoConfig,
        $originalDemoConfig,
        [System.Text.UTF8Encoding]::new($false)
    )
}

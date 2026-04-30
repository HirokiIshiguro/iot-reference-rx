param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\iotref-rx65n-bg96-fleet-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx65n_bg96_e2studio_build_fleet.log"),
    [string]$FleetDemoId = "rx65n-bg96-fp",
    [int]$E2StudioTimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
$demoConfig = Join-Path $projectRoot "Projects\aws_bg96_ck_rx65n\e2studio_ccrx\src\frtos_config\demo_config.h"
$buildScript = Join-Path $projectRoot "tools\build_headless_rx65n_bg96.ps1"

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
    $updated = $updated -replace '#if\s+\(ENABLE_FLEET_PROVISIONING_DEMO\s+==\s+1\)\s*\r?\n\s*#error\s+"Fleet Provisioning demo is not supported!"\s*\r?\n\s*#endif', ''
    $updated = $updated -replace '#define\s+democonfigFP_DEMO_ID\s+"[^"]+"', ('#define democonfigFP_DEMO_ID    "' + $FleetDemoId + '"')

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
        -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds
}
finally {
    [System.IO.File]::WriteAllText(
        $demoConfig,
        $originalDemoConfig,
        [System.Text.UTF8Encoding]::new($false)
    )
}

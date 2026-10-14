param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\ai\codex\ws\iotref-rx65n-bg96-fleet-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx65n_bg96_e2studio_build_fleet.log"),
    [string]$FleetDemoId = "rx65n-bg96-fp",
    [int]$E2StudioTimeoutSeconds = 600,
    [string]$TlsBackend = $(if ($env:RX65N_BG96_TLS_BACKEND) { $env:RX65N_BG96_TLS_BACKEND } else { "software" }),
    [string]$RequireTlsVersion = $(if ($env:RX65N_BG96_REQUIRE_TLS_VERSION) { $env:RX65N_BG96_REQUIRE_TLS_VERSION } else { "" })
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "rx_e2studio_cli.ps1")
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
Initialize-RxBuildDependencies -ProjectRoot $projectRoot
Assert-RxCommonKernel -ProjectRoot $projectRoot
$normalizedTlsBackend = $TlsBackend.ToLowerInvariant()
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_bg96_ck_rx65n" }
    "tsip" { $appProjectName = "aws_bg96_ck_rx65n_tsip" }
    default { throw "Unsupported RX65N BG96 TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$demoConfig = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx\src\frtos_config\demo_config.h"
$buildScript = Join-Path $projectRoot "tools\build_headless_rx65n_bg96.ps1"
$projectDescriptor = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx\.project"

function Enable-FleetProjectSources {
    param([Parameter(Mandatory = $true)][string]$ProjectDescriptor)

    $metadata = [Xml.XmlDocument]::new()
    $metadata.PreserveWhitespace = $true
    $metadata.Load($ProjectDescriptor)
    if (-not $metadata.SelectSingleNode("/projectDescription/linkedResources/link[name='Demos']")) {
        throw 'The RX65N Fleet project must use the shared Demos link.'
    }
    # The normal project includes only the PKCS11 helper in this folder. Expose
    # the actual Fleet sources through Eclipse metadata for this temporary
    # profile, so the standard generator owns compiler and linker inputs.
    foreach ($filter in @($metadata.SelectNodes("/projectDescription/filteredResources/filter[name='Demos/Fleet_Provisioning_With_CSR_Demo']"))) {
        [void]$filter.ParentNode.RemoveChild($filter)
    }
    $metadata.Save($ProjectDescriptor)
}

foreach ($path in @($demoConfig, $projectDescriptor, $buildScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "RX65N Fleet build input not found: $path"
    }
}

$snapshots = @{}
foreach ($path in @($demoConfig, $projectDescriptor)) {
    $snapshots[$path] = [IO.File]::ReadAllBytes($path)
}
try {
    $updated = [Text.Encoding]::UTF8.GetString($snapshots[$demoConfig])
    $updated = $updated -replace '#define\s+ENABLE_FLEET_PROVISIONING_DEMO\s+\([01]\)', '#define ENABLE_FLEET_PROVISIONING_DEMO      (1)'
    $updated = $updated -replace '#define\s+ENABLE_OTA_UPDATE_DEMO\s+\([01]\)', '#define ENABLE_OTA_UPDATE_DEMO              (0)'
    $updated = $updated -replace '#if\s+\(ENABLE_FLEET_PROVISIONING_DEMO\s+==\s+1\)\s*\r?\n\s*#error\s+"Fleet Provisioning demo is not supported!"\s*\r?\n\s*#endif', ''
    $updated = $updated -replace '#define\s+democonfigFP_DEMO_ID\s+"[^"]+"', ('#define democonfigFP_DEMO_ID    "' + $FleetDemoId + '"')
    [IO.File]::WriteAllText($demoConfig, $updated, [Text.UTF8Encoding]::new($false))
    Enable-FleetProjectSources -ProjectDescriptor $projectDescriptor

    & $buildScript `
        -ProjectRoot $projectRoot `
        -E2Studio $E2Studio `
        -Workspace $Workspace `
        -LogFile $LogFile `
        -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds `
        -TlsBackend $normalizedTlsBackend `
        -RequireTlsVersion $RequireTlsVersion
}
finally {
    foreach ($path in $snapshots.Keys) {
        [IO.File]::WriteAllBytes($path, $snapshots[$path])
    }
}

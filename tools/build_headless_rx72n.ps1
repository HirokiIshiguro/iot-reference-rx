param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\ai\codex\ws\iotref-rx72n-ws",
    [string]$ProjectsPath = "Projects",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx72n_e2studio_build.log"),
    [int]$E2StudioTimeoutSeconds = 600,
    [string]$TlsBackend = $(if ($env:RX72N_TLS_BACKEND) { $env:RX72N_TLS_BACKEND } else { "software" }),
    [string]$RequireTlsVersion = $(if ($env:RX72N_REQUIRE_TLS_VERSION) { $env:RX72N_REQUIRE_TLS_VERSION } else { "" }),
    [switch]$Tls13ZeroRtt
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "rx_e2studio_cli.ps1")
Set-StrictMode -Version Latest

if (-not (Test-Path $E2Studio)) {
    throw "e2studio executable not found: $E2Studio"
}

$projectRoot = (Resolve-Path $ProjectRoot).Path
Initialize-RxBuildDependencies -ProjectRoot $projectRoot
Assert-RxCommonKernel -ProjectRoot $projectRoot
$workspace = $Workspace
$projectsPath = $ProjectsPath -replace "/", "\"
$logFile = [System.IO.Path]::GetFullPath($LogFile)
$normalizedTlsBackend = $TlsBackend.ToLowerInvariant()
$normalizedRequireTlsVersion = $RequireTlsVersion.ToLowerInvariant()
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_ether_rx72n_envision_kit" }
    "tsip" { $appProjectName = "aws_ether_rx72n_envision_kit_tsip" }
    default { throw "Unsupported RX72N TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$useTsipTls13Config = ($normalizedTlsBackend -eq "tsip") -and ($normalizedRequireTlsVersion -in @("tlsv1.3", "tls1.3", "tls13"))
$useTsipTls13ZeroRttConfig = $Tls13ZeroRtt.IsPresent
if ($useTsipTls13ZeroRttConfig -and (-not $useTsipTls13Config)) {
    throw "RX72N TLS 1.3 0-RTT smoke requires -TlsBackend tsip and -RequireTlsVersion TLSv1.3."
}
$projectNames = @(
    "boot_loader_rx72n_envision_kit",
    $appProjectName
)
$metadataSnapshots = @{}

if (-not (Test-Path (Join-Path $projectRoot "Middleware\FreeRTOS\FreeRTOS-Kernel\include\FreeRTOS.h"))) {
    throw "Git submodules not initialized."
}

if (-not (Test-Path (Join-Path $projectRoot "Middleware\FreeRTOS\corePKCS11\source\dependency\3rdparty\pkcs11\published\2-40-errata-1\pkcs11.h"))) {
    throw "Git submodules not initialized recursively. Missing corePKCS11 pkcs11.h."
}

Remove-RxE2Workspace -Path $workspace

foreach ($projectName in $projectNames) {
    $hardwareDebug = Join-Path $projectRoot "$projectsPath\$projectName\e2studio_ccrx\HardwareDebug"
    if (Test-Path $hardwareDebug) {
        Remove-RxProjectBuildDirectory -ProjectPath (Split-Path -Parent $hardwareDebug)
        Write-Host "Cleared: $hardwareDebug"
    }

    $projectDir = Join-Path $projectRoot "$projectsPath\$projectName\e2studio_ccrx"
    $preferredRcpc = Join-Path $projectDir "$projectName.rcpc"
    if (Test-Path $preferredRcpc) {
        $rcpcPath = Get-Item $preferredRcpc
    } else {
        $rcpcPath = Get-ChildItem -Path $projectDir -Filter '*.rcpc' -File -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($rcpcPath) {
        $metadataSnapshots[$rcpcPath.FullName] = [System.IO.File]::ReadAllBytes($rcpcPath.FullName)
    }

    $cprojectPath = Join-Path $projectDir ".cproject"
    if (Test-Path -LiteralPath $cprojectPath) {
        $metadataSnapshots[$cprojectPath] = [System.IO.File]::ReadAllBytes($cprojectPath)
    }

    $projectFilePath = Join-Path $projectDir ".project"
    if (Test-Path -LiteralPath $projectFilePath) {
        $metadataSnapshots[$projectFilePath] = [System.IO.File]::ReadAllBytes($projectFilePath)
    }
}

Write-Host "=== RX72N import + build all ==="
Write-Host "Workspace: $workspace"
Write-Host "Log file:  $logFile"
Write-Host "TLS backend: $normalizedTlsBackend"
Write-Host "Require TLS version: $(if ($RequireTlsVersion) { $RequireTlsVersion } else { '<none>' })"
Write-Host "TSIP TLS 1.3 config: $useTsipTls13Config"
Write-Host "TSIP TLS 1.3 0-RTT config: $useTsipTls13ZeroRttConfig"
foreach ($projectName in $projectNames) {
    Write-Host "Import:    $(Join-Path $projectRoot "$projectsPath\$projectName\e2studio_ccrx")"
}

function Use-MbedTlsConfigFile {
    param(
        [string]$ProjectDir,
        [string]$ConfigFile
    )

    $cproject = Join-Path $ProjectDir ".cproject"
    if (-not (Test-Path -LiteralPath $cproject)) {
        throw ".cproject not found: $cproject"
    }

    $from = 'MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip.h&quot;&gt;'
    $to = "MBEDTLS_CONFIG_FILE=&lt;&quot;$ConfigFile&quot;&gt;"
    $content = [System.IO.File]::ReadAllText($cproject)
    if (-not $content.Contains($from)) {
        throw "TSIP mbed TLS config macro not found in $cproject"
    }
    [System.IO.File]::WriteAllText(
        $cproject,
        $content.Replace($from, $to),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Selected mbed TLS config for ${ProjectDir}: $ConfigFile"
}

function Find-Artifacts {
    param(
        [string]$RelativePattern
    )

    $primary = Join-Path $projectRoot $RelativePattern
    $items = Get-ChildItem $primary -ErrorAction SilentlyContinue
    if ($items) {
        return $items
    }
}


try {
    Remove-Item -Force -LiteralPath $logFile -ErrorAction SilentlyContinue
    if ($useTsipTls13ZeroRttConfig) {
        & (Join-Path $projectRoot "tools\prepare_mbedtls364_tsip_0rtt_build.ps1") `
            -ProjectRoot $projectRoot `
            -ProjectName $appProjectName
    }
    elseif ($useTsipTls13Config) {
        Use-MbedTlsConfigFile `
            -ProjectDir (Join-Path $projectRoot "$projectsPath\$appProjectName\e2studio_ccrx") `
            -ConfigFile "aws_mbedtls_config_with_tsip13.h"
    }

    $projectDirs = @($projectNames | ForEach-Object { Join-Path $projectRoot "$projectsPath\$_\e2studio_ccrx" })
    $buildTargets = @($projectNames | ForEach-Object { "$_/HardwareDebug" })
    $expectedOutputs = @(
        (Join-Path $projectDirs[0] 'HardwareDebug/boot_loader_rx72n_envision_kit.mot'),
        (Join-Path $projectDirs[1] "HardwareDebug/$appProjectName.mot"),
        (Join-Path $projectDirs[1] "HardwareDebug/$appProjectName.abs"),
        (Join-Path $projectDirs[1] "HardwareDebug/$appProjectName.x"),
        (Join-Path $projectDirs[1] "HardwareDebug/$appProjectName.map")
    )
    $e2exit = Invoke-RxE2StudioBuild -Executable $E2Studio -WorkspacePath $workspace `
        -ProjectPaths $projectDirs -BuildTargets $buildTargets -OutputLog $logFile `
        -TimeoutSeconds $E2StudioTimeoutSeconds -ExpectedOutputs $expectedOutputs

    Write-Host "e2studio exit code: $e2exit"
    $logLines = Get-Content $logFile -ErrorAction SilentlyContinue
    $logLineCount = if ($logLines) { $logLines.Count } else { 0 }
    Write-Host "Build log: $logLineCount lines"

    # Compiler/CLI diagnostics remain in the build log; credential-bearing
    # source lines must not be copied into the host console.

    $bootMot = Find-Artifacts "$projectsPath\boot_loader_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\*.mot"
    $appMot = Find-Artifacts "$projectsPath\$appProjectName\e2studio_ccrx\HardwareDebug\*.mot"
    $appAbs = Find-Artifacts "$projectsPath\$appProjectName\e2studio_ccrx\HardwareDebug\*.abs"
    $appX = Find-Artifacts "$projectsPath\$appProjectName\e2studio_ccrx\HardwareDebug\*.x"

    Write-Host ""
    Write-Host "--- RX72N artifact search ---"
    Write-Host "  boot_loader .mot: $(if ($bootMot) { $bootMot.FullName } else { 'NOT FOUND' })"
    Write-Host "  $appProjectName .mot: $(if ($appMot) { $appMot.FullName } else { 'NOT FOUND' })"
    Write-Host "  $appProjectName .abs: $(if ($appAbs) { $appAbs.FullName } else { 'NOT FOUND' })"
    Write-Host "  $appProjectName   .x: $(if ($appX) { $appX.FullName } else { 'NOT FOUND' })"

    $missing = @()
    if (-not $bootMot) { $missing += "boot_loader_rx72n_envision_kit .mot" }
    if (-not $appMot) { $missing += "$appProjectName .mot" }
    if (-not $appAbs) { $missing += "$appProjectName .abs" }
    if (-not $appX) { $missing += "$appProjectName .x" }

    if ($e2exit -ne 0) {
        throw "e2studio failed with exit code $e2exit. See $logFile"
    }

    if ($missing.Count -gt 0) {
        throw "RX72N build artifacts missing: $($missing -join ', ')"
    }

    Write-Host ""
    Write-Host "RX72N headless build succeeded."
}
finally {
    foreach ($metadataPath in $metadataSnapshots.Keys) {
        [System.IO.File]::WriteAllBytes($metadataPath, $metadataSnapshots[$metadataPath])
    }
}

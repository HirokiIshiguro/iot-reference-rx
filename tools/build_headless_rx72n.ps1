param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx72n-ws",
    [string]$ProjectsPath = "Projects",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx72n_e2studio_build.log")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Test-Path $E2Studio)) {
    throw "e2studio executable not found: $E2Studio"
}

$projectRoot = (Resolve-Path $ProjectRoot).Path
$workspace = $Workspace
$projectsPath = $ProjectsPath -replace "/", "\"
$logFile = [System.IO.Path]::GetFullPath($LogFile)
$shortRoot = "C:\iotref-rx72n-src"
$projectNames = @(
    "boot_loader_rx72n_envision_kit",
    "aws_ether_rx72n_envision_kit"
)
$rcpcSnapshots = @{}

if (-not (Test-Path (Join-Path $projectRoot "Middleware\FreeRTOS\FreeRTOS-Kernel\include\FreeRTOS.h"))) {
    throw "Git submodules not initialized."
}

if (Test-Path $workspace) {
    Remove-Item -Recurse -Force $workspace
}

foreach ($projectName in $projectNames) {
    $hardwareDebug = Join-Path $projectRoot "$projectsPath\$projectName\e2studio_ccrx\HardwareDebug"
    if (Test-Path $hardwareDebug) {
        Remove-Item -Recurse -Force $hardwareDebug
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
        $rcpcSnapshots[$rcpcPath.FullName] = Get-Content $rcpcPath.FullName -Raw
    }
}

if (Test-Path $shortRoot) {
    cmd /c "rmdir `"$shortRoot`"" 2>$null
}

New-Item -ItemType Junction -Path $shortRoot -Target $projectRoot | Out-Null
Write-Host "Junction: $shortRoot -> $projectRoot"

$imports = @()
foreach ($projectName in $projectNames) {
    $imports += @("-import", (Join-Path $shortRoot "$projectsPath\$projectName\e2studio_ccrx"))
}

$e2base = @(
    "--launcher.suppressErrors",
    "-nosplash",
    "-application", "org.eclipse.cdt.managedbuilder.core.headlessbuild",
    "-data", $workspace
)

Write-Host "=== RX72N import + build all ==="
Write-Host "Workspace: $workspace"
Write-Host "Log file:  $logFile"
foreach ($projectName in $projectNames) {
    Write-Host "Import:    $(Join-Path $shortRoot "$projectsPath\$projectName\e2studio_ccrx")"
}

function Find-Artifacts {
    param(
        [string]$RelativePattern
    )

    $primary = Join-Path $projectRoot $RelativePattern
    $short = Join-Path $shortRoot $RelativePattern

    $items = Get-ChildItem $primary -ErrorAction SilentlyContinue
    if ($items) {
        return $items
    }

    return Get-ChildItem $short -ErrorAction SilentlyContinue
}

try {
    & $E2Studio @e2base @imports -build all 2>&1 | Tee-Object -FilePath $logFile | Out-Null
    $e2exit = $LASTEXITCODE

    Write-Host "e2studio exit code: $e2exit"
    $logLines = Get-Content $logFile -ErrorAction SilentlyContinue
    $logLineCount = if ($logLines) { $logLines.Count } else { 0 }
    Write-Host "Build log: $logLineCount lines"

    if ($e2exit -ne 0) {
        Write-Host "--- Build log (first 100 lines) ---"
        $logLines | Select-Object -First 100 | ForEach-Object { Write-Host "  $_" }
        Write-Host "--- Build log (error lines) ---"
        $logLines | Where-Object { $_ -match '(?i)(error|fatal|cannot|failed|undefined)' } | Select-Object -First 50 | ForEach-Object { Write-Host "  $_" }
    }
    Write-Host "--- Build log tail ---"
    Get-Content $logFile -Tail 30 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $_" }

    $bootMot = Find-Artifacts "$projectsPath\boot_loader_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\*.mot"
    $appMot = Find-Artifacts "$projectsPath\aws_ether_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\*.mot"
    $appAbs = Find-Artifacts "$projectsPath\aws_ether_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\*.abs"
    $appX = Find-Artifacts "$projectsPath\aws_ether_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\*.x"

    Write-Host ""
    Write-Host "--- RX72N artifact search ---"
    Write-Host "  boot_loader .mot: $(if ($bootMot) { $bootMot.FullName } else { 'NOT FOUND' })"
    Write-Host "  aws_ether   .mot: $(if ($appMot) { $appMot.FullName } else { 'NOT FOUND' })"
    Write-Host "  aws_ether   .abs: $(if ($appAbs) { $appAbs.FullName } else { 'NOT FOUND' })"
    Write-Host "  aws_ether     .x: $(if ($appX) { $appX.FullName } else { 'NOT FOUND' })"

    $missing = @()
    if (-not $bootMot) { $missing += "boot_loader_rx72n_envision_kit .mot" }
    if (-not $appMot) { $missing += "aws_ether_rx72n_envision_kit .mot" }
    if (-not $appAbs) { $missing += "aws_ether_rx72n_envision_kit .abs" }
    if (-not $appX) { $missing += "aws_ether_rx72n_envision_kit .x" }

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
    foreach ($rcpcPath in $rcpcSnapshots.Keys) {
        [System.IO.File]::WriteAllText($rcpcPath, $rcpcSnapshots[$rcpcPath], [System.Text.UTF8Encoding]::new($false))
    }

    if (Test-Path $shortRoot) {
        cmd /c "rmdir `"$shortRoot`"" 2>$null
    }
}

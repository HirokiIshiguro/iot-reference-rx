param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx671-wifi-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx671_wifi_e2studio_build.log")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$projectName = "aws_wifi_rx671_ek"
$projectDir = Join-Path $projectRoot "Projects\$projectName\e2studio_ccrx"
$whdDir = Join-Path $projectRoot "Projects\$projectName\external\wifi-host-driver"
$whdPatch = Join-Path $projectRoot "Projects\$projectName\external\patches\whd-v1.70.0-ccrx-portability.patch"

if (-not (Test-Path -LiteralPath $E2Studio)) {
    throw "e2 studio executable not found: $E2Studio"
}

if (-not (Test-Path -LiteralPath (Join-Path $projectDir ".project"))) {
    throw "e2 studio project not found: $projectDir"
}

if (-not (Test-Path -LiteralPath (Join-Path $whdDir ".git"))) {
    throw "WHD submodule is not initialized. Run: git submodule update --init --recursive Projects/aws_wifi_rx671_ek/external/wifi-host-driver"
}

if (-not (Test-Path -LiteralPath $whdPatch)) {
    throw "WHD patch not found: $whdPatch"
}

function Test-GitApply {
    param([string[]]$Arguments)

    & git @Arguments *> $null
    return ($LASTEXITCODE -eq 0)
}

$reverseCheckArgs = @("-C", $whdDir, "apply", "--reverse", "--check", $whdPatch)
$forwardCheckArgs = @("-C", $whdDir, "apply", "--check", $whdPatch)

if (Test-GitApply $reverseCheckArgs) {
    Write-Host "WHD patch is already applied."
} elseif (Test-GitApply $forwardCheckArgs) {
    Write-Host "Applying WHD patch..."
    & git -C $whdDir apply $whdPatch
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to apply WHD patch."
    }
} else {
    throw "WHD patch state is neither clean nor applied. Check submodule status: $whdDir"
}

if (Test-Path -LiteralPath $Workspace) {
    Remove-Item -LiteralPath $Workspace -Recurse -Force
}

$hardwareDebug = Join-Path $projectDir "HardwareDebug"
if (Test-Path -LiteralPath $hardwareDebug) {
    Remove-Item -LiteralPath $hardwareDebug -Recurse -Force
}

$logFilePath = [System.IO.Path]::GetFullPath($LogFile)
Write-Host "=== RX671 Wi-Fi import + build ==="
Write-Host "Project:   $projectDir"
Write-Host "Workspace: $Workspace"
Write-Host "Log file:  $logFilePath"

& $E2Studio `
    -nosplash `
    -application org.eclipse.cdt.managedbuilder.core.headlessbuild `
    -data $Workspace `
    -import $projectDir `
    -cleanBuild "$projectName/HardwareDebug" 2>&1 | Tee-Object -FilePath $logFilePath

if ($LASTEXITCODE -ne 0) {
    throw "e2 studio build failed with exit code $LASTEXITCODE"
}

foreach ($extension in @(".mot", ".abs", ".x")) {
    $output = Join-Path $hardwareDebug "$projectName$extension"
    if (-not (Test-Path -LiteralPath $output)) {
        throw "Expected build output missing: $output"
    }
}

Write-Host "RX671 Wi-Fi build completed successfully."

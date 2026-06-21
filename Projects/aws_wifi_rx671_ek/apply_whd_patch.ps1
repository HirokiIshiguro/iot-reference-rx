param(
    [string]$ProjectRoot = $PSScriptRoot,
    [switch]$Reverse
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$whdPath = Join-Path $projectRootPath "external\wifi-host-driver"
$patchPath = Join-Path $projectRootPath "external\patches\whd-v1.70.0-ccrx-portability.patch"

if (-not (Test-Path -LiteralPath (Join-Path $whdPath ".git"))) {
    throw "WHD submodule is not initialized: $whdPath"
}

if (-not (Test-Path -LiteralPath $patchPath)) {
    throw "WHD patch not found: $patchPath"
}

$checkArgs = @("-C", $whdPath, "apply", "--check", $patchPath)
if ($Reverse.IsPresent) {
    $checkArgs = @("-C", $whdPath, "apply", "--reverse", "--check", $patchPath)
}

& git @checkArgs
if ($LASTEXITCODE -ne 0) {
    throw "Patch check failed. It may already be applied or the submodule is at an unexpected revision."
}

$applyArgs = @("-C", $whdPath, "apply", $patchPath)
if ($Reverse.IsPresent) {
    $applyArgs = @("-C", $whdPath, "apply", "--reverse", $patchPath)
}

& git @applyArgs
if ($LASTEXITCODE -ne 0) {
    throw "Patch apply failed."
}

if ($Reverse.IsPresent) {
    Write-Host "WHD patch reversed: $patchPath"
} else {
    Write-Host "WHD patch applied: $patchPath"
}

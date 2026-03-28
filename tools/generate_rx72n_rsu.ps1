param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$AppMot = "",
    [string]$PrmCsv = "",
    [string]$SigningKey = "",
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
$rsuBuilder = Join-Path $projectRoot "tools\build_fwup_v2_rsu.py"

if ([string]::IsNullOrWhiteSpace($AppMot)) {
    $AppMot = Join-Path $projectRoot "Projects\aws_ether_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\aws_ether_rx72n_envision_kit.mot"
}
if ([string]::IsNullOrWhiteSpace($PrmCsv)) {
    $PrmCsv = Join-Path $projectRoot "Projects\aws_ether_rx72n_envision_kit\e2studio_ccrx\src\smc_gen\r_fwup\tool\RX72N_DualBank_ImageGenerator_PRM.csv"
}
if ([string]::IsNullOrWhiteSpace($SigningKey)) {
    $SigningKey = Join-Path $projectRoot "sample_keys\secp256r1.privatekey"
}
if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $projectRoot "rx72n_local_baseline.rsu"
}

if (-not (Test-Path $rsuBuilder)) {
    throw "RSU builder not found: $rsuBuilder"
}
if (-not (Test-Path $AppMot)) {
    throw "Application .mot not found: $AppMot"
}
if (-not (Test-Path $PrmCsv)) {
    throw "PRM CSV not found: $PrmCsv"
}
if (-not (Test-Path $SigningKey)) {
    throw "Signing key not found: $SigningKey"
}

$outputDir = Split-Path $Output -Parent
if ($outputDir) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

Write-Host "=== Generate RX72N RSU ==="
Write-Host "App MOT:    $AppMot"
Write-Host "PRM CSV:    $PrmCsv"
Write-Host "SigningKey: $SigningKey"
Write-Host "Output:     $Output"

python $rsuBuilder `
    --mot $AppMot `
    --prm $PrmCsv `
    --key $SigningKey `
    --output $Output

if ($LASTEXITCODE -ne 0) {
    throw "RSU generation failed: $LASTEXITCODE"
}

param(
    [Parameter(Mandatory = $true)]
    [string]$E2LSerial,

    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$rfpCli = "C:\Program Files (x86)\Renesas Electronics\Programming Tools\Renesas Flash Programmer V3.22\rfp-cli.exe"
$blMot = Join-Path $RepoRoot "Projects\boot_loader_ck_rx65n_v2\e2studio_ccrx\HardwareDebug\boot_loader_ck_rx65n_v2.mot"
$appMot = Join-Path $RepoRoot "Projects\aws_ether_ck_rx65n_v2\e2studio_ccrx\HardwareDebug\aws_ether_ck_rx65n_v2.mot"

function Invoke-Rfp {
    param(
        [string]$StepLabel,
        [string]$FailureMessage,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "=== $StepLabel ==="
    & $rfpCli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code: $LASTEXITCODE)"
    }
}

Write-Host "============================================================"
Write-Host "iot-reference-rx flash (CK-RX65N V1)"
Write-Host "============================================================"
Write-Host "E2L_SERIAL: $E2LSerial"
Write-Host "REPO_ROOT:  $RepoRoot"
Write-Host "BL_MOT:     $blMot"
Write-Host "APP_MOT:    $appMot"
Write-Host "============================================================"

if (-not (Test-Path $rfpCli)) {
    throw "rfp-cli not found: $rfpCli"
}
if (-not (Test-Path $blMot)) {
    throw "boot_loader .mot not found: $blMot`nRun build_headless.bat first."
}
if (-not (Test-Path $appMot)) {
    throw "app .mot not found: $appMot`nRun build_headless.bat first."
}

$commonArgs = @(
    "-d", "RX65x",
    "-t", "e2l:$E2LSerial",
    "-if", "fine",
    "-s", "500K",
    "-auth", "id", "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
)

try {
    Invoke-Rfp -StepLabel "Step 1: Erase chip" -FailureMessage "Chip erase failed" -Arguments ($commonArgs + @("-erase-chip", "-noquery"))
    Write-Host "Chip erase: OK"

    Invoke-Rfp -StepLabel "Step 2: Write boot_loader" -FailureMessage "boot_loader write failed" -Arguments ($commonArgs + @("-p", $blMot, "-run", "-noquery"))
    Write-Host "boot_loader write: OK"

    Invoke-Rfp -StepLabel "Step 3: Write app" -FailureMessage "app write failed" -Arguments ($commonArgs + @("-file", $appMot, "-auto", "-noerase", "-run", "-noquery"))
    Write-Host "app write: OK"

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "FLASH SUCCESS"
    Write-Host "============================================================"
    exit 0
}
catch {
    Write-Error $_
    if ($LASTEXITCODE) {
        exit $LASTEXITCODE
    }
    exit 1
}

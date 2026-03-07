param(
    [Parameter(Mandatory = $true)]
    [string]$E2LSerial,

    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,

    [string]$UserprogMot = $(Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "userprog.mot")
)

$ErrorActionPreference = "Stop"

$rfpCli = "C:\Program Files (x86)\Renesas Electronics\Programming Tools\Renesas Flash Programmer V3.22\rfp-cli.exe"

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
Write-Host "USERPROG:   $UserprogMot"
Write-Host "============================================================"

if (-not (Test-Path $rfpCli)) {
    throw "rfp-cli not found: $rfpCli"
}
if (-not (Test-Path $UserprogMot)) {
    throw "combined initial image not found: $UserprogMot`nGenerate userprog.mot with image-gen.py first."
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

    Invoke-Rfp -StepLabel "Step 2: Write combined initial image" -FailureMessage "combined image write failed" -Arguments ($commonArgs + @("-p", $UserprogMot, "-run", "-noquery"))
    Write-Host "combined image write: OK"

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

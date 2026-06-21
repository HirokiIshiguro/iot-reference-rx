param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$JLink = "C:\Program Files\SEGGER\JLink_V948\JLink.exe",
    [string]$ProbeSerial = "853004952",
    [string]$MotFile = "",
    [string]$FirmwareBin = "",
    [string]$NvramBin = "",
    [string]$ClmBlob = "",
    [switch]$Run
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$projectName = "aws_wifi_rx671_ek"
$projectDir = Join-Path $projectRootPath "Projects\$projectName\e2studio_ccrx"

if ([string]::IsNullOrWhiteSpace($MotFile)) {
    $MotFile = Join-Path $projectDir "HardwareDebug\$projectName.mot"
}

if (-not (Test-Path -LiteralPath $JLink)) {
    throw "J-Link Commander not found: $JLink"
}

if (-not (Test-Path -LiteralPath $MotFile)) {
    throw "MOT file not found: $MotFile"
}

function Add-LoadBinCommand {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Path,
        [string]$Address
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Binary resource not found: $Path"
    }

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $Lines.Add("loadbin $resolved $Address")
}

$commands = [System.Collections.Generic.List[string]]::new()
$commands.Add("device R5F5671E")
$commands.Add("si JTAG")
$commands.Add("speed 4000")
$commands.Add("jtagconf -1 -1")
$commands.Add("connect")
$commands.Add("loadfile $((Resolve-Path -LiteralPath $MotFile).Path)")
Add-LoadBinCommand -Lines $commands -Path $FirmwareBin -Address "0xFFF00000"
Add-LoadBinCommand -Lines $commands -Path $NvramBin -Address "0xFFF80000"
Add-LoadBinCommand -Lines $commands -Path $ClmBlob -Address "0xFFF90000"

if ($Run.IsPresent) {
    $commands.Add("r")
    $commands.Add("g")
}

$commands.Add("q")

$scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("rx671_wifi_load_{0}.jlink" -f ([System.Guid]::NewGuid().ToString("N")))
try {
    Set-Content -LiteralPath $scriptPath -Value $commands -Encoding ASCII

    $args = @("-CommanderScript", $scriptPath)
    if (-not [string]::IsNullOrWhiteSpace($ProbeSerial)) {
        $args = @("-SelectEmuBySN", $ProbeSerial) + $args
    }

    & $JLink @args
    if ($LASTEXITCODE -ne 0) {
        throw "J-Link Commander failed with exit code $LASTEXITCODE"
    }
} finally {
    if (Test-Path -LiteralPath $scriptPath) {
        Remove-Item -LiteralPath $scriptPath -Force
    }
}

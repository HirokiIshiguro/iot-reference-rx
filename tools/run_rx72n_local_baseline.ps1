param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx72n-ws",
    [string]$RfpCli = "C:\Program Files (x86)\Renesas Electronics\Programming Tools\Renesas Flash Programmer V3.22\rfp-cli.exe",
    [string]$Tool = "e2l:OBE110008",
    [string]$LogPort = "COM7",
    [string]$DownloadPort = "COM7",
    [int]$Baud = 921600,
    [switch]$SkipBuild,
    [switch]$SkipFlashBootLoader,
    [switch]$SkipDownload,
    [switch]$ObserveOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
$bootMot = Join-Path $projectRoot "Projects\boot_loader_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\boot_loader_rx72n_envision_kit.mot"
$appMot = Join-Path $projectRoot "Projects\aws_ether_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\aws_ether_rx72n_envision_kit.mot"
$prm = Join-Path $projectRoot "Projects\aws_ether_rx72n_envision_kit\e2studio_ccrx\src\smc_gen\r_fwup\tool\RX72N_DualBank_ImageGenerator_PRM.csv"
$signingKey = Join-Path $projectRoot "sample_keys\secp256r1.privatekey"
$rsu = Join-Path $projectRoot "rx72n_local_baseline.rsu"
$buildScript = Join-Path $projectRoot "tools\build_headless_rx72n.ps1"
$rsuBuilder = Join-Path $projectRoot "tools\build_fwup_v2_rsu.py"
$bootMonitor = Join-Path $projectRoot "tools\monitor_rx72n_boot.py"
$uartDownload = Join-Path $projectRoot "tools\test_uart_download_rx72n.py"
$readyMessage = 'send "userprog.rsu" via UART.'

function Invoke-Step {
    param(
        [string]$Label,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "============================================================"
    Write-Host $Label
    Write-Host "============================================================"
    & $Action
}

if (-not (Test-Path $RfpCli)) {
    throw "rfp-cli not found: $RfpCli"
}

if (-not $SkipBuild) {
    Invoke-Step "Build RX72N projects" {
        & $buildScript `
            -ProjectRoot $projectRoot `
            -E2Studio $E2Studio `
            -Workspace $Workspace `
            -LogFile (Join-Path $projectRoot "rx72n_e2studio_build.log")
    }
}

if (-not (Test-Path $bootMot)) {
    throw "boot_loader .mot not found: $bootMot"
}
if (-not (Test-Path $appMot)) {
    throw "aws_ether .mot not found: $appMot"
}
if (-not (Test-Path $prm)) {
    throw "PRM file not found: $prm"
}
if (-not (Test-Path $signingKey)) {
    throw "signing key not found: $signingKey"
}

$eraseChipCmd = "& `"$RfpCli`" -device RX72x -tool $Tool -if fine -speed 1500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -erase-chip -noquery"
$flashBootCmd = "& `"$RfpCli`" -device RX72x -tool $Tool -if fine -speed 1500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -p `"$bootMot`" -v -run -noquery"
$resetCmdPwsh = "& `"$RfpCli`" -device RX72x -tool $Tool -if fine -speed 1500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -sig -run -noquery"
$resetCmdCmd = "`"$RfpCli`" -device RX72x -tool $Tool -if fine -speed 1500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -sig -run -noquery"

if (-not $SkipFlashBootLoader) {
    Invoke-Step "Flash boot_loader" {
        Invoke-Expression $eraseChipCmd
        if ($LASTEXITCODE -ne 0) { throw "chip erase failed: $LASTEXITCODE" }
        Invoke-Expression $flashBootCmd
        if ($LASTEXITCODE -ne 0) { throw "boot_loader flash failed: $LASTEXITCODE" }
    }

    Invoke-Step "Observe boot_loader UART" {
        python $bootMonitor `
            --ports $LogPort $DownloadPort `
            --baud $Baud `
            --timeout 10 `
            --command $resetCmdPwsh `
            --expect $readyMessage
    }
}

if ($ObserveOnly) {
    exit 0
}

Invoke-Step "Generate RX72N RSU" {
    python $rsuBuilder `
        --mot $appMot `
        --prm $prm `
        --key $signingKey `
        --output $rsu
}

if (-not $SkipDownload) {
    Invoke-Step "UART download app RSU" {
        python $uartDownload `
            --rsu $rsu `
            --port $DownloadPort `
            --baud $Baud `
            --timeout 300 `
            --diag `
            --wait-for-ready `
            --ready-timeout 60 `
            --send-chunk-size 128 `
            --ack-each-chunk `
            --ack-timeout 20 `
            --reset-cmd $resetCmdCmd `
            --ready-message $readyMessage `
            --success-message "jump to user program" `
            --success-timeout 30
    }
}

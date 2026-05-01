param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\iotref-rx65n-bg96-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx65n_bg96_e2studio_build.log"),
    [int]$E2StudioTimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Test-Path $E2Studio)) {
    throw "e2studio executable not found: $E2Studio"
}

$projectRoot = (Resolve-Path $ProjectRoot).Path
$e2studioHeadless = $E2Studio
if ((Split-Path -Leaf $e2studioHeadless) -ieq "e2studio-cli.exe") {
    $candidate = Join-Path (Split-Path -Parent $e2studioHeadless) "e2studioc.exe"
    if (Test-Path $candidate) {
        $e2studioHeadless = $candidate
    }
}
$workspace = $Workspace
$logFile = [System.IO.Path]::GetFullPath($LogFile)
$bootProject = Join-Path $projectRoot "Projects\boot_loader_ck_rx65n\e2studio_ccrx"
$appProject = Join-Path $projectRoot "Projects\aws_bg96_ck_rx65n\e2studio_ccrx"
$patchBackup = Join-Path $projectRoot "artifacts\rx65n_bg96_aws_dev_mode_key_provisioning.c.orig"

foreach ($projectDir in @($bootProject, $appProject)) {
    if (-not (Test-Path (Join-Path $projectDir ".project"))) {
        throw "e2 studio project not found: $projectDir"
    }
}

function Save-ProjectMetadata {
    param([string[]]$ProjectDirs)

    $snapshots = @{}
    foreach ($projectDir in $ProjectDirs) {
        $paths = @()
        $paths += Get-ChildItem -Path (Join-Path $projectDir ".settings") -File -ErrorAction SilentlyContinue
        $paths += Get-ChildItem -Path $projectDir -Filter "*.rcpc" -File -ErrorAction SilentlyContinue
        foreach ($path in $paths) {
            $snapshots[$path.FullName] = [System.IO.File]::ReadAllBytes($path.FullName)
        }
    }
    return ,$snapshots
}

function Restore-ProjectMetadata {
    param([hashtable]$Snapshots)

    foreach ($path in $Snapshots.Keys) {
        [System.IO.File]::WriteAllBytes($path, $Snapshots[$path])
    }
}

function Convert-ToFileUri {
    param([string]$Path)

    return "file:///" + ($Path -replace "\\", "/" -replace " ", "%20")
}

function Convert-ToArgumentString {
    param([string[]]$Arguments)

    return (($Arguments | ForEach-Object {
        $arg = [string]$_
        if ($arg -match '[\s"]') {
            '"' + ($arg -replace '"', '\"') + '"'
        } else {
            $arg
        }
    }) -join " ")
}

function Write-ProcessOutput {
    param([string[]]$Paths)

    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path) {
            $lines = Get-Content -LiteralPath $path -ErrorAction SilentlyContinue
            if ($lines) {
                Add-Content -LiteralPath $logFile -Value $lines
                $lines | ForEach-Object { Write-Host $_ }
            }
        }
    }
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-ProcessTree -ProcessId $_.ProcessId
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Invoke-E2StudioCli {
    param([string[]]$Arguments)

    Write-Host "+ $e2studioHeadless $($Arguments -join ' ')"
    $tempBase = Join-Path ([System.IO.Path]::GetTempPath()) ("iotref_rx65n_bg96_e2studio_" + [System.Guid]::NewGuid().ToString("N"))
    $stdoutPath = "$tempBase.out"
    $stderrPath = "$tempBase.err"
    $process = Start-Process `
        -FilePath $e2studioHeadless `
        -ArgumentList (Convert-ToArgumentString $Arguments) `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -NoNewWindow `
        -PassThru

    try {
        if (-not $process.WaitForExit($E2StudioTimeoutSeconds * 1000)) {
            Stop-ProcessTree -ProcessId $process.Id
            Write-ProcessOutput @($stdoutPath, $stderrPath)
            throw "e2 studio CLI timed out after $E2StudioTimeoutSeconds seconds: $e2studioHeadless $($Arguments -join ' ')"
        }
        Write-ProcessOutput @($stdoutPath, $stderrPath)
        if ($process.ExitCode -ne 0) {
            throw "e2 studio CLI failed with exit code $($process.ExitCode)"
        }
    }
    finally {
        Remove-Item -Force -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    }
}

function Require-Artifact {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "build artifact missing: $Path"
    }
}

if (-not (Test-Path (Join-Path $appProject "Middleware\FreeRTOS\FreeRTOS-Kernel\include\FreeRTOS.h"))) {
    throw "CK-RX65N BG96 project middleware is incomplete."
}

foreach ($dir in @(
    (Join-Path $bootProject "HardwareDebug"),
    (Join-Path $appProject "HardwareDebug"),
    $workspace
)) {
    if (Test-Path $dir) {
        Remove-Item -Recurse -Force $dir
        Write-Host "Cleared: $dir"
    }
}

$metadataSnapshots = Save-ProjectMetadata @($bootProject, $appProject)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $patchBackup) | Out-Null
if (Test-Path $logFile) {
    Remove-Item -Force $logFile
}

try {
    python (Join-Path $projectRoot "tools\patch_bg96_aws_iot_mcu.py") patch --aws-root $appProject --backup $patchBackup

    New-Item -ItemType Directory -Force -Path $workspace | Out-Null
    $bootWorkspace = Join-Path $workspace "bootloader"
    $appWorkspace = Join-Path $workspace "bg96"
    New-Item -ItemType Directory -Force -Path $bootWorkspace, $appWorkspace | Out-Null

    Write-Host "=== CK-RX65N BG96 boot loader build ==="
    Invoke-E2StudioCli @(
        "--launcher.suppressErrors",
        "-nosplash",
        "-application", "org.eclipse.cdt.managedbuilder.core.headlessbuild",
        "-data", $bootWorkspace,
        "-import", $bootProject,
        "-build", "boot_loader_ck_rx65n/HardwareDebug"
    )

    Write-Host "=== CK-RX65N BG96 application build ==="
    Invoke-E2StudioCli @(
        "--launcher.suppressErrors",
        "-nosplash",
        "-application", "org.eclipse.cdt.managedbuilder.core.headlessbuild",
        "-data", $appWorkspace,
        "-import", $appProject,
        "-build", "aws_bg96_ck_rx65n/HardwareDebug"
    )

    $bootMot = Join-Path $bootProject "HardwareDebug\boot_loader_ck_rx65n.mot"
    $appMot = Join-Path $appProject "HardwareDebug\aws_bg96_ck_rx65n.mot"
    $appAbs = Join-Path $appProject "HardwareDebug\aws_bg96_ck_rx65n.abs"
    $appX = Join-Path $appProject "HardwareDebug\aws_bg96_ck_rx65n.x"
    Require-Artifact $bootMot
    Require-Artifact $appMot
    Require-Artifact $appAbs
    Require-Artifact $appX

    Write-Host ""
    Write-Host "CK-RX65N BG96 headless build succeeded."
    Write-Host "  boot_loader .mot: $bootMot"
    Write-Host "  app         .mot: $appMot"
    Write-Host "  app         .abs: $appAbs"
    Write-Host "  app           .x: $appX"
}
finally {
    python (Join-Path $projectRoot "tools\patch_bg96_aws_iot_mcu.py") restore --aws-root $appProject --backup $patchBackup
    Restore-ProjectMetadata $metadataSnapshots
}

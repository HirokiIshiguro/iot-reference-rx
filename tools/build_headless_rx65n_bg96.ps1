param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\iotref-rx65n-bg96-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx65n_bg96_e2studio_build.log"),
    [int]$E2StudioTimeoutSeconds = 600,
    [string]$Make = $env:RX65N_BG96_MAKE,
    [string]$CcrxBin = $env:BIN_RX,
    [string]$TlsBackend = $(if ($env:RX65N_BG96_TLS_BACKEND) { $env:RX65N_BG96_TLS_BACKEND } else { "software" }),
    [switch]$PrepareBuildFilesOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
$workspace = $Workspace
$logFile = [System.IO.Path]::GetFullPath($LogFile)
$normalizedTlsBackend = $TlsBackend.ToLowerInvariant()
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_bg96_ck_rx65n" }
    "tsip" { $appProjectName = "aws_bg96_ck_rx65n_tsip" }
    default { throw "Unsupported RX65N BG96 TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$bootProject = Join-Path $projectRoot "Projects\boot_loader_ck_rx65n\e2studio_ccrx"
$appProject = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx"
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
        foreach ($fileName in @(".project", ".cproject")) {
            $path = Join-Path $projectDir $fileName
            if (Test-Path -LiteralPath $path) {
                $paths += Get-Item -LiteralPath $path
            }
        }
        $paths += Get-ChildItem -Path (Join-Path $projectDir ".settings") -File -ErrorAction SilentlyContinue
        $paths += Get-ChildItem -Path $projectDir -Filter "*.rcpc" -File -ErrorAction SilentlyContinue
        $paths += Get-ChildItem -Path $projectDir -Filter "*.scfg" -File -ErrorAction SilentlyContinue
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

function Invoke-Tool {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    Write-Host "+ $FilePath $($Arguments -join ' ')"
    Add-Content -LiteralPath $logFile -Value "+ $FilePath $($Arguments -join ' ')"
    $tempBase = Join-Path ([System.IO.Path]::GetTempPath()) ("iotref_rx65n_bg96_make_" + [System.Guid]::NewGuid().ToString("N"))
    $stdoutPath = "$tempBase.out"
    $stderrPath = "$tempBase.err"
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList (Convert-ToArgumentString $Arguments) `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -NoNewWindow `
        -PassThru

    try {
        if (-not $process.WaitForExit($E2StudioTimeoutSeconds * 1000)) {
            Stop-ProcessTree -ProcessId $process.Id
            Write-ProcessOutput @($stdoutPath, $stderrPath)
            throw "build command timed out after $E2StudioTimeoutSeconds seconds: $FilePath $($Arguments -join ' ')"
        }
        Write-ProcessOutput @($stdoutPath, $stderrPath)
        if ($process.ExitCode -ne 0) {
            throw "build command failed with exit code $($process.ExitCode): $FilePath $($Arguments -join ' ')"
        }
    }
    finally {
        Remove-Item -Force -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    }
}

function Get-E2StudioPluginDir {
    if (-not $E2Studio -or -not (Test-Path -LiteralPath $E2Studio)) {
        return $null
    }

    $e2studioPath = (Resolve-Path -LiteralPath $E2Studio).Path
    $baseDir = Split-Path -Parent $e2studioPath
    foreach ($plugins in @(
        (Join-Path $baseDir "plugins"),
        (Join-Path (Join-Path $baseDir "eclipse") "plugins")
    )) {
        if (Test-Path -LiteralPath $plugins) {
            return $plugins
        }
    }
    return $null
}

function Resolve-PluginTool {
    param(
        [string]$PluginFilter,
        [string]$RelativePath
    )

    $plugins = Get-E2StudioPluginDir
    if (-not $plugins) {
        return $null
    }

    $pluginDirs = Get-ChildItem -LiteralPath $plugins -Directory -Filter $PluginFilter -ErrorAction SilentlyContinue |
        Sort-Object -Property Name -Descending
    foreach ($pluginDir in $pluginDirs) {
        $candidate = Join-Path $pluginDir.FullName $RelativePath
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Resolve-Make {
    if ($Make) {
        if (-not (Test-Path -LiteralPath $Make)) {
            throw "make executable not found: $Make"
        }
        return (Resolve-Path -LiteralPath $Make).Path
    }

    $candidate = Resolve-PluginTool "com.renesas.ide.exttools.gnumake.win32.x86_64_*" "mk\make.exe"
    if ($candidate) {
        return $candidate
    }

    $command = Get-Command make.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "GNU make was not found. Set RX65N_BG96_MAKE or provide a valid e2 studio path."
}

function Add-PathEntry {
    param([string]$Path)

    if ($Path -and (Test-Path -LiteralPath $Path)) {
        $resolved = (Resolve-Path -LiteralPath $Path).Path
        $entries = $env:Path -split ';'
        if ($entries -notcontains $resolved) {
            $env:Path = "$resolved;$env:Path"
        }
    }
}

function Resolve-CcrxBin {
    if ($CcrxBin) {
        if (-not (Test-Path -LiteralPath $CcrxBin)) {
            throw "CC-RX bin directory not found: $CcrxBin"
        }
        return (Resolve-Path -LiteralPath $CcrxBin).Path
    }

    if ($env:CCRX_BIN -and (Test-Path -LiteralPath $env:CCRX_BIN)) {
        return (Resolve-Path -LiteralPath $env:CCRX_BIN).Path
    }

    $default = "C:\Program Files (x86)\Renesas\RX\3_7_0\bin"
    if (Test-Path -LiteralPath $default) {
        return (Resolve-Path -LiteralPath $default).Path
    }

    throw "CC-RX bin directory was not found. Set BIN_RX or CCRX_BIN."
}

function Find-FirstArtifact {
    param([string[]]$Paths)

    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    }
    throw "build artifact missing: $($Paths -join ', ')"
}

function Invoke-MakeBuild {
    param(
        [string]$BuildDir,
        [string]$Target
    )

    Invoke-Tool -FilePath $makeExe -Arguments @("clean") -WorkingDirectory $BuildDir
    Invoke-Tool -FilePath $makeExe -Arguments @("-j2", $Target) -WorkingDirectory $BuildDir
}

function Resolve-E2StudioHeadless {
    if (-not $E2Studio -or -not (Test-Path -LiteralPath $E2Studio)) {
        throw "e2 studio executable not found: $E2Studio"
    }

    $resolved = (Resolve-Path -LiteralPath $E2Studio).Path
    $baseDir = Split-Path -Parent $resolved
    $console = Join-Path $baseDir "e2studioc.exe"
    if (Test-Path -LiteralPath $console) {
        return (Resolve-Path -LiteralPath $console).Path
    }
    return $resolved
}

function Get-MissingManagedBuildFiles {
    $missing = @()
    foreach ($projectDir in @($bootProject, $appProject)) {
        $makefile = Join-Path $projectDir "HardwareDebug\makefile"
        if (-not (Test-Path -LiteralPath $makefile)) {
            $missing += $makefile
        }
    }
    return ,$missing
}

function Invoke-E2StudioManagedBuild {
    $headless = Resolve-E2StudioHeadless
    if ($workspace -and (Test-Path -LiteralPath $workspace)) {
        Remove-Item -Recurse -Force -LiteralPath $workspace
    }

    Write-Host "=== CK-RX65N BG96 e2 studio managed build file generation ==="
    Invoke-Tool `
        -FilePath $headless `
        -Arguments @(
            "--launcher.suppressErrors",
            "-nosplash",
            "-application", "org.eclipse.cdt.managedbuilder.core.headlessbuild",
            "-data", $workspace,
            "-import", $bootProject,
            "-import", $appProject,
            "-build", "all"
        ) `
        -WorkingDirectory $projectRoot
}

function Ensure-ManagedBuildFiles {
    $missing = Get-MissingManagedBuildFiles
    if ($missing.Count -eq 0) {
        return
    }

    Write-Host "Generated HardwareDebug makefiles are missing:"
    $missing | ForEach-Object { Write-Host "  $_" }
    Invoke-E2StudioManagedBuild

    $missing = Get-MissingManagedBuildFiles
    if ($missing.Count -ne 0) {
        throw "generated HardwareDebug makefile not found after e2 studio build: $($missing -join ', ')"
    }
}

if (-not (Test-Path (Join-Path $appProject "Middleware\FreeRTOS\FreeRTOS-Kernel\include\FreeRTOS.h"))) {
    throw "CK-RX65N BG96 project middleware is incomplete."
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $patchBackup) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logFile) | Out-Null
if (Test-Path $logFile) {
    Remove-Item -Force $logFile
}

$makeExe = Resolve-Make
$ccrxBinDir = Resolve-CcrxBin
$busyBoxBin = Resolve-PluginTool "com.renesas.ide.exttools.busybox.win32.x86_64_*" "bin"
Add-PathEntry $ccrxBinDir
Add-PathEntry $busyBoxBin

Write-Host "Using GNU make: $makeExe"
Write-Host "Using CC-RX bin: $ccrxBinDir"
Write-Host "TLS backend: $normalizedTlsBackend"
if ($busyBoxBin) {
    Write-Host "Using e2 studio BusyBox tools: $busyBoxBin"
}
if ($workspace) {
    Write-Host "Workspace parameter is unused for direct make builds: $workspace"
}

$metadataSnapshots = Save-ProjectMetadata @($bootProject, $appProject)
$patchApplied = $false

try {
    Ensure-ManagedBuildFiles
    if ($PrepareBuildFilesOnly) {
        Write-Host "CK-RX65N BG96 generated build files are ready."
        return
    }

    python (Join-Path $projectRoot "tools\patch_bg96_aws_iot_mcu.py") patch --aws-root $appProject --backup $patchBackup
    $patchApplied = $true

    $bootBuildDir = Join-Path $bootProject "HardwareDebug"
    $appBuildDir = Join-Path $appProject "HardwareDebug"
    $normalizedBootMot = Join-Path $bootBuildDir "boot_loader_ck_rx65n.mot"
    Remove-Item -Force -LiteralPath $normalizedBootMot -ErrorAction SilentlyContinue

    Write-Host "=== CK-RX65N BG96 boot loader make build ==="
    Invoke-MakeBuild -BuildDir $bootBuildDir -Target "boot_loader_ck_rx65n.mot"

    Write-Host "=== CK-RX65N BG96 application make build ==="
    Invoke-MakeBuild -BuildDir $appBuildDir -Target "$appProjectName.mot"

    $bootMot = Find-FirstArtifact @(
        (Join-Path $bootBuildDir "boot_loader_ck_rx65n.mot"),
        (Join-Path $bootBuildDir "bootloader.mot")
    )
    if ($bootMot -ne $normalizedBootMot) {
        Copy-Item -Force -LiteralPath $bootMot -Destination $normalizedBootMot
        $bootMot = $normalizedBootMot
    }

    $appMot = Find-FirstArtifact @((Join-Path $appBuildDir "$appProjectName.mot"))
    $appAbs = Find-FirstArtifact @((Join-Path $appBuildDir "$appProjectName.abs"))

    Write-Host ""
    Write-Host "CK-RX65N BG96 make build succeeded."
    Write-Host "  boot_loader .mot: $bootMot"
    Write-Host "  app         .mot: $appMot"
    Write-Host "  app         .abs: $appAbs"
}
finally {
    if ($patchApplied) {
        python (Join-Path $projectRoot "tools\patch_bg96_aws_iot_mcu.py") restore --aws-root $appProject --backup $patchBackup
    }
    Restore-ProjectMetadata $metadataSnapshots
}

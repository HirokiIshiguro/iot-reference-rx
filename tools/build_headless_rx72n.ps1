param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx72n-ws",
    [string]$ProjectsPath = "Projects",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx72n_e2studio_build.log"),
    [int]$E2StudioTimeoutSeconds = 600,
    [string]$TlsBackend = $(if ($env:RX72N_TLS_BACKEND) { $env:RX72N_TLS_BACKEND } else { "software" })
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
$normalizedTlsBackend = $TlsBackend.ToLowerInvariant()
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_ether_rx72n_envision_kit" }
    "tsip" { $appProjectName = "aws_ether_rx72n_envision_kit_tsip" }
    default { throw "Unsupported RX72N TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$projectNames = @(
    "boot_loader_rx72n_envision_kit",
    $appProjectName
)
$rcpcSnapshots = @{}

if (-not (Test-Path (Join-Path $projectRoot "Middleware\FreeRTOS\FreeRTOS-Kernel\include\FreeRTOS.h"))) {
    throw "Git submodules not initialized."
}

if (-not (Test-Path (Join-Path $projectRoot "Middleware\FreeRTOS\corePKCS11\source\dependency\3rdparty\pkcs11\published\2-40-errata-1\pkcs11.h"))) {
    throw "Git submodules not initialized recursively. Missing corePKCS11 pkcs11.h."
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

$imports = @()
foreach ($projectName in $projectNames) {
    $imports += @("-import", (Join-Path $projectRoot "$projectsPath\$projectName\e2studio_ccrx"))
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
Write-Host "TLS backend: $normalizedTlsBackend"
foreach ($projectName in $projectNames) {
    Write-Host "Import:    $(Join-Path $projectRoot "$projectsPath\$projectName\e2studio_ccrx")"
}

function Find-Artifacts {
    param(
        [string]$RelativePattern
    )

    $primary = Join-Path $projectRoot $RelativePattern
    $items = Get-ChildItem $primary -ErrorAction SilentlyContinue
    if ($items) {
        return $items
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

function Invoke-E2StudioCli {
    param([string[]]$Arguments)

    Write-Host "+ $E2Studio $($Arguments -join ' ')"
    $tempBase = Join-Path ([System.IO.Path]::GetTempPath()) ("iotref_rx72n_e2studio_" + [System.Guid]::NewGuid().ToString("N"))
    $stdoutPath = "$tempBase.out"
    $stderrPath = "$tempBase.err"
    $process = Start-Process `
        -FilePath $E2Studio `
        -ArgumentList (Convert-ToArgumentString $Arguments) `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -NoNewWindow `
        -PassThru

    try {
        if (-not $process.WaitForExit($E2StudioTimeoutSeconds * 1000)) {
            Stop-ProcessTree -ProcessId $process.Id
            Write-ProcessOutput @($stdoutPath, $stderrPath)
            throw "e2 studio CLI timed out after $E2StudioTimeoutSeconds seconds: $E2Studio $($Arguments -join ' ')"
        }
        Write-ProcessOutput @($stdoutPath, $stderrPath)
        return $process.ExitCode
    }
    finally {
        Remove-Item -Force -LiteralPath $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    }
}

try {
    Remove-Item -Force -LiteralPath $logFile -ErrorAction SilentlyContinue
    $e2exit = Invoke-E2StudioCli (@() + $e2base + $imports + @("-build", "all"))

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
    $appMot = Find-Artifacts "$projectsPath\$appProjectName\e2studio_ccrx\HardwareDebug\*.mot"
    $appAbs = Find-Artifacts "$projectsPath\$appProjectName\e2studio_ccrx\HardwareDebug\*.abs"
    $appX = Find-Artifacts "$projectsPath\$appProjectName\e2studio_ccrx\HardwareDebug\*.x"

    Write-Host ""
    Write-Host "--- RX72N artifact search ---"
    Write-Host "  boot_loader .mot: $(if ($bootMot) { $bootMot.FullName } else { 'NOT FOUND' })"
    Write-Host "  $appProjectName .mot: $(if ($appMot) { $appMot.FullName } else { 'NOT FOUND' })"
    Write-Host "  $appProjectName .abs: $(if ($appAbs) { $appAbs.FullName } else { 'NOT FOUND' })"
    Write-Host "  $appProjectName   .x: $(if ($appX) { $appX.FullName } else { 'NOT FOUND' })"

    $missing = @()
    if (-not $bootMot) { $missing += "boot_loader_rx72n_envision_kit .mot" }
    if (-not $appMot) { $missing += "$appProjectName .mot" }
    if (-not $appAbs) { $missing += "$appProjectName .abs" }
    if (-not $appX) { $missing += "$appProjectName .x" }

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
}

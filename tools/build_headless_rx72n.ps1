param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx72n-ws",
    [string]$ProjectsPath = "Projects",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx72n_e2studio_build.log"),
    [int]$E2StudioTimeoutSeconds = 600,
    [string]$TlsBackend = $(if ($env:RX72N_TLS_BACKEND) { $env:RX72N_TLS_BACKEND } else { "software" }),
    [string]$RequireTlsVersion = $(if ($env:RX72N_REQUIRE_TLS_VERSION) { $env:RX72N_REQUIRE_TLS_VERSION } else { "" }),
    [string]$Tls13ResumptionTest = $(if ($env:RX72N_TLS13_RESUMPTION_TEST) { $env:RX72N_TLS13_RESUMPTION_TEST } else { "" })
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
$normalizedRequireTlsVersion = $RequireTlsVersion.ToLowerInvariant()
$enableTls13ResumptionTest = $Tls13ResumptionTest.ToLowerInvariant() -in @("1", "true", "yes", "on")
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_ether_rx72n_envision_kit" }
    "tsip" { $appProjectName = "aws_ether_rx72n_envision_kit_tsip" }
    default { throw "Unsupported RX72N TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$isTls13Required = $normalizedRequireTlsVersion -in @("tlsv1.3", "tls1.3", "tls13")
$useTsipTls13Config = ($normalizedTlsBackend -eq "tsip") -and $isTls13Required
if ($enableTls13ResumptionTest -and (($normalizedTlsBackend -ne "software") -or (-not $isTls13Required))) {
    throw "RX72N TLS 1.3 resumption test currently requires software TLS backend and RX72N_REQUIRE_TLS_VERSION=TLSv1.3."
}
$projectNames = @(
    "boot_loader_rx72n_envision_kit",
    $appProjectName
)
$metadataSnapshots = @{}

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
        $metadataSnapshots[$rcpcPath.FullName] = [System.IO.File]::ReadAllBytes($rcpcPath.FullName)
    }

    $cprojectPath = Join-Path $projectDir ".cproject"
    if (Test-Path -LiteralPath $cprojectPath) {
        $metadataSnapshots[$cprojectPath] = [System.IO.File]::ReadAllBytes($cprojectPath)
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
Write-Host "Require TLS version: $(if ($RequireTlsVersion) { $RequireTlsVersion } else { '<none>' })"
Write-Host "TSIP TLS 1.3 config: $useTsipTls13Config"
Write-Host "TLS 1.3 resumption test: $enableTls13ResumptionTest"
foreach ($projectName in $projectNames) {
    Write-Host "Import:    $(Join-Path $projectRoot "$projectsPath\$projectName\e2studio_ccrx")"
}

function Use-MbedTlsConfigFile {
    param(
        [string]$ProjectDir,
        [string]$ConfigFile
    )

    $cproject = Join-Path $ProjectDir ".cproject"
    if (-not (Test-Path -LiteralPath $cproject)) {
        throw ".cproject not found: $cproject"
    }

    $from = 'MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip.h&quot;&gt;'
    $to = "MBEDTLS_CONFIG_FILE=&lt;&quot;$ConfigFile&quot;&gt;"
    $content = [System.IO.File]::ReadAllText($cproject)
    if (-not $content.Contains($from)) {
        throw "TSIP mbed TLS config macro not found in $cproject"
    }
    [System.IO.File]::WriteAllText(
        $cproject,
        $content.Replace($from, $to),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Selected mbed TLS config for ${ProjectDir}: $ConfigFile"
}

function Add-CompilerDefine {
    param(
        [string]$ProjectDir,
        [string]$Define
    )

    $cproject = Join-Path $ProjectDir ".cproject"
    if (-not (Test-Path -LiteralPath $cproject)) {
        throw ".cproject not found: $cproject"
    }

    $escapedDefine = [System.Security.SecurityElement]::Escape($Define)
    $content = [System.IO.File]::ReadAllText($cproject)
    if ($content.Contains("value=`"$escapedDefine`"")) {
        Write-Host "Compiler define already present in ${ProjectDir}: $Define"
        return
    }

    $regexOptions = [System.Text.RegularExpressions.RegexOptions]::Singleline
    $pattern = '(<option\b[^>]*superClass="com\.renesas\.cdt\.managedbuild\.renesas\.ccrx\.compiler\.option\.define"[^>]*>)(.*?)(\r?\n\s*</option>)'
    $match = [System.Text.RegularExpressions.Regex]::Match($content, $pattern, $regexOptions)
    if (-not $match.Success) {
        throw "Compiler define option not found in $cproject"
    }

    $lineEnding = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
    $insert = "$lineEnding`t`t`t`t`t`t`t`t`t<listOptionValue builtIn=`"false`" value=`"$escapedDefine`"/>"
    $updated = $content.Substring(0, $match.Groups[3].Index) + $insert + $content.Substring($match.Groups[3].Index)
    [System.IO.File]::WriteAllText($cproject, $updated, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Added compiler define to ${ProjectDir}: $Define"
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
    if ($useTsipTls13Config) {
        Use-MbedTlsConfigFile `
            -ProjectDir (Join-Path $projectRoot "$projectsPath\$appProjectName\e2studio_ccrx") `
            -ConfigFile "aws_mbedtls_config_with_tsip13.h"
    }

    if ($enableTls13ResumptionTest) {
        $appProjectDir = Join-Path $projectRoot "$projectsPath\$appProjectName\e2studio_ccrx"
        Add-CompilerDefine -ProjectDir $appProjectDir -Define "MBEDTLS_SSL_SESSION_TICKETS"
        Add-CompilerDefine -ProjectDir $appProjectDir -Define "TLS_TRANSPORT_ENABLE_TLS13_SESSION_RESUMPTION=1"
        Add-CompilerDefine -ProjectDir $appProjectDir -Define "democonfigTLS13_RESUMPTION_TEST=1"
    }

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
    foreach ($metadataPath in $metadataSnapshots.Keys) {
        [System.IO.File]::WriteAllBytes($metadataPath, $metadataSnapshots[$metadataPath])
    }
}

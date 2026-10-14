param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\ai\codex\ws\iotref-rx65n-bg96-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx65n_bg96_e2studio_build.log"),
    [int]$E2StudioTimeoutSeconds = 1800,
    [string]$Make = $env:RX65N_BG96_MAKE,
    [string]$CcrxBin = $env:BIN_RX,
    [string]$TlsBackend = $(if ($env:RX65N_BG96_TLS_BACKEND) { $env:RX65N_BG96_TLS_BACKEND } else { "software" }),
    [string]$RequireTlsVersion = $(if ($env:RX65N_BG96_REQUIRE_TLS_VERSION) { $env:RX65N_BG96_REQUIRE_TLS_VERSION } else { "" }),
    [switch]$Tls13ZeroRtt,
    [string]$LanbenchTls13ZeroRttHost = $env:LANBENCH_MBEDTLS_0RTT_HOST,
    [string]$LanbenchTls13ZeroRttServerName = $env:LANBENCH_MBEDTLS_0RTT_SERVER_NAME,
    [string]$LanbenchTls13ZeroRttPort = $(if ($env:LANBENCH_MBEDTLS_0RTT_PORT) { $env:LANBENCH_MBEDTLS_0RTT_PORT } else { "5443" }),
    [switch]$PrepareBuildFilesOnly,
    [switch]$PreserveLinkerLayout
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "rx_e2studio_cli.ps1")
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
Initialize-RxBuildDependencies -ProjectRoot $projectRoot
Assert-RxCommonKernel -ProjectRoot $projectRoot
$workspace = $Workspace
$logFile = [System.IO.Path]::GetFullPath($LogFile)
$normalizedTlsBackend = $TlsBackend.ToLowerInvariant()
$normalizedRequireTlsVersion = $RequireTlsVersion.ToLowerInvariant()
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_bg96_ck_rx65n" }
    "tsip" { $appProjectName = "aws_bg96_ck_rx65n_tsip" }
    default { throw "Unsupported RX65N BG96 TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$useTsipTls13Config = ($normalizedTlsBackend -eq "tsip") -and ($normalizedRequireTlsVersion -in @("tlsv1.3", "tls1.3", "tls13"))
$useTls13ZeroRttConfig = $Tls13ZeroRtt.IsPresent
$useSoftwareTls13ZeroRttConfig = $useTls13ZeroRttConfig -and ($normalizedTlsBackend -eq "software")
$useTsipTls13ZeroRttConfig = $useTls13ZeroRttConfig -and ($normalizedTlsBackend -eq "tsip")
$bootProject = Join-Path $projectRoot "Projects\boot_loader_ck_rx65n\e2studio_ccrx"
$appProject = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx"
$lanbenchTls13ZeroRttConfigHeader = Join-Path $projectRoot "Demos\include\lanbench_tls13_0rtt_config.h"

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

function Use-MbedTlsConfigFile {
    param(
        [string]$ProjectDir,
        [string]$ConfigFile
    )

    $cproject = Join-Path $ProjectDir ".cproject"
    if (-not (Test-Path -LiteralPath $cproject)) {
        throw ".cproject not found: $cproject"
    }

    $to = "MBEDTLS_CONFIG_FILE=&lt;&quot;$ConfigFile&quot;&gt;"
    $content = [System.IO.File]::ReadAllText($cproject)
    $pattern = 'MBEDTLS_CONFIG_FILE=&lt;&quot;[^&]+\.h&quot;&gt;'
    if (-not [regex]::IsMatch($content, $pattern)) {
        throw "mbed TLS config macro not found in $cproject"
    }
    [System.IO.File]::WriteAllText(
        $cproject,
        [regex]::Replace($content, $pattern, $to, 1),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Selected mbed TLS config for ${ProjectDir}: $ConfigFile"
}

function Add-CompilerDefine {
    param(
        [string]$ProjectDir,
        [string]$Define,
        [string]$Anchor
    )

    $cproject = Join-Path $ProjectDir ".cproject"
    $content = [System.IO.File]::ReadAllText($cproject)
    if ($content.Contains("value=`"$Define`"")) {
        return
    }
    if (-not $content.Contains($Anchor)) {
        throw "compiler define anchor not found in $cproject"
    }

    $insert = $Anchor + "`r`n" + "`t`t`t`t`t`t`t`t`t<listOptionValue builtIn=`"false`" value=`"$Define`"/>"
    [System.IO.File]::WriteAllText(
        $cproject,
        $content.Replace($Anchor, $insert),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Added compiler define for ${ProjectDir}: $Define"
}

function Assert-LanbenchEndpointValue {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name requires a non-empty value."
    }
    if ($Value -notmatch '^[A-Za-z0-9_.:-]+$') {
        throw "$Name contains a character that is not supported by the generated CC-RX config header: $Value"
    }
}

function Write-LanbenchTls13ZeroRttConfigHeader {
    Assert-LanbenchEndpointValue -Name "LANBENCH_MBEDTLS_0RTT_HOST" -Value $LanbenchTls13ZeroRttHost
    Assert-LanbenchEndpointValue -Name "LANBENCH_MBEDTLS_0RTT_SERVER_NAME" -Value $LanbenchTls13ZeroRttServerName

    $portNumber = [int]$LanbenchTls13ZeroRttPort
    if (($portNumber -lt 1) -or ($portNumber -gt 65535)) {
        throw "LANBENCH TLS 1.3 0-RTT port is out of range: $LanbenchTls13ZeroRttPort"
    }

    $content = @"
/*
 * Generated by tools/build_headless_rx65n_bg96.ps1 for a cellular-reachable
 * LANBENCH TLS 1.3 resumption/0-RTT smoke build. This file is restored by the
 * build script after the build finishes.
 */

#ifndef LANBENCH_TLS13_0RTT_CONFIG_H_
    #define LANBENCH_TLS13_0RTT_CONFIG_H_

    #define LANBENCH_TLS13_0RTT_HOST           "$LanbenchTls13ZeroRttHost"
    #define LANBENCH_TLS13_0RTT_SERVER_NAME    "$LanbenchTls13ZeroRttServerName"
    #define LANBENCH_TLS_PORT                  ( ${portNumber}U )

#endif /* LANBENCH_TLS13_0RTT_CONFIG_H_ */
"@

    [System.IO.File]::WriteAllText(
        $lanbenchTls13ZeroRttConfigHeader,
        $content,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Generated LANBENCH TLS 1.3 0-RTT config header: $lanbenchTls13ZeroRttConfigHeader"
}

function Assert-Tls13ZeroRttBuildInputs {
    if ($normalizedRequireTlsVersion -notin @("tlsv1.3", "tls1.3", "tls13")) {
        throw "-Tls13ZeroRtt requires -RequireTlsVersion TLSv1.3."
    }
    if ([string]::IsNullOrWhiteSpace($LanbenchTls13ZeroRttHost)) {
        throw "-Tls13ZeroRtt requires LANBENCH_MBEDTLS_0RTT_HOST or -LanbenchTls13ZeroRttHost because BG96 must connect to a cellular-reachable TLS server."
    }
    if ([string]::IsNullOrWhiteSpace($LanbenchTls13ZeroRttServerName)) {
        $script:LanbenchTls13ZeroRttServerName = $LanbenchTls13ZeroRttHost
    }
    if ($LanbenchTls13ZeroRttPort -notmatch '^\d+$') {
        throw "LANBENCH TLS 1.3 0-RTT port must be numeric: $LanbenchTls13ZeroRttPort"
    }
}

function Enable-SoftwareTls13ZeroRttBuild {
    Assert-Tls13ZeroRttBuildInputs
    Use-MbedTlsConfigFile -ProjectDir $appProject -ConfigFile "aws_mbedtls_config_tls13_0rtt.h"
    $configAnchor = '<listOptionValue builtIn="false" value="MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_tls13_0rtt.h&quot;&gt;"/>'
    Add-CompilerDefine -ProjectDir $appProject -Define 'LANBENCH_TLS13_0RTT_ENABLE=1' -Anchor $configAnchor
    Add-CompilerDefine -ProjectDir $appProject -Define 'LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE=1' -Anchor $configAnchor
    Write-LanbenchTls13ZeroRttConfigHeader
}

function Enable-TsipTls13ZeroRttBuild {
    Assert-Tls13ZeroRttBuildInputs
    & (Join-Path $projectRoot "tools\prepare_mbedtls364_tsip_0rtt_build.ps1") `
        -ProjectRoot $projectRoot `
        -ProjectName $appProjectName
    Write-LanbenchTls13ZeroRttConfigHeader
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
        [string]$WorkingDirectory,
        [switch]$AllowNonZeroExit
    )

    $displayArguments = @($Arguments | ForEach-Object {
        if ($_.StartsWith('PATH=', [StringComparison]::Ordinal)) { 'PATH=<current process tool paths>' }
        else { $_ }
    })
    Write-Host "+ $FilePath $($displayArguments -join ' ')"
    Add-Content -LiteralPath $logFile -Value "+ $FilePath $($displayArguments -join ' ')"
    $tempBase = Join-Path ([System.IO.Path]::GetTempPath()) ("iotref_rx65n_bg96_make_" + [System.Guid]::NewGuid().ToString("N"))
    $stdoutPath = "$tempBase.out"
    $stderrPath = "$tempBase.err"
    $stdinPath = "$tempBase.in"
    # Headless builds accept no interactive input. An EOF stdin also prevents
    # no-argument compiler version probes from waiting for linker commands.
    [IO.File]::WriteAllBytes($stdinPath, [byte[]]@())
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList (Convert-ToArgumentString $Arguments) `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -RedirectStandardInput $stdinPath `
        -WindowStyle Hidden `
        -PassThru

    try {
        if (-not $process.WaitForExit($E2StudioTimeoutSeconds * 1000)) {
            Stop-ProcessTree -ProcessId $process.Id
            Write-ProcessOutput @($stdoutPath, $stderrPath)
            throw "build command timed out after $E2StudioTimeoutSeconds seconds: $FilePath $($displayArguments -join ' ')"
        }
        $process.WaitForExit()
        $process.Refresh()
        Write-ProcessOutput @($stdoutPath, $stderrPath)
        if ($process.ExitCode -ne 0) {
            if ($AllowNonZeroExit) {
                Write-Warning "build command returned exit code $($process.ExitCode); continuing after output validation: $FilePath $($displayArguments -join ' ')"
                return
            }
            throw "build command failed with exit code $($process.ExitCode): $FilePath $($displayArguments -join ' ')"
        }
    }
    finally {
        Remove-Item -Force -LiteralPath $stdoutPath, $stderrPath, $stdinPath -ErrorAction SilentlyContinue
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

    # Start-Process can inherit the launcher's original environment rather than
    # the tool paths added by this script. Bind GNU make's exported PATH to the
    # resolved current process paths so lbgrx, ccrx and BusyBox remain available.
    Invoke-Tool -FilePath $makeExe -Arguments @("PATH=$env:Path", "clean") -WorkingDirectory $BuildDir
    Invoke-Tool -FilePath $makeExe -Arguments @("PATH=$env:Path", "-j2", $Target) -WorkingDirectory $BuildDir
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

function Clear-GeneratedBuildFiles {
    foreach ($projectDir in @($bootProject, $appProject)) {
        $hardwareDebug = Join-Path $projectDir "HardwareDebug"
        if (Test-Path -LiteralPath $hardwareDebug) {
            Remove-RxProjectBuildDirectory -ProjectPath $projectDir
            Write-Host "Cleared generated build files: $hardwareDebug"
        }
    }
}

function Invoke-E2StudioManagedBuild {
    Remove-RxE2Workspace -Path $workspace
    Write-Host "=== CK-RX65N BG96 e2studio-cli managed build file generation ==="
    $exitCode = Invoke-RxE2StudioBuild -Executable $E2Studio -WorkspacePath $workspace `
        -ProjectPaths @($bootProject, $appProject) `
        -BuildTargets @('boot_loader_ck_rx65n/HardwareDebug', "$appProjectName/HardwareDebug") `
        -OutputLog $logFile -TimeoutSeconds $E2StudioTimeoutSeconds
    if ($exitCode -ne 0) {
        Write-Warning "e2studio-cli returned $exitCode; validating generated makefiles before direct make."
    }
}

function Ensure-ManagedBuildFiles {
    # Generated make/response files are a cache of .project/.cproject. A file's
    # existence cannot prove its source selection, include paths or flags match
    # the current normal/Fleet/native profile. Regenerate from metadata each run.
    Clear-GeneratedBuildFiles
    Invoke-E2StudioManagedBuild

    $missing = Get-MissingManagedBuildFiles
    if ($missing.Count -ne 0) {
        throw "generated HardwareDebug makefile not found after e2 studio build: $($missing -join ', ')"
    }
}

function Get-ReviewedLinkerLayout {
    param([string]$ProjectDir)

    $metadataPath = Join-Path $ProjectDir '.cproject'
    $metadata = [Xml.XmlDocument]::new()
    $metadata.Load($metadataPath)
    $section = $metadata.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.linkerSection']")
    $mapping = $metadata.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.rom']")
    if (-not $section -or -not $mapping -or [string]::IsNullOrWhiteSpace($section.GetAttribute('value'))) {
        throw 'Cannot capture the reviewed CC-RX linker layout.'
    }
    $rom = @($mapping.SelectNodes('listOptionValue') | ForEach-Object { $_.GetAttribute('value') } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ','
    if ([string]::IsNullOrWhiteSpace($rom)) { throw 'The reviewed CC-RX ROM/RAM mapping is empty.' }
    return [ordered]@{
        start = '-start=' + $section.GetAttribute('value')
        rom = '-rom=' + $rom
        cproject_sha256 = (Get-FileHash -LiteralPath $metadataPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Restore-ReviewedLinkerLayout {
    param([hashtable]$Layouts)

    $evidence = @()
    foreach ($projectDir in $Layouts.Keys) {
        $projectName = Split-Path (Split-Path $projectDir -Parent) -Leaf
        $commandPath = Join-Path $projectDir "HardwareDebug\Linker$projectName.tmp"
        if (-not (Test-Path -LiteralPath $commandPath -PathType Leaf)) {
            throw "Generated CC-RX linker command is missing: $commandPath"
        }
        $text = [IO.File]::ReadAllText($commandPath)
        foreach ($option in @('start', 'rom')) {
            if ($text -notmatch "(?m)^\s*-$option=") {
                throw "Generated CC-RX linker command has no -$option option."
            }
        }
        # e2 studio's cold import can replace .cproject sections with an older
        # Smart Configurator layout. CC-RX combines repeated -start options, so
        # an override must replace those lines instead of appending a map.
        $text = [regex]::Replace($text, '(?m)^[ \t]*-(start|rom)=[^\r\n]*(?:\r?\n|$)', '')
        $layout = $Layouts[$projectDir]
        $text = $layout.start + "`r`n" + $layout.rom + "`r`n" + $text
        [IO.File]::WriteAllText($commandPath, $text, [Text.UTF8Encoding]::new($false))
        $evidence += [ordered]@{
            project = $projectName; start = $layout.start; rom = $layout.rom
            cproject_sha256 = $layout.cproject_sha256
            linker_command_sha256 = (Get-FileHash -LiteralPath $commandPath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        Write-Host "Restored the reviewed CC-RX linker layout: $projectName"
    }
    ConvertTo-Json -InputObject @($evidence) -Depth 4 |
        Set-Content -LiteralPath ($logFile + '.linker-layout.json') -Encoding UTF8
}

if (-not (Test-Path (Join-Path $projectRoot "Middleware\FreeRTOS\FreeRTOS-Kernel\include\FreeRTOS.h"))) {
    throw "Root shared FreeRTOS submodules are not initialized."
}

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
Write-Host "Require TLS version: $(if ($RequireTlsVersion) { $RequireTlsVersion } else { '<none>' })"
Write-Host "TSIP TLS 1.3 config: $useTsipTls13Config"
Write-Host "TLS 1.3 resumption/0-RTT config: $useTls13ZeroRttConfig"
if ($busyBoxBin) {
    Write-Host "Using e2 studio BusyBox tools: $busyBoxBin"
}
if ($workspace) {
    Write-Host "e2studio-cli workspace: $workspace"
}

$metadataSnapshots = Save-ProjectMetadata @($bootProject, $appProject)
$reviewedLinkerLayouts = @{}
# Normal and native builds both use the registered dual-bank/RAM layout.
# PreserveLinkerLayout remains accepted by older callers; the layout is always
# captured and restored into generated linker commands.
foreach ($projectDir in @($bootProject, $appProject)) {
    $reviewedLinkerLayouts[$projectDir] = Get-ReviewedLinkerLayout $projectDir
}
$lanbenchConfigHeaderExisted = Test-Path -LiteralPath $lanbenchTls13ZeroRttConfigHeader
$lanbenchConfigHeaderSnapshot = if ($lanbenchConfigHeaderExisted) {
    [System.IO.File]::ReadAllBytes($lanbenchTls13ZeroRttConfigHeader)
} else {
    $null
}

try {
    if ($useSoftwareTls13ZeroRttConfig) {
        Enable-SoftwareTls13ZeroRttBuild
    }
    elseif ($useTsipTls13ZeroRttConfig) {
        Enable-TsipTls13ZeroRttBuild
    }
    elseif ($useTsipTls13Config) {
        Use-MbedTlsConfigFile -ProjectDir $appProject -ConfigFile "aws_mbedtls_config_with_tsip13.h"
    }

    Ensure-ManagedBuildFiles
    Restore-ReviewedLinkerLayout $reviewedLinkerLayouts
    if ($PrepareBuildFilesOnly) {
        Write-Host "CK-RX65N BG96 generated build files are ready."
        return
    }

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
    Restore-ProjectMetadata $metadataSnapshots
    if ($lanbenchConfigHeaderExisted) {
        [System.IO.File]::WriteAllBytes($lanbenchTls13ZeroRttConfigHeader, $lanbenchConfigHeaderSnapshot)
    } else {
        Remove-Item -Force -LiteralPath $lanbenchTls13ZeroRttConfigHeader -ErrorAction SilentlyContinue
    }
}

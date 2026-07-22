param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\Temp\e2ws_iot_ref_rx671_bootloader_2026_04_2",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx671_bootloader_e2studio_build.log"),
    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"

$projectName = "boot_loader_rx671_ek"
$relativeProject = "Projects\boot_loader_rx671_ek\e2studio_ccrx"
$relativeSubmodule = "$relativeProject\lib\rx_bootloader"
$expectedSubmoduleHead = "c31bac703e1406e7a94d398b7bcad108b5e8fdce"

function Remove-BuildDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$AllowedRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedLeaf
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $fullAllowedRoot = [System.IO.Path]::GetFullPath($AllowedRoot).TrimEnd('\', '/')
    $allowedPrefix = $fullAllowedRoot + [System.IO.Path]::DirectorySeparatorChar
    if ((Split-Path -Leaf $fullPath) -ne $ExpectedLeaf -or
        -not $fullPath.StartsWith($allowedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove '$fullPath'; expected '$ExpectedLeaf' below '$fullAllowedRoot'."
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
}

function Invoke-E2StudioBuild {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string]$WorkspacePath,
        [Parameter(Mandatory = $true)][string]$ProjectPath,
        [Parameter(Mandatory = $true)][string]$OutputLog
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $Executable
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    foreach ($argument in @(
        "--launcher.suppressErrors",
        "-nosplash",
        "-application", "org.eclipse.cdt.managedbuilder.core.headlessbuild",
        "-data", $WorkspacePath,
        "-import", $ProjectPath,
        "-build", "$projectName/HardwareDebug"
    )) {
        [void]$psi.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $process.Kill($true) } catch { Write-Warning $_ }
        throw "e2 studio build timed out after $TimeoutSeconds seconds"
    }
    $stdout.Wait()
    $stderr.Wait()
    $outputChunks = @($stdout.Result, $stderr.Result) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $text = [string]::Join([Environment]::NewLine, $outputChunks)
    [System.IO.File]::WriteAllText(
        [System.IO.Path]::GetFullPath($OutputLog),
        $text,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host $text
    return $process.ExitCode
}

$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$projectPath = Join-Path $projectRootPath $relativeProject
$submodulePath = Join-Path $projectRootPath $relativeSubmodule
$e2StudioPath = (Resolve-Path -LiteralPath $E2Studio).Path
$workspacePath = [System.IO.Path]::GetFullPath($Workspace)
$hardwareDebug = Join-Path $projectPath "HardwareDebug"
$workspaceRoots = @(
    [System.IO.Path]::GetFullPath("C:\Temp"),
    [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()),
    [System.IO.Path]::GetFullPath("C:\ai\codex\ws")
) | Select-Object -Unique
$workspaceRoot = $workspaceRoots | Where-Object {
    $prefix = $_.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $workspacePath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($workspaceRoot)) {
    throw "Workspace '$workspacePath' must be below C:\Temp, the current user's temp directory, or C:\ai\codex\ws."
}
$generatedMetadata = @(
    (Join-Path $projectPath ".settings\com.renesas.smc.generationsetting.properties"),
    (Join-Path $projectPath ".settings\com.renesas.smc.tools.swcomponent.fit.properties")
)
$metadataSnapshot = @{}
foreach ($path in $generatedMetadata) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $metadataSnapshot[$path] = [System.IO.File]::ReadAllBytes($path)
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $projectPath ".project"))) {
    throw "RX671 boot-loader e2 studio project is missing: $projectPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $submodulePath ".git"))) {
    $relativeSubmoduleGit = $relativeSubmodule -replace '\\', '/'
    & git -C $projectRootPath submodule update --init --recursive -- $relativeSubmoduleGit
    if ($LASTEXITCODE -ne 0) {
        throw "RX671 boot-loader submodule initialization failed"
    }
}
$actualSubmoduleHead = (& git -C $submodulePath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualSubmoduleHead -ne $expectedSubmoduleHead) {
    throw "RX671 boot-loader submodule HEAD is '$actualSubmoduleHead'; expected '$expectedSubmoduleHead'"
}

Remove-BuildDirectory `
    -Path $workspacePath `
    -AllowedRoot $workspaceRoot `
    -ExpectedLeaf "e2ws_iot_ref_rx671_bootloader_2026_04_2"
Remove-BuildDirectory -Path $hardwareDebug -AllowedRoot $projectPath -ExpectedLeaf "HardwareDebug"
[void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent ([System.IO.Path]::GetFullPath($LogFile))))

$buildStart = Get-Date
try {
    $exitCode = Invoke-E2StudioBuild `
        -Executable $e2StudioPath `
        -WorkspacePath $workspacePath `
        -ProjectPath $projectPath `
        -OutputLog $LogFile
} finally {
    foreach ($entry in $metadataSnapshot.GetEnumerator()) {
        [System.IO.File]::WriteAllBytes([string]$entry.Key, [byte[]]$entry.Value)
    }
}

if ($exitCode -ne 0) {
    throw "e2 studio RX671 boot-loader build failed with exit code $exitCode"
}

$artifacts = @(
    (Join-Path $hardwareDebug "$projectName.mot"),
    (Join-Path $hardwareDebug "$projectName.abs"),
    (Join-Path $hardwareDebug "$projectName.map")
)
foreach ($artifact in $artifacts) {
    if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) {
        throw "RX671 boot-loader build artifact is missing: $artifact"
    }
    if ((Get-Item -LiteralPath $artifact).LastWriteTime -lt $buildStart.AddSeconds(-2)) {
        throw "RX671 boot-loader build artifact is stale: $artifact"
    }
}

Write-Host "BUILD EK-RX671 BOOTLOADER SUCCESS"
Write-Host "  MOT: $($artifacts[0])"
Write-Host "  ABS: $($artifacts[1])"
Write-Host "  MAP: $($artifacts[2])"

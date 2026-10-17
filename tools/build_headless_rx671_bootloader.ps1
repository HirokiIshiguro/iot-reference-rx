param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\ai\codex\ws\e2ws_iot_ref_rx671_bootloader_2026_04_2",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx671_bootloader_e2studio_build.log"),
    [string]$SourceProvenanceFile = "",
    [string]$Python = 'python',
    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "rx_e2studio_cli.ps1")

$projectName = "boot_loader_rx671_ek"
$relativeProject = "Projects\boot_loader_rx671_ek\e2studio_ccrx"
$relativeSubmodule = "$relativeProject\lib\rx_bootloader"
$relativeSubmoduleGit = $relativeSubmodule -replace '\\', '/'
$expectedSubmoduleHead = $null
$dependencyEvidence = [ordered]@{}

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
    return Invoke-RxE2StudioBuild -Executable $Executable -WorkspacePath $WorkspacePath `
        -ProjectPaths @($ProjectPath) -BuildTargets @("$projectName/HardwareDebug") `
        -OutputLog $OutputLog -TimeoutSeconds $TimeoutSeconds `
        -ExpectedOutputs @("$ProjectPath/HardwareDebug/$projectName.mot", "$ProjectPath/HardwareDebug/$projectName.abs", "$ProjectPath/HardwareDebug/$projectName.map")
}

$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
Initialize-RxBuildDependencies -ProjectRoot $projectRootPath
Assert-RxCommonKernel -ProjectRoot $projectRootPath
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
if ($SourceProvenanceFile) {
    & $Python (Join-Path $PSScriptRoot 'idt_source_manifest.py') verify `
        --source $projectRootPath --target rx671-wifi --provenance $SourceProvenanceFile
    if ($LASTEXITCODE -ne 0) { throw 'RX671 boot-loader source-copy dependency verification failed.' }
    $provenance = Get-Content -LiteralPath $SourceProvenanceFile -Raw | ConvertFrom-Json
    $pin = $provenance.submodule_shas.PSObject.Properties[$relativeSubmoduleGit]
    if (-not $pin -or [string]$pin.Value -notmatch '^[0-9a-fA-F]{40}$') {
        throw 'RX671 boot-loader source-copy provenance has no fixed boot-loader pin.'
    }
    $expectedSubmoduleHead = ([string]$pin.Value).ToLowerInvariant()
    $dependencyEvidence = [ordered]@{
        verification = 'captured-source-dependency-files-and-pins'
        bootloader_path = $relativeSubmoduleGit
        bootloader_pin = $expectedSubmoduleHead
        provenance_sha256 = (Get-FileHash -LiteralPath $SourceProvenanceFile -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
else {
    $sourceTop = (& git -c "safe.directory=$projectRootPath" -C $projectRootPath rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($sourceTop) -ne $projectRootPath) {
        throw 'RX671 source Git root does not match the selected project root.'
    }
    $sourceHead = (& git -c "safe.directory=$projectRootPath" -C $projectRootPath rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the fixed RX671 source HEAD.' }
    $row = & git -c "safe.directory=$projectRootPath" -C $projectRootPath ls-tree HEAD -- $relativeSubmoduleGit
    if ($LASTEXITCODE -ne 0 -or $row -notmatch '^160000 commit ([0-9a-fA-F]{40})\t(.+)$' -or $Matches[2] -ne $relativeSubmoduleGit) {
        throw 'The selected RX671 source HEAD has no fixed boot-loader gitlink.'
    }
    $expectedSubmoduleHead = $Matches[1].ToLowerInvariant()
if (-not (Test-Path -LiteralPath (Join-Path $submodulePath ".git"))) {
    & git -c "safe.directory=$projectRootPath" -C $projectRootPath submodule update --init --recursive -- $relativeSubmoduleGit
    if ($LASTEXITCODE -ne 0) {
        throw "RX671 boot-loader submodule initialization failed"
    }
}
$actualSubmoduleRoot = (& git -c "safe.directory=$submodulePath" -C $submodulePath rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($actualSubmoduleRoot) -ne $submodulePath) {
    throw 'RX671 boot-loader dependency Git root is uninitialized or mismatched.'
}
$actualSubmoduleHead = (& git -c "safe.directory=$submodulePath" -C $submodulePath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualSubmoduleHead -ne $expectedSubmoduleHead) {
    throw "RX671 boot-loader submodule HEAD is '$actualSubmoduleHead'; expected '$expectedSubmoduleHead'"
}
    $dependencyEvidence = [ordered]@{
        verification = 'fixed-source-HEAD-gitlink'
        source_sha = $sourceHead
        bootloader_path = $relativeSubmoduleGit
        bootloader_pin = $expectedSubmoduleHead
        bootloader_head = $actualSubmoduleHead
    }
}

Remove-BuildDirectory `
    -Path $workspacePath `
    -AllowedRoot $workspaceRoot `
    -ExpectedLeaf "e2ws_iot_ref_rx671_bootloader_2026_04_2"
Remove-BuildDirectory -Path $hardwareDebug -AllowedRoot $projectPath -ExpectedLeaf "HardwareDebug"
[void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent ([System.IO.Path]::GetFullPath($LogFile))))
$dependencyEvidence | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ($LogFile + '.dependencies.json') -Encoding UTF8

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

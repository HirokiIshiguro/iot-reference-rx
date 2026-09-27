param(
    [string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\ai\codex\ws\rx72n-idt-transport-build",
    [string]$OutputDirectory = "",
    [string]$ProvenanceFile = "",
    [int]$E2StudioTimeoutSeconds = 900,
    [switch]$ValidateOnly
)

# IDT supplies Test/include/test_execution_config.h and test_param_config.h.
# Build exactly the selected transport suite with the unchanged production
# transport. Do not downgrade or rewrite the manifest to satisfy IDT versions.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$idtRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$idtProject = Join-Path $idtRoot "Projects\aws_ether_rx72n_envision_kit\e2studio_ccrx"
$idtWorkspace = [System.IO.Path]::GetFullPath($Workspace).TrimEnd('\')
$allowedWorkspaceRoot = 'C:\ai\codex\ws\'
if (-not $idtWorkspace.StartsWith($allowedWorkspaceRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $idtWorkspace.Equals($idtRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $idtRoot.StartsWith($idtWorkspace + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $idtWorkspace.StartsWith($idtRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "The disposable e2 studio workspace must be a separate directory below C:\ai\codex\ws."
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $idtRoot "artifacts\idt\build_transport"
}
$idtOutput = [System.IO.Path]::GetFullPath($OutputDirectory)

function Read-IdtGitOutput {
    param([string]$Directory, [string[]]$GitArguments)
    try {
        $gitOutput = & git -C $Directory @GitArguments 2>&1
        $gitExitCode = $LASTEXITCODE
    }
    catch {
        throw "Cannot read Git provenance from $Directory. Supply -ProvenanceFile for an IDT runtime source copy."
    }
    if ($gitExitCode -ne 0) {
        throw "Git provenance failed in $Directory (exit $gitExitCode). Supply -ProvenanceFile for an IDT runtime source copy."
    }
    return (($gitOutput | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

if ($ProvenanceFile) {
    try {
        $provenance = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $ProvenanceFile).Path) |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Cannot read -ProvenanceFile as a JSON object."
    }
}
else {
    # An uninitialized submodule can silently resolve its parent's repository.
    # Require both roots to match, then collect provenance before any mutation.
    $testLibraryRoot = Join-Path $idtRoot 'Test\FreeRTOS-Libraries-Integration-Tests'
    foreach ($repositoryRoot in @($idtRoot, $testLibraryRoot)) {
        $gitRoot = Read-IdtGitOutput $repositoryRoot @('rev-parse', '--show-toplevel')
        if ([string]::IsNullOrWhiteSpace($gitRoot) -or
            -not [System.IO.Path]::GetFullPath($gitRoot).TrimEnd('\').Equals(
                [System.IO.Path]::GetFullPath($repositoryRoot).TrimEnd('\'),
                [StringComparison]::OrdinalIgnoreCase)) {
            throw "Git provenance root mismatch in $repositoryRoot. Supply -ProvenanceFile for an IDT runtime source copy."
        }
    }
    $provenance = [pscustomobject]@{
        source_sha = Read-IdtGitOutput $idtRoot @('rev-parse', 'HEAD')
        test_library_sha = Read-IdtGitOutput $testLibraryRoot @('rev-parse', 'HEAD')
        source_tree_dirty = -not [string]::IsNullOrWhiteSpace(
            (Read-IdtGitOutput $idtRoot @('status', '--porcelain')))
    }
}
foreach ($field in @('source_sha', 'test_library_sha', 'source_tree_dirty')) {
    if ($null -eq $provenance -or $null -eq $provenance.PSObject.Properties[$field]) {
        throw "Missing provenance field: $field."
    }
}
foreach ($field in @('source_sha', 'test_library_sha')) {
    if ($provenance.$field -isnot [string] -or $provenance.$field -notmatch '\A[0-9a-fA-F]{40}\z') {
        throw "Invalid provenance field $field; expected exactly 40 hexadecimal characters."
    }
}
if ($provenance.source_tree_dirty -isnot [bool]) {
    throw "Invalid provenance field source_tree_dirty; expected a JSON boolean."
}
$sourceSha = $provenance.source_sha.ToLowerInvariant()
$testLibrarySha = $provenance.test_library_sha.ToLowerInvariant()
$sourceWasDirty = $provenance.source_tree_dirty

$executionPath = Join-Path $idtRoot "Test\include\test_execution_config.h"
$executionText = [System.IO.File]::ReadAllText($executionPath)
$testFlags = @{
    TRANSPORT_INTERFACE_TEST_ENABLED = 1
    DEVICE_ADVISOR_TEST_ENABLED = 0
    MQTT_TEST_ENABLED = 0
    CORE_PKCS11_TEST_ENABLED = 0
    OTA_PAL_TEST_ENABLED = 0
    OTA_E2E_TEST_ENABLED = 0
}
foreach ($flag in $testFlags.Keys) {
    $definitions = [regex]::Matches($executionText, "(?m)^\s*#\s*define\s+$flag\s+\(?\s*([01])\s*\)?\s*(?://[^\r\n]*)?$")
    if ($definitions.Count -ne 1 -or [int]$definitions[0].Groups[1].Value -ne $testFlags[$flag]) {
        throw "Transport-only build requires $flag=$($testFlags[$flag]) in Test/include/test_execution_config.h."
    }
}

# Link only these sources. Linking all of Test/ would compile the incompatible
# 202406 MQTT suite and Unity's own tests, and introduce duplicate entry points.
$testSources = [ordered]@{
    "rx72n_idt_transport.c" = "Test/ports/rx72n_idt_transport.c"
    "test_framework.c" = "Test/Common/test_framework.c"
    "transport_interface_test.c" = "Test/FreeRTOS-Libraries-Integration-Tests/src/transport_interface/transport_interface_test.c"
    "unity.c" = "Test/Unity/src/unity.c"
    "unity_fixture.c" = "Test/Unity/extras/fixture/src/unity_fixture.c"
    "unity_memory.c" = "Test/Unity/extras/memory/src/unity_memory.c"
}
$testIncludes = @(
    "Test/include",
    "Test/ports",
    "Test/FreeRTOS-Libraries-Integration-Tests/src/common",
    "Test/FreeRTOS-Libraries-Integration-Tests/src/transport_interface",
    "Test/Unity/src",
    "Test/Unity/extras/fixture/src",
    "Test/Unity/extras/memory/src"
)
foreach ($relativePath in @($testSources.Values) + $testIncludes) {
    if (-not (Test-Path -LiteralPath (Join-Path $idtRoot $relativePath))) {
        throw "Missing IDT build dependency: $relativePath"
    }
}

$projectPath = Join-Path $idtProject '.project'
$cprojectPath = Join-Path $idtProject '.cproject'
$originalProject = [System.IO.File]::ReadAllBytes($projectPath)
$originalCproject = [System.IO.File]::ReadAllBytes($cprojectPath)
$projectXml = New-Object System.Xml.XmlDocument
$projectXml.PreserveWhitespace = $true
$projectXml.Load($projectPath)
$cprojectXml = New-Object System.Xml.XmlDocument
$cprojectXml.PreserveWhitespace = $true
$cprojectXml.Load($cprojectPath)

function Add-OptionValue {
    param([System.Xml.XmlElement]$Option, [string]$Value)
    $entry = $Option.OwnerDocument.CreateElement('listOptionValue')
    $entry.SetAttribute('builtIn', 'false')
    $entry.SetAttribute('value', $Value)
    [void]$Option.AppendChild($entry)
}

$linkedResources = $projectXml.SelectSingleNode('/projectDescription/linkedResources')
$includeOption = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.include']")
$defineOption = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.define']")
$linkOption = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.noneLinkageOrderList']")
if (-not $linkedResources -or -not $includeOption -or -not $defineOption -or -not $linkOption) {
    throw "RX72N project metadata does not match the expected CCRX HardwareDebug layout."
}

foreach ($sourceName in $testSources.Keys) {
    if ($projectXml.SelectSingleNode("/projectDescription/linkedResources/link[name='$sourceName']")) {
        throw "IDT source is already linked; concurrent/pre-existing metadata mutation: $sourceName"
    }
    $link = $projectXml.CreateElement('link')
    foreach ($field in @('name', 'type', 'locationURI')) {
        $element = $projectXml.CreateElement($field)
        switch ($field) {
            'name' { $element.InnerText = $sourceName }
            'type' { $element.InnerText = '1' }
            'locationURI' { $element.InnerText = 'AWS_IOT_MCU_ROOT/' + $testSources[$sourceName] }
        }
        [void]$link.AppendChild($element)
    }
    [void]$linkedResources.AppendChild($link)
    # Link name must also match the physical basename: the Renesas plugin
    # regenerates linker options using the link, but the compiler uses the file.
    Add-OptionValue $linkOption ('".\' + [System.IO.Path]::GetFileNameWithoutExtension($testSources[$sourceName]) + '.obj"')
}
foreach ($include in $testIncludes) {
    Add-OptionValue $includeOption ('"' + (Join-Path $idtRoot $include) + '"')
}
Add-OptionValue $defineOption 'ENABLE_IDT_TRANSPORT_TEST=1'
Add-OptionValue $defineOption 'UNITY_INCLUDE_CONFIG_H'

# IDT copies source trees without usable Git worktree/submodule metadata. Limit
# filesystem enumeration to the two projects' generated and IDE-owned files.
$generatedFiles = @()
foreach ($snapshotProject in @($idtProject, (Join-Path $idtRoot 'Projects\boot_loader_rx72n_envision_kit\e2studio_ccrx'))) {
    foreach ($directory in @('.settings', 'src\smc_gen')) {
        $generatedDirectory = Join-Path $snapshotProject $directory
        if (Test-Path -LiteralPath $generatedDirectory -PathType Container) {
            $generatedFiles += @(Get-ChildItem -LiteralPath $generatedDirectory -File -Recurse -Force)
        }
    }
    $generatedFiles += @(Get-ChildItem -LiteralPath $snapshotProject -File -Force |
        Where-Object { $_.Extension -in @('.launch', '.scfg', '.rcpc') })
}
if ($ValidateOnly) {
    Write-Host "IDT transport metadata/provenance validated: $($testSources.Count) sources, $($generatedFiles.Count) snapshot files; no compiler or hardware action."
    return
}

New-Item -ItemType Directory -Force -Path $idtOutput | Out-Null
$buildLog = Join-Path $idtOutput 'build.log'
$generatedSnapshots = @{}
# Smart Configurator may rewrite these files. Preserve this copy's exact bytes.
foreach ($generatedFile in $generatedFiles) {
    $generatedSnapshots[$generatedFile.FullName] = [System.IO.File]::ReadAllBytes($generatedFile.FullName)
}
try {
    $projectXml.Save($projectPath)
    $cprojectXml.Save($cprojectPath)
    & (Join-Path $PSScriptRoot 'build_headless_rx72n.ps1') `
        -ProjectRoot $idtRoot -E2Studio $E2Studio -Workspace $idtWorkspace `
        -TlsBackend software -LogFile $buildLog `
        -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds

    $outputs = [ordered]@{}
    foreach ($extension in @('mot', 'abs', 'x')) {
        $source = Join-Path $idtProject "HardwareDebug\aws_ether_rx72n_envision_kit.$extension"
        $destination = Join-Path $idtOutput "rx72n_idt_transport.$extension"
        Copy-Item -LiteralPath $source -Destination $destination -Force
        $outputs[$extension] = @{
            path = $destination
            sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    # No configuration text or credential value belongs in this manifest.
    $evidence = [ordered]@{
        mode = 'idt-transport-only'
        suite = 'FullTransportInterfaceTLS'
        source_sha = $sourceSha
        source_tree_dirty = $sourceWasDirty
        test_library_sha = $testLibrarySha
        execution_config_sha256 = (Get-FileHash -LiteralPath $executionPath -Algorithm SHA256).Hash.ToLowerInvariant()
        parameter_config_sha256 = (Get-FileHash -LiteralPath (Join-Path $idtRoot 'Test/include/test_param_config.h') -Algorithm SHA256).Hash.ToLowerInvariant()
        outputs = $outputs
        qualification_status = 'not-established; individual transport validation only'
    }
    $evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $idtOutput 'build_manifest.json') -Encoding UTF8
    Write-Host "IDT transport build ready: $idtOutput"
}
finally {
    foreach ($generatedPath in $generatedSnapshots.Keys) {
        [System.IO.File]::WriteAllBytes($generatedPath, $generatedSnapshots[$generatedPath])
    }
    [System.IO.File]::WriteAllBytes($projectPath, $originalProject)
    [System.IO.File]::WriteAllBytes($cprojectPath, $originalCproject)
}

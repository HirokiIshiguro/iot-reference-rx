param(
    [string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent),
    [ValidateSet('rx72n-ethernet', 'rx65n-bg96', 'rx671-wifi')]
    [string]$Target = 'rx72n-ethernet',
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studioc.exe",
    [string]$Workspace = "",
    [string]$Python = 'python',
    [string]$OutputDirectory = "",
    [string]$ProvenanceFile = "",
    [string]$ValidationReportFile = "",
    [ValidateSet('Transport', 'DeviceAdvisor', 'OTAE2E', 'PKCS11', 'OTAPAL')]
    [string]$TestGroup = 'Transport',
    [int]$E2StudioTimeoutSeconds = 900,
    [switch]$ValidateOnly
)

# IDT supplies Test/include/test_execution_config.h and test_param_config.h.
# Build exactly the selected transport suite with the unchanged production
# transport. Do not downgrade or rewrite the manifest to satisfy IDT versions.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$idtRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$targetManifestPath = Join-Path $idtRoot 'tools/idt/targets.json'
$targetManifest = [IO.File]::ReadAllText($targetManifestPath) | ConvertFrom-Json
if ($targetManifest.schema_version -ne 1 -or $null -eq $targetManifest.targets.PSObject.Properties[$Target]) {
    throw "Missing/unsupported IDT target mapping: $Target"
}
$targetConfig = $targetManifest.targets.$Target
if ($targetConfig.id -ne $Target) { throw 'IDT target mapping identity mismatch.' }
$canonicalTarget = [ordered]@{}
foreach ($property in ($targetConfig.PSObject.Properties | Sort-Object Name)) {
    $canonicalTarget[$property.Name] = $property.Value
}
$canonicalTargetJson = $canonicalTarget | ConvertTo-Json -Compress -Depth 8
$sha256 = [Security.Cryptography.SHA256]::Create()
try {
    $targetSha256 = ([BitConverter]::ToString($sha256.ComputeHash(
        [Text.Encoding]::UTF8.GetBytes($canonicalTargetJson)))).Replace('-', '').ToLowerInvariant()
}
finally { $sha256.Dispose() }
$idtProject = Join-Path $idtRoot $targetConfig.application_project
$idtProjectName = Split-Path (Split-Path $idtProject -Parent) -Leaf
$idtBootProject = Join-Path $idtRoot $targetConfig.bootloader_project
$idtBootProjectName = Split-Path (Split-Path $idtBootProject -Parent) -Leaf
foreach ($project in @($idtProject, $idtBootProject)) {
    if (-not (Test-Path -LiteralPath (Join-Path $project '.project'))) {
        throw "IDT target project not found: $project"
    }
}
if (-not $Workspace) { $Workspace = Join-Path ([IO.Path]::GetTempPath()) "rx-idt-$Target-$TestGroup" }
$idtWorkspace = [System.IO.Path]::GetFullPath($Workspace).TrimEnd('\')
$allowedWorkspaceRoots = @('C:\ai\codex\ws\', [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\')
$workspaceAllowed = @($allowedWorkspaceRoots | Where-Object {
    $idtWorkspace.StartsWith($_, [StringComparison]::OrdinalIgnoreCase)
}).Count -gt 0
if (-not $workspaceAllowed -or
    $idtWorkspace.Equals($idtRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $idtRoot.StartsWith($idtWorkspace + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $idtWorkspace.StartsWith($idtRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The disposable e2 studio workspace must be separate from the source tree and below C:\ai\codex\ws or the current temporary directory.'
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $idtRoot "artifacts\idt\build_transport"
}
$idtOutput = [System.IO.Path]::GetFullPath($OutputDirectory)

function Read-IdtGitOutput {
    param([string]$Directory, [string[]]$GitArguments)
    try {
        $gitOutput = & git --no-optional-locks -c "safe.directory=$Directory" -C $Directory @GitArguments 2>&1
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

# Capture at the original initialized Git tree. Runtime copies must match the
# captured file list and bytes before any build helper can patch a dependency.
$dependencyTool = Join-Path $PSScriptRoot 'idt_source_manifest.py'
if ($ProvenanceFile) {
    & $Python $dependencyTool verify --source $idtRoot --target $Target --provenance $ProvenanceFile
    if ($LASTEXITCODE -ne 0) { throw 'IDT dependency source-copy verification failed.' }
}
else {
    $capturedJson = & $Python $dependencyTool capture --source $idtRoot --target $Target
    if ($LASTEXITCODE -ne 0) { throw 'IDT dependency Git pin/hash capture failed.' }
    $captured = ($capturedJson -join "`n") | ConvertFrom-Json
    foreach ($property in $captured.PSObject.Properties) {
        $provenance | Add-Member -NotePropertyName $property.Name -NotePropertyValue $property.Value
    }
}
if ($testLibrarySha -ne $provenance.submodule_shas.'Test/FreeRTOS-Libraries-Integration-Tests') {
    throw 'Test library provenance differs from the captured dependency pin.'
}
$stackJson = & $Python (Join-Path $PSScriptRoot 'idt/ota_support.py') stack-metadata $idtRoot --target $Target
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify the selected production MQTT/LTS stack metadata.' }
$productionStack = ($stackJson -join "`n") | ConvertFrom-Json
foreach ($binding in @(@('target_id', $Target), @('target_sha256', $targetSha256))) {
    $name, $value = $binding
    if ($null -ne $provenance.PSObject.Properties[$name] -and $provenance.$name -ne $value) {
        throw "Source provenance target binding differs: $name"
    }
}

$executionPath = Join-Path $idtRoot "Test\include\test_execution_config.h"
$executionText = [System.IO.File]::ReadAllText($executionPath)
$testFlags = @{
    TRANSPORT_INTERFACE_TEST_ENABLED = 0
    DEVICE_ADVISOR_TEST_ENABLED = 0
    MQTT_TEST_ENABLED = 0
    CORE_PKCS11_TEST_ENABLED = 0
    OTA_PAL_TEST_ENABLED = 0
    OTA_E2E_TEST_ENABLED = 0
}
switch ($TestGroup) {
    'Transport' { $testFlags.TRANSPORT_INTERFACE_TEST_ENABLED = 1; $suiteName = 'FullTransportInterfaceTLS' }
    'DeviceAdvisor' { $testFlags.DEVICE_ADVISOR_TEST_ENABLED = 1; $suiteName = 'FullCloudIoT' }
    'OTAE2E' { $testFlags.OTA_E2E_TEST_ENABLED = 1; $suiteName = 'OTADataplaneMQTT' }
    'PKCS11' { $testFlags.CORE_PKCS11_TEST_ENABLED = 1; $suiteName = 'FullPKCS11_Core' }
    'OTAPAL' { $testFlags.OTA_PAL_TEST_ENABLED = 1; $suiteName = 'OTACore' }
}
foreach ($flag in $testFlags.Keys) {
    $definitions = [regex]::Matches($executionText, "(?m)^\s*#\s*define\s+$flag\s+\(?\s*([01])\s*\)?\s*(?://[^\r\n]*)?$")
    if ($definitions.Count -ne 1 -or [int]$definitions[0].Groups[1].Value -ne $testFlags[$flag]) {
        throw "$TestGroup build requires $flag=$($testFlags[$flag]) in Test/include/test_execution_config.h."
    }
}

# Link only these sources. Linking all of Test/ would compile the incompatible
# 202406 MQTT suite and Unity's own tests, and introduce duplicate entry points.
$testSources = [ordered]@{
    "rx72n_idt_platform.c" = "Test/ports/rx72n_idt_platform.c"
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
if ($TestGroup -in @('DeviceAdvisor', 'OTAE2E')) {
    $testSources = [ordered]@{ 'rx72n_idt_cloud.c' = 'Test/ports/rx72n_idt_cloud.c' }
    $testIncludes = @('Test/include', 'Test/ports')
}
elseif ($TestGroup -eq 'PKCS11') {
    $testSources.Remove('rx72n_idt_transport.c')
    $testSources.Remove('transport_interface_test.c')
    $testSources['rx72n_idt_pkcs11.c'] = 'Test/ports/rx72n_idt_pkcs11.c'
    $testSources['core_pkcs11_test.c'] = 'Test/FreeRTOS-Libraries-Integration-Tests/src/pkcs11/core_pkcs11_test.c'
    # The existing production provisioning implementation exports the helpers
    # declared by this header. Do not link a duplicate upstream implementation.
    $testIncludes += @('Test/FreeRTOS-Libraries-Integration-Tests/src/pkcs11',
        'Test/FreeRTOS-Libraries-Integration-Tests/src/pkcs11/dev_mode_key_provisioning')
    $parameterText = [System.IO.File]::ReadAllText((Join-Path $idtRoot 'Test/include/test_param_config.h'))
    $capabilities = @{
        PKCS11_TEST_RSA_KEY_SUPPORT = 0
        PKCS11_TEST_EC_KEY_SUPPORT = 1
        PKCS11_TEST_IMPORT_PRIVATE_KEY_SUPPORT = 1
        PKCS11_TEST_GENERATE_KEYPAIR_SUPPORT = 0
        PKCS11_TEST_PREPROVISIONED_SUPPORT = 0
        PKCS11_TEST_JITP_CODEVERIFY_ROOT_CERT_SUPPORTED = 0
    }
    foreach ($capability in $capabilities.Keys) {
        $definitions = [regex]::Matches($parameterText, "(?m)^\s*#\s*define\s+$capability\s+\(?\s*([01])\s*\)?\s*$")
        if ($definitions.Count -ne 1 -or [int]$definitions[0].Groups[1].Value -ne $capabilities[$capability]) {
            throw "PKCS11 EC/import profile requires $capability=$($capabilities[$capability])."
        }
    }
}
elseif ($TestGroup -eq 'OTAPAL') {
    $testSources.Remove('rx72n_idt_transport.c')
    $testSources.Remove('transport_interface_test.c')
    $testSources['rx72n_idt_otapal.c'] = 'Test/ports/rx72n_idt_otapal.c'
    $testSources['ota_pal_test.c'] = 'Test/Custom/ota/ota_pal_test.c'
    $testIncludes += @('Test/Custom/ota')
    $parameterText = [System.IO.File]::ReadAllText((Join-Path $idtRoot 'Test/include/test_param_config.h'))
    if ($parameterText -notmatch '(?m)^\s*#define\s+OTA_PAL_USE_FILE_SYSTEM\s+\(?\s*0\s*\)?\s*$' -or
        $parameterText -notmatch '(?m)^\s*#define\s+OTA_PAL_TEST_CERT_TYPE\s+\(?\s*(OTA_ECDSA_SHA256|3)\s*\)?\s*$') {
        throw 'OTAPAL requires the direct-flash/ECDSA-SHA256 test profile.'
    }
}
$appVersion = [ordered]@{}
$otaImageId = $null
$otaSignerHeaderHash = $null
if ($TestGroup -eq 'OTAE2E') {
    $otaSignerHeader = Join-Path $idtRoot 'Test/include/idt_ota_signer.h'
    if (-not (Test-Path -LiteralPath $otaSignerHeader)) {
        throw 'OTAE2E requires the runtime-only Test/include/idt_ota_signer.h.'
    }
    $imageIdMatch = [regex]::Matches([IO.File]::ReadAllText($otaSignerHeader), '(?m)^#define IDT_OTA_IMAGE_ID "([a-f0-9]{32})"\r?$')
    if ($imageIdMatch.Count -ne 1) { throw 'OTAE2E requires one generated image identity.' }
    $otaImageId = $imageIdMatch[0].Groups[1].Value
    $otaSignerHeaderHash = (Get-FileHash -LiteralPath $otaSignerHeader -Algorithm SHA256).Hash.ToLowerInvariant()
    $parameterText = [System.IO.File]::ReadAllText((Join-Path $idtRoot 'Test/include/test_param_config.h'))
    foreach ($part in @('MAJOR', 'MINOR', 'BUILD')) {
        $versionMatch = [regex]::Matches($parameterText, "(?m)^\s*#\s*define\s+OTA_APP_VERSION_$part\s+\(?\s*([0-9]+)[uUlL]*\s*\)?\s*$")
        if ($versionMatch.Count -ne 1) { throw "Missing numeric OTA_APP_VERSION_$part." }
        $appVersion[$part] = [uint32]$versionMatch[0].Groups[1].Value
    }
    if ($appVersion.MAJOR -gt 255 -or $appVersion.MINOR -gt 255 -or $appVersion.BUILD -gt 65535) {
        throw 'OTA version exceeds the production 8/8/16-bit application version fields.'
    }
}
if ($Target -ne 'rx72n-ethernet' -and $TestGroup -in @('Transport', 'DeviceAdvisor', 'OTAE2E')) {
    $testSources['rx_idt_network.c'] = 'Test/ports/rx_idt_network.c'
    $networkConfig = Join-Path $idtRoot 'Test/include/idt_network_config.h'
    if (-not (Test-Path -LiteralPath $networkConfig -PathType Leaf)) {
        throw "$Target network groups require the runtime-only Test/include/idt_network_config.h."
    }
}
foreach ($relativePath in @($testSources.Values) + $testIncludes) {
    if (-not (Test-Path -LiteralPath (Join-Path $idtRoot $relativePath))) {
        throw "Missing IDT build dependency: $relativePath"
    }
}

$projectPath = Join-Path $idtProject '.project'
$cprojectPath = Join-Path $idtProject '.cproject'
$originalProject = [System.IO.File]::ReadAllBytes($projectPath)
$originalCproject = [System.IO.File]::ReadAllBytes($cprojectPath)
$profileFiles = $null
$profileName = 'production-dual-bank'
if ($Target -eq 'rx671-wifi') {
    $version = $(if ($TestGroup -eq 'OTAE2E') { "$($appVersion.MAJOR).$($appVersion.MINOR).$($appVersion.BUILD)" } else { '0.1.0' })
    $profileJson = & $Python (Join-Path $PSScriptRoot 'idt_rx671_build_profile.py') `
        --project $idtProject --group $TestGroup --version $version
    if ($LASTEXITCODE -ne 0) { throw 'Cannot construct the reviewed RX671 dual-bank IDT profile.' }
    $profile = ($profileJson -join "`n") | ConvertFrom-Json
    $profileFiles = $profile.files
    $profileName = $profile.profile
}
$demoConfigPath = Join-Path $idtProject 'src/frtos_config/demo_config.h'
$originalDemoConfig = [System.IO.File]::ReadAllBytes($demoConfigPath)
$demoConfigText = [System.IO.File]::ReadAllText($demoConfigPath)
$projectXml = New-Object System.Xml.XmlDocument
$projectXml.PreserveWhitespace = $true
$projectXml.Load($projectPath)
$cprojectXml = New-Object System.Xml.XmlDocument
$cprojectXml.PreserveWhitespace = $true
if ($null -ne $profileFiles) { $cprojectXml.LoadXml($profileFiles.'.cproject') }
else { $cprojectXml.Load($cprojectPath) }

function Add-OptionValue {
    param([System.Xml.XmlElement]$Option, [string]$Value)
    if ($Option.GetAttribute('superClass') -eq 'com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.userBefore') {
        $Value = '-define=' + $Value
    }
    $entry = $Option.OwnerDocument.CreateElement('listOptionValue')
    $entry.SetAttribute('builtIn', 'false')
    $entry.SetAttribute('value', $Value)
    [void]$Option.AppendChild($entry)
}

function Get-IdtLinkerOptions {
    param([System.Xml.XmlDocument]$Metadata)
    $section = $Metadata.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.linkerSection']")
    $mapping = $Metadata.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.rom']")
    if (-not $section -or -not $mapping) { throw 'Missing reviewed CCRX linker settings.' }
    $rom = @($mapping.SelectNodes('listOptionValue') | ForEach-Object { $_.GetAttribute('value') } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ','
    $options = @(('-start=' + $section.GetAttribute('value')), ('-rom=' + $rom))
    return $options
}

$linkedResources = $projectXml.SelectSingleNode('/projectDescription/linkedResources')
$repositoryVariables = @($projectXml.SelectNodes('/projectDescription/variableList/variable') |
    Where-Object { $_.SelectSingleNode('value').InnerText -eq '$%7BPARENT-3-PROJECT_LOC%7D' })
if ($repositoryVariables.Count -ne 1) { throw 'Expected one project variable for the repository root.' }
$repositoryVariable = $repositoryVariables[0].SelectSingleNode('name').InnerText
$resolvedRepositoryRoot = [IO.Path]::GetFullPath((Join-Path $idtProject '../../..')).TrimEnd('\')
if (-not $resolvedRepositoryRoot.Equals($idtRoot.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Selected project repository-root variable does not resolve to the supplied source tree.'
}
$includeOption = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.include']")
$defineOption = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.define']")
if (-not $defineOption) {
    $defineOption = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.userBefore']")
}
$linkOption = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.noneLinkageOrderList']")
if (-not $linkedResources -or -not $includeOption -or -not $defineOption -or -not $linkOption) {
    throw "$Target project metadata does not match the expected CCRX HardwareDebug layout."
}
$targetDefine = 'IDT_TARGET_' + $Target.ToUpperInvariant().Replace('-', '_') + '=1'
if ($cprojectXml.OuterXml -match 'IDT_TARGET_(RX72N_ETHERNET|RX65N_BG96|RX671_WIFI)') {
    throw 'IDT target selector is already present; concurrent/pre-existing metadata mutation.'
}
Add-OptionValue $defineOption $targetDefine
if ($Target -eq 'rx671-wifi') {
    Add-OptionValue $defineOption 'RX671_OTA_PROVISIONER_ENABLE=0'
    Add-OptionValue $defineOption 'RX671_FLEET_PROVISIONING_ENABLE=0'
}
$linkerSection = $cprojectXml.SelectSingleNode("//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.linkerSection']")
if (-not $linkerSection) { throw 'Missing target linker flash layout.' }
$effectiveLinkerSection = $linkerSection.GetAttribute('value')
$bspRelative = 'src/smc_gen/r_config/r_bsp_config.h'
$fwupRelative = $(if ($Target -eq 'rx671-wifi') { 'src/frtos_config/r_fwup_config.h' } else { 'src/smc_gen/r_config/r_fwup_config.h' })
$bspText = $(if ($null -ne $profileFiles) { $profileFiles.$bspRelative } else { [IO.File]::ReadAllText((Join-Path $idtProject $bspRelative)) })
$fwupText = $(if ($null -ne $profileFiles) { $profileFiles.$fwupRelative } else { [IO.File]::ReadAllText((Join-Path $idtProject $fwupRelative)) })
function Get-IdtNumericDefine {
    param([string]$Text, [string]$Name)
    $definitions = [regex]::Matches($Text, "(?m)^\s*#\s*define\s+$Name\s+\(?\s*(0x[0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*\)?\s*(?:/\*[^\r\n]*\*/\s*)?$")
    if ($definitions.Count -ne 1) { throw "Expected one numeric target definition: $Name" }
    $value = $definitions[0].Groups[1].Value
    if ($value.StartsWith('0x', [StringComparison]::OrdinalIgnoreCase)) { return [Convert]::ToUInt32($value.Substring(2), 16) }
    return [uint32]$value
}
$expectedAreaSize = switch ($Target) {
    'rx72n-ethernet' { 0x1C0000 }
    'rx65n-bg96' { 0xF0000 }
    'rx671-wifi' { 0xC0000 }
}
$fwupAreaSize = Get-IdtNumericDefine $fwupText 'FWUP_CFG_AREA_SIZE'
if ((Get-IdtNumericDefine $bspText 'BSP_CFG_CODE_FLASH_BANK_MODE') -ne 0 -or
    (Get-IdtNumericDefine $fwupText 'FWUP_CFG_UPDATE_MODE') -ne 0 -or
    (Get-IdtNumericDefine $fwupText 'FWUP_CFG_FUNCTION_MODE') -ne 1 -or
    (Get-IdtNumericDefine $fwupText 'FWUP_CFG_SIGNATURE_VERIFICATION') -ne 0 -or
    $fwupAreaSize -ne $expectedAreaSize) {
    throw "$Target requires the reviewed dual-bank/ECDSA FWUP profile with area size $expectedAreaSize."
}

foreach ($sourceName in $testSources.Keys) {
    if ($projectXml.SelectSingleNode("/projectDescription/linkedResources/link[name='$sourceName']")) {
        throw "IDT source is already linked; concurrent/pre-existing metadata mutation: $sourceName"
    }
    $linkedSource = [IO.Path]::GetFullPath((Join-Path $resolvedRepositoryRoot $testSources[$sourceName]))
    if (-not $linkedSource.StartsWith($idtRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $linkedSource -PathType Leaf)) {
        throw "IDT source link does not resolve inside the selected source tree: $sourceName"
    }
    $link = $projectXml.CreateElement('link')
    foreach ($field in @('name', 'type', 'locationURI')) {
        $element = $projectXml.CreateElement($field)
        switch ($field) {
            'name' { $element.InnerText = $sourceName }
            'type' { $element.InnerText = '1' }
            'locationURI' { $element.InnerText = $repositoryVariable + '/' + $testSources[$sourceName] }
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
if ($TestGroup -in @('Transport', 'PKCS11', 'OTAPAL')) {
    if ($TestGroup -eq 'Transport') { Add-OptionValue $defineOption 'ENABLE_IDT_TRANSPORT_TEST=1' }
    elseif ($TestGroup -eq 'PKCS11') { Add-OptionValue $defineOption 'ENABLE_IDT_PKCS11_TEST=1' }
    else { Add-OptionValue $defineOption 'ENABLE_IDT_OTAPAL_TEST=1' }
    Add-OptionValue $defineOption 'UNITY_INCLUDE_CONFIG_H'
}
else {
    Add-OptionValue $defineOption 'ENABLE_IDT_CLOUD_DEMO=1'
    # Keep the production pub/sub tasks active across Device Advisor cases.
    # Far beyond the bounded IDT run, while keeping the demo's signed log cast safe.
    Add-OptionValue $defineOption 'mqttexamplePUBLISH_COUNT=1000000U'
    $demoFlags = @{
        ENABLE_FLEET_PROVISIONING_DEMO = 0
        ENABLE_MULTI_TLS_DEMO = 0
        ENABLE_OTA_UPDATE_DEMO = $(if ($TestGroup -eq 'OTAE2E') { 1 } else { 0 })
    }
    foreach ($flag in $demoFlags.Keys) {
        # RX671 maps these flags to its production runtime selectors; its
        # reviewed profile supplies the selectors above. BG96 has no multi-TLS.
        if ($Target -eq 'rx671-wifi' -or ($Target -eq 'rx65n-bg96' -and $flag -eq 'ENABLE_MULTI_TLS_DEMO')) {
            continue
        }
        $pattern = "(?m)^\s*#define\s+$flag\s+\([01]\)\s*$"
        if ([regex]::Matches($demoConfigText, $pattern).Count -ne 1) {
            throw "Expected one demo config definition of $flag."
        }
        $demoConfigText = [regex]::Replace($demoConfigText, $pattern, "#define $flag ($($demoFlags[$flag]))")
    }
    foreach ($part in $appVersion.Keys) {
        if ($Target -ne 'rx671-wifi') { Add-OptionValue $defineOption "APP_VERSION_$part=$($appVersion[$part])" }
    }
}
$appLinkerOverrides = Get-IdtLinkerOptions $cprojectXml
$bootCprojectPath = Join-Path $idtBootProject '.cproject'
$originalBootCproject = [IO.File]::ReadAllBytes($bootCprojectPath)
$bootProjectPath = Join-Path $idtBootProject '.project'
$originalBootProject = [IO.File]::ReadAllBytes($bootProjectPath)
$bootCprojectXml = [Xml.XmlDocument]::new()
$bootCprojectXml.PreserveWhitespace = $true
$bootCprojectXml.Load($bootCprojectPath)
$bootLinkerOverrides = Get-IdtLinkerOptions $bootCprojectXml

# IDT copies source trees without usable Git worktree/submodule metadata. Limit
# filesystem enumeration to the two projects' generated and IDE-owned files.
$generatedFiles = @()
foreach ($snapshotProject in @($idtProject, $idtBootProject)) {
    foreach ($directory in @('.settings', 'src\smc_gen', 'src\frtos_skeleton', 'src\frtos_startup')) {
        $generatedDirectory = Join-Path $snapshotProject $directory
        if (Test-Path -LiteralPath $generatedDirectory -PathType Container) {
            $generatedFiles += @(Get-ChildItem -LiteralPath $generatedDirectory -File -Recurse -Force)
        }
    }
    $generatedFiles += @(Get-ChildItem -LiteralPath $snapshotProject -File -Force |
        Where-Object { $_.Extension -in @('.launch', '.scfg', '.rcpc') })
}
if ($ValidateOnly) {
    if ($ValidationReportFile) {
        $sourceLinks = [ordered]@{}
        foreach ($sourceName in $testSources.Keys) {
            $sourceLinks[$sourceName] = [ordered]@{
                location_uri = $projectXml.SelectSingleNode("/projectDescription/linkedResources/link[name='$sourceName']/locationURI").InnerText
                resolved_path = [IO.Path]::GetFullPath((Join-Path $resolvedRepositoryRoot $testSources[$sourceName]))
            }
        }
        [ordered]@{ target_id=$Target; target_sha256=$targetSha256; group=$TestGroup;
                    repository_variable=$repositoryVariable; source_links=$sourceLinks;
                    qualification='not-established'; compiler_invoked=$false } |
            ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ValidationReportFile -Encoding UTF8
    }
    Write-Host "IDT $Target $TestGroup metadata/provenance validated: $($testSources.Count) sources, profile $profileName; no compiler or hardware action."
    return
}

New-Item -ItemType Directory -Force -Path $idtOutput | Out-Null
$dependencyProvenanceFile = $ProvenanceFile
if (-not $dependencyProvenanceFile) {
    $dependencyProvenanceFile = Join-Path $idtOutput 'source_dependency_provenance.json'
    $provenance | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $dependencyProvenanceFile -Encoding UTF8
}
$buildLog = Join-Path $idtOutput 'build.log'
$generatedSnapshots = @{}
# Smart Configurator may rewrite these files. Preserve this copy's exact bytes.
foreach ($generatedFile in $generatedFiles) {
    $generatedSnapshots[$generatedFile.FullName] = [System.IO.File]::ReadAllBytes($generatedFile.FullName)
}
if ($null -ne $profileFiles) {
    foreach ($property in $profileFiles.PSObject.Properties) {
        $profilePath = Join-Path $idtProject $property.Name
        $generatedSnapshots[$profilePath] = [IO.File]::ReadAllBytes($profilePath)
    }
}
try {
    if ($null -ne $profileFiles) {
        foreach ($property in $profileFiles.PSObject.Properties) {
            [IO.File]::WriteAllText((Join-Path $idtProject $property.Name), $property.Value, [Text.UTF8Encoding]::new($false))
        }
    }
    $projectXml.Save($projectPath)
    $cprojectXml.Save($cprojectPath)
    $bootCprojectXml.Save($bootCprojectPath)
    foreach ($project in @($idtProject, $idtBootProject)) {
        $options = $(if ($project -eq $idtProject) { $appLinkerOverrides } else { $bootLinkerOverrides })
        foreach ($rcpc in @(Get-ChildItem -LiteralPath $project -File -Force -Filter '*.rcpc')) {
            $rcpcXml = [Xml.XmlDocument]::new()
            $rcpcXml.PreserveWhitespace = $true
            $rcpcXml.Load($rcpc.FullName)
            $linkOptions = $rcpcXml.SelectSingleNode("//BuildMode[@Name='HardwareDebug']/LinkOptions")
            if (-not $linkOptions) { throw 'RX IDT RCPC is missing HardwareDebug linker options.' }
            foreach ($entry in @($linkOptions.SelectNodes('Option'))) {
                if ($entry.InnerText -match '^-(start|rom)=') { [void]$linkOptions.RemoveChild($entry) }
            }
            foreach ($option in $options) {
                $entry = $rcpcXml.CreateElement('Option')
                $entry.InnerText = $option
                [void]$linkOptions.AppendChild($entry)
            }
            $rcpcXml.Save($rcpc.FullName)
        }
    }
    if ($TestGroup -in @('DeviceAdvisor', 'OTAE2E')) {
        [System.IO.File]::WriteAllText($demoConfigPath, $demoConfigText, [System.Text.UTF8Encoding]::new($false))
    }
    if ($Target -eq 'rx72n-ethernet') {
        & (Join-Path $PSScriptRoot 'build_headless_rx72n.ps1') `
            -ProjectRoot $idtRoot -E2Studio $E2Studio -Workspace $idtWorkspace `
            -TlsBackend software -LogFile $buildLog `
            -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds
    }
    elseif ($Target -eq 'rx65n-bg96') {
        # The production BG96 helper otherwise reuses existing makefiles and
        # misses this run's added sources/defines. Regenerate them every run.
        foreach ($project in @($idtProject, $idtBootProject)) {
            $buildDirectory = [IO.Path]::GetFullPath((Join-Path $project 'HardwareDebug'))
            if (-not $buildDirectory.StartsWith($idtRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Generated build directory is outside the source tree.'
            }
            if (Test-Path -LiteralPath $buildDirectory) { Remove-Item -LiteralPath $buildDirectory -Recurse -Force }
        }
        & (Join-Path $PSScriptRoot 'build_headless_rx65n_bg96.ps1') `
            -ProjectRoot $idtRoot -E2Studio $E2Studio -Workspace $idtWorkspace `
            -TlsBackend software -RequireTlsVersion '' -LogFile $buildLog `
            -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds -PreserveLinkerLayout
    }
    else {
        & (Join-Path $PSScriptRoot 'build_headless_rx671_bootloader.ps1') `
            -ProjectRoot $idtRoot -E2Studio $E2Studio -Workspace (Join-Path $idtWorkspace 'e2ws_iot_ref_rx671_bootloader_2026_04_2') `
            -LogFile (Join-Path $idtOutput 'bootloader_build.log') -TimeoutSeconds $E2StudioTimeoutSeconds `
            -SourceProvenanceFile $dependencyProvenanceFile -Python $Python
        $rx671OtaVersionArguments = @{}
        if ($TestGroup -eq 'OTAE2E') {
            # Bind the helper's compiled defines and MOT marker expectation to
            # the same canonical version already selected for the IDT profile.
            $rx671OtaVersionArguments.OtaImageVersion = $version
        }
        & (Join-Path $PSScriptRoot 'build_headless_rx671_wifi.ps1') `
            -ProjectRoot $idtRoot -E2Studio $E2Studio -Workspace $idtWorkspace `
            -UseKvsJoinConfig -SkipAwsIotConfig -LogFile $buildLog `
            -SdioRunClockDiv SDHI_DIV_8 -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds `
            -SourceProvenanceFile $dependencyProvenanceFile -Python $Python @rx671OtaVersionArguments
    }

    $outputs = [ordered]@{}
    foreach ($extension in @('mot', 'abs', 'x', 'map')) {
        $source = Join-Path $idtProject "HardwareDebug\$idtProjectName.$extension"
        if (-not (Test-Path -LiteralPath $source) -and $extension -in @('x', 'map')) { continue }
        $destination = Join-Path $idtOutput "$($targetConfig.artifact_basename).$extension"
        Copy-Item -LiteralPath $source -Destination $destination -Force
        $outputs[$extension] = @{
            path = $destination
            sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $bootloaderSource = Join-Path $idtBootProject "HardwareDebug\$idtBootProjectName.mot"
    $bootloaderDestination = Join-Path $idtOutput 'bootloader.mot'
    Copy-Item -LiteralPath $bootloaderSource -Destination $bootloaderDestination -Force
    $outputs['bootloader'] = @{
        path = $bootloaderDestination
        sha256 = (Get-FileHash -LiteralPath $bootloaderDestination -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    # No configuration text or credential value belongs in this manifest.
    $evidence = [ordered]@{
        target_id = $Target
        target_sha256 = $targetSha256
        board = $targetConfig.board
        connectivity = $targetConfig.connectivity
        application_project = $targetConfig.application_project
        bootloader_project = $targetConfig.bootloader_project
        flash_layout = [ordered]@{
            profile = $profileName
            linker_start = $effectiveLinkerSection
            bsp_code_flash_bank_mode = 0
            fwup_area_size = $fwupAreaSize
        }
        mode = $(if ($TestGroup -eq 'Transport') { 'idt-transport-only' } else { "idt-$($TestGroup.ToLowerInvariant())" })
        suite = $suiteName
        application_version = $appVersion
        image_id = $otaImageId
        signer_header_sha256 = $otaSignerHeaderHash
        coverage = $(if ($TestGroup -eq 'OTAPAL') {
            [ordered]@{
                nominal_cases = 15
                assertion_capable_cases = 14
                not_applicable_cases = 1
                not_applicable_test = 'otaPal_CloseFile_NonexistingCodeSignerCertificate'
                required_end_state = 'reset command success and fresh UART quiet; reflash/reprovision before reuse'
            }
        } else { $null })
        source_sha = $sourceSha
        source_tree_dirty = $sourceWasDirty
        test_library_sha = $testLibrarySha
        dependency_manifest_schema_version = $provenance.dependency_manifest_schema_version
        dependency_target_id = $provenance.dependency_target_id
        submodule_shas = $provenance.submodule_shas
        dependency_file_count = @($provenance.dependency_files_sha256.PSObject.Properties).Count
        production_stack = $productionStack
        bootloader_policy_sha256 = $(if ($Target -eq 'rx671-wifi') {
            @{
                'rx_bootloader_config.h' = (Get-FileHash -LiteralPath (Join-Path $idtBootProject 'src/rx_bootloader_config.h') -Algorithm SHA256).Hash.ToLowerInvariant()
                'rx671.h' = (Get-FileHash -LiteralPath (Join-Path $idtBootProject 'src/rx671.h') -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        } else { $null })
        execution_config_sha256 = (Get-FileHash -LiteralPath $executionPath -Algorithm SHA256).Hash.ToLowerInvariant()
        parameter_config_sha256 = (Get-FileHash -LiteralPath (Join-Path $idtRoot 'Test/include/test_param_config.h') -Algorithm SHA256).Hash.ToLowerInvariant()
        outputs = $outputs
        qualification_status = 'not-established; selected individual group only'
    }
    $evidence | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $idtOutput 'build_manifest.json') -Encoding UTF8
    Write-Host "IDT $TestGroup build ready: $idtOutput"
}
finally {
    foreach ($project in @($idtProject, $idtBootProject)) {
        foreach ($rcpc in @(Get-ChildItem -LiteralPath $project -File -Force -Filter '*.rcpc')) {
            if (-not $generatedSnapshots.ContainsKey($rcpc.FullName)) { Remove-Item -LiteralPath $rcpc.FullName -Force }
        }
    }
    foreach ($generatedPath in $generatedSnapshots.Keys) {
        [System.IO.File]::WriteAllBytes($generatedPath, $generatedSnapshots[$generatedPath])
    }
    [System.IO.File]::WriteAllBytes($projectPath, $originalProject)
    [System.IO.File]::WriteAllBytes($cprojectPath, $originalCproject)
    [System.IO.File]::WriteAllBytes($bootCprojectPath, $originalBootCproject)
    [System.IO.File]::WriteAllBytes($bootProjectPath, $originalBootProject)
    [System.IO.File]::WriteAllBytes($demoConfigPath, $originalDemoConfig)
}

param(
    [string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\ai\codex\ws\rx72n-idt-transport-build",
    [string]$OutputDirectory = "",
    [string]$ProvenanceFile = "",
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
if ($TestGroup -eq 'OTAE2E') {
    if (-not (Test-Path -LiteralPath (Join-Path $idtRoot 'Test/include/idt_ota_signer.h'))) {
        throw 'OTAE2E requires the runtime-only Test/include/idt_ota_signer.h.'
    }
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
foreach ($relativePath in @($testSources.Values) + $testIncludes) {
    if (-not (Test-Path -LiteralPath (Join-Path $idtRoot $relativePath))) {
        throw "Missing IDT build dependency: $relativePath"
    }
}

$projectPath = Join-Path $idtProject '.project'
$cprojectPath = Join-Path $idtProject '.cproject'
$originalProject = [System.IO.File]::ReadAllBytes($projectPath)
$originalCproject = [System.IO.File]::ReadAllBytes($cprojectPath)
$demoConfigPath = Join-Path $idtProject 'src/frtos_config/demo_config.h'
$originalDemoConfig = [System.IO.File]::ReadAllBytes($demoConfigPath)
$demoConfigText = [System.IO.File]::ReadAllText($demoConfigPath)
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
if ($TestGroup -in @('Transport', 'PKCS11', 'OTAPAL')) {
    if ($TestGroup -eq 'Transport') { Add-OptionValue $defineOption 'ENABLE_IDT_TRANSPORT_TEST=1' }
    elseif ($TestGroup -eq 'PKCS11') { Add-OptionValue $defineOption 'ENABLE_IDT_PKCS11_TEST=1' }
    else { Add-OptionValue $defineOption 'ENABLE_IDT_OTAPAL_TEST=1' }
    Add-OptionValue $defineOption 'UNITY_INCLUDE_CONFIG_H'
}
else {
    Add-OptionValue $defineOption 'ENABLE_IDT_CLOUD_DEMO=1'
    # Keep the production pub/sub tasks active across Device Advisor cases.
    Add-OptionValue $defineOption 'mqttexamplePUBLISH_COUNT=4294967295U'
    $demoFlags = @{
        ENABLE_FLEET_PROVISIONING_DEMO = 0
        ENABLE_MULTI_TLS_DEMO = 0
        ENABLE_OTA_UPDATE_DEMO = $(if ($TestGroup -eq 'OTAE2E') { 1 } else { 0 })
    }
    foreach ($flag in $demoFlags.Keys) {
        $pattern = "(?m)^\s*#define\s+$flag\s+\([01]\)\s*$"
        if ([regex]::Matches($demoConfigText, $pattern).Count -ne 1) {
            throw "Expected one demo config definition of $flag."
        }
        $demoConfigText = [regex]::Replace($demoConfigText, $pattern, "#define $flag ($($demoFlags[$flag]))")
    }
    foreach ($part in $appVersion.Keys) {
        Add-OptionValue $defineOption "APP_VERSION_$part=$($appVersion[$part])"
    }
}

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
    Write-Host "IDT $TestGroup metadata/provenance validated: $($testSources.Count) sources, $($generatedFiles.Count) snapshot files; no compiler or hardware action."
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
    if ($TestGroup -in @('DeviceAdvisor', 'OTAE2E')) {
        [System.IO.File]::WriteAllText($demoConfigPath, $demoConfigText, [System.Text.UTF8Encoding]::new($false))
    }
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
        mode = $(if ($TestGroup -eq 'Transport') { 'idt-transport-only' } else { "idt-$($TestGroup.ToLowerInvariant())" })
        suite = $suiteName
        application_version = $appVersion
        coverage = $(if ($TestGroup -eq 'OTAPAL') {
            [ordered]@{
                nominal_cases = 15
                assertion_capable_cases = 14
                not_applicable_cases = 1
                not_applicable_test = 'otaPal_CloseFile_NonexistingCodeSignerCertificate'
                required_end_state = 'MCU reset-hold; reflash/reprovision before reuse'
            }
        } else { $null })
        source_sha = $sourceSha
        source_tree_dirty = $sourceWasDirty
        test_library_sha = $testLibrarySha
        execution_config_sha256 = (Get-FileHash -LiteralPath $executionPath -Algorithm SHA256).Hash.ToLowerInvariant()
        parameter_config_sha256 = (Get-FileHash -LiteralPath (Join-Path $idtRoot 'Test/include/test_param_config.h') -Algorithm SHA256).Hash.ToLowerInvariant()
        outputs = $outputs
        qualification_status = 'not-established; selected individual group only'
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
    [System.IO.File]::WriteAllBytes($demoConfigPath, $originalDemoConfig)
}

param(
    [string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$Python = 'python',
    [ValidateSet('rx72n-ethernet', 'rx65n-bg96', 'rx671-wifi')]
    [string[]]$CompileTargets = @(),
    [string]$OutputDirectory = '',
    [string]$WorkspaceRoot = ''
)

# Exercises real project/source metadata with inert runtime headers. No compiler,
# cloud, serial device, flash programmer, or hardware tool is invoked.
# Optional CompileTargets uses upstream placeholder parameters for compile/link
# only. These images must never be flashed or reported as native IDT results.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$builder = Join-Path $PSScriptRoot 'build_rx72n_idt_transport.ps1'
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('idt-builder-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
$runtimePaths = @('test_execution_config.h', 'test_param_config.h', 'idt_ota_signer.h', 'idt_network_config.h') |
    ForEach-Object { Join-Path $root ('Test/include/' + $_) }
$snapshots = @{}
foreach ($path in $runtimePaths) {
    $snapshots[$path] = $(if (Test-Path -LiteralPath $path) { [IO.File]::ReadAllBytes($path) } else { $null })
}
$projectSnapshots = @{}
$manifest = [IO.File]::ReadAllText((Join-Path $root 'tools/idt/targets.json')) | ConvertFrom-Json
foreach ($target in $manifest.targets.PSObject.Properties) {
    foreach ($project in @($target.Value.application_project, $target.Value.bootloader_project)) {
        foreach ($relative in @('.project', '.cproject', 'src/frtos_config/demo_config.h')) {
            $path = Join-Path (Join-Path $root $project) $relative
            if (Test-Path -LiteralPath $path) {
                $projectSnapshots[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
            }
        }
    }
}
$sourceSha = (& git -c "safe.directory=$root" -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot read metadata fixture source provenance.' }
$testRoot = Join-Path $root 'Test/FreeRTOS-Libraries-Integration-Tests'
$testSha = (& git -c "safe.directory=$testRoot" -C $testRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot read integration-test dependency provenance.' }
$provenances = @{}
foreach ($target in $manifest.targets.PSObject.Properties.Name) {
    $provenance = Join-Path $temporary ("provenance-$target.json")
    [ordered]@{ source_sha=$sourceSha; test_library_sha=$testSha; source_tree_dirty=$true } |
        ConvertTo-Json | Set-Content -LiteralPath $provenance -Encoding UTF8
    & $Python (Join-Path $PSScriptRoot 'idt_source_manifest.py') capture `
        --source $root --target $target --provenance $provenance
    if ($LASTEXITCODE -ne 0) { throw "Cannot capture metadata fixture dependencies for $target." }
    $provenances[$target] = $provenance
}
$groups = [ordered]@{
    Transport = 'TRANSPORT_INTERFACE_TEST_ENABLED'
    DeviceAdvisor = 'DEVICE_ADVISOR_TEST_ENABLED'
    OTAE2E = 'OTA_E2E_TEST_ENABLED'
    PKCS11 = 'CORE_PKCS11_TEST_ENABLED'
    OTAPAL = 'OTA_PAL_TEST_ENABLED'
}
$flags = @($groups.Values) + 'MQTT_TEST_ENABLED'
$parameters = @'
#define PKCS11_TEST_RSA_KEY_SUPPORT 0
#define PKCS11_TEST_EC_KEY_SUPPORT 1
#define PKCS11_TEST_IMPORT_PRIVATE_KEY_SUPPORT 1
#define PKCS11_TEST_GENERATE_KEYPAIR_SUPPORT 0
#define PKCS11_TEST_PREPROVISIONED_SUPPORT 0
#define PKCS11_TEST_JITP_CODEVERIFY_ROOT_CERT_SUPPORTED 0
#define OTA_PAL_USE_FILE_SYSTEM 0
#define OTA_PAL_TEST_CERT_TYPE OTA_ECDSA_SHA256
#define OTA_APP_VERSION_MAJOR 0
#define OTA_APP_VERSION_MINOR 1
#define OTA_APP_VERSION_BUILD 1
'@
$count = 0
try {
    [IO.File]::WriteAllText($runtimePaths[1], $parameters)
    [IO.File]::WriteAllText($runtimePaths[2], '#define IDT_OTA_IMAGE_ID "0123456789abcdef0123456789abcdef"' + "`n")
    [IO.File]::WriteAllText($runtimePaths[3], @'
#define IDT_WIFI_SSID "test-only"
#define IDT_WIFI_PASSPHRASE "test-only"
#define IDT_CELLULAR_APN "test-only"
#define IDT_CELLULAR_APN_USER ""
#define IDT_CELLULAR_APN_PASSWORD ""
#define IDT_CELLULAR_APN_AUTH "0"
'@)
    foreach ($group in $groups.Keys) {
        $execution = ($flags | ForEach-Object { '#define ' + $_ + ' (' + [int]($_ -eq $groups[$group]) + ')' }) -join "`n"
        [IO.File]::WriteAllText($runtimePaths[0], $execution + "`n")
        foreach ($target in $manifest.targets.PSObject.Properties.Name) {
            $validationReport = Join-Path $temporary ("links-$target-$group.json")
            & $builder -ProjectRoot $root -Target $target -TestGroup $group -Python $Python `
                -ProvenanceFile $provenances[$target] -ValidateOnly -ValidationReportFile $validationReport
            $validated = [IO.File]::ReadAllText($validationReport) | ConvertFrom-Json
            $expectedVariable = $(if ($target -eq 'rx65n-bg96') { 'AWS_IOT_MCU_REPO_ROOT' } else { 'AWS_IOT_MCU_ROOT' })
            if ($validated.repository_variable -ne $expectedVariable -or $validated.compiler_invoked -ne $false) {
                throw 'IDT source links select the wrong repository root or claim compilation.'
            }
            foreach ($link in $validated.source_links.PSObject.Properties) {
                $prefix = $expectedVariable + '/'
                if (-not $link.Value.location_uri.StartsWith($prefix, [StringComparison]::Ordinal)) {
                    throw "IDT source URI does not use the selected repository variable: $($link.Name)"
                }
                $relative = $link.Value.location_uri.Substring($prefix.Length)
                $expectedSource = [IO.Path]::GetFullPath((Join-Path $root $relative))
                if ($link.Value.resolved_path -ne $expectedSource -or -not (Test-Path -LiteralPath $expectedSource -PathType Leaf)) {
                    throw "IDT source link does not resolve to the real supplied source file: $($link.Name)"
                }
            }
            $count++
        }
    }
    $rejected = $false
    try {
        & $builder -ProjectRoot $root -Target 'rx72n-ethernet' -TestGroup Transport `
            -ProvenanceFile $provenances['rx72n-ethernet'] -ValidateOnly
    }
    catch {
        if ($_.Exception.Message -notmatch 'build requires') { throw }
        $rejected = $true
    }
    if (-not $rejected) { throw 'A mismatched suite header was accepted.' }
    foreach ($path in $projectSnapshots.Keys) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $projectSnapshots[$path]) {
            throw "ValidateOnly modified production metadata: $path"
        }
    }
    Write-Host "PASS: $count target/group metadata validations, suite mismatch rejected, production metadata unchanged. Hardware qualification is not established."
    if ($CompileTargets.Count -gt 0) {
        if (-not $OutputDirectory -or -not $WorkspaceRoot) {
            throw 'CompileTargets requires explicit OutputDirectory and WorkspaceRoot.'
        }
        $template = Join-Path $testRoot 'config_template/test_param_config_template.h'
        # The upstream template documents its example defines inside comments.
        # Select those public examples solely for compile/link; no real endpoint,
        # device credential or native assertion result is introduced.
        $placeholderDefines = @([IO.File]::ReadAllLines($template) | ForEach-Object {
            if ($_ -match '^\s*\*\s*(#define\s+\w+\s+.+)$') { $Matches[1] }
        })
        if ($placeholderDefines.Count -lt 10) { throw 'Upstream placeholder parameter template changed.' }
        [IO.File]::WriteAllText($runtimePaths[1], ($placeholderDefines -join "`n") + "`n")
        $execution = ($flags | ForEach-Object { '#define ' + $_ + ' (' + [int]($_ -eq $groups['Transport']) + ')' }) -join "`n"
        [IO.File]::WriteAllText($runtimePaths[0], $execution + "`n")
        foreach ($target in $CompileTargets) {
            & $builder -ProjectRoot $root -Target $target -TestGroup Transport -Python $Python `
                -ProvenanceFile $provenances[$target] `
                -Workspace (Join-Path $WorkspaceRoot $target) `
                -OutputDirectory (Join-Path $OutputDirectory $target)
            Write-Host "PASS: $target Transport compile/link; placeholder-only image, no native IDT or hardware action."
        }
    }
}
finally {
    foreach ($path in $snapshots.Keys) {
        if ($null -eq $snapshots[$path]) { Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue }
        else { [IO.File]::WriteAllBytes($path, $snapshots[$path]) }
    }
    $fullTemporary = [IO.Path]::GetFullPath($temporary)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $fullTemporary.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to remove a test directory outside the temporary root.'
    }
    Remove-Item -LiteralPath $fullTemporary -Recurse -Force
}

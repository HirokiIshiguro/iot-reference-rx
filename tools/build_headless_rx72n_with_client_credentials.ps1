param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$ThingName = $env:AWS_IOT_THING_NAME,
    [string]$Endpoint = $env:AWS_IOT_ENDPOINT,
    [string]$CertInput = $env:AWS_IOT_CERT,
    [string]$KeyInput = $env:AWS_IOT_PRIVKEY,
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx72n-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx72n_e2studio_build_mqtt_candidate.log"),
    [switch]$KeepRenderedHeaders
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-PemInput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputValue,
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string]$TempDir
    )

    if ([string]::IsNullOrWhiteSpace($InputValue)) {
        throw "$Label is not set."
    }

    if (Test-Path $InputValue -PathType Leaf) {
        return (Resolve-Path $InputValue).Path
    }

    $tempPath = Join-Path $TempDir "$Label.pem"
    [System.IO.File]::WriteAllText(
        $tempPath,
        $InputValue,
        [System.Text.UTF8Encoding]::new($false)
    )
    return $tempPath
}

$projectRoot = (Resolve-Path $ProjectRoot).Path
$renderScript = Join-Path $projectRoot "tools\render_rx72n_client_credentials.py"
$buildScript = Join-Path $projectRoot "tools\build_headless_rx72n.ps1"
$credentialHeader = Join-Path $projectRoot "Demos\include\aws_clientcredential.h"
$keysHeader = Join-Path $projectRoot "Demos\include\aws_clientcredential_keys.h"
$tempDir = Join-Path $projectRoot ".ci_temp_credentials"

if (-not (Test-Path $renderScript)) {
    throw "render script not found: $renderScript"
}
if (-not (Test-Path $buildScript)) {
    throw "build script not found: $buildScript"
}
if (-not (Test-Path $credentialHeader)) {
    throw "credential header not found: $credentialHeader"
}
if (-not (Test-Path $keysHeader)) {
    throw "keys header not found: $keysHeader"
}
if ([string]::IsNullOrWhiteSpace($ThingName)) {
    throw "ThingName is not set."
}
if ([string]::IsNullOrWhiteSpace($Endpoint)) {
    throw "Endpoint is not set."
}

$originalCredentialHeader = [System.IO.File]::ReadAllBytes($credentialHeader)
$originalKeysHeader = [System.IO.File]::ReadAllBytes($keysHeader)

New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

try {
    $certPath = Resolve-PemInput -InputValue $CertInput -Label "device-cert" -TempDir $tempDir
    $keyPath = Resolve-PemInput -InputValue $KeyInput -Label "device-key" -TempDir $tempDir

    Write-Host "=== Render RX72N client credential headers ==="
    Write-Host "Thing name: $ThingName"
    Write-Host "Endpoint:   $Endpoint"
    Write-Host "Cert input: $certPath"
    Write-Host "Key input:  $keyPath"

    python $renderScript `
        --thing-name $ThingName `
        --endpoint $Endpoint `
        --cert $certPath `
        --key $keyPath `
        --credential-header $credentialHeader `
        --keys-header $keysHeader

    if ($LASTEXITCODE -ne 0) {
        throw "credential render failed: $LASTEXITCODE"
    }

    & $buildScript `
        -ProjectRoot $projectRoot `
        -E2Studio $E2Studio `
        -Workspace $Workspace `
        -LogFile $LogFile
}
finally {
    if (-not $KeepRenderedHeaders) {
        [System.IO.File]::WriteAllBytes($credentialHeader, $originalCredentialHeader)
        [System.IO.File]::WriteAllBytes($keysHeader, $originalKeysHeader)
    }

    if (Test-Path $tempDir) {
        Remove-Item -Recurse -Force $tempDir
    }
}

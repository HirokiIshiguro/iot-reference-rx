param(
    [string]$Root = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$sourcesPath = Join-Path $rootPath "sources"
$stagingPath = Join-Path $rootPath "staging"

$firmwareSource = Join-Path $sourcesPath "firmware-wifi-host-driver\WHD\COMPONENT_WIFI5\resources\firmware\COMPONENT_43439\43439A0.bin"
$clmSource = Join-Path $sourcesPath "wifi-resources\clm\COMPONENT_WIFI5\COMPONENT_43439\COMPONENT_MURATA-1YN\43439A0.clm_blob"
$nvramTextSource = Join-Path $sourcesPath "cyw-fmac-nvram\cyfmac43439-sdio.1YN.txt"

$firmwareStage = Join-Path $stagingPath "43439A0.bin"
$clmStage = Join-Path $stagingPath "43439A0.clm_blob"
$nvramStage = Join-Path $stagingPath "nvram_1yn.bin"

function Assert-FileHash {
    param(
        [string]$Path,
        [string]$ExpectedSha256
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required Type 1YN blob source is missing: $Path"
    }

    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($actual -ne $ExpectedSha256.ToUpperInvariant()) {
        throw "SHA256 mismatch for $Path. Expected $ExpectedSha256, got $actual."
    }
}

function Assert-NormalizedTextHash {
    param(
        [string]$Path,
        [string]$ExpectedSha256
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required Type 1YN blob source is missing: $Path"
    }

    $text = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).Path)
    $text = $text.Replace("`r`n", "`n").Replace("`r", "`n")
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $actual = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToUpperInvariant()
    if ($actual -ne $ExpectedSha256.ToUpperInvariant()) {
        throw "Normalized SHA256 mismatch for $Path. Expected $ExpectedSha256, got $actual."
    }
}

function Convert-Type1ynNvram {
    param(
        [string]$InputPath,
        [string]$OutputPath
    )

    $bytes = [System.Collections.Generic.List[byte]]::new()
    foreach ($line in [System.IO.File]::ReadAllLines((Resolve-Path -LiteralPath $InputPath).Path)) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        $bytes.AddRange([System.Text.Encoding]::ASCII.GetBytes($trimmed))
        $bytes.Add(0)
    }

    $bytes.Add(0)
    while (($bytes.Count % 4) -ne 0) {
        $bytes.Add(0)
    }

    [System.IO.File]::WriteAllBytes($OutputPath, $bytes.ToArray())
}

New-Item -ItemType Directory -Path $stagingPath -Force | Out-Null

Assert-FileHash -Path $firmwareSource -ExpectedSha256 "BF545B5E5796E7F9348EC4A77F87D25E557AB97378DC2046A99E70997D2E1CA8"
Assert-FileHash -Path $clmSource -ExpectedSha256 "07BC4851449DB809CE154FF79194A36CC6A2F7015C8B80B4073B5AA6F862CCB6"
Assert-NormalizedTextHash -Path $nvramTextSource -ExpectedSha256 "A397520D73D6D77C77C3B63116A7286BDACCE83923AE8C346F8EF6643ED3D445"

Copy-Item -LiteralPath $firmwareSource -Destination $firmwareStage -Force
Copy-Item -LiteralPath $clmSource -Destination $clmStage -Force
Convert-Type1ynNvram -InputPath $nvramTextSource -OutputPath $nvramStage

Assert-FileHash -Path $firmwareStage -ExpectedSha256 "BF545B5E5796E7F9348EC4A77F87D25E557AB97378DC2046A99E70997D2E1CA8"
Assert-FileHash -Path $clmStage -ExpectedSha256 "07BC4851449DB809CE154FF79194A36CC6A2F7015C8B80B4073B5AA6F862CCB6"
Assert-FileHash -Path $nvramStage -ExpectedSha256 "F8824E0D6F36B5FCA8B36986140733A63F43BBC19293F6DEF40DEC2FD78F055E"

Write-Host "Type 1YN WHD blobs staged:"
Write-Host "  $firmwareStage"
Write-Host "  $nvramStage"
Write-Host "  $clmStage"

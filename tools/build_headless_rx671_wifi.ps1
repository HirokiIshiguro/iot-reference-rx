param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2026_04_2\eclipse\e2studioc.exe",
    [int]$E2StudioTimeoutSeconds = 180,
    [string]$OtaImageVersion = "",
    [string]$Make = "",
    [string]$CcrxBin = "",
    [string]$Workspace = "C:\iotref-rx671-wifi-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx671_wifi_e2studio_build.log"),
    [string]$WifiConfigFile = "",
    [string]$AwsIotConfigDir = "",
    [string]$AwsIotEndpoint = "",
    [string]$AwsIotThingName = "",
    [string]$RequireTlsVersion = "",
    [switch]$UseLocalJoinConfig,
    [switch]$SkipWifiConfig,
    [switch]$UseAwsIotLocalConfig,
    [switch]$SkipAwsIotConfig,
    [switch]$FleetProvisioningEnable,
    [string]$FleetEndpoint = "",
    [string]$FleetTemplateName = "",
    [string]$FleetClaimCertificate = "",
    [string]$FleetClaimPrivateKey = "",
    [switch]$UseTsipEntropy,
    [int]$SoftIrqPollMs = -1,
    [int]$WlanAllowBusSleepDelayMs = 600000,
    [switch]$WlanDisablePowersave,
    [int]$FreeRtosHeapSizeKb = -1,
    [int]$TcpWinSegCount = -1,
    [int]$NetworkBufferDescriptors = -1,
    [int]$WhdPortBufferCount = -1,
    [int]$WhdPortBufferPayloadBytes = -1,
    [int]$WhdPortBufferHeadroomBytes = -1,
    [string]$SdioRunClockDiv = "",
    [string]$SdioCmd53XferEngine = "",
    [string]$SdioCmd53DtcReadEnable = "",
    [string]$SdioCmd53DtcWriteEnable = "",
    [string]$SdioCmd53DtcMinBytes = "",
    [string]$SdioCmd53DmacaReadEnable = "",
    [string]$SdioCmd53DmacaWriteEnable = "",
    [string]$SdioCmd53DmacaMinBytes = "",
    [string]$SdioCmd53DmacaBlockMode = "",
    [switch]$SdioUseHighSpeedClock,
    [switch]$SdioHighSpeedDrive,
    [switch]$TcpThroughputEnable,
    [string]$TcpThroughputHost = "",
    [int]$TcpThroughputPort = -1,
    [string]$TcpThroughputMode = "",
    [int]$TcpThroughputBytes = -1,
    [int]$TcpThroughputChunkBytes = -1,
    [int]$TcpThroughputTxChunkBytes = -1,
    [int]$TcpThroughputRxChunkBytes = -1,
    [int]$TcpThroughputIterations = -1,
    [int]$TcpThroughputTxBufferBytes = -1,
    [int]$TcpThroughputRxBufferBytes = -1,
    [int]$TcpThroughputTxWindowMss = -1,
    [int]$TcpThroughputRxWindowMss = -1,
    [int]$TcpThroughputProgressBytes = -1
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function ConvertFrom-OtaImageVersion {
    param([string]$Version)

    if ($Version.Length -eq 0) {
        return $null
    }

    $formatError = "Invalid OTA image version '$Version': expected x.y.z with major/minor 0..255 and build 0..65535."
    $match = [regex]::Match(
        $Version,
        '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant)
    if (-not $match.Success) {
        throw $formatError
    }

    $major = [uint64]0
    $minor = [uint64]0
    $build = [uint64]0
    if ((-not [uint64]::TryParse(
            $match.Groups[1].Value,
            [System.Globalization.NumberStyles]::None,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [ref]$major)) -or
        (-not [uint64]::TryParse(
            $match.Groups[2].Value,
            [System.Globalization.NumberStyles]::None,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [ref]$minor)) -or
        (-not [uint64]::TryParse(
            $match.Groups[3].Value,
            [System.Globalization.NumberStyles]::None,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [ref]$build))) {
        throw $formatError
    }

    $parts = [PSCustomObject]@{
        Major = $major
        Minor = $minor
        Build = $build
        Text  = $Version
    }
    if (($parts.Major -gt 255) -or
        ($parts.Minor -gt 255) -or
        ($parts.Build -gt 65535)) {
        throw $formatError
    }

    return $parts
}

$otaImageVersionParts = ConvertFrom-OtaImageVersion -Version $OtaImageVersion
$effectiveOtaImageVersion = if ($null -ne $otaImageVersionParts) {
    $otaImageVersionParts.Text
} else {
    "0.1.0"
}
$expectedOtaImageMarker = "RX671_OTA_IMAGE_VERSION=$effectiveOtaImageVersion"

$projectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$projectName = "aws_wifi_rx671_ek"
$projectDir = Join-Path $projectRoot "Projects\$projectName\e2studio_ccrx"
$whdDir = Join-Path $projectRoot "Projects\$projectName\external\wifi-host-driver"
$whdPatch = Join-Path $projectRoot "Projects\$projectName\external\patches\whd-v1.70.0-ccrx-portability.patch"
$type1ynBlobStageScript = Join-Path $projectRoot "Projects\$projectName\external\type1yn-blobs\stage_type1yn_blobs.ps1"
$cproject = Join-Path $projectDir ".cproject"
$localJoinConfig = Join-Path $projectDir "src\whd_join_config_local.h"
$localAwsIotConfig = Join-Path $projectDir "src\frtos_config\aws_iot_config_local.h"
$localTcpThroughputConfig = Join-Path $projectDir "src\frtos_config\tcp_throughput_config_local.h"
$localFleetConfig = Join-Path $projectDir "src\frtos_config\rx671_fleet_config_local.h"
$defaultAwsIotConfigDir = "C:\ai\codex\secrets\aws-iot\rx671-ek-type1yn-01"
$useFleetConfigForBuild = $FleetProvisioningEnable.IsPresent
$explicitWifiConfigRequested = $UseLocalJoinConfig.IsPresent -or
    (-not [string]::IsNullOrWhiteSpace($WifiConfigFile))
if ($SkipWifiConfig.IsPresent -and $explicitWifiConfigRequested) {
    throw "-SkipWifiConfig cannot be combined with -UseLocalJoinConfig or -WifiConfigFile."
}
$useLocalJoinConfigForBuild = (-not $SkipWifiConfig.IsPresent) -and (
    $explicitWifiConfigRequested -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_SSID)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_PASSPHRASE)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_PASSWORD)))
$useAwsIotLocalConfigForBuild = (-not $useFleetConfigForBuild) -and
    (-not $SkipAwsIotConfig.IsPresent) -and ($UseAwsIotLocalConfig.IsPresent -or
    (-not [string]::IsNullOrWhiteSpace($AwsIotConfigDir)) -or
    (Test-Path -LiteralPath $defaultAwsIotConfigDir) -or
    (-not [string]::IsNullOrWhiteSpace($AwsIotEndpoint)) -or
    (-not [string]::IsNullOrWhiteSpace($AwsIotThingName)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_AWS_IOT_ENDPOINT)) -or
    (-not [string]::IsNullOrWhiteSpace($env:AWS_IOT_ENDPOINT)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_AWS_IOT_CERT_PEM)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_AWS_IOT_CERT_PEM_FILE)) -or
    (-not [string]::IsNullOrWhiteSpace($env:AWS_IOT_CERT_PEM)) -or
    (-not [string]::IsNullOrWhiteSpace($env:AWS_IOT_CERT_FILE)))
$useTcpThroughputLocalConfigForBuild = $TcpThroughputEnable.IsPresent -or
    (-not [string]::IsNullOrWhiteSpace($TcpThroughputHost)) -or
    ($TcpThroughputPort -ge 0) -or
    (-not [string]::IsNullOrWhiteSpace($TcpThroughputMode)) -or
    ($TcpThroughputBytes -ge 0) -or
    ($TcpThroughputChunkBytes -ge 0) -or
    ($TcpThroughputTxChunkBytes -ge 0) -or
    ($TcpThroughputRxChunkBytes -ge 0) -or
    ($TcpThroughputIterations -ge 0) -or
    ($TcpThroughputTxBufferBytes -ge 0) -or
    ($TcpThroughputRxBufferBytes -ge 0) -or
    ($TcpThroughputTxWindowMss -ge 0) -or
    ($TcpThroughputRxWindowMss -ge 0) -or
    ($TcpThroughputProgressBytes -ge 0) -or
    ("1" -eq $env:RX671_EK_TCP_THROUGHPUT_ENABLE) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_HOST)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_PORT)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_MODE)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_BYTES)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_CHUNK_BYTES)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_TX_CHUNK_BYTES)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_RX_CHUNK_BYTES)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_ITERATIONS)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_TX_BUFFER_BYTES)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_RX_BUFFER_BYTES)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_TX_WINDOW_MSS)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_RX_WINDOW_MSS)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_TCP_THROUGHPUT_PROGRESS_BYTES))

if (-not (Test-Path -LiteralPath $E2Studio)) {
    throw "e2 studio executable not found: $E2Studio"
}

if (-not (Test-Path -LiteralPath (Join-Path $projectDir ".project"))) {
    throw "e2 studio project not found: $projectDir"
}

$submodulePaths = @(
    "Projects/$projectName/external/wifi-host-driver",
    "Projects/$projectName/external/TraceRecorderSource",
    "Projects/$projectName/external/type1yn-blobs/sources/firmware-wifi-host-driver",
    "Projects/$projectName/external/type1yn-blobs/sources/wifi-resources",
    "Projects/$projectName/external/type1yn-blobs/sources/cyw-fmac-nvram",
    "Middleware/3rdparty/mbedtls",
    "Middleware/FreeRTOS/FreeRTOS-Kernel",
    "Middleware/FreeRTOS/FreeRTOS-Plus-TCP",
    "Middleware/FreeRTOS/coreMQTT",
    "Middleware/FreeRTOS/coreMQTT-Agent",
    "Middleware/FreeRTOS/coreJSON",
    "Middleware/FreeRTOS/backoffAlgorithm",
    "Middleware/FreeRTOS/corePKCS11",
    "Middleware/3rdparty/littlefs",
    "Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c",
    "Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk",
    "Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk"
)

foreach ($submodulePath in $submodulePaths) {
    $submoduleFullPath = Join-Path $projectRoot ($submodulePath -replace '/', '\')
    if (-not (Test-Path -LiteralPath (Join-Path $submoduleFullPath ".git"))) {
        Write-Host "Initializing submodule: $submodulePath"
        & git -C $projectRoot submodule update --init --recursive $submodulePath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to initialize submodule: $submodulePath"
        }
    }
}

if (-not (Test-Path -LiteralPath $whdPatch)) {
    throw "WHD patch not found: $whdPatch"
}

if (-not (Test-Path -LiteralPath $type1ynBlobStageScript)) {
    throw "Type 1YN blob staging script not found: $type1ynBlobStageScript"
}

function Test-GitApply {
    param([string[]]$Arguments)

    & git @Arguments *> $null
    return ($LASTEXITCODE -eq 0)
}

function ConvertTo-CStringLiteral {
    param([string]$Value)

    $builder = [System.Text.StringBuilder]::new()
    foreach ($ch in $Value.ToCharArray()) {
        switch ($ch) {
            "`"" { [void]$builder.Append('\"') }
            "\"  { [void]$builder.Append('\\') }
            "`r" { [void]$builder.Append('\r') }
            "`n" { [void]$builder.Append('\n') }
            "`t" { [void]$builder.Append('\t') }
            default { [void]$builder.Append($ch) }
        }
    }

    return $builder.ToString()
}

function Read-WifiConfig {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Wi-Fi config file not found: $Path"
    }

    $ssid = $null
    $passphrase = $null

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed -match '^(?i:ssid)\s*[:=]\s*(.+)$') {
            $ssid = $Matches[1].Trim().Trim('"')
            continue
        }

        if ($trimmed -match '^(?i:(pass|password|passphrase|psk))\s*[:=]\s*(.+)$') {
            $passphrase = $Matches[2].Trim().Trim('"')
            continue
        }

        if ((-not $ssid) -and (-not $passphrase)) {
            $parts = $trimmed -split '\s+', 2
            if ($parts.Count -ge 2) {
                $ssid = $parts[0].Trim().Trim('"')
                $passphrase = $parts[1].Trim().Trim('"')
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($ssid) -or [string]::IsNullOrWhiteSpace($passphrase)) {
        throw "Wi-Fi config must contain SSID and passphrase. Supported forms: 'ssid passphrase', 'SSID=...', 'PASS=...'."
    }

    return @{
        Ssid       = $ssid
        Passphrase = $passphrase
    }
}

function Read-WifiConfigFromEnvironment {
    $ssid = $env:RX671_EK_WIFI_SSID
    $passphrase = $env:RX671_EK_WIFI_PASSPHRASE

    if ([string]::IsNullOrWhiteSpace($passphrase)) {
        $passphrase = $env:RX671_EK_WIFI_PASSWORD
    }

    if ([string]::IsNullOrWhiteSpace($ssid) -or [string]::IsNullOrWhiteSpace($passphrase)) {
        throw "Wi-Fi config environment must contain RX671_EK_WIFI_SSID and RX671_EK_WIFI_PASSPHRASE."
    }

    return @{
        Ssid       = $ssid
        Passphrase = $passphrase
    }
}

function Write-LocalJoinConfig {
    param(
        [string]$Path,
        [string]$Ssid,
        [string]$Passphrase,
        [int]$PollMs
    )

    $lines = @(
        "/*",
        " * Generated by tools/build_headless_rx671_wifi.ps1.",
        " * This file contains local AP credentials and is intentionally ignored by git.",
        " */",
        "#ifndef WHD_JOIN_CONFIG_LOCAL_H_",
        "#define WHD_JOIN_CONFIG_LOCAL_H_",
        "",
        "#define WHD_JOIN_ENABLE                (1)",
        "#define WHD_JOIN_SSID                  `"$((ConvertTo-CStringLiteral $Ssid))`"",
        "#define WHD_JOIN_PASSPHRASE            `"$((ConvertTo-CStringLiteral $Passphrase))`""
    )

    if ($PollMs -ge 0) {
        $lines += "#define WHD_SDIO_SOFTIRQ_POLL_MS       (${PollMs}U)"
    }

    $lines += @(
        "",
        "#endif /* WHD_JOIN_CONFIG_LOCAL_H_ */",
        ""
    )

    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.UTF8Encoding]::new($false))
}

function ConvertTo-IPv4Octets {
    param([string]$Address)

    $ip = [System.Net.IPAddress]::Parse($Address)
    if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "TCP throughput host must be an IPv4 address: $Address"
    }

    return $ip.GetAddressBytes()
}

function ConvertTo-TcpThroughputModeDefine {
    param([string]$Mode)

    if ([string]::IsNullOrWhiteSpace($Mode)) {
        return "TCP_THROUGHPUT_MODE_BOTH"
    }

    switch ($Mode.Trim().ToLowerInvariant()) {
        "sink"   { return "TCP_THROUGHPUT_MODE_SINK" }
        "tx"     { return "TCP_THROUGHPUT_MODE_SINK" }
        "send"   { return "TCP_THROUGHPUT_MODE_SINK" }
        "source" { return "TCP_THROUGHPUT_MODE_SOURCE" }
        "rx"     { return "TCP_THROUGHPUT_MODE_SOURCE" }
        "recv"   { return "TCP_THROUGHPUT_MODE_SOURCE" }
        "both"   { return "TCP_THROUGHPUT_MODE_BOTH" }
        "3"      { return "TCP_THROUGHPUT_MODE_BOTH" }
        "2"      { return "TCP_THROUGHPUT_MODE_SOURCE" }
        "1"      { return "TCP_THROUGHPUT_MODE_SINK" }
        default  { throw "Unsupported TCP throughput mode '$Mode'. Use sink/source/both." }
    }
}

function Get-ConfigInt {
    param(
        [int]$Value,
        [string]$EnvValue,
        [int]$DefaultValue
    )

    if ($Value -ge 0) {
        return $Value
    }
    if (-not [string]::IsNullOrWhiteSpace($EnvValue)) {
        return [int]$EnvValue
    }

    return $DefaultValue
}

function Write-LocalTcpThroughputConfig {
    param(
        [string]$Path,
        [string]$TargetHost,
        [int]$Port,
        [string]$Mode,
        [int]$Bytes,
        [int]$ChunkBytes,
        [int]$TxChunkBytes,
        [int]$RxChunkBytes,
        [int]$Iterations,
        [int]$TxBufferBytes,
        [int]$RxBufferBytes,
        [int]$TxWindowMss,
        [int]$RxWindowMss,
        [int]$ProgressBytes
    )

    $effectiveHost = Get-FirstNonEmpty @($TargetHost, $env:RX671_EK_TCP_THROUGHPUT_HOST, "192.168.10.105")
    $octets = ConvertTo-IPv4Octets -Address $effectiveHost
    $effectivePort = Get-ConfigInt -Value $Port -EnvValue $env:RX671_EK_TCP_THROUGHPUT_PORT -DefaultValue 5001
    $effectiveMode = ConvertTo-TcpThroughputModeDefine (Get-FirstNonEmpty @($Mode, $env:RX671_EK_TCP_THROUGHPUT_MODE, "both"))
    $effectiveBytes = Get-ConfigInt -Value $Bytes -EnvValue $env:RX671_EK_TCP_THROUGHPUT_BYTES -DefaultValue 10485760
    $effectiveChunkBytes = Get-ConfigInt -Value $ChunkBytes -EnvValue $env:RX671_EK_TCP_THROUGHPUT_CHUNK_BYTES -DefaultValue 1460
    $effectiveTxChunkBytes = Get-ConfigInt -Value $TxChunkBytes -EnvValue $env:RX671_EK_TCP_THROUGHPUT_TX_CHUNK_BYTES -DefaultValue $effectiveChunkBytes
    $effectiveRxChunkBytes = Get-ConfigInt -Value $RxChunkBytes -EnvValue $env:RX671_EK_TCP_THROUGHPUT_RX_CHUNK_BYTES -DefaultValue $effectiveChunkBytes
    $effectiveIterations = Get-ConfigInt -Value $Iterations -EnvValue $env:RX671_EK_TCP_THROUGHPUT_ITERATIONS -DefaultValue 1
    $effectiveTxBufferBytes = Get-ConfigInt -Value $TxBufferBytes -EnvValue $env:RX671_EK_TCP_THROUGHPUT_TX_BUFFER_BYTES -DefaultValue 65536
    $effectiveRxBufferBytes = Get-ConfigInt -Value $RxBufferBytes -EnvValue $env:RX671_EK_TCP_THROUGHPUT_RX_BUFFER_BYTES -DefaultValue 65536
    $effectiveTxWindowMss = Get-ConfigInt -Value $TxWindowMss -EnvValue $env:RX671_EK_TCP_THROUGHPUT_TX_WINDOW_MSS -DefaultValue 44
    $effectiveRxWindowMss = Get-ConfigInt -Value $RxWindowMss -EnvValue $env:RX671_EK_TCP_THROUGHPUT_RX_WINDOW_MSS -DefaultValue 44
    $effectiveProgressBytes = Get-ConfigInt -Value $ProgressBytes -EnvValue $env:RX671_EK_TCP_THROUGHPUT_PROGRESS_BYTES -DefaultValue 0

    $lines = @(
        "/*",
        " * Generated by tools/build_headless_rx671_wifi.ps1.",
        " * This file contains local TCP throughput test settings and is intentionally ignored by git.",
        " */",
        "#ifndef TCP_THROUGHPUT_CONFIG_LOCAL_H_",
        "#define TCP_THROUGHPUT_CONFIG_LOCAL_H_",
        "",
        "#define TCP_THROUGHPUT_ENABLE           (1U)",
        "#define TCP_THROUGHPUT_HOST_IP0         ($($octets[0])U)",
        "#define TCP_THROUGHPUT_HOST_IP1         ($($octets[1])U)",
        "#define TCP_THROUGHPUT_HOST_IP2         ($($octets[2])U)",
        "#define TCP_THROUGHPUT_HOST_IP3         ($($octets[3])U)",
        "#define TCP_THROUGHPUT_PORT             (${effectivePort}U)",
        "#define TCP_THROUGHPUT_MODE             $effectiveMode",
        "#define TCP_THROUGHPUT_TOTAL_BYTES      (${effectiveBytes}UL)",
        "#define TCP_THROUGHPUT_CHUNK_BYTES      (${effectiveChunkBytes}U)",
        "#define TCP_THROUGHPUT_TX_CHUNK_BYTES   (${effectiveTxChunkBytes}U)",
        "#define TCP_THROUGHPUT_RX_CHUNK_BYTES   (${effectiveRxChunkBytes}U)",
        "#define TCP_THROUGHPUT_ITERATIONS       (${effectiveIterations}U)",
        "#define TCP_THROUGHPUT_TX_BUFFER_BYTES  (${effectiveTxBufferBytes}UL)",
        "#define TCP_THROUGHPUT_RX_BUFFER_BYTES  (${effectiveRxBufferBytes}UL)",
        "#define TCP_THROUGHPUT_TX_WINDOW_MSS    (${effectiveTxWindowMss}L)",
        "#define TCP_THROUGHPUT_RX_WINDOW_MSS    (${effectiveRxWindowMss}L)",
        "#define TCP_THROUGHPUT_PROGRESS_BYTES   (${effectiveProgressBytes}UL)",
        "",
        "#endif /* TCP_THROUGHPUT_CONFIG_LOCAL_H_ */",
        ""
    )

    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Host "TCP throughput: host=$effectiveHost port=$effectivePort mode=$effectiveMode bytes=$effectiveBytes chunk=$effectiveChunkBytes txchunk=$effectiveTxChunkBytes rxchunk=$effectiveRxChunkBytes iterations=$effectiveIterations txbuf=$effectiveTxBufferBytes rxbuf=$effectiveRxBufferBytes txwin=$effectiveTxWindowMss rxwin=$effectiveRxWindowMss progress=$effectiveProgressBytes"
}

function Get-FirstNonEmpty {
    param([string[]]$Values)

    foreach ($value in $Values) {
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }

    return ""
}

function Read-TextFromValueOrPath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }

    if (Test-Path -LiteralPath $Value) {
        return [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $Value).Path)
    }

    return $Value
}

function Read-AwsIotMetadata {
    param([string]$Path)

    $metadata = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $metadata
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed -match '^([^=:\s]+)\s*[:=]\s*(.+)$') {
            $metadata[$Matches[1].Trim().ToUpperInvariant()] = $Matches[2].Trim().Trim('"')
        }
    }

    return $metadata
}

function Read-AwsIotConfig {
    param(
        [string]$ConfigDir,
        [string]$EndpointOverride,
        [string]$ThingNameOverride
    )

    $resolvedDir = $ConfigDir
    $environmentCredentialsConfigured = $false
    foreach ($name in @(
        "RX671_EK_AWS_IOT_CERT_PEM",
        "RX671_EK_AWS_IOT_CERT_PEM_FILE",
        "AWS_IOT_CERT_PEM",
        "AWS_IOT_CERT_FILE",
        "AWS_IOT_CERT",
        "RX671_EK_AWS_IOT_PRIVATE_KEY_PEM",
        "RX671_EK_AWS_IOT_PRIVATE_KEY_PEM_FILE",
        "AWS_IOT_PRIVATE_KEY_PEM",
        "AWS_IOT_PRIVATE_KEY_FILE",
        "AWS_IOT_PRIVATE_KEY",
        "AWS_IOT_PRIVKEY",
        "AWS_IOT_PRIVKEY_FILE"
    )) {
        if (-not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
            $environmentCredentialsConfigured = $true
            break
        }
    }

    # CI credentials are the source of truth when present. Do not silently
    # combine them with a runner-local endpoint, certificate, or private key.
    if ([string]::IsNullOrWhiteSpace($resolvedDir) -and
        (-not $environmentCredentialsConfigured) -and
        (Test-Path -LiteralPath $defaultAwsIotConfigDir)) {
        $resolvedDir = $defaultAwsIotConfigDir
    }

    if (-not [string]::IsNullOrWhiteSpace($resolvedDir)) {
        Write-Host "AWS IoT config source: local directory"
        $resolvedDir = (Resolve-Path -LiteralPath $resolvedDir).Path
        $metadata = Read-AwsIotMetadata -Path (Join-Path $resolvedDir "metadata.txt")
        $endpoint = Get-FirstNonEmpty @($EndpointOverride, $metadata["ENDPOINT"])
        $thingName = Get-FirstNonEmpty @($ThingNameOverride, $metadata["THING_NAME"], $metadata["THING"])
        $certPath = Join-Path $resolvedDir "device-certificate.pem"
        $keyPath = Join-Path $resolvedDir "device-private-key.pem"

        if (-not (Test-Path -LiteralPath $certPath)) {
            throw "AWS IoT client certificate not found: $certPath"
        }
        if (-not (Test-Path -LiteralPath $keyPath)) {
            throw "AWS IoT client private key not found: $keyPath"
        }

        return @{
            Endpoint  = $endpoint
            ThingName = $thingName
            CertPem   = [System.IO.File]::ReadAllText($certPath)
            KeyPem    = [System.IO.File]::ReadAllText($keyPath)
        }
    }

    Write-Host "AWS IoT config source: environment"
    $endpoint = Get-FirstNonEmpty @($EndpointOverride, $env:RX671_EK_AWS_IOT_ENDPOINT, $env:AWS_IOT_ENDPOINT)
    $thingName = Get-FirstNonEmpty @($ThingNameOverride, $env:RX671_EK_AWS_IOT_THING_NAME, $env:AWS_IOT_THING_NAME)
    $certValue = Get-FirstNonEmpty @(
        $env:RX671_EK_AWS_IOT_CERT_PEM,
        $env:RX671_EK_AWS_IOT_CERT_PEM_FILE,
        $env:AWS_IOT_CERT_PEM,
        $env:AWS_IOT_CERT_FILE,
        $env:AWS_IOT_CERT
    )
    $keyValue = Get-FirstNonEmpty @(
        $env:RX671_EK_AWS_IOT_PRIVATE_KEY_PEM,
        $env:RX671_EK_AWS_IOT_PRIVATE_KEY_PEM_FILE,
        $env:AWS_IOT_PRIVATE_KEY_PEM,
        $env:AWS_IOT_PRIVATE_KEY_FILE,
        $env:AWS_IOT_PRIVATE_KEY,
        $env:AWS_IOT_PRIVKEY,
        $env:AWS_IOT_PRIVKEY_FILE
    )

    return @{
        Endpoint  = $endpoint
        ThingName = $thingName
        CertPem   = Read-TextFromValueOrPath -Value $certValue
        KeyPem    = Read-TextFromValueOrPath -Value $keyValue
    }
}

function Write-LocalAwsIotConfig {
    param(
        [string]$Path,
        [hashtable]$Config
    )

    if ([string]::IsNullOrWhiteSpace($Config["Endpoint"]) -or
        [string]::IsNullOrWhiteSpace($Config["ThingName"]) -or
        [string]::IsNullOrWhiteSpace($Config["CertPem"]) -or
        [string]::IsNullOrWhiteSpace($Config["KeyPem"])) {
        throw "AWS IoT local config requires endpoint, thing name, client certificate, and private key."
    }

    $lines = @(
        "/*",
        " * Generated by tools/build_headless_rx671_wifi.ps1.",
        " * This file contains local AWS IoT credentials and is intentionally ignored by git.",
        " */",
        "#ifndef AWS_IOT_CONFIG_LOCAL_H_",
        "#define AWS_IOT_CONFIG_LOCAL_H_",
        "",
        "#define AWS_IOT_MQTT_ENABLE             (1)",
        "#define AWS_IOT_ENDPOINT                `"$((ConvertTo-CStringLiteral $Config["Endpoint"]))`"",
        "#define AWS_IOT_THING_NAME              `"$((ConvertTo-CStringLiteral $Config["ThingName"]))`"",
        "#define AWS_IOT_CLIENT_CERT_PEM         `"$((ConvertTo-CStringLiteral $Config["CertPem"]))`"",
        "#define AWS_IOT_CLIENT_PRIVATE_KEY_PEM  `"$((ConvertTo-CStringLiteral $Config["KeyPem"]))`"",
        "",
        "#endif /* AWS_IOT_CONFIG_LOCAL_H_ */",
        ""
    )

    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.UTF8Encoding]::new($false))
}

function Read-FleetConfig {
    $endpoint = Get-FirstNonEmpty @(
        $FleetEndpoint,
        $env:RX671_EK_FLEET_ENDPOINT,
        $AwsIotEndpoint,
        $env:RX671_EK_AWS_IOT_ENDPOINT,
        $env:AWS_IOT_ENDPOINT
    )
    $templateName = Get-FirstNonEmpty @(
        $FleetTemplateName,
        $env:RX671_EK_FLEET_TEMPLATE_NAME
    )
    $claimCertificateValue = Get-FirstNonEmpty @(
        $FleetClaimCertificate,
        $env:RX671_EK_FLEET_CLAIM_CERT_PEM,
        $env:RX671_EK_FLEET_CLAIM_CERT_PEM_FILE
    )
    $claimPrivateKeyValue = Get-FirstNonEmpty @(
        $FleetClaimPrivateKey,
        $env:RX671_EK_FLEET_CLAIM_PRIVATE_KEY_PEM,
        $env:RX671_EK_FLEET_CLAIM_PRIVATE_KEY_PEM_FILE
    )

    $config = @{
        Endpoint        = $endpoint
        TemplateName    = $templateName
        ClaimCertificate = Read-TextFromValueOrPath -Value $claimCertificateValue
        ClaimPrivateKey = Read-TextFromValueOrPath -Value $claimPrivateKeyValue
    }

    if ([string]::IsNullOrWhiteSpace($config["Endpoint"]) -or
        [string]::IsNullOrWhiteSpace($config["TemplateName"]) -or
        [string]::IsNullOrWhiteSpace($config["ClaimCertificate"]) -or
        [string]::IsNullOrWhiteSpace($config["ClaimPrivateKey"])) {
        throw "Fleet Provisioning mode requires endpoint, template name, claim certificate, and claim private key."
    }

    return $config
}

function Write-LocalFleetConfig {
    param(
        [string]$Path,
        [hashtable]$Config
    )

    $lines = @(
        "/*",
        " * Generated by tools/build_headless_rx671_wifi.ps1.",
        " * This file contains Fleet Provisioning claim credentials and is intentionally ignored by git.",
        " */",
        "#ifndef RX671_FLEET_CONFIG_LOCAL_H_",
        "#define RX671_FLEET_CONFIG_LOCAL_H_",
        "",
        "#define RX671_FLEET_PROVISIONING_ENABLE       (1)",
        "#define RX671_FLEET_ENDPOINT                  `"$((ConvertTo-CStringLiteral $Config["Endpoint"]))`"",
        "#define RX671_FLEET_TEMPLATE_NAME             `"$((ConvertTo-CStringLiteral $Config["TemplateName"]))`"",
        "#define RX671_FLEET_CLAIM_CERTIFICATE_PEM     `"$((ConvertTo-CStringLiteral $Config["ClaimCertificate"]))`"",
        "#define RX671_FLEET_CLAIM_PRIVATE_KEY_PEM     `"$((ConvertTo-CStringLiteral $Config["ClaimPrivateKey"]))`"",
        "",
        "#endif /* RX671_FLEET_CONFIG_LOCAL_H_ */",
        ""
    )

    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.UTF8Encoding]::new($false))
}

function Add-CProjectDefine {
    param(
        [string]$Text,
        [string]$Define
    )

    $option = "-define=$Define"
    if ($Text.Contains($option)) {
        return $Text
    }

    $needle = '<listOptionValue builtIn="false" value="-define=__FUNCTION__=__func__"/>'
    if (-not $Text.Contains($needle)) {
        throw "Could not find the CCRX userBefore define anchor in .cproject."
    }

    $insert = "$needle`r`n`t`t`t`t`t`t`t`t`t<listOptionValue builtIn=`"false`" value=`"$option`"/>"
    return $Text.Replace($needle, $insert)
}

function Add-CProjectLinkerOption {
    param(
        [string]$Text,
        [string]$Option
    )

    $encodedOption = $Option.Replace("&", "&amp;").Replace('"', "&quot;")
    $optionElement = "<listOptionValue builtIn=`"false`" value=`"$encodedOption`"/>"
    if ($Text.Contains($optionElement)) {
        return $Text
    }

    $anchor = 'id="com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.userBefore.'
    $anchorIndex = $Text.IndexOf($anchor, [System.StringComparison]::Ordinal)
    if ($anchorIndex -lt 0) {
        throw "Could not find the CCRX linker userBefore option in .cproject."
    }

    $emptyOption = '<listOptionValue builtIn="false" value=""/>'
    $emptyOptionIndex = $Text.IndexOf(
        $emptyOption,
        $anchorIndex,
        [System.StringComparison]::Ordinal)
    if ($emptyOptionIndex -lt 0) {
        throw "Could not find the CCRX linker userBefore value anchor in .cproject."
    }

    $insertIndex = $emptyOptionIndex + $emptyOption.Length
    $insert = "`r`n`t`t`t`t`t`t`t`t`t$optionElement"
    return $Text.Insert($insertIndex, $insert)
}

function Assert-SRecordContainsAsciiMarker {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Marker
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Generated MOT was not found while checking the OTA image marker: $Path"
    }

    $imageBytes = [System.Collections.Generic.SortedDictionary[uint32, byte]]::new()
    foreach ($rawLine in [System.IO.File]::ReadLines($Path)) {
        $line = $rawLine.Trim()
        if (($line.Length -lt 4) -or
            (-not $line.StartsWith("S", [System.StringComparison]::Ordinal))) {
            continue
        }

        $addressBytes = switch ($line.Substring(0, 2)) {
            "S1" { 2 }
            "S2" { 3 }
            "S3" { 4 }
            default { 0 }
        }
        if ($addressBytes -eq 0) {
            continue
        }

        try {
            $count = [Convert]::ToByte($line.Substring(2, 2), 16)
        } catch {
            throw "Malformed Motorola S-record count while checking OTA image marker: $line"
        }
        if (($count -lt ($addressBytes + 1)) -or
            ($line.Length -ne (4 + (2 * $count)))) {
            throw "Malformed Motorola S-record length while checking OTA image marker: $line"
        }

        $recordBytes = [byte[]]::new($count)
        try {
            for ($index = 0; $index -lt $count; $index++) {
                $recordBytes[$index] = [Convert]::ToByte(
                    $line.Substring(4 + (2 * $index), 2),
                    16)
            }
        } catch {
            throw "Malformed Motorola S-record hex while checking OTA image marker: $line"
        }

        $checksumSum = [uint32]$count
        foreach ($value in $recordBytes) {
            $checksumSum += $value
        }
        if (($checksumSum -band 0xFFU) -ne 0xFFU) {
            throw "Motorola S-record checksum mismatch while checking OTA image marker: $line"
        }

        $address = [uint32]0
        for ($index = 0; $index -lt $addressBytes; $index++) {
            $address = [uint32](($address -shl 8) -bor $recordBytes[$index])
        }

        $dataLength = $count - $addressBytes - 1
        for ($index = 0; $index -lt $dataLength; $index++) {
            $dataAddress = [uint32]($address + $index)
            $value = $recordBytes[$addressBytes + $index]
            if ($imageBytes.ContainsKey($dataAddress) -and
                ($imageBytes[$dataAddress] -ne $value)) {
                throw ("Conflicting Motorola S-record data at 0x{0:X8} " +
                    "while checking OTA image marker." -f $dataAddress)
            }
            $imageBytes[$dataAddress] = $value
        }
    }

    $markerBytes = [System.Text.Encoding]::ASCII.GetBytes($Marker)
    foreach ($startAddress in $imageBytes.Keys) {
        if ($imageBytes[$startAddress] -ne $markerBytes[0]) {
            continue
        }

        $matches = $true
        for ($index = 1; $index -lt $markerBytes.Length; $index++) {
            $address = [uint32]($startAddress + $index)
            if ((-not $imageBytes.ContainsKey($address)) -or
                ($imageBytes[$address] -ne $markerBytes[$index])) {
                $matches = $false
                break
            }
        }
        if ($matches) {
            Write-Host ("OTA image marker verified at 0x{0:X8}: {1}" -f
                $startAddress, $Marker)
            return
        }
    }

    throw "OTA image marker was not found in generated MOT: $Marker"
}

function Remove-DirectoryBestEffort {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    try {
        Remove-Item -LiteralPath $Path -Recurse -Force
    } catch {
        Write-Warning "Could not remove $Label '$Path' before build: $($_.Exception.Message)"
        Write-Warning "Continuing; e2 studio -cleanBuild will attempt to refresh build outputs."
    }
}

function Wait-RxBuildProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [datetime]$Since,
        [int]$TimeoutSeconds = 900
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $buildProcs = Get-Process -ErrorAction SilentlyContinue |
            Where-Object {
                (($_.ProcessName -eq "make") -or
                 ($_.ProcessName -eq "ccrx") -or
                 ($_.ProcessName -eq "rlink")) -and
                ($null -ne $_.StartTime) -and
                ($_.StartTime -ge $Since)
            }

        if (-not $buildProcs) {
            return
        }

        $summary = ($buildProcs | Group-Object ProcessName | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join ", "
        Write-Host "Waiting for e2 studio child build processes: $summary"
        Start-Sleep -Seconds 5
    }

    Write-Warning "Timed out waiting for e2 studio child build processes to exit."
}

function Resolve-PluginTool {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PluginPattern,
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $eclipseDir = Split-Path -Parent $E2Studio
    $pluginsDir = Join-Path $eclipseDir "plugins"
    if (-not (Test-Path -LiteralPath $pluginsDir)) {
        return $null
    }

    $pluginDirs = Get-ChildItem -Path $pluginsDir -Directory -Filter $PluginPattern -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending
    foreach ($pluginDir in $pluginDirs) {
        $candidate = Join-Path $pluginDir.FullName $RelativePath
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Resolve-Make {
    if (-not [string]::IsNullOrWhiteSpace($Make)) {
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

    throw "GNU make was not found. Set -Make to the e2 studio make.exe path."
}

function Resolve-CcrxBin {
    if (-not [string]::IsNullOrWhiteSpace($CcrxBin)) {
        if (-not (Test-Path -LiteralPath $CcrxBin)) {
            throw "CC-RX bin directory not found: $CcrxBin"
        }
        return (Resolve-Path -LiteralPath $CcrxBin).Path
    }

    foreach ($candidate in @($env:CCRX_BIN, $env:BIN_RX, "C:\Program Files (x86)\Renesas\RX\3_7_0\bin")) {
        if ((-not [string]::IsNullOrWhiteSpace($candidate)) -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "CC-RX bin directory was not found. Set -CcrxBin, CCRX_BIN, or BIN_RX."
}

function Add-PathEntry {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or (-not (Test-Path -LiteralPath $Path))) {
        return
    }

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $entries = $env:Path -split ';'
    if ($entries -notcontains $resolved) {
        $env:Path = "$resolved;$env:Path"
    }
}

function Invoke-MakeTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuildDir,
        [Parameter(Mandatory = $true)]
        [string]$Target,
        [switch]$Force
    )

    Write-Host "Invoking make target: $Target"
    Push-Location $BuildDir
    try {
        $parallelJobs = [Math]::Max(1, [Math]::Min(24, [Environment]::ProcessorCount))
        $makeArguments = @("-r", "--output-sync", "-j$parallelJobs")
        if ($Force.IsPresent) {
            $makeArguments += "-B"
        }
        $makeArguments += $Target
        & $script:makeExe @makeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "make target '$Target' failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

function Test-ByteArrayEqual {
    param(
        [byte[]]$Left,
        [byte[]]$Right
    )

    if (($null -eq $Left) -or ($null -eq $Right) -or ($Left.Length -ne $Right.Length)) {
        return $false
    }

    for ($i = 0; $i -lt $Left.Length; $i++) {
        if ($Left[$i] -ne $Right[$i]) {
            return $false
        }
    }
    return $true
}

function Restore-TrackedProjectSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,
        [Parameter(Mandatory = $true)]
        [hashtable]$Snapshot
    )

    $restored = [System.Collections.Generic.List[string]]::new()
    foreach ($entry in $Snapshot.GetEnumerator()) {
        $relativePath = [string]$entry.Key
        $fullPath = Join-Path $Root ($relativePath -replace '/', '\')
        $currentBytes = $null
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            $currentBytes = [System.IO.File]::ReadAllBytes($fullPath)
        }

        if (-not (Test-ByteArrayEqual -Left $currentBytes -Right ([byte[]]$entry.Value))) {
            $parent = Split-Path -Parent $fullPath
            if (-not (Test-Path -LiteralPath $parent)) {
                [void](New-Item -ItemType Directory -Force -Path $parent)
            }
            [System.IO.File]::WriteAllBytes($fullPath, [byte[]]$entry.Value)
            $restored.Add($relativePath)
        }
    }

    return $restored.ToArray()
}

function Invoke-E2StudioHeadlessBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string]$WorkspacePath,
        [Parameter(Mandatory = $true)]
        [string]$ProjectPath,
        [Parameter(Mandatory = $true)]
        [string]$BuildTarget,
        [Parameter(Mandatory = $true)]
        [string]$OutputLog
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $Executable
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    foreach ($arg in @(
        "-nosplash",
        "-application",
        "org.eclipse.cdt.managedbuilder.core.headlessbuild",
        "-data",
        $WorkspacePath,
        "-import",
        $ProjectPath,
        "-cleanBuild",
        $BuildTarget
    )) {
        [void]$psi.ArgumentList.Add($arg)
    }

    $proc = [System.Diagnostics.Process]::Start($psi)
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    $timedOut = -not $proc.WaitForExit($E2StudioTimeoutSeconds * 1000)
    if ($timedOut) {
        Write-Warning "e2 studio headless build timed out after $E2StudioTimeoutSeconds seconds; terminating it before the explicit make fallback."
        try {
            $proc.Kill($true)
        } catch {
            Write-Warning "Could not terminate the e2 studio process tree: $($_.Exception.Message)"
        }
    }
    $proc.WaitForExit()
    $stdoutTask.Wait()
    $stderrTask.Wait()

    $outputChunks = @($stdoutTask.Result, $stderrTask.Result) | Where-Object { -not [string]::IsNullOrEmpty($_) }
    $logText = [string]::Join([Environment]::NewLine, $outputChunks)
    try {
        [System.IO.File]::WriteAllText($OutputLog, $logText, [System.Text.UTF8Encoding]::new($false))
    } catch {
        Write-Warning "Could not write e2 studio build log '$OutputLog': $($_.Exception.Message)"
        $fallbackLog = "$OutputLog.codex.log"
        [System.IO.File]::WriteAllText($fallbackLog, $logText, [System.Text.UTF8Encoding]::new($false))
        Write-Warning "Wrote captured e2 studio build log to '$fallbackLog' instead."
    }
    if (-not [string]::IsNullOrEmpty($logText)) {
        Write-Host $logText
    }

    if ($timedOut) {
        return 124
    }
    return $proc.ExitCode
}

$gitApplyWhitespaceArgs = @("--ignore-space-change", "--ignore-whitespace")
$reverseCheckArgs = @("-C", $whdDir, "apply") + $gitApplyWhitespaceArgs + @("--reverse", "--check", $whdPatch)
$forwardCheckArgs = @("-C", $whdDir, "apply") + $gitApplyWhitespaceArgs + @("--check", $whdPatch)

if (Test-GitApply $reverseCheckArgs) {
    Write-Host "WHD patch is already applied."
} elseif (Test-GitApply $forwardCheckArgs) {
    Write-Host "Applying WHD patch..."
    & git -C $whdDir apply @gitApplyWhitespaceArgs $whdPatch
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to apply WHD patch."
    }
} else {
    throw "WHD patch state is neither clean nor applied. Check submodule status: $whdDir"
}

Write-Host "Staging Type 1YN WHD blobs..."
& $type1ynBlobStageScript
if ($LASTEXITCODE -ne 0) {
    throw "Type 1YN blob staging failed with exit code $LASTEXITCODE"
}

Remove-DirectoryBestEffort -Path $Workspace -Label "workspace"

$hardwareDebug = Join-Path $projectDir "HardwareDebug"
Remove-DirectoryBestEffort -Path $hardwareDebug -Label "HardwareDebug"

$logFilePath = [System.IO.Path]::GetFullPath($LogFile)
Write-Host "=== RX671 Wi-Fi import + build ==="
Write-Host "Project:   $projectDir"
Write-Host "Workspace: $Workspace"
Write-Host "Log file:  $logFilePath"
if ($null -ne $otaImageVersionParts) {
    Write-Host "OTA image version override: $effectiveOtaImageVersion"
}
if ($useLocalJoinConfigForBuild) {
    Write-Host "Local AP JOIN config: enabled"
}
if ($useAwsIotLocalConfigForBuild) {
    Write-Host "Local AWS IoT config: enabled"
}
if ($useTcpThroughputLocalConfigForBuild) {
    Write-Host "Local TCP throughput config: enabled"
}
if ($useFleetConfigForBuild) {
    Write-Host "Fleet Provisioning build mode: enabled"
}
if ($WlanAllowBusSleepDelayMs -ge 0) {
    Write-Host "WHD WLAN bus sleep delay: ${WlanAllowBusSleepDelayMs} ms"
}
$effectiveSdioRunClockDiv = Get-FirstNonEmpty @($SdioRunClockDiv, $env:RX671_EK_SDIO_RUN_CLOCK_DIV)
if (-not [string]::IsNullOrWhiteSpace($effectiveSdioRunClockDiv)) {
    Write-Host "SDIO run clock divider override: $effectiveSdioRunClockDiv"
}
if ($SdioUseHighSpeedClock.IsPresent -or ("1" -eq $env:RX671_EK_SDIO_USE_HIGH_SPEED_CLOCK)) {
    Write-Host "SDIO high-speed CCCR/EHS clock path: enabled"
}
if ($SdioHighSpeedDrive.IsPresent -or ("1" -eq $env:RX671_EK_SDIO_HIGH_SPEED_DRIVE)) {
    Write-Host "SDIO PORTD high-speed interface drive: enabled"
}
$effectiveSdioCmd53XferEngine = Get-FirstNonEmpty @($SdioCmd53XferEngine, $env:RX671_EK_SDIO_CMD53_XFER_ENGINE)
if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53XferEngine)) {
    Write-Host "SDIO CMD53 transfer engine override: $effectiveSdioCmd53XferEngine"
}
$script:makeExe = Resolve-Make
Add-PathEntry (Split-Path -Parent $script:makeExe)
Add-PathEntry (Resolve-CcrxBin)

$effectiveSdioCmd53DtcReadEnable = Get-FirstNonEmpty @($SdioCmd53DtcReadEnable, $env:RX671_EK_SDIO_CMD53_DTC_READ_ENABLE)
$effectiveSdioCmd53DtcWriteEnable = Get-FirstNonEmpty @($SdioCmd53DtcWriteEnable, $env:RX671_EK_SDIO_CMD53_DTC_WRITE_ENABLE)
$effectiveSdioCmd53DtcMinBytes = Get-FirstNonEmpty @($SdioCmd53DtcMinBytes, $env:RX671_EK_SDIO_CMD53_DTC_MIN_BYTES)
$effectiveSdioCmd53DmacaReadEnable = Get-FirstNonEmpty @($SdioCmd53DmacaReadEnable, $env:RX671_EK_SDIO_CMD53_DMACA_READ_ENABLE)
$effectiveSdioCmd53DmacaWriteEnable = Get-FirstNonEmpty @($SdioCmd53DmacaWriteEnable, $env:RX671_EK_SDIO_CMD53_DMACA_WRITE_ENABLE)
$effectiveSdioCmd53DmacaMinBytes = Get-FirstNonEmpty @($SdioCmd53DmacaMinBytes, $env:RX671_EK_SDIO_CMD53_DMACA_MIN_BYTES)
$effectiveSdioCmd53DmacaBlockMode = Get-FirstNonEmpty @($SdioCmd53DmacaBlockMode, $env:RX671_EK_SDIO_CMD53_DMACA_BLOCK_MODE)
$effectiveRequireTlsVersion = Get-FirstNonEmpty @($RequireTlsVersion, $env:RX671_WIFI_REQUIRE_TLS_VERSION)

if ((-not [string]::IsNullOrWhiteSpace($effectiveRequireTlsVersion)) -and
    ($effectiveRequireTlsVersion -ne "TLSv1.3")) {
    throw "Unsupported RX671 AWS IoT TLS version requirement: $effectiveRequireTlsVersion (expected TLSv1.3)"
}

$cprojectBytes = $null
$trackedProjectSnapshot = @{}
$fleetConfigCleanupFailed = $false
try {
    $cprojectDefines = @()
    $cprojectLinkerOptions = @(
        "-symbol_forbid=_g_rx671_ota_image_version_marker"
    )

    if ($null -ne $otaImageVersionParts) {
        $cprojectDefines += "APP_VERSION_MAJOR=$($otaImageVersionParts.Major)"
        $cprojectDefines += "APP_VERSION_MINOR=$($otaImageVersionParts.Minor)"
        $cprojectDefines += "APP_VERSION_BUILD=$($otaImageVersionParts.Build)"
    }

    if ($useLocalJoinConfigForBuild) {
        if (-not [string]::IsNullOrWhiteSpace($WifiConfigFile)) {
            $wifi = Read-WifiConfig -Path $WifiConfigFile
            Write-LocalJoinConfig -Path $localJoinConfig -Ssid $wifi["Ssid"] -Passphrase $wifi["Passphrase"] -PollMs $SoftIrqPollMs
            Write-Host "Generated ignored local JOIN header: $localJoinConfig"
        } elseif ((-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_SSID)) -or
                  (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_PASSPHRASE)) -or
                  (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_PASSWORD))) {
            $wifi = Read-WifiConfigFromEnvironment
            Write-LocalJoinConfig -Path $localJoinConfig -Ssid $wifi["Ssid"] -Passphrase $wifi["Passphrase"] -PollMs $SoftIrqPollMs
            Write-Host "Generated ignored local JOIN header from environment: $localJoinConfig"
        } elseif (-not (Test-Path -LiteralPath $localJoinConfig)) {
            throw "Local JOIN config was requested but not found: $localJoinConfig"
        }

        $cprojectDefines += "WHD_JOIN_USE_LOCAL_CONFIG"
    }

    if ($useAwsIotLocalConfigForBuild) {
        $awsIotConfig = Read-AwsIotConfig -ConfigDir $AwsIotConfigDir -EndpointOverride $AwsIotEndpoint -ThingNameOverride $AwsIotThingName
        Write-LocalAwsIotConfig -Path $localAwsIotConfig -Config $awsIotConfig
        Write-Host "Generated ignored local AWS IoT header: $localAwsIotConfig"
        $cprojectDefines += "AWS_IOT_USE_LOCAL_CONFIG"
    }

    if ($useFleetConfigForBuild) {
        $fleetConfig = Read-FleetConfig
        Write-LocalFleetConfig -Path $localFleetConfig -Config $fleetConfig
        Write-Host "Generated ignored local Fleet Provisioning header: $localFleetConfig"
        $cprojectDefines += "RX671_FLEET_USE_LOCAL_CONFIG"
    }

    if ($UseTsipEntropy.IsPresent) {
        $cprojectDefines += "AWS_IOT_USE_TSIP_ENTROPY"
    }

    if (-not [string]::IsNullOrWhiteSpace($effectiveRequireTlsVersion)) {
        $cprojectDefines += "AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3=1"
        Write-Host "AWS IoT MQTT TLS version fixed to TLSv1.3"
    }

    if ($useTcpThroughputLocalConfigForBuild) {
        Write-LocalTcpThroughputConfig `
            -Path $localTcpThroughputConfig `
            -TargetHost $TcpThroughputHost `
            -Port $TcpThroughputPort `
            -Mode $TcpThroughputMode `
            -Bytes $TcpThroughputBytes `
            -ChunkBytes $TcpThroughputChunkBytes `
            -TxChunkBytes $TcpThroughputTxChunkBytes `
            -RxChunkBytes $TcpThroughputRxChunkBytes `
            -Iterations $TcpThroughputIterations `
            -TxBufferBytes $TcpThroughputTxBufferBytes `
            -RxBufferBytes $TcpThroughputRxBufferBytes `
            -TxWindowMss $TcpThroughputTxWindowMss `
            -RxWindowMss $TcpThroughputRxWindowMss `
            -ProgressBytes $TcpThroughputProgressBytes
        $cprojectDefines += "TCP_THROUGHPUT_USE_LOCAL_CONFIG"
    }

    if ($WlanAllowBusSleepDelayMs -ge 0) {
        $cprojectDefines += "PLATFORM_WLAN_ALLOW_BUS_TO_SLEEP_DELAY_MS=$WlanAllowBusSleepDelayMs"
    }
    if ($WlanDisablePowersave.IsPresent -or ("1" -eq $env:RX671_EK_WLAN_DISABLE_POWERSAVE)) {
        $cprojectDefines += "WHD_JOIN_DISABLE_POWERSAVE=1"
    }
    if ($TcpWinSegCount -gt 0) {
        $cprojectDefines += "RX671_TCP_WIN_SEG_COUNT=$TcpWinSegCount"
    }
    if ($NetworkBufferDescriptors -gt 0) {
        $cprojectDefines += "RX671_NETWORK_BUFFER_DESCRIPTORS=$NetworkBufferDescriptors"
    }
    if ($WhdPortBufferCount -gt 0) {
        $cprojectDefines += "WHD_PORT_BUFFER_COUNT=$WhdPortBufferCount"
    }
    if ($WhdPortBufferPayloadBytes -gt 0) {
        $cprojectDefines += "WHD_PORT_BUFFER_PAYLOAD=$WhdPortBufferPayloadBytes"
    }
    if ($WhdPortBufferHeadroomBytes -gt 0) {
        $cprojectDefines += "WHD_PORT_BUFFER_HEADROOM=$WhdPortBufferHeadroomBytes"
    }
    if ($FreeRtosHeapSizeKb -gt 0) {
        $cprojectDefines += "RX671_FREERTOS_HEAP_SIZE_KB=$FreeRtosHeapSizeKb"
    }

    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioRunClockDiv)) {
        $cprojectDefines += "SDIO_HOST_CFG_RUN_CLOCK_DIV=$effectiveSdioRunClockDiv"
    }

    if ($SdioUseHighSpeedClock.IsPresent -or ("1" -eq $env:RX671_EK_SDIO_USE_HIGH_SPEED_CLOCK)) {
        $cprojectDefines += "SDIO_HOST_USE_HIGH_SPEED_CLOCK"
    }

    if ($SdioHighSpeedDrive.IsPresent -or ("1" -eq $env:RX671_EK_SDIO_HIGH_SPEED_DRIVE)) {
        $cprojectDefines += "SDIO_HOST_CFG_HIGH_SPEED_DRIVE=1"
    }

    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53XferEngine)) {
        $cprojectDefines += "SDIO_HOST_CMD53_XFER_ENGINE=$effectiveSdioCmd53XferEngine"
    }
    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53DtcReadEnable)) {
        $cprojectDefines += "SDIO_HOST_CMD53_DTC_READ_ENABLE=$effectiveSdioCmd53DtcReadEnable"
    }
    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53DtcWriteEnable)) {
        $cprojectDefines += "SDIO_HOST_CMD53_DTC_WRITE_ENABLE=$effectiveSdioCmd53DtcWriteEnable"
    }
    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53DtcMinBytes)) {
        $cprojectDefines += "SDIO_HOST_CMD53_DTC_MIN_BYTES=$effectiveSdioCmd53DtcMinBytes"
    }
    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53DmacaReadEnable)) {
        $cprojectDefines += "SDIO_HOST_CMD53_DMACA_READ_ENABLE=$effectiveSdioCmd53DmacaReadEnable"
    }
    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53DmacaWriteEnable)) {
        $cprojectDefines += "SDIO_HOST_CMD53_DMACA_WRITE_ENABLE=$effectiveSdioCmd53DmacaWriteEnable"
    }
    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53DmacaMinBytes)) {
        $cprojectDefines += "SDIO_HOST_CMD53_DMACA_MIN_BYTES=$effectiveSdioCmd53DmacaMinBytes"
    }
    if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53DmacaBlockMode)) {
        $cprojectDefines += "SDIO_HOST_CMD53_DMACA_BLOCK_MODE=$effectiveSdioCmd53DmacaBlockMode"
    }

    if (($cprojectDefines.Count -gt 0) -or ($cprojectLinkerOptions.Count -gt 0)) {
        $cprojectBytes = [System.IO.File]::ReadAllBytes($cproject)
        $patchedCProject = [System.IO.File]::ReadAllText($cproject)
        foreach ($define in $cprojectDefines) {
            $patchedCProject = Add-CProjectDefine -Text $patchedCProject -Define $define
        }
        foreach ($linkerOption in $cprojectLinkerOptions) {
            $patchedCProject = Add-CProjectLinkerOption `
                -Text $patchedCProject `
                -Option $linkerOption
        }
        [System.IO.File]::WriteAllText($cproject, $patchedCProject, [System.Text.UTF8Encoding]::new($false))
    }

    # Importing this Smart Configurator project can regenerate tracked source
    # files before the build starts. Preserve the checked-out source (including
    # any caller edits), restore it after import, and force a canonical rebuild.
    # .cproject is excluded because temporary CI defines must stay active until
    # the final make invocation; it is restored separately in the finally block.
    $repoProjectPath = "Projects/$projectName/e2studio_ccrx"
    $trackedProjectPaths = @(& git -C $projectRoot ls-files -- $repoProjectPath)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not enumerate tracked RX671 project files."
    }
    foreach ($relativePath in $trackedProjectPaths) {
        if ($relativePath -eq "$repoProjectPath/.cproject") {
            continue
        }
        $fullPath = Join-Path $projectRoot ($relativePath -replace '/', '\')
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            $trackedProjectSnapshot[$relativePath] = [System.IO.File]::ReadAllBytes($fullPath)
        }
    }

    $buildStart = Get-Date
    $e2StudioExitCode = Invoke-E2StudioHeadlessBuild `
        -Executable $E2Studio `
        -WorkspacePath $Workspace `
        -ProjectPath $projectDir `
        -BuildTarget "$projectName/HardwareDebug" `
        -OutputLog $logFilePath
    Wait-RxBuildProcesses -Since $buildStart

    $restoredGeneratedFiles = @(Restore-TrackedProjectSnapshot `
        -Root $projectRoot `
        -Snapshot $trackedProjectSnapshot)

    $motOutput = Join-Path $hardwareDebug "$projectName.mot"
    $motWasUpdated = (Test-Path -LiteralPath $motOutput) -and
        ((Get-Item -LiteralPath $motOutput).LastWriteTime -ge $buildStart)
    $canonicalRebuildCompleted = $false

    if ($restoredGeneratedFiles.Count -gt 0) {
        Write-Host "Smart Configurator regenerated $($restoredGeneratedFiles.Count) tracked file(s); restoring checked-out source and forcing a canonical rebuild."
        foreach ($relativePath in $restoredGeneratedFiles) {
            Write-Host "  restored: $relativePath"
        }
        Invoke-MakeTarget -BuildDir $hardwareDebug -Target "$projectName.mot" -Force
        $canonicalRebuildCompleted = $true
        $motWasUpdated = (Test-Path -LiteralPath $motOutput) -and
            ((Get-Item -LiteralPath $motOutput).LastWriteTime -ge $buildStart)
    }

    if ((-not $canonicalRebuildCompleted) -and (($e2StudioExitCode -ne 0) -or (-not $motWasUpdated))) {
        Write-Warning "e2 studio build returned exit code $e2StudioExitCode or did not refresh .mot through the default all target."
        Write-Host "Ensuring the loadable image with an explicit .mot make target."
        Invoke-MakeTarget -BuildDir $hardwareDebug -Target "$projectName.mot"
        $motWasUpdated = (Test-Path -LiteralPath $motOutput) -and
            ((Get-Item -LiteralPath $motOutput).LastWriteTime -ge $buildStart)
    }

    if (-not $motWasUpdated) {
        throw "Expected .mot output was not refreshed: $motOutput"
    } elseif ($e2StudioExitCode -ne 0) {
        Write-Warning "e2 studio returned exit code $e2StudioExitCode, but .mot/.abs/.map were refreshed by the explicit make target."
    }

    Assert-SRecordContainsAsciiMarker -Path $motOutput -Marker $expectedOtaImageMarker
} finally {
    # This generated file contains the Fleet claim private key. Remove it before
    # any other cleanup that could itself fail and prevent later statements.
    if ($useFleetConfigForBuild) {
        Remove-Item -LiteralPath $localFleetConfig -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $localFleetConfig) {
            $fleetConfigCleanupFailed = $true
        }
    }
    if ($trackedProjectSnapshot.Count -gt 0) {
        [void](Restore-TrackedProjectSnapshot -Root $projectRoot -Snapshot $trackedProjectSnapshot)
    }
    if ($null -ne $cprojectBytes) {
        [System.IO.File]::WriteAllBytes($cproject, $cprojectBytes)
    }
    if ($fleetConfigCleanupFailed) {
        throw "Failed to remove the generated Fleet Provisioning credential header: $localFleetConfig"
    }
}

foreach ($extension in @(".mot", ".abs", ".map")) {
    $output = Join-Path $hardwareDebug "$projectName$extension"
    if (-not (Test-Path -LiteralPath $output)) {
        throw "Expected build output missing: $output"
    }
}

Write-Host "RX671 Wi-Fi build completed successfully."

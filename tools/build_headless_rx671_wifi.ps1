param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe",
    [string]$Workspace = "C:\iotref-rx671-wifi-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx671_wifi_e2studio_build.log"),
    [string]$WifiConfigFile = "",
    [string]$AwsIotConfigDir = "",
    [string]$AwsIotEndpoint = "",
    [string]$AwsIotThingName = "",
    [switch]$UseLocalJoinConfig,
    [switch]$UseAwsIotLocalConfig,
    [switch]$UseTsipEntropy,
    [int]$SoftIrqPollMs = -1,
    [int]$WlanAllowBusSleepDelayMs = 600000,
    [string]$SdioRunClockDiv = "",
    [string]$SdioCmd53XferEngine = "",
    [string]$SdioCmd53DtcReadEnable = "",
    [string]$SdioCmd53DtcWriteEnable = "",
    [string]$SdioCmd53DtcMinBytes = "",
    [string]$SdioCmd53DmacaReadEnable = "",
    [string]$SdioCmd53DmacaWriteEnable = "",
    [string]$SdioCmd53DmacaMinBytes = "",
    [string]$SdioCmd53DmacaBlockMode = "",
    [switch]$SdioUseHighSpeedClock
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$projectName = "aws_wifi_rx671_ek"
$projectDir = Join-Path $projectRoot "Projects\$projectName\e2studio_ccrx"
$whdDir = Join-Path $projectRoot "Projects\$projectName\external\wifi-host-driver"
$whdPatch = Join-Path $projectRoot "Projects\$projectName\external\patches\whd-v1.70.0-ccrx-portability.patch"
$type1ynBlobStageScript = Join-Path $projectRoot "Projects\$projectName\external\type1yn-blobs\stage_type1yn_blobs.ps1"
$cproject = Join-Path $projectDir ".cproject"
$localJoinConfig = Join-Path $projectDir "src\whd_join_config_local.h"
$localAwsIotConfig = Join-Path $projectDir "src\frtos_config\aws_iot_config_local.h"
$defaultAwsIotConfigDir = "C:\ai\codex\secrets\aws-iot\rx671-ek-type1yn-01"
$useLocalJoinConfigForBuild = $UseLocalJoinConfig.IsPresent -or
    (-not [string]::IsNullOrWhiteSpace($WifiConfigFile)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_SSID)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_PASSPHRASE)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_WIFI_PASSWORD))
$useAwsIotLocalConfigForBuild = $UseAwsIotLocalConfig.IsPresent -or
    (-not [string]::IsNullOrWhiteSpace($AwsIotConfigDir)) -or
    (Test-Path -LiteralPath $defaultAwsIotConfigDir) -or
    (-not [string]::IsNullOrWhiteSpace($AwsIotEndpoint)) -or
    (-not [string]::IsNullOrWhiteSpace($AwsIotThingName)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_AWS_IOT_ENDPOINT)) -or
    (-not [string]::IsNullOrWhiteSpace($env:AWS_IOT_ENDPOINT)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_AWS_IOT_CERT_PEM)) -or
    (-not [string]::IsNullOrWhiteSpace($env:RX671_EK_AWS_IOT_CERT_PEM_FILE)) -or
    (-not [string]::IsNullOrWhiteSpace($env:AWS_IOT_CERT_PEM)) -or
    (-not [string]::IsNullOrWhiteSpace($env:AWS_IOT_CERT_FILE))

if (-not (Test-Path -LiteralPath $E2Studio)) {
    throw "e2 studio executable not found: $E2Studio"
}

if (-not (Test-Path -LiteralPath (Join-Path $projectDir ".project"))) {
    throw "e2 studio project not found: $projectDir"
}

$submodulePaths = @(
    "Projects/$projectName/external/wifi-host-driver",
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
    if ([string]::IsNullOrWhiteSpace($resolvedDir) -and (Test-Path -LiteralPath $defaultAwsIotConfigDir)) {
        $resolvedDir = $defaultAwsIotConfigDir
    }

    if (-not [string]::IsNullOrWhiteSpace($resolvedDir)) {
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

    return $proc.ExitCode
}

$reverseCheckArgs = @("-C", $whdDir, "apply", "--reverse", "--check", $whdPatch)
$forwardCheckArgs = @("-C", $whdDir, "apply", "--check", $whdPatch)

if (Test-GitApply $reverseCheckArgs) {
    Write-Host "WHD patch is already applied."
} elseif (Test-GitApply $forwardCheckArgs) {
    Write-Host "Applying WHD patch..."
    & git -C $whdDir apply $whdPatch
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
if ($useLocalJoinConfigForBuild) {
    Write-Host "Local AP JOIN config: enabled"
}
if ($useAwsIotLocalConfigForBuild) {
    Write-Host "Local AWS IoT config: enabled"
}
if ($WlanAllowBusSleepDelayMs -ge 0) {
    Write-Host "WHD WLAN bus sleep delay: ${WlanAllowBusSleepDelayMs} ms"
}
if (-not [string]::IsNullOrWhiteSpace($SdioRunClockDiv)) {
    Write-Host "SDIO run clock divider override: $SdioRunClockDiv"
}
$effectiveSdioCmd53XferEngine = Get-FirstNonEmpty @($SdioCmd53XferEngine, $env:RX671_EK_SDIO_CMD53_XFER_ENGINE)
if (-not [string]::IsNullOrWhiteSpace($effectiveSdioCmd53XferEngine)) {
    Write-Host "SDIO CMD53 transfer engine override: $effectiveSdioCmd53XferEngine"
}
$effectiveSdioCmd53DtcReadEnable = Get-FirstNonEmpty @($SdioCmd53DtcReadEnable, $env:RX671_EK_SDIO_CMD53_DTC_READ_ENABLE)
$effectiveSdioCmd53DtcWriteEnable = Get-FirstNonEmpty @($SdioCmd53DtcWriteEnable, $env:RX671_EK_SDIO_CMD53_DTC_WRITE_ENABLE)
$effectiveSdioCmd53DtcMinBytes = Get-FirstNonEmpty @($SdioCmd53DtcMinBytes, $env:RX671_EK_SDIO_CMD53_DTC_MIN_BYTES)
$effectiveSdioCmd53DmacaReadEnable = Get-FirstNonEmpty @($SdioCmd53DmacaReadEnable, $env:RX671_EK_SDIO_CMD53_DMACA_READ_ENABLE)
$effectiveSdioCmd53DmacaWriteEnable = Get-FirstNonEmpty @($SdioCmd53DmacaWriteEnable, $env:RX671_EK_SDIO_CMD53_DMACA_WRITE_ENABLE)
$effectiveSdioCmd53DmacaMinBytes = Get-FirstNonEmpty @($SdioCmd53DmacaMinBytes, $env:RX671_EK_SDIO_CMD53_DMACA_MIN_BYTES)
$effectiveSdioCmd53DmacaBlockMode = Get-FirstNonEmpty @($SdioCmd53DmacaBlockMode, $env:RX671_EK_SDIO_CMD53_DMACA_BLOCK_MODE)

$cprojectBytes = $null
try {
    $cprojectDefines = @()

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

    if ($UseTsipEntropy.IsPresent) {
        $cprojectDefines += "AWS_IOT_USE_TSIP_ENTROPY"
    }

    if ($WlanAllowBusSleepDelayMs -ge 0) {
        $cprojectDefines += "PLATFORM_WLAN_ALLOW_BUS_TO_SLEEP_DELAY_MS=$WlanAllowBusSleepDelayMs"
    }

    if (-not [string]::IsNullOrWhiteSpace($SdioRunClockDiv)) {
        $cprojectDefines += "SDIO_HOST_CFG_RUN_CLOCK_DIV=$SdioRunClockDiv"
    }

    if ($SdioUseHighSpeedClock.IsPresent -or ("1" -eq $env:RX671_EK_SDIO_USE_HIGH_SPEED_CLOCK)) {
        $cprojectDefines += "SDIO_HOST_USE_HIGH_SPEED_CLOCK"
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

    if ($cprojectDefines.Count -gt 0) {
        $cprojectBytes = [System.IO.File]::ReadAllBytes($cproject)
        $patchedCProject = [System.IO.File]::ReadAllText($cproject)
        foreach ($define in $cprojectDefines) {
            $patchedCProject = Add-CProjectDefine -Text $patchedCProject -Define $define
        }
        [System.IO.File]::WriteAllText($cproject, $patchedCProject, [System.Text.UTF8Encoding]::new($false))
    }

    $buildStart = Get-Date
    $e2StudioExitCode = Invoke-E2StudioHeadlessBuild `
        -Executable $E2Studio `
        -WorkspacePath $Workspace `
        -ProjectPath $projectDir `
        -BuildTarget "$projectName/HardwareDebug" `
        -OutputLog $logFilePath
    Wait-RxBuildProcesses -Since $buildStart

    $motOutput = Join-Path $hardwareDebug "$projectName.mot"
    $motWasUpdated = (Test-Path -LiteralPath $motOutput) -and
        ((Get-Item -LiteralPath $motOutput).LastWriteTime -ge $buildStart)

    if (($e2StudioExitCode -ne 0) -and (-not $motWasUpdated)) {
        throw "e2 studio build failed with exit code $e2StudioExitCode"
    } elseif ($e2StudioExitCode -ne 0) {
        Write-Warning "e2 studio returned exit code $e2StudioExitCode before child build completion, but output was refreshed."
    }
} finally {
    if ($null -ne $cprojectBytes) {
        [System.IO.File]::WriteAllBytes($cproject, $cprojectBytes)
    }
}

foreach ($extension in @(".mot", ".abs", ".x")) {
    $output = Join-Path $hardwareDebug "$projectName$extension"
    if (-not (Test-Path -LiteralPath $output)) {
        throw "Expected build output missing: $output"
    }
}

Write-Host "RX671 Wi-Fi build completed successfully."

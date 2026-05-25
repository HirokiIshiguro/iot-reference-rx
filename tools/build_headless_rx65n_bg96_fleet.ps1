param(
    [string]$ProjectRoot = $(Split-Path $PSScriptRoot -Parent),
    [string]$E2Studio = "C:\Renesas\e2_studio_2025_12\eclipse\e2studio-cli.exe",
    [string]$Workspace = "C:\iotref-rx65n-bg96-fleet-ws",
    [string]$LogFile = $(Join-Path (Split-Path $PSScriptRoot -Parent) "rx65n_bg96_e2studio_build_fleet.log"),
    [string]$FleetDemoId = "rx65n-bg96-fp",
    [int]$E2StudioTimeoutSeconds = 600,
    [string]$TlsBackend = $(if ($env:RX65N_BG96_TLS_BACKEND) { $env:RX65N_BG96_TLS_BACKEND } else { "software" }),
    [string]$RequireTlsVersion = $(if ($env:RX65N_BG96_REQUIRE_TLS_VERSION) { $env:RX65N_BG96_REQUIRE_TLS_VERSION } else { "" })
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path $ProjectRoot).Path
$normalizedTlsBackend = $TlsBackend.ToLowerInvariant()
switch ($normalizedTlsBackend) {
    "software" { $appProjectName = "aws_bg96_ck_rx65n" }
    "tsip" { $appProjectName = "aws_bg96_ck_rx65n_tsip" }
    default { throw "Unsupported RX65N BG96 TLS backend: $TlsBackend. Use 'software' or 'tsip'." }
}
$demoConfig = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx\src\frtos_config\demo_config.h"
$buildScript = Join-Path $projectRoot "tools\build_headless_rx65n_bg96.ps1"
$fleetSubdirMk = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx\HardwareDebug\Demos\Fleet_Provisioning_With_CSR_Demo\subdir.mk"
$linkerSubCommand = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx\HardwareDebug\LinkerSubCommand.tmp"
$linkerAppCommand = Join-Path $projectRoot "Projects\$appProjectName\e2studio_ccrx\HardwareDebug\Linker$appProjectName.tmp"

function Set-FleetDemoBuildInputs {
    param(
        [string]$SubdirMk,
        [string[]]$LinkerFiles
    )

    $subdirContent = @'
################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/Fleet_Provisioning_With_CSR_Demo/FleetProvisioningDemoExample.c \
../Demos/Fleet_Provisioning_With_CSR_Demo/pkcs11_operations.c \
../Demos/Fleet_Provisioning_With_CSR_Demo/tinycbor_serializer.c

COMPILER_OBJS += \
Demos/Fleet_Provisioning_With_CSR_Demo/FleetProvisioningDemoExample.obj \
Demos/Fleet_Provisioning_With_CSR_Demo/pkcs11_operations.obj \
Demos/Fleet_Provisioning_With_CSR_Demo/tinycbor_serializer.obj

C_DEPS += \
Demos/Fleet_Provisioning_With_CSR_Demo/FleetProvisioningDemoExample.d \
Demos/Fleet_Provisioning_With_CSR_Demo/pkcs11_operations.d \
Demos/Fleet_Provisioning_With_CSR_Demo/tinycbor_serializer.d

# Each subdirectory must supply rules for building sources it contributes
Demos/Fleet_Provisioning_With_CSR_Demo/%.obj: ../Demos/Fleet_Provisioning_With_CSR_Demo/%.c Demos/Fleet_Provisioning_With_CSR_Demo/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\Fleet_Provisioning_With_CSR_Demo\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\Fleet_Provisioning_With_CSR_Demo\cSubCommand.tmp" "$<"
'@

    [System.IO.File]::WriteAllText(
        $SubdirMk,
        $subdirContent,
        [System.Text.UTF8Encoding]::new($false)
    )

    $fleetInput = '-input=".\Demos/Fleet_Provisioning_With_CSR_Demo\FleetProvisioningDemoExample.obj"'
    $pkcsInput = '-input=".\Demos/Fleet_Provisioning_With_CSR_Demo\pkcs11_operations.obj"'
    $tinycborInput = '-input=".\Demos/Fleet_Provisioning_With_CSR_Demo\tinycbor_serializer.obj"'

    foreach ($linkerFile in $LinkerFiles) {
        $content = [System.IO.File]::ReadAllText($linkerFile)
        if (-not $content.Contains($fleetInput)) {
            $content = $content.Replace($pkcsInput, "$fleetInput`r`n$pkcsInput`r`n$tinycborInput")
        }
        [System.IO.File]::WriteAllText(
            $linkerFile,
            $content,
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

if (-not (Test-Path $demoConfig)) {
    throw "demo_config.h not found: $demoConfig"
}
if (-not (Test-Path $buildScript)) {
    throw "build script not found: $buildScript"
}

& $buildScript `
    -ProjectRoot $projectRoot `
    -E2Studio $E2Studio `
    -Workspace $Workspace `
    -LogFile $LogFile `
    -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds `
    -TlsBackend $normalizedTlsBackend `
    -RequireTlsVersion $RequireTlsVersion `
    -PrepareBuildFilesOnly

foreach ($path in @($fleetSubdirMk, $linkerSubCommand, $linkerAppCommand)) {
    if (-not (Test-Path $path)) {
        throw "generated build file not found: $path"
    }
}

$originalDemoConfig = [System.IO.File]::ReadAllText($demoConfig)
$originalGeneratedBuildFiles = @{}
foreach ($path in @($fleetSubdirMk, $linkerSubCommand, $linkerAppCommand)) {
    $originalGeneratedBuildFiles[$path] = [System.IO.File]::ReadAllText($path)
}

try {
    $updated = $originalDemoConfig
    $updated = $updated -replace '#define\s+ENABLE_FLEET_PROVISIONING_DEMO\s+\([01]\)', '#define ENABLE_FLEET_PROVISIONING_DEMO      (1)'
    $updated = $updated -replace '#define\s+ENABLE_OTA_UPDATE_DEMO\s+\([01]\)', '#define ENABLE_OTA_UPDATE_DEMO              (0)'
    $updated = $updated -replace '#if\s+\(ENABLE_FLEET_PROVISIONING_DEMO\s+==\s+1\)\s*\r?\n\s*#error\s+"Fleet Provisioning demo is not supported!"\s*\r?\n\s*#endif', ''
    $updated = $updated -replace '#define\s+democonfigFP_DEMO_ID\s+"[^"]+"', ('#define democonfigFP_DEMO_ID    "' + $FleetDemoId + '"')

    [System.IO.File]::WriteAllText(
        $demoConfig,
        $updated,
        [System.Text.UTF8Encoding]::new($false)
    )

    Set-FleetDemoBuildInputs `
        -SubdirMk $fleetSubdirMk `
        -LinkerFiles @($linkerSubCommand, $linkerAppCommand)

    & $buildScript `
        -ProjectRoot $projectRoot `
        -E2Studio $E2Studio `
        -Workspace $Workspace `
        -LogFile $LogFile `
        -E2StudioTimeoutSeconds $E2StudioTimeoutSeconds `
        -TlsBackend $normalizedTlsBackend `
        -RequireTlsVersion $RequireTlsVersion
}
finally {
    [System.IO.File]::WriteAllText(
        $demoConfig,
        $originalDemoConfig,
        [System.Text.UTF8Encoding]::new($false)
    )
    foreach ($path in $originalGeneratedBuildFiles.Keys) {
        [System.IO.File]::WriteAllText(
            $path,
            $originalGeneratedBuildFiles[$path],
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

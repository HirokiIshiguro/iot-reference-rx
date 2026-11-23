param(
    [string]$ProjectRoot = $PSScriptRoot,
    [switch]$Reverse
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Kept only as a migration error for existing callers. All CC-RX changes live
# in the reviewed wifi-host-driver fork referenced by the root gitlink.
throw 'WHD source patching is retired. Initialize the fixed wifi-host-driver fork submodule with git submodule update --init Projects/aws_wifi_rx671_ek/external/wifi-host-driver, then use tools/build_headless_rx671_wifi.ps1. Do not apply or reverse the former consumer-side patch.'

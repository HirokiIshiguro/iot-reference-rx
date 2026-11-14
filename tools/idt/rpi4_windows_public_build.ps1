param(
    [Parameter(Mandatory)][string] $ProjectRoot,
    [Parameter(Mandatory)][string] $Python,
    [Parameter(Mandatory)][string] $Workspace,
    [Parameter(Mandatory)][string] $Output,
    [Parameter(Mandatory)][string] $PrivateLog,
    [Parameter(Mandatory)][string] $LeaseDefinition
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([Console]::In.ReadLine() -cne 'go') { throw 'Build containment was not established.' }
. $LeaseDefinition
Enter-WindowsCcrxHostLease
try {
    $tools = @{
        'C:/Renesas/e2_studio_2026_04_2/eclipse/e2studio-cli.exe' = '6b021cc60f8736f4124f2ff61586bf883a415d1957b0a584346403cc91de2320'
        'C:/Program Files (x86)/Renesas/RX/3_7_0/bin/ccrx.exe' = '64c3daf4cd80557efa98071378dbe13fb4ba9f78da80560f5616bbb22ff5bc0a'
    }
    foreach ($path in $tools.Keys) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $tools[$path]) {
            throw 'A reviewed compiler launcher differs.'
        }
    }
    $stage = 'metadata'
    try {
        & (Join-Path $ProjectRoot 'tools/test_build_rx_idt.ps1') -ProjectRoot $ProjectRoot `
            -Python $Python -CompileTargets @('rx72n-ethernet') -OutputDirectory $Output `
            -WorkspaceRoot $Workspace -DiagnosticStage ([ref]$stage) *> $PrivateLog
    }
    catch {
        $failure = $_
        $kind = $failure.Exception.GetType().Name
        if ($kind -cnotin @('RuntimeException', 'ParameterBindingException', 'ParameterBindingValidationException',
                'UnauthorizedAccessException', 'IOException', 'FileNotFoundException', 'DirectoryNotFoundException',
                'InvalidOperationException', 'MethodInvocationException', 'NativeCommandExitException')) { $kind = 'Other' }
        if ($stage -cnotin @('metadata', 'placeholder-prepare', 'target-build')) { $stage = 'unknown' }
        $source = [IO.Path]::GetFileName($failure.InvocationInfo.ScriptName)
        if ($source -cnotin @('test_build_rx_idt.ps1', 'build_rx72n_idt_transport.ps1',
                'build_headless_rx72n.ps1', 'rx_e2studio_cli.ps1')) { $source = 'other' }
        $line = [Math]::Max(0, [Math]::Min(99999, $failure.InvocationInfo.ScriptLineNumber))
        try { Add-Content -LiteralPath $PrivateLog -Encoding utf8 -Value "PUBLIC_BUILD_FAILURE stage=$stage type=$kind source=$source line=$line" } catch { }
        throw $failure
    }
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw 'Public placeholder build failed.' }
} finally {
    if ($script:WindowsCcrxHostLease) { $script:WindowsCcrxHostLease.Dispose() }
}

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
    & (Join-Path $ProjectRoot 'tools/test_build_rx_idt.ps1') -ProjectRoot $ProjectRoot `
        -Python $Python -CompileTargets @('rx72n-ethernet') -OutputDirectory $Output -WorkspaceRoot $Workspace *> $PrivateLog
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw 'Public placeholder build failed.' }
} finally {
    if ($script:WindowsCcrxHostLease) { $script:WindowsCcrxHostLease.Dispose() }
}

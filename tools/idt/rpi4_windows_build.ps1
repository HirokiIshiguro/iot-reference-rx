param(
    [Parameter(Mandatory)][string] $ProjectRoot,
    [Parameter(Mandatory)][string] $ProvenanceFile,
    [Parameter(Mandatory)][string] $Workspace,
    [Parameter(Mandatory)][string] $PrivateLog,
    [Parameter(Mandatory)][string] $LeaseDefinition
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# This definition is exported by the CI job from the pinned shared template.
# Its final invocation is not copied; take the existing lease only for build.
. $LeaseDefinition
Enter-WindowsCcrxHostLease
try {
    $arguments = @{
        ProjectRoot = $ProjectRoot
        Target = 'rx72n-ethernet'
        TestGroup = 'Transport'
        ProvenanceFile = $ProvenanceFile
        Workspace = $Workspace
        E2Studio = 'C:/Renesas/e2_studio_2026_04_2/eclipse/e2studio-cli.exe'
        Python = 'C:/ai/codex/tools/venvs/rx72n-idt-windows/Scripts/python.exe'
    }
    & (Join-Path $ProjectRoot 'tools/build_rx72n_idt_transport.ps1') @arguments *> $PrivateLog
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw 'The build helper failed.' }
} finally {
    if ($script:WindowsCcrxHostLease) { $script:WindowsCcrxHostLease.Dispose() }
}

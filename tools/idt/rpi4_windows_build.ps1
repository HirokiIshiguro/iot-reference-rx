param(
    [Parameter(Mandatory)][string] $ProjectRoot,
    [Parameter(Mandatory)][string] $Python,
    [Parameter(Mandatory)][string] $ProvenanceFile,
    [Parameter(Mandatory)][string] $Workspace,
    [Parameter(Mandatory)][string] $PrivateLog
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# The owning worker assigns this process to its Job Object before sending go.
if ([Console]::In.ReadLine() -cne 'go') { throw 'Build containment was not established.' }

# Compiler serialization is owned by the parent CI resource group.
$arguments = @{
    ProjectRoot = $ProjectRoot
    Target = 'rx72n-ethernet'
    TestGroup = 'Transport'
    ProvenanceFile = $ProvenanceFile
    Workspace = $Workspace
    E2Studio = 'C:/Renesas/e2_studio_2026_04_2/eclipse/e2studio-cli.exe'
    Python = $Python
}
& (Join-Path $ProjectRoot 'tools/build_rx72n_idt_transport.ps1') @arguments *> $PrivateLog
# The PowerShell helper throws on failure; LASTEXITCODE can belong to a Git probe.

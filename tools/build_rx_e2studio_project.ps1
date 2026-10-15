param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$Workspace,
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [Parameter(Mandatory = $true)][string]$OutputLog,
    [ValidateRange(1, 2147483)][int]$TimeoutSeconds = 600
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rx_e2studio_cli.ps1')
$project = (Resolve-Path -LiteralPath $ProjectPath).Path.TrimEnd('\', '/')
$workspacePath = [IO.Path]::GetFullPath($Workspace).TrimEnd('\', '/')
if ($project.Equals($workspacePath, [StringComparison]::OrdinalIgnoreCase) -or
    $project.StartsWith($workspacePath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
    $workspacePath.StartsWith($project + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The disposable e2 studio workspace must be separate from the source project.'
}
$descriptor = [Xml.XmlDocument]::new()
$descriptor.Load((Join-Path $project '.project'))
$name = $descriptor.SelectSingleNode('/projectDescription/name')
if (-not $name -or [string]::IsNullOrWhiteSpace($name.InnerText)) {
    throw 'The source project has no e2 studio project name.'
}
$snapshots = @{}
foreach ($file in @('.project', '.cproject')) {
    $path = Join-Path $project $file
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $snapshots[$path] = [IO.File]::ReadAllBytes($path)
    }
}
foreach ($file in Get-ChildItem -LiteralPath $project -Filter '*.rcpc' -File) {
    $snapshots[$file.FullName] = [IO.File]::ReadAllBytes($file.FullName)
}
try {
    Remove-RxE2Workspace -Path $workspacePath
    $result = Invoke-RxE2StudioBuild -Executable $Executable -WorkspacePath $workspacePath `
        -ProjectPaths @($project) -BuildTargets @("$($name.InnerText)/HardwareDebug") `
        -OutputLog $OutputLog -TimeoutSeconds $TimeoutSeconds -AllowTimeoutExitCode
} finally {
    foreach ($path in $snapshots.Keys) {
        [IO.File]::WriteAllBytes($path, $snapshots[$path])
    }
}
exit $result

# Shared RX project import/build adapter for the Renesas command-line launcher.
# e2studio-cli uses project subcommands, rather than Eclipse -application flags.

function Remove-RxE2Workspace {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $roots = @('C:\ai\codex\ws', 'C:\Temp', [IO.Path]::GetTempPath())
    $allowed = @($roots | Where-Object {
        $prefix = [IO.Path]::GetFullPath($_).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
    })
    if ($allowed.Count -eq 0) { throw "RX build workspace is outside the dedicated workspace roots: $full" }
    if (Test-Path -LiteralPath $full) {
        if ((Get-Item -LiteralPath $full -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'RX build workspace cleanup does not accept a reparse point.'
        }
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

function Remove-RxProjectBuildDirectory {
    param([Parameter(Mandatory = $true)][string]$ProjectPath)
    $project = (Resolve-Path -LiteralPath $ProjectPath -ErrorAction Stop).Path.TrimEnd('\', '/')
    $build = [IO.Path]::GetFullPath((Join-Path $project 'HardwareDebug'))
    if (-not $build.StartsWith($project + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $build) -ne 'HardwareDebug') {
        throw 'RX generated build directory is outside the selected project.'
    }
    if (Test-Path -LiteralPath $build) {
        if ((Get-Item -LiteralPath $build -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'RX generated build cleanup does not accept a reparse point.'
        }
        Remove-Item -LiteralPath $build -Recurse -Force
    }
}

function Invoke-RxE2StudioBuild {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string]$WorkspacePath,
        [Parameter(Mandatory = $true)][string[]]$ProjectPaths,
        [Parameter(Mandatory = $true)][string[]]$BuildTargets,
        [Parameter(Mandatory = $true)][string]$OutputLog,
        [ValidateRange(1, 2147483)][int]$TimeoutSeconds = 600,
        [switch]$AllowTimeoutExitCode
    )

    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw 'RX e2studio-cli builds require PowerShell 7.'
    }
    $tool = (Resolve-Path -LiteralPath $Executable -ErrorAction Stop).Path
    if ((Split-Path -Leaf $tool) -ine 'e2studio-cli.exe') {
        throw 'RX builds require the e2studio-cli.exe project command launcher.'
    }
    $workspace = [IO.Path]::GetFullPath($WorkspacePath)
    $log = [IO.Path]::GetFullPath($OutputLog)
    [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log))
    $utf8 = [Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText($log, '', $utf8)

    $commands = [Collections.Generic.List[object]]::new()
    $projectNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($project in $ProjectPaths) {
        $path = (Resolve-Path -LiteralPath $project -ErrorAction Stop).Path
        $descriptor = Join-Path $path '.project'
        if (-not (Test-Path -LiteralPath $descriptor -PathType Leaf)) {
            throw "e2 studio project descriptor is missing: $descriptor"
        }
        $xml = [Xml.XmlDocument]::new()
        $xml.Load($descriptor)
        $name = $xml.SelectSingleNode('/projectDescription/name')
        if (-not $name -or [string]::IsNullOrWhiteSpace($name.InnerText) -or
            -not $projectNames.Add($name.InnerText)) {
            throw 'e2 studio project names must be non-empty and unique.'
        }
        $commands.Add(@{ phase = 'import'; arguments = @('project', 'import', $path) })
    }
    foreach ($target in $BuildTargets) {
        $parts = $target.Split('/')
        if ($parts.Count -ne 2 -or -not $projectNames.Contains($parts[0]) -or
            [string]::IsNullOrWhiteSpace($parts[1])) {
            throw "Build target must identify an imported project/configuration: $target"
        }
        # CLI selectors accept regular expressions. Quote an exact project and
        # configuration so a name containing punctuation cannot select siblings.
        $selector = '^' + [regex]::Escape($target) + '$'
        $commands.Add(@{ phase = 'build'; arguments = @('project', 'build', $selector) })
    }
    if ($commands.Count -eq 0 -or $BuildTargets.Count -eq 0) {
        throw 'At least one RX project and build target are required.'
    }

    # Keep import-time metadata in memory. Parent helpers restore source files
    # in finally; only a rejected configuration persists these private snapshots.
    $importSnapshots = [Collections.Generic.List[object]]::new()
    $captureMetadata = {
        param([string]$Phase)
        $files = @{}
        foreach ($project in $ProjectPaths) {
            foreach ($file in Get-ChildItem -LiteralPath $project -File -Force) {
                if ($file.Name -in @('.project', '.cproject') -or $file.Extension -eq '.rcpc') {
                    $files[$file.FullName] = [IO.File]::ReadAllBytes($file.FullName)
                }
            }
        }
        [void]$importSnapshots.Add(@{ phase = $Phase; files = $files })
    }
    & $captureMetadata 'before-imports'

    $timer = [Diagnostics.Stopwatch]::StartNew()
    foreach ($command in $commands) {
        $remainingMs = [Math]::Floor(($TimeoutSeconds * 1000.0) - $timer.Elapsed.TotalMilliseconds)
        if ($remainingMs -le 0) {
            if ($AllowTimeoutExitCode) { return 124 }
            throw "e2studio-cli import/build timed out after $TimeoutSeconds seconds. See $log"
        }
        $arguments = @('-nosplash', '-data', $workspace) + $command.arguments
        $psi = [Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = $tool
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        foreach ($argument in $arguments) { [void]$psi.ArgumentList.Add($argument) }
        [IO.File]::AppendAllText($log, '+ e2studio-cli ' + ($arguments -join ' ') + [Environment]::NewLine, $utf8)
        Write-Host "e2studio-cli project $($command.phase); output: $log"
        $process = [Diagnostics.Process]::Start($psi)
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $timedOut = -not $process.WaitForExit([int]$remainingMs)
        if ($timedOut) {
            try { $process.Kill($true) }
            catch { throw "Could not terminate timed-out e2studio-cli: $($_.Exception.Message)" }
            if (-not $process.WaitForExit(10000)) {
                throw 'Timed-out e2studio-cli is still running; make fallback is unsafe.'
            }
        }
        $process.WaitForExit()
        $stdout.Wait()
        $stderr.Wait()
        $text = [string]::Join([Environment]::NewLine, @($stdout.Result, $stderr.Result))
        [IO.File]::AppendAllText($log, $text + [Environment]::NewLine, $utf8)
        if ($command.phase -eq 'import') {
            & $captureMetadata ('after-import-' + $importSnapshots.Count)
        }
        if ($timedOut) {
            if ($AllowTimeoutExitCode) { return 124 }
            throw "e2studio-cli import/build timed out after $TimeoutSeconds seconds. See $log"
        }
        if ($text -match '(?im)^No Config matched\b') {
            try {
                $diagnostics = Join-Path ([IO.Path]::GetTempPath()) ('rx-e2-import-' + [guid]::NewGuid().ToString('N'))
                [void](New-Item -ItemType Directory -Path $diagnostics)
                $index = [Collections.Generic.List[object]]::new()
                for ($number = 0; $number -lt $importSnapshots.Count; $number++) {
                    $snapshot = $importSnapshots[$number]
                    $folder = Join-Path $diagnostics ([string]$number)
                    [void](New-Item -ItemType Directory -Path $folder)
                    $mapping = @{}
                    foreach ($path in @($snapshot.files.Keys | Sort-Object)) {
                        $filename = [string]$mapping.Count + '-' + [IO.Path]::GetFileName($path)
                        [IO.File]::WriteAllBytes((Join-Path $folder $filename), $snapshot.files[$path])
                        $mapping[$path] = [string]$number + '/' + $filename
                    }
                    [void]$index.Add(@{ phase = $snapshot.phase; files = $mapping })
                }
                [IO.File]::WriteAllText((Join-Path $diagnostics 'index.json'), (ConvertTo-Json -InputObject @($index.ToArray()) -Depth 5), $utf8)
                $workspaceLog = Join-Path $workspace '.metadata/.log'
                if (Test-Path -LiteralPath $workspaceLog -PathType Leaf) {
                    Copy-Item -LiteralPath $workspaceLog -Destination (Join-Path $diagnostics 'workspace.log')
                }
                [IO.File]::AppendAllText($log, 'Private import metadata diagnostics: ' + $diagnostics + [Environment]::NewLine, $utf8)
            } catch {
                [IO.File]::AppendAllText($log, 'Could not preserve import metadata diagnostics.' + [Environment]::NewLine, $utf8)
            }
        }
        # The installed launcher returns zero even when an import path cannot
        # be found or no workspace was supplied. Reject those command failures.
        if ($text -match '(?im)^(?:Command requires a workspace\.|Project: .+ can\x27t be found|Unknown command\b|Error importing\b|Import failed\b|No Config matched\b)') {
            throw "e2studio-cli $($command.phase) was rejected. See $log"
        }
        if ($process.ExitCode -ne 0) { return $process.ExitCode }
    }
    return 0
}

# CLI and legacy Crypto come from monorepos; their selected source directories
# have no nested dependencies. Other runtime/test roots retain their pinned
# recursive dependencies. Source-copy IDT builds must already contain them.
function Initialize-RxBuildDependencies {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)
    $root = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
    $gitRoot = & git -C $root rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($gitRoot).TrimEnd('\', '/') -ine $root.TrimEnd('\', '/')) {
        return
    }
    $sourceOnly = @('Middleware/FreeRTOS-Plus-CLI', 'Middleware/freertos_plus')
    $rows = @(& git -C $root config --file .gitmodules --get-regexp '^submodule\..*\.path$')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read pinned RX dependency paths.' }
    $include = & git -C $root config --get include.path 2>$null
    foreach ($row in $rows) {
        $parts = $row -split '\s+', 2
        if ($parts.Count -ne 2) { throw 'Invalid submodule path entry.' }
        $relative = $parts[1]
        if ($sourceOnly -contains $relative) { continue }
        $dependency = Join-Path $root $relative
        if (-not (Test-Path -LiteralPath (Join-Path $dependency '.gitmodules') -PathType Leaf)) { continue }
        $arguments = @('-C', $dependency)
        if ($include) { $arguments += @('-c', "include.path=$include") }
        $arguments += @('submodule', 'update', '--init', '--recursive', '--depth', '1')
        $messages = & git @arguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Pinned nested dependency initialization failed: $relative"
        }
    }
}

function Assert-RxCommonKernel {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)
    $guard = Join-Path $ProjectRoot 'tools/ci/check_common_kernel.py'
    if (-not (Test-Path -LiteralPath $guard -PathType Leaf)) {
        throw 'Common Kernel/SC regeneration guard is missing.'
    }
    $python = if ($env:RX72N_IDT_PYTHON) { $env:RX72N_IDT_PYTHON } else { 'python' }
    & $python $guard --repo-root $ProjectRoot
    if ($LASTEXITCODE -ne 0) { throw 'Shared Kernel or SC configuration drifted; preserve the generated files and inspect the guard failure.' }
}

# Shared RX project import/build adapter for the Renesas command-line launcher.
# Import every project, then build exact configurations in one standard CDT JVM.

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

# Hash public source inputs only. Generated build directories and submodule
# contents are not project-generation inputs. Keep caller-injected profiles as
# the baseline; callers restore their intentional edits in finally.
function Get-RxE2StudioProjectInputState {
    param([string[]]$ProjectPaths, [string[]]$BuildDirectories, [string[]]$ExcludedPaths, [switch]$RejectUntracked)
    $state = @{}
    foreach ($project in $ProjectPaths) {
        $root = (Resolve-Path -LiteralPath $project -ErrorAction Stop).Path.TrimEnd('\', '/')
        $untracked = @{}
        $gitFiles = @(& git -C $root ls-files --error-unmatch -- .project 2>$null)
        if ($LASTEXITCODE -eq 0 -and $gitFiles.Count -gt 0) {
            $inventory = (@(& git -C $root ls-files -z --cached --others --exclude-standard -- .) -join "`n")
            if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate RX project source inputs.' }
            $files = @($inventory -split "`0" | Where-Object { $_ } | ForEach-Object { Join-Path $root $_ })
            if ($RejectUntracked) {
                $others = (@(& git -C $root ls-files -z --others --exclude-standard -- .) -join "`n")
                if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate unregistered RX source inputs.' }
                foreach ($other in @($others -split "`0" | Where-Object { $_ })) {
                    $untracked[[IO.Path]::GetFullPath((Join-Path $root $other))] = $true
                }
            }
        } else {
            # Source-copy IDT projects have no Git metadata. Do not descend into
            # their supplied dependency trees or the disposable IDE workspace.
            $files = [Collections.Generic.List[string]]::new()
            $pending = [Collections.Generic.Stack[string]]::new()
            $pending.Push($root)
            while ($pending.Count -gt 0) {
                foreach ($item in Get-ChildItem -LiteralPath $pending.Pop() -Force -ErrorAction Stop) {
                    if ($item.PSIsContainer) {
                        if ($item.Name -notin (@('.git', '.metadata', 'lib') + $BuildDirectories) -and
                            -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                            $pending.Push($item.FullName)
                        }
                    } else { $files.Add($item.FullName) }
                }
            }
        }
        foreach ($path in $files) {
            $full = [IO.Path]::GetFullPath($path)
            $relative = [IO.Path]::GetRelativePath($root, $full)
            if (($relative -split '[\\/]')[0] -in $BuildDirectories -or $full -in $ExcludedPaths) { continue }
            if (Test-Path -LiteralPath $full -PathType Leaf) {
                if ($RejectUntracked -and $untracked.ContainsKey($full)) {
                    throw "RX project has unregistered source inputs; inspect or register before retrying: $full"
                }
                $state[$full] = (Get-FileHash -LiteralPath $full -Algorithm SHA256 -ErrorAction Stop).Hash
            }
        }
    }
    return $state
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
        [string[]]$ExpectedOutputs = @(),
        # Accepted for caller compatibility; timeouts never permit make fallback.
        [switch]$AllowTimeoutExitCode
    )

    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw 'RX e2studio-cli builds require PowerShell 7.'
    }
    $tool = (Resolve-Path -LiteralPath $Executable -ErrorAction Stop).Path
    if ((Split-Path -Leaf $tool) -ine 'e2studio-cli.exe') {
        throw 'RX builds require the e2studio-cli.exe command launcher.'
    }
    $workspace = [IO.Path]::GetFullPath($WorkspacePath)
    $log = [IO.Path]::GetFullPath($OutputLog)
    [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log))
    $utf8 = [Text.UTF8Encoding]::new($false)

    $importArguments = [Collections.Generic.List[string]]::new()
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
        [void]$importArguments.Add('-import')
        [void]$importArguments.Add($path)
    }
    $buildArguments = [Collections.Generic.List[string]]::new()
    foreach ($target in $BuildTargets) {
        $parts = $target.Split('/')
        if ($parts.Count -ne 2 -or -not $projectNames.Contains($parts[0]) -or
            [string]::IsNullOrWhiteSpace($parts[1])) {
            throw "Build target must identify an imported project/configuration: $target"
        }
        # CLI selectors accept regular expressions. Quote an exact project and
        # configuration so a name containing punctuation cannot select siblings.
        $selector = '^' + [regex]::Escape($target) + '$'
        [void]$buildArguments.Add('-build')
        [void]$buildArguments.Add($selector)
    }
    if ($projectNames.Count -eq 0 -or $BuildTargets.Count -eq 0) {
        throw 'At least one RX project and build target are required.'
    }

    $buildDirectories = @($BuildTargets | ForEach-Object { ($_ -split '/')[1] })
    $expected = @($ExpectedOutputs | ForEach-Object {
        if (-not [IO.Path]::IsPathFullyQualified($_)) { throw 'Expected RX build outputs must use absolute paths.' }
        [IO.Path]::GetFullPath($_)
    })
    $inputState = Get-RxE2StudioProjectInputState -ProjectPaths $ProjectPaths `
        -BuildDirectories $buildDirectories -ExcludedPaths (@($log) + $expected) -RejectUntracked
    # A preflight rejection must not overwrite the preceding failed run's log.
    [IO.File]::WriteAllText($log, '', $utf8)
    $buildStartUtc = [DateTime]::UtcNow

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
    $remainingMs = [Math]::Floor(($TimeoutSeconds * 1000.0) - $timer.Elapsed.TotalMilliseconds)
    if ($remainingMs -le 0) {
        throw "e2studio-cli import/build timed out after $TimeoutSeconds seconds. See $log"
    }
    $arguments = @('-nosplash', '-data', $workspace, '-application',
        'org.eclipse.cdt.managedbuilder.core.headlessbuild') +
        $importArguments.ToArray() + $buildArguments.ToArray()
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $tool
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    foreach ($argument in $arguments) { [void]$psi.ArgumentList.Add($argument) }
    [IO.File]::AppendAllText($log, '+ e2studio-cli ' + ($arguments -join ' ') + [Environment]::NewLine, $utf8)
    Write-Host "e2studio-cli headless import/build; output: $log"
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
    # An exited launcher can leave an orphan holding its output pipes. Drain
    # both streams only within the remaining import/build budget, never forever.
    # After a timeout kill, allow a bounded grace to retain the terminated tool's
    # private output; this never permits a make fallback.
    $drainWaitMs = if ($timedOut) { 5000 } else {
        [Math]::Max(0, [Math]::Floor(($TimeoutSeconds * 1000.0) - $timer.Elapsed.TotalMilliseconds))
    }
    $streams = [Threading.Tasks.Task]::WhenAll([Threading.Tasks.Task[]]@($stdout, $stderr))
    if (-not $streams.Wait([int]$drainWaitMs)) {
        [IO.File]::AppendAllText($log, 'Output drain timed out; make fallback is unsafe.' + [Environment]::NewLine, $utf8)
        throw "e2studio-cli output drain timed out after $TimeoutSeconds seconds; make fallback is unsafe. See $log"
    }
    $text = [string]::Join([Environment]::NewLine, @($stdout.Result, $stderr.Result))
    [IO.File]::AppendAllText($log, $text + [Environment]::NewLine, $utf8)
    & $captureMetadata 'after-headless-run'
    $afterState = Get-RxE2StudioProjectInputState -ProjectPaths $ProjectPaths `
        -BuildDirectories $buildDirectories -ExcludedPaths (@($log) + $expected)
    $changed = @(@($inputState.Keys) + @($afterState.Keys) | Sort-Object -Unique | Where-Object {
        -not $inputState.ContainsKey($_) -or -not $afterState.ContainsKey($_) -or
        $inputState[$_] -ne $afterState[$_]
    })
    if ($changed.Count -gt 0) {
        # Paths and hashes suffice; never print or archive source/header bodies.
        $changes = @($changed | ForEach-Object {
            [ordered]@{
                path = $_
                change = if (-not $inputState.ContainsKey($_)) { 'added' } elseif (-not $afterState.ContainsKey($_)) { 'deleted' } else { 'modified' }
                before_sha256 = $inputState[$_]
                after_sha256 = $afterState[$_]
            }
        })
        [IO.File]::AppendAllText($log, 'Unexpected RX project input changes:' + [Environment]::NewLine +
            (ConvertTo-Json -InputObject $changes -Depth 3 -Compress) + [Environment]::NewLine, $utf8)
    }
    if ($timedOut) {
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
        throw "e2studio-cli headless build was rejected. See $log"
    }
    if ($process.ExitCode -ne 0) {
        throw "e2studio-cli failed with exit code $($process.ExitCode). See $log"
    }
    # The launcher can return zero after CC-RX/compiler/assembler/linker errors.
    # CC-RX manual Table 10.1: C internal, E error, F fatal; W/M continue.
    # Inspect diagnostic codes, not arbitrary words that may occur in warnings.
    if ($text -match '(?im)\b[CEF]05\d{5}\b') {
        throw "e2studio-cli reported a compiler, assembler or linker error. See $log"
    }
    if ($changed.Count -gt 0) {
        throw "e2studio-cli changed project inputs unexpectedly; preserve the log and inspect before retrying. See $log"
    }
    foreach ($output in $expected) {
        if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
            throw "Expected RX build output is missing: $output"
        }
        $item = Get-Item -LiteralPath $output
        if ($item.Length -eq 0 -or $item.LastWriteTimeUtc -lt $buildStartUtc) {
            throw "Expected RX build output is empty or stale: $output"
        }
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

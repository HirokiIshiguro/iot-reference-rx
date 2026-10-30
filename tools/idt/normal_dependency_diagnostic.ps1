param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [switch]$InnerInitialize
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$PSNativeCommandUseErrorActionPreference=$false
$Original='83489f135c0382ef7879612b5cde03844f2d399c'
$HelperHash='5c628ddd6547073f1e2c00d94cbf6cb0374ed8da10e612036c4fbb582b4a399c'
$GitmodulesHash='71e76626e8c266fecc1d86427fc3a4c4e26bd18d9330c90f084a3b5f8a8eb247'
$GitlinksHash='e2f5304be12b2d1e1aab9d0ebe8739e73c9fc7ae42202818d5463cce315574ae'
$SourceOnly=@('Middleware/FreeRTOS-Plus-CLI','Middleware/freertos_plus')
function Require($Condition,[string]$Code) { if(-not $Condition){throw $Code} }
function Digest([byte[]]$Bytes) { [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant() }
function SourceHash([string]$Path) {
    $bytes=[IO.File]::ReadAllBytes($Path)
    Require (-not($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191)) 'SOURCE_BOM'
    $text=[Text.UTF8Encoding]::new($false,$true).GetString($bytes).Replace("`r`n","`n")
    Require (-not $text.Contains("`r")) 'SOURCE_LONE_CR'
    Digest ([Text.Encoding]::UTF8.GetBytes($text))
}
function Unlinked([string]$Path) {
    $item=Get-Item -Force -LiteralPath $Path
    while($null -ne $item) {
        Require (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'LINKED_SOURCE'
        $item=if($item -is [IO.DirectoryInfo]){$item.Parent}else{$item.Directory}
    }
}
function Capture([string]$Executable,[string[]]$Arguments,[int]$Seconds) {
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$Executable; $start.UseShellExecute=$false; $start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
    $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true)
    $start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
    foreach($argument in $Arguments) { $start.ArgumentList.Add($argument) }
    $start.Environment['GIT_TERMINAL_PROMPT']='0'
    $start.Environment['GIT_NO_LAZY_FETCH']='1'
    $process=[Diagnostics.Process]::new(); $process.StartInfo=$start; $started=$false; $captured=$null
    try {
        Require ($process.Start()) 'OWNED_CHILD_START'
        $started=$true; $clock=[Diagnostics.Stopwatch]::StartNew()
        $streams=@($process.StandardOutput.BaseStream,$process.StandardError.BaseStream)
        $buffers=@([byte[]]::new(4096),[byte[]]::new(4096))
        $captured=@([IO.MemoryStream]::new(),[IO.MemoryStream]::new())
        $done=@($false,$false)
        $pending=@($streams[0].ReadAsync($buffers[0],0,4096),$streams[1].ReadAsync($buffers[1],0,4096))
        while(-not($done[0] -and $done[1] -and $process.HasExited)) {
            if($clock.Elapsed.TotalSeconds -gt $Seconds){throw 'OWNED_CHILD_TIME_BUDGET'}
            foreach($index in 0,1) {
                if(-not $done[$index] -and $pending[$index].IsCompleted) {
                    $count=$pending[$index].GetAwaiter().GetResult()
                    if($count -eq 0){$done[$index]=$true;continue}
                    Require (($captured[0].Length+$captured[1].Length+$count) -le 1048576) 'OWNED_CHILD_OUTPUT_BOUND'
                    $captured[$index].Write($buffers[$index],0,$count)
                    $pending[$index]=$streams[$index].ReadAsync($buffers[$index],0,4096)
                }
            }
            Start-Sleep -Milliseconds 10
        }
        $encoding=[Text.UTF8Encoding]::new($false,$true)
        $stdout=$encoding.GetString($captured[0].ToArray()); $stderr=$encoding.GetString($captured[1].ToArray())
        return @{code=$process.ExitCode;stdout=$stdout;stderr=$stderr}
    } finally {
        if($started -and -not $process.HasExited) { $process.Kill($true); Require ($process.WaitForExit(5000)) 'OWNED_CHILD_STOP_UNKNOWN' }
        if($null -ne $captured){foreach($stream in $captured){$stream.Dispose()}}
        $process.Dispose()
    }
}
function GitCapture([string[]]$Arguments) { Capture $script:GitExe (@('--no-optional-locks')+$Arguments) 20 }
$currentDependencyId=$null
$result=@{schema_version=1;result='HOLD';reasonCode='DEPENDENCY_DIAGNOSTIC_HOLD';initializer_invoked=$false;
          initializer_succeeded=$false;raw_git_output_saved=$false;hardware_actions=0;sdk_aws_actions=0}
try {
    Require ($PSVersionTable.PSVersion.Major -eq 7 -and $PSVersionTable.PSVersion -ge [version]'7.2') 'POWERSHELL7_REQUIRED'
    Require ($env:CI_PROJECT_ID -ceq '38' -and $env:CI_PIPELINE_SOURCE -ceq 'api' -and $env:GITLAB_USER_ID -ceq '38') 'CI_IDENTITY'
    Require ($env:CI_JOB_NAME -ceq 'test_rx65n_bg96_idt' -and $env:IDT_TARGET -ceq 'rx65n-bg96' -and $env:IDT_SCOPE -ceq 'transport') 'CI_SELECTOR'
    Require ($env:GIT_SUBMODULE_STRATEGY -ceq 'normal' -and $env:GIT_STRATEGY -ceq 'clone') 'NORMAL_CLONE_REQUIRED'
    $root=(Resolve-Path -LiteralPath $ProjectRoot).Path
    Require ($root -ceq (Resolve-Path -LiteralPath $env:CI_PROJECT_DIR).Path) 'CI_CHECKOUT_ROOT'
    Unlinked $root
    $helper=Join-Path $root 'tools/rx_e2studio_cli.ps1'
    Unlinked $helper; Unlinked (Join-Path $root '.gitmodules')
    Require ((SourceHash $helper) -ceq $HelperHash -and (SourceHash (Join-Path $root '.gitmodules')) -ceq $GitmodulesHash) 'ORIGINAL_SOURCE_HASH'
    $script:GitExe=(Get-Command git.exe -CommandType Application -ErrorAction Stop).Source
    $rootTop=GitCapture @('-C',$root,'rev-parse','--show-toplevel')
    Require ($rootTop.code -eq 0 -and [IO.Path]::GetFullPath($rootTop.stdout.Trim()).TrimEnd('\','/') -ieq [IO.Path]::GetFullPath($root).TrimEnd('\','/')) 'ROOT_TOPLEVEL_MISMATCH'
    $rows=GitCapture @('-C',$root,'config','--file','.gitmodules','--get-regexp','^submodule\..*\.path$')
    Require ($rows.code -eq 0) 'ROOT_DEPENDENCY_METADATA'
    $dependencies=@(); $lookup=@{}
    foreach($line in ($rows.stdout -split '\r?\n' | Where-Object {$_})) {
        $parts=$line -split '\s+',2
        Require ($parts.Count -eq 2 -and $parts[1] -cmatch '^[A-Za-z0-9_.+/-]+$' -and '..' -cnotin ($parts[1] -split '/')) 'DEPENDENCY_PATH_SCHEMA'
        $relative=$parts[1]; $id='DEP_{0:D2}' -f ($dependencies.Count+1)
        $dependencies+=@{id=$id;relative=$relative}; $lookup[$relative]=$id
    }
    Require ($dependencies.Count -eq 41) 'DEPENDENCY_COUNT'
    if($InnerInitialize) {
        # No proxy and no replacement implementation: invoke the pinned function.
        . $helper *> $null
        $result.initializer_invoked=$true
        try {
            $discard=@(Initialize-RxBuildDependencies -ProjectRoot $root *>&1)
            $exit=$global:LASTEXITCODE
            $discard=$null
            $result.initializer_succeeded=$true
            $result.result='INITIALIZER_COMPLETED'; $result.reasonCode='INITIALIZER_COMPLETED'; $result.git_exit_code=if($null -eq $exit){$null}else{[int]$exit}
        } catch {
            $exit=$global:LASTEXITCODE; $message=$_.Exception.Message
            $result.git_exit_code=if($null -eq $exit){$null}else{[int]$exit}
            if($message -cmatch '^Pinned nested dependency initialization failed: ([A-Za-z0-9_.+/-]+)$' -and $lookup.ContainsKey($Matches[1])) {
                $result.failed_dependency_id=$lookup[$Matches[1]]
                $result.reasonCode='NESTED_INITIALIZATION_FAILED'
            } else { $result.reasonCode='INITIALIZER_UNCLASSIFIED_FAILURE' }
            $message=$null; $discard=$null
        }
    } else {
        $head=GitCapture @('-C',$root,'rev-parse','HEAD')
        Require ($head.code -eq 0 -and $head.stdout.Trim() -ceq $env:CI_COMMIT_SHA) 'CI_SOURCE_HEAD'
        $changed=GitCapture @('-C',$root,'diff','--name-only',$Original,'HEAD')
        Require ($changed.code -eq 0) 'SOURCE_DIFF_UNAVAILABLE'
        $allowed=@('.gitlab-ci.yml','tools/idt/run_idt.py','tools/idt/owned_run_diagnostic.py','tools/idt/normal_dependency_diagnostic.ps1')
        Require (@($changed.stdout -split '\r?\n' | Where-Object {$_ -and $_ -cnotin $allowed}).Count -eq 0) 'UNREVIEWED_SOURCE_DELTA'
        $clean=GitCapture @('-C',$root,'diff','--name-only','--ignore-submodules=all','HEAD')
        Require ($clean.code -eq 0 -and -not $clean.stdout.Trim()) 'TRACKED_SOURCE_DIRTY'
        $tree=GitCapture @('-C',$root,'ls-tree','-r','-z','HEAD')
        Require ($tree.code -eq 0) 'GITLINK_METADATA'
        $pins=@{}
        foreach($record in ($tree.stdout -split "`0")) {
            if($record -cmatch '^160000 commit ([0-9a-f]{40})\t(.+)$') { $pins[$Matches[2]]=$Matches[1] }
        }
        [string[]]$keys=@($pins.Keys); [Array]::Sort($keys,[StringComparer]::Ordinal)
        $manifest=(@($keys | ForEach-Object {$_+'='+$pins[$_]}) -join "`n")+"`n"
        Require ($pins.Count -eq 41 -and (Digest ([Text.Encoding]::UTF8.GetBytes($manifest))) -ceq $GitlinksHash) 'ORIGINAL_GITLINKS_CHANGED'
        $public=@(); $nested=0
        foreach($dependency in $dependencies) {
            $currentDependencyId=$dependency.id
            $path=Join-Path $root $dependency.relative; Unlinked $path
            $top=GitCapture @('-C',$path,'rev-parse','--show-toplevel')
            $initialized=$top.code -eq 0 -and [IO.Path]::GetFullPath($top.stdout.Trim()).TrimEnd('\','/') -ieq [IO.Path]::GetFullPath($path).TrimEnd('\','/')
            Require $initialized 'ROOT_DEPENDENCY_NOT_INITIALIZED'
            $pin=GitCapture @('-C',$path,'rev-parse','HEAD')
            $status=GitCapture @('-C',$path,'status','--porcelain=v1','--untracked-files=all','--ignore-submodules=none')
            $shallow=GitCapture @('-C',$path,'rev-parse','--is-shallow-repository')
            Require ($pin.code -eq 0 -and $status.code -eq 0 -and $shallow.code -eq 0 -and $shallow.stdout.Trim() -cin @('true','false')) 'DEPENDENCY_METADATA_FAILED'
            $pinMatches=$pin.stdout.Trim() -ceq $pins[$dependency.relative]
            Require $pinMatches 'ROOT_PIN_MISMATCH'
            $descriptor=Test-Path -LiteralPath (Join-Path $path '.gitmodules') -PathType Leaf
            if($descriptor -and $dependency.relative -cnotin $SourceOnly){$nested++}
            $public+=@{dependency_id=$dependency.id;initialized=$initialized;head_matches_source_pin=$pinMatches;dirty=[bool]$status.stdout.Trim();shallow=($shallow.stdout.Trim() -ceq 'true');nested_descriptor_present=$descriptor;source_only_excluded=($dependency.relative -cin $SourceOnly)}
            $result.dependencies=$public
        }
        $currentDependencyId=$null
        $result.dependencies=$public; $result.expected_nested_update_attempts=$nested
        Require ($nested -gt 0) 'INITIALIZER_NOT_EXERCISED'
        $pwsh=(Get-Process -Id $PID).Path
        $child=Capture $pwsh @('-NoProfile','-NonInteractive','-File',$PSCommandPath,'-ProjectRoot',$root,'-InnerInitialize') 300
        Require ($child.code -eq 0 -and -not $child.stderr.Trim()) 'INITIALIZER_LAUNCHER_HOLD'
        $inner=$child.stdout | ConvertFrom-Json -AsHashtable
        Require ($inner.schema_version -eq 1 -and $inner.initializer_invoked -is [bool] -and $inner.initializer_invoked -and $inner.initializer_succeeded -is [bool]) 'INITIALIZER_RESULT_SCHEMA'
        $result.initializer=$inner; $result.initializer_invoked=$inner.initializer_invoked; $result.initializer_succeeded=$inner.initializer_succeeded
        $result.result='DEPENDENCY_DIAGNOSTIC_OBSERVED'; $result.reasonCode='DEPENDENCY_DIAGNOSTIC_OBSERVED'
    }
} catch {
    $code=$_.Exception.Message
    $result.reasonCode=if($code -cmatch '^[A-Z_]{1,80}$'){$code}else{'DEPENDENCY_DIAGNOSTIC_HOLD'}
    if($currentDependencyId -cmatch '^DEP_(?:0[1-9]|[1-3][0-9]|4[01])$'){$result.metadata_failed_dependency_id=$currentDependencyId}
}
# Only fixed-schema data leaves this process. No Git/config/native error is printed.
$result | ConvertTo-Json -Depth 8 -Compress
exit 0

Set-StrictMode -Version Latest

function New-LanbenchOwner {
    param([string] $ProjectId, [string] $PipelineId, [string] $JobId, [string] $RunId)
    foreach ($value in @($ProjectId, $PipelineId, $JobId)) {
        if ($value -cnotmatch '^[1-9][0-9]*$') { throw 'LANBENCH requires explicit GitLab project, pipeline and creator job IDs.' }
    }
    if ($RunId -cnotmatch '^[0-9a-f]{32}$') { throw 'Invalid LANBENCH run identity.' }
    return [ordered]@{ project_id = $ProjectId; pipeline_id = $PipelineId; job_id = $JobId; run_id = $RunId }
}

function Get-LanbenchOwnerTags {
    param($Owner)
    return [ordered]@{ Project = 'iot-reference-rx'; Purpose = 'lanbench-tls13-0rtt';
        GitLabProjectId = $Owner.project_id; GitLabPipelineId = $Owner.pipeline_id;
        GitLabJobId = $Owner.job_id; RunId = $Owner.run_id }
}

function New-LanbenchTagSpecification {
    param([string] $ResourceType, [string] $Name, $Owner)
    if ($Name -cnotmatch '^[A-Za-z0-9_.-]{1,220}$') { throw 'LANBENCH resource names must use letters, digits, dots, underscores or hyphens.' }
    $tags = Get-LanbenchOwnerTags $Owner
    $values = @("{Key=Name,Value=$Name}")
    foreach ($key in $tags.Keys) { $values += "{Key=$key,Value=$($tags[$key])}" }
    return "ResourceType=$ResourceType,Tags=[$($values -join ',')]"
}

function Assert-LanbenchOwner {
    param($Resource, $Owner)
    $actual = @{}
    foreach ($tag in @($Resource.Tags)) {
        if ($actual.ContainsKey([string]$tag.Key)) { throw 'Duplicate EC2 ownership tag.' }
        $actual[[string]$tag.Key] = [string]$tag.Value
    }
    $expected = Get-LanbenchOwnerTags $Owner
    foreach ($key in $expected.Keys) {
        if (-not $actual.ContainsKey($key) -or $actual[$key] -cne [string]$expected[$key]) {
            throw 'EC2 resource ownership does not match this LANBENCH run.'
        }
    }
}

function Write-LanbenchJournal {
    param([string] $Path, $Value)
    $absolute = [IO.Path]::GetFullPath($Path)
    $parent = Split-Path -Parent $absolute
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temporary = Join-Path $parent ('.lanbench-journal-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $absolute -Force
    } finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Invoke-LanbenchAwsText {
    param([string[]] $Arguments, [string] $AwsCli = 'aws')
    $executable = (Get-Command $AwsCli -CommandType Application, ExternalScript -ErrorAction Stop).Source
    $operation = ($Arguments | Select-Object -First 2) -join ' '
    $job = Start-Job -ArgumentList $executable, $Arguments -ScriptBlock {
        param($Executable, [string[]] $Arguments)
        $ErrorActionPreference = 'Stop'
        $global:LASTEXITCODE = 0
        try {
            $output = @(& $Executable @Arguments 2>&1)
            $code = $LASTEXITCODE
            $body = ($output | Out-String)
        } catch {
            $code = if ($LASTEXITCODE -ne 0) { $LASTEXITCODE } else { -1 }
            $body = $_ | Out-String
        }
        [pscustomobject]@{ exit_code = $code; body = $body }
    }
    try {
        while (-not (Wait-Job -Job $job -Timeout 3)) { Write-Host "LANBENCH AWS operation active: $operation" }
        $result = @(Receive-Job -Job $job -ErrorAction Stop)
        if ($job.State -ne 'Completed' -or $result.Count -ne 1) { throw 'LANBENCH AWS command did not finish normally.' }
        if ($result[0].exit_code -ne 0) {
            $failure = [InvalidOperationException]::new("LANBENCH AWS operation failed: $operation")
            $match = [regex]::Match([string]$result[0].body, 'An error occurred \(([A-Za-z0-9.]+)\)')
            if ($match.Success) { $failure.Data['AwsErrorCode'] = $match.Groups[1].Value }
            throw $failure
        }
        return ([string]$result[0].body).Trim()
    } finally {
        if ($job.State -eq 'Running') { Stop-Job -Job $job }
        Remove-Job -Job $job -Force
    }
}

function Invoke-LanbenchAwsJson {
    param([string[]] $Arguments, [string] $AwsCli = 'aws')
    $text = Invoke-LanbenchAwsText -Arguments $Arguments -AwsCli $AwsCli
    if ([string]::IsNullOrWhiteSpace($text) -or $text -eq 'None') { throw 'LANBENCH AWS returned no JSON result.' }
    try { return $text | ConvertFrom-Json } catch { throw 'LANBENCH AWS returned invalid JSON.' }
}

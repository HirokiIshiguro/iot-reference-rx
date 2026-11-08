<#
Compare the current CPU job's Windows SID with local service/runtime owners.
Only the SID hash and comparisons are printed; no account name, raw SID or environment dump.
This reports the current job token, not every job or a security boundary.
#>
param(
    [string]$ServiceName = 'gitlab-runner',
    [string]$VenvRoot = 'C:/ai/codex/tools/venvs/rx72n-idt-windows',
    [string]$WslVenvRoot = 'C:/ai/codex/tools/venvs/rx72n-idt-linux'
)

function Convert-AccountToSid([string]$Account) {
    if (-not $Account) { throw 'identity unavailable' }
    if ($Account.StartsWith('.\')) { $Account = $env:COMPUTERNAME + $Account.Substring(1) }
    return ([System.Security.Principal.NTAccount]::new($Account)).Translate(
        [System.Security.Principal.SecurityIdentifier]).Value
}

function Compare-Owner([string]$Path, [string]$CurrentSid) {
    try {
        $owner = (Get-Acl -LiteralPath $Path -ErrorAction Stop).Owner
        return ((Convert-AccountToSid $owner) -eq $CurrentSid).ToString().ToLowerInvariant()
    } catch { return 'unknown' }
}

try { $current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value }
catch { $current = $null }
if (-not $current) {
    Write-Output 'runner_identity_comparison=unknown'
    return
}

$hasher = [System.Security.Cryptography.SHA256]::Create()
try {
    $digest = $hasher.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($current))
    $sidHash = -join ($digest | ForEach-Object { $_.ToString('x2') })
} finally { $hasher.Dispose() }
Write-Output ('job_sid_sha256=' + $sidHash)

try {
    if ($ServiceName -notmatch '^[A-Za-z0-9_-]+$') { throw 'invalid service name' }
    $service = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction Stop
    if (-not $service) { throw 'service unavailable' }
    $serviceMatch = ((Convert-AccountToSid $service.StartName) -eq $current).ToString().ToLowerInvariant()
} catch { $serviceMatch = 'unknown' }
Write-Output ('job_sid_matches_runner_service=' + $serviceMatch)
Write-Output ('job_sid_matches_windows_venv_owner=' + (Compare-Owner (Join-Path $VenvRoot 'Lib/site-packages') $current))
Write-Output ('job_sid_matches_wsl_venv_owner=' + (Compare-Owner $WslVenvRoot $current))

try {
    $basePath = $null
    foreach ($line in Get-Content -LiteralPath (Join-Path $VenvRoot 'pyvenv.cfg') -ErrorAction Stop) {
        if ($line -match '^\s*home\s*=\s*(.+?)\s*$') { $basePath = $Matches[1]; break }
    }
    if (-not $basePath) { throw 'base interpreter unavailable' }
    $baseMatch = Compare-Owner (Join-Path $basePath 'Lib') $current
} catch { $baseMatch = 'unknown' }
Write-Output ('job_sid_matches_base_python_owner=' + $baseMatch)

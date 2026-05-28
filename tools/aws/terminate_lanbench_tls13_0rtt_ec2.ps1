param(
    [string] $Region = "ap-northeast-1",
    [string] $InstanceName = "iot-reference-rx-lanbench-tls13-0rtt",
    [string] $MetadataJson,
    [string] $OutputJson
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$instanceIds = @()

if ($MetadataJson -and (Test-Path -LiteralPath $MetadataJson)) {
    $meta = Get-Content -LiteralPath $MetadataJson -Raw | ConvertFrom-Json
    if ($meta.instance_id) {
        $instanceIds += [string] $meta.instance_id
    }
}

if ($instanceIds.Count -eq 0) {
    $query = & aws ec2 describe-instances `
        --region $Region `
        --filters "Name=tag:Name,Values=$InstanceName" "Name=instance-state-name,Values=pending,running,stopping,stopped" `
        --query "Reservations[].Instances[].InstanceId" `
        --output text
    if ($LASTEXITCODE -ne 0) {
        throw "failed to query EC2 instances"
    }
    $instanceIds = (($query | Out-String).Trim() -split '\s+') | Where-Object { $_ }
}

$summary = [ordered]@{
    region = $Region
    instance_name = $InstanceName
    instance_ids = $instanceIds
    terminated = $false
}

if ($instanceIds.Count -eq 0) {
    Write-Host "No active LANBENCH TLS 1.3 0-RTT instance found for Name=$InstanceName"
}
else {
    & aws ec2 terminate-instances --region $Region --instance-ids $instanceIds --output json
    & aws ec2 wait instance-terminated --region $Region --instance-ids $instanceIds
    $summary.terminated = $true
    Write-Host "Terminated LANBENCH TLS 1.3 0-RTT instance(s): $($instanceIds -join ', ')"
}

if ($OutputJson) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputJson) | Out-Null
    $summary | ConvertTo-Json -Depth 4 | Set-Content -Path $OutputJson -Encoding ASCII
}

$summary | ConvertTo-Json -Depth 4

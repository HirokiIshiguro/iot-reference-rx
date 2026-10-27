param(
    [string] $Region = "ap-northeast-1",
    [string] $InstanceName = "iot-reference-rx-lanbench-tls13-0rtt",
    [string] $MetadataJson,
    [string] $OutputJson,
    [string] $ProjectId = $env:CI_PROJECT_ID,
    [string] $PipelineId = $env:CI_PIPELINE_ID,
    [string] $AwsCli = 'aws'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lanbench_ec2_ownership.ps1')
function Aws-Text { param([string[]] $Arguments) Invoke-LanbenchAwsText -Arguments $Arguments -AwsCli $AwsCli }
function Aws-Json { param([string[]] $Arguments) Invoke-LanbenchAwsJson -Arguments $Arguments -AwsCli $AwsCli }
function Is-Missing($ErrorRecord, [string] $Code) { return $ErrorRecord.Exception.Data['AwsErrorCode'] -ceq $Code }
function Instance-Description([string] $Id) {
    try {
        $described = Aws-Json @('ec2', 'describe-instances', '--region', $Region, '--instance-ids', $Id, '--output', 'json')
        return @($described.Reservations | ForEach-Object { $_.Instances })
    } catch {
        if (Is-Missing $_ 'InvalidInstanceID.NotFound') { return }
        throw
    }
}

if ([string]::IsNullOrWhiteSpace($OutputJson)) { throw 'LANBENCH cleanup requires a result path.' }
$result = [ordered]@{ passed = $false; state = 'cleanup_failed'; instance_state = 'not_checked';
    instance_ids = @(); volume_ids = @(); security_group_state = 'not_checked' }
try {
    if ([string]::IsNullOrWhiteSpace($MetadataJson) -or -not (Test-Path -LiteralPath $MetadataJson -PathType Leaf)) {
        throw 'The exact LANBENCH creation journal is required; no resource name fallback is permitted.'
    }
    try { $meta = Get-Content -LiteralPath $MetadataJson -Raw | ConvertFrom-Json } catch { throw 'Invalid LANBENCH creation journal.' }
    if ($meta.schema_version -ne 2 -or $meta.resource_kind -cne 'lanbench-ec2' -or
            $meta.region -cne $Region -or $meta.instance_name -cne $InstanceName) { throw 'LANBENCH creation journal does not match the requested cleanup.' }
    $owner = New-LanbenchOwner -ProjectId $ProjectId -PipelineId $PipelineId -JobId $meta.owner.job_id -RunId $meta.owner.run_id
    if ($meta.owner.project_id -cne $owner.project_id -or $meta.owner.pipeline_id -cne $owner.pipeline_id -or
            $meta.client_token -cne $owner.run_id -or $meta.instance_requested -isnot [bool] -or
            $meta.security_group.created_by_run -isnot [bool]) { throw 'LANBENCH journal ownership or state is invalid.' }
    $instanceId = [string]$meta.instance_id
    $instances = @()
    if ($instanceId) {
        if ($instanceId -cnotmatch '^i-[0-9a-f]{8,17}$') { throw 'Invalid recorded instance identity.' }
        $instances = @(Instance-Description $instanceId)
    } elseif ($meta.instance_requested) {
        # A failed launch response may leave an instance. The durable client
        # token and all owner tags are the only permitted recovery lookup.
        $filters = @('Name=client-token,Values=' + $owner.run_id)
        $tags = Get-LanbenchOwnerTags $owner
        foreach ($key in $tags.Keys) { $filters += "Name=tag:$key,Values=$($tags[$key])" }
        $recovered = Aws-Json (@('ec2', 'describe-instances', '--region', $Region, '--filters') + $filters + @('--output', 'json'))
        $instances = @($recovered.Reservations | ForEach-Object { $_.Instances })
        if ($instances.Count -ne 1) { throw 'EC2 creation outcome is unresolved; preserve the ownership journal.' }
        $instanceId = [string]$instances[0].InstanceId
    }
    if ($instances.Count -gt 1) { throw 'Instance lookup is ambiguous.' }
    $volumeIds = @($meta.volume_ids)
    if ($instanceId) { $result.instance_ids = @($instanceId) }
    if ($instances.Count -eq 1) {
        $instance = $instances[0]
        if ($instance.InstanceId -cne $instanceId -or $instance.ClientToken -cne $owner.run_id) { throw 'Instance identity or client token differs from this run.' }
        Assert-LanbenchOwner $instance $owner
        $volumeIds += @($instance.BlockDeviceMappings | ForEach-Object { [string]$_.Ebs.VolumeId })
        $volumeIds = @($volumeIds | Sort-Object -Unique)
        if ($instance.State.Name -cne 'terminated') {
            # Termination can delete attached EBS volumes. Verify their owner
            # before issuing the instance mutation, rather than trusting a name.
            foreach ($mapping in @($instance.BlockDeviceMappings)) {
                if ($mapping.Ebs.DeleteOnTermination -ne $true) { throw 'An attached volume lacks the owned deletion-on-termination contract.' }
                $volumeId = [string]$mapping.Ebs.VolumeId
                $volumes = Aws-Json @('ec2', 'describe-volumes', '--region', $Region, '--volume-ids', $volumeId, '--output', 'json')
                if (@($volumes.Volumes).Count -ne 1 -or $volumes.Volumes[0].VolumeId -cne $volumeId) { throw 'Attached volume description is incomplete.' }
                Assert-LanbenchOwner $volumes.Volumes[0] $owner
            }
            $null = Aws-Text @('ec2', 'terminate-instances', '--region', $Region, '--instance-ids', $instanceId, '--output', 'json')
            $null = Aws-Text @('ec2', 'wait', 'instance-terminated', '--region', $Region, '--instance-ids', $instanceId)
        }
        $remaining = @(Instance-Description $instanceId)
        if ($remaining.Count -gt 1 -or ($remaining.Count -eq 1 -and $remaining[0].State.Name -cne 'terminated')) { throw 'Instance termination was not confirmed.' }
        $result.instance_state = 'terminated'
    } elseif ($instanceId) {
        $result.instance_state = 'already_absent'
    } else {
        $result.instance_state = 'not_requested'
    }
    foreach ($volumeId in $volumeIds) {
        if ([string]$volumeId -cnotmatch '^vol-[0-9a-f]{8,17}$') { throw 'Invalid recorded volume identity.' }
        $null = Aws-Text @('ec2', 'wait', 'volume-deleted', '--region', $Region, '--volume-ids', $volumeId)
    }
    $result.volume_ids = $volumeIds
    $group = $meta.security_group
    if ($group.created_by_run) {
        $groups = @()
        if ($group.id) {
            if ([string]$group.id -cnotmatch '^sg-[0-9a-f]{8,17}$') { throw 'Invalid recorded security group identity.' }
            try {
                $described = Aws-Json @('ec2', 'describe-security-groups', '--region', $Region, '--group-ids', $group.id, '--output', 'json')
                $groups = @($described.SecurityGroups)
            } catch {
                if (-not (Is-Missing $_ 'InvalidGroup.NotFound')) { throw }
            }
        } else {
            if (-not $group.requested -or [string]$group.name -cnotmatch ('-' + $owner.run_id + '$')) { throw 'Security group creation state is incomplete.' }
            $described = Aws-Json @('ec2', 'describe-security-groups', '--region', $Region, '--filters',
                "Name=vpc-id,Values=$($group.vpc_id)", "Name=group-name,Values=$($group.name)", '--output', 'json')
            $groups = @($described.SecurityGroups)
            if ($groups.Count -ne 1) { throw 'Security group creation outcome is unresolved; preserve the ownership journal.' }
        }
        if ($groups.Count -gt 1) { throw 'Security group lookup is ambiguous.' }
        if ($groups.Count -eq 1) {
            $ownedGroup = $groups[0]
            if ($ownedGroup.VpcId -cne $group.vpc_id -or $ownedGroup.GroupName -cne $group.name -or
                    ($group.id -and $ownedGroup.GroupId -cne $group.id)) { throw 'Security group differs from the creation journal.' }
            Assert-LanbenchOwner $ownedGroup $owner
            $null = Aws-Text @('ec2', 'delete-security-group', '--region', $Region, '--group-id', $ownedGroup.GroupId)
            try {
                $stillPresent = Aws-Json @('ec2', 'describe-security-groups', '--region', $Region, '--group-ids', $ownedGroup.GroupId, '--output', 'json')
                if (@($stillPresent.SecurityGroups).Count -ne 0) { throw 'Owned security group deletion was not confirmed.' }
            } catch {
                if (-not (Is-Missing $_ 'InvalidGroup.NotFound')) { throw }
            }
        }
        $result.security_group_state = 'absent'
    } else {
        $result.security_group_state = 'retained_shared'
    }
    $result.passed = $true
    $result.state = 'cleaned'
    Write-LanbenchJournal -Path $OutputJson -Value $result
    Write-Host 'LANBENCH owned EC2 resources are closed.'
} catch {
    $result['error_type'] = $_.Exception.GetType().Name
    Write-LanbenchJournal -Path $OutputJson -Value $result
    throw
}

param(
    [string] $Region = "ap-northeast-1",
    [string] $InstanceName = "iot-reference-rx-lanbench-tls13-0rtt",
    [string] $InstanceType = "t4g.nano",
    [string] $SecurityGroupName = "iot-reference-rx-lanbench-tls13-0rtt-5443",
    [int] $Port = 5443,
    [string] $AmiParameterName = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64",
    [int] $ServerReadyTimeoutSeconds = 900,
    [string] $OutputJson,
    [string] $OutputEnv,
    [string] $ProjectId = $env:CI_PROJECT_ID,
    [string] $PipelineId = $env:CI_PIPELINE_ID,
    [string] $JobId = $env:CI_JOB_ID,
    [string] $AwsCli = 'aws'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lanbench_ec2_ownership.ps1')

function Aws-Text { param([string[]] $Arguments) Invoke-LanbenchAwsText -Arguments $Arguments -AwsCli $AwsCli }
function Aws-Json { param([string[]] $Arguments) Invoke-LanbenchAwsJson -Arguments $Arguments -AwsCli $AwsCli }
function Save-Journal { Write-LanbenchJournal -Path $OutputJson -Value $journal }

function Wait-TcpPort {
    param([string] $HostName, [int] $PortNumber, [int] $TimeoutSeconds)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        Write-Host 'LANBENCH server startup active'
        $client = [Net.Sockets.TcpClient]::new()
        try {
            $connection = $client.BeginConnect($HostName, $PortNumber, $null, $null)
            if ($connection.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds(3))) {
                $client.EndConnect($connection)
                return
            }
        } catch {
            Start-Sleep -Seconds 3
        } finally {
            $client.Dispose()
        }
    }
    throw 'LANBENCH server did not become ready within the existing startup budget.'
}

if ($Port -lt 1 -or $Port -gt 65535 -or $ServerReadyTimeoutSeconds -le 0) { throw 'Invalid LANBENCH readiness input.' }
if ([string]::IsNullOrWhiteSpace($OutputJson) -or (Test-Path -LiteralPath $OutputJson)) { throw 'A new LANBENCH ownership journal path is required.' }
$owner = New-LanbenchOwner -ProjectId $ProjectId -PipelineId $PipelineId -JobId $JobId -RunId ([guid]::NewGuid().ToString('N'))
$null = New-LanbenchTagSpecification -ResourceType 'instance' -Name $InstanceName -Owner $owner
if ($SecurityGroupName -cnotmatch '^[A-Za-z0-9_.-]{1,180}$') { throw 'Invalid configured LANBENCH security group name.' }
$journal = [ordered]@{ schema_version = 2; resource_kind = 'lanbench-ec2'; state = 'preparing';
    region = $Region; instance_name = $InstanceName; instance_id = ''; instance_requested = $false;
    client_token = $owner.run_id; owner = $owner; volume_ids = @(); port = $Port;
    security_group = [ordered]@{ id = ''; name = ''; vpc_id = ''; created_by_run = $false; requested = $false } }
Save-Journal
$userData = $null
try {
    $vpcs = Aws-Json @('ec2', 'describe-vpcs', '--region', $Region, '--filters', 'Name=isDefault,Values=true', '--output', 'json')
    if (@($vpcs.Vpcs).Count -ne 1) { throw 'Expected exactly one default VPC.' }
    $vpcId = [string]$vpcs.Vpcs[0].VpcId
    $subnets = Aws-Json @('ec2', 'describe-subnets', '--region', $Region, '--filters', "Name=vpc-id,Values=$vpcId", 'Name=default-for-az,Values=true', '--output', 'json')
    $available = @($subnets.Subnets | Where-Object { $_.State -eq 'available' -and $_.VpcId -ceq $vpcId } | Sort-Object SubnetId)
    if ($available.Count -eq 0) { throw 'No available default subnet exists.' }
    $subnetId = [string]$available[0].SubnetId
    $groups = Aws-Json @('ec2', 'describe-security-groups', '--region', $Region, '--filters', "Name=vpc-id,Values=$vpcId", "Name=group-name,Values=$SecurityGroupName", '--output', 'json')
    if (@($groups.SecurityGroups).Count -gt 1) { throw 'Configured security group lookup is ambiguous.' }
    if (@($groups.SecurityGroups).Count -eq 1) {
        $group = $groups.SecurityGroups[0]
        $projectTags = @($group.Tags | Where-Object { $_.Key -ceq 'Project' -and $_.Value -ceq 'iot-reference-rx' })
        $ingress = @($group.IpPermissions | Where-Object {
            ($_.IpProtocol -eq '-1' -or ($_.IpProtocol -eq 'tcp' -and $_.FromPort -le $Port -and $_.ToPort -ge $Port)) -and
            @($_.IpRanges | Where-Object { $_.CidrIp -ceq '0.0.0.0/0' }).Count -gt 0
        })
        if ($group.VpcId -cne $vpcId -or $group.GroupName -cne $SecurityGroupName -or $projectTags.Count -ne 1 -or $ingress.Count -eq 0) {
            throw 'Configured shared security group is not a validated LANBENCH input; it was not modified.'
        }
        $journal.security_group.id = [string]$group.GroupId
        $journal.security_group.name = $SecurityGroupName
        $journal.security_group.vpc_id = $vpcId
        Save-Journal
    } else {
        $groupName = $SecurityGroupName + '-' + $owner.run_id
        $journal.security_group.name = $groupName
        $journal.security_group.vpc_id = $vpcId
        $journal.security_group.created_by_run = $true
        $journal.security_group.requested = $true
        Save-Journal
        $created = Aws-Json @('ec2', 'create-security-group', '--region', $Region, '--group-name', $groupName,
            '--description', 'Owned LANBENCH TLS transport peer', '--vpc-id', $vpcId,
            '--tag-specifications', (New-LanbenchTagSpecification 'security-group' $groupName $owner), '--output', 'json')
        if ([string]$created.GroupId -cnotmatch '^sg-[0-9a-f]{8,17}$') { throw 'AWS did not return a security group identity.' }
        $journal.security_group.id = [string]$created.GroupId
        Save-Journal
        $null = Aws-Text @('ec2', 'authorize-security-group-ingress', '--region', $Region, '--group-id', $journal.security_group.id,
            '--ip-permissions', "IpProtocol=tcp,FromPort=$Port,ToPort=$Port,IpRanges=[{CidrIp=0.0.0.0/0}]", '--output', 'json')
    }
    $ami = Aws-Text @('ssm', 'get-parameter', '--region', $Region, '--name', $AmiParameterName, '--query', 'Parameter.Value', '--output', 'text')
    $images = Aws-Json @('ec2', 'describe-images', '--region', $Region, '--image-ids', $ami, '--output', 'json')
    if (@($images.Images).Count -ne 1 -or $images.Images[0].ImageId -cne $ami) { throw 'AMI description does not match the selected image.' }
    $mappings = @($images.Images[0].BlockDeviceMappings | Where-Object { $_.PSObject.Properties['Ebs'] } | ForEach-Object {
        if ($_.DeviceName -cnotmatch '^/dev/[A-Za-z0-9]+$') { throw 'Unexpected AMI device mapping.' }
        "DeviceName=$($_.DeviceName),Ebs={DeleteOnTermination=true}"
    })
    if ($mappings.Count -eq 0) { throw 'LANBENCH requires explicit EBS deletion-on-termination mappings.' }
    $userData = Join-Path (Split-Path -Parent ([IO.Path]::GetFullPath($OutputJson))) ('user-data-' + $owner.run_id + '.sh')
    $template = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'ec2-user-data-lanbench-tls13-0rtt.sh')).Replace('PORT=5443', "PORT=$Port")
    [IO.File]::WriteAllText($userData, $template, [Text.UTF8Encoding]::new($false))
    $journal.instance_requested = $true
    Save-Journal
    $arguments = @('ec2', 'run-instances', '--region', $Region, '--image-id', $ami, '--instance-type', $InstanceType,
        '--count', '1', '--client-token', $owner.run_id, '--network-interfaces',
        "DeviceIndex=0,SubnetId=$subnetId,Groups=$($journal.security_group.id),AssociatePublicIpAddress=true",
        '--metadata-options', 'HttpTokens=required,HttpEndpoint=enabled', '--user-data', "file://$userData", '--block-device-mappings')
    $arguments += $mappings
    $arguments += @('--tag-specifications', (New-LanbenchTagSpecification 'instance' $InstanceName $owner),
        (New-LanbenchTagSpecification 'volume' $InstanceName $owner), '--output', 'json')
    $created = Aws-Json $arguments
    if (@($created.Instances).Count -ne 1 -or [string]$created.Instances[0].InstanceId -cnotmatch '^i-[0-9a-f]{8,17}$') { throw 'AWS did not return exactly one instance identity.' }
    $journal.instance_id = [string]$created.Instances[0].InstanceId
    Save-Journal
    $null = Aws-Text @('ec2', 'wait', 'instance-running', '--region', $Region, '--instance-ids', $journal.instance_id)
    $described = Aws-Json @('ec2', 'describe-instances', '--region', $Region, '--instance-ids', $journal.instance_id, '--output', 'json')
    $instances = @($described.Reservations | ForEach-Object { $_.Instances })
    if ($instances.Count -ne 1 -or $instances[0].InstanceId -cne $journal.instance_id -or $instances[0].ClientToken -cne $owner.run_id) { throw 'Fresh instance description does not match this creation.' }
    $instance = $instances[0]
    Assert-LanbenchOwner $instance $owner
    $journal.volume_ids = @($instance.BlockDeviceMappings | ForEach-Object {
        if ($_.Ebs.DeleteOnTermination -ne $true) { throw 'An owned instance volume does not have deletion-on-termination enabled.' }
        [string]$_.Ebs.VolumeId
    })
    Save-Journal
    if ([string]::IsNullOrWhiteSpace($instance.PublicIpAddress)) { throw 'LANBENCH instance has no public IPv4 address.' }
    Wait-TcpPort $instance.PublicIpAddress $Port $ServerReadyTimeoutSeconds
    $journal.state = 'ready'
    $journal['public_ip'] = [string]$instance.PublicIpAddress
    $journal['public_dns'] = [string]$instance.PublicDnsName
    $journal['instance_type'] = [string]$instance.InstanceType
    $journal['availability_zone'] = [string]$instance.Placement.AvailabilityZone
    Save-Journal
    if ($OutputEnv) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent ([IO.Path]::GetFullPath($OutputEnv))) | Out-Null
        @("LANBENCH_MBEDTLS_0RTT_HOST=$($instance.PublicIpAddress)", "LANBENCH_MBEDTLS_0RTT_SERVER_NAME=$($instance.PublicIpAddress)",
            "LANBENCH_MBEDTLS_0RTT_PORT=$Port", "LANBENCH_MBEDTLS_0RTT_INSTANCE_ID=$($instance.InstanceId)",
            "LANBENCH_MBEDTLS_0RTT_INSTANCE_NAME=$InstanceName") | Set-Content -LiteralPath $OutputEnv -Encoding ASCII
    }
    Write-Host 'LANBENCH owned EC2 server is ready.'
} catch {
    $journal.state = 'prepare_failed'
    Save-Journal
    throw
} finally {
    if ($userData -and (Test-Path -LiteralPath $userData -PathType Leaf)) { Remove-Item -LiteralPath $userData -Force }
}

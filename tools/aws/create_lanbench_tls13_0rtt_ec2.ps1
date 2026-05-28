param(
    [string] $Region = "ap-northeast-1",
    [string] $InstanceName = "iot-reference-rx-lanbench-tls13-0rtt",
    [string] $InstanceType = "t4g.nano",
    [string] $SecurityGroupName = "iot-reference-rx-lanbench-tls13-0rtt-5443",
    [int] $Port = 5443,
    [string] $AmiParameterName = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64",
    [int] $ServerReadyTimeoutSeconds = 900,
    [string] $OutputJson,
    [string] $OutputEnv
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-AwsText {
    param([string[]] $Arguments)

    $result = & aws @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "aws $($Arguments -join ' ') failed"
    }
    if ($null -eq $result) {
        return ""
    }
    return (($result | Out-String).Trim())
}

function Invoke-AwsJson {
    param([string[]] $Arguments)

    $text = Invoke-AwsText $Arguments
    if ([string]::IsNullOrWhiteSpace($text) -or $text -eq "None") {
        return $null
    }
    return $text | ConvertFrom-Json
}

function Wait-TcpPort {
    param(
        [string] $HostName,
        [int] $PortNumber,
        [int] $TimeoutSeconds
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $client = [System.Net.Sockets.TcpClient]::new()
        try {
            $async = $client.BeginConnect($HostName, $PortNumber, $null, $null)
            if ($async.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds(5))) {
                $client.EndConnect($async)
                return
            }
        }
        catch {
            Start-Sleep -Seconds 5
        }
        finally {
            $client.Dispose()
        }
    }
    throw "Timed out waiting for ${HostName}:${PortNumber}"
}

function Get-LanbenchInstance {
    Invoke-AwsJson @(
        "ec2", "describe-instances",
        "--region", $Region,
        "--filters", "Name=tag:Name,Values=$InstanceName", "Name=instance-state-name,Values=pending,running,stopping,stopped",
        "--query", "Reservations[].Instances[0] | [0].{InstanceId:InstanceId,State:State.Name,PublicIp:PublicIpAddress,PublicDns:PublicDnsName,InstanceType:InstanceType,Az:Placement.AvailabilityZone}",
        "--output", "json"
    )
}

function Get-InstanceDescription {
    param([string] $InstanceId)

    Invoke-AwsJson @(
        "ec2", "describe-instances",
        "--region", $Region,
        "--instance-ids", $InstanceId,
        "--query", "Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name,PublicIp:PublicIpAddress,PublicDns:PublicDnsName,InstanceType:InstanceType,Az:Placement.AvailabilityZone}",
        "--output", "json"
    )
}

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port is out of range: $Port"
}

$instance = Get-LanbenchInstance
if ($null -ne $instance -and -not [string]::IsNullOrWhiteSpace($instance.InstanceId)) {
    Write-Host "Reusing LANBENCH TLS 1.3 0-RTT EC2 instance: $($instance.InstanceId) state=$($instance.State)"
    if ($instance.State -eq "stopped") {
        & aws ec2 start-instances --region $Region --instance-ids $instance.InstanceId | Out-Null
    }
    elseif ($instance.State -eq "stopping") {
        & aws ec2 wait instance-stopped --region $Region --instance-ids $instance.InstanceId
        & aws ec2 start-instances --region $Region --instance-ids $instance.InstanceId | Out-Null
    }
    & aws ec2 wait instance-running --region $Region --instance-ids $instance.InstanceId
    $instance = Get-InstanceDescription -InstanceId $instance.InstanceId
}
else {
    $vpcId = Invoke-AwsText @(
        "ec2", "describe-vpcs",
        "--region", $Region,
        "--filters", "Name=isDefault,Values=true",
        "--query", "Vpcs[0].VpcId",
        "--output", "text"
    )

    $subnetId = Invoke-AwsText @(
        "ec2", "describe-subnets",
        "--region", $Region,
        "--filters", "Name=vpc-id,Values=$vpcId", "Name=default-for-az,Values=true",
        "--query", "Subnets[0].SubnetId",
        "--output", "text"
    )

    $sgId = Invoke-AwsText @(
        "ec2", "describe-security-groups",
        "--region", $Region,
        "--filters", "Name=vpc-id,Values=$vpcId", "Name=group-name,Values=$SecurityGroupName",
        "--query", "SecurityGroups[0].GroupId",
        "--output", "text"
    )

    if ($sgId -eq "None" -or [string]::IsNullOrWhiteSpace($sgId)) {
        $sgId = Invoke-AwsText @(
            "ec2", "create-security-group",
            "--region", $Region,
            "--group-name", $SecurityGroupName,
            "--description", "LANBENCH TLS 1.3 0-RTT port $Port",
            "--vpc-id", $vpcId,
            "--query", "GroupId",
            "--output", "text"
        )
        & aws ec2 create-tags `
            --region $Region `
            --resources $sgId `
            --tags Key=Name,Value=$SecurityGroupName Key=Project,Value=iot-reference-rx | Out-Null
    }

    try {
        & aws ec2 authorize-security-group-ingress `
            --region $Region `
            --group-id $sgId `
            --ip-permissions "IpProtocol=tcp,FromPort=$Port,ToPort=$Port,IpRanges=[{CidrIp=0.0.0.0/0,Description=`"LANBENCH TLS 1.3 0-RTT`"}]" | Out-Null
    }
    catch {
        if ($_.Exception.Message -notmatch "InvalidPermission.Duplicate") {
            throw
        }
    }

    $ami = Invoke-AwsText @(
        "ssm", "get-parameter",
        "--region", $Region,
        "--name", $AmiParameterName,
        "--query", "Parameter.Value",
        "--output", "text"
    )

    $userDataTemplate = Join-Path $PSScriptRoot "ec2-user-data-lanbench-tls13-0rtt.sh"
    $userData = Join-Path ([System.IO.Path]::GetTempPath()) ("lanbench-tls13-0rtt-user-data-{0}.sh" -f ([guid]::NewGuid().ToString("N")))
    $userDataText = [System.IO.File]::ReadAllText($userDataTemplate).Replace("PORT=5443", "PORT=$Port")
    [System.IO.File]::WriteAllText($userData, $userDataText, [System.Text.UTF8Encoding]::new($false))
    $instanceId = Invoke-AwsText @(
        "ec2", "run-instances",
        "--region", $Region,
        "--image-id", $ami,
        "--instance-type", $InstanceType,
        "--count", "1",
        "--network-interfaces", "DeviceIndex=0,SubnetId=$subnetId,Groups=$sgId,AssociatePublicIpAddress=true",
        "--metadata-options", "HttpTokens=required,HttpEndpoint=enabled",
        "--user-data", "file://$userData",
        "--tag-specifications",
        "ResourceType=instance,Tags=[{Key=Name,Value=$InstanceName},{Key=Project,Value=iot-reference-rx},{Key=Purpose,Value=lanbench-tls13-0rtt},{Key=Owner,Value=codex}]",
        "ResourceType=volume,Tags=[{Key=Name,Value=$InstanceName},{Key=Project,Value=iot-reference-rx},{Key=Purpose,Value=lanbench-tls13-0rtt}]",
        "--query", "Instances[0].InstanceId",
        "--output", "text"
    )

    & aws ec2 wait instance-running --region $Region --instance-ids $instanceId
    $instance = Get-InstanceDescription -InstanceId $instanceId
}

if ([string]::IsNullOrWhiteSpace($instance.PublicIp)) {
    throw "LANBENCH EC2 instance has no public IPv4 address: $($instance.InstanceId)"
}

Wait-TcpPort -HostName $instance.PublicIp -PortNumber $Port -TimeoutSeconds $ServerReadyTimeoutSeconds

$result = [ordered]@{
    region = $Region
    instance_name = $InstanceName
    instance_id = $instance.InstanceId
    public_ip = $instance.PublicIp
    public_dns = $instance.PublicDns
    port = $Port
    instance_type = $instance.InstanceType
    availability_zone = $instance.Az
}

if ($OutputJson) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputJson) | Out-Null
    $result | ConvertTo-Json -Depth 4 | Set-Content -Path $OutputJson -Encoding ASCII
}

if ($OutputEnv) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputEnv) | Out-Null
    @(
        "LANBENCH_MBEDTLS_0RTT_HOST=$($instance.PublicIp)",
        "LANBENCH_MBEDTLS_0RTT_SERVER_NAME=$($instance.PublicIp)",
        "LANBENCH_MBEDTLS_0RTT_PORT=$Port",
        "LANBENCH_MBEDTLS_0RTT_INSTANCE_ID=$($instance.InstanceId)",
        "LANBENCH_MBEDTLS_0RTT_INSTANCE_NAME=$InstanceName"
    ) | Set-Content -Path $OutputEnv -Encoding ASCII
}

$result | ConvertTo-Json -Depth 4

function Invoke-Rx72nOtaWithOidc {
    param(
        [Parameter(Mandatory)][scriptblock]$Action,
        [string]$Token
    )

    if ($env:RX72N_OTA_OIDC -cne 'true') {
        & $Action
        return
    }

    if ($env:CI_PROJECT_ID -cne '38' -or
        $env:CI_PROJECT_PATH -cne 'oss/import/github/renesas/iot-reference-rx' -or
        $env:CI_COMMIT_BRANCH -cne 'main' -or $env:CI_COMMIT_TAG -or
        $env:CI_COMMIT_REF_PROTECTED -cne 'true' -or
        $env:CI_PIPELINE_SOURCE -cnotin @('push', 'web', 'api', 'parent_pipeline', 'schedule') -or
        $env:CI_JOB_ID -cnotmatch '^[0-9]+$' -or
        $env:CI_DEBUG_TRACE -match '^(true|t|\+?0*1)$' -or
        $env:CI_DEBUG_SERVICES -match '^(true|t|\+?0*1)$' -or -not $token) {
        throw 'Unexpected RX72N OTA OIDC job context.'
    }
    if ($env:AWS_ROLE_ARN -cnotmatch '^arn:aws:iam::([0-9]{12}):role/saffti-oss-gitlab-oidc$') {
        throw 'Unexpected RX72N OTA OIDC role.'
    }
    $account = $Matches[1]
    $sessionName = "gitlab38-$env:CI_JOB_ID"
    $region = $env:AWS_DEFAULT_REGION
    if ($region -cne 'ap-northeast-1') { throw 'Unexpected RX72N OTA AWS region.' }

    # Use a job-local home for the AWS CLI web identity cache and token file.
    $directory = [IO.Directory]::CreateTempSubdirectory('rx72n-ota-oidc-')
    $settings = @{
        AWS_CONFIG_FILE = Join-Path $directory.FullName 'config'
        AWS_SHARED_CREDENTIALS_FILE = Join-Path $directory.FullName 'credentials'
        BOTO_CONFIG = Join-Path $directory.FullName 'boto'
        AWS_WEB_IDENTITY_TOKEN_FILE = Join-Path $directory.FullName 'token'
        AWS_ROLE_SESSION_NAME = $sessionName
        AWS_EC2_METADATA_DISABLED = 'true'
        AWS_IGNORE_CONFIGURED_ENDPOINT_URLS = 'true'
        AWS_CLI_USE_PYTHON_MODULE = '1'
        AWS_PAGER = ''
        USERPROFILE = $directory.FullName
        HOME = $directory.FullName
    }
    $clear = @('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN',
               'AWS_ACCESS_KEY', 'AWS_SECRET_KEY', 'AWS_CREDENTIAL_FILE', 'AWS_PROFILE', 'AWS_DEFAULT_PROFILE',
               'AWS_CONTAINER_CREDENTIALS_RELATIVE_URI', 'AWS_CONTAINER_CREDENTIALS_FULL_URI',
               'AWS_CONTAINER_AUTHORIZATION_TOKEN', 'AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE',
               'AWS_CA_BUNDLE', 'AWS_CLI_EXE', 'BOTO_PATH', 'AWS_REGION')
    $previous = @{}
    try {
        [IO.File]::WriteAllText($settings.AWS_WEB_IDENTITY_TOKEN_FILE, $token)
        $token = $null
        foreach ($name in ($clear + @($settings.Keys))) {
            $previous[$name] = [Environment]::GetEnvironmentVariable($name)
            [Environment]::SetEnvironmentVariable($name, $settings[$name])
        }

        $caller = & python -I -m awscli sts get-caller-identity --region $region --query Arn --output text 2>$null
        if ($LASTEXITCODE -ne 0 -or $caller -cne "arn:aws:sts::${account}:assumed-role/saffti-oss-gitlab-oidc/$sessionName") {
            throw 'RX72N OTA OIDC caller verification failed.'
        }
        & $Action
    } finally {
        foreach ($name in $previous.Keys) {
            [Environment]::SetEnvironmentVariable($name, $previous[$name])
        }
        $directory.Delete($true)
    }
}

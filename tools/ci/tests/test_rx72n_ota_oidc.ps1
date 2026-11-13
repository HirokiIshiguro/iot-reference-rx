param([Parameter(Mandatory)][string]$Wrapper)
$ErrorActionPreference = 'Stop'
. $Wrapper
function Assert-True($condition, $message) { if (-not $condition) { throw $message } }
function python {
    $global:LASTEXITCODE = 0
    return 'arn:aws:sts::123456789012:assumed-role/saffti-oss-gitlab-oidc/gitlab38-42'
}
$env:CI_PROJECT_ID = '38'
$env:CI_PROJECT_PATH = 'oss/import/github/renesas/iot-reference-rx'
$env:CI_COMMIT_BRANCH = 'main'
$env:CI_COMMIT_TAG = ''
$env:CI_COMMIT_REF_PROTECTED = 'true'
$env:CI_PIPELINE_SOURCE = 'push'
$env:CI_JOB_ID = '42'
$env:CI_DEBUG_TRACE = ''
$env:CI_DEBUG_SERVICES = ''
$env:AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/saffti-oss-gitlab-oidc'
$env:AWS_DEFAULT_REGION = 'ap-northeast-1'
$env:AWS_ACCESS_KEY_ID = 'ambient'
$env:AWS_PROFILE = 'ambient-profile'
$env:AWS_OTA_S3_BUCKET_RX72N_02 = 'business-input'
$env:RX72N_OTA_OIDC = 'false'
$script:ran = $false
Invoke-Rx72nOtaWithOidc -Token '' -Action { $script:ran = $true; Assert-True ($env:AWS_ACCESS_KEY_ID -ceq 'ambient') 'disabled changed credentials' }
Assert-True $script:ran 'disabled action not invoked'
$env:RX72N_OTA_OIDC = 'true'
$script:path = ''
Invoke-Rx72nOtaWithOidc -Token 'synthetic-token' -Action {
    $script:path = $env:AWS_WEB_IDENTITY_TOKEN_FILE
    Assert-True ([IO.File]::ReadAllText($script:path) -ceq 'synthetic-token') 'missing token'
    Assert-True (-not $env:AWS_ACCESS_KEY_ID -and -not $env:AWS_PROFILE) 'ambient credential not cleared'
    Assert-True ($env:AWS_OTA_S3_BUCKET_RX72N_02 -ceq 'business-input') 'business input lost'
}
Assert-True (-not (Test-Path -LiteralPath $script:path)) 'token file left after success'
Assert-True ($env:AWS_ACCESS_KEY_ID -ceq 'ambient' -and $env:AWS_PROFILE -ceq 'ambient-profile') 'environment not restored'
$script:path = ''
try {
    Invoke-Rx72nOtaWithOidc -Token 'synthetic-token' -Action { $script:path = $env:AWS_WEB_IDENTITY_TOKEN_FILE; throw 'synthetic failure' }
    throw 'failure did not propagate'
} catch { if ($_.Exception.Message -cne 'synthetic failure') { throw } }
Assert-True (-not (Test-Path -LiteralPath $script:path)) 'token file left after failure'
Assert-True ($env:AWS_PROFILE -ceq 'ambient-profile') 'environment not restored after failure'
foreach ($name in @('CI_PROJECT_ID', 'CI_COMMIT_BRANCH', 'CI_COMMIT_REF_PROTECTED', 'CI_PIPELINE_SOURCE', 'AWS_ROLE_ARN')) {
    $old = [Environment]::GetEnvironmentVariable($name)
    [Environment]::SetEnvironmentVariable($name, 'invalid')
    $script:ran = $false
    try { Invoke-Rx72nOtaWithOidc -Token 'synthetic-token' -Action { $script:ran = $true }; throw 'context accepted' }
    catch { if ($_.Exception.Message -ceq 'context accepted') { throw } }
    Assert-True (-not $script:ran) "action ran with invalid $name"
    [Environment]::SetEnvironmentVariable($name, $old)
}
$script:ran = $false
try { Invoke-Rx72nOtaWithOidc -Token '' -Action { $script:ran = $true }; throw 'empty token accepted' }
catch { if ($_.Exception.Message -ceq 'empty token accepted') { throw } }
Assert-True (-not $script:ran) 'action ran without token'
function python { $global:LASTEXITCODE = 0; return 'arn:aws:sts::123456789012:assumed-role/wrong/gitlab38-42' }
try { Invoke-Rx72nOtaWithOidc -Token 'synthetic-token' -Action { $script:ran = $true }; throw 'wrong identity accepted' }
catch { if ($_.Exception.Message -ceq 'wrong identity accepted') { throw } }
Assert-True (-not $script:ran) 'action ran with wrong identity'
Assert-True ($env:AWS_PROFILE -ceq 'ambient-profile') 'environment not restored after caller failure'
Write-Host 'RX72N OTA OIDC wrapper offline tests passed'

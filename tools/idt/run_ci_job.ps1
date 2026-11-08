$ErrorActionPreference = "Stop"
& "$env:RX72N_IDT_PYTHON" -I -m awscli --version
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
. tools/rx_e2studio_cli.ps1
Initialize-RxBuildDependencies -ProjectRoot $env:CI_PROJECT_DIR
$idtTarget = if ($env:RUN_RX_IDT -eq 'true') { $env:IDT_TARGET } else { 'rx72n-ethernet' }
$env:IDT_TARGET = $idtTarget
$idtScope = if ($env:RUN_RX_IDT -eq 'true') { $env:IDT_SCOPE } else { $env:RX72N_IDT_SCOPE }
$idtHostJson = & "$env:RX72N_IDT_PYTHON" tools/idt/check_host.py --target "$idtTarget" --check-aws
$idtHostStatus = $LASTEXITCODE
try { $idtHostCheck = ($idtHostJson -join "`n") | ConvertFrom-Json }
catch { throw "IDT host preflight did not return valid JSON" }
foreach ($check in $idtHostCheck.checks) {
  Write-Host ("IDT host check {0}: passed={1}" -f $check.name, $check.passed)
}
Write-Host ("IDT host versions: e2studio={0}, CC-RX={1}, Linux={2}" -f `
  $idtHostCheck.installed_toolchain.e2studio.release, `
  $idtHostCheck.installed_toolchain.ccrx.version, `
  $idtHostCheck.linux_os_release.VERSION_ID)
if ($idtHostStatus -ne 0 -or -not $idtHostCheck.host_preflight_passed) {
  throw "IDT host preflight failed; inspect the named checks under the runner identity"
}
if ($idtScope -ne 'preflight') {
  $bootstrapNames = @('IDT_PUBLIC_SIGNER_PROVISIONER_MOT_FILE', 'IDT_PUBLIC_SIGNER_PROVISIONER_MANIFEST_FILE', 'IDT_PUBLIC_SIGNER_CERT_FILE', 'IDT_PUBLIC_SIGNER_PUBLIC_KEY_FILE')
  $bootstrapPresent = @($bootstrapNames | Where-Object { [Environment]::GetEnvironmentVariable($_, 'Process') })
  if ($bootstrapPresent.Count -eq 0) {
    $bootstrapRoot = "C:/ai/codex/tmp/rx-idt-public-signer-$env:CI_PIPELINE_ID-$env:CI_JOB_ID-$idtTarget"
    $bootstrapJson = & "$env:RX72N_IDT_PYTHON" tools/idt/prepare_public_signer.py --source "$env:CI_PROJECT_DIR" --target "$idtTarget" --output "$bootstrapRoot" --workspace "C:/ai/codex/ws/rx-idt-bootstrap-$env:CI_PIPELINE_ID-$env:CI_JOB_ID" --python "$env:RX72N_IDT_PYTHON"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    try { $bootstrapInputs = ($bootstrapJson -join "`n") | ConvertFrom-Json }
    catch { throw 'Public signer bootstrap did not return valid input paths' }
    if (@($bootstrapInputs.PSObject.Properties).Count -ne $bootstrapNames.Count) {
      throw 'Public signer bootstrap returned an unexpected input set'
    }
    foreach ($name in $bootstrapNames) {
      $path = $bootstrapInputs.$name
      if (-not $path -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Public signer bootstrap input is missing: $name"
      }
      [Environment]::SetEnvironmentVariable($name, $path, 'Process')
    }
  } elseif ($bootstrapPresent.Count -ne $bootstrapNames.Count) {
    throw 'Public signer bootstrap input overrides must supply the complete set'
  }
}
& "$env:RX72N_IDT_PYTHON" tools/idt/oidc_job.py --check-before-run
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$env:RX72N_IDT_PYTHON" tools/idt/run_idt.py --target "$idtTarget" --scope "$idtScope" --output artifacts/idt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

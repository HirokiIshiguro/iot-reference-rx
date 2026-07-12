param(
    [Parameter(Mandatory = $true)]
    [string] $DriverTargetDirectory,

    [int] $ExpectedLoopCount = 0
)

$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $DriverTargetDirectory).Path
$files = Get-ChildItem -LiteralPath (Join-Path $target 'ip') -Filter '*.c' -File
$pattern = '(?ms)(/\* WAIT_LOOP \*/\s*\r?\n\s*while\s*\([^\r\n]*TSIP\.REG_00H\.BIT\.B25[^\r\n]*\)\s*\r?\n\s*\{\s*\r?\n)([ \t]*)/\* waiting \*/'
$b25Pattern = 'TSIP\.REG_00H\.BIT\.B25'
$hookPattern = 'TSIP_PRV_WAIT_LOOP_HOOK\(\);'
$changedFiles = 0
$changedLoops = 0

foreach ($file in $files) {
    $text = Get-Content -Raw -LiteralPath $file.FullName
    $matches = [regex]::Matches($text, $pattern).Count
    if ($matches -eq 0) {
        continue
    }

    $updated = [regex]::Replace($text, $pattern, '$1$2TSIP_PRV_WAIT_LOOP_HOOK();')
    Set-Content -LiteralPath $file.FullName -Value $updated -NoNewline -Encoding utf8
    $changedFiles++
    $changedLoops += $matches
}

$b25Count = 0
$hookCount = 0
foreach ($file in $files) {
    $text = Get-Content -Raw -LiteralPath $file.FullName
    $b25Count += [regex]::Matches($text, $b25Pattern).Count
    $hookCount += [regex]::Matches($text, $hookPattern).Count
}

if (($ExpectedLoopCount -gt 0) -and ($b25Count -ne $ExpectedLoopCount)) {
    throw "Expected $ExpectedLoopCount REG_00H.B25 waits, found $b25Count"
}
if ($hookCount -ne $b25Count) {
    throw "Hook coverage mismatch: hooks=$hookCount REG_00H.B25 waits=$b25Count"
}

[pscustomobject]@{
    driver_target = $target
    source_files = $files.Count
    changed_files = $changedFiles
    changed_loops = $changedLoops
    b25_wait_loops = $b25Count
    hook_calls = $hookCount
} | ConvertTo-Json

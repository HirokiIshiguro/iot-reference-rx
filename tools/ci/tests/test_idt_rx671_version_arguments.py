"""Invoke the real RX671 builder call with an isolated argument-recording stub."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
BUILDER = ROOT / "tools/build_rx72n_idt_transport.ps1"
HELPER = ROOT / "tools/build_headless_rx671_wifi.ps1"
POWERSHELL = shutil.which("pwsh")

HARNESS = r"""
param([string]$BuilderPath, [string]$HelperPath, [string]$RequestPath, [string]$ResultPath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Read-Ast([string]$Path) {
    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw 'Production source must parse before isolated execution.' }
    return $ast
}
function Get-Assignment($Ast, [string]$Name) {
    $matches = @($Ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $node.Left.VariablePath.UserPath -ceq $Name
    }, $true))
    if ($matches.Count -ne 1) { throw "Expected one assignment for $Name" }
    return $matches[0]
}
$builder = Read-Ast $BuilderPath
$helper = Read-Ast $HelperPath
$versionAssignment = Get-Assignment $builder 'version'
$initialize = Get-Assignment $builder 'rx671OtaVersionArguments'
if ($initialize.Right.Expression -isnot [System.Management.Automation.Language.HashtableAst] -or
    $initialize.Right.Expression.KeyValuePairs.Count -ne 0) { throw 'Expected empty version splat initialization.' }
$members = @($builder.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
    $node.Left -is [System.Management.Automation.Language.MemberExpressionAst] -and
    $node.Left.Expression -is [System.Management.Automation.Language.VariableExpressionAst] -and
    $node.Left.Expression.VariablePath.UserPath -ceq 'rx671OtaVersionArguments' -and
    $node.Left.Member.Value -ceq 'OtaImageVersion'
}, $true))
if ($members.Count -ne 1) { throw 'Expected one OTA version member assignment.' }
$conditional = $members[0].Parent.Parent
if ($conditional -isnot [System.Management.Automation.Language.IfStatementAst] -or
    $conditional.Clauses.Count -ne 1 -or $null -ne $conditional.ElseClause -or
    $conditional.Clauses[0].Item2.Statements.Count -ne 1) { throw 'Unsafe conditional extraction.' }
foreach ($node in @($versionAssignment, $initialize, $conditional)) {
    if ($null -ne $node.Find({param($child) $child -is [System.Management.Automation.Language.CommandAst]}, $true)) {
        throw 'Extracted assignment/condition must not invoke commands.'
    }
}
$commands = @($builder.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and
    $node.InvocationOperator -eq [System.Management.Automation.Language.TokenKind]::Ampersand -and
    $null -ne $node.CommandElements[0].Find({
        param($child)
        $child -is [System.Management.Automation.Language.StringConstantExpressionAst] -and
        $child.Value -ceq 'build_headless_rx671_wifi.ps1'
    }, $true)
}, $true))
if ($commands.Count -ne 1) { throw 'Expected one actual RX671 Wi-Fi helper call.' }
$command = $commands[0]
if ($command.Redirections.Count) { throw 'Unexpected call redirection.' }
foreach ($argument in @($command.CommandElements | Select-Object -Skip 1)) {
    if ($null -ne $argument.Find({param($child) $child -is [System.Management.Automation.Language.CommandAst]}, $true)) {
        throw 'Unexpected command evaluation in helper argument.'
    }
}
# Replace only the call target; all production parameters and the splat stay intact.
$callee = $command.CommandElements[0]
$callText = $command.Extent.Text.Remove(
    $callee.Extent.StartOffset - $command.Extent.StartOffset,
    $callee.Extent.EndOffset - $callee.Extent.StartOffset).Insert(
    $callee.Extent.StartOffset - $command.Extent.StartOffset, '$stubPath')

# Use the real receiver's parameter defaults and version-to-marker statements.
# The remaining build script body is never evaluated.
$defaultCommands = @($helper.ParamBlock.FindAll({
    param($child) $child -is [System.Management.Automation.Language.CommandAst]
}, $true))
if (@($defaultCommands | Where-Object { $_.GetCommandName() -cnotin @('Split-Path', 'Join-Path') }).Count) {
    throw 'Unexpected command in receiver parameter defaults.'
}
$converters = @($helper.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'ConvertFrom-OtaImageVersion'
}, $false))
if ($converters.Count -ne 1) { throw 'Expected one receiver version converter.' }
$receiverStatements = @(
    (Get-Assignment $helper 'otaImageVersionParts').Extent.Text,
    (Get-Assignment $helper 'effectiveOtaImageVersion').Extent.Text,
    (Get-Assignment $helper 'expectedOtaImageMarker').Extent.Text
)
$stubResultPath = Join-Path $PSScriptRoot 'received.json'
$stubPath = Join-Path $PSScriptRoot 'argument-recorder.ps1'
$recorder = @'
$record = [ordered]@{
    bound_parameters = $PSBoundParameters
    ota_image_version = $OtaImageVersion
    effective_version = $effectiveOtaImageVersion
    marker = $expectedOtaImageMarker
}
[IO.File]::WriteAllText($stubResultPath, ($record | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
'@
$stub = $helper.ParamBlock.Extent.Text + "`n" + $converters[0].Extent.Text + "`n" +
    ($receiverStatements -join "`n") + "`n" + $recorder
[IO.File]::WriteAllText($stubPath, $stub, [Text.UTF8Encoding]::new($false))
$request = [IO.File]::ReadAllText($RequestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
$TestGroup = [string]$request.group
$Target = 'rx671-wifi'
$appVersion = [ordered]@{ MAJOR = [uint32]$request.major; MINOR = [uint32]$request.minor; BUILD = [uint32]$request.build }
$idtRoot = Join-Path $PSScriptRoot 'fixture source'
$E2Studio = 'inert-e2studio-stub'
$idtWorkspace = Join-Path $PSScriptRoot 'fixture workspace'
$buildLog = Join-Path $PSScriptRoot 'not-created-build.log'
$dependencyProvenanceFile = Join-Path $PSScriptRoot 'not-read-provenance.json'
$Python = 'inert-python-stub'
$E2StudioTimeoutSeconds = 17
# Prove that the actual initialization discards prior invocation state.
$rx671OtaVersionArguments = @{ OtaImageVersion = '77.88.99' }
. ([scriptblock]::Create($versionAssignment.Extent.Text + "`n" + $initialize.Extent.Text +
    "`n" + $conditional.Extent.Text + "`n" + $callText))
if (-not [IO.File]::Exists($stubResultPath)) { throw 'The isolated receiver did not execute.' }
$received = [IO.File]::ReadAllText($stubResultPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
$result = [ordered]@{ selected_version = $version; received = $received }
[IO.File]::WriteAllText($ResultPath, ($result | ConvertTo-Json -Depth 7), [Text.UTF8Encoding]::new($false))
"""


@unittest.skipUnless(POWERSHELL, "PowerShell 7 is required for the production AST")
class Rx671VersionArgumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive",
            "-Command", "$PSVersionTable.PSVersion.Major"], text=True, capture_output=True, timeout=30)
        if result.returncode or int(result.stdout.strip()) < 7:
            raise unittest.SkipTest("PowerShell 7 or later is required")

    def invoke_actual_call(self, group: str, triple: tuple[int, int, int]) -> dict:
        with tempfile.TemporaryDirectory(prefix="rx671 version arguments ") as directory:
            folder = Path(directory)
            harness = folder / "isolate-builder-call.ps1"
            request = folder / "request.json"
            result = folder / "result.json"
            harness.write_text(HARNESS, encoding="utf-8")
            request.write_text(json.dumps(dict(group=group, major=triple[0], minor=triple[1],
                                              build=triple[2])), encoding="utf-8")
            process = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(harness), "-BuilderPath", str(BUILDER),
                "-HelperPath", str(HELPER), "-RequestPath", str(request), "-ResultPath", str(result)],
                text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertTrue(result.is_file(), "Actual command must invoke the argument receiver")
            return json.loads(result.read_text(encoding="utf-8-sig"))

    def assert_forwarded(self, triple: tuple[int, int, int]):
        expected = '.'.join(str(part) for part in triple)
        result = self.invoke_actual_call("OTAE2E", triple)
        received = result["received"]
        self.assertEqual(expected, result["selected_version"])
        self.assertEqual(expected, received["bound_parameters"]["OtaImageVersion"])
        self.assertEqual(expected, received["ota_image_version"])
        self.assertEqual(expected, received["effective_version"])
        self.assertEqual("RX671_OTA_IMAGE_VERSION=" + expected, received["marker"])

    def test_ota_e2e_forwards_selected_0_9_1_to_receiver_and_marker(self):
        self.assert_forwarded((0, 9, 1))

    def test_transport_omits_version_and_keeps_receiver_default(self):
        result = self.invoke_actual_call("Transport", (0, 9, 1))
        received = result["received"]
        self.assertEqual("0.1.0", result["selected_version"])
        self.assertNotIn("OtaImageVersion", received["bound_parameters"])
        self.assertEqual("", received["ota_image_version"])
        self.assertEqual("0.1.0", received["effective_version"])
        self.assertEqual("RX671_OTA_IMAGE_VERSION=0.1.0", received["marker"])

    def test_ota_e2e_forwards_zero_maximum_and_mixed_boundary_triples(self):
        for triple in ((0, 0, 0), (255, 255, 65535), (255, 0, 65535), (0, 255, 1), (1, 2, 3)):
            with self.subTest(triple=triple):
                self.assert_forwarded(triple)

    def test_other_groups_never_bind_ota_version_even_with_stale_splat(self):
        for group in ("DeviceAdvisor", "PKCS11", "OTAPAL"):
            with self.subTest(group=group):
                result = self.invoke_actual_call(group, (255, 255, 65535))
                received = result["received"]
                self.assertEqual("0.1.0", result["selected_version"])
                self.assertNotIn("OtaImageVersion", received["bound_parameters"])
                self.assertEqual("", received["ota_image_version"])
                self.assertEqual("0.1.0", received["effective_version"])

    def test_actual_call_retains_production_nonversion_arguments(self):
        bound = self.invoke_actual_call("OTAE2E", (0, 9, 1))["received"]["bound_parameters"]
        self.assertEqual("SDHI_DIV_8", bound["SdioRunClockDiv"])
        self.assertEqual(17, bound["E2StudioTimeoutSeconds"])
        self.assertTrue(bound["UseKvsJoinConfig"]["IsPresent"])
        self.assertTrue(bound["SkipAwsIotConfig"]["IsPresent"])
        self.assertEqual("inert-e2studio-stub", bound["E2Studio"])
        self.assertEqual("inert-python-stub", bound["Python"])
        self.assertTrue(bound["ProjectRoot"].endswith("fixture source"))
        self.assertTrue(bound["Workspace"].endswith("fixture workspace"))
        self.assertTrue(bound["SourceProvenanceFile"].endswith("not-read-provenance.json"))


if __name__ == "__main__":
    unittest.main()

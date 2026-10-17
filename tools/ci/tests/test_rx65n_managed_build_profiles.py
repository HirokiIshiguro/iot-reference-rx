"""Verify fresh RX65N metadata generation and reversible Fleet profiles."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
PWSH = shutil.which("pwsh")
NORMAL = ROOT / "tools/build_headless_rx65n_bg96.ps1"
FLEET = ROOT / "tools/build_headless_rx65n_bg96_fleet.ps1"
CLI = ROOT / "tools/rx_e2studio_cli.ps1"


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(PWSH, "PowerShell 7 required")
class Rx65ManagedProfileTests(unittest.TestCase):
    def run_script(self, source, folder, environment=None):
        script = folder / "harness.ps1"
        script.write_text(source, encoding="utf-8")
        return subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(script)],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            env=environment, timeout=30)

    def generation_harness(self, folder, fail=False):
        return r'''
$ErrorActionPreference='Stop'
. ''' + quote(CLI) + r'''
$root=''' + quote(folder) + r'''
$bootProject=Join-Path $root 'boot'
$appProject=Join-Path $root 'app'
$workspace=Join-Path $root 'workspace'
$E2Studio='fixture-e2studio-cli.exe'
$appProjectName='aws_bg96_ck_rx65n'
$logFile=Join-Path $root 'log.txt'
$E2StudioTimeoutSeconds=10
$fixtureFail=''' + ("$true" if fail else "$false") + r'''
$script:fixtureCalls=0
foreach($project in @($bootProject,$appProject)) {
    [void](New-Item -ItemType Directory -Force -Path (Join-Path $project 'HardwareDebug'))
    [IO.File]::WriteAllText((Join-Path $project '.cproject'),'CURRENT_PROFILE_ONE')
    [IO.File]::WriteAllText((Join-Path $project 'HardwareDebug/makefile'),'STALE_INCLUDE_SOURCE_FLAGS')
    [IO.File]::WriteAllText((Join-Path $project 'HardwareDebug/stale-response.tmp'),'STALE_THREADSAFE')
}
function Invoke-RxE2StudioBuild {
    param($Executable,$WorkspacePath,$ProjectPaths,$BuildTargets,$OutputLog,$TimeoutSeconds)
    $script:fixtureCalls++
    if ($fixtureFail) { return 23 }
    foreach($project in $ProjectPaths) {
        [void](New-Item -ItemType Directory -Force -Path (Join-Path $project 'HardwareDebug'))
        [IO.File]::WriteAllText((Join-Path $project 'HardwareDebug/makefile'),
            [IO.File]::ReadAllText((Join-Path $project '.cproject')))
    }
    return 0
}
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(''' + quote(NORMAL) + r''',[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'Helper syntax invalid' }
foreach($name in @('Get-MissingManagedBuildFiles','Clear-GeneratedBuildFiles',
    'Invoke-E2StudioManagedBuild','Ensure-ManagedBuildFiles')) {
    $definition=@($ast.FindAll({param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    },$false))
    if ($definition.Count -ne 1) { throw 'Expected one production helper function' }
    . ([scriptblock]::Create($definition[0].Extent.Text))
}
Ensure-ManagedBuildFiles
foreach($project in @($bootProject,$appProject)) {
    if(Test-Path -LiteralPath (Join-Path $project 'HardwareDebug/stale-response.tmp')) {
        throw 'Stale response file survived generation'
    }
    [IO.File]::WriteAllText((Join-Path $project '.cproject'),'CURRENT_NATIVE_PROFILE_TWO')
}
Ensure-ManagedBuildFiles
$result=@{calls=$script:fixtureCalls;app=[IO.File]::ReadAllText((Join-Path $appProject 'HardwareDebug/makefile'))}
$result|ConvertTo-Json -Compress|Write-Output
'''

    def test_existing_stale_cache_is_regenerated_for_each_current_profile(self):
        with tempfile.TemporaryDirectory(prefix="rx65-profile-") as temporary:
            folder = Path(temporary)
            result = self.run_script(self.generation_harness(folder), folder)
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(2, report["calls"])
            self.assertEqual("CURRENT_NATIVE_PROFILE_TWO", report["app"])

    def test_failed_generation_cannot_fall_back_to_existing_stale_cache(self):
        with tempfile.TemporaryDirectory(prefix="rx65-profile-fail-") as temporary:
            folder = Path(temporary)
            result = self.run_script(self.generation_harness(folder, fail=True), folder)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("e2studio-cli returned 23; refusing a subsequent make build", result.stderr)
            self.assertFalse((folder / "app/HardwareDebug/makefile").exists())

    def test_fleet_profile_uses_metadata_and_restores_bytes_on_success_and_failure(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory(prefix="rx65-fleet-") as temporary:
                folder = Path(temporary)
                tools = folder / "tools"
                tools.mkdir()
                shutil.copyfile(FLEET, tools / FLEET.name)
                (tools / CLI.name).write_text(
                    "function Initialize-RxBuildDependencies { param($ProjectRoot) }\n"
                    "function Assert-RxCommonKernel { param($ProjectRoot) }\n", encoding="utf-8")
                (tools / NORMAL.name).write_text(r'''
param($ProjectRoot,$E2Studio,$Workspace,$LogFile,$E2StudioTimeoutSeconds,$TlsBackend,$RequireTlsVersion)
$base=Join-Path $ProjectRoot 'Projects/aws_bg96_ck_rx65n/e2studio_ccrx'
$xml=[Xml.XmlDocument]::new();$xml.Load((Join-Path $base '.project'))
$config=[IO.File]::ReadAllText((Join-Path $base 'src/frtos_config/demo_config.h'))
$result=@{
    fleetFilterCount=@($xml.SelectNodes("//filter[name='Demos/Fleet_Provisioning_With_CSR_Demo']")).Count
    unrelatedFilterCount=@($xml.SelectNodes("//filter[name='Common']")).Count
    fleetEnabled=($config -match 'ENABLE_FLEET_PROVISIONING_DEMO\s+\(1\)')
    otaDisabled=($config -match 'ENABLE_OTA_UPDATE_DEMO\s+\(0\)')
}
$result|ConvertTo-Json|Set-Content -LiteralPath $env:RX65_FLEET_FIXTURE_RESULT -Encoding utf8
if($env:RX65_FLEET_FIXTURE_FAIL -eq '1') { throw 'fixture build failed' }
''', encoding="utf-8")
                base = folder / "Projects/aws_bg96_ck_rx65n/e2studio_ccrx"
                config = base / "src/frtos_config/demo_config.h"
                config.parent.mkdir(parents=True)
                descriptor = base / ".project"
                original_project = b'''<?xml version="1.0" encoding="UTF-8"?>\r
<projectDescription><linkedResources><link><name>Demos</name></link></linkedResources>
<filteredResources><filter><name>Common</name></filter><filter><name>Demos/Fleet_Provisioning_With_CSR_Demo</name></filter></filteredResources></projectDescription>'''
                original_config = (b"\xef\xbb\xbf#define ENABLE_FLEET_PROVISIONING_DEMO (0)\r\n"
                    b"#define ENABLE_OTA_UPDATE_DEMO (1)\r\n"
                    b'#define democonfigFP_DEMO_ID "normal"\r\n')
                descriptor.write_bytes(original_project)
                config.write_bytes(original_config)
                report = folder / "profile.json"
                environment = dict(os.environ, RX65_FLEET_FIXTURE_RESULT=str(report),
                    RX65_FLEET_FIXTURE_FAIL="1" if fail else "0")
                result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File",
                    str(tools / FLEET.name), "-ProjectRoot", str(folder)],
                    text=True, encoding="utf-8", errors="replace", capture_output=True,
                    env=environment, timeout=30)
                self.assertEqual(0 if not fail else 1, result.returncode, result.stderr)
                observed = json.loads(report.read_text(encoding="utf-8-sig"))
                self.assertEqual(0, observed["fleetFilterCount"])
                self.assertEqual(1, observed["unrelatedFilterCount"])
                self.assertTrue(observed["fleetEnabled"])
                self.assertTrue(observed["otaDisabled"])
                self.assertEqual(original_project, descriptor.read_bytes())
                self.assertEqual(original_config, config.read_bytes())


if __name__ == "__main__":
    unittest.main()

"""Execute production IDT profile selection into real project metadata.

These are host XML/source-selection fixtures, not Eclipse generation or MCU builds.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
BUILDER = ROOT / "tools/build_rx72n_idt_transport.ps1"
PWSH = shutil.which("pwsh")
PROJECTS = {"rx72n-ethernet": "aws_ether_rx72n_envision_kit",
            "rx65n-bg96": "aws_bg96_ck_rx65n", "rx671-wifi": "aws_wifi_rx671_ek"}
GROUPS = ("Transport", "DeviceAdvisor", "OTAE2E", "PKCS11", "OTAPAL")


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(os.name == "nt" and PWSH, "Native builder requires Windows PowerShell 7")
class IdtAutoLinkProfileTests(unittest.TestCase):
    def invoke(self, folder, mutation=""):
        script = folder / "profile.ps1"
        script.write_text(r'''
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=''' + quote(ROOT) + r'''
$builder=''' + quote(BUILDER) + r'''
$output=''' + quote(folder) + r'''
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($builder,[ref]$tokens,[ref]$errors)
if($errors.Count) { throw 'Production builder syntax invalid' }
$function=@($ast.FindAll({param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Add-IdtSelectedSources'
},$false))
if($function.Count -ne 1) { throw 'Expected one production source-selection function' }
. ([scriptblock]::Create($function[0].Extent.Text))
$body=[IO.File]::ReadAllText($builder)
$first=$body.IndexOf('$testSources = [ordered]@{')
$last=$body.IndexOf('$appVersion = [ordered]@{}',$first)
if($first -lt 0 -or $last -le $first) { throw 'Production group selection is missing' }
$groupSelection=[scriptblock]::Create($body.Substring($first,$last-$first))
$idtRoot=Join-Path $output 'owned-parameters'
[void](New-Item -ItemType Directory -Force -Path (Join-Path $idtRoot 'Test/include'))
$parameters=@'
#define PKCS11_TEST_RSA_KEY_SUPPORT 0
#define PKCS11_TEST_EC_KEY_SUPPORT 1
#define PKCS11_TEST_IMPORT_PRIVATE_KEY_SUPPORT 1
#define PKCS11_TEST_GENERATE_KEYPAIR_SUPPORT 0
#define PKCS11_TEST_PREPROVISIONED_SUPPORT 0
#define PKCS11_TEST_JITP_CODEVERIFY_ROOT_CERT_SUPPORTED 0
#define OTA_PAL_USE_FILE_SYSTEM 0
#define OTA_PAL_TEST_CERT_TYPE OTA_ECDSA_SHA256
'@
[IO.File]::WriteAllText((Join-Path $idtRoot 'Test/include/test_param_config.h'),$parameters)
$targets=@{'rx72n-ethernet'='aws_ether_rx72n_envision_kit';'rx65n-bg96'='aws_bg96_ck_rx65n';'rx671-wifi'='aws_wifi_rx671_ek'}
$reports=@()
foreach($target in $targets.Keys) {
    foreach($TestGroup in @('Transport','DeviceAdvisor','OTAE2E','PKCS11','OTAPAL')) {
        . $groupSelection
        if($target -ne 'rx72n-ethernet' -and $TestGroup -in @('Transport','DeviceAdvisor','OTAE2E')) {
            $testSources['rx_idt_network.c']='Test/ports/rx_idt_network.c'
        }
        $project=Join-Path $root ('Projects/'+$targets[$target]+'/e2studio_ccrx')
        $projectXml=[Xml.XmlDocument]::new();$projectXml.PreserveWhitespace=$true;$projectXml.Load((Join-Path $project '.project'))
        $cprojectXml=[Xml.XmlDocument]::new();$cprojectXml.PreserveWhitespace=$true;$cprojectXml.Load((Join-Path $project '.cproject'))
        $toolchainBefore=@($cprojectXml.SelectNodes('//toolChain') | ForEach-Object {$_.GetAttribute('superClass')}) -join '|'
        $optionsBefore=@($cprojectXml.SelectNodes('//toolChain/tool/option') | ForEach-Object {$_.OuterXml}) -join '|'
        ''' + mutation + r'''
        Add-IdtSelectedSources $projectXml $cprojectXml $testSources 'AWS_IOT_MCU_ROOT' $root
        if((@($cprojectXml.SelectNodes('//toolChain') | ForEach-Object {$_.GetAttribute('superClass')}) -join '|') -cne $toolchainBefore -or
           (@($cprojectXml.SelectNodes('//toolChain/tool/option') | ForEach-Object {$_.OuterXml}) -join '|') -cne $optionsBefore) {
            throw 'Source selection altered toolchain/stdlib/include/define/link options'
        }
        $name=$target+'-'+$TestGroup
        $projectXml.Save((Join-Path $output ($name+'.project.xml')))
        $cprojectXml.Save((Join-Path $output ($name+'.cproject.xml')))
        $reports+=@{target=$target;group=$TestGroup;sources=$testSources;source_entry='IdtTestSources';link_policy='generated'}
    }
}
$reports|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $output 'profiles.json') -Encoding utf8
''', encoding="utf-8")
        return subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(script)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)

    def test_all_fifteen_profiles_select_only_their_virtual_file_sources(self):
        with tempfile.TemporaryDirectory(prefix="idt-auto-link-") as temporary:
            folder = Path(temporary)
            result = self.invoke(folder)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            reports = json.loads((folder / "profiles.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(len(reports), 15)
            for report in reports:
                with self.subTest(target=report["target"], group=report["group"]):
                    name = report["target"] + "-" + report["group"]
                    description = ET.parse(folder / (name + ".project.xml")).getroot()
                    metadata = ET.parse(folder / (name + ".cproject.xml")).getroot()
                    links = description.findall("linkedResources/link")
                    selected = {x.findtext("name"): x for x in links
                                if x.findtext("name", "").startswith("IdtTestSources/")}
                    self.assertEqual(set(selected), {"IdtTestSources/" + key for key in report["sources"]})
                    self.assertEqual(description.findtext("linkedResources/link[name='IdtTestSources']/locationURI"),
                                     "virtual:/virtual")
                    for filename, relative in report["sources"].items():
                        link = selected["IdtTestSources/" + filename]
                        self.assertEqual(link.findtext("type"), "1")
                        self.assertEqual(link.findtext("locationURI"), "AWS_IOT_MCU_ROOT/" + relative)
                        self.assertTrue((ROOT / relative).is_file())
                    entries = [x for x in metadata.iter("entry") if x.get("kind") == "sourcePath"]
                    root = [x for x in entries if x.get("name") == ""][0]
                    self.assertIn("IdtTestSources/", root.get("excluding", "").split("|"))
                    dedicated = [x for x in entries if x.get("name") == "IdtTestSources"]
                    self.assertEqual(len(dedicated), 1)
                    self.assertFalse(dedicated[0].get("excluding"))
                    self.assertFalse(any(x.get("superClass", "").endswith("noneLinkageOrderList")
                                         for x in metadata.iter("option")))

    def test_custom_order_manual_list_and_conflicting_source_selection_are_rejected(self):
        mutations = {
            "custom": "$cprojectXml.SelectSingleNode(\"//option[@superClass='com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.useCustomLinkageOrder']\").SetAttribute('value','true')",
            "manual": r'''$node=$cprojectXml.CreateElement('option');$node.SetAttribute('superClass','com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.noneLinkageOrderList');[void]$cprojectXml.SelectSingleNode('//tool').AppendChild($node)''',
            "duplicate": "Add-IdtSelectedSources $projectXml $cprojectXml $testSources 'AWS_IOT_MCU_ROOT' $root",
            "outside": "$testSources['outside.c']='../outside.c'",
            "mismatched": "$testSources['wrong.c']='Test/ports/rx72n_idt_platform.c'",
        }
        for label, mutation in mutations.items():
            with self.subTest(mutation=label), tempfile.TemporaryDirectory(prefix="idt-auto-link-invalid-") as temporary:
                result = self.invoke(Path(temporary), mutation)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, r"IDT (?:requires|source)")


if __name__ == "__main__":
    unittest.main()

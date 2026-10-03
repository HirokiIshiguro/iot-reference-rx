"""Execute only RX671 XML option helpers extracted with the PowerShell AST."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "tools/build_headless_rx671_wifi.ps1"
PROJECT = ROOT / "Projects/aws_wifi_rx671_ek/e2studio_ccrx/.cproject"
POWERSHELL = shutil.which("pwsh")
COMPILER = "com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.userBefore"
LINKER = "com.renesas.cdt.managedbuild.renesas.ccrx.linker.option.userBefore"

HARNESS = r"""
param([string]$HelperPath, [string]$RequestPath, [string]$ResultPath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $HelperPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'The helper source has PowerShell parse errors.' }
$definitions = @()
foreach ($name in @('Add-CProjectOptionValue', 'Add-CProjectDefine', 'Add-CProjectLinkerOption')) {
    $matches = @($ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $false))
    if ($matches.Count -ne 1) { throw "Expected exactly one function definition: $name" }
    $definitions += $matches[0].Extent.Text
}
# Dot-source the three definitions, never the helper's top-level build statements.
. ([scriptblock]::Create($definitions -join "`n"))
$request = [IO.File]::ReadAllText($RequestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
$text = [string]$request.text
if ($request.roundtrip) {
    $metadata = [Xml.XmlDocument]::new()
    $metadata.PreserveWhitespace = $true
    $metadata.LoadXml($text)
    $text = $metadata.OuterXml
}
$before = $text
try {
    foreach ($operation in $request.operations) {
        switch ($operation.kind) {
            'define' { $text = Add-CProjectDefine -Text $text -Define $operation.value }
            'linker' { $text = Add-CProjectLinkerOption -Text $text -Option $operation.value }
            'generic' {
                $text = Add-CProjectOptionValue -Text $text -SuperClass $operation.super_class -Value $operation.value
            }
            default { throw 'Unrecognized isolated test operation.' }
        }
    }
    $result = [ordered]@{ text = $text; before = $before; error = $null }
} catch {
    $result = [ordered]@{ text = $null; before = $before; error = $_.Exception.Message }
}
[IO.File]::WriteAllText($ResultPath, ($result | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
"""


def option(super_class: str, contents: str = "", attributes: str = "") -> str:
    return (f'<option id="fixture-{super_class}" superClass="{super_class}" '
            f'valueType="stringList" {attributes}>{contents}</option>')


def configuration(name: str = "HardwareDebug", compiler: str | None = None,
                  linker: str | None = None, extra: str = "") -> str:
    if compiler is None:
        compiler = '<listOptionValue builtIn="false" value="-define=__FUNCTION__=__func__"/>'
    if linker is None:
        linker = '<listOptionValue builtIn="false" value=""/>'
    return (f'<configuration id="fixture-{name}" name="{name}"><folderInfo>'
            '<toolChain><tool id="fixture-compiler">' + option(COMPILER, compiler)
            + '</tool><tool id="fixture-linker">' + option(LINKER, linker)
            + '</tool>' + extra + '</toolChain></folderInfo></configuration>')


def document(*configurations: str) -> str:
    return '<cproject><storageModule moduleId="cdtBuildSystem">' + ''.join(configurations) + '</storageModule></cproject>'


def entries(text: str, super_class: str, config_name: str = "HardwareDebug") -> list[str]:
    root = ET.fromstring(text)
    selected = root.findall(f".//configuration[@name='{config_name}']//option[@superClass='{super_class}']")
    if len(selected) != 1:
        raise AssertionError("Expected one option in test output")
    return [entry.get("value") for entry in selected[0].findall("listOptionValue")]


def semantics(element: ET.Element):
    """Compare unrelated XML content without depending on serializer formatting."""
    return (element.tag, sorted(element.attrib.items()), (element.text or "").strip(),
            [semantics(child) for child in element])


@unittest.skipUnless(POWERSHELL, "PowerShell 7 is needed to parse the production helper")
class Rx671CProjectOptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive",
                                 "-Command", "$PSVersionTable.PSVersion.Major"],
                                text=True, capture_output=True, timeout=30)
        if result.returncode or int(result.stdout.strip()) < 7:
            raise unittest.SkipTest("PowerShell 7 or later is required")

    def run_helpers(self, text: str, *operations: dict, roundtrip: bool = False) -> dict:
        with tempfile.TemporaryDirectory(prefix="rx671-cproject-") as directory:
            folder = Path(directory)
            script = folder / "isolated-functions.ps1"
            request = folder / "request.json"
            result = folder / "result.json"
            script.write_text(HARNESS, encoding="utf-8")
            request.write_text(json.dumps({"text": text, "operations": operations,
                                           "roundtrip": roundtrip}), encoding="utf-8")
            process = subprocess.run([POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(script), "-HelperPath", str(HELPER),
                "-RequestPath", str(request), "-ResultPath", str(result)],
                text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertTrue(result.is_file(), "Isolated helper must emit its result")
            return json.loads(result.read_text(encoding="utf-8-sig"))

    def assert_success(self, result: dict) -> str:
        self.assertIsNone(result["error"], result["error"])
        ET.fromstring(result["text"])
        return result["text"]

    def test_equivalent_xml_serializations_append_to_same_authoritative_option(self):
        variants = (
            '<listOptionValue value="-define=__FUNCTION__=__func__" builtIn="false"/>',
            '<listOptionValue builtIn="false" value="-define=__FUNCTION__=__func__" />',
            '<listOptionValue builtIn="false" value="-define=__FUNCTION__=__func__"></listOptionValue>',
            "<listOptionValue builtIn='false' value='-define=__FUNCTION__=__func__'></listOptionValue>",
        )
        for compiler in variants:
            with self.subTest(compiler=compiler):
                linker = compiler.replace("-define=__FUNCTION__=__func__", "")
                fixture = document(configuration(compiler=compiler, linker=linker)).replace(
                    f'id="fixture-{COMPILER}" superClass="{COMPILER}"',
                    f"superClass='{COMPILER}' id='unrelated-option-id'")
                result = self.run_helpers(fixture, {"kind": "define", "value": "UNIT_XML=1"},
                                          {"kind": "linker", "value": "-UNIT_XML_LINKER"})
                values = entries(self.assert_success(result), COMPILER)
                self.assertEqual(["-define=__FUNCTION__=__func__", "-define=UNIT_XML=1"], values)
                self.assertEqual(["", "-UNIT_XML_LINKER"], entries(result["text"], LINKER))

    def test_empty_options_need_no_text_anchor_or_existing_entry(self):
        fixture = document(configuration(compiler="", linker=""))
        fixture = fixture.replace('valueType="stringList" ></option>', 'valueType="stringList" />')
        result = self.run_helpers(fixture, {"kind": "define", "value": "UNIT_FIRST=1"},
                                  {"kind": "linker", "value": "-UNIT_FIRST_LINKER"})
        text = self.assert_success(result)
        self.assertEqual(["-define=UNIT_FIRST=1"], entries(text, COMPILER))
        self.assertEqual(["-UNIT_FIRST_LINKER"], entries(text, LINKER))

    def test_existing_empty_marker_flags_and_other_attributes_are_preserved(self):
        # Installed CDT accepts a nonempty user list even with IS_VALUE_EMPTY=true.
        # IS_BUILTIN_EMPTY controls separate inheritance and must remain untouched.
        for marker in ("true", "false"):
            with self.subTest(marker=marker):
                fixture = document(configuration(compiler="", linker="")).replace(
                    'valueType="stringList" ',
                    f'valueType="stringList" IS_VALUE_EMPTY="{marker}" IS_BUILTIN_EMPTY="{marker}" ')
                result = self.run_helpers(fixture, {"kind": "define", "value": "UNIT_FIRST=1"},
                                          {"kind": "linker", "value": "-UNIT_FIRST_LINKER"})
                root = ET.fromstring(self.assert_success(result))
                for super_class in (COMPILER, LINKER):
                    selected = root.find(f".//option[@superClass='{super_class}']")
                    self.assertEqual(marker, selected.get("IS_VALUE_EMPTY"))
                    self.assertEqual(marker, selected.get("IS_BUILTIN_EMPTY"))
                    self.assertEqual("stringList", selected.get("valueType"))
                    self.assertEqual("false", selected.find("listOptionValue").get("builtIn"))

    def test_matching_value_elsewhere_does_not_block_debug_insertion(self):
        release = configuration("Release", compiler='<listOptionValue value="-define=UNIT_SCOPE=1"/>',
                                linker='<listOptionValue value="-UNIT_SCOPE_LINKER"/>')
        unrelated = option(COMPILER + ".other", '<listOptionValue value="-define=UNIT_SCOPE=1"/>')
        fixture = document(configuration(extra=unrelated), release)
        result = self.run_helpers(fixture, {"kind": "define", "value": "UNIT_SCOPE=1"},
                                  {"kind": "linker", "value": "-UNIT_SCOPE_LINKER"})
        text = self.assert_success(result)
        self.assertEqual(1, entries(text, COMPILER).count("-define=UNIT_SCOPE=1"))
        self.assertEqual(1, entries(text, LINKER).count("-UNIT_SCOPE_LINKER"))
        before_release = ET.fromstring(fixture).find(".//configuration[@name='Release']")
        after_release = ET.fromstring(text).find(".//configuration[@name='Release']")
        self.assertEqual(semantics(before_release), semantics(after_release))

    def test_xml_special_characters_roundtrip_exactly_and_insertion_is_idempotent(self):
        define = 'UNIT_LABEL="A&B<日本語>\'text\'"'
        linker = '-UNIT_LINKER="A&B<日本語>\'text\'"'
        result = self.run_helpers(document(configuration()), {"kind": "define", "value": define},
                                  {"kind": "linker", "value": linker})
        text = self.assert_success(result)
        self.assertEqual(1, entries(text, COMPILER).count("-define=" + define))
        self.assertEqual(1, entries(text, LINKER).count(linker))
        repeated = self.run_helpers(text, {"kind": "define", "value": define},
                                    {"kind": "linker", "value": linker})
        self.assertEqual(text, self.assert_success(repeated))

    def test_exact_value_case_is_significant(self):
        fixture = document(configuration(compiler='<listOptionValue value="-define=unit_case=1"/>'))
        result = self.run_helpers(fixture, {"kind": "define", "value": "UNIT_CASE=1"})
        self.assertEqual(["-define=unit_case=1", "-define=UNIT_CASE=1"],
                         entries(self.assert_success(result), COMPILER))

    def test_generic_helper_uses_requested_superclass(self):
        result = self.run_helpers(document(configuration()),
            {"kind": "generic", "super_class": LINKER, "value": "-UNIT_GENERIC=1"})
        text = self.assert_success(result)
        self.assertIn("-UNIT_GENERIC=1", entries(text, LINKER))
        self.assertNotIn("-UNIT_GENERIC=1", entries(text, COMPILER))

    def test_missing_or_duplicate_option_is_rejected_even_if_value_is_elsewhere(self):
        for super_class, kind in ((COMPILER, "define"), (LINKER, "linker")):
            for variant in ("missing", "duplicate", "deceptive-id"):
                with self.subTest(kind=kind, variant=variant):
                    fixture = document(configuration())
                    if variant == "missing":
                        root = ET.fromstring(fixture)
                        selected = root.find(f".//option[@superClass='{super_class}']")
                        for parent in root.iter():
                            if selected in list(parent):
                                parent.remove(selected)
                                break
                        fixture = ET.tostring(root, encoding="unicode")
                    elif variant == "duplicate":
                        fixture = fixture.replace('</toolChain>', option(super_class) + '</toolChain>')
                    else:
                        fixture = fixture.replace(f'superClass="{super_class}"',
                                                  f'superClass="{super_class}.other"')
                    result = self.run_helpers(fixture, {"kind": kind, "value": "__FUNCTION__=__func__"})
                    self.assertIsNotNone(result["error"])
                    self.assertIsNone(result["text"])

    def test_missing_or_ambiguous_hardware_debug_configuration_is_rejected(self):
        fixtures = (
            document(configuration("Release")),
            document(configuration(), configuration()),
            document(configuration(), '<configuration name="HardwareDebug" id="empty-debug"/>'),
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                result = self.run_helpers(fixture, {"kind": "define", "value": "UNIT_AMBIGUOUS=1"})
                self.assertIsNotNone(result["error"])
                self.assertIsNone(result["text"])

    def test_invalid_xml_cannot_report_a_successful_update(self):
        result = self.run_helpers('<cproject><configuration name="HardwareDebug"></cproject>',
                                  {"kind": "define", "value": "UNIT_INVALID=1"})
        self.assertIsNotNone(result["error"])
        self.assertIsNone(result["text"])

    def test_real_project_and_builder_xml_roundtrip_support_both_wrappers(self):
        original_bytes = PROJECT.read_bytes()
        original = original_bytes.decode("utf-8")
        original_xml = ET.fromstring(original)
        for label, fixture, roundtrip in (("normal", original, False), ("builder-xml", original, True)):
            with self.subTest(label=label):
                result = self.run_helpers(fixture, {"kind": "define", "value": "UNIT_REAL_XML=1"},
                    {"kind": "linker", "value": "-UNIT_REAL_LINKER=1"}, roundtrip=roundtrip)
                text = self.assert_success(result)
                self.assertEqual(1, entries(text, COMPILER).count("-define=UNIT_REAL_XML=1"))
                self.assertEqual(1, entries(text, LINKER).count("-UNIT_REAL_LINKER=1"))
                for before in original_xml.findall(".//option"):
                    if before.get("superClass") not in (COMPILER, LINKER):
                        after = ET.fromstring(text).find(f".//option[@id='{before.get('id')}']")
                        self.assertIsNotNone(after)
                        self.assertEqual(semantics(before), semantics(after))
                repeated = self.run_helpers(text, {"kind": "define", "value": "UNIT_REAL_XML=1"},
                    {"kind": "linker", "value": "-UNIT_REAL_LINKER=1"})
                self.assertEqual(text, self.assert_success(repeated))
        self.assertEqual(original_bytes, PROJECT.read_bytes(), "The real .cproject must remain untouched")

    def test_actual_idt_profile_survives_builder_xml_roundtrip_and_extra_options(self):
        profile = subprocess.run([sys.executable, str(ROOT / "tools/idt_rx671_build_profile.py"),
            "--project", str(PROJECT.parent), "--group", "OTAPAL", "--version", "0.1.0"],
            text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
        self.assertEqual(0, profile.returncode, profile.stderr)
        before = json.loads(profile.stdout)["files"][".cproject"]
        compiler_values = entries(before, COMPILER)
        linker_values = entries(before, LINKER)
        self.assertIn("-define=APP_VERSION_MAJOR=0", compiler_values)
        self.assertIn("-define=RX671_OTA_RUNTIME_ENABLE=0", compiler_values)
        result = self.run_helpers(before,
            {"kind": "define", "value": "APP_VERSION_MAJOR=0"},
            {"kind": "define", "value": "UNIT_PROFILE_XML=1"},
            {"kind": "linker", "value": "-UNIT_PROFILE_LINKER=1"}, roundtrip=True)
        text = self.assert_success(result)
        self.assertEqual(compiler_values + ["-define=UNIT_PROFILE_XML=1"], entries(text, COMPILER))
        self.assertEqual(linker_values + ["-UNIT_PROFILE_LINKER=1"], entries(text, LINKER))
        repeated = self.run_helpers(text,
            {"kind": "define", "value": "APP_VERSION_MAJOR=0"},
            {"kind": "define", "value": "UNIT_PROFILE_XML=1"},
            {"kind": "linker", "value": "-UNIT_PROFILE_LINKER=1"})
        self.assertEqual(text, self.assert_success(repeated))


if __name__ == "__main__":
    unittest.main()

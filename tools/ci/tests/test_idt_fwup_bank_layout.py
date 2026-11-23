"""Native FWUP policy must retain the production app/boot bank boundary."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]


def numeric_define(text, name):
    values = re.findall(
        r"^\s*#\s*define\s+" + re.escape(name)
        + r"\s+\(\s*(0x[0-9a-fA-F]+|[0-9]+)[uUlL]*\s*\)",
        text, re.MULTILINE,
    )
    if len(values) != 1:
        raise AssertionError("Expected one numeric definition: " + name)
    return int(values[0], 0)


def section_start(project, section):
    tree = ET.parse(project / ".cproject")
    options = [node for node in tree.iter("option")
               if node.get("superClass", "").endswith(".option.linkerSection")]
    if len(options) != 1:
        raise AssertionError("Expected one linker section policy")
    starts = [int(match[2], 16) for match in re.finditer(
        r"(?:^|,)([^/]+)/([0-9a-fA-F]+)(?=,|$)", options[0].get("value", ""))
        if section in match[1].split(",")]
    if len(starts) != 1:
        raise AssertionError("Expected one section anchor: " + section)
    return starts[0]


class IdtFwupBankLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = (ROOT / "tools/build_rx72n_idt_transport.ps1").read_text(
            encoding="utf-8-sig")
        cls.targets = json.loads((ROOT / "tools/idt/targets.json").read_text(
            encoding="utf-8"))["targets"]
        cls.expected_areas = dict((target, int(area, 0)) for target, area in
            re.findall(r"'([^']+)'\s*\{\s*(0x[0-9a-fA-F]+)\s*\}",
                       cls.builder.split("$expectedAreaSize = switch ($Target) {", 1)[1]
                       .split("$fwupAreaSize =", 1)[0]))

    def test_all_normal_app_slots_end_at_the_reserved_bootloader_boundary(self):
        self.assertEqual(set(self.expected_areas), set(self.targets))
        for target, mapping in self.targets.items():
            projects = [ROOT / mapping["application_project"]]
            tsip = projects[0].parent.with_name(
                projects[0].parent.name + "_tsip") / "e2studio_ccrx"
            if tsip.exists():
                projects.append(tsip)
            boot = ROOT / mapping["bootloader_project"]
            boot_start = section_start(boot, "PResetPRG")
            self.assertEqual(boot_start, 0xFFFC0000)
            for project in projects:
                with self.subTest(target=target, project=project.parent.name):
                    config = (project / "src/frtos_config/rx_ota_config.h").read_text(
                            encoding="utf-8-sig")
                    main = numeric_define(config, "RX_OTA_CFG_MAIN_AREA_ADDR_L")
                    buffer = numeric_define(config, "RX_OTA_CFG_BUF_AREA_ADDR_L")
                    area = numeric_define(config, "RX_OTA_CFG_AREA_SIZE")
                    self.assertEqual(main, int(mapping["bank_range_start"], 16))
                    self.assertEqual(buffer, main + int(mapping["bank_shift"], 16))
                    self.assertEqual(area, self.expected_areas[target])
                    self.assertEqual(main + area, boot_start)
                    self.assertEqual(section_start(project, "EXCEPTVECT"),
                                     boot_start - 0x80)
                    self.assertEqual(section_start(project, "RESETVECT"),
                                     boot_start - 4)
                    self.assertEqual(int(mapping["bank_range_end"], 16),
                                     0xFFFFFFFF)

    def test_no_application_or_boot_project_selects_the_fwup_module(self):
        for name in (".project", ".cproject", "*.scfg"):
            for path in (ROOT / "Projects").glob("*/e2studio_ccrx/" + name):
                tree = ET.parse(path)
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertFalse(tree.findall(".//configuration[@name='r_fwup']"))
                    for node in tree.iter():
                        selected = node.get("name", "")
                        self.assertFalse(selected.startswith("Vendor/r_fwup"))
                        self.assertNotIn("/Vendor/r_fwup", node.get("value", ""))
                        self.assertNotIn("ota_fwup_wrap_code", node.get("value", ""))
                    for node in tree.findall(".//locationURI"):
                        self.assertNotIn("/r_fwup/", node.text or "")

    def test_native_pal_guard_uses_each_normal_application_layout(self):
        source = (ROOT / "Test/ports/rx72n_idt_otapal.c").read_text(encoding="utf-8")
        selectors = {"rx72n-ethernet": "IDT_TARGET_RX72N_ETHERNET",
                     "rx65n-bg96": "IDT_TARGET_RX65N_BG96",
                     "rx671-wifi": "IDT_TARGET_RX671_WIFI"}
        for target, selector in selectors.items():
            guard = re.search(r"#(?:if|elif) \( " + selector
                              + r" == 1 \)(.*?)(?=#(?:elif|else))", source, re.S).group(1)
            config = (ROOT / self.targets[target]["application_project"]
                      / "src/frtos_config/rx_ota_config.h").read_text(encoding="utf-8")
            with self.subTest(target=target):
                checks = re.findall(r"(RX_OTA_CFG_[A-Z_]+) != (0x[0-9A-Fa-f]+)U", guard)
                self.assertEqual(len(checks), 3)
                for macro, value in checks:
                    self.assertEqual(numeric_define(config, macro), int(value, 0))

    def test_tinycrypt_adapter_is_selected_only_by_bootloaders(self):
        applications = (
            "aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip",
            "aws_ether_rx72n_envision_kit", "aws_ether_rx72n_envision_kit_tsip",
        )
        for name in applications:
            project = ROOT / "Projects" / name / "e2studio_ccrx"
            with self.subTest(application=name):
                resources = ET.parse(project / ".project")
                for link in resources.findall(".//linkedResources/link"):
                    self.assertNotIn("tinycrypt", link.findtext("name", ""))
                    self.assertNotIn("tinycrypt", link.findtext("locationURI", ""))
                sources = ET.parse(project / ".cproject").findall(
                    ".//sourceEntries/entry")
                for source in sources:
                    self.assertNotIn("tinycrypt", source.get("name", ""))
                # Both links to Common/ports must remain excluded from root
                # recursion after the explicit adapter entry is removed.
                roots = [source for source in sources if source.get("name") == ""]
                self.assertEqual(len(roots), 1)
                exclusions = roots[0].get("excluding", "").split("|")
                self.assertIn("Common/ports/", exclusions)
                self.assertIn("src/application_code/ports/", exclusions)
        for target in self.targets.values():
            project = ROOT / target["bootloader_project"]
            with self.subTest(bootloader=project.parent.name):
                links = {link.findtext("name"): link.findtext("locationURI")
                         for link in ET.parse(project / ".project").findall(
                             ".//linkedResources/link")}
                self.assertIn("Vendor/tinycrypt", links)
                self.assertTrue(links["src/tinycrypt_rx_port.c"].endswith(
                    "/Common/ports/tinycrypt/tinycrypt_rx_port.c"))
                sources = ET.parse(project / ".cproject").findall(
                    ".//sourceEntries/entry")
                self.assertIn("Vendor/tinycrypt/lib/source",
                              [source.get("name") for source in sources])
                selected_src = [source for source in sources
                                if source.get("name") == "src"]
                self.assertEqual(len(selected_src), 1)
                self.assertNotIn("tinycrypt_rx_port.c",
                                 selected_src[0].get("excluding", ""))

    def test_rx65n_old_area_would_overlap_the_common_bootloader(self):
        target = self.targets["rx65n-bg96"]
        main = int(target["bank_range_start"], 16)
        boot_start = section_start(ROOT / target["bootloader_project"], "PResetPRG")
        self.assertEqual(self.expected_areas["rx65n-bg96"], 0xC0000)
        self.assertEqual(main + self.expected_areas["rx65n-bg96"], boot_start)
        self.assertGreater(main + 0xF0000, boot_start)

    def test_native_guard_preserves_bank_mode_and_signature_policy(self):
        guard = self.builder.split("$fwupAreaSize =", 1)[1].split(
            "Add-IdtSelectedSources", 1)[0]
        for name, expected in (("BSP_CFG_CODE_FLASH_BANK_MODE", 0),
                               ("RX_OTA_CFG_UPDATE_MODE", 0),
                               ("RX_OTA_CFG_FUNCTION_MODE", 1),
                               ("RX_OTA_CFG_SIGNATURE_VERIFICATION", 0)):
            self.assertRegex(guard, "'" + name + r"'\)\s*-ne\s*" + str(expected))
        self.assertIn("$fwupAreaSize -ne $expectedAreaSize", guard)
        self.assertIn("requires the reviewed dual-bank/ECDSA FWUP profile", guard)


if __name__ == "__main__":
    unittest.main()

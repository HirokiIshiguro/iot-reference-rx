"""Exercise the CC-RX context-restore policy with semantic XML mutations."""

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.ci import check_rx_context_restore as checker


def fixture() -> ET.Element:
    config = ET.Element("configuration", name="HardwareDebug")
    chain = ET.SubElement(ET.SubElement(config, "folderInfo", resourcePath=""), "toolChain")
    compiler = ET.SubElement(chain, "tool", superClass=checker.PREFIX + "base.compiler")
    ET.SubElement(compiler, "option", superClass=checker.COMPILER_ENABLED,
                  valueType="boolean", value="true")
    linker = ET.SubElement(chain, "tool", superClass=checker.PREFIX + "base.linker")
    ET.SubElement(linker, "option", superClass=checker.LINK_OPTIMIZE,
                  valueType="enumerated", value=checker.LINK_OPTIMIZE + ".all")
    forbid = ET.SubElement(linker, "option", superClass=checker.FORBID, valueType="stringList")
    for function in sorted(checker.FUNCTIONS):
        ET.SubElement(forbid, "listOptionValue", builtIn="false", value=function)
    return config


def get_option(config, key):
    return config.find(f".//option[@superClass='{key}']")


class RxContextRestoreTests(unittest.TestCase):
    def test_valid_policy_accepts_default_level2_and_unrelated_flags(self):
        config = fixture()
        compiler = config.find(".//tool[@superClass='" + checker.PREFIX + "base.compiler']")
        raw = ET.SubElement(compiler, "option", superClass=checker.PREFIX + "compiler.option.userBefore",
                            valueType="stringList")
        ET.SubElement(raw, "listOptionValue", value="-define=CONFIG_FREERTOS_ASSERT_FAIL_ABORT")
        checker.validate_configuration(config)
        ET.SubElement(compiler, "option", superClass=checker.COMPILER_OPTIMIZE,
                      valueType="enumerated", value=checker.COMPILER_OPTIMIZE + ".level2")
        checker.validate_configuration(config)

    def test_missing_or_wrong_function_is_rejected(self):
        for replacement in (None, "_prvStartFirstTask", "_prvYieldHandler", "_unrelatedFunction"):
            with self.subTest(replacement=replacement):
                config = fixture()
                option = get_option(config, checker.FORBID)
                if replacement is None:
                    option.remove(option[0])
                else:
                    option[0].set("value", replacement)
                with self.assertRaisesRegex(RuntimeError, "exactly the two outer"):
                    checker.validate_configuration(config)

    def test_missing_duplicate_and_wrong_type_option_are_rejected(self):
        for mutation in ("missing", "duplicate", "wrong_type", "duplicate_function"):
            with self.subTest(mutation=mutation):
                config = fixture()
                option = get_option(config, checker.FORBID)
                linker = config.find(".//tool[@superClass='" + checker.PREFIX + "base.linker']")
                if mutation == "missing":
                    linker.remove(option)
                elif mutation == "duplicate":
                    linker.append(ET.fromstring(ET.tostring(option)))
                elif mutation == "wrong_type":
                    option.set("valueType", "string")
                else:
                    option[1].set("value", option[0].get("value"))
                with self.assertRaises(RuntimeError):
                    checker.validate_configuration(config)

    def test_global_linker_workaround_and_compiler_changes_are_rejected(self):
        for kind, value in (("linker", "speed"), ("linker", "size"), ("linker", "none"),
                            ("compiler", "level0"), ("compiler", "level1"), ("compiler", "levelMax")):
            with self.subTest(kind=kind, value=value):
                config = fixture()
                if kind == "linker":
                    get_option(config, checker.LINK_OPTIMIZE).set("value", checker.LINK_OPTIMIZE + "." + value)
                else:
                    compiler = config.find(".//tool[@superClass='" + checker.PREFIX + "base.compiler']")
                    ET.SubElement(compiler, "option", superClass=checker.COMPILER_OPTIMIZE,
                                  valueType="enumerated", value=checker.COMPILER_OPTIMIZE + "." + value)
                with self.assertRaisesRegex(RuntimeError, "optimization must remain"):
                    checker.validate_configuration(config)
        config = fixture()
        get_option(config, checker.COMPILER_ENABLED).set("value", "false")
        with self.assertRaisesRegex(RuntimeError, "remain enabled"):
            checker.validate_configuration(config)

    def test_raw_optimizer_overrides_cannot_bypass_managed_policy(self):
        for flag in ("-optimize=all", "-optimize=speed", "-opt=2", "-nooptimize",
                     "-same_code", "-samecode_forbid=_other", "-symbol_delete", "-branch"):
            for role in ("compiler", "linker"):
                with self.subTest(role=role, flag=flag):
                    config = fixture()
                    tool = config.find(".//tool[@superClass='" + checker.PREFIX + "base." + role + "']")
                    raw = ET.SubElement(tool, "option", superClass=checker.PREFIX + role + ".option.userAfter",
                                        valueType="stringList")
                    ET.SubElement(raw, "listOptionValue", value=flag)
                    with self.assertRaisesRegex(RuntimeError, "raw user options"):
                        checker.validate_configuration(config)

    def test_per_file_override_and_option_on_wrong_tool_are_rejected(self):
        config = fixture()
        file_tool = ET.SubElement(ET.SubElement(config, "fileInfo"), "tool")
        ET.SubElement(file_tool, "option", superClass=checker.COMPILER_ENABLED,
                      valueType="boolean", value="false")
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            checker.validate_configuration(config)
        config = fixture()
        option = get_option(config, checker.FORBID)
        linker = config.find(".//tool[@superClass='" + checker.PREFIX + "base.linker']")
        linker.remove(option)
        config.find(".//tool").append(option)
        with self.assertRaisesRegex(RuntimeError, "root tool"):
            checker.validate_configuration(config)

    def test_repository_check_requires_all_five_apps_and_ignores_boot_projects(self):
        with tempfile.TemporaryDirectory(prefix="rx-context-restore-") as temporary:
            root = Path(temporary)
            for project in checker.PROJECTS:
                path = root / "Projects" / project / "e2studio_ccrx/.cproject"
                path.parent.mkdir(parents=True)
                document = ET.Element("cproject")
                document.append(fixture())
                ET.ElementTree(document).write(path, encoding="utf-8")
            # Boot roles are intentionally outside this RTOS-only policy.
            boot = root / "Projects/boot_loader_rx671_ek/e2studio_ccrx/.cproject"
            boot.parent.mkdir(parents=True)
            boot.write_text("not XML", encoding="utf-8")
            self.assertEqual({"projects": 5, "configurations": 5,
                "restore_function_exemptions_per_configuration": 2}, checker.check(root))
            (root / "Projects" / checker.PROJECTS[0] / "e2studio_ccrx/.cproject").unlink()
            with self.assertRaisesRegex(RuntimeError, checker.PROJECTS[0]):
                checker.check(root)

    def test_repository_projects_satisfy_policy(self):
        self.assertEqual(5, checker.check(Path(__file__).resolve().parents[3])["projects"])


if __name__ == "__main__":
    unittest.main()

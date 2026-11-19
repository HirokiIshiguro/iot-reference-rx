"""The six FreeRTOS projects use heap_5 and one shared piece of code that hands the heap regions to it."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "Common/FreeRTOS_common/freertos_heap.c"

# project -> (configTOTAL_HEAP_SIZE_N in KiB, FREERTOS_HEAP_UPPER_REGION_SIZE in KiB, startup file)
PROJECTS = {
    "aws_bg96_ck_rx65n": (256, 0, "src/frtos_startup/freertos_start.c"),
    "aws_bg96_ck_rx65n_tsip": (256, 0, "src/frtos_startup/freertos_start.c"),
    "aws_ether_rx72n_envision_kit": (320, 248, "src/frtos_startup/freertos_start.c"),
    "aws_ether_rx72n_envision_kit_tsip": (368, 148, "src/frtos_startup/freertos_start.c"),
    "aws_wifi_rx671_ek": (256, 0, "src/application/startup/freertos_user_port.c"),
    "aws_wifi_rx671_ek_tsip": (256, 0, "src/application/startup/freertos_user_port.c"),
}
MEMMANG = "Middleware/FreeRTOS/FreeRTOS-Kernel/portable/MemMang"


def read(project, relative):
    return (ROOT / "Projects" / project / "e2studio_ccrx" / relative).read_text(encoding="utf-8")


def linker_start(project):
    match = re.search(r'linker\.option\.linkerSection[^>]*\bvalue="([^"]*)"', read(project, ".cproject"))
    assert match, project
    return match.group(1)


class HeapLayoutTests(unittest.TestCase):
    def test_cproject_links_heap_5_and_excludes_the_other_allocators(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                match = re.search(r'<entry excluding="([^"]*)"[^>]*name="' + re.escape(MEMMANG) + '"', read(name, ".cproject"))
                self.assertIsNotNone(match)
                excluded = match.group(1).split("|")
                self.assertEqual(sorted(excluded), ["heap_1.c", "heap_2.c", "heap_3.c", "heap_4.c"])

    def test_application_allocates_the_heap(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                self.assertRegex(read(name, "src/frtos_config/FreeRTOSConfig.h"),
                                 r"(?m)^#define\s+configAPPLICATION_ALLOCATED_HEAP\s+1\s*$")

    def test_heap_sizes_are_unchanged(self):
        for name, (lower, upper, _) in PROJECTS.items():
            with self.subTest(project=name):
                config = read(name, "src/frtos_config/FreeRTOSConfig.h")
                if "rx671" in name:
                    self.assertRegex(config, r"(?m)^#define\s+RX671_FREERTOS_HEAP_SIZE_KB\s+%d\s*$" % lower)
                else:
                    self.assertRegex(config, r"(?m)^#define\s+configTOTAL_HEAP_SIZE_N\s+\(%d\)\s*$" % lower)
                heap_config = read(name, "src/application_code/freertos_heap_config.h")
                if upper:
                    self.assertRegex(heap_config, r"FREERTOS_HEAP_UPPER_REGION_SIZE\s+\(%dU \* 1024U\)" % upper)
                else:
                    self.assertRegex(heap_config, r"FREERTOS_HEAP_UPPER_REGION_SIZE\s+\(0U\)")

    def test_one_shared_file_hands_the_regions_to_every_project(self):
        self.assertTrue(SHARED.is_file())
        for name in PROJECTS:
            with self.subTest(project=name):
                folder = ROOT / "Projects" / name / "e2studio_ccrx"
                self.assertEqual(list(folder.rglob("freertos_heap.c")), [], "a private copy of the shared file")
                self.assertTrue((folder / "src/application_code/freertos_heap_config.h").is_file())
                project = (folder / ".project").read_text(encoding="utf-8")
                self.assertIn("AWS_IOT_MCU_ROOT/Common</locationURI>", project)
                cproject = (folder / ".cproject").read_text(encoding="utf-8")
                root_entry = re.search(r'<entry excluding="([^"]*)"[^>]*kind="sourcePath" name=""', cproject)
                self.assertIsNotNone(root_entry)
                for excluded in root_entry.group(1).split("|"):
                    self.assertFalse("Common/FreeRTOS_common/freertos_heap".startswith(excluded.rstrip("/")) and
                                     excluded.startswith("Common/FreeRTOS_common"), excluded)
                self.assertIn("${workspace_loc:/${ProjName}/src/application_code}", cproject)

    def test_shared_file_keeps_the_region_rules_of_heap_5(self):
        text = SHARED.read_text(encoding="utf-8")
        self.assertIn("vPortDefineHeapRegions(xHeapRegions)", text)
        self.assertLess(text.index("{ ucHeap, sizeof(ucHeap) }"), text.index("{ ucUpperHeap, sizeof(ucUpperHeap) }"))
        self.assertLess(text.index("{ ucUpperHeap, sizeof(ucUpperHeap) }"), text.index("{ NULL, 0U }"))

    def test_regions_are_defined_before_anything_allocates(self):
        for name, (_, _, startup) in PROJECTS.items():
            with self.subTest(project=name):
                text = read(name, startup)
                self.assertIn("extern void vConfigureHeapRegions(", text.replace("( void )", "(void)"))
                body = text[text.index("void Processing_Before_Start_Kernel(void)"):]
                call = body.index("vConfigureHeapRegions();")
                for later in ("xTraceInitialize()", "Kernel_Object_init()", "xTaskCreate("):
                    self.assertLess(call, body.index(later), later)

    def test_linker_places_the_heap_sections_without_losing_an_address(self):
        for name, (_, upper, _) in PROJECTS.items():
            with self.subTest(project=name):
                start = linker_start(name)
                self.assertEqual(start.count("B_FREERTOS_HEAP*"), 1)
                self.assertEqual(start.count("B_MULTI_TLS_HEAP*"), 1 if upper else 0)
                self.assertEqual(start.count(",B_FREERTOS_HEAP*,"), 1)
                # Without the heap sections every other address the link was reviewed with is still there.
                without = start.replace("B_FREERTOS_HEAP*,", "")
                addresses = re.findall(r"/([0-9A-F]+)", without)
                for address in ("04", "0FFFEFF80", "0FFFEFFFC") if "rx671" in name else ("0FFFEFF80", "0FFFEFFFC"):
                    self.assertIn(address, addresses)
                if "rx65n" in name:
                    self.assertEqual(addresses, ["04", "0FFFEFF80", "0FFFEFFFC", "00100000", "00102000", "00102300",
                                                 "00800000", "FFF00300"])
                    # The heap sits in the extended RAM block that held it as part of B_1.
                    self.assertIn("/00800000", start)
                    self.assertLess(start.index("B_FREERTOS_HEAP*"), start.index("/00800000"))
                    self.assertGreater(start.index("B_FREERTOS_HEAP*"), start.index("/00102300"))

    def test_rx671_ota_profile_builder_uses_the_same_heap_section(self):
        text = (ROOT / "tools/build_rx671_ota_images.py").read_text(encoding="utf-8")
        self.assertEqual(text.count('"SU,SI,B_FREERTOS_HEAP*,B_1,'), 2)
        for name in ("aws_wifi_rx671_ek", "aws_wifi_rx671_ek_tsip"):
            self.assertIn("SU,SI,B_FREERTOS_HEAP*,B_1,R_1,B_2,R_2,B,R,B_8,R_8,RPFRAM2/04,", linker_start(name))

    def test_boot_loaders_do_not_use_freertos(self):
        for name in ("boot_loader_ck_rx65n", "boot_loader_rx671_ek", "boot_loader_rx72n_envision_kit"):
            with self.subTest(project=name):
                folder = ROOT / "Projects" / name / "e2studio_ccrx"
                self.assertRegex((folder / "src/smc_gen/r_config/r_bsp_config.h").read_text(encoding="utf-8"),
                                 r"#define BSP_CFG_RTOS_USED\s+\(0\)")
                self.assertNotIn("FreeRTOS", (folder / ".cproject").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

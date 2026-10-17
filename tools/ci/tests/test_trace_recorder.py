"""Trace source selection and actual original Kernel/recorder preprocessing.

Host preprocessing validates inclusion/hooks, not MCU code generation or RTT.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.ci.tests import test_product_oss_api as host

ROOT = Path(__file__).resolve().parents[3]
PROJECTS = ("aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip",
            "aws_ether_rx72n_envision_kit", "aws_ether_rx72n_envision_kit_tsip", "aws_wifi_rx671_ek")
RECORDER = ROOT / "Middleware/3rdparty/TraceRecorderSource"
KERNEL = ROOT / "Middleware/FreeRTOS/FreeRTOS-Kernel"
COMMON = ROOT / "Common/ports/trace_recorder"
LINK = "AWS_IOT_MCU_ROOT/Middleware/3rdparty/TraceRecorderSource"


def selected_recorder_sources(project):
    metadata = ET.parse(project / ".cproject").getroot()
    description = ET.parse(project / ".project").getroot()
    links = description.findall("linkedResources/link[name='TraceRecorder']")
    if len(links) != 1 or links[0].findtext("locationURI") != LINK:
        raise ValueError("Recorder must use the single original submodule")
    selected = []
    for entry in metadata.iter("entry"):
        name = entry.get("name", "")
        if entry.get("kind") != "sourcePath" or not name.startswith("TraceRecorder"):
            continue
        folder = RECORDER / name.removeprefix("TraceRecorder").lstrip("/")
        exclusions = entry.get("excluding", "").split("|")
        for path in folder.rglob("*.c"):
            relative = path.relative_to(folder).as_posix()
            if not any(item and (relative == item or relative.startswith(item)) for item in exclusions):
                selected.append(path.relative_to(RECORDER).as_posix())
    return selected


class TraceMetadataTests(unittest.TestCase):
    def test_every_app_selects_same_original_core_and_public_ports(self):
        expected = {x.name for x in RECORDER.glob("*.c")} | {
            "kernelports/FreeRTOS/trcKernelPort.c", "streamports/Jlink_RTT/SEGGER_RTT.c",
            "streamports/Jlink_RTT/trcStreamPort.c"}
        self.assertEqual(len(expected), 29)
        for name in PROJECTS:
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                selected = selected_recorder_sources(project)
                self.assertEqual(set(selected), expected)
                self.assertEqual(len(selected), len(expected), "Duplicate recorder compilation")
                metadata = ET.parse(project / ".cproject").getroot()
                roots = [x for x in metadata.iter("entry") if x.get("kind") == "sourcePath" and x.get("name") == ""]
                self.assertEqual(len(roots), 1)
                self.assertIn("TraceRecorder/", roots[0].get("excluding", "").split("|"))
                includes = [x.get("value") for o in metadata.iter("option")
                    if o.get("superClass") == "com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.include"
                    for x in o.findall("listOptionValue")]
                facade = '"${workspace_loc:/${ProjName}/TraceProduct/freertos_wrap}"'
                kernel = '"${workspace_loc:/${ProjName}/Middleware/FreeRTOS/FreeRTOS-Kernel/include}"'
                self.assertLess(includes.index(facade), includes.index(kernel))
                self.assertFalse(any((project / "src/TraceRecorder").rglob("*.c")))
                self.assertFalse(any((project / "src/tracealyzer_recorder").rglob("*.c")))
                config = (project / "src/frtos_config/FreeRTOSConfig.h").read_text(encoding="utf-8")
                self.assertRegex(config, r"#define\s+CONFIG_USE_PERCEPIO_TRACE_RECORDER\s+1\b")

    def test_product_config_alias_avoids_the_actual_common_ports_filter(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                description = ET.parse(project / ".project").getroot()
                links = description.findall("linkedResources/link[name='TraceProduct']")
                self.assertEqual(len(links), 1)
                self.assertEqual(links[0].findtext("locationURI"),
                                 "AWS_IOT_MCU_ROOT/Common/ports/trace_recorder")
                filters = description.findall("filteredResources/filter")
                self.assertFalse(any((f.findtext("name") or "").startswith("TraceProduct") for f in filters))
                common_filters = [f for f in filters if f.findtext("name") == "Common"]
                self.assertTrue(any("name-matches-false-true-ports" in
                                    (f.findtext("matcher/arguments") or "") for f in common_filters))
                metadata = ET.parse(project / ".cproject").getroot()
                includes = [x.get("value") for o in metadata.iter("option")
                    if o.get("superClass") == "com.renesas.cdt.managedbuild.renesas.ccrx.compiler.option.include"
                    for x in o.findall("listOptionValue")]
                for leaf in ("config", "freertos_wrap"):
                    self.assertIn('"${workspace_loc:/${ProjName}/TraceProduct/' + leaf + '}"', includes)
                    self.assertFalse(any("Common/ports/trace_recorder/" + leaf in value for value in includes))

    def test_startup_initializes_before_objects_and_starts_all_main_profiles(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                project = ROOT / "Projects" / name / "e2studio_ccrx"
                startup = project / ("src/application/startup/freertos_user_port.c" if name == "aws_wifi_rx671_ek" else "src/frtos_startup/freertos_start.c")
                text = startup.read_text(encoding="utf-8")
                body = text[text.index("void Processing_Before_Start_Kernel(void)\n{"):]
                self.assertLess(body.index("xTraceInitialize()"), body.index("Kernel_Object_init()"))
                self.assertLess(body.index("xTraceInitialize()"), body.index("xTaskCreate("))
                if "rx72n" in name:
                    self.assertLess(body.index("vConfigureHeapRegions()"), body.index("xTraceInitialize()"))
                main = project / ("src/aws_wifi_rx671_ek.c" if name == "aws_wifi_rx671_ek" else "src/application_code/main.c")
                text = main.read_text(encoding="utf-8")
                self.assertRegex(text, r"void main_task\([^\n]*\)\n\{\n\s*\(void\)xTraceEnable\(TRC_START\);")
                self.assertNotIn("TRC_START_FROM_HOST", text)


@unittest.skipUnless(host.GCC or host.MSVC, "Host preprocessor required; no MCU build")
class TracePreprocessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = None
        if not host.GCC:
            with tempfile.TemporaryDirectory(prefix="trace-host-env-") as folder:
                setup = host.MSVC.parents[6] / "Auxiliary/Build/vcvars64.bat"
                script = Path(folder) / "environment.cmd"
                script.write_text('@echo off\ncall "' + str(setup) + '" >nul\nif errorlevel 1 exit /b 1\nset INCLUDE\nset PATH\n', encoding="utf-8")
                output = subprocess.run(["cmd.exe", "/d", "/c", str(script)], capture_output=True,
                                        text=True, check=True, timeout=20).stdout
                cls.environment = dict(os.environ, VSLANG="1033")
                for line in output.splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        if key.upper() in ("INCLUDE", "PATH"):
                            cls.environment[key] = value

    def preprocess(self, name, path=None, *, facade=True):
        with tempfile.TemporaryDirectory(prefix="trace-preprocess-") as temporary:
            fixture = Path(temporary)
            (fixture / "machine.h").write_text("/* Host preprocessing only; no MCU intrinsic execution. */\n")
            (fixture / "r_bsp_config.h").write_text("#define BSP_CFG_RTOS_USED 1\n")
            (fixture / "platform.h").write_text("#define BSP_ICLK_HZ 120000000UL\n#define BSP_PCLKB_HZ 60000000UL\n")
            project = ROOT / "Projects" / name / "e2studio_ccrx"
            port = KERNEL / "portable/Renesas" / ("RX600v2" if "rx65n" in name else "RX700v3_DPFPU")
            includes = ([COMMON / "freertos_wrap"] if facade else []) + [fixture,
                project / "src/frtos_config", COMMON / "config", KERNEL / "include", port,
                RECORDER / "include", RECORDER / "kernelports/FreeRTOS/include",
                RECORDER / "streamports/Jlink_RTT/include"]
            if path is None:
                path = fixture / "probe.c"
                path.write_text(r'''
#include <FreeRTOS.h>
#if CONFIG_USE_PERCEPIO_TRACE_RECORDER != 1 || TRC_USE_TRACEALYZER_RECORDER != 1
#error Actual trace hooks are not enabled
#endif
#if TRC_CFG_INCLUDE_ISR_TRACING != 0 || TRC_CFG_SCHEDULING_ONLY != 1
#error Low-noise production profile changed
#endif
#define STRING_(...) #__VA_ARGS__
#define STRING(...) STRING_(__VA_ARGS__)
const char * probe_tick=STRING(traceTASK_INCREMENT_TICK(1234));
const char * probe_switch=STRING(traceTASK_SWITCHED_IN());
const char * probe_create=STRING(traceTASK_CREATE(testTask));
const char * probe_mask=STRING(TRC_KERNEL_PORT_SET_INTERRUPT_MASK());
const char * probe_counter=STRING(TRC_HWTC_COUNT);
const char * probe_frequency=STRING(TRC_HWTC_FREQ_HZ);
''', encoding="utf-8")
            if host.GCC:
                arguments = [host.GCC, "-E", "-P", "-D__CCRX__"] + ["-I" + str(x) for x in includes]
            else:
                arguments = [str(host.MSVC), "/nologo", "/TC", "/EP", "/D__CCRX__"] + ["/I" + str(x) for x in includes]
            return subprocess.run([*arguments, str(path)], cwd=fixture, env=self.environment,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)

    def test_original_kernel_hook_expansion_for_every_app(self):
        for name in PROJECTS:
            with self.subTest(project=name):
                result = self.preprocess(name)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout[-1800:])
                for text in ("pxTraceTimestamp->osTickCount", "xTraceTaskSwitch", "xTraceObjectRegisterWithoutHandle",
                             "CMT0.CMCNT", "CMT0.CMCOR"):
                    self.assertIn(text, result.stdout)
                self.assertRegex(result.stdout, r'probe_mask=.*get_ipl\(\).*set_ipl\(')
                tasks = self.preprocess(name, KERNEL / "tasks.c")
                self.assertEqual(tasks.returncode, 0, tasks.stderr + tasks.stdout[-1800:])
                self.assertGreater(tasks.stdout.count("xTraceObjectRegisterWithoutHandle"), 1)
                self.assertGreater(tasks.stdout.count("xTraceTaskSwitch"), 1)
                self.assertRegex(tasks.stdout, r"pxTraceTimestamp->osTickCount\s*=\s*\(xTickCount\)\s*\+\s*1")
        # This fixture must reject the native empty hooks when the facade is bypassed.
        result = self.preprocess(PROJECTS[0], facade=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Actual trace hooks are not enabled", result.stderr + result.stdout)

    def test_original_recorder_source_closure_preprocesses_with_both_rx_ports(self):
        for name in (PROJECTS[0], PROJECTS[-1]):
            project = ROOT / "Projects" / name / "e2studio_ccrx"
            for relative in selected_recorder_sources(project):
                with self.subTest(project=name, source=relative):
                    result = self.preprocess(name, RECORDER / relative)
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout[-1800:])


if __name__ == "__main__":
    unittest.main()

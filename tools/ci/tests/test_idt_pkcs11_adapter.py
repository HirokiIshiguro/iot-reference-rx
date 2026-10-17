"""Check product group routing with the pinned, unchanged Unity public API.

Host fixture groups are opaque test doubles; these tests do not execute or
claim success for the PKCS11 assertions on a microcontroller.
"""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from tools.ci.tests import test_product_oss_api as product_api

ROOT = Path(__file__).resolve().parents[3]
UNITY = ROOT / "Test/Unity"
BUILDER = ROOT / "tools/build_rx72n_idt_transport.ps1"


@unittest.skipUnless(product_api.GCC or product_api.MSVC, "Host C compiler required")
class Pkcs11AdapterTests(unittest.TestCase):
    def run_adapter(self, selected):
        source = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#define RX_IDT_PKCS11_SELECTED_GROUP HOST_SELECTION
#include "Test/ports/rx72n_idt_pkcs11.c"
static unsigned calls[3], deleted, delay;
static int printed_failures = -1;
void fixture_printf(const char *format, ...) {
    va_list args; (void)format;
    va_start(args, format); printed_failures=va_arg(args,int); va_end(args);
}
void FRTest_TimeDelay(uint32_t milliseconds) { assert(milliseconds==5000); delay++; }
void vTaskDelete(void *task) { assert(task==NULL); deleted++; }
BaseType_t xTaskCreate(void (*entry)(void *), const char *name, unsigned stack,
                     void *arg, unsigned priority, void *handle) {
    assert(strcmp(name,"IDT PKCS11")==0 && stack==8192 && arg==NULL);
    assert(priority==1 && handle==NULL); entry(arg); return 7;
}
TEST_GROUP(Full_PKCS11_StartFinish);
TEST_SETUP(Full_PKCS11_StartFinish) {}
TEST_TEAR_DOWN(Full_PKCS11_StartFinish) {}
TEST(Full_PKCS11_StartFinish, HostFailure) { TEST_FAIL_MESSAGE("host fixture failure"); }
TEST_GROUP_RUNNER(Full_PKCS11_StartFinish) {
    calls[0]++; RUN_TEST_CASE(Full_PKCS11_StartFinish, HostFailure);
}
TEST_GROUP(Full_PKCS11_Capabilities);
TEST_SETUP(Full_PKCS11_Capabilities) {}
TEST_TEAR_DOWN(Full_PKCS11_Capabilities) {}
TEST(Full_PKCS11_Capabilities, HostPass) { TEST_ASSERT_TRUE(1); }
TEST_GROUP_RUNNER(Full_PKCS11_Capabilities) {
    calls[1]++; RUN_TEST_CASE(Full_PKCS11_Capabilities, HostPass);
}
TEST_GROUP(Full_PKCS11_NoObject);
TEST_SETUP(Full_PKCS11_NoObject) {}
TEST_TEAR_DOWN(Full_PKCS11_NoObject) {}
TEST(Full_PKCS11_NoObject, HostPass) { TEST_ASSERT_TRUE(1); }
TEST_GROUP_RUNNER(Full_PKCS11_NoObject) {
    calls[2]++; RUN_TEST_CASE(Full_PKCS11_NoObject, HostPass);
}
int main(void) {
    /* A stale fixture filter must not silently skip the selected group. */
    UnityFixture.GroupFilter="stale"; UnityFixture.NameFilter="stale";
    UnityFixture.Silent=1; UnityFixture.RepeatCount=3;
    assert(xStartIdtPkcs11Test()==7 && delay==1 && deleted==1);
    assert(UnityFixture.GroupFilter==NULL && UnityFixture.NameFilter==NULL);
    assert(UnityFixture.Silent==0 && UnityFixture.RepeatCount==1);
#if HOST_SELECTION == 1
    assert(calls[0]==1 && calls[1]==1 && calls[2]==0);
    assert(printed_failures==1 && Unity.NumberOfTests==2 && Unity.TestFailures==1);
#else
    assert(calls[0]==0 && calls[1]==1 && calls[2]==1);
    assert(printed_failures==0 && Unity.NumberOfTests==2 && Unity.TestFailures==0);
#endif
    return 0;
}
'''.replace("HOST_SELECTION", str(selected))
        headers = {
            "FreeRTOS.h": "#ifndef FIXTURE_FREERTOS_H\n#define FIXTURE_FREERTOS_H\n"
                "#include <stdint.h>\ntypedef int BaseType_t;\n"
                "void fixture_printf(const char *, ...);\n#define configPRINTF(args) fixture_printf args\n#endif\n",
            "task.h": "#include \"FreeRTOS.h\"\n#define tskIDLE_PRIORITY 0\n"
                "BaseType_t xTaskCreate(void (*)(void *),const char *,unsigned,void *,unsigned,void *);\n"
                "void vTaskDelete(void *);\n",
            "platform.h": "#define BSP_MCU_RX72N 1\n#define IDT_TARGET_RX72N_ETHERNET 1\n"
                "#define ENABLE_IDT_PKCS11_TEST 1\n",
            "test_execution_config.h": "#define CORE_PKCS11_TEST_ENABLED 1\n"
                "#define TRANSPORT_INTERFACE_TEST_ENABLED 0\n#define MQTT_TEST_ENABLED 0\n"
                "#define DEVICE_ADVISOR_TEST_ENABLED 0\n#define OTA_PAL_TEST_ENABLED 0\n"
                "#define OTA_E2E_TEST_ENABLED 0\n",
            "test_param_config.h": "#define PKCS11_TEST_RSA_KEY_SUPPORT 0\n"
                "#define PKCS11_TEST_EC_KEY_SUPPORT 1\n#define PKCS11_TEST_IMPORT_PRIVATE_KEY_SUPPORT 1\n"
                "#define PKCS11_TEST_GENERATE_KEYPAIR_SUPPORT 0\n#define PKCS11_TEST_PREPROVISIONED_SUPPORT 0\n",
            "platform_function.h": "#include <stdint.h>\nvoid FRTest_TimeDelay(uint32_t);\n",
        }
        product_api.ProductApiTests().compile_run(source, headers=headers,
            extra_sources=(UNITY / "src/unity.c", UNITY / "extras/fixture/src/unity_fixture.c",
                           UNITY / "extras/memory/src/unity_memory.c"),
            extra_includes=(UNITY / "src", UNITY / "extras/fixture/src", UNITY / "extras/memory/src"))

    def test_start_finish_routes_capabilities_and_preserves_unity_failure(self):
        self.run_adapter(1)

    def test_no_object_routes_capabilities_and_no_object_public_groups(self):
        self.run_adapter(2)

    def test_product_unity_output_retains_markers_pacing_and_all_long_line_bytes(self):
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "Test/ports/rx_idt_unity_output.c"
static char recorded[4096];
static unsigned chunks, delays;
void host_print(const char *text) { assert(strlen(recorded)+strlen(text)<sizeof(recorded)); strcat(recorded,text); chunks++; }
void vTaskDelay(unsigned ticks) { assert(ticks==100); delays++; }
int main(void) {
    unsigned count;
    RxIdt_UnityOutputStart();
    assert(strcmp(recorded,"---------STARTING TESTS---------\n")==0 && chunks==1 && delays==1);
    RxIdt_UnityOutputChar('A'); RxIdt_UnityOutputChar('\n');
    assert(strstr(recorded,"A\n") && chunks==2 && delays==2);
    RxIdt_UnityOutputFlush(); assert(chunks==2 && delays==2);
    /* More than a buffer capacity must preserve each byte and final partial line. */
    recorded[0]=0; chunks=delays=0;
    for(count=0;count<2050;count++) RxIdt_UnityOutputChar('x');
    RxIdt_UnityOutputComplete();
    assert(strlen(recorded)==2050+strlen("-------ALL TESTS FINISHED-------\n"));
    for(count=0;count<2050;count++) assert(recorded[count]=='x');
    assert(strcmp(recorded+2050,"-------ALL TESTS FINISHED-------\n")==0);
    assert(chunks==4 && delays==4);
    return 0;
}
'''
        headers = {"FreeRTOS.h": "#define pdMS_TO_TICKS(x) (x)\n",
            "task.h": "void vTaskDelay(unsigned);\n",
            "iot_logging_task.h": "void host_print(const char *);\n#define configPRINT_STRING(text) host_print(text)\n"}
        product_api.ProductApiTests().compile_run(source, headers=headers)


class Pkcs11InputTests(unittest.TestCase):
    def test_core_case_obligations_come_from_pinned_original_group_runners(self):
        body = (ROOT / "Test/FreeRTOS-Libraries-Integration-Tests/src/pkcs11/core_pkcs11_test.c").read_text()
        actual = {}
        for group in ("Full_PKCS11_StartFinish", "Full_PKCS11_Capabilities", "Full_PKCS11_NoObject"):
            section = re.search(r"TEST_GROUP_RUNNER\( " + group + r" \)\s*\{(.*?)\n\}", body, re.S)
            self.assertIsNotNone(section)
            actual[group] = re.findall(r"RUN_TEST_CASE\( " + group + r", (\w+) \)", section.group(1))
        self.assertEqual([5, 1, 4], [len(cases) for cases in actual.values()])
        self.assertEqual(10, sum(len(cases) for cases in actual.values()))

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 required")
    def test_missing_or_out_of_scope_selection_fails_before_source_access(self):
        for arguments in (("-TestGroup", "PKCS11"),
                          ("-TestGroup", "Transport", "-Pkcs11Group", "NoObject")):
            result = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-File", str(BUILDER),
                "-ProjectRoot", str(ROOT / "no-such-native-source"), *arguments],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Pkcs11Group", result.stderr)
            self.assertNotIn("Cannot find path", result.stderr)


if __name__ == "__main__":
    unittest.main()

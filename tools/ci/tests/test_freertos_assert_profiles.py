"""Exercise the actual app config and assert handler across build profiles.

Only the hardware critical-section/NOP and Unity jump are mocked. The handler
is compiled verbatim from each product startup file; no Kernel body is replaced.
"""
from pathlib import Path
import unittest

from tools.ci.tests import test_product_oss_api as host

ROOT = Path(__file__).resolve().parents[3]
PROJECTS = ("aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip",
            "aws_ether_rx72n_envision_kit", "aws_ether_rx72n_envision_kit_tsip",
            "aws_wifi_rx671_ek")
UNUSED_SELECTORS = ("INCLUDE_xEventGroupSetBitsFromISR",
                    "INCLUDE_xEventGroupSetBitFromISR", "INCLUDE_xResumeFromISR",
                    "INCLUDE_vTaskCleanUpResources", "INCLUDE_xTimerGetTimerTaskHandle")
PROFILES = ((), ("NDEBUG=1",), ("CONFIG_FREERTOS_ASSERT_DISABLE=1",),
            ("ENABLE_UNIT_TESTS=1",), ("FREERTOS_ENABLE_UNIT_TESTS=1",),
            ("CONFIG_FREERTOS_ASSERT_FAIL_ABORT=1",),
            ("ENABLE_UNIT_TESTS=1", "NDEBUG=1", "CONFIG_FREERTOS_ASSERT_DISABLE=1"),
            ("ENABLE_UNIT_TESTS=1", "CONFIG_FREERTOS_ASSERT_FAIL_ABORT=1"))


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required; no MCU execution")
class FreeRtosAssertProfilesTests(unittest.TestCase):
    def test_each_config_stops_once_even_in_release_and_preserves_unit_test_abort(self):
        for name in PROJECTS:
            project = ROOT / "Projects" / name / "e2studio_ccrx"
            is_rx671 = name == "aws_wifi_rx671_ek"
            startup = project / ("src/application/startup/freertos_user_port.c"
                                 if is_rx671 else "src/frtos_startup/freertos_start.c")
            text = startup.read_text(encoding="utf-8")
            begin = text.index("void vAssertCalled(void)\n{")
            end = text.index("} /* End of function vAssertCalled() */", begin) + 1
            handler = text[begin:end]
            config = (project / "src/frtos_config/FreeRTOSConfig.h").relative_to(ROOT).as_posix()
            no_legacy = "\n".join("#ifdef " + name + "\n#error Unused Kernel selector remains\n#endif"
                                  for name in UNUSED_SELECTORS)
            for defines in PROFILES:
                with self.subTest(project=name, defines=defines):
                    unit = any(x.startswith(("ENABLE_UNIT_TESTS=", "FREERTOS_ENABLE_UNIT_TESTS="))
                               for x in defines)
                    expected = 2 if unit and not is_rx671 else 1
                    source = r'''
#include <stdint.h>
#include <stddef.h>
#include <setjmp.h>
static jmp_buf stopped;
static unsigned critical, exited, reason, evaluations;
static void stop(unsigned why) { reason=why; longjmp(stopped,1); }
#define taskENTER_CRITICAL() (++critical)
#define taskEXIT_CRITICAL() (++exited)
#define R_BSP_NOP() stop(1)
#define portNOP() stop(1)
''' + '#include "' + config + '"\n' + no_legacy + r'''
#if INCLUDE_xTimerPendFunctionCall != 1 || INCLUDE_xTaskAbortDelay != 1
#error Common API selections are inconsistent
#endif
''' + handler + r'''
int main(void) {
    configASSERT(++evaluations);
    if(evaluations!=1 || critical || exited || reason) return 1;
    if(setjmp(stopped)==0) {
        configASSERT((++evaluations,0));
        return 2; /* An assert may never disappear or return silently. */
    }
    if(evaluations!=2 || reason!=EXPECTED_STOP || exited) return 3;
    if(critical!=(EXPECTED_STOP==1 ? 1U : 0U)) return 4;
    return 0;
}
'''
                    host.ProductApiTests.compile_run(self, source,
                        headers={"unity.h": "#define TEST_ABORT() stop(2)\n",
                                 "unity_internals.h": "#define TEST_ABORT() stop(2)\n"},
                        extra_includes=(project / "src/smc_gen/r_config",),
                        extra_defines=(*defines, "EXPECTED_STOP=" + str(expected)))


if __name__ == "__main__":
    unittest.main()

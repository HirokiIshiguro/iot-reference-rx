"""Exercise product OTA gate code with the unchanged public event-group API.

Host doubles model API calls; this does not qualify the existing manufacturing
self-test stub, OTA image acceptance, bank switching or a hardware scheduler.
"""
from pathlib import Path
import re
import unittest

from tools.ci.tests import test_product_oss_api as product_api

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / "Middleware/FreeRTOS/FreeRTOS-Kernel/include"
TARGETS = ("aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip")


def function_body(path, declaration):
    body = path.read_text(encoding="utf-8")
    start = body.index(declaration)
    brace = body.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (body[end] == "{") - (body[end] == "}")
        end += 1
    return body[start:end]


API = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <setjmp.h>
/* Host kernel port type/config fixture; event-group declarations are original. */
#define INC_FREERTOS_H
#define TIMERS_H
typedef int BaseType_t;
typedef unsigned UBaseType_t;
typedef uint32_t TickType_t;
#define TICK_TYPE_WIDTH_16_BITS 16
#define TICK_TYPE_WIDTH_32_BITS 32
#define TICK_TYPE_WIDTH_64_BITS 64
#define configTICK_TYPE_WIDTH_IN_BITS TICK_TYPE_WIDTH_32_BITS
#define configSUPPORT_DYNAMIC_ALLOCATION 1
#define configSUPPORT_STATIC_ALLOCATION 0
#define configUSE_TRACE_FACILITY 0
#define configUSE_TIMERS 0
#define PRIVILEGED_FUNCTION
#include "event_groups.h"
#define pdTRUE 1
#define pdFALSE 0
#define portMAX_DELAY UINT32_MAX
static jmp_buf stopped;
static unsigned stage, logged;
static int allocation_fails;
static EventBits_t bits;
EventGroupHandle_t xStartDemoEventGroup;
#define configASSERT(condition) do { if(!(condition)) longjmp(stopped,1); } while(0)
EventGroupHandle_t xEventGroupCreate(void) {
    assert(stage++==1); bits=0;
    return allocation_fails ? NULL : (EventGroupHandle_t)(uintptr_t)1;
}
EventBits_t xEventGroupSetBits(EventGroupHandle_t group,const EventBits_t value) {
    assert(group==xStartDemoEventGroup && group!=NULL); bits |= value; return bits;
}
EventBits_t xEventGroupWaitBits(EventGroupHandle_t group,const EventBits_t mask,
                              const BaseType_t clear,const BaseType_t all,const TickType_t wait) {
    assert(group==xStartDemoEventGroup && group!=NULL && mask==1);
    assert(clear==pdFALSE && all==pdFALSE && wait==portMAX_DELAY);
    return bits;
}
'''


@unittest.skipUnless(product_api.GCC or product_api.MSVC, "Host C compiler required")
class OtaStartupGateTests(unittest.TestCase):
    def test_both_owned_startups_create_group_and_stop_before_logging_if_allocation_fails(self):
        for target in TARGETS:
            path = ROOT / "Projects" / target / "e2studio_ccrx/src/application_code/main.c"
            original = path.read_text(encoding="utf-8")
            self.assertRegex(original, r'EventGroupHandle_t xStartDemoEventGroup\s*=\s*NULL;')
            body = function_body(path, "void prvMiscInitialization(void)\n{")
            source = API + r'''
#define tskIDLE_PRIORITY 0
#define mainLOGGING_TASK_STACK_SIZE 11
#define mainLOGGING_MESSAGE_QUEUE_LENGTH 7
void CLI_Support_Settings(void) { assert(stage++==0); }
void xLoggingTaskInitialize(unsigned stack,unsigned priority,unsigned length) {
    assert(stage++==2 && stack==11 && priority==2 && length==7); logged++;
}
''' + body + r'''
int main(void) {
    stage=0; allocation_fails=0; logged=0;
    assert(setjmp(stopped)==0); prvMiscInitialization();
    assert(stage==3 && logged==1 && xStartDemoEventGroup!=NULL && bits==0);
    stage=0; allocation_fails=1; logged=0;
    if(setjmp(stopped)==0) { prvMiscInitialization(); assert(!"allocation failure must assert"); }
    assert(stage==2 && logged==0 && xStartDemoEventGroup==NULL);
    return 0;
}
'''
            product_api.ProductApiTests().compile_run(source, extra_includes=(KERNEL,))

    def test_ota_version_selftest_branch_releases_only_success_and_keeps_wait_flags(self):
        ota = ROOT / "Demos/OtaOverMqtt/OtaOverMqttDemo.c"
        version = function_body(ota, "static OtaPalJobDocProcessingResult_t verifyVersion(char *updaterVersion)\n{")
        pubsub = (ROOT / "Demos/SimplePubSub/simple_pub_sub_task.c").read_text(encoding="utf-8")
        waits = re.findall(r"xEventGroupWaitBits\(xStartDemoEventGroup, SELF_TEST_PASSED,[^;]+;", pubsub)
        self.assertEqual(1, len(waits))
        for target in TARGETS:
            config = ROOT / "Projects" / target / "e2studio_ccrx/src/frtos_config/demo_config.h"
            definitions = re.findall(r"^#define SELF_TEST_PASSED[^\r\n]+", config.read_text(), re.M)
            self.assertEqual(1, len(definitions))
            source = API + "\n" + definitions[0] + r'''
#include <stdlib.h>
#define LogInfo(args) ((void)0)
#define LogError(args) ((void)0)
typedef enum { OtaPalNewImageBooted, OtaPalNewImageBootFailed,
               OtaPalNewImageSameVersionSelfTestOK, OtaPalNewImageSameVersionSelfTestNG } OtaPalJobDocProcessingResult_t;
static struct { struct { uint32_t unsignedVersion32; } u; } appFirmwareVersion;
static BaseType_t test_result;
static unsigned test_calls;
BaseType_t OtaSelfTest(void) { test_calls++; return test_result; }
''' + version + "\nvoid wait_for_ota(void) { " + waits[0] + r''' }
int main(void) {
    xStartDemoEventGroup=(EventGroupHandle_t)(uintptr_t)1;
    appFirmwareVersion.u.unsignedVersion32=0x102;
    test_result=pdFALSE; bits=0;
    assert(verifyVersion("101")==OtaPalNewImageBootFailed && bits==0);
    assert(verifyVersion("102")==OtaPalNewImageSameVersionSelfTestNG && bits==0);
    test_result=pdTRUE;
    assert(verifyVersion("101")==OtaPalNewImageBooted && bits==SELF_TEST_PASSED);
    wait_for_ota(); assert(bits==SELF_TEST_PASSED); /* wait does not clear the gate */
    bits=0;
    assert(verifyVersion("102")==OtaPalNewImageSameVersionSelfTestOK && bits==SELF_TEST_PASSED);
    bits=0;
    assert(verifyVersion("103")==OtaPalNewImageBootFailed && bits==0);
    assert(test_calls==5);
    return 0;
}
'''
            product_api.ProductApiTests().compile_run(source, extra_includes=(KERNEL,))


if __name__ == "__main__":
    unittest.main()

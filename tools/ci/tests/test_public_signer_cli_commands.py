"""Exercise the product maintenance registry through the pristine CLI dispatcher.

Flash/cache, conf and forbidden handlers are host stubs; no MCU or UART is used.
"""
import importlib.util
from pathlib import Path
import re
import unittest

_spec = importlib.util.spec_from_file_location(
    "public_signer_host_compiler", Path(__file__).with_name("test_product_oss_api.py"))
_host = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_host)
ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "Middleware/FreeRTOS-Plus-CLI/FreeRTOS-Plus/Source/FreeRTOS-Plus-CLI"


def _product_source():
    return (ROOT / "Demos/cli/CLIcommands.c").read_text(encoding="utf-8")


def _function(source, pattern):
    match = re.search(pattern + r"\s*\{", source)
    if match is None:
        raise AssertionError("Product CLI function was not found")
    depth = 0
    for index in range(source.index("{", match.start()), len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    raise AssertionError("Product CLI function is incomplete")


def _definition(source, name):
    match = re.search(r"static\s+CLI_Command_Definition_t\s+" + name + r"\s*=\s*\{[\s\S]*?^\};",
                      source, re.MULTILINE)
    if match is None:
        raise AssertionError("Product CLI command definition was not found: " + name)
    return match.group(0)


class PublicSignerCliCommandTests(unittest.TestCase):
    # Reuse the existing gcc/MSVC setup, diagnostics and execution checks only.
    # Inheriting ProductApiTests would repeat its unrelated test methods.
    compile_run = _host.ProductApiTests.compile_run

    def test_public_signer_registry_dispatches_format_and_conf_only(self):
        self.assertTrue(_host.GCC or _host.MSVC,
                        "Host C compiler required: dispatch contract must execute, not skip")
        self.assertTrue((CLI / "FreeRTOS_CLI.c").is_file(),
                        "Initialize the selected pristine FreeRTOS-Plus-CLI gitlink")
        source = _product_source()
        registration = _function(source, r"void\s+vRegisterPublicSignerCLICommands\s*\(\s*void\s*\)")
        handler = _function(source, r"static\s+BaseType_t\s+prvFormat\s*\([^{}]*\)")
        definitions = "\n".join(_definition(source, name) for name in
                                ("xCommandConfig", "xFormat", "xReset", "xWait"))
        fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "FreeRTOS.h"
#include "FreeRTOS_CLI.h"
#define LFS_ERR_OK 0
static int format_calls, cache_calls, conf_calls, forbidden_calls, format_result;
static int32_t littlFs_format(void) { format_calls++; return format_result; }
static void vprvCacheFormat(void) { cache_calls++; }
static BaseType_t prvConfigCommandHandler(char *out, size_t size, const char *input) {
    (void)input; conf_calls++; snprintf(out,size,"PUBLIC_CONF_STUB"); return pdFALSE;
}
static BaseType_t prvReset(char *out, size_t size, const char *input) {
    (void)out; (void)size; (void)input; forbidden_calls++; return pdFALSE;
}
static BaseType_t prvWaitMessage(char *out, size_t size, const char *input) {
    (void)out; (void)size; (void)input; forbidden_calls++; return pdFALSE;
}
''' + handler + "\n" + definitions + "\n" + registration + r'''
static void dispatch(const char *command, char *output, size_t size) {
    memset(output,0,size);
    assert(FreeRTOS_CLIProcessCommand(command,output,size)==pdFALSE);
}
int main(void) {
    char output[1024];
    vRegisterPublicSignerCLICommands();
    dispatch("format",output,sizeof(output));
    assert(strstr(output,"Format OK !")!=NULL);
    assert(format_calls==1 && cache_calls==1);
    format_result=-1;
    dispatch("format",output,sizeof(output));
    assert(strstr(output,"Format NG !")!=NULL);
    assert(format_calls==2 && cache_calls==1);
    dispatch("conf commit",output,sizeof(output));
    assert(strstr(output,"PUBLIC_CONF_STUB")!=NULL && conf_calls==1);
    dispatch("reset",output,sizeof(output));
    assert(strstr(output,"Command not recognised.")!=NULL);
    dispatch("CLI",output,sizeof(output));
    assert(strstr(output,"Command not recognised.")!=NULL);
    assert(forbidden_calls==0);
    return 0;
}
'''
        headers = {
            "FreeRTOS.h": """#ifndef PUBLIC_SIGNER_FIXTURE_FREERTOS_H
#define PUBLIC_SIGNER_FIXTURE_FREERTOS_H
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
typedef int BaseType_t;
typedef unsigned UBaseType_t;
#define pdFALSE 0
#define pdTRUE 1
#define pdFAIL 0
#define pdPASS 1
#define configASSERT assert
#define configCOMMAND_INT_MAX_OUTPUT_SIZE 1024
#define configSUPPORT_DYNAMIC_ALLOCATION 1
#define configSUPPORT_STATIC_ALLOCATION 0
#define pvPortMalloc malloc
#define vPortFree free
#define taskENTER_CRITICAL() ((void)0)
#define taskEXIT_CRITICAL() ((void)0)
#endif
""",
            "task.h": "#include \"FreeRTOS.h\"\n#define vTaskSuspendAll() ((void)0)\n#define xTaskResumeAll() pdTRUE\n",
        }
        self.compile_run(fixture, headers=headers,
                         extra_sources=(CLI / "FreeRTOS_CLI.c",), extra_includes=(CLI,))


if __name__ == "__main__":
    unittest.main()

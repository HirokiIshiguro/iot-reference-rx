"""Product protocol and queued-argument tests against pristine Agent2 headers."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
GCC = shutil.which("gcc")
MSVC = next(iter(sorted(Path("C:/Program Files/Microsoft Visual Studio").glob(
    "*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"), reverse=True)), None) if os.name == "nt" else None
AGENT = ROOT / "Middleware/FreeRTOS/coreMQTT-Agent/source/include"
MQTT = ROOT / "Middleware/FreeRTOS/coreMQTT/source"
RCELLULAR = ROOT / "Middleware/Renesas/r_cellular/r_cellular_vx.xx/r_cellular"


def r_cellular_headers():
    """Stub board/RTOS services while compiling the actual pinned public FIT API."""
    return {
        "r_bsp_config.h": "#ifndef FIXTURE_BSP_H\n#define FIXTURE_BSP_H\n#define BSP_CFG_RTOS_USED 1\ntypedef int sci_cb_evt_t;\ntypedef void *sci_hdl_t;\ntypedef void *irq_handle_t;\n#endif\n",
        "r_cellular_config.h": '#include "Projects/aws_bg96_ck_rx65n/e2studio_ccrx/src/smc_gen/r_config/r_cellular_config.h"\n',
        "platform.h": "#define BSP_MCU_RX65N 1\n",
        "semphr.h": "", "event_groups.h": "",
        "logging_levels.h": "#define LOG_INFO 3\n", "logging_stack.h": "#define LogInfo(x) ((void)0)\n#define LogError(x) ((void)0)\n",
        "user_tcp_hook_config.h": "#define USER_TCP_HOOK_ENABLED 0\n#define USER_RECONNECT_TRIES 1\n#define USER_CLOSE_SOCKET_TRIES 1\n#define USER_TCP_HOOK_FUNCTION SocketErrorHook\n",
    }


def r_cellular_includes():
    return [RCELLULAR, RCELLULAR / "src/include", ROOT / "Common/ports/r_cellular"]


@unittest.skipUnless(GCC or MSVC, "Host C compiler required; no MCU build is performed")
class ProductApiTests(unittest.TestCase):
    def compile_run(self, source, headers=None, extra_sources=(), extra_includes=(), extra_defines=()):
        with tempfile.TemporaryDirectory(prefix="product-api-") as temporary:
            directory = Path(temporary)
            for name, body in (headers or {}).items():
                header = directory / name
                header.parent.mkdir(parents=True, exist_ok=True)
                header.write_text(body, encoding="utf-8")
            main = directory / "main.c"
            main.write_text(source, encoding="utf-8")
            output = directory / ("test.exe" if os.name == "nt" else "test")
            environment = None
            if GCC:
                arguments = [GCC, "-std=c99", "-Wall", "-Wextra", "-Werror=implicit-function-declaration",
                             "-Werror=incompatible-pointer-types", "-DMQTT_DO_NOT_USE_CUSTOM_CONFIG",
                             "-DMQTT_AGENT_DO_NOT_USE_CUSTOM_CONFIG", "-I" + str(directory), "-I" + str(ROOT)]
                arguments += ["-I" + str(path) for path in extra_includes]
                arguments += ["-D" + value for value in extra_defines]
                arguments += [str(main), *map(str, extra_sources), "-o", str(output)]
            else:
                setup = MSVC.parents[6] / "Auxiliary/Build/vcvars64.bat"
                # Read only compiler path variables from the setup process.
                setup_script = directory / "compiler-env.cmd"
                setup_script.write_text('@echo off\ncall "' + str(setup) +
                    '" >nul\nif errorlevel 1 exit /b 1\nset INCLUDE\nset LIB\nset LIBPATH\nset PATH\n',
                    encoding="utf-8")
                settings = subprocess.run(["cmd.exe", "/d", "/c", str(setup_script)],
                    capture_output=True, text=True, check=True, timeout=20).stdout
                environment = dict(os.environ)
                environment["VSLANG"] = "1033"
                for line in settings.splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        if key.upper() in ("INCLUDE", "LIB", "LIBPATH", "PATH"):
                            environment[key] = value
                arguments = [str(MSVC), "/nologo", "/TC", "/std:c11", "/utf-8", "/MT", "/we4047", "/we4024", "/we4133",
                             "/DMQTT_DO_NOT_USE_CUSTOM_CONFIG", "/DMQTT_AGENT_DO_NOT_USE_CUSTOM_CONFIG",
                             "/I" + str(directory), "/I" + str(ROOT)]
                arguments += ["/I" + str(path) for path in extra_includes]
                arguments += ["/D" + value for value in extra_defines]
                arguments += [str(main), *map(str, extra_sources), "/Fe:" + str(output), "/Fo:" + str(directory) + os.sep]
            result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    cwd=directory, env=environment, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            executed = subprocess.run([str(output)], capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=10)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)

    def test_conf_value_and_uart_output_boundaries(self):
        self.compile_run(r'''
#include <assert.h>
#include "Demos/cli/config_command_value.h"
int main(void) {
    const char command[]="conf set codesignpubkey -----BEGIN PUBLIC KEY-----\\nPUBLIC\\n-----END PUBLIC KEY-----";
    const char * value; size_t length=99;
    value=Cli_ConfigValueTail(command,&length);
    assert(value && strcmp(value,"-----BEGIN PUBLIC KEY-----\\nPUBLIC\\n-----END PUBLIC KEY-----")==0);
    assert(length==strlen(value));
    assert(!Cli_ConfigValueTail("conf set key ",&length) && length==0);
    assert(!Cli_ConfigValueTail("conf set",&length));
    value=Cli_ConfigValueTail(" conf  set  endpoint  example.test ",&length);
    assert(value && strcmp(value,"example.test ")==0);
    struct { char output[8]; char guard; } data={{'x','x','x','x','x','x','x','x'},'G'};
    assert(Cli_TerminateOutput(data.output,sizeof(data.output))==7);
    assert(data.output[7]==0 && data.guard=='G');
    assert(Cli_TerminateOutput(NULL,0)==0);
    assert(Cli_PublicSignerCommandAllowed("conf set codesignpubkey -----BEGIN PUBLIC KEY-----\\nPUBLIC"));
    assert(Cli_PublicSignerCommandAllowed("conf get codesigncert"));
    assert(Cli_PublicSignerCommandAllowed(" conf commit "));
    assert(!Cli_PublicSignerCommandAllowed("conf get key"));
    assert(!Cli_PublicSignerCommandAllowed("conf set claimkey PRIVATE"));
    assert(!Cli_PublicSignerCommandAllowed("conf commit unexpected"));
    assert(!Cli_PublicSignerCommandAllowed("conf get codesigncert extra"));
    assert(!Cli_PublicSignerCommandAllowed("conf set codesignpubkey "));
    return 0;
}
''')

    def test_signer_startup_opens_only_cli_after_valid_storage(self):
        self.compile_run(r'''
#include <assert.h>
#include <setjmp.h>
#include <string.h>
#define PUBLIC_SIGNER_PROVISIONER_ENABLE 1
#define PUBLIC_SIGNER_SOURCE_SHA aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
#include "Demos/cli/public_signer_provisioner.h"
static jmp_buf stopped;
static unsigned stage, console, registered, message, pins;
static int storage_result, cache_result;
void UserInitialization(void) { assert(stage++==0); }
void CLI_Support_Settings(void) { assert(stage++==1); }
static void route(void) { assert(stage++==2); pins++; }
int32_t littlFs_init(void) { assert(stage++==3); return storage_result; }
int32_t vprvCacheInit(void) { assert(stage++==4); return cache_result; }
void vRegisterPublicSignerCLICommands(void) { assert(stage++==5); registered++; }
void vUARTCommandConsoleStart(uint16_t depth,UBaseType_t priority) {
    assert(stage++==6 && depth==2048 && priority==1); console++;
}
void vSerialPutString(const signed char * text,unsigned short length) {
    assert(length>0);
    if (strstr((const char *)text,"source_sha=")) {
        assert(stage==3 && strstr((const char *)text,"source_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\r\n"));return;
    }
    assert(strstr((const char *)text,"ERROR"));message++;
}
void vTaskSuspend(void * task) { assert(task==NULL); longjmp(stopped,1); }
static void run(void) { if (setjmp(stopped)==0) vRunPublicSignerProvisioner(route); }
int main(void) {
    run(); assert(stage==7 && pins==1 && console==1 && registered==1 && message==0);
    stage=0;storage_result=-1;run();assert(stage==4 && console==1 && registered==1 && message==1);
    stage=0;storage_result=0;cache_result=-1;run();assert(stage==5 && console==1 && registered==1 && message==2);
    return 0;
}
''', {
            "FreeRTOS.h": "#include <stddef.h>\ntypedef unsigned UBaseType_t;\n#define tskIDLE_PRIORITY 0\n",
            "task.h": "void vTaskSuspend(void * task);\n",
            "lfs_common_data.h": "#include <stdint.h>\nint32_t littlFs_init(void);\n",
            "store.h": "#include <stdint.h>\nint32_t vprvCacheInit(void);\n",
            "serial.h": "void vSerialPutString(const signed char *, unsigned short);\n",
        })

    def test_common_tls_bio_maps_retry_and_remote_eof_for_all_socket_ports(self):
        self.compile_run(r'''
#include <assert.h>
#include "FreeRTOS.h"
#include "tcp_sockets_wrapper.h"
#include "mbedtls_bio_tcp_sockets_wrapper.h"
#include "mbedtls/ssl.h"
static int result;
int32_t TCP_Sockets_Send(Socket_t s,const void * data,size_t size) {(void)s;(void)data;(void)size;return result;}
int32_t TCP_Sockets_Recv(Socket_t s,void * data,size_t size) {(void)s;(void)data;(void)size;return result;}
int main(void) {
    unsigned char byte=0;void * socket=(void *)1;
    result=0;
    assert(xMbedTLSBioTCPSocketsWrapperSend(socket,&byte,1)==MBEDTLS_ERR_SSL_WANT_WRITE);
    assert(xMbedTLSBioTCPSocketsWrapperRecv(socket,&byte,1)==MBEDTLS_ERR_SSL_WANT_READ);
    result=TCP_SOCKETS_ERRNO_ECLOSED;
    assert(xMbedTLSBioTCPSocketsWrapperSend(socket,&byte,1)==MBEDTLS_ERR_SSL_CONN_EOF);
    assert(xMbedTLSBioTCPSocketsWrapperRecv(socket,&byte,1)==MBEDTLS_ERR_SSL_CONN_EOF);
    result=1;
    assert(xMbedTLSBioTCPSocketsWrapperSend(socket,&byte,1)==1);
    assert(xMbedTLSBioTCPSocketsWrapperRecv(socket,&byte,1)==1);
    return 0;
}
''', {
            "FreeRTOS.h": '#include <stddef.h>\n#include <assert.h>\ntypedef int BaseType_t;\n#define configASSERT(x) assert(x)\n',
            "threading_alt.h": '', "mbedtls/mbedtls_config.h": '', "mbedtls/entropy.h": '',
            "mbedtls/ssl.h": '#define MBEDTLS_ERR_SSL_WANT_WRITE -0x6880\n#define MBEDTLS_ERR_SSL_WANT_READ -0x6900\n#define MBEDTLS_ERR_SSL_CONN_EOF -0x7280\n#define MBEDTLS_ERR_SSL_INTERNAL_ERROR -0x6C00\n#define MBEDTLS_ERR_SSL_TIMEOUT -0x6800\n',
            "logging_levels.h": '#define LOG_INFO 3\n', "logging_stack.h": '',
        }, [ROOT / "Middleware/3rdparty/mbedtls_utils/mbedtls_bio_tcp_sockets_wrapper.c"],
           [ROOT / "Middleware/network_transport/sockets_wrapper/include", ROOT / "Middleware/3rdparty/mbedtls_utils"])

    def test_r_cellular_socket_api_timeouts_and_failure_cleanup(self):
        headers = r_cellular_headers()
        headers.update({
            "FreeRTOS.h": r'''
#ifndef FIXTURE_KERNEL_H
#define FIXTURE_KERNEL_H
#include <stddef.h>
#include <stdint.h>
#include <assert.h>
typedef int BaseType_t;
#define configASSERT(x) assert(x)
void *pvPortMalloc(size_t);void vPortFree(void *);
#endif
''',
            "task.h": "", "list.h": "", "core_pkcs11.h": "", "iot_crypto.h": "",
            "logging_stack.h": "#define LogInfo(x) ((void)0)\n#define LogError(x) ((void)0)\n#define LogDebug(x) ((void)0)\n",
        })
        self.compile_run(r'''
#ifdef NDEBUG
#error Assertions must remain enabled
#endif
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "r_cellular_if.h"
#include "tcp_sockets_wrapper.h"
st_cellular_ctrl_t cellular_ctrl;
static unsigned created,closed,allocated,freed;
static int failAllocation,failDns,failConnect,receiveResult=4,sendResult=4;
void *pvPortMalloc(size_t size) { if(failAllocation)return NULL;allocated++;return malloc(size); }
void vPortFree(void *value) { assert(value);freed++;free(value); }
void CloseSocket(uint32_t no) { assert(no==1);closed++; }
e_cellular_err_t SocketErrorHook(e_cellular_err_t error,bool reset) { (void)reset;return error; }
int32_t R_CELLULAR_CreateSocket(st_cellular_ctrl_t *const ctrl,const uint8_t protocol,const uint8_t ip) {
 assert(ctrl==&cellular_ctrl && protocol==CELLULAR_PROTOCOL_TCP && ip==CELLULAR_PROTOCOL_IPV4);created++;return 1;
}
e_cellular_err_t R_CELLULAR_DnsQuery(st_cellular_ctrl_t *const ctrl,const uint8_t *const host,const uint8_t ip,st_cellular_ipaddr_t *const address) {
 assert(ctrl==&cellular_ctrl && !strcmp((const char*)host,"example.test") && ip==CELLULAR_PROTOCOL_IPV4);
 strcpy((char*)address->ipv4,"192.0.2.1");return failDns?CELLULAR_ERR_MODULE_COM:CELLULAR_SUCCESS;
}
e_cellular_err_t R_CELLULAR_ConnectSocket(st_cellular_ctrl_t *const ctrl,const uint8_t no,const uint8_t *const address,const uint16_t port) {
 assert(ctrl==&cellular_ctrl && no==1 && !strcmp((const char*)address,"192.0.2.1") && port==8883);
 return failConnect?CELLULAR_ERR_MODULE_COM:CELLULAR_SUCCESS;
}
int32_t R_CELLULAR_SendSocket(st_cellular_ctrl_t *const ctrl,const uint8_t no,const uint8_t *const data,const int32_t size,const uint32_t timeout) {
 assert(ctrl==&cellular_ctrl && no==1 && size==4 && !memcmp(data,"DATA",4) && timeout==23);return sendResult;
}
int32_t R_CELLULAR_ReceiveSocket(st_cellular_ctrl_t *const ctrl,const uint8_t no,uint8_t *const data,const int32_t size,const uint32_t timeout) {
 assert(ctrl==&cellular_ctrl && no==1 && size==8 && timeout==17);memcpy(data,"DATA",4);return receiveResult;
}
int main(void) {
 Socket_t socket=NULL;char bytes[8];unsigned before;
 assert(TCP_Sockets_Connect(&socket,"example.test",8883,17,23)==0 && socket);
 assert(TCP_Sockets_Recv(socket,bytes,sizeof(bytes))==4 && !memcmp(bytes,"DATA",4));
 assert(TCP_Sockets_Send(socket,"DATA",4)==4);
 receiveResult=CELLULAR_ERR_OTHER_API_RUNNING;assert(TCP_Sockets_Recv(socket,bytes,sizeof(bytes))==0);
 sendResult=CELLULAR_ERR_NOT_CONNECT;assert(TCP_Sockets_Send(socket,"DATA",4)==0);
 /* Driver error values must not escape into the common socket error space. */
 sendResult=CELLULAR_ERR_SOCKET_NOT_READY;
 assert(TCP_Sockets_Send(socket,"DATA",4)==TCP_SOCKETS_ERRNO_ENOTCONN && closed==1);
 receiveResult=CELLULAR_ERR_SOCKET_NOT_READY;
 assert(TCP_Sockets_Recv(socket,bytes,sizeof(bytes))==TCP_SOCKETS_ERRNO_ENOTCONN && closed==2);
 TCP_Sockets_Disconnect(socket);assert(closed==3 && allocated==freed);
 failDns=1;before=closed;assert(TCP_Sockets_Connect(&socket,"example.test",8883,17,23)!=0 && !socket);
 assert(closed==before+1 && allocated==freed);failDns=0;
 failConnect=1;before=closed;assert(TCP_Sockets_Connect(&socket,"example.test",8883,17,23)!=0 && !socket);
 assert(closed==before+1 && allocated==freed);failConnect=0;
 failAllocation=1;before=closed;assert(TCP_Sockets_Connect(&socket,"example.test",8883,17,23)!=0 && !socket);
 assert(closed==before+1 && allocated==freed && created==4);
 return 0;
}
''', headers, [ROOT / "Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/sockets_wrapper.c"],
             r_cellular_includes() + [ROOT / "Middleware/network_transport/sockets_wrapper/include"])

    def test_r_cellular_logging_macros_keep_normal_logs_and_disable_maintenance_side_effects(self):
        source = r'''
#include <assert.h>
#include "logging_levels.h"
static unsigned calls;
static void RecordLog(const char *format,int value) { (void)format;(void)value;calls++; }
#include "cellular_freertos.h"
#if !defined(CELLULAR_LOG_ERROR) || !defined(CELLULAR_LOG_WARN) || !defined(CELLULAR_LOG_INFO) || !defined(CELLULAR_LOG_DEBUG)
#error CELLULAR_LOG_macros_must_be_defined
#endif
int main(void) {
 unsigned effects=0;
 CELLULAR_LOG_ERROR(("fixture %d",++effects));CELLULAR_LOG_WARN(("fixture %d",++effects));
 CELLULAR_LOG_INFO(("fixture %d",++effects));CELLULAR_LOG_DEBUG(("fixture %d",++effects));
#if PUBLIC_SIGNER_PROVISIONER_ENABLE == 1
 assert(CELLULAR_CFG_DEBUGLOG==0 && calls==0 && effects==0);
#else
 assert(CELLULAR_CFG_DEBUGLOG==4 && calls==4 && effects==4);
#endif
 return 0;
}
'''
        for project in ("aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip"):
            config = Path("Projects") / project / "e2studio_ccrx/src/smc_gen/r_config/r_cellular_config.h"
            headers = r_cellular_headers()
            headers.update({
                "r_cellular_config.h": '#include "' + config.as_posix() + '"\n',
                "FreeRTOS.h": "#include <stddef.h>\n#include <stdint.h>\n",
                "task.h": "",
                "logging_levels.h": "#define LOG_NONE 0\n#define LOG_INFO 3\n",
                "logging_stack.h": "#define LogError(x) RecordLog x\n#define LogWarn(x) RecordLog x\n#define LogInfo(x) RecordLog x\n#define LogDebug(x) RecordLog x\n",
            })
            includes = r_cellular_includes() + [RCELLULAR / "src/RTOS/include"]
            with self.subTest(project=project, role="normal"):
                self.compile_run(source, headers, extra_includes=includes)
            maintenance_defines = ["PUBLIC_SIGNER_PROVISIONER_ENABLE=1", "LIBRARY_LOG_LEVEL=LOG_NONE"]
            with self.subTest(project=project, role="maintenance"):
                self.compile_run(source, headers, extra_includes=includes, extra_defines=maintenance_defines)
            # The former unconditionally enabled setting must fail the same macro contract.
            old_headers = dict(headers)
            old_headers["r_cellular_config.h"], replacements = re.subn(
                r"#if PUBLIC_SIGNER_PROVISIONER_ENABLE == 1\n.*?\n#endif",
                "#define CELLULAR_CFG_DEBUGLOG (4)",
                (ROOT / config).read_text(encoding="utf-8"), count=1, flags=re.S)
            self.assertEqual(replacements, 1)
            with self.subTest(project=project, role="old-maintenance-negative-control"):
                with self.assertRaisesRegex(AssertionError, "CELLULAR_LOG_macros_must_be_defined"):
                    self.compile_run(source, old_headers, extra_includes=includes, extra_defines=maintenance_defines)

    def test_product_jobs_topic_bounds_and_nonterminated_id(self):
        self.compile_run(r'''
#include <assert.h>
#include "Demos/OtaOverMqtt/ota_jobs_topic.h"
int main(void) {
    char output[110], id[64]; size_t length;
    assert(otaJobs_BuildCancellationTopic(output,sizeof(output),"job-1_A",7,&length));
    assert(strcmp(output,"$aws/events/job/job-1_A/cancellation_in_progress")==0);
    assert(length==strlen(output));
    memset(id,'A',sizeof(id));
    assert(otaJobs_BuildCancellationTopic(output,sizeof(output),id,sizeof(id),&length));
    assert(!otaJobs_BuildCancellationTopic(output,length,id,sizeof(id),&length));
    assert(length==0 && output[0]==0);
    assert(!otaJobs_BuildCancellationTopic(output,sizeof(output),"a/b",3,&length));
    assert(!otaJobs_BuildCancellationTopic(output,sizeof(output),"",0,&length));
    return 0;
}
''')

    @unittest.skipUnless((AGENT / "core_mqtt_agent.h").is_file(), "Pristine Agent2 submodule required")
    def test_queued_publish_args_survive_wait_and_unsubscribe_callback(self):
        headers = {
            "FreeRTOS.h": r'''
#ifndef FIXTURE_FREERTOS_H
#define FIXTURE_FREERTOS_H
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef int BaseType_t; typedef unsigned UBaseType_t; typedef unsigned TickType_t;
#define pdTRUE 1
#define pdFALSE 0
#define portMAX_DELAY UINT32_MAX
#define configASSERT(x) assert(x)
#define configPRINTF(x) ((void)0)
#define configTASK_NOTIFICATION_ARRAY_ENTRIES 4
#endif
''',
            "task.h": r'''
#ifndef FIXTURE_TASK_H
#define FIXTURE_TASK_H
#include "FreeRTOS.h"
typedef void * TaskHandle_t;
typedef enum {eSetValueWithOverwrite} eNotifyAction;
TaskHandle_t xTaskGetCurrentTaskHandle(void);
BaseType_t xTaskNotifyIndexed(TaskHandle_t,UBaseType_t,uint32_t,eNotifyAction);
BaseType_t xTaskNotifyWaitIndexed(UBaseType_t,uint32_t,uint32_t,uint32_t*,TickType_t);
BaseType_t xTaskNotifyStateClearIndexed(TaskHandle_t,UBaseType_t);
#endif
''',
            "mqtt_agent_task.h": r'''
#include "core_mqtt_agent.h"
typedef void (*IncomingPubCallback_t)(void *, MQTTPublishInfo_t *);
void vRemoveMQTTTopicFilterCallback(const char *,uint16_t);
MQTTStatus_t MqttAgent_SubscribeSync(const char *,uint16_t,MQTTQoS_t,IncomingPubCallback_t,void *);
''',
            "ota_demo.h": r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
bool otaDemo_handleIncomingMQTTMessage(char *,size_t,uint8_t *,size_t);
''',
        }
        self.compile_run(r'''
#include <assert.h>
#include <string.h>
#include "Demos/common/mqtt-wrapper/mqtt_wrapper.h"
MQTTAgentContext_t xGlobalMqttAgentContext;
static const MQTTAgentCommandInfo_t * pending;
static MQTTAgentPublishArgs_t * publish;
static MQTTAgentSubscribeArgs_t * subscribe;
static unsigned waits;
static int operation,removed,notified;
static MQTTStatus_t completion=MQTTSuccess;
TaskHandle_t xTaskGetCurrentTaskHandle(void) { return (TaskHandle_t)1; }
BaseType_t xTaskNotifyStateClearIndexed(TaskHandle_t t,UBaseType_t i) { (void)t;assert(i==2);notified=0;return pdTRUE; }
BaseType_t xTaskNotifyIndexed(TaskHandle_t t,UBaseType_t i,uint32_t value,eNotifyAction action) {
    (void)t;(void)action;assert(i==2);
    if(operation==2 && completion==MQTTSuccess) assert(removed);
    notified=1; assert(value==(uint32_t)completion); return pdTRUE;
}
BaseType_t xTaskNotifyWaitIndexed(UBaseType_t i,uint32_t entry,uint32_t exit,uint32_t * value,TickType_t timeout) {
    (void)entry;(void)exit; assert(i==2 && timeout==portMAX_DELAY); waits++;
    if(waits==1) return pdFALSE;
    assert(pending);
    if(operation==1) {
        assert(publish->pProperties==NULL);
        assert(publish->pPublishInfo->payloadLength==4);
        assert(memcmp(publish->pPublishInfo->pPayload,"DATA",4)==0);
    } else { assert(subscribe->pProperties==NULL); }
    MQTTAgentReturnInfo_t result={0};result.returnCode=completion;
    pending->cmdCompleteCallback(pending->pCmdCompleteCallbackContext,&result);
    assert(notified); *value=(uint32_t)completion; pending=NULL; return pdTRUE;
}
MQTTStatus_t MQTTAgent_Publish(const MQTTAgentContext_t * ctx,MQTTAgentPublishArgs_t * args,const MQTTAgentCommandInfo_t * command) {
    (void)ctx;operation=1;publish=args;pending=command;return MQTTSuccess;
}
MQTTStatus_t MQTTAgent_Unsubscribe(const MQTTAgentContext_t * ctx,MQTTAgentSubscribeArgs_t * args,const MQTTAgentCommandInfo_t * command) {
    (void)ctx;operation=2;subscribe=args;pending=command;return MQTTSuccess;
}
void vRemoveMQTTTopicFilterCallback(const char * topic,uint16_t length) {
    assert(!notified && length==10 && memcmp(topic,"test/topic",10)==0);removed=1;
}
MQTTStatus_t MqttAgent_SubscribeSync(const char * t,uint16_t n,MQTTQoS_t q,IncomingPubCallback_t c,void * p) {
    (void)t;(void)n;(void)q;(void)c;(void)p;return MQTTSuccess;
}
bool otaDemo_handleIncomingMQTTMessage(char * t,size_t n,uint8_t * p,size_t s) { (void)t;(void)n;(void)p;(void)s;return false; }
int main(void) {
    MQTTContext_t context={0};context.connectStatus=MQTTConnected;mqttWrapper_setCoreMqttContext(&context);
    assert(mqttWrapper_publish("test/topic",10,(uint8_t *)"DATA",4));assert(waits==2);
    waits=0;assert(mqttWrapper_unsubscribe("test/topic",10));assert(waits==2 && removed);
    waits=0;removed=0;completion=MQTTBadResponse;
    assert(!mqttWrapper_unsubscribe("test/topic",10));assert(waits==2 && !removed);
    return 0;
}
''', headers, [ROOT / "Demos/common/mqtt-wrapper/mqtt_wrapper.c"],
             [AGENT, MQTT / "include", MQTT / "interface"])


if __name__ == "__main__":
    unittest.main()

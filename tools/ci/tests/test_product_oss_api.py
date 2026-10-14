"""Product protocol and queued-argument tests against pristine Agent2 headers."""
from pathlib import Path
import os
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


@unittest.skipUnless(GCC or MSVC, "Host C compiler required; no MCU build is performed")
class ProductApiTests(unittest.TestCase):
    def compile_run(self, source, headers=None, extra_sources=(), extra_includes=()):
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
                arguments += [str(main), *map(str, extra_sources), "/Fe:" + str(output), "/Fo:" + str(directory) + os.sep]
            result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    cwd=directory, env=environment, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            subprocess.run([str(output)], capture_output=True, check=True, timeout=10)

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

    def test_bg96_official_socket_urc_drain_and_remote_close(self):
        cellular = ROOT / "Middleware/FreeRTOS/FreeRTOS-Cellular-Interface/source"
        product = ROOT / "Common/ports/cellular_bg96"
        self.compile_run(r'''
#include <assert.h>
#include <string.h>
#include "task.h"
#include "event_groups.h"
#include "bg96_network.h"
#include "tcp_sockets_wrapper.h"
static unsigned tick,queries,opens,closes,waits;
static int failOpen;
static CellularSocketOpenCallback_t onOpen;
static CellularSocketDataReadyCallback_t onData;
static CellularSocketClosedCallback_t onClosed;
static void * openCtx,*dataCtx,*closedCtx;
static CellularSocketHandle_t opaque=(CellularSocketHandle_t)2;
TickType_t xTaskGetTickCount(void) { return tick; }
void vTaskDelay(TickType_t ticks) { tick+=ticks; }
EventGroupHandle_t xEventGroupCreateStatic(StaticEventGroup_t * storage) { storage->bits=0;return storage; }
EventBits_t xEventGroupSetBits(EventGroupHandle_t group,EventBits_t bits) { return group->bits|=bits; }
EventBits_t xEventGroupClearBits(EventGroupHandle_t group,EventBits_t bits) { unsigned before=group->bits;group->bits&=~bits;return before; }
EventBits_t xEventGroupGetBits(EventGroupHandle_t group) { return group->bits; }
EventBits_t xEventGroupWaitBits(EventGroupHandle_t group,EventBits_t bits,BaseType_t clear,BaseType_t all,TickType_t timeout) {
    (void)clear;(void)all;waits++;
    if (!(group->bits&bits)) tick+=timeout;
    return group->bits;
}
CellularHandle_t Bg96_GetHandle(void) { return (CellularHandle_t)1; }
CellularError_t Cellular_GetHostByName(CellularHandle_t h,uint8_t id,const char * host,char * address) {
    (void)h;assert(id==1 && strcmp(host,"example.test")==0);strcpy(address,"192.0.2.1");return CELLULAR_SUCCESS;
}
CellularError_t Cellular_CreateSocket(CellularHandle_t h,uint8_t id,CellularSocketDomain_t domain,CellularSocketType_t type,CellularSocketProtocol_t protocol,CellularSocketHandle_t * result) {
    (void)h;assert(id==1 && domain==CELLULAR_SOCKET_DOMAIN_AF_INET && type==CELLULAR_SOCKET_TYPE_STREAM && protocol==CELLULAR_SOCKET_PROTOCOL_TCP);*result=opaque;opens++;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketRegisterSocketOpenCallback(CellularHandle_t h,CellularSocketHandle_t s,CellularSocketOpenCallback_t cb,void * ctx) {
    (void)h;assert(s==opaque);onOpen=cb;openCtx=ctx;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketRegisterDataReadyCallback(CellularHandle_t h,CellularSocketHandle_t s,CellularSocketDataReadyCallback_t cb,void * ctx) {
    (void)h;assert(s==opaque);onData=cb;dataCtx=ctx;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketRegisterClosedCallback(CellularHandle_t h,CellularSocketHandle_t s,CellularSocketClosedCallback_t cb,void * ctx) {
    (void)h;assert(s==opaque);onClosed=cb;closedCtx=ctx;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketSetSockOpt(CellularHandle_t h,CellularSocketHandle_t s,CellularSocketOptionLevel_t level,CellularSocketOption_t option,const uint8_t * value,uint32_t length) {
    (void)h;(void)option;(void)value;assert(s==opaque && level==CELLULAR_SOCKET_OPTION_LEVEL_TRANSPORT && length==4);return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketConnect(CellularHandle_t h,CellularSocketHandle_t s,CellularSocketAccessMode_t mode,const CellularSocketAddress_t * address) {
    (void)h;assert(s==opaque && mode==CELLULAR_ACCESSMODE_BUFFER && address->port==8883 && address->ipAddress.ipAddressType==CELLULAR_IP_ADDRESS_V4);
    onOpen(failOpen?CELLULAR_URC_SOCKET_OPEN_FAILED:CELLULAR_URC_SOCKET_OPENED,s,openCtx);return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketClose(CellularHandle_t h,CellularSocketHandle_t s) {
    (void)h;assert(s==opaque && onOpen==NULL && onData==NULL && onClosed==NULL);closes++;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketRecv(CellularHandle_t h,CellularSocketHandle_t s,uint8_t * data,uint32_t size,uint32_t * received) {
    (void)h;assert(s==opaque && size==8);queries++;
    if(queries<=2) { memcpy(data,"DATA",4);*received=4; } else *received=0;
    return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SocketSend(CellularHandle_t h,CellularSocketHandle_t s,const uint8_t * data,uint32_t size,uint32_t * sent) {
    (void)h;assert(s==opaque && size==4 && memcmp(data,"DATA",4)==0);*sent=4;return CELLULAR_SUCCESS;
}
int main(void) {
    Socket_t socket=NULL;char data[8];
    assert(TCP_Sockets_Connect(&socket,"example.test",8883,10,10)==0 && socket);
    assert(TCP_Sockets_Recv(socket,data,sizeof(data))==0 && queries==0 && tick==10);
    onData(opaque,dataCtx);
    assert(TCP_Sockets_Recv(socket,data,sizeof(data))==4 && queries==1);
    assert(TCP_Sockets_Recv(socket,data,sizeof(data))==4 && queries==2);
    assert(TCP_Sockets_Recv(socket,data,sizeof(data))==0 && queries==3);
    assert(TCP_Sockets_Send(socket,"DATA",4)==4);
    onClosed(opaque,closedCtx);
    assert(TCP_Sockets_Recv(socket,data,sizeof(data))==TCP_SOCKETS_ERRNO_ECLOSED);
    assert(TCP_Sockets_Send(socket,"DATA",4)==TCP_SOCKETS_ERRNO_ECLOSED);
    TCP_Sockets_Disconnect(socket);assert(closes==1);
    failOpen=1;
    assert(TCP_Sockets_Connect(&socket,"example.test",8883,10,10)!=0 && socket==NULL && closes==2);
    assert(opens==2);
    return 0;
}
''', {
            "FreeRTOS.h": r'''
#ifndef FIXTURE_KERNEL_H
#define FIXTURE_KERNEL_H
#include <stddef.h>
#include <stdint.h>
typedef int BaseType_t;typedef unsigned TickType_t;
#define pdTRUE 1
#define pdFALSE 0
#define portMAX_DELAY UINT32_MAX
#define pdMS_TO_TICKS(x) (x)
#define taskENTER_CRITICAL() ((void)0)
#define taskEXIT_CRITICAL() ((void)0)
#endif
''',
            "task.h": '#include "FreeRTOS.h"\nTickType_t xTaskGetTickCount(void);void vTaskDelay(TickType_t);\n',
            "event_groups.h": r'''
#ifndef FIXTURE_EVENTS_H
#define FIXTURE_EVENTS_H
#include "FreeRTOS.h"
typedef unsigned EventBits_t;typedef struct {unsigned bits;} StaticEventGroup_t;
typedef StaticEventGroup_t * EventGroupHandle_t;
EventGroupHandle_t xEventGroupCreateStatic(StaticEventGroup_t *);
EventBits_t xEventGroupGetBits(EventGroupHandle_t);
EventBits_t xEventGroupSetBits(EventGroupHandle_t,EventBits_t);
EventBits_t xEventGroupClearBits(EventGroupHandle_t,EventBits_t);
EventBits_t xEventGroupWaitBits(EventGroupHandle_t,EventBits_t,BaseType_t,BaseType_t,TickType_t);
#endif
''',
            "logging_levels.h": '#define LOG_INFO 3\n', "logging_stack.h": '',
        }, [ROOT / "Middleware/network_transport/sockets_wrapper/ports/cellular_bg96/tcp_sockets_wrapper.c"],
           [product, cellular / "include", cellular / "interface", cellular / "include/common",
            ROOT / "Middleware/network_transport/sockets_wrapper/include"])

    def test_bg96_comm_enables_cts_only_after_ifc_ack_and_detects_overflow(self):
        cellular = ROOT / "Middleware/FreeRTOS/FreeRTOS-Cellular-Interface/source"
        product = ROOT / "Common/ports/cellular_bg96"
        self.compile_run(r'''
#include <assert.h>
#include <string.h>
#include "queue.h"
#include "r_sci_rx_if.h"
#include "bg96_network.h"
FixturePort PORT5,PORTB,PORTJ,PORT0;FixtureMpc MPC;
static unsigned tick,rate,cts,notifications,baudChanges;
static void (*interruptHandler)(void *);
struct Queue {uint8_t bytes[8192];unsigned used,read;};
static struct Queue queue;
TickType_t xTaskGetTickCount(void) { return tick; }
void vTaskDelay(TickType_t t) { tick+=t; }
QueueHandle_t xQueueCreate(unsigned length,unsigned item) { assert(length==8192 && item==1);memset(&queue,0,sizeof(queue));return &queue; }
void vQueueDelete(QueueHandle_t q) { assert(q==&queue); }
BaseType_t xQueueSendFromISR(QueueHandle_t q,const void * value,BaseType_t * wake) {
    (void)wake;assert(q==&queue);if(q->used==8192)return 0;q->bytes[(q->read+q->used)%8192]=*(const uint8_t *)value;q->used++;return 1;
}
BaseType_t xQueueReceive(QueueHandle_t q,void * value,TickType_t timeout) {
    assert(q==&queue);if(q->used==0){tick+=timeout;return 0;}*(uint8_t *)value=q->bytes[q->read++%8192];q->used--;return 1;
}
static void inject(const char * text) { while(*text){sci_cb_args_t args={SCI_EVT_RX_CHAR,(uint8_t)*text++};interruptHandler(&args);} }
void R_BSP_RegisterProtectDisable(int n) {(void)n;}
void R_BSP_RegisterProtectEnable(int n) {(void)n;}
void R_SCI_PinSet_SCI6(void) {PORTJ.PMR.BIT.B3=1;}
sci_err_t R_SCI_Open(int channel,int mode,sci_cfg_t * config,void (*cb)(void *),sci_hdl_t * result) {
    (void)mode;assert(channel==SCI_CH6 && config->async.int_priority==4 && PORTJ.PMR.BIT.B3==0);
    rate=config->async.baud_rate;interruptHandler=cb;*result=(void *)1;return SCI_SUCCESS;
}
sci_err_t R_SCI_Close(sci_hdl_t h) {assert(h==(void *)1);return SCI_SUCCESS;}
sci_err_t R_SCI_Send(sci_hdl_t h,uint8_t * data,uint16_t length) {
    assert(h==(void *)1);
    if(length==3 && memcmp(data,"AT\r",3)==0) {if(rate==460800)inject("\r\nOK\r\n");}
    else if(length==11 && memcmp(data,"AT+IFC=2,2\r",11)==0) {assert(cts==0);inject("\r\nOK\r\n");}
    return SCI_SUCCESS;
}
sci_err_t R_SCI_Control(sci_hdl_t h,int command,void * argument) {
    assert(h==(void *)1);
    if(command==SCI_CMD_EN_CTS_IN){assert(PORTJ.PMR.BIT.B3==0);cts++;}
    else {sci_baud_t * baud=argument;assert(command==SCI_CMD_CHANGE_BAUD && baud->rate==460800 && baud->pclk==64000000);baudChanges++;}
    return SCI_SUCCESS;
}
static CellularCommInterfaceError_t receive(void * user,CellularCommInterfaceHandle_t handle) {
    assert(user==(void *)3 && handle);notifications++;return IOT_COMM_INTERFACE_BUSY;
}
int main(void) {
    CellularCommInterfaceHandle_t handle;uint8_t bytes[64];uint32_t used;
    PORTB.PIDR.BIT.B6=1;
    assert(Bg96_CommInterface.open(receive,(void *)3,&handle)==IOT_COMM_INTERFACE_SUCCESS);
    assert(rate==460800 && cts==0 && !Bg96_CommSetRuntimeBaud());
    assert(Bg96_CommInterface.send(handle,(uint8_t *)"AT+IFC=2,2\r",11,100,&used)==IOT_COMM_INTERFACE_SUCCESS && used==11);
    assert(cts==0);
    assert(Bg96_CommInterface.recv(handle,bytes,sizeof(bytes),100,&used)==IOT_COMM_INTERFACE_SUCCESS && used==6);
    assert(cts==1 && PORTJ.PMR.BIT.B3==1 && Bg96_CommSetRuntimeBaud() && baudChanges==1);
    assert(notifications==6);
    assert(Bg96_CommInterface.recv(handle,bytes,sizeof(bytes),10,&used)==IOT_COMM_INTERFACE_TIMEOUT && used==0);
    for(unsigned i=0;i<8193;i++)inject("A");
    assert(Bg96_CommInterface.recv(handle,bytes,sizeof(bytes),10,&used)==IOT_COMM_INTERFACE_DRIVER_ERROR);
    assert(Bg96_CommInterface.close(handle)==IOT_COMM_INTERFACE_SUCCESS && PORTJ.PMR.BIT.B3==0);
    return 0;
}
''', {
            "FreeRTOS.h": r'''
#ifndef FIXTURE_KERNEL_H
#define FIXTURE_KERNEL_H
#include <stddef.h>
#include <stdint.h>
typedef int BaseType_t;typedef unsigned TickType_t;
#define pdTRUE 1
#define pdFALSE 0
#define pdPASS 1
#define configMAX_SYSCALL_INTERRUPT_PRIORITY 4
#define pdMS_TO_TICKS(x) (x)
#define portYIELD_FROM_ISR(x) ((void)(x))
#endif
''',
            "task.h": '#include "FreeRTOS.h"\nTickType_t xTaskGetTickCount(void);void vTaskDelay(TickType_t);\n',
            "queue.h": r'''
#ifndef FIXTURE_QUEUE_H
#define FIXTURE_QUEUE_H
#include "FreeRTOS.h"
typedef struct Queue * QueueHandle_t;
QueueHandle_t xQueueCreate(unsigned,unsigned);void vQueueDelete(QueueHandle_t);
BaseType_t xQueueSendFromISR(QueueHandle_t,const void *,BaseType_t *);
BaseType_t xQueueReceive(QueueHandle_t,void *,TickType_t);
#endif
''',
            "platform.h": r'''
#ifndef FIXTURE_PLATFORM_H
#define FIXTURE_PLATFORM_H
typedef struct {unsigned B2,B3,B5,B6,B7;} FixtureBits;
typedef struct {FixtureBits BIT;} FixtureRegister;
typedef struct {FixtureRegister PMR,PDR,PODR,PIDR;} FixturePort;
typedef struct {unsigned BYTE;} FixturePfs;
typedef struct {FixturePfs P55PFS,PB7PFS,PB6PFS,P02PFS;} FixtureMpc;
extern FixturePort PORT5,PORTB,PORTJ,PORT0;extern FixtureMpc MPC;
#define BSP_REG_PROTECT_MPC 1
#define BSP_PCLKB_HZ 64000000
void R_BSP_RegisterProtectDisable(int);void R_BSP_RegisterProtectEnable(int);
#endif
''',
            "r_sci_rx_if.h": r'''
#ifndef FIXTURE_SCI_H
#define FIXTURE_SCI_H
#include <stdint.h>
#include "platform.h"
typedef void * sci_hdl_t;typedef int sci_err_t;
typedef struct {unsigned event;uint8_t byte;} sci_cb_args_t;
typedef struct {struct {uint32_t baud_rate;unsigned clk_src,data_size,parity_en,parity_type,stop_bits,int_priority;} async;} sci_cfg_t;
typedef struct {uint32_t pclk,rate;} sci_baud_t;
enum {SCI_EVT_RX_CHAR=1,SCI_EVT_RXBUF_OVFL,SCI_CH6,SCI_MODE_ASYNC,SCI_CLK_INT,SCI_DATA_8BIT,SCI_PARITY_OFF,SCI_EVEN_PARITY,SCI_STOPBITS_1,SCI_ERR_INSUFFICIENT_SPACE,SCI_ERR_XCVR_BUSY,SCI_CMD_EN_CTS_IN,SCI_CMD_CHANGE_BAUD};
#define SCI_SUCCESS 0
sci_err_t R_SCI_Open(int,int,sci_cfg_t *,void (*)(void *),sci_hdl_t *);
sci_err_t R_SCI_Close(sci_hdl_t);sci_err_t R_SCI_Send(sci_hdl_t,uint8_t *,uint16_t);sci_err_t R_SCI_Control(sci_hdl_t,int,void *);
#endif
''',
            "r_sci_rx_pinset.h": 'void R_SCI_PinSet_SCI6(void);\n',
        }, [product / "bg96_comm.c"],
           [product, cellular / "include", cellular / "interface", cellular / "include/common"])

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

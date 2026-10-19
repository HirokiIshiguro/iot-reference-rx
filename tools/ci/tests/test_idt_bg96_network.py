"""Native APN binding through product ports and the pinned r_cellular public API."""
from pathlib import Path
import unittest

from tools.ci.tests import test_product_oss_api as host
from tools.ci.tests.test_public_signer_cli_commands import _function

ROOT = Path(__file__).resolve().parents[3]
CELLULAR = host.RCELLULAR
PRODUCT = ROOT / "Common/ports/r_cellular"


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required; no MCU build")
class Bg96NativeNetworkTests(unittest.TestCase):
    def test_actual_store_maps_preserve_bg96_keys_only_when_selected(self):
        lookup = _function((ROOT / "Demos/cli/store.c").read_text(encoding="utf-8"),
                           r"int32_t\s+Filename2Handle\s*\([^{};]*\)")
        for enabled in (0, 1):
            source = r'''
#ifdef NDEBUG
#error Assertions must remain enabled
#endif
#include <assert.h>
#include "store.h"
''' + lookup + r'''
int main(void) {
 const char *files[]=KVSTORE_KEYS;
 const char *commands[]={"apn","apnuser","apnpass","apnauth"};
 const char *oldFiles[]={"cellular_ap_name","cellular_ap_userid","cellular_ap_password","cellular_ap_auth_type"};
 unsigned i;
 for(i=0;i<4;i++) {
   int32_t key=Filename2Handle((char *)commands[i],strlen(commands[i]));
#if CELLULAR_APN_KVS_ENABLE
   assert(key>=0 && strcmp(files[key],oldFiles[i])==0);
#else
   assert(key==KVS_INVALID_KEY);
#endif
 }
 assert(Filename2Handle("apnuser-extra",13)==KVS_INVALID_KEY);
 assert(Filename2Handle("apn",2)==KVS_INVALID_KEY);
 return 0;
}
'''
            host.ProductApiTests.compile_run(self, source, self.store_headers(),
                                             extra_defines=["CELLULAR_APN_KVS_ENABLE=" + str(enabled)])

    @staticmethod
    def store_headers():
        labels = ("DEVICE_CERTIFICATE_FOR_TLS", "DEVICE_PRIVATE_KEY_FOR_TLS", "DEVICE_PUBLIC_KEY_FOR_TLS",
                  "CLAIM_CERTIFICATE", "CLAIM_PRIVATE_KEY")
        return {**host.r_cellular_headers(), "FreeRTOS.h": '#include <stddef.h>\n#include <stdint.h>\ntypedef int BaseType_t;\n#define pdTRUE 1\n#define pdFALSE 0\n',
                "lfs_common_data.h": "", "lfs.h": "typedef int lfs_ssize_t;\n",
                "store.h": "".join('#define pkcs11configLABEL_' + label + ' "' + label + '"\n' for label in labels) +
                           '#include "Demos/cli/store.h"\n'}

    def test_normal_persistent_ap_and_native_override_use_actual_key_lookup(self):
        store_source = (ROOT / "Demos/cli/store.c").read_text(encoding="utf-8")
        lookup = _function(store_source, r"int32_t\s+Filename2Handle\s*\([^{};]*\)")
        validation = _function(store_source, r"static\s+BaseType_t\s+prvCellularValueValid\s*\([^{};]*\)")
        source = r'''
#ifdef NDEBUG
#error Assertions must remain enabled
#endif
#include <assert.h>
#include <string.h>
#include "task.h"
#include "r_cellular_network.h"
#include "store.h"
#include "rx_idt_network.h"
static char values[KVS_NUM_KEYS][128];static size_t lengths[KVS_NUM_KEYS];
static unsigned tick,inits;static int shortRead;
static st_cellular_ap_cfg_t received;
''' + lookup + validation + r'''
size_t prvGetCacheEntryLength(KVStoreKey_t key) { return lengths[key]; }
size_t xReadEntry(KVStoreKey_t key,void *out,size_t size) {
 assert(size==lengths[key]);memcpy(out,values[key],size);return shortRead?size-1:size;
}
int32_t xprvWriteCacheEntry(size_t kl,char *name,size_t size,char *value) {
 int32_t key=Filename2Handle(name,kl);
 if(key<0 || !prvCellularValueValid((KVStoreKey_t)key,value,size))return KVS_INVALID_KEY;
 assert(size<=128);memcpy(values[key],value,size);lengths[key]=size;return key;
}
BaseType_t KVStore_xCommitChanges(void) { return pdTRUE; }
TickType_t xTaskGetTickCount(void) { return tick; }
void vTaskDelay(TickType_t ticks) { tick+=ticks; }
e_cellular_err_t R_CELLULAR_Open(st_cellular_ctrl_t *const ctrl,const st_cellular_cfg_t *const config) { (void)config;assert(ctrl==&cellular_ctrl);inits++;ctrl->system_state=CELLULAR_SYSTEM_OPEN;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_Close(st_cellular_ctrl_t *const ctrl) { assert(ctrl==&cellular_ctrl);ctrl->system_state=CELLULAR_SYSTEM_CLOSE;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_SetOperator(st_cellular_ctrl_t *const ctrl,const uint8_t *const op) { (void)ctrl;(void)op;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_SetBand(st_cellular_ctrl_t *const ctrl,const uint8_t *const band) { (void)ctrl;(void)band;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_HardwareReset(st_cellular_ctrl_t *const ctrl) { (void)ctrl;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_CloseSocket(st_cellular_ctrl_t *const ctrl,const uint8_t no) { (void)ctrl;(void)no;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_APConnect(st_cellular_ctrl_t *const ctrl,const st_cellular_ap_cfg_t *const config) {
 assert(ctrl==&cellular_ctrl);
 if(config)received=*config;else { memset(&received,0,sizeof(received));strcpy((char*)received.ap_name,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_NAME));received.auth_type=CELLULAR_CFG_AUTH_TYPE; }
 ctrl->system_state=CELLULAR_SYSTEM_CONNECT;return CELLULAR_SUCCESS;
}
static void save(KVStoreKey_t key,const char *value,size_t size) { assert(size<128);memcpy(values[key],value,size);lengths[key]=size; }
int main(void) {
 unsigned before;char longValue[128];
 assert(Connect2AP() && strcmp((char*)received.ap_name,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_NAME))==0);RCellular_NetworkCleanup();
 save(KVS_CELLULAR_AP_NAME,"stored.invalid",14);save(KVS_CELLULAR_AP_USERID,"user",4);
 save(KVS_CELLULAR_AP_PASSWORD,"password",8);save(KVS_CELLULAR_AP_AUTH_TYPE,"1",1);
 assert(Connect2AP() && strcmp((char*)received.ap_name,"stored.invalid")==0);
 assert(strcmp((char*)received.ap_user_name,"user")==0 && strcmp((char*)received.ap_pass,"password")==0 && received.auth_type==CELLULAR_AUTH_TYPE_PAP);RCellular_NetworkCleanup();
 save(KVS_CELLULAR_AP_USERID,"",1);save(KVS_CELLULAR_AP_PASSWORD,"",1);save(KVS_CELLULAR_AP_AUTH_TYPE,"2",2);
 assert(Connect2AP() && received.ap_user_name[0]==0 && received.ap_pass[0]==0 && received.auth_type==CELLULAR_AUTH_TYPE_CHAP);RCellular_NetworkCleanup();
 before=inits;save(KVS_CELLULAR_AP_AUTH_TYPE,"3",1);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_AUTH_TYPE,"00",2);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_AUTH_TYPE,"0",1);memset(longValue,'a',sizeof(longValue));
 save(KVS_CELLULAR_AP_NAME,longValue,sizeof(received.ap_name)+1);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_NAME,"a\0b",3);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_NAME,"",1);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_NAME,"stored.invalid",15);shortRead=1;assert(!Connect2AP() && inits==before);shortRead=0;
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_AUTH_TYPE,"3",1));
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_NAME,longValue,CELLULAR_MAX_AP_NAME_LENGTH+1));
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_USERID,longValue,CELLULAR_MAX_AP_ID_LENGTH+1));
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_PASSWORD,longValue,CELLULAR_MAX_AP_PASS_LENGTH+1));
 assert(prvCellularValueValid(KVS_CELLULAR_AP_USERID,"",1));
 assert(prvCellularValueValid(KVS_CELLULAR_AP_PASSWORD,"",1));
 assert(xProvisionIdtNetworkCredentials()==pdTRUE);
 save(KVS_CELLULAR_AP_NAME,"later.invalid",14);save(KVS_CELLULAR_AP_AUTH_TYPE,"3",1);
 assert(Connect2AP() && strcmp((char*)received.ap_name,"native.invalid")==0 && received.auth_type==CELLULAR_AUTH_TYPE_NONE);
 assert(received.ap_user_name[0]==0 && received.ap_pass[0]==0);RCellular_NetworkCleanup();
 return 0;
}
'''
        headers = self.store_headers()
        headers["FreeRTOS.h"] += 'typedef unsigned TickType_t;\n#define pdMS_TO_TICKS(x) (x)\n'
        headers["task.h"] = '#include "FreeRTOS.h"\nTickType_t xTaskGetTickCount(void);void vTaskDelay(TickType_t);\n'
        headers["platform.h"] = '#define BSP_MCU_RX65N 1\n'
        headers["idt_network_config.h"] = '#define IDT_CELLULAR_APN "native.invalid"\n#define IDT_CELLULAR_APN_USER ""\n#define IDT_CELLULAR_APN_PASSWORD ""\n#define IDT_CELLULAR_APN_AUTH "0"\n'
        host.ProductApiTests.compile_run(self, source, headers,
            [PRODUCT / "r_cellular_network.c", ROOT / "Test/ports/rx_idt_network.c"],
            host.r_cellular_includes() + [ROOT / "Test/ports"],
            ["ENABLE_IDT_TRANSPORT_TEST=1", "IDT_TARGET_RX65N_BG96=1", "CELLULAR_APN_KVS_ENABLE=1"])

    def test_native_committed_profile_reaches_public_r_cellular_ap_api(self):
        host.ProductApiTests.compile_run(self, r'''
#include <assert.h>
#include <string.h>
#include "task.h"
#include "r_cellular_network.h"
#include "rx_idt_network.h"
#include "store.h"

char fixtureApn[128]="native.invalid", fixtureUser[128]="", fixturePassword[128]="", fixtureAuth[8]="0";
static unsigned tick, writes, commits, modemConfigs, activates, cleanups;
static int failWriteAt, failCommit, failAp;
static st_cellular_ap_cfg_t received;
static const char *keys[]={"apn","apnuser","apnpass","apnauth"};
static const char *values[]={fixtureApn,fixtureUser,fixturePassword,fixtureAuth};

TickType_t xTaskGetTickCount(void) { return tick; }
void vTaskDelay(TickType_t ticks) { tick+=ticks; }
e_cellular_err_t R_CELLULAR_Open(st_cellular_ctrl_t *const ctrl,const st_cellular_cfg_t *const config) { (void)config;assert(ctrl==&cellular_ctrl);ctrl->system_state=CELLULAR_SYSTEM_OPEN;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_Close(st_cellular_ctrl_t *const ctrl) { assert(ctrl==&cellular_ctrl);cleanups++;ctrl->system_state=CELLULAR_SYSTEM_CLOSE;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_SetOperator(st_cellular_ctrl_t *const ctrl,const uint8_t *const op) { (void)ctrl;(void)op;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_SetBand(st_cellular_ctrl_t *const ctrl,const uint8_t *const band) { (void)ctrl;(void)band;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_HardwareReset(st_cellular_ctrl_t *const ctrl) { (void)ctrl;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_CloseSocket(st_cellular_ctrl_t *const ctrl,const uint8_t no) { (void)ctrl;(void)no;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_APConnect(st_cellular_ctrl_t *const ctrl,const st_cellular_ap_cfg_t *const config) {
 assert(ctrl==&cellular_ctrl);modemConfigs++;
 if(config)received=*config;else { memset(&received,0,sizeof(received));strcpy((char*)received.ap_name,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_NAME));received.auth_type=CELLULAR_CFG_AUTH_TYPE; }
 if(failAp)return CELLULAR_ERR_MODULE_COM;
 ctrl->system_state=CELLULAR_SYSTEM_CONNECT;activates++;return CELLULAR_SUCCESS;
}
int xprvWriteCacheEntry(size_t keyLength,char *key,size_t length,char *value) {
    unsigned index=writes++;
    assert(index<4 && keyLength==strlen(keys[index]) && strcmp(key,keys[index])==0);
    assert(length==(strlen(values[index])?strlen(values[index]):1));
    assert(memcmp(value,values[index],length)==0);
    return ((int)writes==failWriteAt)?-1:0;
}
BaseType_t KVStore_xCommitChanges(void) { commits++;return failCommit?pdFALSE:pdTRUE; }
size_t prvGetCacheEntryLength(KVStoreKey_t key) { (void)key;return 0; }
size_t xReadEntry(KVStoreKey_t key,void *value,size_t size) { (void)key;(void)value;(void)size;assert(0);return 0; }
static void defaults(void) {
    strcpy(fixtureApn,"native.invalid");strcpy(fixtureUser,"");strcpy(fixturePassword,"");strcpy(fixtureAuth,"0");
    writes=commits=0;failWriteAt=failCommit=0;
}
static void invalidNative(void) {
    assert(xProvisionIdtNetworkCredentials()==pdFALSE && writes==0 && commits==0);
}
int main(void) {
    st_cellular_ap_cfg_t config={0};unsigned before;
    /* Ordinary startup still uses the product board defaults. */
    assert(Connect2AP());
    assert(strcmp((char*)received.ap_name,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_NAME))==0 && strcmp((char*)received.ap_user_name,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_USERID))==0);
    assert(strcmp((char*)received.ap_pass,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_PASSWORD))==0 && received.auth_type==CELLULAR_CFG_AUTH_TYPE);
    before=modemConfigs;assert(Connect2AP() && modemConfigs==before);
    RCellular_NetworkCleanup();

    defaults();assert(xProvisionIdtNetworkCredentials()==pdTRUE && writes==4 && commits==1);
    /* The wrapper owns a copy, so later fixture mutations cannot change it. */
    strcpy(fixtureApn,"later.invalid");
    assert(Connect2AP() && strcmp((char*)received.ap_name,"native.invalid")==0);
    assert(received.auth_type==CELLULAR_AUTH_TYPE_NONE);
    assert(received.ap_user_name[0]==0 && received.ap_pass[0]==0);
    config=received;assert(!RCellular_SetRuntimeApConfig(&config));
    defaults();invalidNative();RCellular_NetworkCleanup();

    defaults();memset(fixtureApn,'a',CELLULAR_MAX_AP_NAME_LENGTH);fixtureApn[CELLULAR_MAX_AP_NAME_LENGTH]=0;
    memset(fixtureUser,'u',CELLULAR_MAX_AP_ID_LENGTH);fixtureUser[CELLULAR_MAX_AP_ID_LENGTH]=0;
    memset(fixturePassword,'p',CELLULAR_MAX_AP_PASS_LENGTH);fixturePassword[CELLULAR_MAX_AP_PASS_LENGTH]=0;
    strcpy(fixtureAuth,"1");assert(xProvisionIdtNetworkCredentials()==pdTRUE && writes==4 && commits==1);
    assert(Connect2AP() && strcmp((char*)received.ap_name,fixtureApn)==0 && strcmp((char*)received.ap_user_name,fixtureUser)==0);
    assert(strcmp((char*)received.ap_pass,fixturePassword)==0 && received.auth_type==CELLULAR_AUTH_TYPE_PAP);
    RCellular_NetworkCleanup();
    defaults();strcpy(fixtureAuth,"2");assert(xProvisionIdtNetworkCredentials()==pdTRUE);
    assert(Connect2AP() && received.auth_type==CELLULAR_AUTH_TYPE_CHAP);RCellular_NetworkCleanup();

    defaults();fixtureApn[0]=0;invalidNative();
    defaults();memset(fixtureApn,'a',CELLULAR_MAX_AP_NAME_LENGTH+1);fixtureApn[CELLULAR_MAX_AP_NAME_LENGTH+1]=0;invalidNative();
    defaults();memset(fixtureUser,'u',CELLULAR_MAX_AP_ID_LENGTH+1);fixtureUser[CELLULAR_MAX_AP_ID_LENGTH+1]=0;invalidNative();
    defaults();memset(fixturePassword,'p',CELLULAR_MAX_AP_PASS_LENGTH+1);fixturePassword[CELLULAR_MAX_AP_PASS_LENGTH+1]=0;invalidNative();
    defaults();strcpy(fixtureAuth,"");invalidNative();
    defaults();strcpy(fixtureAuth,"3");invalidNative();
    defaults();strcpy(fixtureAuth,"00");invalidNative();

    defaults();strcpy(fixtureApn,"uncommitted.invalid");failWriteAt=2;
    assert(xProvisionIdtNetworkCredentials()==pdFALSE && writes==2 && commits==0);
    defaults();strcpy(fixtureApn,"uncommitted.invalid");failCommit=1;
    assert(xProvisionIdtNetworkCredentials()==pdFALSE && writes==4 && commits==1);
    assert(Connect2AP() && strcmp((char*)received.ap_name,"native.invalid")==0 && received.auth_type==CELLULAR_AUTH_TYPE_CHAP);
    RCellular_NetworkCleanup();

    config=received;assert(!RCellular_SetRuntimeApConfig(NULL));
    config=received;config.auth_type=(e_cellular_auth_type_t)255;assert(!RCellular_SetRuntimeApConfig(&config));
    config=received;memset(config.ap_name,'a',sizeof(config.ap_name));assert(!RCellular_SetRuntimeApConfig(&config));
    config=received;memset(config.ap_user_name,'u',sizeof(config.ap_user_name));assert(!RCellular_SetRuntimeApConfig(&config));
    config=received;memset(config.ap_pass,'p',sizeof(config.ap_pass));assert(!RCellular_SetRuntimeApConfig(&config));
    config=received;config.ap_name[0]=0;assert(!RCellular_SetRuntimeApConfig(&config));
    /* A failed public AP call and cleanup retain the committed profile. */
    failAp=1;before=activates;assert(!Connect2AP() && activates==before);RCellular_NetworkCleanup();
    failAp=0;assert(Connect2AP() && strcmp((char*)received.ap_name,"native.invalid")==0);
    RCellular_NetworkCleanup();assert(cleanups>0);
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
#define pdMS_TO_TICKS(x) (x)
#endif
''',
            "task.h": '#include "FreeRTOS.h"\nTickType_t xTaskGetTickCount(void);void vTaskDelay(TickType_t);\n',
            "platform.h": '#define BSP_MCU_RX65N 1\n',
            "store.h": '#ifndef FIXTURE_STORE_H\n#define FIXTURE_STORE_H\n#include "FreeRTOS.h"\ntypedef enum {KVS_CELLULAR_AP_NAME,KVS_CELLULAR_AP_USERID,KVS_CELLULAR_AP_PASSWORD,KVS_CELLULAR_AP_AUTH_TYPE} KVStoreKey_t;\nint xprvWriteCacheEntry(size_t,char *,size_t,char *);\nBaseType_t KVStore_xCommitChanges(void);\nsize_t prvGetCacheEntryLength(KVStoreKey_t);\nsize_t xReadEntry(KVStoreKey_t,void *,size_t);\n#endif\n',
            "idt_network_config.h": r'''
extern char fixtureApn[128],fixtureUser[128],fixturePassword[128],fixtureAuth[8];
#define IDT_CELLULAR_APN fixtureApn
#define IDT_CELLULAR_APN_USER fixtureUser
#define IDT_CELLULAR_APN_PASSWORD fixturePassword
#define IDT_CELLULAR_APN_AUTH fixtureAuth
''',
            **host.r_cellular_headers(),
        }, [PRODUCT / "r_cellular_network.c", ROOT / "Test/ports/rx_idt_network.c"],
            host.r_cellular_includes() + [ROOT / "Test/ports"],
            ["ENABLE_IDT_TRANSPORT_TEST=1", "IDT_TARGET_RX65N_BG96=1"])

    def test_without_apn_kvs_uses_defaults_and_copied_runtime_profile(self):
        headers = self.store_headers()
        headers["FreeRTOS.h"] += 'typedef unsigned TickType_t;\n'
        headers["task.h"] = '#include "FreeRTOS.h"\nvoid vTaskDelay(TickType_t);\n'
        host.ProductApiTests.compile_run(self, r'''
#ifdef NDEBUG
#error Assertions must remain enabled
#endif
#include <assert.h>
#include <string.h>
#include "store.h"
#include "r_cellular_network.h"
static st_cellular_ap_cfg_t received;
static unsigned opens,connections,closes;
void vTaskDelay(TickType_t ticks) { (void)ticks; }
e_cellular_err_t R_CELLULAR_Open(st_cellular_ctrl_t *const ctrl,const st_cellular_cfg_t *const config) {
 (void)config;assert(ctrl==&cellular_ctrl);opens++;ctrl->system_state=CELLULAR_SYSTEM_OPEN;return CELLULAR_SUCCESS;
}
e_cellular_err_t R_CELLULAR_Close(st_cellular_ctrl_t *const ctrl) {
 assert(ctrl==&cellular_ctrl);closes++;ctrl->system_state=CELLULAR_SYSTEM_CLOSE;return CELLULAR_SUCCESS;
}
e_cellular_err_t R_CELLULAR_SetOperator(st_cellular_ctrl_t *const ctrl,const uint8_t *const value) { (void)ctrl;(void)value;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_SetBand(st_cellular_ctrl_t *const ctrl,const uint8_t *const value) { (void)ctrl;(void)value;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_HardwareReset(st_cellular_ctrl_t *const ctrl) { (void)ctrl;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_CloseSocket(st_cellular_ctrl_t *const ctrl,const uint8_t no) { (void)ctrl;(void)no;return CELLULAR_SUCCESS; }
e_cellular_err_t R_CELLULAR_APConnect(st_cellular_ctrl_t *const ctrl,const st_cellular_ap_cfg_t *const config) {
 assert(ctrl==&cellular_ctrl && config);received=*config;connections++;ctrl->system_state=CELLULAR_SYSTEM_CONNECT;return CELLULAR_SUCCESS;
}
/* Deliberately supply no KVS API bodies: an accidental call must fail to link. */
int main(void) {
 st_cellular_ap_cfg_t runtime={0};
 assert(CELLULAR_APN_KVS_ENABLE==0 && KVS_NUM_KEYS==KVS_TSIP_CLIENT_PRIKEY_ID+1);
 assert(Connect2AP() && opens==1 && connections==1);
 assert(!strcmp((char*)received.ap_name,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_NAME)));
 assert(!strcmp((char*)received.ap_user_name,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_USERID)));
 assert(!strcmp((char*)received.ap_pass,CELLULAR_STRING_CONVERT(CELLULAR_CFG_AP_PASSWORD)));
 assert(received.auth_type==CELLULAR_CFG_AUTH_TYPE);
 RCellular_NetworkCleanup();assert(closes==1 && !RCellular_IsOpen());
 strcpy((char*)runtime.ap_name,"benchmark.invalid");strcpy((char*)runtime.ap_user_name,"bench");
 strcpy((char*)runtime.ap_pass,"test-only");runtime.auth_type=CELLULAR_AUTH_TYPE_PAP;
 assert(RCellular_SetRuntimeApConfig(&runtime));
 memset(&runtime,0,sizeof(runtime));
 assert(Connect2AP() && opens==2 && connections==2);
 assert(!strcmp((char*)received.ap_name,"benchmark.invalid") && !strcmp((char*)received.ap_user_name,"bench"));
 assert(!strcmp((char*)received.ap_pass,"test-only") && received.auth_type==CELLULAR_AUTH_TYPE_PAP);
 assert(Connect2AP() && opens==2 && connections==2);
 RCellular_NetworkCleanup();assert(closes==2 && !RCellular_IsOpen());
 assert(Connect2AP() && !strcmp((char*)received.ap_name,"benchmark.invalid"));
 RCellular_NetworkCleanup();return 0;
}
''', headers, [PRODUCT / "r_cellular_network.c"], host.r_cellular_includes(),
            ["CELLULAR_APN_KVS_ENABLE=0"])


if __name__ == "__main__":
    unittest.main()

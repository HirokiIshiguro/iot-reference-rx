"""Native APN binding through product ports and pristine public Cellular headers."""
from pathlib import Path
import unittest

from tools.ci.tests import test_product_oss_api as host
from tools.ci.tests.test_public_signer_cli_commands import _function

ROOT = Path(__file__).resolve().parents[3]
CELLULAR = ROOT / "Middleware/FreeRTOS/FreeRTOS-Cellular-Interface/source"
PRODUCT = ROOT / "Common/ports/cellular_bg96"


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
        return {"FreeRTOS.h": '#include <stddef.h>\n#include <stdint.h>\ntypedef int BaseType_t;\n#define pdTRUE 1\n#define pdFALSE 0\n',
                "lfs_common_data.h": "", "lfs.h": "typedef int lfs_ssize_t;\n",
                "store.h": "".join('#define pkcs11configLABEL_' + label + ' "' + label + '"\n' for label in labels) +
                           '#include "Demos/cli/store.h"\n'}

    def test_normal_persistent_pdn_and_native_override_use_actual_key_lookup(self):
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
#include "bg96_network.h"
#include "store.h"
#include "rx_idt_network.h"
static char values[KVS_NUM_KEYS][128];static size_t lengths[KVS_NUM_KEYS];
static unsigned tick,inits;static int shortRead;
static CellularPdnConfig_t received;
const CellularCommInterface_t Bg96_CommInterface={0};
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
bool Bg96_CommSetRuntimeBaud(void) { return true; }
CellularError_t Cellular_Init(CellularHandle_t *h,const CellularCommInterface_t *c) { assert(c==&Bg96_CommInterface);*h=(CellularHandle_t)1;inits++;return CELLULAR_SUCCESS; }
CellularError_t Cellular_Cleanup(CellularHandle_t h) { (void)h;return CELLULAR_SUCCESS; }
CellularError_t Cellular_ATCommandRaw(CellularHandle_t h,const char *p,const char *v,CellularATCommandType_t t,CellularATCommandResponseReceivedCallback_t c,void *d,uint16_t n) { (void)h;(void)p;(void)v;(void)t;(void)c;(void)d;(void)n;return CELLULAR_SUCCESS; }
CellularError_t Cellular_GetSimCardStatus(CellularHandle_t h,CellularSimCardStatus_t *s) { (void)h;s->simCardState=CELLULAR_SIM_CARD_READY;return CELLULAR_SUCCESS; }
CellularError_t Cellular_SetPdnConfig(CellularHandle_t h,uint8_t id,const CellularPdnConfig_t *p) { (void)h;assert(id==CELLULAR_PDN_CONTEXT_ID);received=*p;return CELLULAR_SUCCESS; }
CellularError_t Cellular_GetServiceStatus(CellularHandle_t h,CellularServiceStatus_t *s) { (void)h;s->psRegistrationStatus=REGISTRATION_STATUS_REGISTERED_HOME;return CELLULAR_SUCCESS; }
CellularError_t Cellular_ActivatePdn(CellularHandle_t h,uint8_t id) { (void)h;(void)id;return CELLULAR_SUCCESS; }
CellularError_t Cellular_DeactivatePdn(CellularHandle_t h,uint8_t id) { (void)h;(void)id;return CELLULAR_SUCCESS; }
static void save(KVStoreKey_t key,const char *value,size_t size) { assert(size<128);memcpy(values[key],value,size);lengths[key]=size; }
int main(void) {
 unsigned before;char longValue[128];
 assert(Connect2AP() && strcmp(received.apnName,BG96_APN_NAME)==0);Bg96_NetworkCleanup();
 save(KVS_CELLULAR_AP_NAME,"stored.invalid",14);save(KVS_CELLULAR_AP_USERID,"user",4);
 save(KVS_CELLULAR_AP_PASSWORD,"password",8);save(KVS_CELLULAR_AP_AUTH_TYPE,"1",1);
 assert(Connect2AP() && strcmp(received.apnName,"stored.invalid")==0);
 assert(strcmp(received.username,"user")==0 && strcmp(received.password,"password")==0 && received.pdnAuthType==CELLULAR_PDN_AUTH_PAP);Bg96_NetworkCleanup();
 save(KVS_CELLULAR_AP_USERID,"",1);save(KVS_CELLULAR_AP_PASSWORD,"",1);save(KVS_CELLULAR_AP_AUTH_TYPE,"2",2);
 assert(Connect2AP() && received.username[0]==0 && received.password[0]==0 && received.pdnAuthType==CELLULAR_PDN_AUTH_CHAP);Bg96_NetworkCleanup();
 before=inits;save(KVS_CELLULAR_AP_AUTH_TYPE,"3",1);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_AUTH_TYPE,"00",2);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_AUTH_TYPE,"0",1);memset(longValue,'a',sizeof(longValue));
 save(KVS_CELLULAR_AP_NAME,longValue,sizeof(received.apnName)+1);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_NAME,"a\0b",3);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_NAME,"",1);assert(!Connect2AP() && inits==before);
 save(KVS_CELLULAR_AP_NAME,"stored.invalid",15);shortRead=1;assert(!Connect2AP() && inits==before);shortRead=0;
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_AUTH_TYPE,"3",1));
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_NAME,longValue,CELLULAR_APN_MAX_SIZE+1));
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_USERID,longValue,CELLULAR_PDN_USERNAME_MAX_SIZE+1));
 assert(!prvCellularValueValid(KVS_CELLULAR_AP_PASSWORD,longValue,CELLULAR_PDN_PASSWORD_MAX_SIZE+1));
 assert(prvCellularValueValid(KVS_CELLULAR_AP_USERID,"",1));
 assert(prvCellularValueValid(KVS_CELLULAR_AP_PASSWORD,"",1));
 assert(xProvisionIdtNetworkCredentials()==pdTRUE);
 save(KVS_CELLULAR_AP_NAME,"later.invalid",14);save(KVS_CELLULAR_AP_AUTH_TYPE,"3",1);
 assert(Connect2AP() && strcmp(received.apnName,"native.invalid")==0 && received.pdnAuthType==CELLULAR_PDN_AUTH_NONE);
 assert(received.username[0]==0 && received.password[0]==0);Bg96_NetworkCleanup();
 return 0;
}
'''
        headers = self.store_headers()
        headers["FreeRTOS.h"] += 'typedef unsigned TickType_t;\n#define pdMS_TO_TICKS(x) (x)\n'
        headers["task.h"] = '#include "FreeRTOS.h"\nTickType_t xTaskGetTickCount(void);void vTaskDelay(TickType_t);\n'
        headers["platform.h"] = '#define BSP_MCU_RX65N 1\n'
        headers["idt_network_config.h"] = '#define IDT_CELLULAR_APN "native.invalid"\n#define IDT_CELLULAR_APN_USER ""\n#define IDT_CELLULAR_APN_PASSWORD ""\n#define IDT_CELLULAR_APN_AUTH "0"\n'
        host.ProductApiTests.compile_run(self, source, headers,
            [PRODUCT / "bg96_network.c", ROOT / "Test/ports/rx_idt_network.c"],
            [PRODUCT, CELLULAR / "include", CELLULAR / "interface", ROOT / "Test/ports"],
            ["ENABLE_IDT_TRANSPORT_TEST=1", "IDT_TARGET_RX65N_BG96=1", "CELLULAR_APN_KVS_ENABLE=1"])

    def test_native_committed_profile_reaches_public_pdn_api(self):
        host.ProductApiTests.compile_run(self, r'''
#include <assert.h>
#include <string.h>
#include "task.h"
#include "bg96_network.h"
#include "rx_idt_network.h"

char fixtureApn[128]="native.invalid", fixtureUser[128]="", fixturePassword[128]="", fixtureAuth[8]="0";
static unsigned tick, writes, commits, modemConfigs, activates, cleanups;
static int failWriteAt, failCommit, failPdn;
static CellularPdnConfig_t received;
static const char *keys[]={"apn","apnuser","apnpass","apnauth"};
static const char *values[]={fixtureApn,fixtureUser,fixturePassword,fixtureAuth};
const CellularCommInterface_t Bg96_CommInterface={0};

TickType_t xTaskGetTickCount(void) { return tick; }
void vTaskDelay(TickType_t ticks) { tick+=ticks; }
bool Bg96_CommSetRuntimeBaud(void) { return true; }
CellularError_t Cellular_Init(CellularHandle_t *handle,const CellularCommInterface_t *comm) {
    assert(comm==&Bg96_CommInterface);*handle=(CellularHandle_t)1;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_Cleanup(CellularHandle_t handle) {
    assert(handle==(CellularHandle_t)1);cleanups++;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_ATCommandRaw(CellularHandle_t handle,const char *prefix,const char *payload,
    CellularATCommandType_t type,CellularATCommandResponseReceivedCallback_t callback,void *data,uint16_t length) {
    assert(handle==(CellularHandle_t)1 && !prefix && !callback && !data && !length);
    assert(type==CELLULAR_AT_NO_RESULT);
    assert(strcmp(payload,"AT+IPR=460800")==0 || strcmp(payload,"AT+QICFG=\"recvind\",1")==0);
    return CELLULAR_SUCCESS;
}
CellularError_t Cellular_GetSimCardStatus(CellularHandle_t handle,CellularSimCardStatus_t *sim) {
    assert(handle==(CellularHandle_t)1);sim->simCardState=CELLULAR_SIM_CARD_READY;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_SetPdnConfig(CellularHandle_t handle,uint8_t id,const CellularPdnConfig_t *config) {
    assert(handle==(CellularHandle_t)1 && id==CELLULAR_PDN_CONTEXT_ID);
    modemConfigs++;received=*config;return failPdn?CELLULAR_BAD_PARAMETER:CELLULAR_SUCCESS;
}
CellularError_t Cellular_GetServiceStatus(CellularHandle_t handle,CellularServiceStatus_t *service) {
    assert(handle==(CellularHandle_t)1);service->psRegistrationStatus=REGISTRATION_STATUS_REGISTERED_HOME;
    return CELLULAR_SUCCESS;
}
CellularError_t Cellular_ActivatePdn(CellularHandle_t handle,uint8_t id) {
    assert(handle==(CellularHandle_t)1 && id==CELLULAR_PDN_CONTEXT_ID);activates++;return CELLULAR_SUCCESS;
}
CellularError_t Cellular_DeactivatePdn(CellularHandle_t handle,uint8_t id) {
    assert(handle==(CellularHandle_t)1 && id==CELLULAR_PDN_CONTEXT_ID);return CELLULAR_SUCCESS;
}
int xprvWriteCacheEntry(size_t keyLength,char *key,size_t length,char *value) {
    unsigned index=writes++;
    assert(index<4 && keyLength==strlen(keys[index]) && strcmp(key,keys[index])==0);
    assert(length==(strlen(values[index])?strlen(values[index]):1));
    assert(memcmp(value,values[index],length)==0);
    return ((int)writes==failWriteAt)?-1:0;
}
BaseType_t KVStore_xCommitChanges(void) { commits++;return failCommit?pdFALSE:pdTRUE; }
static void defaults(void) {
    strcpy(fixtureApn,"native.invalid");strcpy(fixtureUser,"");strcpy(fixturePassword,"");strcpy(fixtureAuth,"0");
    writes=commits=0;failWriteAt=failCommit=0;
}
static void invalidNative(void) {
    assert(xProvisionIdtNetworkCredentials()==pdFALSE && writes==0 && commits==0);
}
int main(void) {
    CellularPdnConfig_t config={0};unsigned before;
    /* Ordinary startup still uses the product board defaults. */
    assert(Connect2AP());
    assert(strcmp(received.apnName,BG96_APN_NAME)==0 && strcmp(received.username,BG96_APN_USER)==0);
    assert(strcmp(received.password,BG96_APN_PASSWORD)==0 && received.pdnAuthType==BG96_PDN_AUTH_TYPE);
    before=modemConfigs;assert(Connect2AP() && modemConfigs==before);
    Bg96_NetworkCleanup();

    defaults();assert(xProvisionIdtNetworkCredentials()==pdTRUE && writes==4 && commits==1);
    /* The wrapper owns a copy, so later fixture mutations cannot change it. */
    strcpy(fixtureApn,"later.invalid");
    assert(Connect2AP() && strcmp(received.apnName,"native.invalid")==0);
    assert(received.pdnContextType==CELLULAR_PDN_CONTEXT_IPV4 && received.pdnAuthType==CELLULAR_PDN_AUTH_NONE);
    assert(received.username[0]==0 && received.password[0]==0);
    config=received;assert(!Bg96_SetRuntimePdnConfig(&config));
    defaults();invalidNative();Bg96_NetworkCleanup();

    defaults();memset(fixtureApn,'a',CELLULAR_APN_MAX_SIZE);fixtureApn[CELLULAR_APN_MAX_SIZE]=0;
    memset(fixtureUser,'u',CELLULAR_PDN_USERNAME_MAX_SIZE);fixtureUser[CELLULAR_PDN_USERNAME_MAX_SIZE]=0;
    memset(fixturePassword,'p',CELLULAR_PDN_PASSWORD_MAX_SIZE);fixturePassword[CELLULAR_PDN_PASSWORD_MAX_SIZE]=0;
    strcpy(fixtureAuth,"1");assert(xProvisionIdtNetworkCredentials()==pdTRUE && writes==4 && commits==1);
    assert(Connect2AP() && strcmp(received.apnName,fixtureApn)==0 && strcmp(received.username,fixtureUser)==0);
    assert(strcmp(received.password,fixturePassword)==0 && received.pdnAuthType==CELLULAR_PDN_AUTH_PAP);
    Bg96_NetworkCleanup();
    defaults();strcpy(fixtureAuth,"2");assert(xProvisionIdtNetworkCredentials()==pdTRUE);
    assert(Connect2AP() && received.pdnAuthType==CELLULAR_PDN_AUTH_CHAP);Bg96_NetworkCleanup();

    defaults();fixtureApn[0]=0;invalidNative();
    defaults();memset(fixtureApn,'a',CELLULAR_APN_MAX_SIZE+1);fixtureApn[CELLULAR_APN_MAX_SIZE+1]=0;invalidNative();
    defaults();memset(fixtureUser,'u',CELLULAR_PDN_USERNAME_MAX_SIZE+1);fixtureUser[CELLULAR_PDN_USERNAME_MAX_SIZE+1]=0;invalidNative();
    defaults();memset(fixturePassword,'p',CELLULAR_PDN_PASSWORD_MAX_SIZE+1);fixturePassword[CELLULAR_PDN_PASSWORD_MAX_SIZE+1]=0;invalidNative();
    defaults();strcpy(fixtureAuth,"");invalidNative();
    defaults();strcpy(fixtureAuth,"3");invalidNative();
    defaults();strcpy(fixtureAuth,"00");invalidNative();

    defaults();strcpy(fixtureApn,"uncommitted.invalid");failWriteAt=2;
    assert(xProvisionIdtNetworkCredentials()==pdFALSE && writes==2 && commits==0);
    defaults();strcpy(fixtureApn,"uncommitted.invalid");failCommit=1;
    assert(xProvisionIdtNetworkCredentials()==pdFALSE && writes==4 && commits==1);
    assert(Connect2AP() && strcmp(received.apnName,"native.invalid")==0 && received.pdnAuthType==CELLULAR_PDN_AUTH_CHAP);
    Bg96_NetworkCleanup();

    config=received;assert(!Bg96_SetRuntimePdnConfig(NULL));
    config.pdnContextType=CELLULAR_PDN_CONTEXT_IPV6;assert(!Bg96_SetRuntimePdnConfig(&config));
    config=received;config.pdnAuthType=(CellularPdnAuthType_t)255;assert(!Bg96_SetRuntimePdnConfig(&config));
    config=received;memset(config.apnName,'a',sizeof(config.apnName));assert(!Bg96_SetRuntimePdnConfig(&config));
    config=received;memset(config.username,'u',sizeof(config.username));assert(!Bg96_SetRuntimePdnConfig(&config));
    config=received;memset(config.password,'p',sizeof(config.password));assert(!Bg96_SetRuntimePdnConfig(&config));
    config=received;config.apnName[0]=0;assert(!Bg96_SetRuntimePdnConfig(&config));
    /* Public PDN failure cleans the handle; retry retains the committed profile. */
    failPdn=1;before=activates;assert(!Connect2AP() && Bg96_GetHandle()==NULL && activates==before);
    failPdn=0;assert(Connect2AP() && strcmp(received.apnName,"native.invalid")==0);
    Bg96_NetworkCleanup();assert(cleanups>0);
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
            "store.h": '#include "FreeRTOS.h"\nint xprvWriteCacheEntry(size_t,char *,size_t,char *);\nBaseType_t KVStore_xCommitChanges(void);\n',
            "idt_network_config.h": r'''
extern char fixtureApn[128],fixtureUser[128],fixturePassword[128],fixtureAuth[8];
#define IDT_CELLULAR_APN fixtureApn
#define IDT_CELLULAR_APN_USER fixtureUser
#define IDT_CELLULAR_APN_PASSWORD fixturePassword
#define IDT_CELLULAR_APN_AUTH fixtureAuth
''',
        }, [PRODUCT / "bg96_network.c", ROOT / "Test/ports/rx_idt_network.c"],
            [PRODUCT, CELLULAR / "include", CELLULAR / "interface", ROOT / "Test/ports"],
            ["ENABLE_IDT_TRANSPORT_TEST=1", "IDT_TARGET_RX65N_BG96=1"])


if __name__ == "__main__":
    unittest.main()

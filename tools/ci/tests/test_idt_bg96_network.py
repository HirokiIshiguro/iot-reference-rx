"""Native APN binding through product ports and pristine public Cellular headers."""
from pathlib import Path
import unittest

from tools.ci.tests import test_product_oss_api as host

ROOT = Path(__file__).resolve().parents[3]
CELLULAR = ROOT / "Middleware/FreeRTOS/FreeRTOS-Cellular-Interface/source"
PRODUCT = ROOT / "Common/ports/cellular_bg96"


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required; no MCU build")
class Bg96NativeNetworkTests(unittest.TestCase):
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

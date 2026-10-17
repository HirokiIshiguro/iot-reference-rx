/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "bg96_network.h"
#if CELLULAR_APN_KVS_ENABLE == 1
#include "store.h"
#endif

static CellularHandle_t moduleHandle;
static bool pdnReady;
static bool runtimePdnConfigured;
static CellularPdnConfig_t runtimePdnConfig;

CellularHandle_t Bg96_GetHandle(void) { return moduleHandle; }

#if CELLULAR_APN_KVS_ENABLE == 1
static bool prvReadPdnString(KVStoreKey_t key, char * value, size_t capacity)
{
    size_t length = prvGetCacheEntryLength(key);
    const char * end;
    if (length == 0U) { return true; } /* Preserve the board default when absent. */
    if (length > capacity) { return false; }
    memset(value, 0, capacity);
    if (xReadEntry(key, value, length) != length) { return false; }
    end = memchr(value, '\0', length);
    if (end != NULL) { return end == value + length - 1U; }
    if (length == capacity) { return false; }
    value[length] = '\0';
    return true;
}

static bool prvLoadPersistentPdn(CellularPdnConfig_t * config)
{
    char auth[3] = {0};
    if (!prvReadPdnString(KVS_CELLULAR_AP_NAME, config->apnName, sizeof(config->apnName)) ||
        !prvReadPdnString(KVS_CELLULAR_AP_USERID, config->username, sizeof(config->username)) ||
        !prvReadPdnString(KVS_CELLULAR_AP_PASSWORD, config->password, sizeof(config->password))) { return false; }
    if (config->apnName[0] == '\0') { return false; }
    if (prvGetCacheEntryLength(KVS_CELLULAR_AP_AUTH_TYPE) != 0U)
    {
        if (!prvReadPdnString(KVS_CELLULAR_AP_AUTH_TYPE, auth, sizeof(auth)) ||
            auth[0] < '0' || auth[0] > '2' || auth[1] != '\0') { return false; }
        switch (auth[0])
        {
            case '0': config->pdnAuthType = CELLULAR_PDN_AUTH_NONE; break;
            case '1': config->pdnAuthType = CELLULAR_PDN_AUTH_PAP; break;
            default: config->pdnAuthType = CELLULAR_PDN_AUTH_CHAP; break;
        }
    }
    return true;
}
#endif

bool Bg96_SetRuntimePdnConfig(const CellularPdnConfig_t * config)
{
    if ((config == NULL) || (moduleHandle != NULL) ||
        (config->pdnContextType != CELLULAR_PDN_CONTEXT_IPV4) ||
        ((config->pdnAuthType != CELLULAR_PDN_AUTH_NONE) &&
         (config->pdnAuthType != CELLULAR_PDN_AUTH_PAP) &&
         (config->pdnAuthType != CELLULAR_PDN_AUTH_CHAP) &&
         (config->pdnAuthType != CELLULAR_PDN_AUTH_PAP_OR_CHAP)) ||
        (config->apnName[0] == '\0') ||
        (memchr(config->apnName, '\0', sizeof(config->apnName)) == NULL) ||
        (memchr(config->username, '\0', sizeof(config->username)) == NULL) ||
        (memchr(config->password, '\0', sizeof(config->password)) == NULL))
    {
        return false;
    }
    runtimePdnConfig = *config;
    runtimePdnConfigured = true;
    return true;
}

void Bg96_NetworkCleanup(void)
{
    if (moduleHandle != NULL)
    {
        if (pdnReady) { (void)Cellular_DeactivatePdn(moduleHandle, CELLULAR_PDN_CONTEXT_ID); }
        (void)Cellular_Cleanup(moduleHandle);
    }
    pdnReady = false;
    moduleHandle = NULL;
}

bool Connect2AP(void)
{
    CellularPdnConfig_t pdn = {0};
    CellularServiceStatus_t service = {0};
    CellularSimCardStatus_t sim = {0};
    CellularError_t status;
    TickType_t began;
    if (pdnReady) { return true; }
    if (runtimePdnConfigured)
    {
        pdn = runtimePdnConfig;
    }
    else
    {
        pdn.pdnContextType = CELLULAR_PDN_CONTEXT_IPV4;
        pdn.pdnAuthType = (CellularPdnAuthType_t)BG96_PDN_AUTH_TYPE;
        strncpy(pdn.apnName, BG96_APN_NAME, sizeof(pdn.apnName) - 1U);
        strncpy(pdn.username, BG96_APN_USER, sizeof(pdn.username) - 1U);
        strncpy(pdn.password, BG96_APN_PASSWORD, sizeof(pdn.password) - 1U);
#if CELLULAR_APN_KVS_ENABLE == 1
        if (!prvLoadPersistentPdn(&pdn)) { return false; }
#endif
    }
    status = Cellular_Init(&moduleHandle, &Bg96_CommInterface);
    if (status != CELLULAR_SUCCESS) { Bg96_NetworkCleanup(); return false; }
    /* Change the modem first; change the host only after the public API returns
     * its positive acknowledgement. This preserves the established 460800 baud. */
    status = Cellular_ATCommandRaw(moduleHandle, NULL, "AT+IPR=460800",
                                   CELLULAR_AT_NO_RESULT, NULL, NULL, 0U);
    if ((status != CELLULAR_SUCCESS) || !Bg96_CommSetRuntimeBaud())
    { Bg96_NetworkCleanup(); return false; }
    status = Cellular_ATCommandRaw(moduleHandle, NULL, "AT+QICFG=\"recvind\",1",
                                   CELLULAR_AT_NO_RESULT, NULL, NULL, 0U);
    if (status != CELLULAR_SUCCESS) { Bg96_NetworkCleanup(); return false; }
    began = xTaskGetTickCount();
    do
    {
        status = Cellular_GetSimCardStatus(moduleHandle, &sim);
        if ((status == CELLULAR_SUCCESS) && (sim.simCardState == CELLULAR_SIM_CARD_READY)) { break; }
        vTaskDelay(pdMS_TO_TICKS(1000U));
    } while ((xTaskGetTickCount() - began) < pdMS_TO_TICKS(60000U));
    if ((status != CELLULAR_SUCCESS) || (sim.simCardState != CELLULAR_SIM_CARD_READY))
    { Bg96_NetworkCleanup(); return false; }
    status = Cellular_SetPdnConfig(moduleHandle, CELLULAR_PDN_CONTEXT_ID, &pdn);
    if (status != CELLULAR_SUCCESS) { Bg96_NetworkCleanup(); return false; }
    began = xTaskGetTickCount();
    do
    {
        status = Cellular_GetServiceStatus(moduleHandle, &service);
        if ((status == CELLULAR_SUCCESS) &&
            ((service.psRegistrationStatus == REGISTRATION_STATUS_REGISTERED_HOME) ||
             (service.psRegistrationStatus == REGISTRATION_STATUS_ROAMING_REGISTERED))) { break; }
        vTaskDelay(pdMS_TO_TICKS(1000U));
    } while ((xTaskGetTickCount() - began) < pdMS_TO_TICKS(180000U));
    if ((status != CELLULAR_SUCCESS) ||
        ((service.psRegistrationStatus != REGISTRATION_STATUS_REGISTERED_HOME) &&
         (service.psRegistrationStatus != REGISTRATION_STATUS_ROAMING_REGISTERED)))
    { Bg96_NetworkCleanup(); return false; }
    status = Cellular_ActivatePdn(moduleHandle, CELLULAR_PDN_CONTEXT_ID);
    pdnReady = status == CELLULAR_SUCCESS;
    if (!pdnReady) { Bg96_NetworkCleanup(); }
    return pdnReady;
}

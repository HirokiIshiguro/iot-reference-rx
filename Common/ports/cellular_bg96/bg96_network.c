/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "bg96_network.h"

static CellularHandle_t moduleHandle;
static bool pdnReady;

CellularHandle_t Bg96_GetHandle(void) { return moduleHandle; }

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
    pdn.pdnContextType = CELLULAR_PDN_CONTEXT_IPV4;
    pdn.pdnAuthType = (CellularPdnAuthType_t)BG96_PDN_AUTH_TYPE;
    strncpy(pdn.apnName, BG96_APN_NAME, sizeof(pdn.apnName) - 1U);
    strncpy(pdn.username, BG96_APN_USER, sizeof(pdn.username) - 1U);
    strncpy(pdn.password, BG96_APN_PASSWORD, sizeof(pdn.password) - 1U);
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

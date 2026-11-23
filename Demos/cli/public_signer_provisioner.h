/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#ifndef PUBLIC_SIGNER_PROVISIONER_H
#define PUBLIC_SIGNER_PROVISIONER_H

#include <stdint.h>
#include "FreeRTOS.h"
#include "task.h"
#include <lfs_common_data.h>
#include <store.h>
#include <serial.h>

#ifndef PUBLIC_SIGNER_PROVISIONER_ENABLE
#define PUBLIC_SIGNER_PROVISIONER_ENABLE 0
#endif

#if PUBLIC_SIGNER_PROVISIONER_ENABLE == 1
#ifndef PUBLIC_SIGNER_SOURCE_SHA
#define PUBLIC_SIGNER_SOURCE_SHA unqualified
#endif
#define PUBLIC_SIGNER_STRING_INNER(value) #value
#define PUBLIC_SIGNER_STRING(value) PUBLIC_SIGNER_STRING_INNER(value)
extern void UserInitialization(void);
extern void CLI_Support_Settings(void);
extern void vRegisterPublicSignerCLICommands(void);
extern void vUARTCommandConsoleStart(uint16_t stackDepth, UBaseType_t priority);

/* Standalone maintenance startup. No MQTT/network/logger task is created and
 * no built-in client credentials are assigned. The same code is used by all
 * MCU/backend combinations; the caller supplies only its UART pin routing. */
static void vRunPublicSignerProvisioner(void (*routeUartPins)(void))
{
    int32_t storageResult;
    UserInitialization();
    CLI_Support_Settings();
    if (routeUartPins != NULL) { routeUartPins(); }
    {
        static const signed char identity[] = "PUBLIC_SIGNER_PROVISIONER source_sha="
            PUBLIC_SIGNER_STRING(PUBLIC_SIGNER_SOURCE_SHA) "\r\n";
        vSerialPutString(identity, sizeof(identity) - 1U);
    }
    storageResult = littlFs_init();
    if (storageResult == 0) { storageResult = vprvCacheInit(); }
    if (storageResult != 0)
    {
        static const signed char failed[] =
            "\r\nPUBLIC_SIGNER_PROVISIONER ERROR: LittleFS/KVS init failed.\r\n";
        vSerialPutString(failed, sizeof(failed) - 1U);
    }
    else
    {
        vRegisterPublicSignerCLICommands();
        vUARTCommandConsoleStart(2048U, tskIDLE_PRIORITY + 1U);
        /* The CLI owns UART output after it is started. */
    }
    for (;;) { vTaskSuspend(NULL); }
}
#endif

#endif

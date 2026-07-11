/*
 * Copyright (C) 2026 OpenAI.
 * SPDX-License-Identifier: MIT
 */

#include <stdbool.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "FreeRTOS.h"
#include "semphr.h"
#include "task.h"

#include "core_mqtt.h"
#include "core_pkcs11_config.h"
#include "core_pkcs11_config_defaults.h"
#include "demo_config.h"
#include "mqtt_agent_task.h"
#include "mqtt_pkcs11_demo_helpers.h"
#include "mqtt_wrapper.h"
#include "multi_tls_demo.h"
#include "transport_mbedtls_pkcs11.h"

#ifndef MULTI_TLS_PRIMARY_TASK_STACK_SIZE
#define MULTI_TLS_PRIMARY_TASK_STACK_SIZE       (2048U)
#endif

#ifndef MULTI_TLS_SECONDARY_TASK_STACK_SIZE
#define MULTI_TLS_SECONDARY_TASK_STACK_SIZE     (6144U)
#endif

#ifndef MULTI_TLS_TASK_PRIORITY
#define MULTI_TLS_TASK_PRIORITY                 (tskIDLE_PRIORITY + 2U)
#endif

#ifndef MULTI_TLS_HEARTBEAT_INTERVAL_MS
#define MULTI_TLS_HEARTBEAT_INTERVAL_MS         (2000U)
#endif

#ifndef MULTI_TLS_SECONDARY_NETWORK_BUFFER_SIZE
#define MULTI_TLS_SECONDARY_NETWORK_BUFFER_SIZE (4096U)
#endif

#ifndef MULTI_TLS_RECONNECT_HOLD_MS
#define MULTI_TLS_RECONNECT_HOLD_MS             (8000U)
#endif

#ifndef MULTI_TLS_MIN_OVERLAP_MS
/* Keep a margin over the CI contract's 30-second minimum. */
#define MULTI_TLS_MIN_OVERLAP_MS                (35000U)
#endif

#define MULTI_TLS_MAX_CLIENT_ID_LENGTH          (128U)
#define MULTI_TLS_CLIENT_ID_SIZE                (MULTI_TLS_MAX_CLIENT_ID_LENGTH + 1U)
#define MULTI_TLS_SECONDARY_CLIENT_ID_SUFFIX    "-tls2"
#define MULTI_TLS_SECONDARY_CLIENT_ID_SUFFIX_LENGTH \
    (sizeof(MULTI_TLS_SECONDARY_CLIENT_ID_SUFFIX) - 1U)
#define MULTI_TLS_TOPIC_SIZE                    (224U)
#define MULTI_TLS_PAYLOAD_SIZE                  (64U)
#define MULTI_TLS_MARKER_SIZE                   (160U)

/* The transport interface intentionally leaves NetworkContext opaque. Every
 * consumer defines the single transport pointer needed by this application. */
struct NetworkContext
{
    TlsTransportParams_t *pParams;
};

static MQTTContext_t xSecondaryMqttContext;
static TlsTransportParams_t xSecondaryTlsParams;
static NetworkContext_t xSecondaryNetworkContext;
static uint8_t ucSecondaryNetworkBuffer[MULTI_TLS_SECONDARY_NETWORK_BUFFER_SIZE];
static SemaphoreHandle_t xMultiTlsStateMutex;

static char pcPrimaryClientId[MULTI_TLS_CLIENT_ID_SIZE];
static char pcSecondaryClientId[MULTI_TLS_CLIENT_ID_SIZE];
static char pcPrimaryTopic[MULTI_TLS_TOPIC_SIZE];
static char pcSecondaryTopic[MULTI_TLS_TOPIC_SIZE];
static uint32_t ulPrimaryClientIdFingerprint = 0U;
static uint32_t ulSecondaryClientIdFingerprint = 0U;

static BaseType_t xPrimaryIdentityReady = pdFALSE;
static volatile BaseType_t xPrimaryUp = pdFALSE;
static volatile BaseType_t xSecondaryUp = pdFALSE;
static volatile BaseType_t xBothUpReported = pdFALSE;
static volatile BaseType_t xSecondaryReconnectRequested = pdFALSE;
static volatile BaseType_t xSecondaryReconnectObserved = pdFALSE;
static volatile BaseType_t xTestCompleteReported = pdFALSE;
static volatile uint32_t ulPrimaryRxCount = 0U;
static volatile uint32_t ulSecondaryRxSinceConnect = 0U;
static volatile uint32_t ulPrimaryRxAtSecondaryDown = 0U;
static volatile TickType_t xSecondaryUpTick = 0U;
static uint32_t ulBothUpGeneration = 0U;

static void prvEvidencePrintf(const char *pcFormat, ...)
{
    char pcMarker[MULTI_TLS_MARKER_SIZE];
    int xLength;
    va_list xArgs;

    va_start(xArgs, pcFormat);
    xLength = vsnprintf(pcMarker, sizeof(pcMarker), pcFormat, xArgs);
    va_end(xArgs);

    if ((xLength < 0) || ((size_t)xLength >= sizeof(pcMarker)))
    {
        configPRINT_STRING("[MULTI_TLS] ERROR reason=marker_truncated\r\n");
    }
    else
    {
        /* Evidence bypasses the nonblocking logging queue so a full queue
         * cannot silently discard one-shot state-transition markers. */
        configPRINT_STRING(pcMarker);
    }
}

static uint32_t prvClientIdFingerprint(const char *pcClientId)
{
    uint32_t ulHash = 2166136261UL;

    while ('\0' != *pcClientId)
    {
        ulHash ^= (uint8_t)*pcClientId;
        ulHash *= 16777619UL;
        pcClientId++;
    }

    return ulHash;
}

static BaseType_t prvHeartbeatSequence(const MQTTPublishInfo_t *pxPublishInfo,
                                       const char *pcExpectedTopic,
                                       uint32_t ulExpectedSession,
                                       uint32_t *pulSequence)
{
    char pcPayload[MULTI_TLS_PAYLOAD_SIZE];
    const char *pcPrefix = (1U == ulExpectedSession) ? "session=1 seq=" : "session=2 seq=";
    char *pcEnd = NULL;
    size_t xExpectedTopicLength;
    size_t xPrefixLength;
    unsigned long ulValue;

    if ((NULL == pxPublishInfo) ||
        (NULL == pxPublishInfo->pTopicName) ||
        (NULL == pxPublishInfo->pPayload) ||
        (NULL == pcExpectedTopic) ||
        (NULL == pulSequence) ||
        (pxPublishInfo->payloadLength >= sizeof(pcPayload)))
    {
        return pdFAIL;
    }

    xExpectedTopicLength = strlen(pcExpectedTopic);
    if ((pxPublishInfo->topicNameLength != xExpectedTopicLength) ||
        (0 != memcmp(pxPublishInfo->pTopicName,
                     pcExpectedTopic,
                     xExpectedTopicLength)))
    {
        return pdFAIL;
    }

    (void)memcpy(pcPayload, pxPublishInfo->pPayload, pxPublishInfo->payloadLength);
    pcPayload[pxPublishInfo->payloadLength] = '\0';
    xPrefixLength = strlen(pcPrefix);
    if ((pxPublishInfo->payloadLength <= xPrefixLength) ||
        (0 != strncmp(pcPayload, pcPrefix, xPrefixLength)))
    {
        return pdFAIL;
    }

    ulValue = strtoul(pcPayload + xPrefixLength, &pcEnd, 10);
    if ((pcEnd == (pcPayload + xPrefixLength)) ||
        ('\0' != *pcEnd) ||
        (0UL == ulValue))
    {
        return pdFAIL;
    }

    *pulSequence = (uint32_t)ulValue;
    return pdPASS;
}

static void prvLockState(void)
{
    BaseType_t xResult;

    configASSERT(NULL != xMultiTlsStateMutex);
    xResult = xSemaphoreTake(xMultiTlsStateMutex, portMAX_DELAY);
    configASSERT(pdTRUE == xResult);
    (void)xResult;
}

static void prvUnlockState(void)
{
    BaseType_t xResult = xSemaphoreGive(xMultiTlsStateMutex);

    configASSERT(pdTRUE == xResult);
    (void)xResult;
}

static BaseType_t prvIsPrimaryIdentityReady(void)
{
    BaseType_t xReady;

    prvLockState();
    xReady = xPrimaryIdentityReady;
    prvUnlockState();

    return xReady;
}

/* The caller holds xMultiTlsStateMutex so state transitions and their UART
 * markers are observed in one deterministic order by the CI monitor. */
static void prvMaybeReportBothUpLocked(void)
{
    if ((pdTRUE == xPrimaryUp) &&
        (pdTRUE == xSecondaryUp) &&
        (pdFALSE == xBothUpReported))
    {
        xBothUpReported = pdTRUE;
        ulBothUpGeneration++;
        prvEvidencePrintf("[MULTI_TLS] BOTH_UP generation=%lu\r\n",
                          (unsigned long)ulBothUpGeneration);
    }
}

static void prvMaybeReportComplete(void)
{
    TickType_t xNow = xTaskGetTickCount();

    prvLockState();
    if ((pdTRUE == xSecondaryReconnectObserved) &&
        (pdTRUE == xPrimaryUp) &&
        (pdTRUE == xSecondaryUp) &&
        (ulPrimaryRxCount > ulPrimaryRxAtSecondaryDown) &&
        (ulSecondaryRxSinceConnect > 0U) &&
        ((xNow - xSecondaryUpTick) >= pdMS_TO_TICKS(MULTI_TLS_MIN_OVERLAP_MS)) &&
        (pdFALSE == xTestCompleteReported))
    {
        xTestCompleteReported = pdTRUE;
        prvEvidencePrintf("[MULTI_TLS] TEST_COMPLETE\r\n");
    }
    prvUnlockState();
}

static void prvReportSessionUp(uint32_t ulSession,
                               uint32_t ulClientIdFingerprint,
                               uintptr_t uxNetworkContext,
                               uintptr_t uxTlsContext,
                               uintptr_t uxSocket,
                               uint32_t ulConnectionGeneration)
{
    TickType_t xNow = xTaskGetTickCount();

    prvLockState();
    if (1U == ulSession)
    {
        xPrimaryUp = pdTRUE;
    }
    else
    {
        xSecondaryUp = pdTRUE;
        ulSecondaryRxSinceConnect = 0U;
        xSecondaryUpTick = xNow;
        if (pdTRUE == xSecondaryReconnectRequested)
        {
            xSecondaryReconnectRequested = pdFALSE;
            xSecondaryReconnectObserved = pdTRUE;
        }
    }
    prvEvidencePrintf("[MULTI_TLS] SESSION_UP s=%lu cid=%08lx net=%p tls=%p sock=%p gen=%lu\r\n",
                      (unsigned long)ulSession,
                      (unsigned long)ulClientIdFingerprint,
                      (void *)uxNetworkContext,
                      (void *)uxTlsContext,
                      (void *)uxSocket,
                      (unsigned long)ulConnectionGeneration);
    prvMaybeReportBothUpLocked();
    prvUnlockState();
}

static void prvReportSessionDown(uint32_t ulSession, const char *pcReason)
{
    prvLockState();
    if (1U == ulSession)
    {
        xPrimaryUp = pdFALSE;
    }
    else
    {
        xSecondaryUp = pdFALSE;
        ulPrimaryRxAtSecondaryDown = ulPrimaryRxCount;
    }
    xBothUpReported = pdFALSE;
    prvEvidencePrintf("[MULTI_TLS] SESSION_DOWN session=%lu reason=%s\r\n",
                      (unsigned long)ulSession,
                      pcReason);
    prvUnlockState();
}

static void prvPrimaryIncomingPublish(void *pvContext, MQTTPublishInfo_t *pxPublishInfo)
{
    uint32_t ulSequence = 0U;
    (void)pvContext;

    if (pdPASS == prvHeartbeatSequence(pxPublishInfo,
                                       pcPrimaryTopic,
                                       1U,
                                       &ulSequence))
    {
        prvLockState();
        ulPrimaryRxCount++;
        prvEvidencePrintf("[MULTI_TLS] HEARTBEAT_RX session=1 seq=%lu\r\n", (unsigned long)ulSequence);
        prvUnlockState();
        prvMaybeReportComplete();
    }
}

static bool prvSecondaryIncomingPacket(MQTTContext_t *pxMqttContext,
                                       MQTTPacketInfo_t *pxPacketInfo,
                                       MQTTDeserializedInfo_t *pxDeserializedInfo,
                                       MQTTSuccessFailReasonCode_t *pxReasonCode,
                                       MQTTPropBuilder_t *pxSendPropsBuffer,
                                       MQTTPropBuilder_t *pxGetPropsBuffer)
{
    (void)pxMqttContext;
    (void)pxReasonCode;
    (void)pxSendPropsBuffer;
    (void)pxGetPropsBuffer;

    if ((NULL != pxPacketInfo) &&
        (NULL != pxDeserializedInfo) &&
        (MQTT_PACKET_TYPE_PUBLISH == (pxPacketInfo->type & 0xF0U)) &&
        (NULL != pxDeserializedInfo->pPublishInfo))
    {
        MQTTPublishInfo_t *pxPublishInfo = pxDeserializedInfo->pPublishInfo;
        uint32_t ulSequence = 0U;

        if (pdPASS == prvHeartbeatSequence(pxPublishInfo,
                                           pcSecondaryTopic,
                                           2U,
                                           &ulSequence))
        {
            prvLockState();
            ulSecondaryRxSinceConnect++;
            prvEvidencePrintf("[MULTI_TLS] HEARTBEAT_RX session=2 seq=%lu\r\n", (unsigned long)ulSequence);
            prvUnlockState();
            prvMaybeReportComplete();
        }
    }
    else if ((NULL != pxPacketInfo) && (NULL != pxDeserializedInfo))
    {
        vHandleOtherIncomingPacket(pxPacketInfo, pxDeserializedInfo->packetIdentifier);
    }

    return true;
}

static void prvPrimaryHeartbeatTask(void *pvParameters)
{
    uint32_t ulSequence = 0U;
    BaseType_t xSubscriptionReady = pdFALSE;
    BaseType_t xWasUp = pdFALSE;
    MQTTAgentConnectionInfo_t xInfo;
    uint32_t ulPrimaryConnectionGeneration = 0U;
    int xClientIdLength;
    (void)pvParameters;

    (void)xWaitForMQTTAgentState(MQTT_AGENT_STATE_CONNECTED, portMAX_DELAY);
    while (pdPASS != xGetMQTTAgentConnectionInfo(&xInfo))
    {
        vTaskDelay(pdMS_TO_TICKS(100U));
    }
    xClientIdLength = snprintf(pcPrimaryClientId,
                               sizeof(pcPrimaryClientId),
                               "%s",
                               xInfo.pcClientIdentifier);
    if ((xClientIdLength < 1) ||
        ((size_t)xClientIdLength >= sizeof(pcPrimaryClientId)))
    {
        prvEvidencePrintf("[MULTI_TLS] ERROR reason=primary_client_id_too_long\r\n");
        vTaskDelete(NULL);
        return;
    }
    ulPrimaryClientIdFingerprint = prvClientIdFingerprint(pcPrimaryClientId);
    (void)snprintf(pcPrimaryTopic,
                   sizeof(pcPrimaryTopic),
                   "multi_tls/%s/session/1",
                   pcPrimaryClientId);
    prvLockState();
    xPrimaryIdentityReady = pdTRUE;
    prvUnlockState();

    for (;;)
    {
        if (pdPASS == xGetMQTTAgentConnectionInfo(&xInfo))
        {
            if ((pdTRUE == xWasUp) &&
                (ulPrimaryConnectionGeneration != xInfo.ulConnectionGeneration))
            {
                prvReportSessionDown(1U, "agent_reconnect");
                xSubscriptionReady = pdFALSE;
                xWasUp = pdFALSE;
            }

            if (pdFALSE == xSubscriptionReady)
            {
                if (MQTTSuccess == MqttAgent_SubscribeSync(pcPrimaryTopic,
                                                           (uint16_t)strlen(pcPrimaryTopic),
                                                           MQTTQoS1,
                                                           prvPrimaryIncomingPublish,
                                                           NULL))
                {
                    xSubscriptionReady = pdTRUE;
                }
            }

            if (pdFALSE == xWasUp)
            {
                prvReportSessionUp(1U,
                                   ulPrimaryClientIdFingerprint,
                                   xInfo.uxNetworkContext,
                                   xInfo.uxTlsContext,
                                   xInfo.uxSocket,
                                   xInfo.ulConnectionGeneration);
                ulPrimaryConnectionGeneration = xInfo.ulConnectionGeneration;
                xWasUp = pdTRUE;
            }

            if (pdTRUE == xSubscriptionReady)
            {
                char pcPayload[MULTI_TLS_PAYLOAD_SIZE];
                size_t xPayloadLength;

                ulSequence++;
                (void)snprintf(pcPayload, sizeof(pcPayload), "session=1 seq=%lu", (unsigned long)ulSequence);
                xPayloadLength = strlen(pcPayload);

                if (mqttWrapper_publish(pcPrimaryTopic,
                                        strlen(pcPrimaryTopic),
                                        (uint8_t *)pcPayload,
                                        xPayloadLength))
                {
                    prvEvidencePrintf("[MULTI_TLS] HEARTBEAT_TX session=1 seq=%lu\r\n", (unsigned long)ulSequence);
                }
            }
        }
        else if (pdTRUE == xWasUp)
        {
            prvReportSessionDown(1U, "agent_disconnect");
            xSubscriptionReady = pdFALSE;
            xWasUp = pdFALSE;
        }

        vTaskDelay(pdMS_TO_TICKS(MULTI_TLS_HEARTBEAT_INTERVAL_MS));
    }
}

static void prvSecondarySessionTask(void *pvParameters)
{
    uint32_t ulSequence = 0U;
    uint32_t ulConnectedHeartbeats = 0U;
    uint32_t ulSecondaryConnectionGeneration = 0U;
    BaseType_t xForcedReconnectDone = pdFALSE;
    TickType_t xSessionUpTick = 0U;
    int xClientIdLength;
    (void)pvParameters;

    while (pdFALSE == prvIsPrimaryIdentityReady())
    {
        vTaskDelay(pdMS_TO_TICKS(100U));
    }

    xClientIdLength = snprintf(pcSecondaryClientId,
                               sizeof(pcSecondaryClientId),
                               "%.*s%s",
                               (int)(MULTI_TLS_MAX_CLIENT_ID_LENGTH -
                                     MULTI_TLS_SECONDARY_CLIENT_ID_SUFFIX_LENGTH),
                               pcPrimaryClientId,
                               MULTI_TLS_SECONDARY_CLIENT_ID_SUFFIX);
    configASSERT((xClientIdLength > 0) &&
                 ((size_t)xClientIdLength < sizeof(pcSecondaryClientId)));
    ulSecondaryClientIdFingerprint = prvClientIdFingerprint(pcSecondaryClientId);
    if (ulSecondaryClientIdFingerprint == ulPrimaryClientIdFingerprint)
    {
        prvEvidencePrintf("[MULTI_TLS] ERROR reason=client_id_fingerprint_collision\r\n");
        vTaskDelete(NULL);
        return;
    }
    (void)snprintf(pcSecondaryTopic,
                   sizeof(pcSecondaryTopic),
                   "multi_tls/%s/session/2",
                   pcPrimaryClientId);
    xSecondaryNetworkContext.pParams = &xSecondaryTlsParams;

    for (;;)
    {
        MQTTFixedBuffer_t xNetworkBuffer =
        {
            .pBuffer = ucSecondaryNetworkBuffer,
            .size = sizeof(ucSecondaryNetworkBuffer)
        };
        BaseType_t xSessionReady;
        BaseType_t xMqttConnected;
        const char *pcDownReason = "network_error";

        xMqttConnected = xEstablishMqttSession(&xSecondaryMqttContext,
                                               &xSecondaryNetworkContext,
                                               &xNetworkBuffer,
                                               prvSecondaryIncomingPacket,
                                               pkcs11configLABEL_DEVICE_CERTIFICATE_FOR_TLS,
                                               pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS,
                                               pcSecondaryClientId);
        xSessionReady = xMqttConnected;

        if (pdPASS == xSessionReady)
        {
            xSessionReady = xSubscribeToTopic(&xSecondaryMqttContext,
                                              pcSecondaryTopic,
                                              (uint16_t)strlen(pcSecondaryTopic));
        }

        if (pdPASS == xSessionReady)
        {
            ulConnectedHeartbeats = 0U;
            ulSecondaryConnectionGeneration++;
            prvReportSessionUp(2U,
                               ulSecondaryClientIdFingerprint,
                               (uintptr_t)&xSecondaryNetworkContext,
                               (uintptr_t)&xSecondaryTlsParams,
                               (uintptr_t)xSecondaryTlsParams.tcpSocket,
                               ulSecondaryConnectionGeneration);
            xSessionUpTick = xTaskGetTickCount();

            while (pdPASS == xSessionReady)
            {
                char pcPayload[MULTI_TLS_PAYLOAD_SIZE];
                size_t xPayloadLength;

                ulSequence++;
                (void)snprintf(pcPayload, sizeof(pcPayload), "session=2 seq=%lu", (unsigned long)ulSequence);
                xPayloadLength = strlen(pcPayload);
                prvEvidencePrintf("[MULTI_TLS] HEARTBEAT_TX session=2 seq=%lu\r\n", (unsigned long)ulSequence);

                xSessionReady = xPublishToTopic(&xSecondaryMqttContext,
                                                pcSecondaryTopic,
                                                (int32_t)strlen(pcSecondaryTopic),
                                                pcPayload,
                                                xPayloadLength);

                if (pdPASS == xSessionReady)
                {
                    ulConnectedHeartbeats++;
                    prvMaybeReportComplete();
                }

                if ((pdFALSE == xForcedReconnectDone) &&
                    (ulConnectedHeartbeats > 0U) &&
                    ((xTaskGetTickCount() - xSessionUpTick) >=
                     pdMS_TO_TICKS(MULTI_TLS_MIN_OVERLAP_MS)))
                {
                    pcDownReason = "ci_reconnect";
                    xForcedReconnectDone = pdTRUE;
                    prvLockState();
                    xSecondaryReconnectRequested = pdTRUE;
                    prvUnlockState();
                    xSessionReady = pdFAIL;
                }

                if (pdPASS == xSessionReady)
                {
                    vTaskDelay(pdMS_TO_TICKS(MULTI_TLS_HEARTBEAT_INTERVAL_MS));
                }
            }

            prvReportSessionDown(2U, pcDownReason);
            (void)xDisconnectMqttSession(&xSecondaryMqttContext, &xSecondaryNetworkContext);
        }
        else if (pdPASS == xMqttConnected)
        {
            (void)xDisconnectMqttSession(&xSecondaryMqttContext, &xSecondaryNetworkContext);
        }

        if ((pdTRUE == xForcedReconnectDone) && (0 == strcmp(pcDownReason, "ci_reconnect")))
        {
            vTaskDelay(pdMS_TO_TICKS(MULTI_TLS_RECONNECT_HOLD_MS));
        }
        else
        {
            vTaskDelay(pdMS_TO_TICKS(MULTI_TLS_HEARTBEAT_INTERVAL_MS));
        }
    }
}

void vStartMultiTlsDemo(void)
{
    BaseType_t xResult;

    xMultiTlsStateMutex = xSemaphoreCreateMutex();
    configASSERT(NULL != xMultiTlsStateMutex);

    xResult = xTaskCreate(prvPrimaryHeartbeatTask,
                          "MultiTLS-1",
                          MULTI_TLS_PRIMARY_TASK_STACK_SIZE,
                          NULL,
                          MULTI_TLS_TASK_PRIORITY,
                          NULL);
    configASSERT(pdPASS == xResult);

    xResult = xTaskCreate(prvSecondarySessionTask,
                          "MultiTLS-2",
                          MULTI_TLS_SECONDARY_TASK_STACK_SIZE,
                          NULL,
                          MULTI_TLS_TASK_PRIORITY,
                          NULL);
    configASSERT(pdPASS == xResult);
}

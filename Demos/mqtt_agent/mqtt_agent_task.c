/*
 * Copyright (C) 2020 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
 * Modifications Copyright (C) 2023-2025 Renesas Electronics Corporation or its affiliates.
 *
 * SPDX-License-Identifier: MIT
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * http://www.FreeRTOS.org
 * http://aws.amazon.com/freertos
 */

/*
 * This demo creates multiple tasks, all of which use the MQTT agent API to
 * communicate with an MQTT broker through the same MQTT connection.
 *
 * This file contains the initial task created after the TCP/IP stack connects
 * to the network.  The task:
 *
 * 1) Connects to the MQTT broker.
 * 2) Creates the other demo tasks, in accordance with the #defines set in
 *    demo_config.h.  For example, if demo_config.h contains the following
 *    settings:
 *
 *    #define democonfigCREATE_LARGE_MESSAGE_SUB_PUB_TASK     1
 *    #define democonfigNUM_SIMPLE_SUB_PUB_TASKS_TO_CREATE 3
 *
 *    then the initial task will create the task implemented in
 *    large_message_sub_pub_demo.c and three instances of the task
 *    implemented in simple_sub_pub_demo.c.  See the comments at the top
 *    of those files for more information.
 *
 * 3) After creating the demo tasks the initial task could create the MQTT
 *    agent task.  However, as it has no other operations to perform, rather
 *    than create the MQTT agent as a separate task the initial task just calls
 *    the agent's implementing function - effectively turning itself into the
 *    MQTT agent.
 */

/* Standard includes. */
#include <string.h>
#include <stdio.h>
#include <assert.h>

/* Kernel includes. */
#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"
#include "event_groups.h"

/* Demo Specific configs. */
#include "demo_config.h"
#include "demo_config.h"
#include "core_pkcs11_config.h"
#include "core_pkcs11_config_defaults.h"

/* MQTT library includes. */
#include "core_mqtt.h"

/* Transport interface implementation include header for TLS. */
#include "transport_mbedtls_pkcs11.h"
#include "aws_clientcredential.h"
#include "iot_default_root_certificates.h"

/* MQTT library includes. */
#include "core_mqtt.h"

/* MQTT agent include. */
#include "core_mqtt_agent.h"

/* MQTT Agent ports. */
#include "freertos_agent_message.h"
#include "freertos_command_pool.h"

/* Exponential backoff retry include. */
#include "backoff_algorithm.h"

/* Transport interface header file. */
#include "transport_mbedtls_pkcs11.h"

/* Keystore APIs to fetch configuration data. */
#include "aws_clientcredential.h"

/* Includes MQTT Agent Task management APIs. */
#include "mqtt_agent_task.h"
#include "backoff_algorithm.h"

#include "store.h"
#if (ENABLE_OTA_UPDATE_DEMO == 1)
#include "mqtt_wrapper.h"
#endif
#include "pkcs11_helpers.h"

#ifndef democonfigMQTT_BROKER_ENDPOINT
#define democonfigMQTT_BROKER_ENDPOINT (clientcredentialMQTT_BROKER_ENDPOINT)
#endif

/**
 * @brief The root CA certificate belonging to the broker.
 */
#ifndef democonfigROOT_CA_PEM
#define democonfigROOT_CA_PEM (tlsATS1_ROOT_CERTIFICATE_PEM)
#endif

#ifndef democonfigCLIENT_IDENTIFIER

/**
 * @brief The MQTT client identifier used in this example.  Each client identifier
 * must be unique so edit as required to ensure no two clients connecting to the
 * same broker use the same client identifier.
 */
#define democonfigCLIENT_IDENTIFIER (clientcredentialIOT_THING_NAME)
#endif

#ifndef democonfigMQTT_BROKER_PORT

/**
 * @brief The port to use for the demo.
 */
#define democonfigMQTT_BROKER_PORT (clientcredentialMQTT_BROKER_PORT)
#endif

/**
 * @brief The maximum number of times to run the subscribe publish loop in this
 * demo.
 */
#ifndef democonfigMQTT_MAX_DEMO_COUNT
#define democonfigMQTT_MAX_DEMO_COUNT (3)
#endif

/**
 * @brief Dimensions the buffer used to serialize and deserialize MQTT packets.
 * @note Specified in bytes.  Must be large enough to hold the maximum
 * anticipated MQTT payload.
 */
#ifndef MQTT_AGENT_NETWORK_BUFFER_SIZE
#define MQTT_AGENT_NETWORK_BUFFER_SIZE (5000)
#endif

/**
 * @brief Maximum number of subscriptions maintained by the MQTT agent in the subscription store.
 */
#ifndef MQTT_AGENT_MAX_SUBSCRIPTIONS
#define MQTT_AGENT_MAX_SUBSCRIPTIONS (10U)
#endif

/**
 * @brief Timeout for receiving CONNACK after sending an MQTT CONNECT packet.
 * Defined in milliseconds.
 */
#define mqttexampleCONNACK_RECV_TIMEOUT_MS (10000U)

/**
 * @brief The maximum number of retries for network operation with server.
 */
#define RETRY_MAX_ATTEMPTS (BACKOFF_ALGORITHM_RETRY_FOREVER)

/**
 * @brief The maximum back-off delay (in milliseconds) for retrying failed operation
 *  with server.
 */
#define RETRY_MAX_BACKOFF_DELAY_MS (5000U)

/**
 * @brief The base back-off delay (in milliseconds) to use for network operation retry
 * attempts.
 */
#define RETRY_BACKOFF_BASE_MS (500U)

/**
 * @brief The maximum time interval in seconds which is allowed to elapse
 *  between two Control Packets.
 *
 *  It is the responsibility of the Client to ensure that the interval between
 *  Control Packets being sent does not exceed the this Keep Alive value. In the
 *  absence of sending any other Control Packets, the Client MUST send a
 *  PINGREQ Packet.
 */
/*_RB_ Move to be the responsibility of the agent. */
#define mqttexampleKEEP_ALIVE_INTERVAL_SECONDS (60U)

/**
 * @brief Socket send timeouts to use.  Specified in milliseconds.
 */
#define mqttexampleTRANSPORT_SEND_TIMEOUT_MS (60000)

/**
 * @brief Socket receive timeouts to use.  Specified in milliseconds.
 */
#define mqttexampleTRANSPORT_RECV_TIMEOUT_MS (450)

/**
 * @brief Configuration is used to turn on or off persistent sessions with MQTT broker.
 * If the flag is set to true, MQTT broker will remember the previous session so that a re
 * subscription to the topics are not required. Also any incoming publishes to subscriptions
 * will be stored by the broker and resend to device, when it comes back online.
 *
 */
#define mqttexamplePERSISTENT_SESSION_REQUIRED       ( 1 )

/**
 * @brief Used to convert times to/from ticks and milliseconds.
 */
#define mqttexampleMILLISECONDS_PER_SECOND (1000U)
#define mqttexampleMILLISECONDS_PER_TICK (mqttexampleMILLISECONDS_PER_SECOND / configTICK_RATE_HZ)

/**
 * @brief The MQTT agent manages the MQTT contexts.  This set the handle to the
 * context used by this demo.
 */
#define mqttexampleMQTT_CONTEXT_HANDLE ((MQTTContextHandle_t)0)

/**
 * @brief Event Bit corresponding to an MQTT agent state.
 * The event bit is used to set the state bit in event group so that application tasks can
 * wait on a state transition.
 */
#define mqttexampleEVENT_BIT(xState) ((EventBits_t)(1UL << xState))

/**
 * @brief Mask to clear all set event bits for the MQTT agent state event group.
 * State event group is always cleared before setting the next state event bit so that only
 * state is set at anytime.
 */
#define mqttexampleEVENT_BITS_ALL ((EventBits_t)((1ULL << MQTT_AGENT_NUM_STATES) - 1U))

/**
 * @brief MQTT Agent task notification index
 */
#define MQTT_AGENT_NOTIFY_IDX (3U)

/**
 * @brief ThingName which is used as the client identifier for MQTT connection.
 * Thing name is retrieved  at runtime from a key value store.
 */
static char *pcThingName = NULL;

/**
 * @brief Broker endpoint name for the MQTT connection.
 * Broker endpoint name is retrieved at runtime from a key value store.
 */
static char *pcBrokerEndpoint = NULL;

/**
 * @brief Root CA
 */
static char *pcRootCA = NULL;
/*-----------------------------------------------------------*/

/**
 * @brief An element in the list of topic filter subscriptions.
 */
typedef struct TopicFilterSubscription
{
    IncomingPubCallback_t pxIncomingPublishCallback;
    void *pvIncomingPublishCallbackContext;
    uint16_t usTopicFilterLength;
    const char *pcTopicFilter;
    BaseType_t xManageResubscription;
} TopicFilterSubscription_t;

/*-----------------------------------------------------------*/

static TlsTransportParams_t xTlsTransportParams;

/**
 * @brief Initializes an MQTT context, including transport interface and
 * network buffer.
 *
 * @return `MQTTSuccess` if the initialization succeeds, else `MQTTBadParameter`.
 */
static MQTTStatus_t prvMQTTInit (void);

/**
 * @brief Sends an MQTT Connect packet over the already connected TCP socket.
 *
 * @param[in] xIsReconnect Boolean flag to indicate if this is a reconnection.
 * @return `MQTTSuccess` if connection succeeds, else appropriate error code
 * from MQTT_Connect.
 */
static MQTTStatus_t prvCreateMQTTConnection (bool xIsReconnect);

/**
 * @brief Connect a TCP socket to the MQTT broker.
 *
 * @param[in] pxNetworkContext Network context.
 *
 * @return `pdPASS` if connection succeeds, else `pdFAIL`.
 */
static BaseType_t prvCreateTLSConnection (NetworkContext_t *pxNetworkContext);

/**
 * @brief Disconnect a TCP connection.
 *
 * @param[in] pxNetworkContext Network context.
 *
 * @return `pdPASS` if disconnect succeeds, else `pdFAIL`.
 */
static BaseType_t prvDisconnectTLS (NetworkContext_t *pxNetworkContext);

/**
 * @brief Function to attempt to resubscribe to the topics already present in the
 * subscription list.
 *
 * This function will be invoked when this demo requests the broker to
 * reestablish the session and the broker cannot do so. This function will
 * enqueue commands to the MQTT Agent queue and will be processed once the
 * command loop starts.
 *
 * @return `MQTTSuccess` if adding subscribes to the command queue succeeds, else
 * appropriate error code from MQTTAgent_Subscribe.
 */
static MQTTStatus_t prvHandleResubscribe (void);

/**
 * @brief The callback invoked by MQTT agent for a response to SUBSCRIBE request.
 * Parameter indicates whether the request was successful or not. If subscribe was not successful
 * then callback removes the topic from the subscription store and displays a warning log.
 *
 *
 * @param pxCommandContext Pointer to the command context passed from caller
 * @param pxReturnInfo Return Info containing the result of the subscribe command.
 */
static void prvSubscriptionCommandCallback (MQTTAgentCommandContext_t *pxCommandContext,
                                           MQTTAgentReturnInfo_t *pxReturnInfo);

/**
 * @brief Fan out the incoming publishes to the callbacks registered by different
 * tasks. If there are no callbacks registered for the incoming publish, it will be
 * passed to the unsolicited publish handler.
 *
 * @param[in] pMqttAgentContext Agent context.
 * @param[in] packetId Packet ID of publish.
 * @param[in] pxPublishInfo Info of incoming publish.
 */
static void prvIncomingPublishCallback (MQTTAgentContext_t *pMqttAgentContext,
                                       uint16_t packetId,
                                       MQTTPublishInfo_t *pxPublishInfo);

static bool prvMatchTopicFilterSubscriptions (MQTTPublishInfo_t *pxPublishInfo);

static void prvSetMQTTAgentState (MQTTAgentState_t xAgentState);

/**
 * @brief The timer query function provided to the MQTT context.
 *
 * @return Time in milliseconds.
 */
static uint32_t prvGetTimeMs (void);

/**
 * @brief Connects a TCP socket to the MQTT broker, then creates and MQTT
 * connection to the same.
 * @param[in] xIsReconnect Boolean flag to indicate if its a reconnection.
 * @return MQTTConnected if connection was successful, MQTTNotConnected if MQTT connection
 *         failed and all retries exhausted.
 */
static MQTTConnectionStatus_t prvConnectToMQTTBroker (bool xIsReconnect);

/**
 * @brief Get the string value for a key from the KV store.
 * Memory allocated for the string should be freed by calling vPortFree.
 *
 * @return NULL if value not found, pointer to the NULL terminated string value
 *         if found.
 */
/* static char * prvKVStoreGetString( KVStoreKey_t xKey ); */

static void prvMQTTAgentTask (void *pvParameters);
/*-----------------------------------------------------------*/

/**
 * @brief The network context used by the MQTT library transport interface.
 * See https://www.freertos.org/network-interface.html
 */
struct NetworkContext
{
    TlsTransportParams_t *pParams;
};

static NetworkContext_t xNetworkContext;

/**
 * @brief Global entry time into the application to use as a reference timestamp
 * in the #prvGetTimeMs function. #prvGetTimeMs will always return the difference
 * between the current time and the global entry time. This will reduce the chances
 * of overflow for the 32 bit unsigned integer used for holding the timestamp.
 */
static uint32_t ulGlobalEntryTimeMs;

MQTTAgentContext_t xGlobalMqttAgentContext;

static uint8_t xNetworkBuffer[MQTT_AGENT_NETWORK_BUFFER_SIZE];

static MQTTAgentMessageContext_t xCommandQueue;

static TopicFilterSubscription_t xTopicFilterSubscriptions[MQTT_AGENT_MAX_SUBSCRIPTIONS];

static SemaphoreHandle_t xSubscriptionsMutex;

/**
 * @brief Holds the current state of the MQTT agent.
 */
static MQTTAgentState_t xState = MQTT_AGENT_STATE_NONE;

/**
 * @brief Event group used by other tasks to synchronize with the MQTT agent states.
 */
static EventGroupHandle_t xStateEventGrp = NULL;

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvMQTTInit
 * Description  : Initialize an MQTT agent context, including transport and
 *                message interfaces. Allocates and configures the command
 *                queue and initializes the command pool.
 * Arguments    : None.
 * Return Value : MQTTStatus_t - MQTTSuccess if initialization succeeded,
 *                otherwise an appropriate MQTT error code.
 *********************************************************************************************************************/
static MQTTStatus_t prvMQTTInit(void)
{
    TransportInterface_t xTransport;
    MQTTStatus_t xReturn;
    MQTTFixedBuffer_t xFixedBuffer = {.pBuffer = xNetworkBuffer, .size = MQTT_AGENT_NETWORK_BUFFER_SIZE};
    static uint8_t staticQueueStorageArea[MQTT_AGENT_COMMAND_QUEUE_LENGTH * sizeof(MQTTAgentCommand_t *)];
    static StaticQueue_t staticQueueStructure;
    MQTTAgentMessageInterface_t messageInterface =
        {
            .pMsgCtx = NULL,
            .send = Agent_MessageSend,
            .recv = Agent_MessageReceive,
            .getCommand = Agent_GetCommand,
            .releaseCommand = Agent_ReleaseCommand};

    LogDebug(("Creating command queue."));
    xCommandQueue.queue = xQueueCreateStatic(MQTT_AGENT_COMMAND_QUEUE_LENGTH,
                                             sizeof(MQTTAgentCommand_t *),
                                             staticQueueStorageArea,
                                             &staticQueueStructure);
    configASSERT(xCommandQueue.queue);
    messageInterface.pMsgCtx = &xCommandQueue;

    /* Initialize the command pool. */
    Agent_InitializePool();

    /* Fill in Transport Interface send and receive function pointers. */
    xTransport.pNetworkContext = &xNetworkContext;
    xTransport.send = TLS_FreeRTOS_send;
    xTransport.recv = TLS_FreeRTOS_recv;
    xTransport.writev = NULL;

    /* Initialize MQTT library. */
    xReturn = MQTTAgent_Init(&xGlobalMqttAgentContext,
                             &messageInterface,
                             &xFixedBuffer,
                             &xTransport,
                             prvGetTimeMs,
                             prvIncomingPublishCallback,
                             /* Context to pass into the callback. Passing the pointer to subscription array. */
                             NULL);

    return xReturn;
}
/**********************************************************************************************************************
 End of function prvMQTTInit
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvCreateMQTTConnection
 * Description  : Build and send an MQTT CONNECT packet using the global
 *                MQTT context. Handles session resumption and triggers
 *                resubscription if necessary.
 * Arguments    : bool xIsReconnect - true if this is a reconnect attempt.
 * Return Value : MQTTStatus_t - MQTTSuccess on success, otherwise an MQTT
 *                error code from MQTT_Connect or session resume calls.
 *********************************************************************************************************************/
static MQTTStatus_t prvCreateMQTTConnection(bool xIsReconnect)
{
    MQTTStatus_t xResult;
    MQTTConnectInfo_t xConnectInfo;
    bool xSessionPresent = false;

    /* Many fields are not used in this demo so start with everything at 0. */
    memset(&xConnectInfo, 0x00, sizeof(xConnectInfo));

    /* Start with a clean session i.e. direct the MQTT broker to discard any
     * previous session data. Also, establishing a connection with clean session
     * will ensure that the broker does not store any data when this client
     * gets disconnected. */
#if (mqttexamplePERSISTENT_SESSION_REQUIRED == 1)
    {
        xConnectInfo.cleanSession = false;
    }
#else
    {
        xConnectInfo.cleanSession = true;
    }
#endif

    /* The client identifier is used to uniquely identify this MQTT client to
     * the MQTT broker. In a production device the identifier can be something
     * unique, such as a device serial number. */
    xConnectInfo.pClientIdentifier = pcThingName;
    xConnectInfo.clientIdentifierLength = (uint16_t)strlen(pcThingName);

    /* Set MQTT keep-alive period. It is the responsibility of the application
     * to ensure that the interval between Control Packets being sent does not
     * exceed the Keep Alive value. In the absence of sending any other Control
     * Packets, the Client MUST send a PINGREQ Packet.  This responsibility will
     * be moved inside the agent. */
    xConnectInfo.keepAliveSeconds = mqttexampleKEEP_ALIVE_INTERVAL_SECONDS;

    /* Append metrics when connecting to the AWS IoT Core broker. */
#ifdef democonfigUSE_AWS_IOT_CORE_BROKER
#ifdef democonfigCLIENT_USERNAME
    xConnectInfo.pUserName = CLIENT_USERNAME_WITH_METRICS;
    xConnectInfo.userNameLength = (uint16_t)strlen(CLIENT_USERNAME_WITH_METRICS);
    xConnectInfo.pPassword = democonfigCLIENT_PASSWORD;
    xConnectInfo.passwordLength = (uint16_t)strlen(democonfigCLIENT_PASSWORD);
#else
    xConnectInfo.pUserName = AWS_IOT_METRICS_STRING;
    xConnectInfo.userNameLength = AWS_IOT_METRICS_STRING_LENGTH;
    /* Password for authentication is not used. */
    xConnectInfo.pPassword = NULL;
    xConnectInfo.passwordLength = 0U;
#endif
#else /* ifdef democonfigUSE_AWS_IOT_CORE_BROKER */
#ifdef democonfigCLIENT_USERNAME
    xConnectInfo.pUserName = democonfigCLIENT_USERNAME;
    xConnectInfo.userNameLength = (uint16_t)strlen(democonfigCLIENT_USERNAME);
    xConnectInfo.pPassword = democonfigCLIENT_PASSWORD;
    xConnectInfo.passwordLength = (uint16_t)strlen(democonfigCLIENT_PASSWORD);
#endif /* ifdef democonfigCLIENT_USERNAME */
#endif /* ifdef democonfigUSE_AWS_IOT_CORE_BROKER */

    LogInfo(("Creating an MQTT connection to the broker."));

    /* Send MQTT CONNECT packet to broker. MQTT's Last Will and Testament feature
     * is not used in this demo, so it is passed as NULL. */
    xResult = MQTT_Connect(&(xGlobalMqttAgentContext.mqttContext),
                           &xConnectInfo,
                           NULL,
                           mqttexampleCONNACK_RECV_TIMEOUT_MS,
                           &xSessionPresent);

    if ((MQTTSuccess == xResult) && (true == xIsReconnect))
    {
        LogInfo(("Resuming previous MQTT session with broker."));
        xResult = MQTTAgent_ResumeSession(&xGlobalMqttAgentContext, xSessionPresent);

        if ((MQTTSuccess == xResult) && (false == xSessionPresent))
        {
            /* Resubscribe to all the subscribed topics. */
            xResult = prvHandleResubscribe();
        }
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function prvCreateMQTTConnection
 *********************************************************************************************************************/
/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvCreateTLSConnection
 * Description  : Establish a TLS (TCP) connection to the configured MQTT
 *                broker using TLS_FreeRTOS with exponential backoff and
 *                optional ALPN settings for AWS IoT Core.
 * Arguments    : NetworkContext_t * pxNetworkContext - Network context to
 *                populate and connect.
 * Return Value : BaseType_t - pdPASS on success, pdFAIL on failure.
 *********************************************************************************************************************/
static BaseType_t prvCreateTLSConnection(NetworkContext_t *pxNetworkContext)
{
    BaseType_t xConnected = pdFAIL;

    TlsTransportStatus_t xNetworkStatus = TLS_TRANSPORT_CONNECT_FAILURE;
    NetworkCredentials_t xNetworkCredentials = {0};
    BackoffAlgorithmStatus_t xBackoffAlgStatus = BackoffAlgorithmSuccess;
    BackoffAlgorithmContext_t xReconnectParams = {0};
    uint16_t usNextRetryBackOff = 0U;

#ifdef democonfigUSE_AWS_IOT_CORE_BROKER

    /* ALPN protocols must be a NULL-terminated list of strings. Therefore,
     * the first entry will contain the actual ALPN protocol string while the
     * second entry must remain NULL. */
    const char *pcAlpnProtocols[] = {NULL, NULL};

    /* The ALPN string changes depending on whether username/password authentication is used. */
#ifdef democonfigCLIENT_USERNAME
    pcAlpnProtocols[0] = AWS_IOT_CUSTOM_AUTH_ALPN;
#else
    pcAlpnProtocols[0] = AWS_IOT_MQTT_ALPN;
#endif
    xNetworkCredentials.pAlpnProtos = pcAlpnProtocols;
#endif /* ifdef democonfigUSE_AWS_IOT_CORE_BROKER */

    /* Set the credentials for establishing a TLS connection. */
    xNetworkCredentials.pRootCa = (const unsigned char *)pcRootCA;
    xNetworkCredentials.rootCaSize = strlen(pcRootCA) + 1;
    xNetworkCredentials.pClientCertLabel = pkcs11configLABEL_DEVICE_CERTIFICATE_FOR_TLS;
    xNetworkCredentials.pPrivateKeyLabel = pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS;

    xNetworkCredentials.disableSni = democonfigDISABLE_SNI;
    BackoffAlgorithm_InitializeParams(&xReconnectParams,
                                      RETRY_BACKOFF_BASE_MS,
                                      RETRY_MAX_BACKOFF_DELAY_MS,
                                      RETRY_MAX_ATTEMPTS);

    /* Establish a TCP connection with the MQTT broker. This example connects to
     * the MQTT broker as specified in democonfigMQTT_BROKER_ENDPOINT and
     * democonfigMQTT_BROKER_PORT at the top of this file. */

    uint32_t ulRandomNum = 0;
    do
    {
        LogInfo(("Creating a TLS connection to %s:%u.",
                 pcBrokerEndpoint,
                 democonfigMQTT_BROKER_PORT));
        xNetworkStatus = TLS_FreeRTOS_Connect(pxNetworkContext,
                                              pcBrokerEndpoint,
                                              democonfigMQTT_BROKER_PORT,
                                              &xNetworkCredentials,
                                              mqttexampleTRANSPORT_RECV_TIMEOUT_MS,
                                              mqttexampleTRANSPORT_SEND_TIMEOUT_MS);

        xConnected = (TLS_TRANSPORT_SUCCESS == xNetworkStatus) ? pdPASS : pdFAIL;

        if (!xConnected)
        {
            /* Get back-off value (in milliseconds) for the next connection retry. */
            if (xPkcs11GenerateRandomNumber((uint8_t *)&ulRandomNum,
                                            sizeof(ulRandomNum)) == pdPASS)
            {
                xBackoffAlgStatus = BackoffAlgorithm_GetNextBackoff(&xReconnectParams, ulRandomNum, &usNextRetryBackOff);
            }

            if (BackoffAlgorithmSuccess == xBackoffAlgStatus)
            {
                LogWarn(("Connection to the broker failed. "
                         "Retrying connection in %hu ms.",
                         usNextRetryBackOff));
                vTaskDelay(pdMS_TO_TICKS(usNextRetryBackOff));
            }
        }

        if (BackoffAlgorithmRetriesExhausted == xBackoffAlgStatus)
        {
            LogError(("Connection to the broker failed, all attempts exhausted."));
        }
    } while ((pdPASS != xConnected) && (BackoffAlgorithmSuccess == xBackoffAlgStatus));

    return xConnected;
}
/**********************************************************************************************************************
 End of function prvCreateTLSConnection
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvDisconnectTLS
 * Description  : Gracefully disconnect the TLS connection associated with
 *                the provided network context.
 * Arguments    : NetworkContext_t * pxNetworkContext - Network context to
 *                disconnect.
 * Return Value : BaseType_t - pdPASS on success.
 *********************************************************************************************************************/
static BaseType_t prvDisconnectTLS(NetworkContext_t *pxNetworkContext)
{
    LogInfo(("Disconnecting TLS connection.\n"));
    TLS_FreeRTOS_Disconnect(pxNetworkContext);
    return pdPASS;
}
/**********************************************************************************************************************
 End of function prvDisconnectTLS
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvHandleResubscribe
 * Description  : Iterate over the managed subscription list and enqueue
 *                subscribe commands to the MQTT agent so that topics are
 *                resubscribed after a reconnect.
 * Arguments    : None.
 * Return Value : MQTTStatus_t - MQTTSuccess if subscribe commands were
 *                enqueued successfully or if nothing to resubscribe,
 *                otherwise an appropriate MQTT error code.
 *********************************************************************************************************************/
static MQTTStatus_t prvHandleResubscribe(void)
{
    MQTTStatus_t xResult = MQTTBadParameter;
    uint32_t ulIndex = 0U;
    uint16_t usNumSubscriptions = 0U;

    /* These variables need to stay in scope until command completes. */
    static MQTTAgentSubscribeArgs_t xSubArgs = {0};
    static MQTTSubscribeInfo_t xSubInfo[MQTT_AGENT_MAX_SUBSCRIPTIONS] = {0};
    static MQTTAgentCommandInfo_t xCommandParams = {0};

    /* Loop through each subscription in the subscription list and add a subscribe
     * command to the command queue. */
    xSemaphoreTake(xSubscriptionsMutex, portMAX_DELAY);
    {
        for (ulIndex = 0U; ulIndex < MQTT_AGENT_MAX_SUBSCRIPTIONS; ulIndex++)
        {
            /* Check if there is a subscription in the subscription list. This demo
             * doesn't check for duplicate subscriptions. */
            if ((xTopicFilterSubscriptions[ulIndex].usTopicFilterLength > 0) &&
                (pdTRUE == xTopicFilterSubscriptions[ulIndex].xManageResubscription))
            {
                xSubInfo[usNumSubscriptions].pTopicFilter = xTopicFilterSubscriptions[ulIndex].pcTopicFilter;
                xSubInfo[usNumSubscriptions].topicFilterLength = xTopicFilterSubscriptions[ulIndex].usTopicFilterLength;

                /* QoS1 is used for all the subscriptions in this demo. */
                xSubInfo[usNumSubscriptions].qos = MQTTQoS1;

                LogInfo(("Resubscribe to the topic %.*s will be attempted.",
                         xSubInfo[usNumSubscriptions].topicFilterLength,
                         xSubInfo[usNumSubscriptions].pTopicFilter));

                usNumSubscriptions++;
            }
        }
    }
    xSemaphoreGive(xSubscriptionsMutex);

    if (usNumSubscriptions > 0U)
    {
        xSubArgs.pSubscribeInfo = xSubInfo;
        xSubArgs.numSubscriptions = usNumSubscriptions;

        /* The block time can be 0 as the command loop is not running at this point. */
        xCommandParams.blockTimeMs = 0U;
        xCommandParams.cmdCompleteCallback = prvSubscriptionCommandCallback;
        xCommandParams.pCmdCompleteCallbackContext = (void *)&xSubArgs;

        /* Enqueue subscribe to the command queue. These commands will be processed only
         * when command loop starts. */
        xResult = MQTTAgent_Subscribe(&xGlobalMqttAgentContext, &xSubArgs, &xCommandParams);
    }
    else
    {
        /* Mark the resubscribe as success if there is nothing to be subscribed. */
        xResult = MQTTSuccess;
    }

    if (MQTTSuccess != xResult)
    {
        LogError(("Failed to enqueue the MQTT subscribe command. xResult=%s.",
                  MQTT_Status_strerror(xResult)));
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function prvHandleResubscribe
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvSubscriptionCommandCallback
 * Description  : Callback executed when a subscribe command completes. Logs
 *                failures for individual subscriptions and triggers an
 *                assert if the subscribe command failed overall.
 * Arguments    : MQTTAgentCommandContext_t * pxCommandContext - context for
 *                the original subscribe command.
 *                MQTTAgentReturnInfo_t * pxReturnInfo - return info for the
 *                completed command.
 * Return Value : void
 *********************************************************************************************************************/
static void prvSubscriptionCommandCallback(MQTTAgentCommandContext_t *pxCommandContext,
                                           MQTTAgentReturnInfo_t *pxReturnInfo)
{
    uint32_t ulIndex = 0;
    MQTTAgentSubscribeArgs_t *pxSubscribeArgs = (MQTTAgentSubscribeArgs_t *)pxCommandContext;

    /* If the return code is success, no further action is required as all the topic filters
     * are already part of the subscription list. */
    if (MQTTSuccess != pxReturnInfo->returnCode)
    {
        /* Check through each of the suback codes and determine if there are any failures. */
        for (ulIndex = 0; ulIndex < pxSubscribeArgs->numSubscriptions; ulIndex++)
        {
            /* This demo doesn't attempt to resubscribe in the event that a SUBACK failed. */
            if (MQTTSubAckFailure == pxReturnInfo->pSubackCodes[ulIndex])
            {
                LogError(("Failed to resubscribe to topic %.*s.",
                          pxSubscribeArgs->pSubscribeInfo[ulIndex].topicFilterLength,
                          pxSubscribeArgs->pSubscribeInfo[ulIndex].pTopicFilter));
            }
        }

        /* Hit an assert as some of the tasks won't be able to proceed correctly without
         * the subscriptions. This logic will be updated with exponential backoff and retry.  */
        configASSERT(pdTRUE);
    }
}
/**********************************************************************************************************************
 End of function prvSubscriptionCommandCallback
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvIncomingPublishCallback
 * Description  : Handle incoming PUBLISH messages from the broker. Attempts
 *                to match the publish to registered topic filter callbacks
 *                and forwards the publish to the appropriate handler. If no
 *                registered handler exists, the publish is treated as an
 *                unsolicited publish (e.g. OTA handler).
 * Arguments    : MQTTAgentContext_t * pMqttAgentContext - agent context.
 *                uint16_t packetId - packet identifier for the publish.
 *                MQTTPublishInfo_t * pxPublishInfo - deserialized publish info.
 * Return Value : void
 *********************************************************************************************************************/
static void prvIncomingPublishCallback(MQTTAgentContext_t *pMqttAgentContext,
                                       uint16_t packetId,
                                       MQTTPublishInfo_t *pxPublishInfo)
{
    bool xPublishHandled = false;
    char cOriginalChar;
    char *pcLocation;

    (void)packetId;
    (void)pMqttAgentContext;

#if (ENABLE_OTA_UPDATE_DEMO == 1) || (OTA_E2E_TEST_ENABLED == 1)
    extern void handleReceivedPublish(void *pvIncomingPublishCallbackContext,
                                      MQTTPublishInfo_t *pxPublishInfo);
#endif

    /* Fan out the incoming publishes to the callbacks registered using
     * subscription manager. */
    xPublishHandled = prvMatchTopicFilterSubscriptions(pxPublishInfo);

    /* If there are no callbacks to handle the incoming publishes,
     * handle it as an unsolicited publish. */
    if (true != xPublishHandled)
    {
#if (ENABLE_OTA_UPDATE_DEMO == 1) || (OTA_E2E_TEST_ENABLED == 1)
        handleReceivedPublish(NULL, pxPublishInfo);
#endif
    }
    else
    {
        ;
    }
}
/**********************************************************************************************************************
 End of function prvIncomingPublishCallback
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/
/**********************************************************************************************************************
 * Function Name: vStartMQTTAgent
 * Description  : Create the MQTT agent task which runs the MQTT agent
 *                command loop. This function is a thin wrapper around
 *                xTaskCreate.
 * Arguments    : configSTACK_DEPTH_TYPE uxStackSize - stack size for task.
 *                UBaseType_t uxPriority - task priority.
 * Return Value : void
 *********************************************************************************************************************/
void vStartMQTTAgent(configSTACK_DEPTH_TYPE uxStackSize,
                     UBaseType_t uxPriority)
{
    xTaskCreate(prvMQTTAgentTask,
                "MQTT",
                uxStackSize,
                NULL,
                uxPriority,
                NULL);
}
/**********************************************************************************************************************
 End of function vStartMQTTAgent
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: prvMQTTAgentTask
 * Description  : Task implementation for the MQTT agent. Initializes runtime
 *                configuration, retrieves credentials from the key store,
 *                initializes the MQTT context, and runs the agent command
 *                loop handling reconnects and cleanup on termination.
 * Arguments    : void * pvParameters - task parameter (unused).
 * Return Value : void
 *********************************************************************************************************************/
void prvMQTTAgentTask(void *pvParameters)
{
    BaseType_t xStatus = pdPASS;
    MQTTStatus_t xMQTTStatus = MQTTBadParameter;
    MQTTContext_t *pMqttContext = &(xGlobalMqttAgentContext.mqttContext);
    (void)pvParameters;
    size_t thingnameLength;
    size_t endpointLength;
    size_t rootCALength;

    (void)xWaitForMQTTAgentState(MQTT_AGENT_STATE_INITIALIZED, portMAX_DELAY);
    LogInfo(("---------Start MQTT Agent Task---------\r\n"));

    /* Initialization of timestamp for MQTT. */
    ulGlobalEntryTimeMs = prvGetTimeMs();

#if defined(__TEST__)
    pcThingName = clientcredentialIOT_THING_NAME;
    pcBrokerEndpoint = clientcredentialMQTT_BROKER_ENDPOINT;
    pcRootCA = (char *)democonfigROOT_CA_PEM;
#else
    /* Load broker endpoint and thing name for client connection, from the key store. */
    thingnameLength = prvGetCacheEntryLength(KVS_CORE_THING_NAME);
    endpointLength = prvGetCacheEntryLength(KVS_CORE_MQTT_ENDPOINT);
    rootCALength = prvGetCacheEntryLength(KVS_ROOT_CA_ID);

    if (thingnameLength > 0)
    {
        pcThingName = GetStringValue(KVS_CORE_THING_NAME, thingnameLength);
    }

    if (endpointLength > 0)
    {
        pcBrokerEndpoint = GetStringValue(KVS_CORE_MQTT_ENDPOINT, endpointLength);
    }

    if (rootCALength > 0)
    {
        LogInfo(("Using rootCA cert from key store."));
        pcRootCA = GetStringValue(KVS_ROOT_CA_ID, rootCALength);
    }
    else
    {
        LogInfo(("Using default rootCA cert."));
        /* Cast to type "char *" to be compatible with parameter type */
        pcRootCA = (char *)democonfigROOT_CA_PEM;
    }

#endif

    /* Initialize the MQTT context with the buffer and transport interface. */
    if (pdPASS == xStatus)
    {
        xMQTTStatus = prvMQTTInit();

        if (MQTTSuccess != xMQTTStatus)
        {
            LogError(("Failed to initialize MQTT with error %d.", xMQTTStatus));
        }
    }

    if (MQTTSuccess == xMQTTStatus)
    {
        pMqttContext->connectStatus = prvConnectToMQTTBroker(false);

        while (MQTTConnected == pMqttContext->connectStatus)
        {
            /* MQTTAgent_CommandLoop() is effectively the agent implementation.  It
             * will manage the MQTT protocol until such time that an error occurs,
             * which could be a disconnect.  If an error occurs the MQTT context on
             * which the error happened is returned so there is an attempt to
             * clean up and reconnect. */

#if (ENABLE_OTA_UPDATE_DEMO == 1)
            /* Set the MQTT context to be used by the MQTT wrapper. */
            mqttWrapper_setCoreMqttContext(&(xGlobalMqttAgentContext.mqttContext));
#endif

            prvSetMQTTAgentState(MQTT_AGENT_STATE_CONNECTED);

            xMQTTStatus = MQTTAgent_CommandLoop(&xGlobalMqttAgentContext);

            pMqttContext->connectStatus = MQTTNotConnected;
            prvSetMQTTAgentState(MQTT_AGENT_STATE_DISCONNECTED);

            if (MQTTSuccess == xMQTTStatus)
            {
                /*
                 * On a graceful termination, MQTT agent loop returns success.
                 * Cancel all pending MQTT agent requests.
                 * Disconnect the socket and terminate MQTT agent loop.
                 */
                LogInfo(("MQTT Agent loop terminated due to a graceful disconnect."));
                (void)MQTTAgent_CancelAll(&xGlobalMqttAgentContext);
                (void)prvDisconnectTLS(&xNetworkContext);
            }
            else
            {
                LogInfo(("MQTT Agent loop terminated due to abrupt disconnect. Retrying MQTT connection.."));
                /* MQTT agent returned due to an underlying error, reconnect to the loop. */
                (void)prvDisconnectTLS(&xNetworkContext);
                pMqttContext->connectStatus = prvConnectToMQTTBroker(true);
            }
        }
    }

    prvSetMQTTAgentState(MQTT_AGENT_STATE_TERMINATED);
    if (NULL != pcThingName)
    {
        vPortFree(pcThingName);
        pcThingName = NULL;
    }

    if (NULL != pcBrokerEndpoint)
    {
        vPortFree(pcBrokerEndpoint);
        pcBrokerEndpoint = NULL;
    }

    if (NULL != pcRootCA)
    {
        /* pcRootCA can only be released if the value(address) by pcRootCA does not match \
           democonfigROOT_CA_PEM */
        if (pcRootCA != democonfigROOT_CA_PEM)
        {
            vPortFree(pcRootCA);
            pcRootCA = NULL;
        }
        else
        {
            /* No action needed as democonfigROOT_CA_PEM is macro defined. */
        }
    }

    LogInfo(("---------MQTT Agent Task Finished---------\r\n"));
    vTaskDelete(NULL);
}
/**********************************************************************************************************************
 End of function prvMQTTAgentTask
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvConnectToMQTTBroker
 * Description  : Attempt to establish a TLS connection and create an MQTT
 *                connection. Uses exponential backoff and retries on
 *                failure.
 * Arguments    : bool xIsReconnect - true if this is a reconnect attempt.
 * Return Value : MQTTConnectionStatus_t - MQTTConnected on success,
 *                MQTTNotConnected if all retries are exhausted.
 *********************************************************************************************************************/
static MQTTConnectionStatus_t prvConnectToMQTTBroker(bool xIsReconnect)
{
    BaseType_t xStatus = pdFAIL;
    MQTTStatus_t xMQTTStatus;
    MQTTConnectionStatus_t xConnectionStatus = MQTTNotConnected;
    BackoffAlgorithmStatus_t xBackoffAlgStatus = BackoffAlgorithmSuccess;
    BackoffAlgorithmContext_t xReconnectParams = {0};
    uint16_t usNextRetryBackOff = 0U;
    /* Initialize network context. */
    xNetworkContext.pParams = &xTlsTransportParams;

    /* We will use a retry mechanism with an exponential backoff mechanism and
     * jitter.  That is done to prevent a fleet of IoT devices all trying to
     * reconnect at exactly the same time should they become disconnected at
     * the same time. We initialize reconnect attempts and interval here. */
    BackoffAlgorithm_InitializeParams(&xReconnectParams,
                                      RETRY_BACKOFF_BASE_MS,
                                      RETRY_MAX_BACKOFF_DELAY_MS,
                                      RETRY_MAX_ATTEMPTS);

    /* Attempt to connect to MQTT broker. If connection fails, retry after a
     * timeout. Timeout value will exponentially increase until the maximum
     * number of attempts are reached.
     */
    do
    {
        /* Create a TLS connection to broker */
        xStatus = prvCreateTLSConnection(&xNetworkContext);

        if (pdPASS == xStatus)
        {
            xMQTTStatus = prvCreateMQTTConnection(xIsReconnect);

            if (MQTTSuccess != xMQTTStatus)
            {
                LogError(("Failed to connect to MQTT broker, error = %u", xMQTTStatus));
                prvDisconnectTLS(&xNetworkContext);
                xStatus = pdFAIL;
            }
            else
            {
                LogInfo(("Successfully connected to MQTT broker."));
                xConnectionStatus = MQTTConnected;
            }
        }

        if (pdFAIL == xStatus)
        {
            /* Get back-off value (in milliseconds) for the next connection retry. */
            xBackoffAlgStatus = BackoffAlgorithm_GetNextBackoff(&xReconnectParams, xTaskGetTickCount(), &usNextRetryBackOff);

            if (BackoffAlgorithmSuccess == xBackoffAlgStatus)
            {
                LogWarn(("Connection to the broker failed. "
                         "Retrying connection in %hu ms.",
                         usNextRetryBackOff));
                vTaskDelay(pdMS_TO_TICKS(usNextRetryBackOff));
            }
            else if (BackoffAlgorithmRetriesExhausted == xBackoffAlgStatus)
            {
                LogError(("Connection to the broker failed, all attempts exhausted."));
            }
            else
            {
                /* Empty Else. */
            }
        }
    } while ((MQTTNotConnected == xConnectionStatus) && (BackoffAlgorithmSuccess == xBackoffAlgStatus));

    return xConnectionStatus;
}
/**********************************************************************************************************************
 End of function prvConnectToMQTTBroker
 *********************************************************************************************************************/
/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvGetTimeMs
 * Description  : Return the elapsed time in milliseconds since the global
 *                entry time recorded at agent startup. Used by the MQTT
 *                library as its timer source.
 * Arguments    : None.
 * Return Value : uint32_t - elapsed time in milliseconds.
 *********************************************************************************************************************/
static uint32_t prvGetTimeMs(void)
{
    TickType_t xTickCount = 0;
    uint32_t ulTimeMs = 0UL;

    /* Get the current tick count. */
    xTickCount = xTaskGetTickCount();

    /* Convert the ticks to milliseconds. */
    ulTimeMs = (uint32_t)xTickCount * mqttexampleMILLISECONDS_PER_TICK;

    /* Reduce ulGlobalEntryTimeMs from obtained time so as to always return the
     * elapsed time in the application. */
    ulTimeMs = (uint32_t)(ulTimeMs - ulGlobalEntryTimeMs);

    return ulTimeMs;
}
/**********************************************************************************************************************
 End of function prvGetTimeMs
 *********************************************************************************************************************/
/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvMatchTopicFilterSubscriptions
 * Description  : Match an incoming publish against the locally registered
 *                topic filter subscriptions and invoke their callbacks.
 * Arguments    : MQTTPublishInfo_t * pxPublishInfo - incoming publish info.
 * Return Value : bool - true if any subscription handled the publish,
 *                otherwise false.
 *********************************************************************************************************************/
static bool prvMatchTopicFilterSubscriptions(MQTTPublishInfo_t *pxPublishInfo)
{
    uint32_t ulIndex = 0;
    bool isMatched = false;
    bool publishHandled = false;

    xSemaphoreTake(xSubscriptionsMutex, portMAX_DELAY);
    {
        for (ulIndex = 0U; ulIndex < MQTT_AGENT_MAX_SUBSCRIPTIONS; ulIndex++)
        {
            if (xTopicFilterSubscriptions[ulIndex].usTopicFilterLength > 0)
            {
                MQTT_MatchTopic(pxPublishInfo->pTopicName,
                                pxPublishInfo->topicNameLength,
                                xTopicFilterSubscriptions[ulIndex].pcTopicFilter,
                                xTopicFilterSubscriptions[ulIndex].usTopicFilterLength,
                                &isMatched);

                if (true == isMatched)
                {
                    xTopicFilterSubscriptions[ulIndex].pxIncomingPublishCallback(xTopicFilterSubscriptions[ulIndex].pvIncomingPublishCallbackContext,
                                                                                 pxPublishInfo);
                    publishHandled = true;
                }
            }
        }
    }
    xSemaphoreGive(xSubscriptionsMutex);
    return publishHandled;
}
/**********************************************************************************************************************
 End of function prvMatchTopicFilterSubscriptions
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvSetMQTTAgentState
 * Description  : Update the internal state of the MQTT agent and notify
 *                any waiting tasks via the state event group.
 * Arguments    : MQTTAgentState_t xAgentState - new state to set.
 * Return Value : void
 *********************************************************************************************************************/
static void prvSetMQTTAgentState(MQTTAgentState_t xAgentState)
{
    xState = xAgentState;
    (void)xEventGroupClearBits(xStateEventGrp, mqttexampleEVENT_BITS_ALL);
    (void)xEventGroupSetBits(xStateEventGrp, mqttexampleEVENT_BIT(xAgentState));
}
/**********************************************************************************************************************
 End of function prvSetMQTTAgentState
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xMQTTAgentInit
 * Description  : Initialize synchronization primitives used by the MQTT
 *                agent (subscriptions mutex and state event group).
 * Arguments    : None.
 * Return Value : BaseType_t - pdPASS if initialization succeeded, pdFAIL on error.
 *********************************************************************************************************************/
BaseType_t xMQTTAgentInit(void)
{
    BaseType_t xResult = pdFAIL;

    if (MQTT_AGENT_STATE_NONE == xState)
    {
        xSubscriptionsMutex = xSemaphoreCreateMutex();

        if (NULL != xSubscriptionsMutex)
        {
            xResult = pdPASS;
        }

        if (pdPASS == xResult)
        {
            xStateEventGrp = xEventGroupCreate();

            if (NULL == xStateEventGrp)
            {
                xResult = pdFAIL;
            }
        }
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function xMQTTAgentInit
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xGetMQTTAgentState
 * Description  : Return the current state of the MQTT agent.
 * Arguments    : None.
 * Return Value : MQTTAgentState_t - current agent state.
 *********************************************************************************************************************/
MQTTAgentState_t xGetMQTTAgentState(void)
{
    return xState;
}
/**********************************************************************************************************************
 End of function xGetMQTTAgentState
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: xSetMQTTAgentState
 * Description  : Public wrapper to set the MQTT agent state.
 * Arguments    : MQTTAgentState_t xAgentState - state to set.
 * Return Value : void
 *********************************************************************************************************************/
void xSetMQTTAgentState(MQTTAgentState_t xAgentState)
{
    prvSetMQTTAgentState(xAgentState);
}
/**********************************************************************************************************************
 End of function xSetMQTTAgentState
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xWaitForMQTTAgentState
 * Description  : Block until the MQTT agent reaches the specified state or
 *                a timeout occurs.
 * Arguments    : MQTTAgentState_t xState - desired state to wait for.
 *                TickType_t xTicksToWait - max ticks to wait (use portMAX_DELAY to wait indefinitely).
 * Return Value : BaseType_t - pdTRUE if state reached, pdFALSE on timeout or error.
 *********************************************************************************************************************/
BaseType_t xWaitForMQTTAgentState(MQTTAgentState_t xState,
                                  TickType_t xTicksToWait)
{
    EventBits_t xBitsSet;
    EventBits_t xBitsToWaitFor;
    BaseType_t xResult = pdFAIL;

    if (MQTT_AGENT_STATE_NONE != xState)
    {
        xBitsToWaitFor = mqttexampleEVENT_BIT(xState);
        xBitsSet = xEventGroupWaitBits(xStateEventGrp, xBitsToWaitFor, pdFALSE, pdFALSE, xTicksToWait);

        if (0 != (xBitsSet & xBitsToWaitFor))
        {
            xResult = pdTRUE;
        }
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function xWaitForMQTTAgentState
 *********************************************************************************************************************/

/*-----------------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xAddMQTTTopicFilterCallback
 * Description  : Register a local subscription callback for a topic filter.
 *                If the same topic filter and callback are already present,
 *                the call is a no-op. The subscription is stored in a fixed
 *                size subscription table protected by a mutex.
 * Arguments    : const char * pcTopicFilter - topic filter string (pointer must remain valid).
 *                uint16_t usTopicFilterLength - length of the topic filter.
 *                IncomingPubCallback_t pxCallback - callback invoked on matching publishes.
 *                void * pvCallbackContext - context passed to the callback.
 *                BaseType_t xManageResubscription - pdTRUE if agent should resubscribe after reconnect.
 * Return Value : BaseType_t - pdPASS on success, pdFAIL on failure.
 *********************************************************************************************************************/
BaseType_t xAddMQTTTopicFilterCallback(const char *pcTopicFilter,
                                       uint16_t usTopicFilterLength,
                                       IncomingPubCallback_t pxCallback,
                                       void *pvCallbackContext,
                                       BaseType_t xManageResubscription)
{
    BaseType_t xResult = pdFAIL;
    uint32_t ulIndex = 0U;
    uint32_t ulAvailableIndex = MQTT_AGENT_MAX_SUBSCRIPTIONS;

    xSemaphoreTake(xSubscriptionsMutex, portMAX_DELAY);
    {
        /**
         * If this is a duplicate subscription for same topic filter do nothing and return a failure.
         * Else insert at the first available index;
         */
        for (ulIndex = 0U; ulIndex < MQTT_AGENT_MAX_SUBSCRIPTIONS; ulIndex++)
        {
            if ((NULL == xTopicFilterSubscriptions[ulIndex].pcTopicFilter) &&
                (MQTT_AGENT_MAX_SUBSCRIPTIONS == ulAvailableIndex))
            {
                ulAvailableIndex = ulIndex;
            }
            else if ((xTopicFilterSubscriptions[ulIndex].usTopicFilterLength == usTopicFilterLength) &&
                     (strncmp(pcTopicFilter, xTopicFilterSubscriptions[ulIndex].pcTopicFilter, (size_t)usTopicFilterLength) == 0))
            {
                /* If a subscription already exists, don't do anything. */
                if ((xTopicFilterSubscriptions[ulIndex].pxIncomingPublishCallback == pxCallback) &&
                    (xTopicFilterSubscriptions[ulIndex].pvIncomingPublishCallbackContext == pvCallbackContext))
                {
                    ulAvailableIndex = MQTT_AGENT_MAX_SUBSCRIPTIONS;
                    xResult = pdPASS;
                    break;
                }
            }
            else
            {
                ;
            }
        }

        if (ulAvailableIndex < MQTT_AGENT_MAX_SUBSCRIPTIONS)
        {
            xTopicFilterSubscriptions[ulAvailableIndex].pcTopicFilter = pcTopicFilter;
            xTopicFilterSubscriptions[ulAvailableIndex].usTopicFilterLength = usTopicFilterLength;
            xTopicFilterSubscriptions[ulAvailableIndex].pxIncomingPublishCallback = pxCallback;
            xTopicFilterSubscriptions[ulAvailableIndex].pvIncomingPublishCallbackContext = pvCallbackContext;
            xTopicFilterSubscriptions[ulAvailableIndex].xManageResubscription = xManageResubscription;
            xResult = pdPASS;
        }
    }
    xSemaphoreGive(xSubscriptionsMutex);

    return xResult;
}
/**********************************************************************************************************************
 End of function xAddMQTTTopicFilterCallback
 *********************************************************************************************************************/
/*-----------------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: vRemoveMQTTTopicFilterCallback
 * Description  : Remove a previously registered topic filter callback from
 *                the local subscription table. Thread-safe.
 * Arguments    : const char * pcTopicFilter - topic filter string to remove.
 *                uint16_t usTopicFilterLength - length of the topic filter.
 * Return Value : void
 *********************************************************************************************************************/
void vRemoveMQTTTopicFilterCallback(const char *pcTopicFilter,
                                    uint16_t usTopicFilterLength)
{
    uint32_t ulIndex;

    xSemaphoreTake(xSubscriptionsMutex, portMAX_DELAY);
    {
        for (ulIndex = 0U; ulIndex < MQTT_AGENT_MAX_SUBSCRIPTIONS; ulIndex++)
        {
            if (xTopicFilterSubscriptions[ulIndex].usTopicFilterLength == usTopicFilterLength)
            {
                if (strncmp(xTopicFilterSubscriptions[ulIndex].pcTopicFilter, pcTopicFilter, usTopicFilterLength) == 0)
                {
                    memset(&(xTopicFilterSubscriptions[ulIndex]), 0x00, sizeof(TopicFilterSubscription_t));
                }
            }
        }
    }
    xSemaphoreGive(xSubscriptionsMutex);
}
/**********************************************************************************************************************
 End of function vRemoveMQTTTopicFilterCallback
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvSubscribeRqCallback
 * Description  : Internal callback used by synchronous subscribe helper to
 *                notify the calling task of subscribe completion via task
 *                notifications.
 * Arguments    : MQTTAgentCommandContext_t * pxCommandContext - pointer used to carry the caller task handle.
 *                MQTTAgentReturnInfo_t * pxReturnInfo - result information for the subscribe operation.
 * Return Value : void
 *********************************************************************************************************************/
static void prvSubscribeRqCallback(MQTTAgentCommandContext_t *pxCommandContext,
                                   MQTTAgentReturnInfo_t *pxReturnInfo)
{
    TaskHandle_t xTaskHandle = (struct tskTaskControlBlock *)pxCommandContext;

    configASSERT(pxReturnInfo);

    if (NULL != xTaskHandle)
    {
        uint32_t ulNotifyValue = (pxReturnInfo->returnCode & 0xFFFFFF);

        if (pxReturnInfo->pSubackCodes)
        {
            ulNotifyValue += (pxReturnInfo->pSubackCodes[0] << 24);
        }

        (void)xTaskNotifyIndexed(xTaskHandle,
                                 MQTT_AGENT_NOTIFY_IDX,
                                 ulNotifyValue,
                                 eSetValueWithOverwrite);
    }
}
/**********************************************************************************************************************
 End of function prvSubscribeRqCallback
 *********************************************************************************************************************/
/*-----------------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: MqttAgent_SubscribeSync
 * Description  : Convenience helper that registers a local callback for a
 *                topic filter and enqueues a subscribe command synchronously
 *                waiting for the subscribe to complete.
 * Arguments    : const char * pcTopicFilter - topic filter to subscribe to.
 *                uint16_t uxTopicFilterLength - length of topic filter.
 *                MQTTQoS_t xRequestedQoS - requested QoS for the subscription.
 *                IncomingPubCallback_t pxCallback - local callback invoked on publishes.
 *                void * pvCallbackCtx - context for the callback.
 * Return Value : MQTTStatus_t - MQTTSuccess on success or an MQTT error code.
 *********************************************************************************************************************/
MQTTStatus_t MqttAgent_SubscribeSync(const char *pcTopicFilter,
                                     uint16_t uxTopicFilterLength,
                                     MQTTQoS_t xRequestedQoS,
                                     IncomingPubCallback_t pxCallback,
                                     void *pvCallbackCtx)
{
    BaseType_t xMQTTCallbackAdded;
    MQTTStatus_t xResult;

    xMQTTCallbackAdded = xAddMQTTTopicFilterCallback(pcTopicFilter,
                                                     uxTopicFilterLength,
                                                     pxCallback,
                                                     pvCallbackCtx,
                                                     pdFALSE);

    if (pdTRUE == xMQTTCallbackAdded)
    {
        MQTTSubscribeInfo_t xSubInfo =
            {
                .qos = xRequestedQoS,
                .pTopicFilter = pcTopicFilter,
                .topicFilterLength = uxTopicFilterLength};

        MQTTAgentSubscribeArgs_t xSubArgs =
            {
                .pSubscribeInfo = &xSubInfo,
                .numSubscriptions = 1};

        /* The block time can be 0 as the command loop is not running at this point. */
        MQTTAgentCommandInfo_t xCommandParams =
            {
                .blockTimeMs = portMAX_DELAY,
                .cmdCompleteCallback = prvSubscribeRqCallback,
                .pCmdCompleteCallbackContext = (void *)(xTaskGetCurrentTaskHandle())};

        (void)xTaskNotifyStateClearIndexed(NULL, MQTT_AGENT_NOTIFY_IDX);

        /* Enqueue subscribe to the command queue. These commands will be processed only
         * when command loop starts. */
        xResult = MQTTAgent_Subscribe(&xGlobalMqttAgentContext, &xSubArgs, &xCommandParams);

        if (MQTTSuccess == xResult)
        {
            uint32_t ulNotifyValue = 0;

            if (xTaskNotifyWaitIndexed(MQTT_AGENT_NOTIFY_IDX,
                                       0x0,
                                       0xFFFFFFFF,
                                       &ulNotifyValue,
                                       portMAX_DELAY))
            {
                xResult = (ulNotifyValue & 0x00FFFFFF);
            }
            else
            {
                xResult = MQTTKeepAliveTimeout;
            }
        }
    }

    return 0;
}
/**********************************************************************************************************************
 End of function MqttAgent_SubscribeSync
 *********************************************************************************************************************/

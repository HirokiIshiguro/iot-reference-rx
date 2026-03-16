/*
 * Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
* Modifications Copyright (C) 2025 Renesas Electronics Corporation or its affiliates.
 * SPDX-License-Identifier: MIT
 *
 * Licensed under the MIT License. See the LICENSE accompanying this file
 * for the specific language governing permissions and limitations under
 * the License.
 */

#ifndef OTA_DEMO_H
#define OTA_DEMO_H

#include <stdint.h>
#include <stdbool.h>

#include "MQTTFileDownloader_config.h"

#define OTA_DATA_BLOCK_SIZE    mqttFileDownloader_CONFIG_BLOCK_SIZE
#define JOB_DOC_SIZE           (2048U)

typedef enum OtaEvent
{
    OtaAgentEventStart = 0,           /*!< @brief Start the OTA state machine */
    OtaAgentEventWaitForJob,          /*!< @brief Event to wait for Job notification */
    OtaAgentEventRequestJobDocument,  /*!< @brief Event for requesting job document. */
    OtaAgentEventReceivedJobDocument, /*!< @brief Event when job document is received. */
    OtaAgentEventCreateFile,          /*!< @brief Event to create a file. */
    OtaAgentEventRequestFileBlock,    /*!< @brief Event to request file blocks. */
    OtaAgentEventReceivedFileBlock,   /*!< @brief Event to trigger when file block is received. */
    OtaAgentEventCloseFile,           /*!< @brief Event to trigger closing file. */
    OtaAgentEventActivateImage,       /*!< @brief Event to activate the new image. */
    OtaAgentEventVersionCheck,        /*!< @brief Event to verify the new image version. */
    OtaAgentEventSuspend,             /*!< @brief Event to suspend ota task */
    OtaAgentEventResume,              /*!< @brief Event to resume suspended task */
    OtaAgentEventUserAbort,           /*!< @brief Event triggered by user to stop agent. */
    OtaAgentEventJobCanceled,         /*!< @brief Event triggered by AWS that cancels the OTA job. */
    OtaAgentEventShutdown,            /*!< @brief Event to trigger ota shutdown */
    OtaAgentEventNotifyCanceled,      /*!< @brief Event to Unsubscribe from Job topic */
    OtaAgentEventMax                  /*!< @brief Last event specifier */
} OtaEvent_t;

/**
 * @brief OTA Agent states.
 *
 * The current state of the OTA Task (OTA Agent).
 */
typedef enum OtaState
{
    OtaAgentStateNoTransition = -1,
    OtaAgentStateInit = 0,
    OtaAgentStateReady,
    OtaAgentStateRequestingJob,
    OtaAgentStateWaitingForJob,
    OtaAgentStateCreatingFile,
    OtaAgentStateRequestingFileBlock,
    OtaAgentStateWaitingForFileBlock,
    OtaAgentStateClosingFile,
    OtaAgentStateSuspended,
    OtaAgentStateJobCanceled,
    OtaAgentStateShuttingDown,
    OtaAgentStateStopped,
    OtaAgentStateAll
} OtaState_t;

/**
 * @brief  The OTA Agent event and data structures.
 */

typedef struct OtaDataEvent
{
    uint8_t data[OTA_DATA_BLOCK_SIZE * 2]; /*!< Buffer for storing event information. */
    size_t dataLength;                       /*!< Total space required for the event. */
    bool bufferUsed;                         /*!< Flag set when buffer is used otherwise cleared. */
} OtaDataEvent_t;

typedef struct OtaJobEventData
{
    uint8_t jobData[JOB_DOC_SIZE];
    size_t jobDataLength;
} OtaJobEventData_t;

/**
 * @brief Application version structure.
 *
 */
typedef struct
{
    /* MISRA Ref 19.2.1 [Unions] */
    /* More details at: https://github.com/aws/ota-for-aws-iot-embedded-sdk/blob/main/MISRA.md#rule-192 */
    /* coverity[misra_c_2012_rule_19_2_violation] */
    union
    {
#if ( defined( __BYTE_ORDER__ ) && defined( __ORDER_LITTLE_ENDIAN__ ) && ( __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__ ) ) || ( __little_endian__ == 1 ) || WIN32 || ( __BYTE_ORDER == __LITTLE_ENDIAN )
        struct version
        {
            uint16_t build; /*!< @brief Build of the firmware (Z in firmware version Z.Y.X). */
            uint8_t minor;  /*!< @brief Minor version number of the firmware (Y in firmware version Z.Y.X). */

            uint8_t major;  /*!< @brief Major version number of the firmware (X in firmware version Z.Y.X). */
        } x;                /*!< @brief Version number of the firmware. */
#elif ( defined( __BYTE_ORDER__ ) && defined( __ORDER_BIG_ENDIAN__ ) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__ ) || ( __big_endian__ == 1 ) || ( __BYTE_ORDER == __BIG_ENDIAN )
        struct version
        {
            uint8_t major;  /*!< @brief Major version number of the firmware (X in firmware version X.Y.Z). */
            uint8_t minor;  /*!< @brief Minor version number of the firmware (Y in firmware version X.Y.Z). */

            uint16_t build; /*!< @brief Build of the firmware (Z in firmware version X.Y.Z). */
        } x;                /*!< @brief Version number of the firmware. */
#else /* if ( defined( __BYTE_ORDER__ ) && defined( __ORDER_LITTLE_ENDIAN__ ) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__ ) || ( __little_endian__ == 1 ) || WIN32 || ( __BYTE_ORDER == __LITTLE_ENDIAN ) */
#error "Unable to determine byte order!"
#endif /* if ( defined( __BYTE_ORDER__ ) && defined( __ORDER_LITTLE_ENDIAN__ ) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__ ) || ( __little_endian__ == 1 ) || WIN32 || ( __BYTE_ORDER == __LITTLE_ENDIAN ) */
        uint32_t unsignedVersion32;
        int32_t signedVersion32;
    } u; /*!< @brief Version based on configuration in big endian or little endian. */
} AppVersion32_t;

/**
 * @brief Stores information about the event message.
 *
 */
typedef struct OtaEventMsg
{
    OtaDataEvent_t * dataEvent;   /*!< Data Event message. */
    OtaJobEventData_t * jobEvent; /*!< Job Event message. */
    OtaEvent_t eventId;           /*!< Identifier for the event. */
} OtaEventMsg_t;


/**********************************************************************************************************************
 * Function Name: otaDemo_start
 * Description  : Start the OTA demo agent. This function typically creates
 *                OTA tasks and initializes OTA resources.
 * Arguments    : None.
 * Return Value : void
 *********************************************************************************************************************/
void otaDemo_start ( void );

/**********************************************************************************************************************
 End of function otaDemo_start
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: otaDemo_handleIncomingMQTTMessage
 * Description  : Handler for incoming MQTT messages relevant to OTA. Called
 *                by the MQTT receive path when a topic/message pair is
 *                identified as intended for the OTA demo.
 * Arguments    : char * topic - topic string (not necessarily null-terminated).
 *                size_t topicLength - length of the topic string.
 *                uint8_t * message - pointer to message payload.
 *                size_t messageLength - length of message payload.
 * Return Value : bool - true if message handled by OTA demo, false otherwise.
 *********************************************************************************************************************/
bool otaDemo_handleIncomingMQTTMessage ( char * topic,
                                        size_t topicLength,
                                        uint8_t * message,
                                        size_t messageLength );

/**********************************************************************************************************************
 End of function otaDemo_handleIncomingMQTTMessage
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: getOtaAgentState
 * Description  : Return the current OTA agent state.
 * Arguments    : None.
 * Return Value : OtaState_t - current OTA agent state.
 *********************************************************************************************************************/
OtaState_t getOtaAgentState ();

/**********************************************************************************************************************
 End of function getOtaAgentState
 *********************************************************************************************************************/
#endif /* ifndef OTA_DEMO_H */

/*
 * Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
 * Modifications Copyright (C) 2025 Renesas Electronics Corporation or its affiliates.
 * SPDX-License-Identifier: MIT
 *
 * Licensed under the MIT License. See the LICENSE accompanying this file
 * for the specific language governing permissions and limitations under
 * the License.
 */

/**
 * @file ota_os_freertos.c
 * @brief Example implementation of the OTA OS Functional Interface for
 * FreeRTOS.
 */

/* FreeRTOS includes. */
#include "FreeRTOS.h"
#include "queue.h"
#include "timers.h"

/* OTA OS POSIX Interface Includes.*/

#include "ota_demo.h"
#include "ota_os_freertos.h"

/* OTA Event queue attributes.*/
#define MAX_MESSAGES    (20)
#define MAX_MSG_SIZE    (sizeof( OtaEventMsg_t ))

/* Array containing pointer to the OTA event structures used to send events to
 * the OTA task. */
static OtaEventMsg_t queueData[MAX_MESSAGES * MAX_MSG_SIZE];

/* The queue control structure.  .*/
static StaticQueue_t staticQueue;

/* The queue control handle.  .*/
static QueueHandle_t otaEventQueue = NULL;

/**********************************************************************************************************************
 * Function Name: OtaInitEvent_FreeRTOS
 * Description  : Create and initialize the OTA event queue used by the OTA
 *                agent on FreeRTOS platforms. Uses a static buffer and
 *                returns an OtaOsStatus_t indicating success or failure.
 * Arguments    : None.
 * Return Value : OtaOsStatus_t - OtaOsSuccess on success, otherwise an error code.
 *********************************************************************************************************************/
OtaOsStatus_t OtaInitEvent_FreeRTOS()
{
    OtaOsStatus_t otaOsStatus = OtaOsSuccess;

    otaEventQueue = xQueueCreateStatic( ( UBaseType_t ) MAX_MESSAGES,
                                        ( UBaseType_t ) MAX_MSG_SIZE,
                                        ( uint8_t * ) queueData,
                                        &staticQueue );

    if ( NULL == otaEventQueue )
    {
        otaOsStatus = OtaOsEventQueueCreateFailed;

        LogError( ("Failed to create OTA Event Queue: "
                "xQueueCreateStatic returned error: "
                "OtaOsStatus_t=%d \n",
                ( int ) otaOsStatus ) );
    }
    else
    {
        LogInfo( ( "OTA Event Queue created.\n" ) );
    }

    return otaOsStatus;
}
/**********************************************************************************************************************
 End of function OtaInitEvent_FreeRTOS
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: OtaSendEvent_FreeRTOS
 * Description  : Send an OTA event to the OTA event queue. Non-blocking;
 *                returns status indicating if the send succeeded.
 * Arguments    : const void * pEventMsg - pointer to an OtaEventMsg_t to enqueue.
 * Return Value : OtaOsStatus_t - OtaOsSuccess on success, otherwise an error code.
 *********************************************************************************************************************/
OtaOsStatus_t OtaSendEvent_FreeRTOS( const void * pEventMsg )
{
    OtaOsStatus_t otaOsStatus = OtaOsSuccess;
    BaseType_t retVal = pdFALSE;

    /* Send the event to OTA event queue.*/
    retVal = xQueueSendToBack(otaEventQueue, pEventMsg, (TickType_t)0);

    if ( pdTRUE == retVal )
    {
        LogInfo( ( "OTA Event Sent.\n" ) );
    }
    else
    {
        otaOsStatus = OtaOsEventQueueSendFailed;

        LogError( ( "Failed to send event to OTA Event Queue: "
                "xQueueSendToBack returned error: "
                "OtaOsStatus_t=%d \n",
                ( int ) otaOsStatus ) );
    }

    return otaOsStatus;
}
/**********************************************************************************************************************
 End of function OtaSendEvent_FreeRTOS
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: OtaReceiveEvent_FreeRTOS
 * Description  : Receive the next OTA event from the OTA event queue.
 * Arguments    : void * pEventMsg - pointer to an OtaEventMsg_t to populate.
 * Return Value : OtaOsStatus_t - OtaOsSuccess on success, otherwise an error code.
 *********************************************************************************************************************/
OtaOsStatus_t OtaReceiveEvent_FreeRTOS( void * pEventMsg )
{
    OtaOsStatus_t otaOsStatus = OtaOsSuccess;
    BaseType_t retVal = pdFALSE;

    retVal = xQueueReceive(otaEventQueue, (OtaEventMsg_t *)pEventMsg, pdMS_TO_TICKS(3000U));

    if ( pdTRUE == retVal )
    {
        LogInfo( ( "OTA Event received \n" ) );
    }
    else
    {
        otaOsStatus = OtaOsEventQueueReceiveFailed;

        LogInfo(("Pending event on OTA Event Queue"));
    }

    return otaOsStatus;
}
/**********************************************************************************************************************
 End of function OtaReceiveEvent_FreeRTOS
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: OtaDeinitEvent_FreeRTOS
 * Description  : Deinitialize the OTA event queue and free associated resources.
 * Arguments    : None.
 * Return Value : void
 *********************************************************************************************************************/
void OtaDeinitEvent_FreeRTOS()
{
    vQueueDelete( otaEventQueue );

    LogInfo( ( "OTA Event Queue Deleted. \n" ) );
}
/**********************************************************************************************************************
 End of function OtaDeinitEvent_FreeRTOS
 *********************************************************************************************************************/

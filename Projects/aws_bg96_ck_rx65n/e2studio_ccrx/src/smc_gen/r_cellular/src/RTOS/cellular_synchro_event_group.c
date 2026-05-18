/**********************************************************************************************************************
 * DISCLAIMER
 * This software is supplied by Renesas Electronics Corporation and is only intended for use with Renesas products. No
 * other uses are authorized. This software is owned by Renesas Electronics Corporation and is protected under all
 * applicable laws, including copyright laws.
 * THIS SOFTWARE IS PROVIDED "AS IS" AND RENESAS MAKES NO WARRANTIES REGARDING
 * THIS SOFTWARE, WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. ALL SUCH WARRANTIES ARE EXPRESSLY DISCLAIMED. TO THE MAXIMUM
 * EXTENT PERMITTED NOT PROHIBITED BY LAW, NEITHER RENESAS ELECTRONICS CORPORATION NOR ANY OF ITS AFFILIATED COMPANIES
 * SHALL BE LIABLE FOR ANY DIRECT, INDIRECT, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES FOR ANY REASON RELATED TO
 * THIS SOFTWARE, EVEN IF RENESAS OR ITS AFFILIATES HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
 * Renesas reserves the right, without notice, to make changes to this software and to discontinue the availability of
 * this software. By using this software, you agree to the additional terms and conditions found by accessing the
 * following link:
 * http://www.renesas.com/disclaimer
 *
 * Copyright (C) 2024 Renesas Electronics Corporation. All rights reserved.
 *********************************************************************************************************************/
/**********************************************************************************************************************
 * File Name    : cellular_synchro_event_group.c
 * Description  : Function to synchronize between multiple tasks.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "cellular_freertos.h"

/**********************************************************************************************************************
 * Macro definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Exported global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Private (static) variables and functions
 *********************************************************************************************************************/

/*****************************************************************************************
 * Function Name  @fn            cellular_synchro_event_group
 ****************************************************************************************/
uint32_t cellular_synchro_event_group(void * const xEventGroup,
                                        const uint32_t uxBitsToSet,
                                        const uint32_t uxBitsToWaitFor,
                                        const uint32_t xTicksToWait)
{
    uint32_t ret = 0;

    if (NULL != xEventGroup)
    {
#if BSP_CFG_RTOS_USED == (1)
        EventBits_t current_bits = 0;
        TickType_t wait_ticks    = 0;
        const char * task_name   = pcTaskGetName(NULL);

        if (CELLULAR_TIME_OUT_MAX_DELAY == xTicksToWait)
        {
            wait_ticks = (TickType_t)portMAX_DELAY;
        }
        else
        {
            wait_ticks = (TickType_t)xTicksToWait;
        }

        CELLULAR_LOG_INFO(("cellular_synchro_event_group: pre-bits task=%s handle=0x%08lx tick=%lu sched=%ld "
                           "set=0x%08lx wait=0x%08lx timeout=%lu heap=%lu stack_hwm=%lu.",
                           task_name,
                           (unsigned long)xEventGroup,
                           (unsigned long)xTaskGetTickCount(),
                           (long)xTaskGetSchedulerState(),
                           (unsigned long)uxBitsToSet,
                           (unsigned long)uxBitsToWaitFor,
                           (unsigned long)wait_ticks,
                           (unsigned long)xPortGetFreeHeapSize(),
                           (unsigned long)uxTaskGetStackHighWaterMark(NULL)));
        current_bits = xEventGroupGetBitsFromISR((EventGroupHandle_t)xEventGroup);
        CELLULAR_LOG_INFO(("cellular_synchro_event_group: pre-sync task=%s handle=0x%08lx tick=%lu bits=0x%08lx.",
                           task_name,
                           (unsigned long)xEventGroup,
                           (unsigned long)xTaskGetTickCount(),
                           (unsigned long)current_bits));

        if (CELLULAR_TIME_OUT_MAX_DELAY == xTicksToWait)
        {
            ret = xEventGroupSync((EventGroupHandle_t)xEventGroup,
                                    (EventBits_t)uxBitsToSet,
                                    (EventBits_t)uxBitsToWaitFor,
                                    (TickType_t)portMAX_DELAY);
        }
        else
        {
            ret = xEventGroupSync((EventGroupHandle_t)xEventGroup,
                                    (EventBits_t)uxBitsToSet,
                                    (EventBits_t)uxBitsToWaitFor,
                                    (TickType_t)xTicksToWait);
        }

        current_bits = xEventGroupGetBitsFromISR((EventGroupHandle_t)xEventGroup);
        CELLULAR_LOG_INFO(("cellular_synchro_event_group: leave task=%s handle=0x%08lx tick=%lu sched=%ld "
                           "ret=0x%08lx bits=0x%08lx heap=%lu stack_hwm=%lu.",
                           task_name,
                           (unsigned long)xEventGroup,
                           (unsigned long)xTaskGetTickCount(),
                           (long)xTaskGetSchedulerState(),
                           (unsigned long)ret,
                           (unsigned long)current_bits,
                           (unsigned long)xPortGetFreeHeapSize(),
                           (unsigned long)uxTaskGetStackHighWaterMark(NULL)));
#elif BSP_CFG_RTOS_USED == (5)
        UINT rtos_ret;

        rtos_ret = tx_event_flags_set((TX_EVENT_FLAGS_GROUP *)xEventGroup,
                                        (ULONG)uxBitsToSet,
                                        (UINT)TX_OR);
        if (TX_SUCCESS == rtos_ret)
        {
            if (CELLULAR_TIME_OUT_MAX_DELAY == xTicksToWait)
            {
                rtos_ret = tx_event_flags_get((TX_EVENT_FLAGS_GROUP *)xEventGroup,
                                                (ULONG)uxBitsToWaitFor,
                                                (UINT)TX_AND,
                                                (ULONG *)&ret,
                                                (ULONG)TX_WAIT_FOREVER);
            }
            else
            {
                rtos_ret = tx_event_flags_get((TX_EVENT_FLAGS_GROUP *)xEventGroup,
                                                (ULONG)uxBitsToWaitFor,
                                                (UINT)TX_AND,
                                                (ULONG *)&ret,
                                                (ULONG)xTicksToWait);
            }
        }
#endif
    }

    return ret;
}
/**********************************************************************************************************************
 End of function cellular_synchro_event_group
 *********************************************************************************************************************/

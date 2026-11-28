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
 * File Name    : cellular_get_tickcount.c
 * Description  : Function to get the time elapsed since the task was started using the RTOS function.
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
 * Function Name  @fn            cellular_get_tickcount
 ****************************************************************************************/
uint32_t cellular_get_tickcount(void)
{
    uint32_t ret = 0;
#if BSP_CFG_RTOS_USED == (1)
    ret = xTaskGetTickCount();
#elif BSP_CFG_RTOS_USED == (5)
    ret = tx_time_get();
#endif

    return ret;
}
/**********************************************************************************************************************
 * End of function cellular_get_tickcount
 *********************************************************************************************************************/

/*****************************************************************************************
 * Function Name  @fn            cellular_ms_to_ticks
 ****************************************************************************************/
uint32_t cellular_ms_to_ticks(const uint32_t time_ms)
{
    uint64_t tick_rate_hz = 1000U;
    uint64_t ticks        = 0U;
#if BSP_CFG_RTOS_USED == (1)
    tick_rate_hz = (uint64_t)configTICK_RATE_HZ;
#elif BSP_CFG_RTOS_USED == (5)
    tick_rate_hz = (uint64_t)TX_TIMER_TICKS_PER_SECOND;
#endif

    /* Round up so that the time is never shorter than requested.
     * Any time_ms other than 0 gives at least 1 tick. */
    ticks = (((uint64_t)time_ms * tick_rate_hz) + 999U) / 1000U;

    if (ticks > 0xffffffffU)
    {
        ticks = 0xffffffffU;
    }

    return (uint32_t)ticks;
}
/**********************************************************************************************************************
 * End of function cellular_ms_to_ticks
 *********************************************************************************************************************/

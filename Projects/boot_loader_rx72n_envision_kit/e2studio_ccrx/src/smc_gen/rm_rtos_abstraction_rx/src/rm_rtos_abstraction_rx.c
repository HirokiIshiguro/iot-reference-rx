/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
#include <stdint.h>
#include <stddef.h>

#include "platform.h"
#include "rm_rtos_abstraction_rx_if.h"

static rm_rtos_abstraction_sleep_task_t g_rm_rtos_abstraction_sleep_task = NULL;

#ifndef BSP_CFG_RTOS_USED
#error "BSP_CFG_RTOS_USED must be defined by r_bsp before using rm_rtos_abstraction_rx."
#endif

rm_rtos_abstraction_err_t RM_RTOS_ABSTRACTION_SetSleepTask(rm_rtos_abstraction_sleep_task_t p_sleep_task)
{
    g_rm_rtos_abstraction_sleep_task = p_sleep_task;
    return RM_RTOS_ABSTRACTION_SUCCESS;
}

rm_rtos_abstraction_err_t RM_RTOS_ABSTRACTION_SleepTask(rm_rtos_abstraction_task_id_t task_id)
{
    if (NULL != g_rm_rtos_abstraction_sleep_task)
    {
        g_rm_rtos_abstraction_sleep_task(task_id);
        return RM_RTOS_ABSTRACTION_SUCCESS;
    }

#if (BSP_CFG_RTOS_USED == RM_RTOS_ABSTRACTION_RTOS_NONE)
    return RM_RTOS_ABSTRACTION_SUCCESS;
#else
    (void) task_id;
    return RM_RTOS_ABSTRACTION_ERR_NOT_CONFIGURED;
#endif
}

uint32_t RM_RTOS_ABSTRACTION_GetRtosUsed(void)
{
    return (uint32_t) BSP_CFG_RTOS_USED;
}

uint32_t RM_RTOS_ABSTRACTION_GetVersion(void)
{
    return (RM_RTOS_ABSTRACTION_RX_VERSION_MAJOR << 16) | RM_RTOS_ABSTRACTION_RX_VERSION_MINOR;
}

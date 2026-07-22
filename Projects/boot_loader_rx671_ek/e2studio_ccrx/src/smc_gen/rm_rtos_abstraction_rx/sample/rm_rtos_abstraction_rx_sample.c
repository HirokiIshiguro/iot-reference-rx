/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
#include "rm_rtos_abstraction_rx_if.h"

static void sample_sleep_task(rm_rtos_abstraction_task_id_t task_id);

void rm_rtos_abstraction_rx_sample(void)
{
    uint32_t rtos_used = RM_RTOS_ABSTRACTION_GetRtosUsed();

    (void) rtos_used;
    (void) RM_RTOS_ABSTRACTION_SetSleepTask(sample_sleep_task);
    (void) RM_RTOS_ABSTRACTION_SleepTask(0u);
}

static void sample_sleep_task(rm_rtos_abstraction_task_id_t task_id)
{
    (void) task_id;
}

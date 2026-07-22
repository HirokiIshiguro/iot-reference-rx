/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
#ifndef RM_RTOS_ABSTRACTION_RX_IF_H
#define RM_RTOS_ABSTRACTION_RX_IF_H

#include <stdint.h>
#include "rm_rtos_abstraction_rx_config.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RM_RTOS_ABSTRACTION_RX_VERSION_MAJOR    (1u)
#define RM_RTOS_ABSTRACTION_RX_VERSION_MINOR    (0u)

#define RM_RTOS_ABSTRACTION_RTOS_NONE           (0u)
#define RM_RTOS_ABSTRACTION_RTOS_FREERTOS       (1u)
#define RM_RTOS_ABSTRACTION_RTOS_EMBOS          (2u)
#define RM_RTOS_ABSTRACTION_RTOS_MICRIUM        (3u)
#define RM_RTOS_ABSTRACTION_RTOS_RENESAS        (4u)
#define RM_RTOS_ABSTRACTION_RTOS_AZURE          (5u)

typedef enum e_rm_rtos_abstraction_err
{
    RM_RTOS_ABSTRACTION_SUCCESS = 0,
    RM_RTOS_ABSTRACTION_ERR_INVALID_ARGUMENT,
    RM_RTOS_ABSTRACTION_ERR_NOT_CONFIGURED
} rm_rtos_abstraction_err_t;

typedef uint32_t rm_rtos_abstraction_task_id_t;
typedef void (* rm_rtos_abstraction_sleep_task_t)(rm_rtos_abstraction_task_id_t task_id);

rm_rtos_abstraction_err_t RM_RTOS_ABSTRACTION_SetSleepTask(rm_rtos_abstraction_sleep_task_t p_sleep_task);
rm_rtos_abstraction_err_t RM_RTOS_ABSTRACTION_SleepTask(rm_rtos_abstraction_task_id_t task_id);
uint32_t RM_RTOS_ABSTRACTION_GetRtosUsed(void);
uint32_t RM_RTOS_ABSTRACTION_GetVersion(void);

#ifdef __cplusplus
}
#endif

#endif /* RM_RTOS_ABSTRACTION_RX_IF_H */

/*
 * whd_rtos - WHD RTOS abstraction (cyabs_rtos) over FreeRTOS for the EK-RX671.
 *
 * WHD calls the Cypress cy_rtos_* abstraction for its worker thread, the SDPCM
 * semaphores and timing. This maps that abstraction onto the project's FreeRTOS.
 * Only the subset WHD actually references is implemented; missing entry points
 * surface as link errors if a future WHD path needs them.
 */
#include <stdint.h>
#include <stdbool.h>

#include "whd.h"
#include "cy_result.h"
#include "cyabs_rtos.h"

#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

static const uint32_t ms_to_tick_ratio = (uint32_t)(1000U / configTICK_RATE_HZ);
static volatile bool g_whd_port_thread_context_irq;

void whd_port_rtos_set_thread_context_irq(bool enabled)
{
    g_whd_port_thread_context_irq = enabled;
}

cy_rslt_t cy_rtos_create_thread(cy_thread_t *thread, cy_thread_entry_fn_t entry_function,
                                const char *name, void *stack, uint32_t stack_size,
                                cy_thread_priority_t priority, cy_thread_arg_t arg)
{
    signed portBASE_TYPE result;

    (void)stack;
    result = xTaskCreate((TaskFunction_t)entry_function, name,
                         (uint16_t)(stack_size / sizeof(portSTACK_TYPE)), (void *)arg,
                         (UBaseType_t)priority, (TaskHandle_t *)thread);
    return (result == (signed portBASE_TYPE)pdPASS) ? CY_RSLT_SUCCESS : CY_RTOS_NO_MEMORY;
}

cy_rslt_t cy_rtos_exit_thread(void)
{
    vTaskDelete(NULL);
    return CY_RSLT_SUCCESS;
}

cy_rslt_t cy_rtos_terminate_thread(cy_thread_t *thread)
{
    vTaskDelete((TaskHandle_t)*thread);
    return CY_RSLT_SUCCESS;
}

cy_rslt_t cy_rtos_join_thread(cy_thread_t *thread)
{
    (void)thread;
    return CY_RSLT_SUCCESS;
}

cy_rslt_t cy_rtos_init_semaphore(cy_semaphore_t *semaphore, uint32_t maxcount, uint32_t initcount)
{
    *semaphore = xSemaphoreCreateCounting(maxcount, initcount);
    return (*semaphore == NULL) ? CY_RTOS_GENERAL_ERROR : CY_RSLT_SUCCESS;
}

cy_rslt_t cy_rtos_get_semaphore(cy_semaphore_t *semaphore, uint32_t timeout_ms, bool will_set_in_isr)
{
    (void)will_set_in_isr;

    if (*semaphore == NULL)
    {
        return CY_RTOS_BAD_PARAM;
    }
    if (timeout_ms == CY_RTOS_NEVER_TIMEOUT)
    {
        (void)xSemaphoreTake((SemaphoreHandle_t)*semaphore, portMAX_DELAY);
        return CY_RSLT_SUCCESS;
    }
    if (pdTRUE != xSemaphoreTake((SemaphoreHandle_t)*semaphore,
                                 (TickType_t)(timeout_ms / ms_to_tick_ratio)))
    {
        return CY_RTOS_TIMEOUT;
    }
    return CY_RSLT_SUCCESS;
}

cy_rslt_t cy_rtos_set_semaphore(cy_semaphore_t *semaphore, bool called_from_ISR)
{
    BaseType_t result;
    BaseType_t higher_priority_task_woken = pdFALSE;

    if (*semaphore == NULL)
    {
        return CY_RTOS_GENERAL_ERROR;
    }
    if (called_from_ISR && !g_whd_port_thread_context_irq)
    {
        result = xSemaphoreGiveFromISR((SemaphoreHandle_t)*semaphore, &higher_priority_task_woken);
        portYIELD_FROM_ISR(higher_priority_task_woken);
    }
    else
    {
        result = xSemaphoreGive((SemaphoreHandle_t)*semaphore);
    }
    return (result == pdPASS) ? CY_RSLT_SUCCESS : CY_RSLT_TYPE_FATAL;
}

cy_rslt_t cy_rtos_deinit_semaphore(cy_semaphore_t *semaphore)
{
    if (*semaphore != NULL)
    {
        vSemaphoreDelete((SemaphoreHandle_t)*semaphore);
        *semaphore = NULL;
    }
    return CY_RSLT_SUCCESS;
}

cy_rslt_t cy_rtos_get_time(cy_time_t *tval)
{
    *tval = (cy_time_t)(xTaskGetTickCount() * ms_to_tick_ratio);
    return CY_RSLT_SUCCESS;
}

cy_rslt_t cy_rtos_delay_milliseconds(cy_time_t num_ms)
{
    if ((num_ms / ms_to_tick_ratio) != 0U)
    {
        vTaskDelay((TickType_t)(num_ms / ms_to_tick_ratio));
    }
    return CY_RSLT_SUCCESS;
}

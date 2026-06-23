/*
 * cyhal_sdhc - WHD SDIO bus backend (cyhal_sdio) for the EK-RX671 / Type 1YN.
 *
 * Implements the cyhal_sdio contract WHD's whd_bus_sdio driver calls, on top of
 * the project's proven polled SDHI host (sdio_host.c / r_sdio_rx). WHD owns
 * everything above the raw transport: it programs F1 enable, the Broadcom
 * backplane window, the firmware download and the SDPCM/scan flow itself through
 * cyhal_sdio_send_cmd (CMD52) and cyhal_sdio_bulk_transfer (CMD53). So this file
 * is a thin shim - the heavy lifting was de-risked in increments 4a-4c.
 *
 * The host data path is synchronous today. WHD receives SDPCM control/event
 * traffic by having the SDHI SDIO card interrupt (SDACI / IOIRQ from DAT1)
 * wake the WHD thread; the legacy FreeRTOS-timer soft IRQ remains as a bring-up
 * fallback when WHD_SDIO_USE_SDHI_IRQ is disabled.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include "whd.h"
#include "cy_result.h"
#include "cyhal_sdio.h"
#include "cyhal_gpio.h"

#include "FreeRTOS.h"
#include "task.h"
#include "timers.h"

#include "platform.h"
#include "debug_uart.h"
#include "r_sdhi_rx_if.h"
#include "sdio_host.h"
#include "whd_join_config.h"
#include "whd_port.h"

#define SDIOD_CCCR_INTPEND              (0x05U)
#define INTR_STATUS_FUNC1               (0x02U)
#define INTR_STATUS_FUNC2               (0x04U)
#define SDIO_SDHI_IRQ_TASK_STACK_WORDS  (1024U)
#define SDIO_SDHI_IRQ_TASK_PRIORITY     (tskIDLE_PRIORITY + 3U)
#define SDIO_DEBUG_TRACE_DEPTH          (32U)
#define SDIO_DEBUG_TRACE_MASK           (SDIO_DEBUG_TRACE_DEPTH - 1U)
#define SDIO_DEBUG_TRACE_CMD52          (52U)
#define SDIO_DEBUG_TRACE_CMD53          (53U)

static cyhal_sdio_irq_handler_t g_sdio_irq_handler;
static void * g_sdio_irq_handler_arg;
static TimerHandle_t g_sdio_softirq_timer;
static TaskHandle_t g_sdio_sdhi_irq_task;
static volatile bool g_sdio_softirq_enabled;
static volatile bool g_sdio_sdhi_irq_enabled;
static volatile bool g_sdio_sdhi_irq_latched;
static uint32_t g_sdio_sdhi_irq_enable_count;
static uint32_t g_cmd52_fail_log_count;
static uint32_t g_cmd53_fail_log_count;
static bool g_pre_cmd53_clocks_ready;
static volatile bool g_sdio_bus_busy;

volatile uint32_t g_whd_sdio_sdhi_irq_count;
volatile uint32_t g_whd_sdio_sdhi_irq_ignored_count;
volatile uint32_t g_whd_sdio_sdhi_irq_rearm_count;
volatile uint32_t g_whd_sdio_sdhi_irq_last_status;
volatile uint32_t g_whd_sdio_sdhi_irq_notify_count;
volatile uint32_t g_whd_sdio_sdhi_irq_task_count;
volatile uint32_t g_whd_sdio_sdhi_irq_enable_count;
volatile uint32_t g_whd_sdio_sdhi_irq_deferred_enable_count;
volatile uint32_t g_whd_sdio_softirq_notify_count;
volatile uint32_t g_whd_sdio_softirq_pending_count;
volatile uint32_t g_whd_sdio_irq_task_state;
volatile uint32_t g_whd_sdio_irq_handler_enter_count;
volatile uint32_t g_whd_sdio_irq_handler_exit_count;
volatile uint32_t g_whd_sdio_irq_handler_ptr_last;
volatile uint32_t g_whd_sdio_irq_handler_arg_last;
volatile uint32_t g_whd_sdio_irq_handler_event_last;
volatile uint32_t g_whd_sdio_cmd52_enter_count;
volatile uint32_t g_whd_sdio_cmd52_exit_count;
volatile uint32_t g_whd_sdio_cmd52_fail_count;
volatile uint32_t g_whd_sdio_cmd52_last_write;
volatile uint32_t g_whd_sdio_cmd52_last_function;
volatile uint32_t g_whd_sdio_cmd52_last_address;
volatile uint32_t g_whd_sdio_cmd52_last_io;
volatile uint32_t g_whd_sdio_cmd52_last_ok;
volatile uint32_t g_whd_sdio_cmd52_fail_last_s1;
volatile uint32_t g_whd_sdio_cmd52_fail_last_s2;
volatile uint32_t g_whd_sdio_cmd53_enter_count;
volatile uint32_t g_whd_sdio_cmd53_exit_count;
volatile uint32_t g_whd_sdio_cmd53_fail_count;
volatile uint32_t g_whd_sdio_cmd53_last_write;
volatile uint32_t g_whd_sdio_cmd53_last_function;
volatile uint32_t g_whd_sdio_cmd53_last_address;
volatile uint32_t g_whd_sdio_cmd53_last_increment;
volatile uint32_t g_whd_sdio_cmd53_last_block_mode;
volatile uint32_t g_whd_sdio_cmd53_last_count;
volatile uint32_t g_whd_sdio_cmd53_last_length;
volatile uint32_t g_whd_sdio_cmd53_last_data_ptr;
volatile uint32_t g_whd_sdio_cmd53_last_wait_count;
volatile uint32_t g_whd_sdio_cmd53_last_r5;
volatile uint32_t g_whd_sdio_cmd53_last_ok;
volatile uint32_t g_whd_sdio_cmd53_last_result;
volatile uint32_t g_whd_sdio_cmd53_last_data0;
volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_retry_count;
volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_recovered_count;
volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_retry_fail_count;
volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_retry_abort_count;
volatile uint32_t g_whd_sdio_cmd53_fail_last_stage;
volatile uint32_t g_whd_sdio_cmd53_fail_last_s1;
volatile uint32_t g_whd_sdio_cmd53_fail_last_s2;
volatile uint32_t g_whd_sdio_cmd53_fail_last_er1;
volatile uint32_t g_whd_sdio_cmd53_fail_last_er2;
volatile uint32_t g_whd_sdio_cmd53_fail_last_diag_r5;
volatile uint32_t g_whd_sdio_cmd53_fail_last_data0;
volatile uint32_t g_whd_sdio_cmd53_f2_write_enter_count;
volatile uint32_t g_whd_sdio_cmd53_f2_write_ok_count;
volatile uint32_t g_whd_sdio_cmd53_f2_write_fail_count;
volatile uint32_t g_whd_sdio_cmd53_f2_write_byte_count;
volatile uint32_t g_whd_sdio_cmd53_f2_write_block_count;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_address;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_increment;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_block_mode;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_count;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_length;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_r5;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_result;
volatile uint32_t g_whd_sdio_cmd53_f2_write_last_data0;
volatile uint32_t g_whd_sdio_cmd53_f2_read_enter_count;
volatile uint32_t g_whd_sdio_cmd53_f2_read_ok_count;
volatile uint32_t g_whd_sdio_cmd53_f2_read_fail_count;
volatile uint32_t g_whd_sdio_cmd53_f2_read_byte_count;
volatile uint32_t g_whd_sdio_cmd53_f2_read_block_count;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_address;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_increment;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_block_mode;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_count;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_length;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_r5;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_result;
volatile uint32_t g_whd_sdio_cmd53_f2_read_last_data0;
volatile uint32_t g_whd_sdio_debug_break_count;
volatile uint32_t g_whd_sdio_debug_break_reason;
volatile uint32_t g_whd_sdio_trace_index;
volatile uint32_t g_whd_sdio_trace_frozen;
volatile uint32_t g_whd_sdio_trace[SDIO_DEBUG_TRACE_DEPTH][9];

void whd_sdio_debug_break_hook(uint32_t reason)
{
    g_whd_sdio_debug_break_reason = reason;
    g_whd_sdio_debug_break_count++;
}

static void sdio_debug_trace(uint32_t kind, uint32_t write, uint32_t function,
                             uint32_t address, uint32_t count_or_value,
                             uint32_t length_or_io, uint32_t r5,
                             uint32_t result, uint32_t data0)
{
    uint32_t slot = g_whd_sdio_trace_index & SDIO_DEBUG_TRACE_MASK;

    if (0U != g_whd_sdio_trace_frozen)
    {
        return;
    }

    g_whd_sdio_trace[slot][0] = kind;
    g_whd_sdio_trace[slot][1] = write;
    g_whd_sdio_trace[slot][2] = function;
    g_whd_sdio_trace[slot][3] = address;
    g_whd_sdio_trace[slot][4] = count_or_value;
    g_whd_sdio_trace[slot][5] = length_or_io;
    g_whd_sdio_trace[slot][6] = r5;
    g_whd_sdio_trace[slot][7] = result;
    g_whd_sdio_trace[slot][8] = data0;
    g_whd_sdio_trace_index++;
}

static uint32_t sdio_debug_data0(const uint32_t * data, uint32_t length)
{
    const uint8_t * p = (const uint8_t *)(const void *)data;

    if ((NULL == p) || (length < 4U))
    {
        return 0U;
    }

    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static void sdio_diag_cmd53_f2_enter(bool write, uint32_t address, bool increment,
                                     bool block_mode, uint32_t count, uint32_t length)
{
    if (write)
    {
        g_whd_sdio_cmd53_f2_write_enter_count++;
        g_whd_sdio_cmd53_f2_write_last_address = address;
        g_whd_sdio_cmd53_f2_write_last_increment = increment ? 1U : 0U;
        g_whd_sdio_cmd53_f2_write_last_block_mode = block_mode ? 1U : 0U;
        g_whd_sdio_cmd53_f2_write_last_count = count;
        g_whd_sdio_cmd53_f2_write_last_length = length;
    }
    else
    {
        g_whd_sdio_cmd53_f2_read_enter_count++;
        g_whd_sdio_cmd53_f2_read_last_address = address;
        g_whd_sdio_cmd53_f2_read_last_increment = increment ? 1U : 0U;
        g_whd_sdio_cmd53_f2_read_last_block_mode = block_mode ? 1U : 0U;
        g_whd_sdio_cmd53_f2_read_last_count = count;
        g_whd_sdio_cmd53_f2_read_last_length = length;
    }
}

static void sdio_diag_cmd53_f2_exit(bool write, bool ok, bool block_mode, uint32_t count,
                                    uint32_t length, uint32_t r5, uint32_t result, uint32_t data0)
{
    if (write)
    {
        g_whd_sdio_cmd53_f2_write_last_r5 = r5;
        g_whd_sdio_cmd53_f2_write_last_result = result;
        g_whd_sdio_cmd53_f2_write_last_data0 = data0;
        if (ok)
        {
            g_whd_sdio_cmd53_f2_write_ok_count++;
            g_whd_sdio_cmd53_f2_write_byte_count += length;
            if (block_mode)
            {
                g_whd_sdio_cmd53_f2_write_block_count += count;
            }
        }
        else
        {
            g_whd_sdio_cmd53_f2_write_fail_count++;
        }
    }
    else
    {
        g_whd_sdio_cmd53_f2_read_last_r5 = r5;
        g_whd_sdio_cmd53_f2_read_last_result = result;
        g_whd_sdio_cmd53_f2_read_last_data0 = data0;
        if (ok)
        {
            g_whd_sdio_cmd53_f2_read_ok_count++;
            g_whd_sdio_cmd53_f2_read_byte_count += length;
            if (block_mode)
            {
                g_whd_sdio_cmd53_f2_read_block_count += count;
            }
        }
        else
        {
            g_whd_sdio_cmd53_f2_read_fail_count++;
        }
    }
}

static bool sdio_try_begin_bus(void)
{
    bool acquired = false;

    taskENTER_CRITICAL();
    if (!g_sdio_bus_busy)
    {
        g_sdio_bus_busy = true;
        acquired = true;
    }
    taskEXIT_CRITICAL();

    return acquired;
}

static void sdio_end_bus(void)
{
    taskENTER_CRITICAL();
    g_sdio_bus_busy = false;
    taskEXIT_CRITICAL();
}

static uint32_t sdio_begin_bus_blocking(void)
{
    uint32_t wait_count = 0U;

    while (!sdio_try_begin_bus())
    {
        wait_count++;
        taskYIELD();
    }

    return wait_count;
}

static TickType_t sdio_softirq_period_ticks(void)
{
    TickType_t ticks = pdMS_TO_TICKS(WHD_SDIO_SOFTIRQ_POLL_MS);

    if (0U == WHD_SDIO_SOFTIRQ_POLL_MS)
    {
        return 0U;
    }
    return (0U == ticks) ? 1U : ticks;
}

static void sdio_softirq_timer_callback(TimerHandle_t xTimer)
{
#if !WHD_SDIO_SOFTIRQ_ALWAYS_NOTIFY
    uint8_t pending = 0U;
#endif

    (void)xTimer;

    if (!g_sdio_softirq_enabled || (NULL == g_sdio_irq_handler))
    {
        return;
    }
#if !WHD_SDIO_SOFTIRQ_ALWAYS_NOTIFY
    if (!sdio_try_begin_bus())
    {
        return;
    }
    if (!sdio_host_cmd52_read(0U, SDIOD_CCCR_INTPEND, &pending))
    {
        sdio_end_bus();
        return;
    }
    sdio_end_bus();

    if (0U == (pending & (INTR_STATUS_FUNC1 | INTR_STATUS_FUNC2)))
    {
        return;
    }
    g_whd_sdio_softirq_pending_count++;
#endif

    g_whd_sdio_softirq_notify_count++;
    whd_port_rtos_set_thread_context_irq(true);
    g_sdio_irq_handler(g_sdio_irq_handler_arg, CYHAL_SDIO_CARD_INTERRUPT);
    whd_port_rtos_set_thread_context_irq(false);
}

static void sdio_softirq_enable(bool enable)
{
    if (0U == WHD_SDIO_SOFTIRQ_POLL_MS)
    {
        g_sdio_softirq_enabled = false;
        return;
    }

    if (NULL == g_sdio_softirq_timer)
    {
        g_sdio_softirq_timer = xTimerCreate("whd_sdio_irq", sdio_softirq_period_ticks(), pdTRUE,
                                            NULL, sdio_softirq_timer_callback);
    }

    if (NULL == g_sdio_softirq_timer)
    {
        g_sdio_softirq_enabled = false;
        return;
    }

    g_sdio_softirq_enabled = enable;
    if (enable)
    {
        (void)xTimerStart(g_sdio_softirq_timer, 0U);
    }
    else
    {
        (void)xTimerStop(g_sdio_softirq_timer, 0U);
    }
}

static sdhi_status_t sdio_sdhi_irq_callback(uint32_t sdiosts)
{
    BaseType_t higher_priority_task_woken = pdFALSE;

    g_whd_sdio_sdhi_irq_last_status = sdiosts;

    if (0U == (sdiosts & SDHI_SDIOSTS_IOIRQ))
    {
        g_whd_sdio_sdhi_irq_ignored_count++;
        return SDHI_SUCCESS;
    }

    g_whd_sdio_sdhi_irq_count++;
    g_sdio_sdhi_irq_latched = true;

    /* IOIRQ is level-like from the WLAN function's point of view. Mask it until
     * the awakened WHD thread has had a chance to drain the SDPCM interrupt
     * source; otherwise the SDHI group interrupt can immediately retrigger. */
    (void)R_SDHI_ClearSdioIntMask(SDHI_CH0, SDHI_SDIOIMSK_IOIRQ);
    (void)R_SDHI_ClearSdiostsReg(SDHI_CH0, SDHI_SDIOSTS_IOIRQ);

    if (g_sdio_sdhi_irq_enabled && (NULL != g_sdio_sdhi_irq_task))
    {
        g_whd_sdio_sdhi_irq_notify_count++;
        vTaskNotifyGiveFromISR(g_sdio_sdhi_irq_task, &higher_priority_task_woken);
        portYIELD_FROM_ISR(higher_priority_task_woken);
    }
    else
    {
        g_whd_sdio_sdhi_irq_ignored_count++;
    }

    return SDHI_SUCCESS;
}

static void sdio_sdhi_irq_task(void * pvParameters)
{
    (void)pvParameters;

    for (;;)
    {
        g_whd_sdio_irq_task_state = 1U;
        (void)ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        g_whd_sdio_irq_task_state = 2U;
        g_whd_sdio_sdhi_irq_task_count++;

        if (g_sdio_sdhi_irq_enabled && (NULL != g_sdio_irq_handler))
        {
            g_whd_sdio_irq_task_state = 3U;
            g_whd_sdio_irq_handler_ptr_last = (uint32_t)(uintptr_t)g_sdio_irq_handler;
            g_whd_sdio_irq_handler_arg_last = (uint32_t)(uintptr_t)g_sdio_irq_handler_arg;
            g_whd_sdio_irq_handler_event_last = (uint32_t)CYHAL_SDIO_CARD_INTERRUPT;
            g_whd_sdio_irq_handler_enter_count++;
            whd_port_rtos_set_thread_context_irq(true);
            g_sdio_irq_handler(g_sdio_irq_handler_arg, CYHAL_SDIO_CARD_INTERRUPT);
            whd_port_rtos_set_thread_context_irq(false);
            g_whd_sdio_irq_handler_exit_count++;
            g_whd_sdio_irq_task_state = 4U;
        }
        else
        {
            g_whd_sdio_sdhi_irq_ignored_count++;
            g_whd_sdio_irq_task_state = 5U;
        }

        /* Optionally let the WHD worker drain the SDPCM interrupt source before
         * re-enabling the level-like DAT1/IOIRQ source in SDHI. The performance
         * path keeps this at zero so RX is not quantized by the FreeRTOS tick. */
        g_whd_sdio_irq_task_state = 6U;
#if (WHD_SDIO_SDHI_IRQ_REARM_DELAY_TICKS > 0U)
        vTaskDelay((TickType_t)WHD_SDIO_SDHI_IRQ_REARM_DELAY_TICKS);
#endif

        if (g_sdio_sdhi_irq_enabled && g_sdio_sdhi_irq_latched)
        {
            g_whd_sdio_irq_task_state = 7U;
            g_sdio_sdhi_irq_latched = false;
            (void)R_SDHI_ClearSdiostsReg(SDHI_CH0, SDHI_SDIOSTS_IOIRQ);
            (void)R_SDHI_SetSdioIntMask(SDHI_CH0, SDHI_SDIOIMSK_IOIRQ);
            g_whd_sdio_sdhi_irq_rearm_count++;
        }
        g_whd_sdio_irq_task_state = 8U;
    }
}

static void sdio_sdhi_irq_rearm_after_bus(void)
{
#if WHD_SDIO_USE_SDHI_IRQ
    if (g_sdio_sdhi_irq_enabled && g_sdio_sdhi_irq_latched)
    {
        g_sdio_sdhi_irq_latched = false;
        (void)R_SDHI_ClearSdiostsReg(SDHI_CH0, SDHI_SDIOSTS_IOIRQ);
        (void)R_SDHI_SetSdioIntMask(SDHI_CH0, SDHI_SDIOIMSK_IOIRQ);
        g_whd_sdio_sdhi_irq_rearm_count++;
    }
#endif
}

static void sdio_sdhi_irq_enable(bool enable)
{
#if WHD_SDIO_USE_SDHI_IRQ
    if (enable)
    {
        g_sdio_sdhi_irq_enable_count++;
        g_whd_sdio_sdhi_irq_enable_count = g_sdio_sdhi_irq_enable_count;

#if WHD_SDIO_SDHI_IRQ_DEFER_FIRST_ENABLE
        if (1U == g_sdio_sdhi_irq_enable_count)
        {
            g_sdio_sdhi_irq_enabled = false;
            g_sdio_sdhi_irq_latched = false;
            g_whd_sdio_sdhi_irq_deferred_enable_count++;
            (void)R_SDHI_IntSdioCallback(SDHI_CH0, sdio_sdhi_irq_callback);
            (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDIOMD, SDHI_SDIOMD_INTEN);
            (void)R_SDHI_ClearSdioIntMask(SDHI_CH0, SDHI_SDIOIMSK_IOIRQ);
            (void)R_SDHI_ClearSdiostsReg(SDHI_CH0, SDHI_SDIOSTS_IOIRQ);
            return;
        }
#endif

        if (NULL == g_sdio_sdhi_irq_task)
        {
            (void)xTaskCreate(sdio_sdhi_irq_task, "sdio_irq",
                              SDIO_SDHI_IRQ_TASK_STACK_WORDS, NULL,
                              SDIO_SDHI_IRQ_TASK_PRIORITY, &g_sdio_sdhi_irq_task);
        }

        if (NULL == g_sdio_sdhi_irq_task)
        {
            g_sdio_sdhi_irq_enabled = false;
            return;
        }

        g_sdio_sdhi_irq_latched = false;
        g_sdio_sdhi_irq_enabled = true;
        (void)R_SDHI_IntSdioCallback(SDHI_CH0, sdio_sdhi_irq_callback);
        (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDIOMD, SDHI_SDIOMD_INTEN);
        (void)R_SDHI_ClearSdiostsReg(SDHI_CH0, SDHI_SDIOSTS_IOIRQ);
        (void)R_SDHI_SetSdioIntMask(SDHI_CH0, SDHI_SDIOIMSK_IOIRQ);
        (void)R_SDHI_EnableIcuInt(SDHI_CH0, SDHI_HWINT_ACCESS_CD);
    }
    else
    {
        g_sdio_sdhi_irq_enabled = false;
        g_sdio_sdhi_irq_latched = false;
        (void)R_SDHI_ClearSdioIntMask(SDHI_CH0, SDHI_SDIOIMSK_IOIRQ);
        (void)R_SDHI_DisableIcuInt(SDHI_CH0, SDHI_HWINT_ACCESS_CD);
        (void)R_SDHI_IntSdioCallback(SDHI_CH0, NULL);
    }
#else
    (void)enable;
#endif
}

static void sdio_log_cmd52_fail(bool write, uint8_t function, uint32_t address, uint8_t io, uint32_t r5)
{
    uint32_t s1 = 0U;
    uint32_t s2 = 0U;
    char line[160];
    char * p = line;

    g_whd_sdio_cmd52_fail_count++;
    if (g_cmd52_fail_log_count >= WHD_SDIO_DIAG_FAIL_LIMIT)
    {
        return;
    }
    g_cmd52_fail_log_count++;

    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS1, &s1);
    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, &s2);
    g_whd_sdio_cmd52_fail_last_s1 = s1;
    g_whd_sdio_cmd52_fail_last_s2 = s2;

    p = append_text(p, "sdio cmd52 NG dir=");
    p = append_text(p, write ? "W" : "R");
    p = append_text(p, " f=");
    p = append_dec32(p, function);
    p = append_text(p, " a=");
    p = append_hex32(p, address);
    p = append_text(p, " io=");
    p = append_hex8(p, io);
    p = append_text(p, " r5=");
    p = append_hex32(p, r5);
    p = append_text(p, " s1=");
    p = append_hex32(p, s1);
    p = append_text(p, " s2=");
    p = append_hex32(p, s2);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void sdio_log_cmd53_fail(bool write, uint8_t function, uint32_t address, bool increment,
                                bool block_mode, uint32_t count, uint32_t r5)
{
    uint8_t stage = 0U;
    uint32_t s1 = 0U;
    uint32_t s2 = 0U;
    uint32_t er1 = 0U;
    uint32_t er2 = 0U;
    uint32_t diag_r5 = 0U;
    uint32_t data0 = 0U;
    char line[240];
    char * p = line;

    g_whd_sdio_cmd53_fail_count++;
    if (g_cmd53_fail_log_count >= WHD_SDIO_DIAG_FAIL_LIMIT)
    {
        return;
    }
    g_cmd53_fail_log_count++;

    sdio_host_cmd53_diag_ext(&stage, &s1, &s2, &er1, &er2, &diag_r5, &data0);
    g_whd_sdio_cmd53_fail_last_stage = stage;
    g_whd_sdio_cmd53_fail_last_s1 = s1;
    g_whd_sdio_cmd53_fail_last_s2 = s2;
    g_whd_sdio_cmd53_fail_last_er1 = er1;
    g_whd_sdio_cmd53_fail_last_er2 = er2;
    g_whd_sdio_cmd53_fail_last_diag_r5 = diag_r5;
    g_whd_sdio_cmd53_fail_last_data0 = data0;

    p = append_text(p, "sdio cmd53 NG dir=");
    p = append_text(p, write ? "W" : "R");
    p = append_text(p, " f=");
    p = append_dec32(p, function);
    p = append_text(p, " a=");
    p = append_hex32(p, address);
    p = append_text(p, " inc=");
    p = append_dec32(p, increment ? 1U : 0U);
    p = append_text(p, " blk=");
    p = append_dec32(p, block_mode ? 1U : 0U);
    p = append_text(p, " cnt=");
    p = append_dec32(p, count);
    p = append_text(p, " r5=");
    p = append_hex32(p, r5);
    p = append_text(p, " st=");
    p = append_dec32(p, stage);
    p = append_text(p, " s1=");
    p = append_hex32(p, s1);
    p = append_text(p, " s2=");
    p = append_hex32(p, s2);
    p = append_text(p, " er1=");
    p = append_hex32(p, er1);
    p = append_text(p, " er2=");
    p = append_hex32(p, er2);
    p = append_text(p, " dr5=");
    p = append_hex32(p, diag_r5);
    p = append_text(p, " d0=");
    p = append_hex32(p, data0);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static bool sdio_prepare_pre_cmd53(uint8_t function)
{
#if WHD_SDIO_PRE_CMD53_CLOCKS
    uint8_t csr = 0U;
    uint8_t slp = 0U;
    bool ok;
    char line[96];
    char * p = line;

    if ((1U != function) || g_pre_cmd53_clocks_ready)
    {
        return true;
    }

    ok = sdio_host_brcm_force_clocks(&csr) && sdio_host_request_kso(&slp);
    p = append_text(p, ok ? "sdio pre-cmd53 ok csr=" : "sdio pre-cmd53 NG csr=");
    p = append_hex8(p, csr);
    p = append_text(p, " slp=");
    p = append_hex8(p, slp);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);

    g_pre_cmd53_clocks_ready = ok;
    return ok;
#else
    (void)function;
    return true;
#endif
}

/* Bring up the SDHI host and enumerate the card into the transfer state
 * (CMD0/CMD5/CMD3/CMD7), then open the r_sdio_rx protocol layer over the CMD52
 * host. WHD drives F1 enable / bus width / backplane / firmware download after
 * this through send_cmd + bulk_transfer. The SDHI pins are fixed by the board
 * pin configuration (corrected PORTD map), so the pin arguments are ignored. */
cy_rslt_t cyhal_sdio_init(cyhal_sdio_t *obj, cyhal_gpio_t cmd, cyhal_gpio_t clk,
                          cyhal_gpio_t data0, cyhal_gpio_t data1,
                          cyhal_gpio_t data2, cyhal_gpio_t data3)
{
    uint32_t r4 = 0U;
    uint8_t func = 0U;
    uint16_t rca = 0U;

    (void)obj;
    (void)cmd;
    (void)clk;
    (void)data0;
    (void)data1;
    (void)data2;
    (void)data3;

    if (!sdio_host_init())
    {
        return CYHAL_SDIO_RSLT_ERR_CLOCK;
    }
    if (!sdio_host_first_contact(&r4, &func))
    {
        return CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_CMD_TIMEOUT);
    }
    if (!sdio_host_select_card(&rca))
    {
        return CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_NO_SP_ERRORS);
    }
    if (!sdio_host_protocol_open())
    {
        return CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_NO_SP_ERRORS);
    }
    return CY_RSLT_SUCCESS;
}

void cyhal_sdio_free(cyhal_sdio_t *obj)
{
    (void)obj;
}

/* Host-side bus configuration: 4-bit data and run clock - the proven
 * pre-data-phase setup. WHD programs function block sizes during its bus init,
 * and cyhal_sdio_send_cmd mirrors those writes into the host-side block-size
 * cache, so we do not pre-program block size here. */
cy_rslt_t cyhal_sdio_configure(cyhal_sdio_t *obj, const cyhal_sdio_cfg_t *config)
{
    (void)obj;

    if (NULL == config)
    {
        return CYHAL_SDIO_RSLT_ERR_BAD_PARAM;
    }

    (void)sdio_host_set_high_speed();
    (void)sdio_host_set_bus_4bit();
    (void)sdio_host_set_run_clock();
    return CY_RSLT_SUCCESS;
}

/* WHD issues only CMD52 (IO_RW_DIRECT) here; CMD0/3/5/7 happened in init. The
 * argument is the standard SDIO CMD52 layout: func[30:28], addr[25:9], data[7:0].
 * The response carries the R5 data byte. */
cy_rslt_t cyhal_sdio_send_cmd(const cyhal_sdio_t *obj, cyhal_transfer_t direction,
                              cyhal_sdio_command_t command, uint32_t argument, uint32_t *response)
{
    uint8_t function = (uint8_t)((argument >> 28) & 0x07U);
    uint32_t address = (argument >> 9) & 0x1FFFFU;
    uint8_t io = (uint8_t)(argument & 0xFFU);
    bool ok;

    (void)obj;

    if (NULL != response)
    {
        *response = 0UL;
    }

    /* CMD0/CMD3/CMD5/CMD7 are handled in cyhal_sdio_init(); ignore them here the
     * way the WHD bus driver expects. */
    if (CYHAL_SDIO_CMD_IO_RW_DIRECT != command)
    {
        return CY_RSLT_SUCCESS;
    }

    if (CYHAL_WRITE == direction)
    {
        uint8_t value = io;

        g_whd_sdio_cmd52_enter_count++;
        g_whd_sdio_cmd52_last_write = 1U;
        g_whd_sdio_cmd52_last_function = function;
        g_whd_sdio_cmd52_last_address = address;
        g_whd_sdio_cmd52_last_io = io;
        (void)sdio_begin_bus_blocking();
        ok = sdio_host_cmd52_write(function, address, value, &io);
        sdio_end_bus();
        sdio_sdhi_irq_rearm_after_bus();
        g_whd_sdio_cmd52_last_io = io;
        g_whd_sdio_cmd52_last_ok = ok ? 1U : 0U;
        g_whd_sdio_cmd52_exit_count++;
        if (ok)
        {
            /* Keep the host block-size cache in sync with the per-function
             * block-size registers WHD programs here (notably F2), so block-mode
             * CMD53 on those functions is not rejected for a zero cached size. */
            sdio_host_note_cmd52_write(function, address, value);
        }
    }
    else
    {
        g_whd_sdio_cmd52_enter_count++;
        g_whd_sdio_cmd52_last_write = 0U;
        g_whd_sdio_cmd52_last_function = function;
        g_whd_sdio_cmd52_last_address = address;
        g_whd_sdio_cmd52_last_io = io;
        (void)sdio_begin_bus_blocking();
        ok = sdio_host_cmd52_read(function, address, &io);
        sdio_end_bus();
        sdio_sdhi_irq_rearm_after_bus();
        g_whd_sdio_cmd52_last_io = io;
        g_whd_sdio_cmd52_last_ok = ok ? 1U : 0U;
        g_whd_sdio_cmd52_exit_count++;
    }

    sdio_debug_trace(SDIO_DEBUG_TRACE_CMD52, (CYHAL_WRITE == direction) ? 1U : 0U,
                     function, address, (uint32_t)(argument & 0xFFU),
                     (uint32_t)io, (uint32_t)io, ok ? CY_RSLT_SUCCESS :
                     CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_CMD_TIMEOUT), 0U);

    if (NULL != response)
    {
        *response = (uint32_t)io;
    }
    if (!ok)
    {
        sdio_log_cmd52_fail((CYHAL_WRITE == direction), function, address, io, (uint32_t)io);
    }
    return ok ? CY_RSLT_SUCCESS : CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_CMD_TIMEOUT);
}

/* CMD53 bulk transfer. Decode the SDIO CMD53 argument and dispatch to the raw
 * CMD53 host. WHD programs the Broadcom backplane window (SBADDR*) via CMD52
 * beforehand, so this issues the CMD53 verbatim. Byte-mode count 0 means 512. */
cy_rslt_t cyhal_sdio_bulk_transfer(cyhal_sdio_t *obj, cyhal_transfer_t direction, uint32_t argument,
                                   const uint32_t *data, uint16_t length, uint32_t *response)
{
    bool write = (CYHAL_WRITE == direction);
    uint8_t function = (uint8_t)((argument >> 28) & 0x07U);
    uint32_t address = (argument >> 9) & 0x1FFFFU;
    bool block_mode = (0U != ((argument >> 27) & 0x01U));
    bool increment = (0U != ((argument >> 26) & 0x01U));
    uint32_t count = argument & 0x1FFU; /* bytes (byte mode) or blocks (block mode) */
    uint32_t wait_count;
    uint32_t r5 = 0U;
    uint32_t data0 = 0U;
    uint32_t result = 0U;
    bool ok;

    (void)obj;
    (void)length;

    if (NULL != response)
    {
        *response = 0UL;
    }

    if ((!block_mode) && (0U == count))
    {
        count = 512U; /* byte-mode count field of 0 means 512 bytes */
    }

    g_whd_sdio_cmd53_enter_count++;
    g_whd_sdio_cmd53_last_write = write ? 1U : 0U;
    g_whd_sdio_cmd53_last_function = function;
    g_whd_sdio_cmd53_last_address = address;
    g_whd_sdio_cmd53_last_increment = increment ? 1U : 0U;
    g_whd_sdio_cmd53_last_block_mode = block_mode ? 1U : 0U;
    g_whd_sdio_cmd53_last_count = count;
    g_whd_sdio_cmd53_last_length = length;
    g_whd_sdio_cmd53_last_data_ptr = (uint32_t)(uintptr_t)data;
    g_whd_sdio_cmd53_last_result = 0U;
    g_whd_sdio_cmd53_last_data0 = 0U;
    if (2U == function)
    {
        sdio_diag_cmd53_f2_enter(write, address, increment, block_mode, count, length);
    }

    wait_count = sdio_begin_bus_blocking();
    g_whd_sdio_cmd53_last_wait_count = wait_count;
    if (!sdio_prepare_pre_cmd53(function))
    {
        sdio_end_bus();
        sdio_sdhi_irq_rearm_after_bus();
        g_whd_sdio_cmd53_last_ok = 0U;
        result = CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_CMD_TIMEOUT);
        g_whd_sdio_cmd53_last_result = result;
        g_whd_sdio_cmd53_exit_count++;
        if (2U == function)
        {
            sdio_diag_cmd53_f2_exit(write, false, block_mode, count, length, 0U, result, 0U);
        }
        sdio_debug_trace(SDIO_DEBUG_TRACE_CMD53, write ? 1U : 0U, function, address,
                         count, length, 0U, g_whd_sdio_cmd53_last_result, 0U);
        return CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_CMD_TIMEOUT);
    }

    ok = sdio_host_cmd53(write, function, address, increment, block_mode,
                         (uint8_t *)data, count, &r5);
#if (WHD_SDIO_CMD53_F2_BYTE_READ_RETRY > 0U)
    if ((!ok) && (!write) && (2U == function) && (!block_mode))
    {
        uint32_t retry;

        for (retry = 0U; retry < WHD_SDIO_CMD53_F2_BYTE_READ_RETRY; retry++)
        {
            g_whd_sdio_cmd53_f2_byte_read_retry_count++;
#if WHD_SDIO_CMD53_F2_BYTE_READ_ABORT_ON_RETRY
            if (sdio_host_abort_function(function))
            {
                g_whd_sdio_cmd53_f2_byte_read_retry_abort_count++;
            }
#endif
            R_BSP_SoftwareDelay(WHD_SDIO_CMD53_F2_BYTE_READ_RETRY_DELAY_US, BSP_DELAY_MICROSECS);
            ok = sdio_host_cmd53(write, function, address, increment, block_mode,
                                 (uint8_t *)data, count, &r5);
            if (ok)
            {
                g_whd_sdio_cmd53_f2_byte_read_recovered_count++;
                break;
            }
        }
        if (!ok)
        {
            g_whd_sdio_cmd53_f2_byte_read_retry_fail_count++;
        }
    }
#endif
    data0 = sdio_debug_data0(data, length);
    sdio_end_bus();
    sdio_sdhi_irq_rearm_after_bus();

    if (NULL != response)
    {
        *response = r5;
    }
    g_whd_sdio_cmd53_last_r5 = r5;
    g_whd_sdio_cmd53_last_ok = ok ? 1U : 0U;
    result = ok ? CY_RSLT_SUCCESS : CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_DAT_TIMEOUT);
    g_whd_sdio_cmd53_last_result = result;
    g_whd_sdio_cmd53_last_data0 = data0;
    g_whd_sdio_cmd53_exit_count++;
    if (2U == function)
    {
        sdio_diag_cmd53_f2_exit(write, ok, block_mode, count, length, r5, result, data0);
    }
    sdio_debug_trace(SDIO_DEBUG_TRACE_CMD53, write ? 1U : 0U, function, address,
                     count, length, r5, g_whd_sdio_cmd53_last_result, data0);
    if (!ok)
    {
        g_whd_sdio_trace_frozen = 1U;
        sdio_log_cmd53_fail(write, function, address, increment, block_mode, count, r5);
        whd_sdio_debug_break_hook(0x53000000UL | ((write ? 1UL : 0UL) << 16) | (uint32_t)function);
    }
    return ok ? CY_RSLT_SUCCESS : CYHAL_SDIO_RSLT_ERR_FUNC_RET(CYHAL_SDIO_RET_DAT_TIMEOUT);
}

/* No DMA/async engine on this polled host: run the transfer synchronously. */
cy_rslt_t cyhal_sdio_transfer_async(cyhal_sdio_t *obj, cyhal_transfer_t direction, uint32_t argument,
                                    const uint32_t *data, uint16_t length)
{
    return cyhal_sdio_bulk_transfer(obj, direction, argument, data, length, NULL);
}

bool cyhal_sdio_is_busy(const cyhal_sdio_t *obj)
{
    (void)obj;
    return false; /* synchronous host: never busy on return */
}

cy_rslt_t cyhal_sdio_abort_async(const cyhal_sdio_t *obj)
{
    (void)obj;
    return CY_RSLT_SUCCESS;
}

/* Store WHD's in-band card-interrupt callback. By default CYHAL_SDIO_CARD_INTERRUPT
 * is driven from SDHI SDACI; the software timer path remains only as an optional
 * fallback for low-level isolation. */
void cyhal_sdio_register_irq(cyhal_sdio_t *obj, cyhal_sdio_irq_handler_t handler, void *handler_arg)
{
    (void)obj;

    g_sdio_irq_handler = handler;
    g_sdio_irq_handler_arg = handler_arg;
}

void cyhal_sdio_irq_enable(cyhal_sdio_t *obj, cyhal_sdio_irq_event_t event, bool enable)
{
    (void)obj;

    if (CYHAL_SDIO_CARD_INTERRUPT == event)
    {
#if WHD_SDIO_USE_SDHI_IRQ
        sdio_softirq_enable(false);
        sdio_sdhi_irq_enable(enable);
#else
        sdio_softirq_enable(enable);
#endif
    }
}

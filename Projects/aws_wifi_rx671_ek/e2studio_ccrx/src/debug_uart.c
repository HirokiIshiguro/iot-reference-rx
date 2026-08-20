/*
 * debug_uart - SCI6 async debug console for the EK-RX671 WHD project.
 * See debug_uart.h. Ported (minus the scope_pulse / LED side effects that
 * caused the SDHI_CLK GPIO incident in the baseline) from
 * sdio_test_freertos_perf.
 */
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#include "platform.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "iot_logging_task.h"
#include "r_sci_rx_if.h"
#include "r_sci_rx_pinset.h"
#include "debug_uart.h"

#if (configSUPPORT_STATIC_ALLOCATION != 1)
#error debug_uart requires configSUPPORT_STATIC_ALLOCATION=1
#endif
#if (INCLUDE_xTaskGetSchedulerState != 1)
#error debug_uart requires INCLUDE_xTaskGetSchedulerState=1
#endif

#define DEBUG_UART_BAUD_RATE   (921600U)
#define DEBUG_STDIO_LINE_BYTES (160U)
#define DEBUG_UART_TX_SPIN_LIMIT (2000000UL)
#define DEBUG_UART_PSW_I_BIT     (0x00010000UL)
#define DEBUG_UART_TX_INT_PRIORITY (3U)

static sci_hdl_t         g_sci6;
static volatile bool     g_sci6_ready;
static volatile uint32_t g_sci6_err_count;   /* framing/parity/overflow tally */
static volatile uint32_t g_sci6_tx_timeout_count;
static StaticSemaphore_t g_sci6_tx_mutex_storage;
static SemaphoreHandle_t g_sci6_tx_mutex;
static char              g_stdio_line[DEBUG_STDIO_LINE_BYTES];
static uint16_t          g_stdio_line_length;
static volatile bool     g_stdio_flush_active;

/*
 * SCI event callback. Transmit is polled (see sci6_wait_tx_idle), so the
 * callback only tallies RX-side error events for diagnostics. TEI is not
 * relied upon (SCI_CFG_TEI_INCLUDED == 0).
 */
static void sci6_callback(void * p_args)
{
    sci_cb_args_t * p_evt = (sci_cb_args_t *)p_args;

    if (NULL == p_evt)
    {
        return;
    }

    switch (p_evt->event)
    {
        case SCI_EVT_FRAMING_ERR:
        case SCI_EVT_PARITY_ERR:
        case SCI_EVT_OVFL_ERR:
        case SCI_EVT_RXBUF_OVFL:
            g_sci6_err_count++;
            break;
        default:
            break;
    }
}

void debug_uart_init(void)
{
    sci_cfg_t cfg = {0};

    if (NULL == g_sci6_tx_mutex)
    {
        g_sci6_tx_mutex = xSemaphoreCreateMutexStatic(&g_sci6_tx_mutex_storage);
    }
    if (NULL == g_sci6_tx_mutex)
    {
        return;
    }

    cfg.async.baud_rate    = DEBUG_UART_BAUD_RATE;
    cfg.async.clk_src      = SCI_CLK_INT;
    cfg.async.data_size    = SCI_DATA_8BIT;
    cfg.async.parity_en    = SCI_PARITY_OFF;
    cfg.async.parity_type  = SCI_EVEN_PARITY;
    cfg.async.stop_bits    = SCI_STOPBITS_1;
    cfg.async.int_priority = DEBUG_UART_TX_INT_PRIORITY;

    if (SCI_SUCCESS == R_SCI_Open(SCI_CH6, SCI_MODE_ASYNC, &cfg, sci6_callback, &g_sci6))
    {
        R_SCI_PinSet_SCI6();
        g_sci6_ready = true;
    }
}

/*
 * Wait until the TX queue has fully drained and the last byte has shifted
 * out (SSR.TEND). TEI-independent: matches the baseline's polled flush.
 */
static bool sci6_wait_tx_idle(void)
{
    volatile uint32_t timeout = 2000000UL;
    uint16_t tx_free = 0U;

    if (!g_sci6_ready)
    {
        return false;
    }

    while (0UL != timeout)
    {
        if ((SCI_SUCCESS == R_SCI_Control(g_sci6, SCI_CMD_TX_Q_BYTES_FREE, &tx_free)) &&
            (SCI_CFG_CH6_TX_BUFSIZ == tx_free) &&
            (0U != SCI6.SSR.BIT.TEND))
        {
            return true;
        }
        timeout--;
    }

    return false;
}

static void debug_stdio_flush(bool append_newline)
{
    char line[DEBUG_STDIO_LINE_BYTES + 3U];
    uint16_t length = g_stdio_line_length;

    if (g_stdio_flush_active)
    {
        return;
    }
    if ((0U == length) && (!append_newline))
    {
        return;
    }

    g_stdio_flush_active = true;
    if (DEBUG_STDIO_LINE_BYTES < length)
    {
        length = DEBUG_STDIO_LINE_BYTES;
    }

    memcpy(line, g_stdio_line, length);
    g_stdio_line_length = 0U;

    if (append_newline)
    {
        line[length] = '\r';
        length++;
        line[length] = '\n';
        length++;
    }
    line[length] = '\0';

    if (taskSCHEDULER_RUNNING == xTaskGetSchedulerState())
    {
        vLoggingPrint(line);
    }
    else
    {
        debug_puts(line);
    }

    g_stdio_flush_active = false;
}

void debug_uart_stdio_charput(char output_char)
{
    if ('\r' == output_char)
    {
        return;
    }
    if ('\n' == output_char)
    {
        debug_stdio_flush(true);
        return;
    }

    if (g_stdio_line_length >= (DEBUG_STDIO_LINE_BYTES - 1U))
    {
        debug_stdio_flush(false);
    }

    g_stdio_line[g_stdio_line_length] = output_char;
    g_stdio_line_length++;
}

/*
 * The logging task and several RX671 bring-up/OTA tasks all terminate at this
 * SCI6 handle.  r_sci_rx uses an unprotected BYTEQ in this project, so the
 * free-space check plus enqueue must be one task-owned transaction.  Callers
 * are task context (or the scheduler-not-started boot path), never ISR context.
 */
static bool debug_uart_take_tx_mutex(TickType_t wait_ticks, bool * p_taken)
{
    BaseType_t scheduler_state;

    *p_taken = false;
    scheduler_state = xTaskGetSchedulerState();
    if (taskSCHEDULER_NOT_STARTED == scheduler_state)
    {
        return true;
    }
    if (NULL == g_sci6_tx_mutex)
    {
        return false;
    }
    if (taskSCHEDULER_RUNNING != scheduler_state)
    {
        wait_ticks = 0U;
    }
    if (pdTRUE != xSemaphoreTake(g_sci6_tx_mutex, wait_ticks))
    {
        return false;
    }

    *p_taken = true;
    return true;
}

static void debug_uart_give_tx_mutex(bool taken)
{
    if (taken)
    {
        (void)xSemaphoreGive(g_sci6_tx_mutex);
    }
}

static bool debug_uart_write(const char * text, TickType_t wait_ticks)
{
    uint16_t remaining;
    uint32_t spin_budget = DEBUG_UART_TX_SPIN_LIMIT;
    bool mutex_taken = false;
    bool success = false;

    if (!g_sci6_ready || (NULL == text))
    {
        return false;
    }
    /* Every output path depends on the TXI ISR.  Fatal/assert, ISR, or critical
     * context can clear PSW.I or raise IPL high enough to mask TXI; drop before
     * entering any FreeRTOS API or waiting for queue progress. */
    if ((0UL == (R_BSP_GET_PSW() & DEBUG_UART_PSW_I_BIT)) ||
        (R_BSP_GET_IPL() >= DEBUG_UART_TX_INT_PRIORITY))
    {
        return false;
    }
    if (!debug_uart_take_tx_mutex(wait_ticks, &mutex_taken))
    {
        return false;
    }

    remaining = (uint16_t)strlen(text);

    while (0U != remaining)
    {
        uint16_t tx_free = 0U;
        uint16_t n;

        if (SCI_SUCCESS != R_SCI_Control(g_sci6, SCI_CMD_TX_Q_BYTES_FREE, &tx_free))
        {
            goto cleanup;
        }
        if (0U == tx_free)
        {
            if (0UL == spin_budget)
            {
                g_sci6_tx_timeout_count++;
                goto cleanup;
            }
            spin_budget--;
            continue;                          /* let the TXI ISR drain */
        }

        n = (remaining < tx_free) ? remaining : tx_free;
        if (SCI_SUCCESS != R_SCI_Send(g_sci6, (uint8_t *)text, n))
        {
            if (0UL == spin_budget)
            {
                g_sci6_tx_timeout_count++;
                goto cleanup;
            }
            spin_budget--;
            continue;                          /* transient busy: retry */
        }

        text      += n;
        remaining -= n;
        spin_budget = DEBUG_UART_TX_SPIN_LIMIT;
    }

    if (!sci6_wait_tx_idle())
    {
        g_sci6_tx_timeout_count++;
        goto cleanup;
    }
    success = true;

cleanup:
    debug_uart_give_tx_mutex(mutex_taken);
    return success;
}

void debug_puts(const char * text)
{
    (void)debug_uart_write(text, portMAX_DELAY);
}

void debug_puts_try(const char * text)
{
    (void)debug_uart_write(text, 0U);
}

static char hex_nibble(uint8_t value)
{
    value &= 0x0fU;
    return (value < 10U) ? (char)('0' + value) : (char)('A' + (value - 10U));
}

char * append_text(char * dst, const char * src)
{
    while ('\0' != *src)
    {
        *dst = *src;
        dst++;
        src++;
    }

    return dst;
}

char * append_hex32(char * dst, uint32_t value)
{
    int8_t shift;

    for (shift = 28; shift >= 0; shift -= 4)
    {
        *dst = hex_nibble((uint8_t)(value >> shift));
        dst++;
    }

    return dst;
}

char * append_hex16(char * dst, uint32_t value)
{
    int8_t shift;

    for (shift = 12; shift >= 0; shift -= 4)
    {
        *dst = hex_nibble((uint8_t)(value >> shift));
        dst++;
    }

    return dst;
}

char * append_hex8(char * dst, uint32_t value)
{
    *dst = hex_nibble((uint8_t)(value >> 4));
    dst++;
    *dst = hex_nibble((uint8_t)value);
    dst++;

    return dst;
}

char * append_dec32(char * dst, uint32_t value)
{
    char tmp[10];
    uint8_t digits = 0U;

    do
    {
        tmp[digits] = (char)('0' + (value % 10UL));
        digits++;
        value /= 10UL;
    } while ((0UL != value) && (digits < sizeof(tmp)));

    while (digits > 0U)
    {
        digits--;
        *dst = tmp[digits];
        dst++;
    }

    return dst;
}

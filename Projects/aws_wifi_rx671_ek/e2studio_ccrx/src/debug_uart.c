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
#include "r_sci_rx_if.h"
#include "r_sci_rx_pinset.h"
#include "debug_uart.h"

#define DEBUG_UART_BAUD_RATE   (921600U)

static sci_hdl_t         g_sci6;
static volatile bool     g_sci6_ready;
static volatile uint32_t g_sci6_err_count;   /* framing/parity/overflow tally */

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

    cfg.async.baud_rate    = DEBUG_UART_BAUD_RATE;
    cfg.async.clk_src      = SCI_CLK_INT;
    cfg.async.data_size    = SCI_DATA_8BIT;
    cfg.async.parity_en    = SCI_PARITY_OFF;
    cfg.async.parity_type  = SCI_EVEN_PARITY;
    cfg.async.stop_bits    = SCI_STOPBITS_1;
    cfg.async.int_priority = 3;

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
static void sci6_wait_tx_idle(void)
{
    volatile uint32_t timeout = 2000000UL;
    uint16_t tx_free = 0U;

    if (!g_sci6_ready)
    {
        return;
    }

    while (0UL != timeout)
    {
        if ((SCI_SUCCESS == R_SCI_Control(g_sci6, SCI_CMD_TX_Q_BYTES_FREE, &tx_free)) &&
            (SCI_CFG_CH6_TX_BUFSIZ == tx_free) &&
            (0U != SCI6.SSR.BIT.TEND))
        {
            return;
        }
        timeout--;
    }
}

static void sci6_send_byte(char output_char)
{
    uint8_t ch = (uint8_t)output_char;

    if (!g_sci6_ready)
    {
        return;
    }

    for (;;)
    {
        uint16_t tx_free = 0U;

        if (SCI_SUCCESS != R_SCI_Control(g_sci6, SCI_CMD_TX_Q_BYTES_FREE, &tx_free))
        {
            return;
        }
        if (0U == tx_free)
        {
            continue;
        }
        if (SCI_SUCCESS == R_SCI_Send(g_sci6, &ch, 1U))
        {
            return;
        }
    }
}

void debug_putchar(char output_char)
{
    if ('\n' == output_char)
    {
        sci6_send_byte('\r');
    }
    sci6_send_byte(output_char);
}

void debug_puts(const char * text)
{
    uint16_t remaining;

    if (!g_sci6_ready || (NULL == text))
    {
        return;
    }

    remaining = (uint16_t)strlen(text);

    while (0U != remaining)
    {
        uint16_t tx_free = 0U;
        uint16_t n;

        if (SCI_SUCCESS != R_SCI_Control(g_sci6, SCI_CMD_TX_Q_BYTES_FREE, &tx_free))
        {
            return;
        }
        if (0U == tx_free)
        {
            continue;                          /* let the TXI ISR drain */
        }

        n = (remaining < tx_free) ? remaining : tx_free;
        if (SCI_SUCCESS != R_SCI_Send(g_sci6, (uint8_t *)text, n))
        {
            continue;                          /* transient busy: retry */
        }

        text      += n;
        remaining -= n;
    }

    sci6_wait_tx_idle();
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

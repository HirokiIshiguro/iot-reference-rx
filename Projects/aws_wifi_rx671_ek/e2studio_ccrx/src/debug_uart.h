/*
 * debug_uart - SCI6 async debug console for the EK-RX671 WHD project.
 *
 * Ported from the sdio_test_freertos_perf bring-up firmware. Uses the
 * board USB-serial path (P00 = TXD6 / P01 = RXD6, FT234XD-T) which the host
 * enumerates as the EK-RX671 COM port at 921600 8N1. Transmit is
 * interrupt-driven through the r_sci_rx FIT module; the flush is polled
 * (TX queue empty + SSR.TEND), so it does NOT depend on
 * SCI_CFG_TEI_INCLUDED (which is 0 in this project, as in the baseline).
 */
#ifndef DEBUG_UART_H_
#define DEBUG_UART_H_

#include <stdint.h>

/* Open SCI6 (async, 921600 8N1) and route the pins. Safe to call once at
 * task start; debug_puts() is a no-op until this succeeds. */
void debug_uart_init(void);

/* Blocking, NUL-terminated string output. Enqueues to the SCI TX queue in
 * pieces no larger than the free space, then waits for the line to drain. */
void debug_puts(const char * text);

/* Single-character output used by the BSP stdio charput hook. This lets WHD's
 * existing WPRINT/printf diagnostics share the SCI6 console. */
void debug_putchar(char output_char);

/* printf-free line builders. Each writes at the cursor and returns the new
 * cursor; the caller sizes the buffer and writes the final '\0'. */
char * append_text(char * dst, const char * src);
char * append_hex8(char * dst, uint32_t value);
char * append_hex16(char * dst, uint32_t value);
char * append_hex32(char * dst, uint32_t value);
char * append_dec32(char * dst, uint32_t value);

#endif /* DEBUG_UART_H_ */

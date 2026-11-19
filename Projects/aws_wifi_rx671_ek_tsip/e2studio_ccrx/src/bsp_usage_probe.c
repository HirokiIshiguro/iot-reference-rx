/*
 * bsp_usage_probe - see bsp_usage_probe.h. Measurement only.
 *
 * Stack high water mark: the stack areas are filled once with 0x55555555, as early as possible, from the bottom up to
 * 128 bytes below the current stack pointer (the margin keeps the fill clear of its own frame). Counting walks up from
 * the bottom to the first word that is not 0x55555555; from there to the top is the depth reached.
 *
 * User stack (SU): the BSP starts on the interrupt stack (PSW.U = 0), switches to SU when it sets PSW.U for main(), and
 * the FreeRTOS RX port then runs every task on the stack of the task. SU is therefore used from main() to the start of
 * the scheduler. SI is used by every interrupt. SI lies directly above SU, so an overflow of SI lands in SU.
 * C library heap: sbrk() of the BSP only grows, so the current break is the highest use.
 *
 * Nothing is kept in static RAM: the first words of SU (never reached by a stack that is not nearly full) hold the
 * bookkeeping, because the bss is cleared and the data initialised after the first callback.
 */
#include <stddef.h>
#include <stdint.h>

#include "platform.h"
#include "debug_uart.h"
#include "bsp_usage_probe.h"
#include "sdio_host.h"

#define BSP_PROBE_FILL      (0x55555555UL)
#define BSP_PROBE_MARGIN    (128U)

/* Bookkeeping words at the bottom of SU. The stack measurement of SU starts after them. */
#define META_SU_PAINT_END   (0U)    /* end of the area filled in SU */
#define META_SI_PAINT_END   (1U)    /* end of the area filled in SI */
#define META_SU_START_USED  (2U)    /* depth of SU used from the reset to the start of the scheduler */
#define META_CHEAP_BASE     (3U)    /* start of the C library heap (the break before anything was allocated) */
#define META_WORDS          (4U)

extern int8_t * sbrk(size_t size);

static volatile uint32_t * meta(void)
{
    return (volatile uint32_t *)__sectop("SU");
}

static uint32_t su_scan_bottom(void)
{
    return (uint32_t)__sectop("SU") + (META_WORDS * 4U);
}

/* Fill [bottom, stack pointer - margin) and return the end of the filled area (bottom when nothing was filled). */
static uint32_t paint(uint32_t bottom, uint32_t sp)
{
    volatile uint32_t * p = (volatile uint32_t *)((bottom + 3U) & ~3UL);
    uint32_t end = bottom;

    if (sp > (bottom + BSP_PROBE_MARGIN))
    {
        end = (sp - BSP_PROBE_MARGIN) & ~3UL;
        while ((uint32_t)p < end)
        {
            *p = BSP_PROBE_FILL;
            p++;
        }
    }
    return end;
}

/* The stack pointer register of a stack that is not the running one holds its top; a value outside the area is not
 * trusted. */
static uint32_t sane_sp(uint32_t sp, uint32_t bottom, uint32_t top)
{
    return ((sp > bottom) && (sp <= top)) ? sp : top;
}

void rx671_bsp_prec(void)
{
    const uint32_t su_bottom = su_scan_bottom();
    const uint32_t su_top = (uint32_t)__secend("SU");
    const uint32_t si_bottom = (uint32_t)__sectop("SI");
    const uint32_t si_top = (uint32_t)__secend("SI");
    const uint32_t usp = sane_sp((uint32_t)R_BSP_GET_USP(), su_bottom, su_top);
    const uint32_t isp = sane_sp((uint32_t)R_BSP_GET_ISP(), si_bottom, si_top);

    meta()[META_SU_PAINT_END] = paint(su_bottom, usp);
    meta()[META_SI_PAINT_END] = paint(si_bottom, isp);
    meta()[META_SU_START_USED] = 0U;
    meta()[META_CHEAP_BASE] = 0U;
}

void rx671_bsp_postc(void)
{
    meta()[META_CHEAP_BASE] = (uint32_t)sbrk(0U);
}

/* Walk up from the bottom to the first word that is not the fill value. Returns the depth reached (top - that word). */
static uint32_t stack_used(uint32_t bottom, uint32_t top)
{
    const volatile uint32_t * p = (const volatile uint32_t *)bottom;
    const volatile uint32_t * end = (const volatile uint32_t *)top;

    while ((p < end) && (BSP_PROBE_FILL == *p))
    {
        p++;
    }
    return top - (uint32_t)p;
}

void rx671_bsp_scheduler_started(void)
{
    const uint32_t bottom = su_scan_bottom();
    const uint32_t top = (uint32_t)__secend("SU");
    volatile uint32_t * p = (volatile uint32_t *)bottom;

    meta()[META_SU_START_USED] = stack_used(bottom, top);
    /* The start-up stack is dead: this task runs on its own stack. Fill SU again to see what lands there later. */
    while ((uint32_t)p < top)
    {
        *p = BSP_PROBE_FILL;
        p++;
    }
}

void rx671_bsp_log(void)
{
    char line[160];
    uint32_t dtc_done = 0U;
    uint32_t dtc_ok = 0U;
    uint32_t dtc_fail = 0U;
    uint32_t dtc_fallback = 0U;
    uint32_t dtc_error = 0U;
    uint32_t dtc_engine = 0U;
    uint32_t dtc_open_calls = 0U;
    uint32_t dtc_open_ret = 0U;
    uint32_t dtc_open_table = 0U;
    char * p = line;
    const uint32_t su_bottom = su_scan_bottom();
    const uint32_t su_top = (uint32_t)__secend("SU");
    const uint32_t si_bottom = (uint32_t)__sectop("SI");
    const uint32_t si_top = (uint32_t)__secend("SI");
    const uint32_t brk = (uint32_t)sbrk(0U);
    const uint32_t cheap_base = meta()[META_CHEAP_BASE];

    /* ustack is the depth used until the scheduler started; over is what has landed in SU since (an interrupt stack
     * overflow, or a use of SU after the start). upaint is the size of the area that was filled before the start. */
    p = append_text(p, "RX671 stack: ustack=");
    p = append_dec32(p, meta()[META_SU_START_USED]);
    p = append_text(p, "/");
    p = append_dec32(p, su_top - (uint32_t)__sectop("SU"));
    p = append_text(p, " upaint=");
    p = append_dec32(p, meta()[META_SU_PAINT_END] - su_bottom);
    p = append_text(p, " istack=");
    p = append_dec32(p, stack_used(si_bottom, si_top));
    p = append_text(p, "/");
    p = append_dec32(p, si_top - si_bottom);
    p = append_text(p, " ipaint=");
    p = append_dec32(p, meta()[META_SI_PAINT_END] - si_bottom);
    p = append_text(p, " over=");
    p = append_dec32(p, stack_used(su_bottom, su_top));
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);

    p = line;
    sdio_host_cmd53_xfer_diag(&dtc_engine, &dtc_done, &dtc_ok, &dtc_fail, &dtc_fallback, &dtc_error);
    sdio_host_cmd53_dtc_open_diag(&dtc_open_calls, &dtc_open_ret, &dtc_open_table);
    p = append_text(p, "RX671 cheap: used=");
    p = append_dec32(p, (0U != cheap_base) ? (brk - cheap_base) : 0U);
    p = append_text(p, "/");
    p = append_dec32(p, (uint32_t)BSP_CFG_HEAP_BYTES);
    /* DTC of the SDIO CMD53 path: its vector table is a malloc of the C library. */
    p = append_text(p, " dtc_ok=");
    p = append_dec32(p, dtc_ok);
    p = append_text(p, " dtc_fail=");
    p = append_dec32(p, dtc_fail);
    p = append_text(p, " dtc_err=0x");
    p = append_hex32(p, dtc_error);
    p = append_text(p, " dtc_open=");
    p = append_dec32(p, dtc_open_ret);
    p = append_text(p, "/");
    p = append_dec32(p, dtc_open_calls);
    p = append_text(p, " dtc_table=");
    p = append_dec32(p, dtc_open_table);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

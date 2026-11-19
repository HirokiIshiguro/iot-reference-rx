/*
 * bsp_usage_probe - see bsp_usage_probe.h. Measurement only.
 *
 * User stack (SU): the BSP starts on the interrupt stack (PSW.U = 0), switches to SU when it sets PSW.U for main(), and
 * the FreeRTOS RX port then runs every task on the stack of the task. SU is therefore used from main() to the start of
 * the scheduler. SI is used by every interrupt.
 * C library heap: sbrk() of the BSP only grows, so the current break is the highest use.
 */
#include <stddef.h>
#include <stdint.h>

#include "platform.h"
#include "debug_uart.h"
#include "bsp_usage_probe.h"

#define BSP_PROBE_FILL      (0xA5A5A5A5UL)
#define BSP_PROBE_GUARD     (64U)

extern int8_t * sbrk(size_t size);

/* Start of the C library heap (the break before anything was allocated). Zero until rx671_bsp_postc() ran. */
static uint32_t s_cheap_base;

void rx671_bsp_prec(void)
{
    volatile uint32_t * p;
    volatile uint32_t * end;

    /* SU is not in use before PSW.U is set. */
    p = (volatile uint32_t *)__sectop("SU");
    end = (volatile uint32_t *)__secend("SU");
    while (p < end)
    {
        *p = BSP_PROBE_FILL;
        p++;
    }

    /* SI is in use right now: paint only below the stack pointer, with a guard for this function's own frame. */
    p = (volatile uint32_t *)__sectop("SI");
    end = (volatile uint32_t *)(((uint32_t)R_BSP_GET_ISP() - BSP_PROBE_GUARD) & ~3UL);
    while (p < end)
    {
        *p = BSP_PROBE_FILL;
        p++;
    }
}

void rx671_bsp_postc(void)
{
    s_cheap_base = (uint32_t)sbrk(0U);
}

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

static char * append_used(char * p, const char * label, uint32_t used, uint32_t total)
{
    p = append_text(p, label);
    p = append_dec32(p, used);
    p = append_text(p, "/");
    p = append_dec32(p, total);
    return p;
}

void rx671_bsp_log(void)
{
    char line[96];
    char * p = line;
    const uint32_t su_bottom = (uint32_t)__sectop("SU");
    const uint32_t su_top = (uint32_t)__secend("SU");
    const uint32_t si_bottom = (uint32_t)__sectop("SI");
    const uint32_t si_top = (uint32_t)__secend("SI");
    const uint32_t brk = (uint32_t)sbrk(0U);

    p = append_text(p, "RX671 bsp: ");
    p = append_used(p, "ustack=", stack_used(su_bottom, su_top), su_top - su_bottom);
    p = append_used(p, " istack=", stack_used(si_bottom, si_top), si_top - si_bottom);
    p = append_used(p, " cheap=", (0U != s_cheap_base) ? (brk - s_cheap_base) : 0U, (uint32_t)BSP_CFG_HEAP_BYTES);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

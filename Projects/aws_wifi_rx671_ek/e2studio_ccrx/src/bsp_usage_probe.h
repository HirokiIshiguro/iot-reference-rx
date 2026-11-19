/*
 * bsp_usage_probe - how much of the BSP user stack (SU), interrupt stack (SI) and C library heap the firmware used.
 *
 * Measurement only. The two warm start callbacks of the BSP (r_bsp_config.h) paint the stacks before the C runtime is
 * initialised and remember where the C library heap starts; rx671_bsp_log() reads the high water marks.
 */
#ifndef BSP_USAGE_PROBE_H_
#define BSP_USAGE_PROBE_H_

/* BSP_CFG_USER_WARM_START_PRE_C_FUNCTION: paints the unused part of SU and SI. No statics (the bss is cleared later). */
void rx671_bsp_prec(void);

/* BSP_CFG_USER_WARM_START_POST_C_FUNCTION: records the start of the C library heap (sbrk(0)). */
void rx671_bsp_postc(void);

/* Call once at the head of the first task, after the scheduler has started: records how deep the start-up used SU and
 * repaints SU. Whatever is written to SU afterwards is not start-up (the scheduler runs every task on its own stack): it
 * is an interrupt stack overflow into SU (SI lies directly above SU) or a use of SU after the start. */
void rx671_bsp_scheduler_started(void);

/* Task context only. Prints "RX671 bsp: ustack=<start-up used>/<size> istack=<used>/<size> over=<bytes>
 * cheap=<used>/<size>". */
void rx671_bsp_log(void);

#endif /* BSP_USAGE_PROBE_H_ */

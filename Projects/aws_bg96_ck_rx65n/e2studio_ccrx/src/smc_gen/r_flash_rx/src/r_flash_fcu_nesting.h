/*
 * Copyright (c) 2026 SAFFTI
 * SPDX-License-Identifier: BSD-3-Clause
 */
#ifndef RX_FLASH_FCU_NESTING_HEADER_FILE
#define RX_FLASH_FCU_NESTING_HEADER_FILE

/* Old generated configuration headers retain the upstream behavior. */
#ifndef FLASH_CFG_FCU_EN_NESTED_INT
#define FLASH_CFG_FCU_EN_NESTED_INT (0)
#endif

#if (FLASH_CFG_FCU_EN_NESTED_INT != 0) && (FLASH_CFG_FCU_EN_NESTED_INT != 1)
#error "FLASH_CFG_FCU_EN_NESTED_INT must be 0 or 1."
#endif

#if FLASH_CFG_FCU_EN_NESTED_INT == 1
#if (FLASH_TYPE != FLASH_TYPE_4) || (FLASH_IN_DUAL_BANK_MODE != 1) || \
    (FLASH_CFG_CODE_FLASH_RUN_FROM_ROM != 1) || (FLASH_CFG_CODE_FLASH_ENABLE != 1) || \
    (FLASH_CFG_CODE_FLASH_BGO != 1)
#error "FCU nesting requires type 4, dual bank, code flash BGO and execution from the other ROM bank."
#endif

/* Include after r_flash_rx_if.h, r_flash_fcu.h and r_flash_group.h.
 * FSADDR names the active command; dest_addr is the next halfword for writes
 * and the current block for erases. Check both before allowing preemption.
 * The caller must keep vectors and all higher-priority ISR dependencies in
 * the resident high bank/RAM and must not call Flash APIs from those ISRs.
 * Only PSW.I changes: retaining IPL prevents equal-priority FCU reentry.
 * No out-of-line helper is introduced into the P/E execution path. */
#define FLASH_FCU_TRY_ENABLE_NESTED_INT()                                                    \
    do                                                                                     \
    {                                                                                      \
        if (((FLASH_CUR_CF_BGO_WRITE == g_current_parameters.current_operation) ||           \
             (FLASH_CUR_CF_BGO_ERASE == g_current_parameters.current_operation)) &&           \
            (true == g_current_parameters.bgo_enabled_cf) &&                                 \
            (0x0001U == FLASH.FENTRYR.WORD) &&                                                \
            ((uint32_t) FLASH_CF_LO_BANK_LO_ADDR <= FLASH.FSADDR.LONG) &&                      \
            ((uint32_t) FLASH_CF_LO_BANK_HI_ADDR >= FLASH.FSADDR.LONG) &&                      \
            ((uint32_t) FLASH_CF_LO_BANK_LO_ADDR <= g_current_parameters.dest_addr) &&         \
            ((uint32_t) FLASH_CF_LO_BANK_HI_ADDR >= g_current_parameters.dest_addr))           \
        {                                                                                  \
            R_BSP_SETPSW_I();                                                               \
        }                                                                                  \
    } while (0)
#else
#define FLASH_FCU_TRY_ENABLE_NESTED_INT() do { } while (0)
#endif

#endif /* RX_FLASH_FCU_NESTING_HEADER_FILE */

#ifndef REGEN_SAFE_R_BSP_CONFIG_H
#define REGEN_SAFE_R_BSP_CONFIG_H

/*
 * Smart Configurator regeneration may rewrite the RX72N MCU identity macros in
 * a form that breaks r_bsp/mcu_info.h. Keep the generated file as the primary
 * source of settings, then override only the MCU identity fields here.
 */

#include "../smc_gen/r_config/r_bsp_config.h"

#undef BSP_CFG_MCU_PART_PACKAGE
#define BSP_CFG_MCU_PART_PACKAGE        (0x2) /* RX72N Envision Kit: LFBGA224 */

#undef BSP_CFG_MCU_PART_FUNCTION
#define BSP_CFG_MCU_PART_FUNCTION       (0x11) /* encryption + dual-bank */

#undef BSP_CFG_MCU_PART_ENCRYPTION_INCLUDED
#define BSP_CFG_MCU_PART_ENCRYPTION_INCLUDED   (true)

#undef BSP_CFG_MCU_PART_MEMORY_SIZE
#define BSP_CFG_MCU_PART_MEMORY_SIZE    (0x17) /* 4MB ROM / 1MB RAM / 32KB DF */

#undef BSP_CFG_MCU_PART_GROUP
#define BSP_CFG_MCU_PART_GROUP          (0x0) /* RX72N group */

#undef BSP_CFG_MCU_PART_SERIES
#define BSP_CFG_MCU_PART_SERIES         (0x0) /* RX700 series */

#undef BSP_CFG_MCU_PART_MEMORY_TYPE
#define BSP_CFG_MCU_PART_MEMORY_TYPE    (0x0)

#endif /* REGEN_SAFE_R_BSP_CONFIG_H */

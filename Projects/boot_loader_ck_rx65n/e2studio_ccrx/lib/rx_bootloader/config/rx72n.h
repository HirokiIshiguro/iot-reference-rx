/***********************************************************************************************************************
* File Name    : rx72n.h
* Description  : RX72N (4MB Code Flash, dual-bank) configuration for rx_bootloader.
*
*                Values below are extracted from the original rx72n-envision-kit boot_loader
*                (projects/renesas/rx72n_envision_kit/e2studio/boot_loader/src/rx72n_boot_loader.c).
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_MCU_RX72N_H
#define RX_BOOTLOADER_MCU_RX72N_H

/* Code Flash address map (4MB dual-bank, BANK0: lower, BANK1: upper) */
/* R_FLASH_Write() arguments: specify "low address" and process to "high address" */
#define RX_BOOTLOADER_LOW_ADDRESS                           FLASH_CF_BLOCK_13
#define RX_BOOTLOADER_MIRROR_LOW_ADDRESS                    FLASH_CF_BLOCK_83

/* R_FLASH_Erase() arguments: specify "high address (low block number)" and process to "low address (high block number)" */
#define RX_BOOTLOADER_MIRROR_HIGH_ADDRESS                   FLASH_CF_BLOCK_70
#define RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_HIGH_ADDRESS    FLASH_CF_BLOCK_84

/* Mirror block counts */
#define RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL            (8)
#define RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM           (6)

/* Mirror copy source/destination for small-block area (boundary between small and medium blocks) */
#define RX_BOOTLOADER_SMALL_BLOCK_SRC                       FLASH_CF_BLOCK_7
#define RX_BOOTLOADER_SMALL_BLOCK_DST                       FLASH_CF_BLOCK_77

/* Data Flash area for user const data */
#define RX_BOOTLOADER_USER_CONST_DATA_LOW_ADDRESS           FLASH_DF_BLOCK_32
#define RX_BOOTLOADER_USER_CONST_DATA_BLOCK_NUM             (448)

/* Const data target block number calculation.
 * RX72N: equals USER_CONST_DATA_BLOCK_NUM (install area is dedicated to user const data). */
#define RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER \
    (RX_BOOTLOADER_USER_CONST_DATA_BLOCK_NUM)

/* Firmware header/descriptor lengths (common across RX family; kept per-MCU for flexibility) */
#define RX_BOOTLOADER_FW_HEADER_LENGTH                      (0x200)
#define RX_BOOTLOADER_FW_DESCRIPTOR_LENGTH                  (0x100)

#endif /* RX_BOOTLOADER_MCU_RX72N_H */

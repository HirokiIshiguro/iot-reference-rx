/***********************************************************************************************************************
* File Name    : rx65n.h
* Description  : RX65N (2MB Code Flash, dual-bank) configuration for rx_bootloader.
*
*                Values below are extracted from the amazon-freertos RX65N-RSK boot_loader
*                (projects/renesas/rx65n-rsk/e2studio/boot_loader/src/boot_loader.h).
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_MCU_RX65N_H
#define RX_BOOTLOADER_MCU_RX65N_H

/* Code Flash address map (2MB dual-bank) */
#define RX_BOOTLOADER_LOW_ADDRESS                           FLASH_CF_BLOCK_13
#define RX_BOOTLOADER_MIRROR_LOW_ADDRESS                    FLASH_CF_BLOCK_51

#define RX_BOOTLOADER_MIRROR_HIGH_ADDRESS                   FLASH_CF_BLOCK_38
#define RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_HIGH_ADDRESS    FLASH_CF_BLOCK_52

/* Mirror block counts */
#define RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL            (8)
#define RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM           (6)

/* Mirror copy source/destination for small-block area
 * NOTE: Verify against RX65N-RSK boot_loader.c before use. */
#define RX_BOOTLOADER_SMALL_BLOCK_SRC                       FLASH_CF_BLOCK_7
#define RX_BOOTLOADER_SMALL_BLOCK_DST                       FLASH_CF_BLOCK_45

/* Data Flash area for user const data */
#define RX_BOOTLOADER_USER_CONST_DATA_LOW_ADDRESS           FLASH_DF_BLOCK_0
#define RX_BOOTLOADER_USER_CONST_DATA_BLOCK_NUM             (256)

/* Const data target block number calculation.
 * RX65N: remaining DF blocks after reserving USER_CONST_DATA_BLOCK_NUM at the bottom. */
#define RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER \
    (FLASH_NUM_BLOCKS_DF - RX_BOOTLOADER_USER_CONST_DATA_BLOCK_NUM)

/* Firmware header/descriptor lengths */
#define RX_BOOTLOADER_FW_HEADER_LENGTH                      (0x200)
#define RX_BOOTLOADER_FW_DESCRIPTOR_LENGTH                  (0x100)

#endif /* RX_BOOTLOADER_MCU_RX65N_H */

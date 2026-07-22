/***********************************************************************************************************************
* File Name    : rx671.h
* Description  : RX671 (2MB Code Flash, dual-bank) configuration for rx_bootloader.
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_MCU_RX671_H
#define RX_BOOTLOADER_MCU_RX671_H

/* Code Flash address map (2MB dual-bank). */
#define RX_BOOTLOADER_LOW_ADDRESS                           FLASH_CF_BLOCK_13
#define RX_BOOTLOADER_MIRROR_LOW_ADDRESS                    FLASH_CF_BLOCK_51

#define RX_BOOTLOADER_MIRROR_HIGH_ADDRESS                   FLASH_CF_BLOCK_38
#define RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_HIGH_ADDRESS    FLASH_CF_BLOCK_52

/* Mirror block counts. */
#define RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL            (8)
#define RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM           (6)

/* Mirror copy source/destination for the small-block area. */
#define RX_BOOTLOADER_SMALL_BLOCK_SRC                       FLASH_CF_BLOCK_7
#define RX_BOOTLOADER_SMALL_BLOCK_DST                       FLASH_CF_BLOCK_45

/*
 * RX671 has 8 KiB of Data Flash. The RX671 IoT application owns the whole area
 * for LittleFS/KVS, so firmware installation must preserve it. This switch only
 * disables raw const-data installation; it does not disable a separately
 * configured key store. RX671 uses LittleFS because the bundled SFD port is
 * RX72N-only.
 */
#define RX_BOOTLOADER_INSTALL_DATA_FLASH                    (0)
#define RX_BOOTLOADER_USER_CONST_DATA_LOW_ADDRESS           FLASH_DF_BLOCK_0
#define RX_BOOTLOADER_USER_CONST_DATA_BLOCK_NUM             (FLASH_NUM_BLOCKS_DF)
#define RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER (0)
#define RX_BOOTLOADER_LITTLEFS_KEY_STORE_BASE_ADDRESS       FLASH_DF_BLOCK_0
#define RX_BOOTLOADER_LITTLEFS_KEY_STORE_REGION_SIZE        (FLASH_DF_BLOCK_SIZE * FLASH_NUM_BLOCKS_DF)

/* Firmware header/descriptor lengths. */
#define RX_BOOTLOADER_FW_HEADER_LENGTH                      (0x200)
#define RX_BOOTLOADER_FW_DESCRIPTOR_LENGTH                  (0x100)

#endif /* RX_BOOTLOADER_MCU_RX671_H */

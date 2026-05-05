/***********************************************************************
*
*  FILE        : rx_bootloader_config.h
*  DESCRIPTION : RX72N Envision Kit configuration for rx_bootloader.
*
***********************************************************************/

#ifndef RX_BOOTLOADER_CONFIG_H
#define RX_BOOTLOADER_CONFIG_H

#include "rx72n.h"

#define RX_BOOTLOADER_USE_LCD                   (1)
#define RX_BOOTLOADER_USE_DUAL_BANK             (1)
#define RX_BOOTLOADER_USE_PERF_COUNTER          (0)
#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE   (0)
#define RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE    (1)

/*
 * Share the application LittleFS/KV region so the bootloader can consume a
 * provisioned code signer public key without owning a second Data Flash format.
 */
#define RX_BOOTLOADER_LITTLEFS_KEY_STORE_BASE_ADDRESS  (RX_BOOTLOADER_USER_CONST_DATA_LOW_ADDRESS)
#define RX_BOOTLOADER_LITTLEFS_KEY_STORE_REGION_SIZE   (128U * 70U)
#define RX_BOOTLOADER_LITTLEFS_PUBLIC_KEY_FILE         "code_signer_public_key"
#define RX_BOOTLOADER_LITTLEFS_CODE_SIGN_CERT_FILE     "code_sign_cert_id"
#define RX_BOOTLOADER_LITTLEFS_PUBLIC_KEY_BUFFER_SIZE  (512U)

#define RX_BOOTLOADER_FLASH_INT_PRIORITY        (14)
#define RX_BOOTLOADER_SCI_INT_PRIORITY          (15)

#define RX_BOOTLOADER_INITIAL_FW_FILENAME       "userprog.rsu"

#define RX_BOOTLOADER_USE_TINYCRYPT             (1)

#define BSP_CFG_SCI_UART_TERMINAL_CHANNEL       (7)
#define BSP_CFG_SCI_UART_TERMINAL_BITRATE       (921600)
#define BSP_CFG_SCI_UART_TERMINAL_INTERRUPT_PRIORITY (15)

#endif /* RX_BOOTLOADER_CONFIG_H */

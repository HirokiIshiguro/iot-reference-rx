/***********************************************************************************************************************
* File Name    : rx_bootloader_config.h
* Description  : Project configuration for the EK-RX671 secure bootloader sample.
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_CONFIG_H
#define RX_BOOTLOADER_CONFIG_H

#include "r_flash_rx_if.h"
#include "rx671.h"

#define RX_BOOTLOADER_USE_LCD                          (0)
#define RX_BOOTLOADER_USE_DUAL_BANK                    (1)
#define RX_BOOTLOADER_USE_PERF_COUNTER                 (0)
#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE          (0)
#define RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE            (1)
#define RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK (0)
#define RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE           (1)

/* Share the application's whole 8 KiB Data Flash LittleFS/KVS region. */
#define RX_BOOTLOADER_LITTLEFS_PUBLIC_KEY_FILE          "code_signer_public_key"
#define RX_BOOTLOADER_LITTLEFS_CODE_SIGN_CERT_FILE      "code_sign_cert_id"
#define RX_BOOTLOADER_LITTLEFS_PUBLIC_KEY_BUFFER_SIZE   (512U)

#define RX_BOOTLOADER_FLASH_INT_PRIORITY               (14)
#define RX_BOOTLOADER_SCI_INT_PRIORITY                 (15)

#define RX_BOOTLOADER_INITIAL_FW_FILENAME              "userprog.rsu"

#define RX_BOOTLOADER_USE_TINYCRYPT                    (1)
/* #define RX_BOOTLOADER_USE_MBEDTLS                   (1) */

#endif /* RX_BOOTLOADER_CONFIG_H */

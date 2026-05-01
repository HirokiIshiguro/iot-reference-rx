/***********************************************************************************************************************
* File Name    : rx_bootloader_config.h
* Description  : Project configuration for the CK-RX65N V1 secure bootloader sample.
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_CONFIG_H
#define RX_BOOTLOADER_CONFIG_H

#include "r_flash_rx_if.h"
#include "rx65n.h"

#define RX_BOOTLOADER_USE_LCD                          (0)
#define RX_BOOTLOADER_USE_DUAL_BANK                    (1)
#define RX_BOOTLOADER_USE_PERF_COUNTER                 (0)
#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE          (0)

#define RX_BOOTLOADER_FLASH_INT_PRIORITY               (14)
#define RX_BOOTLOADER_SCI_INT_PRIORITY                 (15)

#define RX_BOOTLOADER_INITIAL_FW_FILENAME              "userprog.rsu"

#define RX_BOOTLOADER_USE_TINYCRYPT                    (1)
/* #define RX_BOOTLOADER_USE_MBEDTLS                   (1) */

#endif /* RX_BOOTLOADER_CONFIG_H */

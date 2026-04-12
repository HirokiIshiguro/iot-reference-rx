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
#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE   (1)

#define RX_BOOTLOADER_FLASH_INT_PRIORITY        (14)
#define RX_BOOTLOADER_SCI_INT_PRIORITY          (15)

#define RX_BOOTLOADER_INITIAL_FW_FILENAME       "userprog.rsu"

#define RX_BOOTLOADER_USE_TINYCRYPT             (1)

#define BSP_CFG_SCI_UART_TERMINAL_CHANNEL       (7)
#define BSP_CFG_SCI_UART_TERMINAL_BITRATE       (921600)
#define BSP_CFG_SCI_UART_TERMINAL_INTERRUPT_PRIORITY (15)

#endif /* RX_BOOTLOADER_CONFIG_H */

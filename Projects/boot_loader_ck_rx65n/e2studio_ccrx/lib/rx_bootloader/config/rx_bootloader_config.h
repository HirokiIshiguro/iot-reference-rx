/***********************************************************************************************************************
* File Name    : rx_bootloader_config.h
* Description  : User-editable configuration template for rx_bootloader.
*
*                Copy this file into your project's include path and adjust the settings below
*                for the target MCU and board.
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_CONFIG_H
#define RX_BOOTLOADER_CONFIG_H

/*---------------------------------------------------------------------------------------------------------------------*
 * MCU group selection: include exactly one per-MCU header.
 *---------------------------------------------------------------------------------------------------------------------*/
#include "rx72n.h"
/* #include "rx65n.h" */

/*---------------------------------------------------------------------------------------------------------------------*
 * Optional features
 *---------------------------------------------------------------------------------------------------------------------*/

/* Enable LCD output via r_simple_graphic_rx FIT module (e.g., RX72N Envision Kit).
 * When 0, console output goes to SCI (UART) only. */
#define RX_BOOTLOADER_USE_LCD                   (0)

/* Enable dual-bank bank-swap flow. Required for MCUs with dual-bank Code Flash. */
#define RX_BOOTLOADER_USE_DUAL_BANK             (1)

/* Enable 10us performance counter (uses r_cmt_rx). */
#define RX_BOOTLOADER_USE_PERF_COUNTER          (0)

/* Enable key provisioning via Simple Filesystem on DataFlash (SFD).
 * When 0, the public key defined in code_signer_public_key.h is used directly. */
#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE   (0)

/*---------------------------------------------------------------------------------------------------------------------*
 * Interrupt priorities (0: lowest, 15: highest)
 *---------------------------------------------------------------------------------------------------------------------*/
#define RX_BOOTLOADER_FLASH_INT_PRIORITY        (14)
#define RX_BOOTLOADER_SCI_INT_PRIORITY          (15)

/*---------------------------------------------------------------------------------------------------------------------*
 * UART download settings
 *---------------------------------------------------------------------------------------------------------------------*/
#define RX_BOOTLOADER_INITIAL_FW_FILENAME       "userprog.rsu"

/*---------------------------------------------------------------------------------------------------------------------*
 * Crypto library selection (define exactly one)
 *---------------------------------------------------------------------------------------------------------------------*/
#define RX_BOOTLOADER_USE_TINYCRYPT             (1)
/* #define RX_BOOTLOADER_USE_MBEDTLS            (1) */

#endif /* RX_BOOTLOADER_CONFIG_H */

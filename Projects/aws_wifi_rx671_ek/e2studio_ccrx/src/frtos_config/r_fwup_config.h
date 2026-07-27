/*
* Copyright (c) 2026 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

#ifndef R_FWUP_CONFIG_H
#define R_FWUP_CONFIG_H

#include "platform.h"

#define FWUP_CFG_UPDATE_MODE                        (0)
#define FWUP_CFG_FUNCTION_MODE                      (1)

/* RX671 2 MB code flash, prepared for the future dual-bank OTA layout.
 * The OTA image build profile temporarily narrows each install area to
 * 768 KiB while preserving this linear-mode runtime default. */
#define FWUP_CFG_MAIN_AREA_ADDR_L                   (0xFFF00000U)
#define FWUP_CFG_BUF_AREA_ADDR_L                    (0xFFE00000U)
#define FWUP_CFG_AREA_SIZE                          (0x00100000U)

#define FWUP_CFG_CF_BLK_SIZE                        (0x8000U)
#define FWUP_CFG_CF_W_UNIT_SIZE                     (128U)

#define FWUP_CFG_EXT_BUF_AREA_ADDR_L                (0x00000U)
#define FWUP_CFG_EXT_BUF_AREA_BLK_SIZE              (4096U)

#define FWUP_CFG_DF_ADDR_L                          (0x00100000U)
#define FWUP_CFG_DF_BLK_SIZE                        (64U)
#define FWUP_CFG_DF_NUM_BLKS                        (128U)

#define FWUP_CFG_FWUPV1_COMPATIBLE                  (0)
#define FWUP_CFG_SIGNATURE_VERIFICATION             (0)
#define FWUP_CFG_PRINTF_DISABLE                     (0)

#define FWUP_CFG_USER_DISABLE_INTERRUPT_ENABLED     (0)
#define FWUP_CFG_USER_DISABLE_INTERRUPT_FUNCTION    my_disable_interrupt_function

#define FWUP_CFG_USER_ENABLE_INTERRUPT_ENABLED      (0)
#define FWUP_CFG_USER_ENABLE_INTERRUPT_FUNCTION     my_enable_interrupt_function

#define FWUP_CFG_USER_SOFTWARE_DELAY_ENABLED        (0)
#define FWUP_CFG_USER_SOFTWARE_DELAY_FUNCTION       my_software_delay_function

#define FWUP_CFG_USER_SOFTWARE_RESET_ENABLED        (0)
#define FWUP_CFG_USER_SOFTWARE_RESET_FUNCTION       my_software_reset_function

#define FWUP_CFG_USER_SHA256_INIT_ENABLED           (0)
#define FWUP_CFG_USER_SHA256_INIT_FUNCTION          my_sha256_init_function

#define FWUP_CFG_USER_SHA256_UPDATE_ENABLED         (0)
#define FWUP_CFG_USER_SHA256_UPDATE_FUNCTION        my_sha256_update_function

#define FWUP_CFG_USER_SHA256_FINAL_ENABLED          (0)
#define FWUP_CFG_USER_SHA256_FINAL_FUNCTION         my_sha256_final_function

#define FWUP_CFG_USER_VERIFY_ECDSA_ENABLED          (0)
#define FWUP_CFG_USER_VERIFY_ECDSA_FUNCTION         my_verify_ecdsa_function

#define FWUP_CFG_USER_GET_CRYPT_CONTEXT_ENABLED     (0)
#define FWUP_CFG_USER_GET_CRYPT_CONTEXT_FUNCTION    my_get_crypt_context_function

#define FWUP_CFG_USER_FLASH_OPEN_ENABLED            (0)
#define FWUP_CFG_USER_FLASH_OPEN_FUNCTION           my_flash_open_function

#define FWUP_CFG_USER_FLASH_CLOSE_ENABLED           (0)
#define FWUP_CFG_USER_FLASH_CLOSE_FUNCTION          my_flash_close_function

#define FWUP_CFG_USER_FLASH_ERASE_ENABLED           (0)
#define FWUP_CFG_USER_FLASH_ERASE_FUNCTION          my_flash_erase_function

#define FWUP_CFG_USER_FLASH_WRITE_ENABLED           (0)
#define FWUP_CFG_USER_FLASH_WRITE_FUNCTION          my_flash_write_function

#define FWUP_CFG_USER_FLASH_READ_ENABLED            (0)
#define FWUP_CFG_USER_FLASH_READ_FUNCTION           my_flash_read_function

#define FWUP_CFG_USER_BANK_SWAP_ENABLED             (0)
#define FWUP_CFG_USER_BANK_SWAP_FUNCTION            my_bank_swap_function

#define FWUP_CFG_USER_EXT_FLASH_OPEN_ENABLED        (0)
#define FWUP_CFG_USER_EXT_FLASH_OPEN_FUNCTION       my_ext_flash_open_function

#define FWUP_CFG_USER_EXT_FLASH_CLOSE_ENABLED       (0)
#define FWUP_CFG_USER_EXT_FLASH_CLOSE_FUNCTION      my_ext_flash_close_function

#define FWUP_CFG_USER_EXT_FLASH_ERASE_ENABLED       (0)
#define FWUP_CFG_USER_EXT_FLASH_ERASE_FUNCTION      my_ext_flash_erase_function

#define FWUP_CFG_USER_EXT_FLASH_WRITE_ENABLED       (0)
#define FWUP_CFG_USER_EXT_FLASH_WRITE_FUNCTION      my_ext_flash_write_function

#define FWUP_CFG_USER_EXT_FLASH_READ_ENABLED        (0)
#define FWUP_CFG_USER_EXT_FLASH_READ_FUNCTION       my_ext_flash_read_function

#endif /* R_FWUP_CONFIG_H */

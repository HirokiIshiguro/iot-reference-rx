/* SPDX-License-Identifier: MIT
 * Direct-flash OTA PAL policy and memory layout, owned by this application.
 * Smart Configurator does not generate this file. No r_fwup module is used.
 */
#ifndef RX_OTA_CONFIG_H
#define RX_OTA_CONFIG_H

/* Dual-bank application; ECDSA P-256/SHA-256 verification. */
#define RX_OTA_CFG_UPDATE_MODE                           (0)
#define RX_OTA_CFG_FUNCTION_MODE                         (1)
#define RX_OTA_CFG_MAIN_AREA_ADDR_L                      (0xFFF00000U)
#define RX_OTA_CFG_BUF_AREA_ADDR_L                       (0xFFE00000U)
#define RX_OTA_CFG_AREA_SIZE                             (0xC0000U)
#define RX_OTA_CFG_CF_BLK_SIZE                           (0x8000U)
#define RX_OTA_CFG_CF_W_UNIT_SIZE                        (128U)
#define RX_OTA_CFG_DF_ADDR_L                             (0x00100000)
#define RX_OTA_CFG_DF_BLK_SIZE                           (64U)
#define RX_OTA_CFG_DF_NUM_BLKS                           (512U)
#define RX_OTA_CFG_SIGNATURE_VERIFICATION                (0)

#endif /* RX_OTA_CONFIG_H */

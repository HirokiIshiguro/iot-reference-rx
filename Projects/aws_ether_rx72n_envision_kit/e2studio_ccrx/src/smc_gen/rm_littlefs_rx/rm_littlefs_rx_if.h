/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
#ifndef RM_LITTLEFS_RX_IF_H
#define RM_LITTLEFS_RX_IF_H

#include <stdint.h>
#include "rm_littlefs_rx_config.h"
#include "lfs.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RM_LITTLEFS_RX_VERSION_MAJOR             (1u)
#define RM_LITTLEFS_RX_VERSION_MINOR             (0u)

/*
 * Persistent format compatibility policy:
 * - The on-flash format is upstream littlefs v2. rm_littlefs_rx does not add a private header before littlefs.
 * - Bootloader and application images sharing a region must use compatible littlefs v2 code and identical geometry.
 * - The same base address and region size must be passed to RM_LITTLEFS_Open().
 */
#define RM_LITTLEFS_PERSISTENT_SCHEMA_VERSION    (2u)

typedef enum e_rm_littlefs_err
{
    RM_LITTLEFS_SUCCESS = 0,
    RM_LITTLEFS_ERR_INVALID_ARGUMENT,
    RM_LITTLEFS_ERR_FLASH,
    RM_LITTLEFS_ERR_MOUNT,
    RM_LITTLEFS_ERR_FORMAT,
    RM_LITTLEFS_ERR_NOT_OPEN
} rm_littlefs_err_t;

typedef struct st_rm_littlefs_cfg
{
    uint32_t base_address;
    uint32_t region_size;
    uint32_t read_size;
    uint32_t prog_size;
    uint32_t block_size;
    uint32_t cache_size;
    uint32_t lookahead_size;
    int32_t block_cycles;
    uint32_t format_if_mount_failed;
} rm_littlefs_cfg_t;

typedef struct st_rm_littlefs_ctrl
{
    lfs_t lfs;
    struct lfs_config lfs_cfg;
    uint32_t opened;
    uint32_t close_flash_on_close;
    uint32_t base_address;
    uint32_t region_size;
    uint8_t read_buffer[RM_LITTLEFS_CFG_CACHE_SIZE];
    uint8_t prog_buffer[RM_LITTLEFS_CFG_CACHE_SIZE];
    uint8_t lookahead_buffer[RM_LITTLEFS_CFG_LOOKAHEAD_SIZE];
} rm_littlefs_ctrl_t;

rm_littlefs_err_t RM_LITTLEFS_Open(rm_littlefs_ctrl_t * p_ctrl, rm_littlefs_cfg_t const * p_cfg);
rm_littlefs_err_t RM_LITTLEFS_Close(rm_littlefs_ctrl_t * p_ctrl);
rm_littlefs_err_t RM_LITTLEFS_Format(rm_littlefs_ctrl_t * p_ctrl);
lfs_t * RM_LITTLEFS_GetLfs(rm_littlefs_ctrl_t * p_ctrl);
uint32_t RM_LITTLEFS_GetVersion(void);

#ifdef __cplusplus
}
#endif

#endif /* RM_LITTLEFS_RX_IF_H */


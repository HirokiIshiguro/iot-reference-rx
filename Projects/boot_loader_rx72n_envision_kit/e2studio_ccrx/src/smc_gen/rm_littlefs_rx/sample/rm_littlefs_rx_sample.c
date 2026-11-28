/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
#include <stdint.h>

#include "r_flash_rx_if.h"
#include "rm_littlefs_rx_if.h"

void rm_littlefs_rx_sample(void)
{
    static rm_littlefs_ctrl_t ctrl;
    rm_littlefs_cfg_t cfg;
    lfs_file_t file;
    uint8_t value[4] = { 1u, 2u, 3u, 4u };

    cfg.base_address = (uint32_t) FLASH_DF_BLOCK_0;
    cfg.region_size = 32768u;
    cfg.read_size = RM_LITTLEFS_CFG_READ_SIZE;
    cfg.prog_size = RM_LITTLEFS_CFG_PROG_SIZE;
    cfg.block_size = RM_LITTLEFS_CFG_BLOCK_SIZE;
    cfg.cache_size = RM_LITTLEFS_CFG_CACHE_SIZE;
    cfg.lookahead_size = RM_LITTLEFS_CFG_LOOKAHEAD_SIZE;
    cfg.block_cycles = RM_LITTLEFS_CFG_BLOCK_CYCLES;
    cfg.format_if_mount_failed = 1u;

    if (RM_LITTLEFS_SUCCESS != RM_LITTLEFS_Open(&ctrl, &cfg))
    {
        return;
    }

    if (0 == lfs_file_open(RM_LITTLEFS_GetLfs(&ctrl), &file, "key-index.bin", LFS_O_WRONLY | LFS_O_CREAT))
    {
        (void) lfs_file_write(RM_LITTLEFS_GetLfs(&ctrl), &file, value, sizeof(value));
        (void) lfs_file_close(RM_LITTLEFS_GetLfs(&ctrl), &file);
    }

    (void) RM_LITTLEFS_Close(&ctrl);
}


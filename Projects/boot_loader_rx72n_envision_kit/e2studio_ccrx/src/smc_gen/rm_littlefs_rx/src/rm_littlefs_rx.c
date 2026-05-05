/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#include "platform.h"
#include "r_flash_rx_if.h"
#include "rm_littlefs_rx_if.h"

#if (FLASH_CFG_DATA_FLASH_BGO)
#include "rm_rtos_abstraction_rx_if.h"
#endif

static int rm_littlefs_bd_read(const struct lfs_config * p_cfg,
                               lfs_block_t block,
                               lfs_off_t off,
                               void * p_buffer,
                               lfs_size_t size);
static int rm_littlefs_bd_prog(const struct lfs_config * p_cfg,
                               lfs_block_t block,
                               lfs_off_t off,
                               const void * p_buffer,
                               lfs_size_t size);
static int rm_littlefs_bd_erase(const struct lfs_config * p_cfg, lfs_block_t block);
static int rm_littlefs_bd_sync(const struct lfs_config * p_cfg);
static flash_err_t rm_littlefs_flash_open(rm_littlefs_ctrl_t * p_ctrl);
static rm_littlefs_err_t rm_littlefs_flash_wait_ready(void);

rm_littlefs_err_t RM_LITTLEFS_Open(rm_littlefs_ctrl_t * p_ctrl, rm_littlefs_cfg_t const * p_cfg)
{
    int lfs_err;

#if (RM_LITTLEFS_CFG_PARAM_CHECKING_ENABLE)
    if ((NULL == p_ctrl) || (NULL == p_cfg) || (0u == p_cfg->base_address) || (0u == p_cfg->region_size))
    {
        return RM_LITTLEFS_ERR_INVALID_ARGUMENT;
    }
#endif

    memset(p_ctrl, 0, sizeof(*p_ctrl));
    p_ctrl->base_address = p_cfg->base_address;
    p_ctrl->region_size = p_cfg->region_size;

    p_ctrl->lfs_cfg.context = p_ctrl;
    p_ctrl->lfs_cfg.read = rm_littlefs_bd_read;
    p_ctrl->lfs_cfg.prog = rm_littlefs_bd_prog;
    p_ctrl->lfs_cfg.erase = rm_littlefs_bd_erase;
    p_ctrl->lfs_cfg.sync = rm_littlefs_bd_sync;
    p_ctrl->lfs_cfg.read_size = (0u != p_cfg->read_size) ? p_cfg->read_size : RM_LITTLEFS_CFG_READ_SIZE;
    p_ctrl->lfs_cfg.prog_size = (0u != p_cfg->prog_size) ? p_cfg->prog_size : RM_LITTLEFS_CFG_PROG_SIZE;
    p_ctrl->lfs_cfg.block_size = (0u != p_cfg->block_size) ? p_cfg->block_size : RM_LITTLEFS_CFG_BLOCK_SIZE;
    p_ctrl->lfs_cfg.block_count = p_cfg->region_size / p_ctrl->lfs_cfg.block_size;
    p_ctrl->lfs_cfg.block_cycles = (0 != p_cfg->block_cycles) ? p_cfg->block_cycles : RM_LITTLEFS_CFG_BLOCK_CYCLES;
    p_ctrl->lfs_cfg.cache_size = (0u != p_cfg->cache_size) ? p_cfg->cache_size : RM_LITTLEFS_CFG_CACHE_SIZE;
    p_ctrl->lfs_cfg.lookahead_size = (0u != p_cfg->lookahead_size) ? p_cfg->lookahead_size : RM_LITTLEFS_CFG_LOOKAHEAD_SIZE;
    p_ctrl->lfs_cfg.read_buffer = p_ctrl->read_buffer;
    p_ctrl->lfs_cfg.prog_buffer = p_ctrl->prog_buffer;
    p_ctrl->lfs_cfg.lookahead_buffer = p_ctrl->lookahead_buffer;

    if ((p_ctrl->lfs_cfg.cache_size > RM_LITTLEFS_CFG_CACHE_SIZE) ||
        (p_ctrl->lfs_cfg.lookahead_size > RM_LITTLEFS_CFG_LOOKAHEAD_SIZE) ||
        (p_ctrl->lfs_cfg.block_count < 2u) ||
        (0u != (p_cfg->base_address % FLASH_DF_BLOCK_SIZE)) ||
        (0u != (p_ctrl->lfs_cfg.block_size % FLASH_DF_BLOCK_SIZE)) ||
        (p_ctrl->lfs_cfg.block_size < 128u) ||
        (0u != (p_ctrl->lfs_cfg.prog_size % FLASH_DF_MIN_PGM_SIZE)) ||
        (0u != (p_cfg->region_size % p_ctrl->lfs_cfg.block_size)))
    {
        return RM_LITTLEFS_ERR_INVALID_ARGUMENT;
    }

    if (FLASH_SUCCESS != rm_littlefs_flash_open(p_ctrl))
    {
        return RM_LITTLEFS_ERR_FLASH;
    }

    lfs_err = lfs_mount(&p_ctrl->lfs, &p_ctrl->lfs_cfg);
    if ((0 != lfs_err) &&
        ((0u != p_cfg->format_if_mount_failed) || (0u != RM_LITTLEFS_CFG_FORMAT_IF_MOUNT_FAILED)))
    {
        lfs_err = lfs_format(&p_ctrl->lfs, &p_ctrl->lfs_cfg);
        if (0 == lfs_err)
        {
            lfs_err = lfs_mount(&p_ctrl->lfs, &p_ctrl->lfs_cfg);
        }
    }

    if (0 != lfs_err)
    {
        if (0u != p_ctrl->close_flash_on_close)
        {
            (void) R_FLASH_Close();
        }
        memset(p_ctrl, 0, sizeof(*p_ctrl));
        return RM_LITTLEFS_ERR_MOUNT;
    }

    p_ctrl->opened = 1u;
    return RM_LITTLEFS_SUCCESS;
}

rm_littlefs_err_t RM_LITTLEFS_Close(rm_littlefs_ctrl_t * p_ctrl)
{
#if (RM_LITTLEFS_CFG_PARAM_CHECKING_ENABLE)
    if (NULL == p_ctrl)
    {
        return RM_LITTLEFS_ERR_INVALID_ARGUMENT;
    }
#endif

    if (0u == p_ctrl->opened)
    {
        return RM_LITTLEFS_ERR_NOT_OPEN;
    }

    (void) lfs_unmount(&p_ctrl->lfs);
    if (0u != p_ctrl->close_flash_on_close)
    {
        (void) R_FLASH_Close();
    }
    memset(p_ctrl, 0, sizeof(*p_ctrl));
    return RM_LITTLEFS_SUCCESS;
}

rm_littlefs_err_t RM_LITTLEFS_Format(rm_littlefs_ctrl_t * p_ctrl)
{
    int lfs_err;

    if ((NULL == p_ctrl) || (0u == p_ctrl->base_address))
    {
        return RM_LITTLEFS_ERR_INVALID_ARGUMENT;
    }

    if (0u != p_ctrl->opened)
    {
        (void) lfs_unmount(&p_ctrl->lfs);
        p_ctrl->opened = 0u;
    }

    lfs_err = lfs_format(&p_ctrl->lfs, &p_ctrl->lfs_cfg);
    if (0 != lfs_err)
    {
        return RM_LITTLEFS_ERR_FORMAT;
    }

    lfs_err = lfs_mount(&p_ctrl->lfs, &p_ctrl->lfs_cfg);
    if (0 != lfs_err)
    {
        return RM_LITTLEFS_ERR_MOUNT;
    }

    p_ctrl->opened = 1u;
    return RM_LITTLEFS_SUCCESS;
}

lfs_t * RM_LITTLEFS_GetLfs(rm_littlefs_ctrl_t * p_ctrl)
{
    if ((NULL == p_ctrl) || (0u == p_ctrl->opened))
    {
        return NULL;
    }
    return &p_ctrl->lfs;
}

uint32_t RM_LITTLEFS_GetVersion(void)
{
    return (RM_LITTLEFS_RX_VERSION_MAJOR << 16) | RM_LITTLEFS_RX_VERSION_MINOR;
}

static int rm_littlefs_bd_read(const struct lfs_config * p_cfg,
                               lfs_block_t block,
                               lfs_off_t off,
                               void * p_buffer,
                               lfs_size_t size)
{
    rm_littlefs_ctrl_t * p_ctrl = (rm_littlefs_ctrl_t *) p_cfg->context;
    uint32_t address = p_ctrl->base_address + ((uint32_t) block * p_cfg->block_size) + off;
    memcpy(p_buffer, (void const *) address, size);
    return 0;
}

static int rm_littlefs_bd_prog(const struct lfs_config * p_cfg,
                               lfs_block_t block,
                               lfs_off_t off,
                               const void * p_buffer,
                               lfs_size_t size)
{
    rm_littlefs_ctrl_t * p_ctrl = (rm_littlefs_ctrl_t *) p_cfg->context;
    uint32_t address = p_ctrl->base_address + ((uint32_t) block * p_cfg->block_size) + off;

    if (FLASH_SUCCESS != R_FLASH_Write((uint32_t) (uintptr_t) p_buffer, address, size))
    {
        return LFS_ERR_IO;
    }
    return (RM_LITTLEFS_SUCCESS == rm_littlefs_flash_wait_ready()) ? 0 : LFS_ERR_IO;
}

static int rm_littlefs_bd_erase(const struct lfs_config * p_cfg, lfs_block_t block)
{
    rm_littlefs_ctrl_t * p_ctrl = (rm_littlefs_ctrl_t *) p_cfg->context;
    uint32_t address = p_ctrl->base_address + ((uint32_t) block * p_cfg->block_size);
    uint32_t blocks = p_cfg->block_size / FLASH_DF_BLOCK_SIZE;

    if (FLASH_SUCCESS != R_FLASH_Erase((flash_block_address_t) address, blocks))
    {
        return LFS_ERR_IO;
    }
    return (RM_LITTLEFS_SUCCESS == rm_littlefs_flash_wait_ready()) ? 0 : LFS_ERR_IO;
}

static int rm_littlefs_bd_sync(const struct lfs_config * p_cfg)
{
    (void) p_cfg;
    return (RM_LITTLEFS_SUCCESS == rm_littlefs_flash_wait_ready()) ? 0 : LFS_ERR_IO;
}

static flash_err_t rm_littlefs_flash_open(rm_littlefs_ctrl_t * p_ctrl)
{
    flash_err_t err = R_FLASH_Open();
    if (FLASH_ERR_ALREADY_OPEN == err)
    {
        p_ctrl->close_flash_on_close = 0u;
        return FLASH_SUCCESS;
    }
    if (FLASH_SUCCESS == err)
    {
        p_ctrl->close_flash_on_close = 1u;
    }
    return err;
}

static rm_littlefs_err_t rm_littlefs_flash_wait_ready(void)
{
    flash_err_t err;
    do
    {
        err = R_FLASH_Control(FLASH_CMD_STATUS_GET, NULL);
#if (FLASH_CFG_DATA_FLASH_BGO)
        if (FLASH_ERR_BUSY == err)
        {
            (void) RM_RTOS_ABSTRACTION_SleepTask(RM_LITTLEFS_CFG_FLASH_WAIT_TASK_ID);
        }
#endif
    } while (FLASH_ERR_BUSY == err);

    return (FLASH_SUCCESS == err) ? RM_LITTLEFS_SUCCESS : RM_LITTLEFS_ERR_FLASH;
}

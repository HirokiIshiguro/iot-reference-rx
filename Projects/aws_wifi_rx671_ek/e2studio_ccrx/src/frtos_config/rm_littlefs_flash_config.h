/*
 * Copyright (c) 2026 Renesas Electronics Corporation and/or its affiliates
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

/***********************************************************************************************************************
 * File Name    : rm_littlefs_flash_config.h
 * Description  : LittleFS data flash configuration for EK-RX671.
 **********************************************************************************************************************/

#ifndef FRTOS_CONFIG_RM_LITTLEFS_FLASH_CONFIG_H_
#define FRTOS_CONFIG_RM_LITTLEFS_FLASH_CONFIG_H_

#include "rm_littlefs_df_rx65n.h"

#define LFS_FLASH_READ_SIZE             (1)
#define LFS_FLASH_PROGRAM_SIZE          (4)
#define LFS_FLASH_BLOCK_SIZE            (128)
#define LFS_FLASH_BLOCK_COUNT           (64)
#define RM_LITTLEFS_FLASH_DATA_START    FLASH_DF_BLOCK_0_MACRO

#if (LFS_FLASH_BLOCK_SIZE * LFS_FLASH_BLOCK_COUNT + (RM_LITTLEFS_FLASH_DATA_START - FLASH_DF_BLOCK_0_MACRO)) > \
    BSP_DATA_FLASH_SIZE_BYTES
#error "Too many blocks"
#endif

#endif /* FRTOS_CONFIG_RM_LITTLEFS_FLASH_CONFIG_H_ */

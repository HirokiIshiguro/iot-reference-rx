/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/
/**********************************************************************************************************************
 * File Name    : r_fwup_private.h
 * Description  : Functions for using Firmware update.
 **********************************************************************************************************************
 * History : DD.MM.YYYY Version Description
 *         : 20.07.2023 2.00    First Release
 *         : 29.09.2023 2.01    Fixed log messages.
 *                              Add parameter checking.
 *                              Added arguments to R_FWUP_WriteImageProgram API.
 *         : 28.03.2024 2.02    Update wrapper functions.
 *         : 09.04.2024 2.03    Fixed wrapper function.
 *         : 15.10.2024 2.04    Fixed wrapper function.
 *         : 24.10.2025 2.05    V205 Release.
 *         : 23.01.2025 2.06    V206 Release.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include <stdio.h>
#include <string.h>
#include "platform.h"
#include "r_fwup_config.h"

#ifndef R_FWUP_PRIVATE_H
#define R_FWUP_PRIVATE_H

/**********************************************************************************************************************
 Macro definitions
 *********************************************************************************************************************/
#if (FWUP_CFG_PRINTF_DISABLE == 1)
#define FWUP_LOG_ERR(...)
#define FWUP_LOG_INFO(...)
#define FWUP_LOG_DBG(...)
#else
#define FWUP_LOG_ERR                printf
#define FWUP_LOG_INFO               printf
#define FWUP_LOG_DBG                printf
#endif /* (FWUP_CFG_PRINTF_DISABLE == 1) */


#define FWUP_IMAGE_BLOCKS           (31)
#define FWUP_MAGIC_CODE_LEN         (7)
#define FWUP_SIG_TYPE_LENGTH        (32)
#define FWUP_SIG_SIZE_MAX           (64)

/**********************************************************************************************************************
 Global Typedef definitions
 *********************************************************************************************************************/
/* Firmware header */
typedef struct st_fw_header
{
    uint8_t  magic_code[FWUP_MAGIC_CODE_LEN];
    uint8_t  image_flag;
    uint8_t  sig_type[FWUP_SIG_TYPE_LENGTH];
    uint32_t sig_size;
    uint8_t  sig[FWUP_SIG_SIZE_MAX];
    uint32_t image_file_size;
    uint8_t  rsv[400];
} st_fw_header_t;

/* Firmware descriptor */
typedef struct st_fw_image
{
    uint32_t addr;
    uint32_t size;
} st_fw_image_t;

typedef struct st_fw_desc
{
    uint32_t n;
    st_fw_image_t fw[FWUP_IMAGE_BLOCKS];
    uint8_t  rsv[4];
} st_fw_desc_t;

/* Firmware control block */
typedef struct st_fw_ctrlblk
{
    st_fw_header_t head;
    st_fw_desc_t   desc;
} st_fw_ctrlblk_t;

/**********************************************************************************************************************
 External global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Exported global functions
 *********************************************************************************************************************/

#endif /* R_FWUP_PRIVATE_H */

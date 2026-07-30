/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/
/**********************************************************************************************************************
 * File Name    : r_fwup_wrap_flash.h
 * Description  : Functions for the Firmware update module.
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

/**********************************************************************************************************************
 Macro definitions
 *********************************************************************************************************************/
#ifndef R_FWUP_WRAP_FLASH_H_
#define R_FWUP_WRAP_FLASH_H_

/* Flash functions */
#if (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT)
#define FWUP_FUNC_BUFFER_AREA_ERASE               r_fwup_wrap_ext_flash_erase
#define FWUP_FUNC_BUFFER_AREA_WRITE               r_fwup_wrap_ext_flash_write
#define FWUP_FUNC_BUFFER_AREA_READ                r_fwup_wrap_ext_flash_read
#else
#define FWUP_FUNC_BUFFER_AREA_ERASE               r_fwup_wrap_flash_erase
#define FWUP_FUNC_BUFFER_AREA_WRITE               r_fwup_wrap_flash_write
#define FWUP_FUNC_BUFFER_AREA_READ                r_fwup_wrap_flash_read
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT) */

/**********************************************************************************************************************
 Global Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 External global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Exported global functions
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_flash_open  (void);
void         r_fwup_wrap_flash_close (void);
e_fwup_err_t r_fwup_wrap_flash_erase (uint32_t addr, uint32_t num_blocks);
e_fwup_err_t r_fwup_wrap_flash_write (uint32_t src_addr, uint32_t dest_addr, uint32_t num_bytes);
e_fwup_err_t r_fwup_wrap_flash_read  (uint32_t buf_addr, uint32_t src_addr, uint32_t size);
#if (FWUP_CFG_UPDATE_MODE == FWUP_DUAL_BANK)
e_fwup_err_t r_fwup_wrap_bank_swap   (void);
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_DUAL_BANK) */

#if (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT)
e_fwup_err_t r_fwup_wrap_ext_flash_open  (void);
void         r_fwup_wrap_ext_flash_close (void);
e_fwup_err_t r_fwup_wrap_ext_flash_erase (uint32_t offsetadd, uint32_t num_sectors);
e_fwup_err_t r_fwup_wrap_ext_flash_write (uint32_t src_addr, uint32_t dest_addr, uint32_t num_bytes);
e_fwup_err_t r_fwup_wrap_ext_flash_read  (uint32_t buf_addr, uint32_t src_addr, uint32_t size);
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT) */

#endif /* R_FWUP_WRAP_FLASH_H_ */

/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/
/**********************************************************************************************************************
 * File Name    : r_fwup_wrap_flash.c
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
#include "r_fwup_if.h"
#include "r_fwup_wrap_com.h"
#include "r_fwup_wrap_flash.h"

#include "r_flash_rx_if.h"
#if (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT)
#include "r_flash_spi_if.h"
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT) */

/**********************************************************************************************************************
 Macro definitions
 *********************************************************************************************************************/
#if (defined(FLASH_SPI_CFG_USE_FIT) && (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT))
/* Sector Erase busy timeout 480*1ms = 0.48s  */
#define FLASH_SE_BUSY_WAIT      (uint32_t)(480)
/* Chip Erase busy timeout 630,000*1ms = 630s */
#define FLASH_CE_BUSY_WAIT      (uint32_t)(630000)
/* Page Program time out 4*1ms = 4ms */
#define FLASH_PP_BUSY_WAIT      (uint32_t)(4)
#endif /* (defined(FLASH_SPI_CFG_USE_FIT) && (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT)) */

/**********************************************************************************************************************
 Local Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Exported global variables
 *********************************************************************************************************************/
#if (FWUP_CFG_USER_FLASH_OPEN_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_FLASH_OPEN_FUNCTION(void);
#endif /* (FWUP_CFG_USER_FLASH_OPEN_ENABLED != 0) */

#if (FWUP_CFG_USER_FLASH_CLOSE_ENABLED != 0)
void FWUP_CFG_USER_FLASH_CLOSE_FUNCTION(void);
#endif /* (FWUP_CFG_USER_FLASH_CLOSE_ENABLED != 0) */

#if (FWUP_CFG_USER_FLASH_ERASE_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_FLASH_ERASE_FUNCTION(uint32_t addr, uint32_t num_blocks);
#endif /* (FWUP_CFG_USER_FLASH_ERASE_ENABLED != 0) */

#if (FWUP_CFG_USER_FLASH_WRITE_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_FLASH_WRITE_FUNCTION(uint32_t src_addr, uint32_t dest_addr, uint32_t num_bytes);
#endif /* (FWUP_CFG_USER_FLASH_WRITE_ENABLED != 0) */

#if (FWUP_CFG_USER_FLASH_READ_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_FLASH_READ_FUNCTION(uint32_t buf_addr, uint32_t src_addr, uint32_t size);
#endif /* (FWUP_CFG_USER_FLASH_READ_ENABLED != 0) */

#if (FWUP_CFG_UPDATE_MODE == FWUP_DUAL_BANK)
#if (FWUP_CFG_USER_BANK_SWAP_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_BANK_SWAP_FUNCTION(void);
#endif /* (FWUP_CFG_USER_BANK_SWAP_ENABLED != 0) */
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_DUAL_BANK) */

#if (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT)
#if (FWUP_CFG_USER_EXT_FLASH_OPEN_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_EXT_FLASH_OPEN_FUNCTION(void);
#endif /* (FWUP_CFG_USER_EXT_FLASH_OPEN_ENABLED != 0) */

#if (FWUP_CFG_USER_EXT_FLASH_CLOSE_ENABLED != 0)
void FWUP_CFG_USER_EXT_FLASH_CLOSE_FUNCTION(void);
#endif /* (FWUP_CFG_USER_EXT_FLASH_CLOSE_ENABLED != 0) */

#if (FWUP_CFG_USER_EXT_FLASH_ERASE_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_EXT_FLASH_ERASE_FUNCTION(uint32_t offsetadd, uint32_t num_sectors);
#endif /* (FWUP_CFG_USER_EXT_FLASH_ERASE_ENABLED != 0) */

#if (FWUP_CFG_USER_EXT_FLASH_WRITE_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_EXT_FLASH_WRITE_FUNCTION(uint32_t src_addr, uint32_t dest_addr, uint32_t num_bytes);
#endif /* (FWUP_CFG_USER_EXT_FLASH_WRITE_ENABLED != 0) */

#if (FWUP_CFG_USER_EXT_FLASH_READ_ENABLED != 0)
e_fwup_err_t FWUP_CFG_USER_EXT_FLASH_READ_FUNCTION(uint32_t buf_addr, uint32_t src_addr, uint32_t size);
#endif /* (FWUP_CFG_USER_EXT_FLASH_READ_ENABLED != 0) */
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT) */

/**********************************************************************************************************************
 Private (static) variables and functions
 *********************************************************************************************************************/
#if (defined(FLASH_SPI_CFG_USE_FIT) && (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT))
static uint8_t s_dev_no = FLASH_SPI_DEV0;
static uint8_t s_config[4];
#endif /* (defined(FLASH_SPI_CFG_USE_FIT) && (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT)) */

/*
 * Internal flash
 */
/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_flash_open
 * Description  : wrapper function for initializing Flash module.
 * Arguments    : None
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash open error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_flash_open(void)
{
#if (FWUP_CFG_USER_FLASH_OPEN_ENABLED == 1)
    return FWUP_CFG_USER_FLASH_OPEN_FUNCTION();
#else
    if (FLASH_SUCCESS != R_FLASH_Open())
    {
        return (FWUP_ERR_FLASH);
    }
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_FLASH_OPEN_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_flash_open
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_flash_close
 * Description  : wrapper function for closing Flash module.
 * Arguments    : None
 * Return Value : None
 *********************************************************************************************************************/
void r_fwup_wrap_flash_close(void)
{
#if (FWUP_CFG_USER_FLASH_CLOSE_ENABLED == 1)
    FWUP_CFG_USER_FLASH_CLOSE_FUNCTION();
#else
    R_FLASH_Close();
#endif /* (FWUP_CFG_USER_FLASH_CLOSE_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_flash_close
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_flash_erase
 * Description  : wrapper function for erasing Flash.
 * Arguments    : addr           : erasure destination address
 *                num_blocks     : number of blocks to erase
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash erase error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_flash_erase(uint32_t addr, uint32_t num_blocks)
{
#if (FWUP_CFG_USER_FLASH_ERASE_ENABLED == 1)
    return FWUP_CFG_USER_FLASH_ERASE_FUNCTION(addr, num_blocks);
#else

    uint32_t blk_addr;
    flash_err_t ret;

#if (FLASH_TYPE == FLASH_TYPE_1)
    blk_addr = addr;
#else
    if((FLASH_DF_BLOCK_0 <= addr) && (addr < FLASH_DF_BLOCK_INVALID ))
    {
        blk_addr = addr;
    }
    else
    {
        blk_addr = addr + (FWUP_CFG_CF_BLK_SIZE * (num_blocks - 1));
    }
#endif /* (FLASH_TYPE == FLASH_TYPE_1) */

#if (defined(MCU_RX130) && (MCU_ROM_SIZE_BYTES > 0x40000L))
    /* For parts with CF > 256K, erase and blankcheck cannot cross 256k boundary */
    if ((blk_addr > (uint32_t)FLASH_CF_BLOCK_INVALID) && 
        (blk_addr < (uint32_t)FLASH_CF_256KBOUNDARY) &&
        ((blk_addr + (num_blocks * FLASH_CF_BLOCK_SIZE) - 1) > (uint32_t)FLASH_CF_256KBOUNDARY))
    {
        uint32_t tmp_num_blocks = ((uint32_t)FLASH_CF_256KBOUNDARY - addr) / FLASH_CF_BLOCK_SIZE;
        r_fwup_wrap_disable_interrupt();
        ret = R_FLASH_Erase((flash_block_address_t )blk_addr, tmp_num_blocks);
        r_fwup_wrap_enable_interrupt();
        if (FLASH_SUCCESS != ret)
        {
            return (FWUP_ERR_FLASH);
        }
        blk_addr = (uint32_t)FLASH_CF_256KBOUNDARY;
        num_blocks -= tmp_num_blocks;
    }
#endif /* (defined(MCU_RX130) && (MCU_ROM_SIZE_BYTES > 0x40000L)) */

    r_fwup_wrap_disable_interrupt();
    ret = R_FLASH_Erase((flash_block_address_t )blk_addr, num_blocks);
    r_fwup_wrap_enable_interrupt();
    if (FLASH_SUCCESS != ret)
    {
        return (FWUP_ERR_FLASH);
    }
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_FLASH_ERASE_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_flash_erase
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_flash_write
 * Description  : wrapper function for writing Flash.
 * Arguments    : src_addr       : write source address
 *                dest_addr      : write destination address
 *                num_bytes      : number of bytes to write
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash write error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_flash_write(uint32_t src_addr, uint32_t dest_addr, uint32_t num_bytes)
{
#if (FWUP_CFG_USER_FLASH_WRITE_ENABLED == 1)
    return FWUP_CFG_USER_FLASH_WRITE_FUNCTION(src_addr, dest_addr, num_bytes);
#else
    r_fwup_wrap_disable_interrupt();
    flash_err_t ret = R_FLASH_Write(src_addr, dest_addr, num_bytes);
    r_fwup_wrap_enable_interrupt();
    if (FLASH_SUCCESS != ret)
    {
        return (FWUP_ERR_FLASH);
    }
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_FLASH_WRITE_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_flash_write
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_flash_read
 * Description  : wrapper function for reading Flash.
 * Arguments    : buf_addr     : storage destination address
 *                src_addr     : read source address
 *                size         : number of bytes to read
 * Return Value : FWUP_SUCCESS : success
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_flash_read(uint32_t buf_addr, uint32_t src_addr, uint32_t size)
{
#if (FWUP_CFG_USER_FLASH_READ_ENABLED == 1)
    return FWUP_CFG_USER_FLASH_READ_FUNCTION(buf_addr, src_addr, size);
#else

    MEMCPY((void FWUP_FAR *)buf_addr, (void FWUP_FAR *)src_addr, size);
    return (FWUP_SUCCESS);

#endif /* (FWUP_CFG_USER_FLASH_READ_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_flash_read
 *********************************************************************************************************************/

#if (FWUP_CFG_UPDATE_MODE == FWUP_DUAL_BANK)
/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_bank_swap
 * Description  : wrapper function for bank swap.
 * Arguments    : none
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash control error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_bank_swap(void)
{
#if (FWUP_CFG_USER_BANK_SWAP_ENABLED == 1)
    return FWUP_CFG_USER_BANK_SWAP_FUNCTION();
#else
    flash_err_t err;

    r_fwup_wrap_disable_interrupt();
    err = R_FLASH_Control(FLASH_CMD_BANK_TOGGLE, NULL);
    r_fwup_wrap_enable_interrupt();

    if (FLASH_SUCCESS != err)
    {
        return (FWUP_ERR_FLASH);
    }
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_BANK_SWAP_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_bank_swap
 *********************************************************************************************************************/
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_DUAL_BANK) */

#if (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT)
/*
 * External flash
 */
#if (defined(FLASH_SPI_CFG_USE_FIT))
/**********************************************************************************************************************
 * Function Name: ext_flash_busy_check
 * Description  : function for confirming completion of writing or erasing.
 * Arguments    : mode              : device number (0, 1)
 *              : loop_cnt          : Count in milliseconds
 * Return Value : FLASH_SPI_SUCCESS : success
 *                FLASH_SPI_ERR_*** : error
 *********************************************************************************************************************/
static flash_spi_status_t ext_flash_busy_check(flash_spi_poll_mode_t mode, uint32_t loop_cnt)
{
    flash_spi_status_t ret = FLASH_SPI_SUCCESS_BUSY;
    do
    {
        /* FLASH is busy. */
        ret = R_FLASH_SPI_Polling(s_dev_no, mode);
        if (FLASH_SPI_SUCCESS_BUSY != ret)
        {
            /* FLASH is ready or error. */
            break;
        }
        loop_cnt--;
        R_BSP_SoftwareDelay(1, BSP_DELAY_MILLISECS);     /* 1ms */
    }
    while (0 != loop_cnt);
    return ret;
}
/**********************************************************************************************************************
 End of function ext_flash_busy_check
 *********************************************************************************************************************/
#endif /* defined(FLASH_SPI_CFG_USE_FIT) */

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_ext_flash_open
 * Description  : wrapper function for opening external Flash.
 * Arguments    : None
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash open error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_ext_flash_open(void)
{
#if (FWUP_CFG_USER_EXT_FLASH_OPEN_ENABLED == 1)
    return FWUP_CFG_USER_EXT_FLASH_OPEN_FUNCTION();
#else
#if (defined(FLASH_SPI_CFG_USE_FIT))
    if (FLASH_SPI_SUCCESS > R_FLASH_SPI_Open(s_dev_no))
    {
        return (FWUP_ERR_FLASH);
    }
    if (FLASH_SPI_SUCCESS != ext_flash_busy_check(FLASH_SPI_MODE_ERASE_POLL, FLASH_CE_BUSY_WAIT))
    {
        return (FWUP_ERR_FLASH);
    }
    if (FLASH_SPI_SUCCESS > R_FLASH_SPI_Set_4byte_Address_Mode(s_dev_no))
    {
        return (FWUP_ERR_FLASH);
    }

    /* Read configuration register */
    if (FLASH_SPI_SUCCESS > R_FLASH_SPI_Read_Configuration(s_dev_no, &s_config[0]))
    {
        return (FWUP_ERR_FLASH);
    }
#else
#warning "r_fwup_wrap_ext_flash_open is not implemented. Please add Serial Flash memory FIT module."
#endif /* defined(FLASH_SPI_CFG_USE_FIT) */
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_EXT_FLASH_OPEN_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_ext_flash_open
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_ext_flash_close
 * Description  : wrapper function for closing external Flash.
 * Arguments    : None
 * Return Value : None
 *********************************************************************************************************************/
void r_fwup_wrap_ext_flash_close(void)
{
#if (FWUP_CFG_USER_EXT_FLASH_CLOSE_ENABLED == 1)
    FWUP_CFG_USER_EXT_FLASH_CLOSE_FUNCTION();
#else
#if (defined(FLASH_SPI_CFG_USE_FIT))
    R_FLASH_SPI_Close(s_dev_no);
#else
#warning "r_fwup_wrap_ext_flash_close is not implemented. Please add Serial Flash memory FIT module."
#endif /* defined(FLASH_SPI_CFG_USE_FIT) */
#endif /* (FWUP_CFG_USER_EXT_FLASH_CLOSE_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_ext_flash_close
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_ext_flash_erase
 * Description  : wrapper function for erasing external Flash.
 * Arguments    : addr           : erasure destination address
 *              : num_sectors    : number of sectors to erase
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash erase error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_ext_flash_erase(uint32_t addr, uint32_t num_sectors)
{
#if (FWUP_CFG_USER_EXT_FLASH_ERASE_ENABLED == 1)
    return FWUP_CFG_USER_EXT_FLASH_ERASE_FUNCTION(addr, num_sectors);
#else
#if (defined(FLASH_SPI_CFG_USE_FIT))
    flash_spi_erase_info_t flash_info_e;
    uint32_t               sector_count;

    for (sector_count = 0; sector_count < num_sectors; sector_count++ )
    {
        flash_info_e.addr = addr + (FWUP_CFG_EXT_BUF_AREA_BLK_SIZE * sector_count);
        flash_info_e.mode = FLASH_SPI_MODE_S_ERASE;
        if (FLASH_SPI_SUCCESS > R_FLASH_SPI_Erase(s_dev_no, &flash_info_e))
        {
            return (FWUP_ERR_FLASH);
        }
        if (FLASH_SPI_SUCCESS > ext_flash_busy_check(FLASH_SPI_MODE_ERASE_POLL, FLASH_SE_BUSY_WAIT))
        {
            return (FWUP_ERR_FLASH);
        }
    }
#else
#warning "r_fwup_wrap_ext_flash_erase is not implemented. Please add Serial Flash memory FIT module."
#endif /* defined(FLASH_SPI_CFG_USE_FIT) */
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_EXT_FLASH_ERASE_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_ext_flash_erase
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_ext_flash_write
 * Description  : wrapper function for writing external Flash.
 * Arguments    : src_addr       : write source address
 *              : dest_addr      : write destination address
 *              : num_bytes      : number of bytes to write
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash write error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_ext_flash_write(uint32_t src_addr, uint32_t dest_addr, uint32_t num_bytes)
{
#if (FWUP_CFG_USER_EXT_FLASH_WRITE_ENABLED == 1)
    return FWUP_CFG_USER_EXT_FLASH_WRITE_FUNCTION(src_addr, dest_addr, num_bytes);
#else
#if (defined(FLASH_SPI_CFG_USE_FIT))
    flash_spi_info_t flash_info_w;
    flash_info_w.addr   = dest_addr;
    flash_info_w.cnt    = num_bytes;
    flash_info_w.p_data = (uint8_t *)(src_addr);
    flash_info_w.op_mode = FLASH_SPI_SINGLE;
    if (FLASH_SPI_SUCCESS > R_FLASH_SPI_Write_Data_Page(s_dev_no, &flash_info_w))
    {
        return (FWUP_ERR_FLASH);
    }
    if (FLASH_SPI_SUCCESS > ext_flash_busy_check(FLASH_SPI_MODE_PROG_POLL, FLASH_PP_BUSY_WAIT))
    {
        return (FWUP_ERR_FLASH);
    }
#else
#warning "r_fwup_wrap_ext_flash_write is not implemented. Please add Serial Flash memory FIT module."
#endif /* defined(FLASH_SPI_CFG_USE_FIT) */
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_EXT_FLASH_WRITE_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_ext_flash_write
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_ext_flash_read
 * Description  : wrapper function for reading external Flash.
 * Arguments    : buf_addr       : storage destination address
 *              : src_addr       : read source address
 *              : size           : number of bytes to read
 * Return Value : FWUP_SUCCESS   : success
 *                FWUP_ERR_FLASH : flash read error
 *********************************************************************************************************************/
e_fwup_err_t r_fwup_wrap_ext_flash_read(uint32_t buf_addr, uint32_t src_addr, uint32_t size)
{
#if (FWUP_CFG_USER_EXT_FLASH_READ_ENABLED == 1)
    return FWUP_CFG_USER_EXT_FLASH_READ_FUNCTION(buf_addr, src_addr, size);
#else
#if (defined(FLASH_SPI_CFG_USE_FIT))
    flash_spi_info_t flash_info_r;
    flash_info_r.addr   = src_addr;
    flash_info_r.cnt    = size;
    flash_info_r.p_data = (uint8_t *)(buf_addr);
    flash_info_r.op_mode = FLASH_SPI_SINGLE;
    if (FLASH_SPI_SUCCESS > R_FLASH_SPI_Read_Data(s_dev_no, &flash_info_r))
    {
        return (FWUP_ERR_FLASH);
    }
#else
#warning "r_fwup_wrap_ext_flash_read is not implemented. Please add Serial Flash memory FIT module."
#endif /* defined(FLASH_SPI_CFG_USE_FIT) */
    return (FWUP_SUCCESS);
#endif /* (FWUP_CFG_USER_EXT_FLASH_READ_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_ext_flash_read
 *********************************************************************************************************************/
#endif /* (FWUP_CFG_UPDATE_MODE == FWUP_SINGLE_BANK_W_BUFFER_EXT) */

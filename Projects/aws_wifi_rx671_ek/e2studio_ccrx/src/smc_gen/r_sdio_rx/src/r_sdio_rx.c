/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
/***********************************************************************************************************************
* File Name    : r_sdio_rx.c
* Description  : SDIO protocol helpers for the r_sdio_rx FIT module.
***********************************************************************************************************************/

/***********************************************************************************************************************
Includes
***********************************************************************************************************************/
#include "r_sdio_rx_if.h"

/***********************************************************************************************************************
Private function prototypes
***********************************************************************************************************************/
static sdio_err_t sdio_check_open(sdio_hdl_t const hdl);
static sdio_err_t sdio_check_function(uint8_t function);
static sdio_err_t sdio_check_address(uint32_t address);
static sdio_err_t sdio_check_cmd53_count(bool block_mode, uint32_t count);
static uint32_t   sdio_cis_pointer_base(uint8_t function);

/***********************************************************************************************************************
Exported global functions
***********************************************************************************************************************/
sdio_err_t R_SDIO_Open(sdio_hdl_t const hdl, const sdio_cfg_t * const p_cfg)
{
    if ((NULL == hdl) || (NULL == p_cfg) || (NULL == p_cfg->p_cmd52) || (NULL == p_cfg->p_cmd53))
    {
        return SDIO_ERR_NULL_PTR;
    }

    if (hdl->open)
    {
        return SDIO_ERR_ALREADY_OPEN;
    }

    hdl->p_cfg = p_cfg;
    hdl->open = true;
    hdl->brcm_sb_window = 0UL;
    hdl->brcm_sb_window_valid = false;

    return SDIO_SUCCESS;
}

sdio_err_t R_SDIO_Close(sdio_hdl_t const hdl)
{
    if (NULL == hdl)
    {
        return SDIO_ERR_NULL_PTR;
    }

    hdl->p_cfg = NULL;
    hdl->open = false;
    hdl->brcm_sb_window = 0UL;
    hdl->brcm_sb_window_valid = false;

    return SDIO_SUCCESS;
}

uint32_t R_SDIO_GetVersion(void)
{
    return ((SDIO_VERSION_MAJOR << 16) | SDIO_VERSION_MINOR);
}

uint32_t R_SDIO_MakeCmd52Arg(bool write, uint8_t function, uint32_t address, bool raw, uint8_t data)
{
    uint32_t arg = 0UL;

    if (write)
    {
        arg |= (1UL << 31);
    }

    arg |= (((uint32_t)function & 0x07UL) << 28);

    if (raw)
    {
        arg |= (1UL << 27);
    }

    arg |= ((address & SDIO_CMD52_MAX_REG_ADDR) << 9);
    arg |= (uint32_t)data;

    return arg;
}

uint32_t R_SDIO_MakeCmd53Arg(bool write, uint8_t function, uint32_t address, bool increment, bool block_mode,
                             uint32_t count)
{
    uint32_t arg = 0UL;

    if (write)
    {
        arg |= (1UL << 31);
    }

    arg |= (((uint32_t)function & 0x07UL) << 28);

    if (block_mode)
    {
        arg |= (1UL << 27);
    }

    if (increment)
    {
        arg |= (1UL << 26);
    }

    arg |= ((address & SDIO_CMD53_MAX_REG_ADDR) << 9);
    arg |= (count & 0x000001ffUL);

    return arg;
}

sdio_err_t R_SDIO_Cmd52Read(sdio_hdl_t const hdl, uint8_t function, uint32_t address, uint8_t * const p_data,
                            uint32_t * const p_r5)
{
    sdio_err_t err;
    sdio_cmd52_t args;

    err = sdio_check_open(hdl);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    if ((NULL == p_data) || (NULL == p_r5))
    {
        return SDIO_ERR_NULL_PTR;
    }

    err = sdio_check_function(function);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = sdio_check_address(address);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    args.write = false;
    args.function = function;
    args.address = address;
    args.raw = false;
    args.write_data = 0U;
    args.read_data = 0U;
    args.r5 = 0UL;

    err = hdl->p_cfg->p_cmd52(hdl->p_cfg->p_context, &args);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    *p_data = args.read_data;
    *p_r5 = args.r5;

    return SDIO_SUCCESS;
}

sdio_err_t R_SDIO_Cmd52Write(sdio_hdl_t const hdl, uint8_t function, uint32_t address, uint8_t data,
                             bool read_after_write, uint8_t * const p_readback, uint32_t * const p_r5)
{
    sdio_err_t err;
    sdio_cmd52_t args;

    err = sdio_check_open(hdl);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    if (NULL == p_r5)
    {
        return SDIO_ERR_NULL_PTR;
    }

    if ((read_after_write) && (NULL == p_readback))
    {
        return SDIO_ERR_NULL_PTR;
    }

    err = sdio_check_function(function);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = sdio_check_address(address);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    args.write = true;
    args.function = function;
    args.address = address;
    args.raw = read_after_write;
    args.write_data = data;
    args.read_data = 0U;
    args.r5 = 0UL;

    err = hdl->p_cfg->p_cmd52(hdl->p_cfg->p_context, &args);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    if (NULL != p_readback)
    {
        *p_readback = args.read_data;
    }
    *p_r5 = args.r5;

    return SDIO_SUCCESS;
}

sdio_err_t R_SDIO_Cmd53(sdio_hdl_t const hdl, sdio_cmd53_t * const p_args)
{
    sdio_err_t err;

    err = sdio_check_open(hdl);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    if ((NULL == p_args) || (NULL == p_args->p_data))
    {
        return SDIO_ERR_NULL_PTR;
    }

    err = sdio_check_function(p_args->function);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = sdio_check_address(p_args->address);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = sdio_check_cmd53_count(p_args->block_mode, p_args->count);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    return hdl->p_cfg->p_cmd53(hdl->p_cfg->p_context, p_args);
}

sdio_err_t R_SDIO_Cmd53ReadBytes(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                 uint8_t * const p_data, uint32_t length, uint32_t * const p_r5)
{
    sdio_err_t err;
    sdio_cmd53_t args;

    if (NULL == p_r5)
    {
        return SDIO_ERR_NULL_PTR;
    }

    args.write = false;
    args.function = function;
    args.address = address;
    args.increment = increment;
    args.block_mode = false;
    args.count = length;
    args.p_data = p_data;
    args.r5 = 0UL;

    err = R_SDIO_Cmd53(hdl, &args);
    *p_r5 = args.r5;

    return err;
}

sdio_err_t R_SDIO_Cmd53WriteBytes(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                  uint8_t * const p_data, uint32_t length, uint32_t * const p_r5)
{
    sdio_err_t err;
    sdio_cmd53_t args;

    if (NULL == p_r5)
    {
        return SDIO_ERR_NULL_PTR;
    }

    args.write = true;
    args.function = function;
    args.address = address;
    args.increment = increment;
    args.block_mode = false;
    args.count = length;
    args.p_data = p_data;
    args.r5 = 0UL;

    err = R_SDIO_Cmd53(hdl, &args);
    *p_r5 = args.r5;

    return err;
}

sdio_err_t R_SDIO_Cmd53ReadBlocks(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                  uint8_t * const p_data, uint32_t block_count, uint32_t * const p_r5)
{
    sdio_err_t err;
    sdio_cmd53_t args;

    if (NULL == p_r5)
    {
        return SDIO_ERR_NULL_PTR;
    }

    args.write = false;
    args.function = function;
    args.address = address;
    args.increment = increment;
    args.block_mode = true;
    args.count = block_count;
    args.p_data = p_data;
    args.r5 = 0UL;

    err = R_SDIO_Cmd53(hdl, &args);
    *p_r5 = args.r5;

    return err;
}

sdio_err_t R_SDIO_Cmd53WriteBlocks(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                   uint8_t * const p_data, uint32_t block_count, uint32_t * const p_r5)
{
    sdio_err_t err;
    sdio_cmd53_t args;

    if (NULL == p_r5)
    {
        return SDIO_ERR_NULL_PTR;
    }

    args.write = true;
    args.function = function;
    args.address = address;
    args.increment = increment;
    args.block_mode = true;
    args.count = block_count;
    args.p_data = p_data;
    args.r5 = 0UL;

    err = R_SDIO_Cmd53(hdl, &args);
    *p_r5 = args.r5;

    return err;
}

sdio_err_t R_SDIO_EnableFunction(sdio_hdl_t const hdl, uint8_t function, uint8_t * const p_ready,
                                 uint32_t * const p_r5)
{
    sdio_err_t err;
    uint8_t enable;
    uint8_t readback;
    uint8_t ready;
    uint8_t function_bit;
    uint32_t poll;
    uint32_t poll_count;

    if ((NULL == p_ready) || (NULL == p_r5))
    {
        return SDIO_ERR_NULL_PTR;
    }

    if ((SDIO_FUNCTION_0 == function) || (function > SDIO_MAX_FUNCTION))
    {
        return SDIO_ERR_INVALID_ARG;
    }

    function_bit = SDIO_INT_FUNCTION(function);

    err = R_SDIO_Cmd52Read(hdl, SDIO_FUNCTION_0, SDIO_CCCR_IO_ENABLE, &enable, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    enable = (uint8_t)(enable | function_bit);
    err = R_SDIO_Cmd52Write(hdl, SDIO_FUNCTION_0, SDIO_CCCR_IO_ENABLE, enable, true, &readback, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    poll_count = hdl->p_cfg->io_ready_poll_count;
    if (0UL == poll_count)
    {
        poll_count = SDIO_CFG_IO_READY_POLL_COUNT;
    }

    for (poll = 0UL; poll < poll_count; poll++)
    {
        err = R_SDIO_ReadIoReady(hdl, &ready, p_r5);
        if (SDIO_SUCCESS != err)
        {
            return err;
        }

        if (0U != (ready & function_bit))
        {
            *p_ready = ready;
            return SDIO_SUCCESS;
        }

        if (NULL != hdl->p_cfg->p_delay_ms)
        {
            hdl->p_cfg->p_delay_ms(hdl->p_cfg->p_context, 1UL);
        }
    }

    *p_ready = ready;
    return SDIO_ERR_TIMEOUT;
}

sdio_err_t R_SDIO_ReadIoReady(sdio_hdl_t const hdl, uint8_t * const p_ready, uint32_t * const p_r5)
{
    return R_SDIO_Cmd52Read(hdl, SDIO_FUNCTION_0, SDIO_CCCR_IO_READY, p_ready, p_r5);
}

sdio_err_t R_SDIO_EnableInterrupts(sdio_hdl_t const hdl, uint8_t int_enable, uint8_t * const p_readback,
                                   uint32_t * const p_r5)
{
    return R_SDIO_Cmd52Write(hdl, SDIO_FUNCTION_0, SDIO_CCCR_INT_ENABLE, int_enable, true, p_readback, p_r5);
}

sdio_err_t R_SDIO_ReadInterruptPending(sdio_hdl_t const hdl, uint8_t * const p_pending, uint32_t * const p_r5)
{
    return R_SDIO_Cmd52Read(hdl, SDIO_FUNCTION_0, SDIO_CCCR_INT_PENDING, p_pending, p_r5);
}

sdio_err_t R_SDIO_ReadCisPointer(sdio_hdl_t const hdl, uint8_t function, uint32_t * const p_pointer,
                                 uint32_t * const p_r5)
{
    sdio_err_t err;
    uint32_t base;
    uint8_t low;
    uint8_t middle;
    uint8_t high;

    if ((NULL == p_pointer) || (NULL == p_r5))
    {
        return SDIO_ERR_NULL_PTR;
    }

    err = sdio_check_function(function);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    base = sdio_cis_pointer_base(function);

    err = R_SDIO_Cmd52Read(hdl, SDIO_FUNCTION_0, base, &low, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = R_SDIO_Cmd52Read(hdl, SDIO_FUNCTION_0, base + 1UL, &middle, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = R_SDIO_Cmd52Read(hdl, SDIO_FUNCTION_0, base + 2UL, &high, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    *p_pointer = ((uint32_t)low) | ((uint32_t)middle << 8) | ((uint32_t)high << 16);

    return SDIO_SUCCESS;
}

uint32_t R_SDIO_BrcmBackplaneWindow(uint32_t address)
{
    return (address & SDIO_BRCM_SB_WINDOW_MASK);
}

uint32_t R_SDIO_BrcmBackplaneFunctionAddress(uint32_t address, uint32_t length)
{
    uint32_t f1_address = (address & SDIO_BRCM_SB_OFT_ADDR_MASK);

    if (4UL == length)
    {
        f1_address |= SDIO_BRCM_SB_ACCESS_2_4B_FLAG;
    }

    return f1_address;
}

void R_SDIO_BrcmInvalidateBackplaneWindow(sdio_hdl_t const hdl)
{
    if (NULL != hdl)
    {
        hdl->brcm_sb_window = 0UL;
        hdl->brcm_sb_window_valid = false;
    }
}

sdio_err_t R_SDIO_BrcmSetBackplaneWindow(sdio_hdl_t const hdl, uint32_t address, uint32_t * const p_window,
                                         uint32_t * const p_r5)
{
    sdio_err_t err;
    uint32_t window;
    uint8_t low;
    uint8_t middle;
    uint8_t high;
    uint8_t readback;

    err = sdio_check_open(hdl);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    if (NULL == p_r5)
    {
        return SDIO_ERR_NULL_PTR;
    }

    window = R_SDIO_BrcmBackplaneWindow(address);
    if (NULL != p_window)
    {
        *p_window = window;
    }

#if (SDIO_CFG_BACKPLANE_WINDOW_CACHE_ENABLE == 1)
    if ((hdl->brcm_sb_window_valid) && (window == hdl->brcm_sb_window))
    {
        *p_r5 = 0UL;
        return SDIO_SUCCESS;
    }
#endif

    high = (uint8_t)(window >> 24);
    middle = (uint8_t)(window >> 16);
    low = (uint8_t)(window >> 8);

    err = R_SDIO_Cmd52Write(hdl, 1U, SDIO_BRCM_FUNC1_SBADDRHIGH, high, true, &readback, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = R_SDIO_Cmd52Write(hdl, 1U, SDIO_BRCM_FUNC1_SBADDRMID, middle, true, &readback, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    err = R_SDIO_Cmd52Write(hdl, 1U, SDIO_BRCM_FUNC1_SBADDRLOW, low, true, &readback, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    hdl->brcm_sb_window = window;
    hdl->brcm_sb_window_valid = true;

    return SDIO_SUCCESS;
}

sdio_err_t R_SDIO_BrcmBackplaneRead(sdio_hdl_t const hdl, uint32_t address, bool increment, uint8_t * const p_data,
                                    uint32_t length, uint32_t * const p_r5)
{
    sdio_err_t err;
    uint32_t f1_address;

    err = R_SDIO_BrcmSetBackplaneWindow(hdl, address, NULL, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    f1_address = R_SDIO_BrcmBackplaneFunctionAddress(address, length);
    return R_SDIO_Cmd53ReadBytes(hdl, 1U, f1_address, increment, p_data, length, p_r5);
}

sdio_err_t R_SDIO_BrcmBackplaneWrite(sdio_hdl_t const hdl, uint32_t address, bool increment, uint8_t * const p_data,
                                     uint32_t length, uint32_t * const p_r5)
{
    sdio_err_t err;
    uint32_t f1_address;

    err = R_SDIO_BrcmSetBackplaneWindow(hdl, address, NULL, p_r5);
    if (SDIO_SUCCESS != err)
    {
        return err;
    }

    f1_address = R_SDIO_BrcmBackplaneFunctionAddress(address, length);
    return R_SDIO_Cmd53WriteBytes(hdl, 1U, f1_address, increment, p_data, length, p_r5);
}

/***********************************************************************************************************************
Private functions
***********************************************************************************************************************/
static sdio_err_t sdio_check_open(sdio_hdl_t const hdl)
{
    if (NULL == hdl)
    {
        return SDIO_ERR_NULL_PTR;
    }

    if ((!hdl->open) || (NULL == hdl->p_cfg))
    {
        return SDIO_ERR_NOT_OPEN;
    }

    if ((NULL == hdl->p_cfg->p_cmd52) || (NULL == hdl->p_cfg->p_cmd53))
    {
        return SDIO_ERR_NULL_PTR;
    }

    return SDIO_SUCCESS;
}

static sdio_err_t sdio_check_function(uint8_t function)
{
    if (function > SDIO_MAX_FUNCTION)
    {
        return SDIO_ERR_INVALID_ARG;
    }

    return SDIO_SUCCESS;
}

static sdio_err_t sdio_check_address(uint32_t address)
{
    if (address > SDIO_CMD52_MAX_REG_ADDR)
    {
        return SDIO_ERR_INVALID_ARG;
    }

    return SDIO_SUCCESS;
}

static sdio_err_t sdio_check_cmd53_count(bool block_mode, uint32_t count)
{
    if (0UL == count)
    {
        return SDIO_ERR_INVALID_ARG;
    }

    if (block_mode)
    {
        if (count > 511UL)
        {
            return SDIO_ERR_INVALID_ARG;
        }
    }
    else
    {
        if (count > SDIO_CFG_CMD53_MAX_BYTE_COUNT)
        {
            return SDIO_ERR_INVALID_ARG;
        }
    }

    return SDIO_SUCCESS;
}

static uint32_t sdio_cis_pointer_base(uint8_t function)
{
    uint32_t base;

    if (SDIO_FUNCTION_0 == function)
    {
        base = SDIO_CCCR_CIS_PTR0;
    }
    else
    {
        base = SDIO_FBR_BASE(function) + SDIO_FBR_CIS_PTR0;
    }

    return base;
}

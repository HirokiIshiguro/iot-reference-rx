/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
/***********************************************************************************************************************
* File Name    : r_sdio_rx_if.h
* Description  : Public interface for the r_sdio_rx FIT module.
***********************************************************************************************************************/
#ifndef R_SDIO_RX_IF_H
#define R_SDIO_RX_IF_H

/***********************************************************************************************************************
Includes
***********************************************************************************************************************/
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "platform.h"
#include "r_sdio_rx_config.h"

#ifdef __cplusplus
extern "C" {
#endif

/***********************************************************************************************************************
Macro definitions
***********************************************************************************************************************/
#define SDIO_VERSION_MAJOR                    (1UL)
#define SDIO_VERSION_MINOR                    (0UL)

#define SDIO_MAX_FUNCTION                     (7U)
#define SDIO_FUNCTION_0                       (0U)
#define SDIO_CMD52_MAX_REG_ADDR               (0x0001ffffUL)
#define SDIO_CMD53_MAX_REG_ADDR               (0x0001ffffUL)
#define SDIO_CMD53_BYTE_COUNT_512_ARG         (0U)

#define SDIO_CCCR_IO_ENABLE                   (0x02UL)
#define SDIO_CCCR_IO_READY                    (0x03UL)
#define SDIO_CCCR_INT_ENABLE                  (0x04UL)
#define SDIO_CCCR_INT_PENDING                 (0x05UL)
#define SDIO_CCCR_CIS_PTR0                    (0x09UL)
#define SDIO_CCCR_CIS_PTR1                    (0x0aUL)
#define SDIO_CCCR_CIS_PTR2                    (0x0bUL)

#define SDIO_FBR_BASE(function)               ((uint32_t)(function) << 8)
#define SDIO_FBR_STD_IF                       (0x00UL)
#define SDIO_FBR_EXT_IF                       (0x01UL)
#define SDIO_FBR_HIGH_POWER                   (0x02UL)
#define SDIO_FBR_CIS_PTR0                     (0x09UL)
#define SDIO_FBR_CIS_PTR1                     (0x0aUL)
#define SDIO_FBR_CIS_PTR2                     (0x0bUL)
#define SDIO_FBR_BLKSIZ0                      (0x10UL)
#define SDIO_FBR_BLKSIZ1                      (0x11UL)

#define SDIO_INT_MASTER                       (0x01U)
#define SDIO_INT_FUNCTION(function)           ((uint8_t)(1U << (function)))

#define SDIO_R5_DATA(response)                ((uint8_t)((response) & 0xffU))

#define SDIO_BRCM_CCCR_CARDCAP                (0x000000f0UL)
#define SDIO_BRCM_CCCR_CARDCTL                (0x000000f1UL)
#define SDIO_BRCM_FUNC1_DEVICE_CTL            (0x00010009UL)
#define SDIO_BRCM_FUNC1_SBADDRLOW             (0x0001000aUL)
#define SDIO_BRCM_FUNC1_SBADDRMID             (0x0001000bUL)
#define SDIO_BRCM_FUNC1_SBADDRHIGH            (0x0001000cUL)
#define SDIO_BRCM_FUNC1_FRAMECTRL             (0x0001000dUL)
#define SDIO_BRCM_FUNC1_CHIPCLKCSR            (0x0001000eUL)
#define SDIO_BRCM_FUNC1_SDIOPULLUP            (0x0001000fUL)
#define SDIO_BRCM_FUNC1_RFRAMEBCLO            (0x0001001bUL)
#define SDIO_BRCM_FUNC1_RFRAMEBCHI            (0x0001001cUL)
#define SDIO_BRCM_FUNC1_MESBUSYCTRL           (0x0001001dUL)
#define SDIO_BRCM_FUNC1_WAKEUPCTRL            (0x0001001eUL)
#define SDIO_BRCM_FUNC1_SLEEPCSR              (0x0001001fUL)

#define SDIO_BRCM_FORCE_ALP                   (0x01U)
#define SDIO_BRCM_ALP_AVAIL_REQ               (0x08U)
#define SDIO_BRCM_FORCE_HW_CLKREQ_OFF         (0x20U)
#define SDIO_BRCM_ALP_AVAIL                   (0x40U)
#define SDIO_BRCM_CLK_ALP_REQ                 (SDIO_BRCM_FORCE_HW_CLKREQ_OFF | SDIO_BRCM_ALP_AVAIL_REQ)
#define SDIO_BRCM_CLK_FORCE_ALP               (SDIO_BRCM_FORCE_HW_CLKREQ_OFF | SDIO_BRCM_FORCE_ALP)

#define SDIO_BRCM_SB_OFT_ADDR_MASK            (0x00007fffUL)
#define SDIO_BRCM_SB_ACCESS_2_4B_FLAG         (0x00008000UL)
#define SDIO_BRCM_SB_WINDOW_MASK              (0xffff8000UL)

/***********************************************************************************************************************
Typedef definitions
***********************************************************************************************************************/
typedef enum e_sdio_err
{
    SDIO_SUCCESS = 0,
    SDIO_ERR_NULL_PTR,
    SDIO_ERR_INVALID_ARG,
    SDIO_ERR_NOT_OPEN,
    SDIO_ERR_ALREADY_OPEN,
    SDIO_ERR_HOST,
    SDIO_ERR_TIMEOUT
} sdio_err_t;

typedef struct st_sdio_cmd52
{
    bool     write;
    uint8_t  function;
    uint32_t address;
    bool     raw;
    uint8_t  write_data;
    uint8_t  read_data;
    uint32_t r5;
} sdio_cmd52_t;

typedef struct st_sdio_cmd53
{
    bool      write;
    uint8_t   function;
    uint32_t  address;
    bool      increment;
    bool      block_mode;
    uint32_t  count;
    uint8_t * p_data;
    uint32_t  r5;
} sdio_cmd53_t;

/*
 * CMD52/CMD53 callbacks bind this protocol layer to an application-supplied SDIO host.
 * CMD53 callbacks must complete the full data phase before returning. For write transfers,
 * the host must not read from its data port while feeding p_args->p_data to the card.
 */
typedef sdio_err_t (*sdio_cmd52_callback_t)(void * p_context, sdio_cmd52_t * p_args);
typedef sdio_err_t (*sdio_cmd53_callback_t)(void * p_context, sdio_cmd53_t * p_args);
typedef void       (*sdio_delay_ms_callback_t)(void * p_context, uint32_t delay_ms);

typedef struct st_sdio_cfg
{
    void *                   p_context;
    sdio_cmd52_callback_t    p_cmd52;
    sdio_cmd53_callback_t    p_cmd53;
    sdio_delay_ms_callback_t p_delay_ms;
    uint32_t                 io_ready_poll_count;
} sdio_cfg_t;

typedef struct st_sdio_ctrl
{
    const sdio_cfg_t * p_cfg;
    bool               open;
    uint32_t           brcm_sb_window;
    bool               brcm_sb_window_valid;
} sdio_ctrl_t;

typedef sdio_ctrl_t * sdio_hdl_t;

/***********************************************************************************************************************
Public Functions
***********************************************************************************************************************/
sdio_err_t R_SDIO_Open(sdio_hdl_t const hdl, const sdio_cfg_t * const p_cfg);
sdio_err_t R_SDIO_Close(sdio_hdl_t const hdl);
uint32_t   R_SDIO_GetVersion(void);

uint32_t R_SDIO_MakeCmd52Arg(bool write, uint8_t function, uint32_t address, bool raw, uint8_t data);
uint32_t R_SDIO_MakeCmd53Arg(bool write, uint8_t function, uint32_t address, bool increment, bool block_mode,
                             uint32_t count);

sdio_err_t R_SDIO_Cmd52Read(sdio_hdl_t const hdl, uint8_t function, uint32_t address, uint8_t * const p_data,
                            uint32_t * const p_r5);
sdio_err_t R_SDIO_Cmd52Write(sdio_hdl_t const hdl, uint8_t function, uint32_t address, uint8_t data,
                             bool read_after_write, uint8_t * const p_readback, uint32_t * const p_r5);
sdio_err_t R_SDIO_Cmd53(sdio_hdl_t const hdl, sdio_cmd53_t * const p_args);
sdio_err_t R_SDIO_Cmd53ReadBytes(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                 uint8_t * const p_data, uint32_t length, uint32_t * const p_r5);
sdio_err_t R_SDIO_Cmd53WriteBytes(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                  uint8_t * const p_data, uint32_t length, uint32_t * const p_r5);
sdio_err_t R_SDIO_Cmd53ReadBlocks(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                  uint8_t * const p_data, uint32_t block_count, uint32_t * const p_r5);
sdio_err_t R_SDIO_Cmd53WriteBlocks(sdio_hdl_t const hdl, uint8_t function, uint32_t address, bool increment,
                                   uint8_t * const p_data, uint32_t block_count, uint32_t * const p_r5);

sdio_err_t R_SDIO_EnableFunction(sdio_hdl_t const hdl, uint8_t function, uint8_t * const p_ready,
                                 uint32_t * const p_r5);
sdio_err_t R_SDIO_ReadIoReady(sdio_hdl_t const hdl, uint8_t * const p_ready, uint32_t * const p_r5);
sdio_err_t R_SDIO_EnableInterrupts(sdio_hdl_t const hdl, uint8_t int_enable, uint8_t * const p_readback,
                                   uint32_t * const p_r5);
sdio_err_t R_SDIO_ReadInterruptPending(sdio_hdl_t const hdl, uint8_t * const p_pending, uint32_t * const p_r5);
sdio_err_t R_SDIO_ReadCisPointer(sdio_hdl_t const hdl, uint8_t function, uint32_t * const p_pointer,
                                 uint32_t * const p_r5);

uint32_t   R_SDIO_BrcmBackplaneWindow(uint32_t address);
uint32_t   R_SDIO_BrcmBackplaneFunctionAddress(uint32_t address, uint32_t length);
void       R_SDIO_BrcmInvalidateBackplaneWindow(sdio_hdl_t const hdl);
sdio_err_t R_SDIO_BrcmSetBackplaneWindow(sdio_hdl_t const hdl, uint32_t address, uint32_t * const p_window,
                                         uint32_t * const p_r5);
sdio_err_t R_SDIO_BrcmBackplaneRead(sdio_hdl_t const hdl, uint32_t address, bool increment, uint8_t * const p_data,
                                    uint32_t length, uint32_t * const p_r5);
sdio_err_t R_SDIO_BrcmBackplaneWrite(sdio_hdl_t const hdl, uint32_t address, bool increment, uint8_t * const p_data,
                                     uint32_t length, uint32_t * const p_r5);

#ifdef __cplusplus
}
#endif

#endif /* R_SDIO_RX_IF_H */

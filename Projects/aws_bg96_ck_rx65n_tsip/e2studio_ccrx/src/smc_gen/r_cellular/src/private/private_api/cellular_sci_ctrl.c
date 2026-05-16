/**********************************************************************************************************************
 * DISCLAIMER
 * This software is supplied by Renesas Electronics Corporation and is only intended for use with Renesas products. No
 * other uses are authorized. This software is owned by Renesas Electronics Corporation and is protected under all
 * applicable laws, including copyright laws.
 * THIS SOFTWARE IS PROVIDED "AS IS" AND RENESAS MAKES NO WARRANTIES REGARDING
 * THIS SOFTWARE, WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. ALL SUCH WARRANTIES ARE EXPRESSLY DISCLAIMED. TO THE MAXIMUM
 * EXTENT PERMITTED NOT PROHIBITED BY LAW, NEITHER RENESAS ELECTRONICS CORPORATION NOR ANY OF ITS AFFILIATED COMPANIES
 * SHALL BE LIABLE FOR ANY DIRECT, INDIRECT, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES FOR ANY REASON RELATED TO
 * THIS SOFTWARE, EVEN IF RENESAS OR ITS AFFILIATES HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
 * Renesas reserves the right, without notice, to make changes to this software and to discontinue the availability of
 * this software. By using this software, you agree to the additional terms and conditions found by accessing the
 * following link:
 * http://www.renesas.com/disclaimer
 *
 * Copyright (C) 2024 Renesas Electronics Corporation. All rights reserved.
 *********************************************************************************************************************/
/**********************************************************************************************************************
 * File Name    : cellular_sci_ctrl.c
 * Description  : Functions to manage serial communication functions.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "cellular_private_api.h"
#include "cellular_freertos.h"

/**********************************************************************************************************************
 * Macro definitions
 *********************************************************************************************************************/
#if defined(CELLULAR_TARGET_BG96) && !defined(CELLULAR_CFG_BG96_USE_HW_CTS)
#define CELLULAR_CFG_BG96_USE_HW_CTS (0)
#endif

/**********************************************************************************************************************
 * Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Exported global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Private (static) variables and functions
 *********************************************************************************************************************/
static void cellular_uart_callback (void * const p_Args);

/**********************************************************************************************
 * Function Name  @fn            cellular_serial_open
 *********************************************************************************************/
e_cellular_err_t cellular_serial_open(st_cellular_ctrl_t * const p_ctrl)
{
    sci_err_t        sci_ret  = SCI_SUCCESS;
    sci_cfg_t        sci_cfg  = {0};
    e_cellular_err_t ret      = CELLULAR_SUCCESS;
#if defined(__CCRX__) || defined(__ICCRX__) || defined(__RX__)
    uint8_t          priority = CELLULAR_CFG_SCI_PRIORITY - 1;
#endif

#if (CELLULAR_CFG_CTS_SW_CTRL == 0) && (!defined(CELLULAR_TARGET_BG96) || (CELLULAR_CFG_BG96_USE_HW_CTS == 1))
    CELLULAR_SET_PMR(CELLULAR_CFG_CTS_PORT, CELLULAR_CFG_CTS_PIN) = 0;
    CELLULAR_SET_PDR(CELLULAR_CFG_CTS_PORT, CELLULAR_CFG_CTS_PIN) = CELLULAR_PIN_DIRECTION_MODE_INPUT;
#endif

    p_ctrl->sci_ctrl.tx_buff_size   = R_SCI_CFG_TX_BUFSIZE;
    p_ctrl->sci_ctrl.rx_buff_size   = R_SCI_CFG_RX_BUFSIZE;
    sci_cfg.async.baud_rate         = p_ctrl->sci_ctrl.baud_rate;
    sci_cfg.async.clk_src           = SCI_CLK_INT;
    sci_cfg.async.data_size         = SCI_DATA_8BIT;
    sci_cfg.async.parity_en         = SCI_PARITY_OFF;
    sci_cfg.async.parity_type       = SCI_EVEN_PARITY;
    sci_cfg.async.stop_bits         = SCI_STOPBITS_1;
    sci_cfg.async.int_priority      = CELLULAR_CFG_SCI_PRIORITY;    // 1=lowest, 15=highest

    sci_ret = R_SCI_Open((uint8_t)R_SCI_CFG_CELLULAR_SERIAL_CH, SCI_MODE_ASYNC, &sci_cfg,   //cast
                            cellular_uart_callback, &p_ctrl->sci_ctrl.sci_hdl);

    if (SCI_SUCCESS != sci_ret)
    {
        ret = CELLULAR_ERR_SERIAL_OPEN;
    }
    else
    {
        R_SCI_CFG_PINSET_CELLULAR_SERIAL();
#if (CELLULAR_CFG_CTS_SW_CTRL == 0) && !defined(CELLULAR_TARGET_BG96)
        R_SCI_Control(p_ctrl->sci_ctrl.sci_hdl, SCI_CMD_EN_CTS_IN, NULL);
#endif
#if defined(__CCRX__) || defined(__ICCRX__) || defined(__RX__)
        R_SCI_Control(p_ctrl->sci_ctrl.sci_hdl, SCI_CMD_SET_TXI_PRIORITY, &priority);
#endif
#if CELLULAR_CFG_CTS_SW_CTRL == 0
        CELLULAR_SET_PODR(CELLULAR_CFG_RTS_PORT, CELLULAR_CFG_RTS_PIN) = 0;
        CELLULAR_SET_PDR(CELLULAR_CFG_RTS_PORT, CELLULAR_CFG_RTS_PIN)  = CELLULAR_PIN_DIRECTION_MODE_OUTPUT;
#endif
    }

    return ret;
}
/**********************************************************************************************************************
 * End of function cellular_serial_open
 *********************************************************************************************************************/

/**********************************************************************************************
 * Function Name  @fn            cellular_serial_enable_cts
 *********************************************************************************************/
e_cellular_err_t cellular_serial_enable_cts(st_cellular_ctrl_t * const p_ctrl)
{
#if (CELLULAR_CFG_CTS_SW_CTRL == 0) && defined(CELLULAR_TARGET_BG96) && (CELLULAR_CFG_BG96_USE_HW_CTS == 1)
    if ((NULL == p_ctrl) || (FIT_NO_PTR == p_ctrl) ||
        (NULL == p_ctrl->sci_ctrl.sci_hdl) || (FIT_NO_PTR == p_ctrl->sci_ctrl.sci_hdl))
    {
        return CELLULAR_ERR_PARAMETER;
    }

    R_SCI_Control(p_ctrl->sci_ctrl.sci_hdl, SCI_CMD_EN_CTS_IN, NULL);
#else
    (void)p_ctrl;
#endif

    return CELLULAR_SUCCESS;
}
/**********************************************************************************************************************
 * End of function cellular_serial_enable_cts
 *********************************************************************************************************************/

/**********************************************************************************************
 * Function Name  @fn            cellular_serial_close
 * Description    @details       Terminate the serial communication function.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *********************************************************************************************/
void cellular_serial_close(st_cellular_ctrl_t * const p_ctrl)
{
    R_SCI_Close(p_ctrl->sci_ctrl.sci_hdl);
    return;
}
/**********************************************************************************************************************
 * End of function cellular_serial_close
 *********************************************************************************************************************/

/**********************************************************************************************
 * Function Name  @fn            cellular_serial_reopen
 * Description    @details       Close and reopen the SCI at a new baud rate.
 *                               The receive task busy-polls R_SCI_Receive and yields when it
 *                               fails, so the brief window between close and open is absorbed
 *                               without losing task state.
 *********************************************************************************************/
e_cellular_err_t cellular_serial_reopen(st_cellular_ctrl_t * const p_ctrl, uint32_t new_baud)
{
    cellular_serial_close(p_ctrl);
    p_ctrl->sci_ctrl.baud_rate = new_baud;
    return cellular_serial_open(p_ctrl);
}
/**********************************************************************************************************************
 * End of function cellular_serial_reopen
 *********************************************************************************************************************/

/**********************************************************************************************
 * Function Name  @fn            cellular_uart_callback
 * Description    @details       Callback function for serial communication.
 * Arguments      @param[in/out] p_Args -
 *                                  callback arguments.
 *********************************************************************************************/
static void cellular_uart_callback(void * const p_Args)
{
    sci_cb_args_t * const p_args = (sci_cb_args_t *)p_Args; //(void *)->(sci_cb_args_t *)

    switch (p_args->event)
    {
        case SCI_EVT_RX_CHAR:
        {
            /* Do Nothing */
            break;
        }
#if SCI_CFG_TEI_INCLUDED
        case SCI_EVT_TEI:
        {
            gp_cellular_ctrl->sci_ctrl.tx_end_flg = CELLULAR_TX_END_FLAG_ON;
            break;
        }
#endif
        case SCI_EVT_RXBUF_OVFL:
        {
            gp_cellular_ctrl->sci_ctrl.sci_err_flg = SCI_EVT_RXBUF_OVFL;
            break;
        }
        case SCI_EVT_OVFL_ERR:
        {
            gp_cellular_ctrl->sci_ctrl.sci_err_flg = SCI_EVT_OVFL_ERR;
            break;
        }
        case SCI_EVT_FRAMING_ERR:
        {
            gp_cellular_ctrl->sci_ctrl.sci_err_flg = SCI_EVT_FRAMING_ERR;
            break;
        }
        case SCI_EVT_PARITY_ERR:
        {
            gp_cellular_ctrl->sci_ctrl.sci_err_flg = SCI_EVT_PARITY_ERR;
            break;
        }
        default:
        {
            break;
        }
    }
}
/**********************************************************************************************************************
 * End of function cellular_uart_callback
 *********************************************************************************************************************/

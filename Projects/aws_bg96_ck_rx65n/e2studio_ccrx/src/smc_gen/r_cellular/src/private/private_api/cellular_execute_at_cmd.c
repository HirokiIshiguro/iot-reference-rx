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
 * File Name    : cellular_execute_at_cmd.c
 * Description  : Function to send an AT command to a module.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "cellular_private_api.h"
#include "cellular_freertos.h"
#include "at_command.h"
#if BSP_CFG_RTOS_USED == (1)
#include "FreeRTOS.h"
#include "task.h"
#endif

/**********************************************************************************************************************
 * Macro definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Exported global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Private (static) variables and functions
 *********************************************************************************************************************/
static e_cellular_err_atc_t cellular_send_atc (st_cellular_ctrl_t * const p_ctrl);
static e_cellular_err_atc_t cellular_res_check (st_cellular_ctrl_t * const p_ctrl,
                                                const e_cellular_atc_return_t expect_code);
#if BSP_CFG_RTOS_USED == (1)
static void cellular_prepare_atc_wait (st_cellular_ctrl_t * const p_ctrl);
static void cellular_clear_atc_wait (st_cellular_ctrl_t * const p_ctrl);
static void cellular_wait_atc_event (void);
#endif
#if CELLULAR_CFG_CTS_SW_CTRL == 1
static e_cellular_timeout_check_t cellular_tx_flag_check (st_cellular_ctrl_t * const p_ctrl);
#endif

/****************************************************************************
 * Function Name  @fn            cellular_execute_at_command
 ***************************************************************************/
e_cellular_err_t cellular_execute_at_command(st_cellular_ctrl_t * const p_ctrl, const uint32_t timeout_ms,
                                                        const e_cellular_atc_return_t expect_code,
                                                            const e_atc_list_t command)
{
    e_cellular_err_t           ret           = CELLULAR_SUCCESS;
    e_cellular_err_atc_t       atc_ret       = CELLULAR_ATC_OK;
    e_cellular_err_semaphore_t semaphore_ret = CELLULAR_SEMAPHORE_ERR_TAKE;

    if (NULL != p_ctrl)
    {
        if ((CELLULAR_PSM_ACTIVE == p_ctrl->ring_ctrl.psm) &&
            (1                   == CELLULAR_SET_PODR(CELLULAR_CFG_RTS_PORT, CELLULAR_CFG_RTS_PIN)))
        {
            /* WAIT_LOOP */
            while (1)
            {
                semaphore_ret = cellular_take_semaphore(p_ctrl->ring_ctrl.rts_semaphore);
                if (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret)
                {
                    break;
                }
                cellular_delay_task(1);
            }
#if CELLULAR_CFG_CTS_SW_CTRL == 1
            cellular_rts_hw_flow_enable();
#else
            cellular_rts_ctrl(0);
#endif
#ifdef CELLULAR_RTS_DELAY
            cellular_delay_task(CELLULAR_RTS_DELAYTIME);
#endif
        }

        cellular_timeout_init(&p_ctrl->sci_ctrl.timeout_ctrl, timeout_ms);
        cellular_set_atc_number(p_ctrl, command);
        atc_ret = cellular_send_atc(p_ctrl);

        if (CELLULAR_ATC_OK == atc_ret)
        {
            atc_ret = cellular_res_check(p_ctrl, expect_code);
        }

        if ((CELLULAR_PSM_ACTIVE == p_ctrl->ring_ctrl.psm) && (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret))
        {
#if CELLULAR_CFG_CTS_SW_CTRL == 1
            cellular_rts_hw_flow_disable();
#endif
            cellular_rts_ctrl(1);
            cellular_give_semaphore(p_ctrl->ring_ctrl.rts_semaphore);
        }

        if (CELLULAR_ATC_OK == atc_ret)
        {
            ret = CELLULAR_SUCCESS;
        }
        else if (CELLULAR_ATC_ERR_TIMEOUT == atc_ret)
        {
            ret = CELLULAR_ERR_MODULE_TIMEOUT;
        }
        else
        {
            ret = CELLULAR_ERR_MODULE_COM;
        }
    }
    else
    {
        ret = CELLULAR_ERR_PARAMETER;
    }

    return ret;
}
/**********************************************************************************************************************
 * End of function cellular_execute_at_command
 *********************************************************************************************************************/

/****************************************************************************
 * Function Name  @fn            cellular_send_atc
 ***************************************************************************/
static e_cellular_err_atc_t cellular_send_atc(st_cellular_ctrl_t * const p_ctrl)
{
    uint16_t                   length      = 0;
#if CELLULAR_CFG_CTS_SW_CTRL == 1
    uint16_t                   send_size   = 0;
#endif
    sci_err_t                  sci_ret     = SCI_SUCCESS;
    e_cellular_err_atc_t       ret         = CELLULAR_ATC_OK;
    e_cellular_timeout_check_t timeout_ret = CELLULAR_NOT_TIMEOUT;
    length = (uint16_t)strlen((const char *)p_ctrl->sci_ctrl.atc_buff);
#if CELLULAR_CFG_CTS_SW_CTRL == 0
    p_ctrl->sci_ctrl.tx_end_flg = CELLULAR_TX_END_FLAG_OFF;

    sci_ret = R_SCI_Send(p_ctrl->sci_ctrl.sci_hdl, p_ctrl->sci_ctrl.atc_buff, length);

    if (SCI_SUCCESS == sci_ret)
    {
        /* WAIT_LOOP */
        while (1)
        {
            if (CELLULAR_TX_END_FLAG_ON == p_ctrl->sci_ctrl.tx_end_flg)
            {
                break;
            }

            timeout_ret = cellular_check_timeout(&p_ctrl->sci_ctrl.timeout_ctrl);
            if (CELLULAR_TIMEOUT == timeout_ret)
            {
                CELLULAR_LOG_ERROR(("AT command TX timeout: cmd=%d len=%u tx_end=%d sci_err=%d.\n",
                                    (int)p_ctrl->sci_ctrl.at_command,
                                    (unsigned int)length,
                                    (int)p_ctrl->sci_ctrl.tx_end_flg,
                                    (int)p_ctrl->sci_ctrl.sci_err_flg));
                ret = CELLULAR_ATC_ERR_TIMEOUT;
                break;
            }
        }
        if ((CELLULAR_ATC_OK == ret) && (ATC_RECV_SOCKET == p_ctrl->sci_ctrl.at_command))
        {
            CELLULAR_LOG_DEBUG(("BG96 QIRD AT TX done: len=%u.\n", (unsigned int)length));
        }
    }
    else
    {
        CELLULAR_LOG_ERROR(("AT command TX start failed: cmd=%d len=%u sci_ret=%d sci_err=%d.\n",
                            (int)p_ctrl->sci_ctrl.at_command,
                            (unsigned int)length,
                            (int)sci_ret,
                            (int)p_ctrl->sci_ctrl.sci_err_flg));
        ret = CELLULAR_ATC_ERR_MODULE_COM;
    }
#else
    /* WAIT_LOOP */
    while (send_size < length)
    {
        if (1 != CELLULAR_GET_PIDR(CELLULAR_CFG_CTS_PORT, CELLULAR_CFG_CTS_PIN))
        {
            p_ctrl->sci_ctrl.tx_end_flg = CELLULAR_TX_END_FLAG_OFF;

            sci_ret = R_SCI_Send(p_ctrl->sci_ctrl.sci_hdl, &p_ctrl->sci_ctrl.atc_buff[send_size], 1);
            if (SCI_SUCCESS == sci_ret)
            {
                timeout_ret = cellular_tx_flag_check(p_ctrl);
                if (CELLULAR_TIMEOUT == timeout_ret)
                {
                    CELLULAR_LOG_ERROR(("AT command TX timeout: cmd=%d len=%u sent=%u tx_end=%d sci_err=%d.\n",
                                        (int)p_ctrl->sci_ctrl.at_command,
                                        (unsigned int)length,
                                        (unsigned int)send_size,
                                        (int)p_ctrl->sci_ctrl.tx_end_flg,
                                        (int)p_ctrl->sci_ctrl.sci_err_flg));
                    ret = CELLULAR_ATC_ERR_TIMEOUT;
                    break;
                }
                send_size++;
            }
            else
            {
                CELLULAR_LOG_ERROR(("AT command TX byte failed: cmd=%d len=%u sent=%u sci_ret=%d sci_err=%d.\n",
                                    (int)p_ctrl->sci_ctrl.at_command,
                                    (unsigned int)length,
                                    (unsigned int)send_size,
                                    (int)sci_ret,
                                    (int)p_ctrl->sci_ctrl.sci_err_flg));
                ret = CELLULAR_ATC_ERR_MODULE_COM;
                break;
            }
        }
    };
    if ((CELLULAR_ATC_OK == ret) && (ATC_RECV_SOCKET == p_ctrl->sci_ctrl.at_command))
    {
        CELLULAR_LOG_DEBUG(("BG96 QIRD AT TX done: len=%u.\n", (unsigned int)length));
    }
#endif  /* CELLULAR_CFG_CTS_SW_CTRL == 0 */

    return ret;
}
/**********************************************************************************************************************
 * End of function cellular_send_atc
 *********************************************************************************************************************/

/****************************************************************************
 * Function Name  @fn            cellular_res_check
 ***************************************************************************/
static e_cellular_err_atc_t cellular_res_check(st_cellular_ctrl_t * const p_ctrl,
                                                const e_cellular_atc_return_t expect_code)
{
    e_cellular_err_atc_t       ret         = CELLULAR_ATC_OK;
    e_cellular_atc_return_t    res         = ATC_RETURN_NONE;
    e_cellular_timeout_check_t timeout_ret = CELLULAR_NOT_TIMEOUT;

#if BSP_CFG_RTOS_USED == (1)
    cellular_prepare_atc_wait(p_ctrl);
#endif

    /* WAIT_LOOP */
    while (1)
    {
        res = cellular_get_atc_response(p_ctrl);
        if (ATC_RETURN_NONE != res)
        {
            if (res != expect_code)
            {
                ret = CELLULAR_ATC_ERR_COMPARE;
            }
            break;
        }

        timeout_ret = cellular_check_timeout(&p_ctrl->sci_ctrl.timeout_ctrl);
        if (CELLULAR_TIMEOUT == timeout_ret)
        {
            CELLULAR_LOG_ERROR(("AT command response timeout: cmd=%d expect=%d res=%d sci_err=%d.\n",
                                (int)p_ctrl->sci_ctrl.at_command,
                                (int)expect_code,
                                (int)res,
                                (int)p_ctrl->sci_ctrl.sci_err_flg));
            ret = CELLULAR_ATC_ERR_TIMEOUT;
            break;
        }

#if BSP_CFG_RTOS_USED == (1)
        cellular_wait_atc_event();
#endif
    }

#if BSP_CFG_RTOS_USED == (1)
    cellular_clear_atc_wait(p_ctrl);
#endif

    if (ATC_RECV_SOCKET == p_ctrl->sci_ctrl.at_command)
    {
        CELLULAR_LOG_DEBUG(("BG96 QIRD AT response done: ret=%d res=%d expect=%d.\n",
                            (int)ret,
                            (int)res,
                            (int)expect_code));
    }

    return ret;
}
/**********************************************************************************************************************
 * End of function cellular_res_check
 *********************************************************************************************************************/

#if BSP_CFG_RTOS_USED == (1)
/****************************************************************************
 * Function Name  @fn            cellular_prepare_atc_wait
 ***************************************************************************/
static void cellular_prepare_atc_wait(st_cellular_ctrl_t * const p_ctrl)
{
#if configTASK_NOTIFICATION_ARRAY_ENTRIES <= CELLULAR_TASK_NOTIFY_INDEX
#error "configTASK_NOTIFICATION_ARRAY_ENTRIES must reserve CELLULAR_TASK_NOTIFY_INDEX."
#endif
    p_ctrl->sci_ctrl.atc_wait_taskhandle = (void *)xTaskGetCurrentTaskHandle();
    while (0U != ulTaskNotifyTakeIndexed(CELLULAR_TASK_NOTIFY_INDEX, pdTRUE, 0))
    {
        R_BSP_NOP();
    }
}
/**********************************************************************************************************************
 * End of function cellular_prepare_atc_wait
 *********************************************************************************************************************/

/****************************************************************************
 * Function Name  @fn            cellular_clear_atc_wait
 ***************************************************************************/
static void cellular_clear_atc_wait(st_cellular_ctrl_t * const p_ctrl)
{
    p_ctrl->sci_ctrl.atc_wait_taskhandle = NULL;
}
/**********************************************************************************************************************
 * End of function cellular_clear_atc_wait
 *********************************************************************************************************************/

/****************************************************************************
 * Function Name  @fn            cellular_wait_atc_event
 ***************************************************************************/
static void cellular_wait_atc_event(void)
{
    (void)ulTaskNotifyTakeIndexed(CELLULAR_TASK_NOTIFY_INDEX, pdTRUE, pdMS_TO_TICKS(1));
}
/**********************************************************************************************************************
 * End of function cellular_wait_atc_event
 *********************************************************************************************************************/
#endif /* BSP_CFG_RTOS_USED == (1) */

#if CELLULAR_CFG_CTS_SW_CTRL == 1
/*************************************************************************************************
 * Function Name  @fn            cellular_tx_flag_check
 * Description    @details       Wait for transmission completion flag.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for sending data.
 * Return Value   @retval        CELLULAR_NOT_TIMEOUT -
 *                                  Successfully flag check.
 *                @retval        CELLULAR_TIMEOUT -
 *                                  Time out.
 ************************************************************************************************/
static e_cellular_timeout_check_t cellular_tx_flag_check(st_cellular_ctrl_t * const p_ctrl)
{
    e_cellular_timeout_check_t timeout = CELLULAR_NOT_TIMEOUT;

    st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl = &p_ctrl->sci_ctrl.timeout_ctrl;

    /* WAIT_LOOP */
    while (1)
    {
        if (CELLULAR_TX_END_FLAG_ON == p_ctrl->sci_ctrl.tx_end_flg)
        {
            break;
        }

        p_cellular_timeout_ctrl->this_time = cellular_get_tickcount();

        if (CELLULAR_TIMEOUT_NOT_OVERFLOW == p_cellular_timeout_ctrl->timeout_overflow_flag)
        {
            if ((p_cellular_timeout_ctrl->this_time >= p_cellular_timeout_ctrl->end_time) ||
                    (p_cellular_timeout_ctrl->this_time < p_cellular_timeout_ctrl->start_time))
            {
                timeout = CELLULAR_TIMEOUT;
                break;
            }
        }
        else
        {
            if ((p_cellular_timeout_ctrl->this_time < p_cellular_timeout_ctrl->start_time) &&
                    (p_cellular_timeout_ctrl->this_time >= p_cellular_timeout_ctrl->end_time))
            {
                timeout = CELLULAR_TIMEOUT;
                break;
            }
        }
    }

    return timeout;
}
/**********************************************************************************************************************
 * End of function cellular_tx_flag_check
 *********************************************************************************************************************/
#endif  /* CELLULAR_CFG_CTS_SW_CTRL == 1 */

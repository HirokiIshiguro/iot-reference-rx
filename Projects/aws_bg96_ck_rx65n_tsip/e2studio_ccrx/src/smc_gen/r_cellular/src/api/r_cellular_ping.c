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
 * File Name    : r_cellular_ping.c
 * Description  : Functions for performing PING.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "cellular_private_api.h"
#include "cellular_freertos.h"
#include "at_command.h"

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
#if defined(CELLULAR_TARGET_BG96)
static e_cellular_err_t cellular_bg96_ping (st_cellular_ctrl_t * const p_ctrl, const uint8_t * const p_host,
                                            const st_cellular_ping_cfg_t * const p_cfg);
#endif /* CELLULAR_TARGET_BG96 */

/************************************************************************
 * Function Name  @fn            R_CELLULAR_Ping
 ***********************************************************************/
e_cellular_err_t R_CELLULAR_Ping(st_cellular_ctrl_t * const p_ctrl, const uint8_t * const p_host,
                                    const st_cellular_ping_cfg_t * const p_cfg)
{
    uint32_t                   preemption    = 0;
    e_cellular_err_t           ret           = CELLULAR_SUCCESS;
    e_cellular_err_semaphore_t semaphore_ret = CELLULAR_SEMAPHORE_SUCCESS;

    preemption = cellular_interrupt_disable();
    if ((NULL == p_ctrl) || (NULL == p_host))
    {
        ret = CELLULAR_ERR_PARAMETER;
    }

    if ((CELLULAR_SUCCESS == ret) && (NULL != p_cfg))
    {
        if (((p_cfg->count < CELLULAR_PING_REQ_MIN) || (p_cfg->count > CELLULAR_PING_REQ_MAX) ||
            (p_cfg->len < CELLULAR_PING_MES_MIN) || (p_cfg->len > CELLULAR_PING_MES_MAX) ||
            (p_cfg->interval < CELLULAR_PING_INTER_MIN) || (p_cfg->interval > CELLULAR_PING_INTER_MAX) ||
            (p_cfg->timeout < CELLULAR_PING_TIMEOUT_MIN) || (p_cfg->timeout > CELLULAR_PING_TIMEOUT_MAX)))
        {
            ret = CELLULAR_ERR_PARAMETER;
        }
    }

    if (CELLULAR_SUCCESS == ret)
    {
        if (0 != (p_ctrl->running_api_count % 2))
        {
            ret = CELLULAR_ERR_OTHER_API_RUNNING;
        }
        else if (CELLULAR_SYSTEM_CLOSE == p_ctrl->system_state)
        {
            ret = CELLULAR_ERR_NOT_OPEN;
        }
        else if (CELLULAR_SYSTEM_OPEN == p_ctrl->system_state)
        {
            ret = CELLULAR_ERR_NOT_CONNECT;
        }
        else
        {
            p_ctrl->running_api_count += 2;
        }
    }
    cellular_interrupt_enable(preemption);

    if (CELLULAR_SUCCESS == ret)
    {
        semaphore_ret = cellular_take_semaphore(p_ctrl->at_semaphore);
        if (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret)
        {
#if defined(CELLULAR_TARGET_BG96)
            ret = cellular_bg96_ping(p_ctrl, p_host, p_cfg);
#else
            ret = atc_ping(p_ctrl, p_host, p_cfg);
#endif /* CELLULAR_TARGET_BG96 */
            cellular_give_semaphore(p_ctrl->at_semaphore);
        }
        else
        {
            ret = CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
        }
        p_ctrl->running_api_count -= 2;
    }

    return ret;
}
/**********************************************************************************************************************
 * End of function R_CELLULAR_Ping
 *********************************************************************************************************************/

#if defined(CELLULAR_TARGET_BG96)
/************************************************************************
 * Function Name  @fn            cellular_bg96_ping
 * Description    @details       BG96 answers AT+QPING with OK at once and gives the results later in "+QPING:"
 *                               URCs. Wait for the end line with the AT semaphore held (the RYZ014A AT+PING also
 *                               gives its results before OK), so that the return value tells whether the ping
 *                               worked: SUCCESS when at least one reply came, MODULE_COM when the ping failed
 *                               (an error code in the end line, or no reply), MODULE_TIMEOUT when the end line
 *                               did not come within count x timeout plus a margin.
 ***********************************************************************/
static e_cellular_err_t cellular_bg96_ping(st_cellular_ctrl_t * const p_ctrl, const uint8_t * const p_host,
                                           const st_cellular_ping_cfg_t * const p_cfg)
{
    st_cellular_bg96_ping_t result;
    uint32_t                limit_ms;
    uint32_t                waited_ms = 0;
    e_cellular_err_t        ret       = CELLULAR_SUCCESS;

    memset(&result, 0, sizeof(result));
    if (NULL != p_cfg)
    {
        limit_ms = p_cfg->count * p_cfg->timeout * 1000U;
    }
    else
    {
        limit_ms = CELLULAR_PING_REQ_DEFAULT * CELLULAR_PING_TIMEOUT_DEFAULT * 1000U;
    }
    limit_ms += BG96_PING_RESULT_MARGIN_MS;

    /* AT+QPING needs context 1 activated for the TCP/IP stack with AT+QIACT; the AT+CGACT of APConnect does not
     * do that (AT+QPING then fails with 558, seen on hardware). BG96 answers ERROR when the context is active
     * already, so the result is not used. */
    (void)atc_qiact(p_ctrl);

    p_ctrl->recv_data = &result;
    ret               = atc_ping(p_ctrl, p_host, p_cfg);
    if (CELLULAR_SUCCESS == ret)
    {
        /* WAIT_LOOP */
        while ((0U == result.done) && (waited_ms < limit_ms))
        {
            cellular_delay_task(BG96_PING_POLL_MS);
            waited_ms += BG96_PING_POLL_MS;
        }

        if (0U == result.done)
        {
            ret = CELLULAR_ERR_MODULE_TIMEOUT;
        }
        else if ((0 != result.result) || (result.rcvd < 1))
        {
            CELLULAR_LOG_ERROR(("AT+QPING failed: result %ld, %ld of %ld replies.", (long)result.result,
                                (long)result.rcvd, (long)result.sent));
            ret = CELLULAR_ERR_MODULE_COM;
        }
        else
        {
            R_BSP_NOP();
        }
    }
    p_ctrl->recv_data = NULL;

    return ret;
}
/**********************************************************************************************************************
 * End of function cellular_bg96_ping
 *********************************************************************************************************************/
#endif /* CELLULAR_TARGET_BG96 */

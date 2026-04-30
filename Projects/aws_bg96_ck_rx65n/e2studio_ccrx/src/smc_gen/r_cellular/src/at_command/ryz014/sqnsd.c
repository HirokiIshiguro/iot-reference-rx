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
 * File Name    : sqnsd.c
 * Description  : Function to execute the AT command (SQNSD).
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "at_command.h"
#include "cellular_private_api.h"
#include "cellular_freertos.h"  /* cellular_delay_task */

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

/*************************************************************************************************
 * Function Name  @fn            atc_sqnsd
 *
 * BG96: AT+QIOPEN=<contextID>,<connectID>,"<service_type>","<host>",<rport>,<lport>,<access_mode>
 *   contextID = 1 (fixed, set up by R_CELLULAR_APConnect via AT+QICSGP/QIACT)
 *   connectID = socket_no
 *   service_type = "TCP" or "UDP"
 *   host = IP literal (p_ip_addr)
 *   rport = remote port
 *   lport = 0 (auto-assign local port)
 *   access_mode = 0 (buffer access; read via AT+QIRD)
 *
 * Note: BG96 AT+QIOPEN returns OK immediately as "command accepted", then
 * emits "+QIOPEN: <connectID>,<err>" URC when the connection attempt
 * completes. Wait for that URC before reporting the socket connected.
 ************************************************************************************************/
e_cellular_err_t atc_sqnsd(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                            const uint8_t * const p_ip_addr, const uint16_t port)
{
    uint8_t          cid_str[4]                            = {0};
    uint8_t          port_str[8]                           = {0};
    const uint8_t *  type_str                              = (const uint8_t *) "TCP";
    const uint8_t *  p_command_arg[CELLULAR_MAX_ARG_COUNT] = {0};
    e_cellular_err_t ret                                   = CELLULAR_SUCCESS;
    uint32_t         connect_wait_ms                       = 0;

    sprintf((char *)cid_str,  "%d", socket_no); /*(uint8_t *)->(char *)*/
    sprintf((char *)port_str, "%u", port);      /*(uint8_t *)->(char *)*/
    if (CELLULAR_PROTOCOL_TCP != p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].protocol)
    {
        type_str = (const uint8_t *) "UDP";
    }

    p_command_arg[0] = cid_str;
    p_command_arg[1] = type_str;
    p_command_arg[2] = (uint8_t *)p_ip_addr;    /*(const uint8_t *)->(uint8_t *)*/
    p_command_arg[3] = port_str;

    atc_generate(p_ctrl->sci_ctrl.atc_buff, gp_at_command[ATC_CONNECT_SOCKET], p_command_arg);

#if defined(CELLULAR_TARGET_BG96)
    p_ctrl->sci_ctrl.active_connect_socket   = socket_no;
    p_ctrl->sci_ctrl.active_connect_complete = 0u;
    p_ctrl->sci_ctrl.active_connect_result   = -1;
#endif /* CELLULAR_TARGET_BG96 */

    if (p_ctrl->sci_ctrl.atc_timeout >
        ((p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].connect_timeout * 100)
                + CELLULAR_SOCKETCONNECT_DELAY))
    {
        connect_wait_ms = p_ctrl->sci_ctrl.atc_timeout;
        ret = cellular_execute_at_command(p_ctrl, p_ctrl->sci_ctrl.atc_timeout, ATC_RETURN_OK, ATC_CONNECT_SOCKET);
    }
    else
    {
        connect_wait_ms =
                ((uint32_t)p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].connect_timeout * 100)
                    + CELLULAR_SOCKETCONNECT_DELAY;
        ret = cellular_execute_at_command(p_ctrl,
                connect_wait_ms, ATC_RETURN_OK, ATC_CONNECT_SOCKET);
    }

#if defined(CELLULAR_TARGET_BG96)
    if (CELLULAR_SUCCESS == ret)
    {
        const uint32_t poll_interval_ms = 100u;
        uint32_t       poll_limit       = connect_wait_ms / poll_interval_ms;
        uint32_t       cnt              = 0u;

        if (0u == poll_limit)
        {
            poll_limit = 1u;
        }

        while (cnt < poll_limit)
        {
            if (0u != p_ctrl->sci_ctrl.active_connect_complete)
            {
                break;
            }
            cellular_delay_task(poll_interval_ms);
            cnt++;
        }

        if (0u == p_ctrl->sci_ctrl.active_connect_complete)
        {
            CELLULAR_LOG_ERROR(("QIOPEN URC timeout - socket %d did not report completion.", socket_no));
            ret = CELLULAR_ERR_MODULE_TIMEOUT;
        }
        else if (0 != p_ctrl->sci_ctrl.active_connect_result)
        {
            CELLULAR_LOG_ERROR(("QIOPEN failed - socket %d, result %ld.",
                                socket_no, p_ctrl->sci_ctrl.active_connect_result));
            ret = CELLULAR_ERR_MODULE_COM;
        }
    }

    p_ctrl->sci_ctrl.active_connect_socket = 0u;
#endif /* CELLULAR_TARGET_BG96 */

    return ret;
}
/**********************************************************************************************************************
 * End of function atc_sqnsd
 *********************************************************************************************************************/

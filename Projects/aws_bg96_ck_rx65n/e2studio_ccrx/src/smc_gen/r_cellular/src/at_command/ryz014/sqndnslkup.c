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
 * File Name    : sqndnslkup.c  (BG96 variant — AT+QIDNSGIP)
 * Description  : Function to execute the AT command for DNS resolution on BG96.
 *
 * The function keeps the SQN-compatible atc_sqndnslkup() signature so the FIT
 * caller R_CELLULAR_DnsQuery() builds unchanged. On the wire it sends BG96
 * native AT+QIDNSGIP=1,"<host>" and polls p_ctrl->recv_data for the asynchronous
 * "+QIURC: \"dnsgip\",\"<ip>\"" notification filled in by the receive task.
 *
 * NOTE: future consolidation (BG96 FIT module integration) will move this file
 * under smc_gen/r_cellular/src/at_command/bg96/, tracked as a separate Issue.
 * e2studio's managed-build source discovery did not cleanly handle that
 * relocation in-session, so the file is kept here for now.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "at_command.h"
#include "cellular_private_api.h"
#include "cellular_freertos.h"  /* cellular_delay_task */

/*************************************************************************************************
 * Function Name  @fn            atc_sqndnslkup
 *
 * BG96: AT+QIDNSGIP=<contextID>,"<hostname>"
 *   contextID = 1 (fixed)
 *   hostname  = p_domain_name
 *
 * Response: OK immediately, then
 *   +QIURC: "dnsgip",<err>[,<resolved_count>,<ttl>]
 *   +QIURC: "dnsgip","<ip>"     (one line per resolved address)
 *
 * The receive task's cellular_dns_result handler parses the second URC and
 * writes just the IP string to p_ctrl->recv_data. We poll that buffer here
 * for up to 15s before returning.
 *
 * ip_version is accepted for API compatibility but BG96 only supports IPv4
 * resolution via QIDNSGIP (no explicit type selector in the AT command).
 ************************************************************************************************/
e_cellular_err_t atc_sqndnslkup(st_cellular_ctrl_t * const p_ctrl, const uint8_t * const p_domain_name,
                                    const uint8_t ip_version)
{
    const uint8_t *  p_command_arg[CELLULAR_MAX_ARG_COUNT] = {0};
    e_cellular_err_t ret                                   = CELLULAR_SUCCESS;

    (void) ip_version;  /* BG96 QIDNSGIP is IPv4-only from this helper. */

    p_command_arg[0] = (uint8_t *)p_domain_name;    /*(const uint8_t *)->(uint8_t *)*/

    atc_generate(p_ctrl->sci_ctrl.atc_buff, gp_at_command[ATC_DNS_LOOKUP], p_command_arg);

    ret = cellular_execute_at_command(p_ctrl, p_ctrl->sci_ctrl.atc_timeout,
                                      ATC_RETURN_OK, ATC_DNS_LOOKUP);
    if (CELLULAR_SUCCESS != ret)
    {
        return ret;
    }

    /* Poll p_ctrl->recv_data for the asynchronous URC-delivered IP.
     * A successful resolution leaves recv_data[0] set to an ASCII digit
     * (IPv4 literal). */
    {
        const uint32_t poll_interval_ms = 100u;
        const uint32_t poll_limit       = 150u;  /* 150 * 100ms = 15s */
        uint32_t       cnt              = 0u;
        char *         recv_buf         = (char *)p_ctrl->recv_data;

        while (cnt < poll_limit)
        {
            if ((NULL != recv_buf) && (recv_buf[0] >= '0') && (recv_buf[0] <= '9'))
            {
                return CELLULAR_SUCCESS;
            }
            cellular_delay_task(poll_interval_ms);
            cnt++;
        }
    }
    CELLULAR_LOG_ERROR(("QIDNSGIP URC timeout — no IP returned within 15s."));
    return CELLULAR_ERR_MODULE_TIMEOUT;
}
/**********************************************************************************************************************
 * End of function atc_sqndnslkup
 *********************************************************************************************************************/

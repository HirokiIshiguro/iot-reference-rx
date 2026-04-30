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
 * File Name    : at_command.c
 * Description  : Function to generate AT command.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "at_command.h"
#include "cellular_freertos.h"

/**********************************************************************************************************************
 * Macro definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Exported global variables
 *********************************************************************************************************************/
const uint8_t g_bg96_echo_off[]                = BG96_ATC_ECHO_OFF;
const uint8_t g_bg96_function_level_check[]    = BG96_ATC_FUNCTION_LEVEL_CHECK;
const uint8_t g_bg96_function_level[]          = BG96_ATC_FUNCTION_LEVEL;
const uint8_t g_bg96_pin_lock_check[]          = BG96_ATC_PIN_LOCK_CHECK;
const uint8_t g_bg96_pin_lock_release[]        = BG96_ATC_PIN_LOCK_RELEASE;
const uint8_t g_bg96_connect_socket[]          = BG96_ATC_CONNECT_SOCKET;
const uint8_t g_bg96_close_socket[]            = BG96_ATC_CLOSE_SOCKET;
const uint8_t g_bg96_send_socket[]             = BG96_ATC_SEND_SCOKET;
const uint8_t g_bg96_recv_socket[]             = BG96_ATC_RECV_SCOKET;
const uint8_t g_bg96_dns_lookup[]              = BG96_ATC_DNS_LOOKUP;
const uint8_t g_bg96_ap_config[]               = BG96_ATC_AP_CONFIG;
const uint8_t g_bg96_private_ap_config[]       = BG96_ATC_PRIVATE_AP_CONFIG;
const uint8_t g_bg96_ap_config_check[]         = BG96_ATC_AP_CONFIG_CHECK;
const uint8_t g_bg96_user_config[]             = BG96_ATC_USER_CONFIG;
const uint8_t g_bg96_clear_config[]            = BG96_ATC_CLEAR_CONFIG;
const uint8_t g_bg96_socket_config_1[]         = BG96_ATC_SOCKET_CONFIG_1;
const uint8_t g_bg96_socket_config_2[]         = BG96_ATC_SOCKET_CONFIG_2;
const uint8_t g_bg96_listening_socket[]        = BG96_ATC_LISTENING_SOCKET;
const uint8_t g_bg96_connect_check[]           = BG96_ATC_CONNECT_CHECK;
const uint8_t g_bg96_set_connect_status[]      = BG96_ATC_SET_CONNECT_STATUS;
const uint8_t g_bg96_shutdown[]                = BG96_ATC_SHUTDOWN;
const uint8_t g_bg96_get_time[]                = BG96_ATC_GET_TIME;
const uint8_t g_bg96_set_time[]                = BG96_ATC_SET_TIME;
const uint8_t g_bg96_reset[]                   = BG96_ATC_RESET;
const uint8_t g_bg96_set_notice_level[]        = BG96_ATC_SET_NOTICE_LEVEL;
const uint8_t g_bg96_get_notice_level[]        = BG96_ATC_GET_NOTICE_LEVEL;
const uint8_t g_bg96_auto_connect[]            = BG96_ATC_AUTO_CONNECT;
const uint8_t g_bg96_auto_connect_check[]      = BG96_ATC_AUTO_CONNECT_CHECK;
const uint8_t g_bg96_sim_st_off[]              = BG96_ATC_SIM_ST_OFF;
const uint8_t g_bg96_get_service_status[]      = BG96_ATC_GET_SERVICE_STATUS;
const uint8_t g_bg96_set_provider[]            = BG96_ATC_SET_PROVIDER;
const uint8_t g_bg96_get_pdn_state[]           = BG96_ATC_GET_PDN_STATE;
const uint8_t g_bg96_activate_pdn[]            = BG96_ATC_ACTIVATE_PDN;
const uint8_t g_bg96_atc_get_ipaddr[]          = BG96_ATC_GET_IPADDR;
const uint8_t g_bg96_atc_get_psm[]             = BG96_ATC_GET_PSM;
const uint8_t g_bg96_atc_set_psm[]             = BG96_ATC_SET_PSM;
const uint8_t g_bg96_atc_get_edrx[]            = BG96_ATC_GET_EDRX;
const uint8_t g_bg96_atc_set_edrx[]            = BG96_ATC_SET_EDRX;
const uint8_t g_bg96_atc_get_signal[]          = BG96_ATC_GET_SIGNAL_STRENGTH;
const uint8_t g_bg96_atc_get_sw_revision[]     = BG96_ATC_GET_SW_REVISION;
const uint8_t g_bg96_atc_get_serial_num[]      = BG96_ATC_GET_SERIAL_NUMBER;
const uint8_t g_bg96_atc_get_svn[]             = BG96_ATC_GET_SVN;
const uint8_t g_bg96_atc_get_module_name[]     = BG96_ATC_GET_MODULE_NAME;
const uint8_t g_bg96_atc_get_maker_name[]      = BG96_ATC_GET_MAKER_NAME;
const uint8_t g_bg96_atc_get_imsi[]            = BG96_ATC_GET_IMSI;
const uint8_t g_bg96_atc_send_command_sim[]    = BG96_ATC_SEND_COMMAND_TO_SIM;
const uint8_t g_bg96_atc_set_inter_config[]    = BG96_ATC_SET_INTER_CONFIG;
const uint8_t g_bg96_atc_set_ring_config[]     = BG96_ATC_SET_RING_CONFIG;
const uint8_t g_bg96_atc_set_psm_config[]      = BG96_ATC_SET_PSM_CONFIG;
const uint8_t g_bg96_atc_set_ind_notify[]      = BG96_ATC_SET_IND_NOTIFY;
const uint8_t g_bg96_atc_get_phone_num[]       = BG96_ATC_GET_PHONE_NUM;
const uint8_t g_bg96_atc_get_iccid[]           = BG96_ATC_GET_ICCID;
const uint8_t g_bg96_atc_ping[]                = BG96_ATC_PING;
const uint8_t g_bg96_atc_get_cellinfo[]        = BG96_ATC_GET_CELLINFO;
const uint8_t g_bg96_atc_set_ctm[]             = BG96_ATC_SET_CTM;
const uint8_t g_bg96_atc_get_ctm[]             = BG96_ATC_GET_CTM;
const uint8_t g_bg96_atc_set_band[]            = BG96_ATC_SET_BAND;
const uint8_t g_bg96_atc_factoryreset[]        = BG96_ATC_FACTORYRESET;
const uint8_t g_bg96_atc_smcwrx[]              = BG96_ATC_SMCWRX;
const uint8_t g_bg96_atc_smcwtx[]              = BG96_ATC_SMCWTX;
const uint8_t g_bg96_atc_cgpiaf[]              = BG96_ATC_CGPIAF;
const uint8_t g_bg96_atc_ceer[]                = BG96_ATC_CEER;
const uint8_t g_bg96_atc_firmupgrade[]         = BG96_ATC_FIRMUPGRADE;
const uint8_t g_bg96_atc_firmupgrade_ssl[]     = BG96_ATC_FIRMUPGRADE_SSL;
const uint8_t g_bg96_atc_firmupgrade_check[]   = BG96_ATC_FIRMUPGRADE_CHECK;
const uint8_t g_bg96_atc_get_lr_svn[]          = BG96_ATC_GET_LR_SVN;
const uint8_t g_bg96_write_certificate[]       = BG96_ATC_WRITE_CERTIFICATE;
const uint8_t g_bg96_erase_certificate[]       = BG96_ATC_ERASE_CERTIFICATE;
const uint8_t g_bg96_get_certificate[]         = BG96_ATC_GET_CERTIFICATE;
const uint8_t g_bg96_config_ssl_profile[]      = BG96_ATC_CONFIG_SSL_PROFILE;
#if (CELLULAR_IMPLEMENT_TYPE == 'B')
const uint8_t g_bg96_config_ssl_socket[]       = BG96_ATC_CONFIG_SSL_SOCKET;
#endif
const uint8_t g_bg96_no_command[]              = BG96_NO_COMMAND;

const uint8_t * const gp_at_command[ATC_LIST_MAX] =
{
    g_bg96_echo_off,
    g_bg96_function_level_check,
    g_bg96_function_level,
    g_bg96_pin_lock_check,
    g_bg96_pin_lock_release,
    g_bg96_connect_socket,
    g_bg96_close_socket,
    g_bg96_send_socket,
    g_bg96_recv_socket,
    g_bg96_dns_lookup,
    g_bg96_ap_config,
    g_bg96_private_ap_config,
    g_bg96_ap_config_check,
    g_bg96_user_config,
    g_bg96_clear_config,
    g_bg96_socket_config_1,
    g_bg96_socket_config_2,
    g_bg96_listening_socket,
    g_bg96_connect_check,
    g_bg96_set_connect_status,
    g_bg96_shutdown,
    g_bg96_get_time,
    g_bg96_set_time,
    g_bg96_reset,
    g_bg96_set_notice_level,
    g_bg96_get_notice_level,
    g_bg96_auto_connect,
    g_bg96_auto_connect_check,
    g_bg96_sim_st_off,
    g_bg96_get_service_status,
    g_bg96_set_provider,
    g_bg96_get_pdn_state,
    g_bg96_activate_pdn,
    g_bg96_atc_get_ipaddr,
    g_bg96_atc_get_psm,
    g_bg96_atc_set_psm,
    g_bg96_atc_get_edrx,
    g_bg96_atc_set_edrx,
    g_bg96_atc_get_signal,
    g_bg96_atc_get_sw_revision,
    g_bg96_atc_get_serial_num,
    g_bg96_atc_get_svn,
    g_bg96_atc_get_module_name,
    g_bg96_atc_get_maker_name,
    g_bg96_atc_get_imsi,
    g_bg96_atc_send_command_sim,
    g_bg96_atc_set_inter_config,
    g_bg96_atc_set_ring_config,
    g_bg96_atc_set_psm_config,
    g_bg96_atc_set_ind_notify,
    g_bg96_atc_get_phone_num,
    g_bg96_atc_get_iccid,
    g_bg96_atc_ping,
    g_bg96_atc_get_cellinfo,
    g_bg96_atc_set_ctm,
    g_bg96_atc_get_ctm,
    g_bg96_atc_set_band,
    g_bg96_atc_factoryreset,
    g_bg96_atc_smcwrx,
    g_bg96_atc_smcwtx,
    g_bg96_atc_cgpiaf,
    g_bg96_atc_ceer,
    g_bg96_atc_firmupgrade,
    g_bg96_atc_firmupgrade_ssl,
    g_bg96_atc_firmupgrade_check,
    g_bg96_atc_get_lr_svn,
    g_bg96_write_certificate,
    g_bg96_erase_certificate,
    g_bg96_get_certificate,
    g_bg96_config_ssl_profile,
#if (CELLULAR_IMPLEMENT_TYPE == 'B')
    g_bg96_config_ssl_socket,
#endif
    g_bg96_no_command,
};

/**********************************************************************************************************************
 * Private (static) variables and functions
 *********************************************************************************************************************/

/*****************************************************************************
 * Function Name  @fn            atc_generate
 * Description    @details       Generate the AT command.
 * Arguments      @param[in/out] p_command_buff -
 *                                  Pointer to store the command.
 *                @param[in]     pp_command -
 *                                  Pointer to AT command.
 *                @param[in]     pp_command_arg -
 *                                  Pointer to the argument of the AT command.
 ****************************************************************************/
void atc_generate(uint8_t * const p_command_buff, const uint8_t * const p_command,
                                                    const uint8_t ** const pp_command_arg)
{
    memset(p_command_buff, 0, CELLULAR_ATC_BUFF_SIZE);
    if (NULL == pp_command_arg)
    {
        sprintf((char *)p_command_buff,     // (uint8_t *) -> (char *)
                (const char *)p_command);   // (uint8_t *) -> (char *)
    }
    else
    {
        sprintf((char *)p_command_buff,     // (uint8_t *) -> (char *)
                (const char *)p_command,    // (uint8_t *) -> (char *)
                        pp_command_arg[0],
                        pp_command_arg[1],
                        pp_command_arg[2],
                        pp_command_arg[3],
                        pp_command_arg[4],
                        pp_command_arg[5],
                        pp_command_arg[6],
                        pp_command_arg[7]);
    }
    CELLULAR_LOG_DEBUG(("generated AT command: %s", p_command_buff));
    return;
}
/**********************************************************************************************************************
 * End of function atc_generate
 *********************************************************************************************************************/

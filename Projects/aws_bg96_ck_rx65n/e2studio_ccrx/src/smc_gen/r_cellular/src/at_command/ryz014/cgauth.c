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
 * File Name    : cgauth.c
 * Description  : Function to execute the AT command (CGAUTH).
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "at_command.h"
#include "cellular_private_api.h"

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
 * Function Name  @fn            atc_cgauth
 *
 * BG96: APN authentication (auth_type / username / password) is configured via
 * AT+QICSGP arguments inside atc_cgdcont(). A separate AT+CGAUTH is redundant
 * and BG96 returns ERROR for the "AT+CGAUTH=<cid>,0" form that the original
 * RYZ014A flow uses. The cbt-aqua reference driver does not call CGAUTH at
 * all and connects successfully via QICSGP only. Therefore both atc_cgauth
 * and atc_cgauth_reset are no-op SUCCESS for BG96.
 ************************************************************************************************/
e_cellular_err_t atc_cgauth(st_cellular_ctrl_t * const p_ctrl, const st_cellular_ap_cfg_t * const p_ap_cfg)
{
    (void) p_ctrl;
    (void) p_ap_cfg;
    return CELLULAR_SUCCESS;
}
/**********************************************************************************************************************
 * End of function atc_cgauth
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            atc_cgauth_reset
 ************************************************************************************************/
e_cellular_err_t atc_cgauth_reset(st_cellular_ctrl_t * const p_ctrl)
{
    (void) p_ctrl;
    return CELLULAR_SUCCESS;
}
/**********************************************************************************************************************
 * End of function atc_cgauth_reset
 *********************************************************************************************************************/

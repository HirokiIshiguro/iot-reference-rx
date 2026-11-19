/*
* Copyright (c) 2016 - 2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/***********************************************************************************************************************
* File Name    : r_s12ad_rx_pinset.c
* Version      : 1.0.2
* Device(s)    : R5F5671EHxFB
* Tool-Chain   : RXC toolchain
* Description  : Setting of port and mpc registers
***********************************************************************************************************************/

/***********************************************************************************************************************
Includes
***********************************************************************************************************************/
#include "r_s12ad_rx_pinset.h"
#include "platform.h"

/***********************************************************************************************************************
Global variables and functions
***********************************************************************************************************************/

/***********************************************************************************************************************
* Function Name: R_ADC_PinSet_S12AD0
* Description  : This function initializes pins for r_s12ad_rx module
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void R_ADC_PinSet_S12AD0()
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set AN000 pin */
    PORT4.PCR.BIT.B0 = 0U;
    PORT4.PDR.BIT.B0 = 0U;
    PORT4.PMR.BIT.B0 = 0U;
    MPC.P40PFS.BYTE = 0x80U;

    /* Set AN001 pin */
    PORT4.PCR.BIT.B1 = 0U;
    PORT4.PDR.BIT.B1 = 0U;
    PORT4.PMR.BIT.B1 = 0U;
    MPC.P41PFS.BYTE = 0x80U;

    /* Set AN002 pin */
    PORT4.PCR.BIT.B2 = 0U;
    PORT4.PDR.BIT.B2 = 0U;
    PORT4.PMR.BIT.B2 = 0U;
    MPC.P42PFS.BYTE = 0x80U;

    /* Set AN003 pin */
    PORT4.PCR.BIT.B3 = 0U;
    PORT4.PDR.BIT.B3 = 0U;
    PORT4.PMR.BIT.B3 = 0U;
    MPC.P43PFS.BYTE = 0x80U;

    /* Set AN004 pin */
    PORT4.PCR.BIT.B4 = 0U;
    PORT4.PDR.BIT.B4 = 0U;
    PORT4.PMR.BIT.B4 = 0U;
    MPC.P44PFS.BYTE = 0x80U;

    /* Set AN005 pin */
    PORT4.PCR.BIT.B5 = 0U;
    PORT4.PDR.BIT.B5 = 0U;
    PORT4.PMR.BIT.B5 = 0U;
    MPC.P45PFS.BYTE = 0x80U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}


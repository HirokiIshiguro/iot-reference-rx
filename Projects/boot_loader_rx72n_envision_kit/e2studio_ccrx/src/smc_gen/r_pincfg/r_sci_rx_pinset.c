/*
* Copyright (c) 2016 - 2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/***********************************************************************************************************************
* File Name    : r_sci_rx_pinset.c
* Version      : 1.0.2
* Device(s)    : R5F572NNHxFB
* Tool-Chain   : RXC toolchain
* Description  : Setting of port and mpc registers
***********************************************************************************************************************/

/***********************************************************************************************************************
Includes
***********************************************************************************************************************/
#include "r_sci_rx_pinset.h"
#include "platform.h"

/***********************************************************************************************************************
Global variables and functions
***********************************************************************************************************************/

/***********************************************************************************************************************
* Function Name: R_SCI_PinSet_SCI2
* Description  : This function initializes pins for r_sci_rx module
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void R_SCI_PinSet_SCI2()
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set RXD2/SMISO2 pin */
    MPC.P12PFS.BYTE = 0x0AU;
    PORT1.PMR.BIT.B2 = 1U;

    /* Set TXD2/SMOSI2 pin */
    MPC.P13PFS.BYTE = 0x0AU;
    PORT1.PMR.BIT.B3 = 1U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}

/***********************************************************************************************************************
* Function Name: R_SCI_PinSet_SCI7
* Description  : This function initializes pins for r_sci_rx module
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void R_SCI_PinSet_SCI7()
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set RXD7/SMISO7 pin */
    MPC.P92PFS.BYTE = 0x0AU;
    PORT9.PMR.BIT.B2 = 1U;

    /* Set TXD7/SMOSI7 pin */
    MPC.P90PFS.BYTE = 0x0AU;
    PORT9.PMR.BIT.B0 = 1U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}


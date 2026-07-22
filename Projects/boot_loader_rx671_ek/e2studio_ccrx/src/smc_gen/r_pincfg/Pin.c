/*
* Copyright (c) 2016 - 2026 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/***********************************************************************************************************************
* File Name        : Pin.c
* Version          : 1.0.2
* Device(s)        : R5F5671EHxFB
* Description      : This file implements SMC pin code generation.
***********************************************************************************************************************/

/***********************************************************************************************************************
Pragma directive
***********************************************************************************************************************/
/* Start user code for pragma. Do not edit comment generated here */
/* End user code. Do not edit comment generated here */

/***********************************************************************************************************************
Includes
***********************************************************************************************************************/
#include "r_cg_macrodriver.h"
/* Start user code for include. Do not edit comment generated here */
/* End user code. Do not edit comment generated here */
#include "r_cg_userdefine.h"

/***********************************************************************************************************************
Global variables and functions
***********************************************************************************************************************/
/* Start user code for global. Do not edit comment generated here */
/* End user code. Do not edit comment generated here */

/***********************************************************************************************************************
* Function Name: R_Pins_Create
* Description  : This function initializes Smart Configurator pins
* Arguments    : None
* Return Value : None
***********************************************************************************************************************/

void R_Pins_Create(void)
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set EXTAL pin */
    PORT3.PMR.BYTE &= 0xBFU;
    PORT3.PDR.BYTE &= 0xBFU;

    /* Set RXD6 pin */
    MPC.P01PFS.BYTE = 0x0AU;
    PORT0.PMR.BYTE |= 0x02U;

    /* Set TXD6 pin */
    PORT0.PODR.BYTE |= 0x01U;
    MPC.P00PFS.BYTE = 0x0AU;
    PORT0.PDR.BYTE |= 0x01U;
    // PORT0.PMR.BIT.B0 = 1U; // Please set the PMR bit after TE bit is set to 1.

    /* Set XTAL pin */
    PORT3.PMR.BYTE &= 0x7FU;
    PORT3.PDR.BYTE &= 0x7FU;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}


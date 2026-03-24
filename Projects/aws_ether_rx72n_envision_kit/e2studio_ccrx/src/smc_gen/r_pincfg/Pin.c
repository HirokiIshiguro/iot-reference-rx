/*
* Copyright (c) 2016 - 2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/***********************************************************************************************************************
* File Name        : Pin.c
* Version          : 1.0.2
* Device(s)        : R5F572NNHxFB
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

    /* Set AN115 pin */
    PORT9.PMR.BYTE &= 0xFDU;
    PORT9.PDR.BYTE &= 0xFDU;
    MPC.P91PFS.BYTE = 0x80U;

    /* Set AN117 pin */
    PORT9.PMR.BYTE &= 0xF7U;
    PORT9.PDR.BYTE &= 0xF7U;
    MPC.P93PFS.BYTE = 0x80U;

    /* Set ET0_LINKSTA pin */
    MPC.P54PFS.BYTE = 0x11U;
    PORT5.PMR.BYTE |= 0x10U;

    /* Set ET0_MDC pin */
    MPC.P72PFS.BYTE = 0x11U;
    PORT7.PMR.BYTE |= 0x04U;

    /* Set ET0_MDIO pin */
    MPC.P71PFS.BYTE = 0x11U;
    PORT7.PMR.BYTE |= 0x02U;

    /* Set IRQ2 pin */
    MPC.PD2PFS.BYTE = 0x40U;
    PORTD.PMR.BYTE &= 0xFBU;
    PORTD.PDR.BYTE &= 0xFBU;

    /* Set REF50CK0 pin */
    MPC.P76PFS.BYTE = 0x12U;
    PORT7.PMR.BYTE |= 0x40U;

    /* Set RMII0_CRS_DV pin */
    MPC.P83PFS.BYTE = 0x12U;
    PORT8.PMR.BYTE |= 0x08U;

    /* Set RMII0_RXD0 pin */
    MPC.P75PFS.BYTE = 0x12U;
    PORT7.PMR.BYTE |= 0x20U;

    /* Set RMII0_RXD1 pin */
    MPC.P74PFS.BYTE = 0x12U;
    PORT7.PMR.BYTE |= 0x10U;

    /* Set RMII0_RX_ER pin */
    MPC.P77PFS.BYTE = 0x12U;
    PORT7.PMR.BYTE |= 0x80U;

    /* Set RMII0_TXD0 pin */
    MPC.P81PFS.BYTE = 0x12U;
    PORT8.PMR.BYTE |= 0x02U;

    /* Set RMII0_TXD1 pin */
    MPC.P82PFS.BYTE = 0x12U;
    PORT8.PMR.BYTE |= 0x04U;

    /* Set RMII0_TXD_EN pin */
    MPC.PB4PFS.BYTE = 0x12U;
    PORTB.PMR.BYTE |= 0x10U;

    /* Set RXD2 pin */
    MPC.P12PFS.BYTE = 0x0AU;
    PORT1.PMR.BYTE |= 0x04U;

    /* Set RXD7 pin */
    MPC.P92PFS.BYTE = 0x0AU;
    PORT9.PMR.BYTE |= 0x04U;

    /* Set TXD2 pin */
    PORT1.PODR.BYTE |= 0x08U;
    MPC.P13PFS.BYTE = 0x0AU;
    PORT1.PDR.BYTE |= 0x08U;

    /* Set TXD7 pin */
    PORT9.PODR.BYTE |= 0x01U;
    MPC.P90PFS.BYTE = 0x0AU;
    PORT9.PDR.BYTE |= 0x01U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}


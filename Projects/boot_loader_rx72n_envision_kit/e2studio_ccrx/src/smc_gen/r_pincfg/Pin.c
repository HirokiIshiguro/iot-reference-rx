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

    /* Set CLKOUT25M pin */
    MPC.P56PFS.BYTE = 0x2AU;
    PORT5.PMR.BYTE |= 0x40U;

    /* Set LCD_CLK pin */
    MPC.PB5PFS.BYTE = 0x25U;
    PORTB.PMR.BYTE |= 0x20U;

    /* Set LCD_DATA0 pin */
    MPC.PB0PFS.BYTE = 0x25U;
    PORTB.PMR.BYTE |= 0x01U;

    /* Set LCD_DATA1 pin */
    MPC.PA7PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x80U;

    /* Set LCD_DATA2 pin */
    MPC.PA6PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x40U;

    /* Set LCD_DATA3 pin */
    MPC.PA5PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x20U;

    /* Set LCD_DATA4 pin */
    MPC.PA4PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x10U;

    /* Set LCD_DATA5 pin */
    MPC.PA3PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x08U;

    /* Set LCD_DATA6 pin */
    MPC.PA2PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x04U;

    /* Set LCD_DATA7 pin */
    MPC.PA1PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x02U;

    /* Set LCD_DATA8 pin */
    MPC.PA0PFS.BYTE = 0x25U;
    PORTA.PMR.BYTE |= 0x01U;

    /* Set LCD_DATA9 pin */
    MPC.PE7PFS.BYTE = 0x25U;
    PORTE.PMR.BYTE |= 0x80U;

    /* Set LCD_DATA10 pin */
    MPC.PE6PFS.BYTE = 0x25U;
    PORTE.PMR.BYTE |= 0x40U;

    /* Set LCD_DATA11 pin */
    MPC.PE5PFS.BYTE = 0x25U;
    PORTE.PMR.BYTE |= 0x20U;

    /* Set LCD_DATA12 pin */
    MPC.PE4PFS.BYTE = 0x25U;
    PORTE.PMR.BYTE |= 0x10U;

    /* Set LCD_DATA13 pin */
    MPC.PE3PFS.BYTE = 0x25U;
    PORTE.PMR.BYTE |= 0x08U;

    /* Set LCD_DATA14 pin */
    MPC.PE2PFS.BYTE = 0x25U;
    PORTE.PMR.BYTE |= 0x04U;

    /* Set LCD_DATA15 pin */
    MPC.PE1PFS.BYTE = 0x25U;
    PORTE.PMR.BYTE |= 0x02U;

    /* Set LCD_TCON0 pin */
    MPC.PB4PFS.BYTE = 0x25U;
    PORTB.PMR.BYTE |= 0x10U;

    /* Set LCD_TCON2 pin */
    MPC.PB2PFS.BYTE = 0x25U;
    PORTB.PMR.BYTE |= 0x04U;

    /* Set LCD_TCON3 pin */
    MPC.PB1PFS.BYTE = 0x25U;
    PORTB.PMR.BYTE |= 0x02U;

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
    // PORT1.PMR.BIT.B3 = 1U; // Please set the PMR bit after TE bit is set to 1.

    /* Set TXD7 pin */
    PORT9.PODR.BYTE |= 0x01U;
    MPC.P90PFS.BYTE = 0x0AU;
    PORT9.PDR.BYTE |= 0x01U;
    // PORT9.PMR.BIT.B0 = 1U; // Please set the PMR bit after TE bit is set to 1.

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}


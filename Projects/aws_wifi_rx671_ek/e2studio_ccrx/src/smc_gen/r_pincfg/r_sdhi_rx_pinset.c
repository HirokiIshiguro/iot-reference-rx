/*
* Copyright (c) 2016 - 2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/***********************************************************************************************************************
* File Name    : r_sdhi_rx_pinset.c
* Version      : 1.0.2
* Device(s)    : R5F5671EHxFB
* Tool-Chain   : RXC toolchain
* Description  : Setting of port and mpc registers
***********************************************************************************************************************/

/***********************************************************************************************************************
Includes
***********************************************************************************************************************/
#include "r_sdhi_rx_pinset.h"
#include "platform.h"

/***********************************************************************************************************************
Global variables and functions
***********************************************************************************************************************/
/***********************************************************************************************************************
* Function Name: R_SDHI_PinSetInit
* Description  : This function initializes pins for r_sdhi_rx module
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void R_SDHI_PinSetInit()
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set SDHI_CLK pin */
    PORTD.PMR.BIT.B5 = 0U;
    PORTD.DSCR.BIT.B5 = 1U;
    PORTD.PCR.BIT.B5 = 0U;
    PORTD.PODR.BIT.B5 = 0U;
    PORTD.PDR.BIT.B5 = 1U;
    MPC.PD5PFS.BYTE = 0x00U;

    /* Set SDHI_CMD pin */
    PORTD.PMR.BIT.B4 = 0U;
    PORTD.DSCR.BIT.B4 = 1U;
    PORTD.PCR.BIT.B4 = 0U;
    PORTD.PODR.BIT.B4 = 0U;
    PORTD.PDR.BIT.B4 = 1U;
    MPC.PD4PFS.BYTE = 0x00U;

    /* Set SDHI_CD pin */
    PORT8.PMR.BIT.B1 = 0U;
    PORT8.PCR.BIT.B1 = 0U;
    PORT8.PDR.BIT.B1 = 0U;
    MPC.P81PFS.BYTE = 0x1AU;
    PORT8.PMR.BIT.B1 = 1U;

    /* Set SDHI_D0 pin */
    PORTD.PMR.BIT.B6 = 0U;
    PORTD.DSCR.BIT.B6 = 1U;
    PORTD.PCR.BIT.B6 = 0U;
    PORTD.PODR.BIT.B6 = 0U;
    PORTD.PDR.BIT.B6 = 1U;
    MPC.PD6PFS.BYTE = 0x00U;

    /* Set SDHI_D1 pin */
    PORTD.PMR.BIT.B7 = 0U;
    PORTD.DSCR.BIT.B7 = 1U;
    PORTD.PCR.BIT.B7 = 0U;
    PORTD.PODR.BIT.B7 = 0U;
    PORTD.PDR.BIT.B7 = 1U;
    MPC.PD7PFS.BYTE = 0x00U;

    /* Set SDHI_D2 pin */
    PORTD.PMR.BIT.B2 = 0U;
    PORTD.DSCR.BIT.B2 = 1U;
    PORTD.PCR.BIT.B2 = 0U;
    PORTD.PODR.BIT.B2 = 0U;
    PORTD.PDR.BIT.B2 = 1U;
    MPC.PD2PFS.BYTE = 0x00U;

    /* Set SDHI_D3 pin */
    PORTD.PMR.BIT.B3 = 0U;
    PORTD.DSCR.BIT.B3 = 1U;
    PORTD.PCR.BIT.B3 = 0U;
    PORTD.PODR.BIT.B3 = 0U;
    PORTD.PDR.BIT.B3 = 1U;
    MPC.PD3PFS.BYTE = 0x00U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}


/***********************************************************************************************************************
* Function Name: R_SDHI_PinSetTransfer
* Description  : This function enables SD communication
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void R_SDHI_PinSetTransfer()
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set SDHI_CLK pin */
    MPC.PD5PFS.BYTE = 0x1AU;
    PORTD.PMR.BIT.B5 = 1U;

    /* Set SDHI_CMD pin */
    MPC.PD4PFS.BYTE = 0x1AU;
    PORTD.PMR.BIT.B4 = 1U;

    /* Set SDHI_CD pin */
    MPC.P81PFS.BYTE = 0x1AU;
    PORT8.PMR.BIT.B1 = 1U;

    /* Set SDHI_D0 pin */
    MPC.PD6PFS.BYTE = 0x1AU;
    PORTD.PMR.BIT.B6 = 1U;

    /* Set SDHI_D1 pin */
    MPC.PD7PFS.BYTE = 0x1AU;
    PORTD.PMR.BIT.B7 = 1U;

    /* Set SDHI_D2 pin */
    MPC.PD2PFS.BYTE = 0x1AU;
    PORTD.PMR.BIT.B2 = 1U;

    /* Set SDHI_D3 pin */
    MPC.PD3PFS.BYTE = 0x1AU;
    PORTD.PMR.BIT.B3 = 1U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}

/***********************************************************************************************************************
* Function Name: R_SDHI_PinSetDetection
* Description  : This function disables SD communication and enables card detection and write protection
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void R_SDHI_PinSetDetection()
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set SDHI_CLK pin */
    PORTD.PMR.BIT.B5 = 0U;
    MPC.PD5PFS.BYTE = 0x00U;

    /* Set SDHI_CMD pin */
    PORTD.PMR.BIT.B4 = 0U;
    MPC.PD4PFS.BYTE = 0x00U;

    /* Set SDHI_CD pin */
    MPC.P81PFS.BYTE = 0x1AU;
    PORT8.PMR.BIT.B1 = 1U;

    /* Set SDHI_D0 pin */
    PORTD.PMR.BIT.B6 = 0U;
    MPC.PD6PFS.BYTE = 0x00U;

    /* Set SDHI_D1 pin */
    PORTD.PMR.BIT.B7 = 0U;
    MPC.PD7PFS.BYTE = 0x00U;

    /* Set SDHI_D2 pin */
    PORTD.PMR.BIT.B2 = 0U;
    MPC.PD2PFS.BYTE = 0x00U;

    /* Set SDHI_D3 pin */
    PORTD.PMR.BIT.B3 = 0U;
    MPC.PD3PFS.BYTE = 0x00U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}

/***********************************************************************************************************************
* Function Name: R_SDHI_PinSetEnd
* Description  : This function ends pins for r_sdhi_rx module
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void R_SDHI_PinSetEnd()
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    /* Set SDHI_CLK pin */
    PORTD.PMR.BIT.B5 = 0U;
    MPC.PD5PFS.BYTE = 0x00U;

    /* Set SDHI_CMD pin */
    PORTD.PMR.BIT.B4 = 0U;
    MPC.PD4PFS.BYTE = 0x00U;

    /* Set SDHI_CD pin */
    PORT8.PMR.BIT.B1 = 0U;
    MPC.P81PFS.BYTE = 0x00U;

    /* Set SDHI_D0 pin */
    PORTD.PMR.BIT.B6 = 0U;
    MPC.PD6PFS.BYTE = 0x00U;

    /* Set SDHI_D1 pin */
    PORTD.PMR.BIT.B7 = 0U;
    MPC.PD7PFS.BYTE = 0x00U;

    /* Set SDHI_D2 pin */
    PORTD.PMR.BIT.B2 = 0U;
    MPC.PD2PFS.BYTE = 0x00U;

    /* Set SDHI_D3 pin */
    PORTD.PMR.BIT.B3 = 0U;
    MPC.PD3PFS.BYTE = 0x00U;

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}


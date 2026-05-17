/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/**********************************************************************************************************************
 * File Name    : user_init.c
 * Description  : User initialization
 *********************************************************************************************************************/
/**********************************************************************************************************************
 * History : DD.MM.YYYY Version Description
 *         : 29.12.2019 1.00 First Release
 *********************************************************************************************************************/

/******************************************************************************
 Includes   <System Includes> , "Project Includes"
 ******************************************************************************/

/* for using C standard library */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* for using FIT Module */
#include "platform.h"
#include "r_pinset.h"
#include "r_flash_rx_if.h"
#include "Pin.h"

/* for using FreeRTOS */
#include "FreeRTOS.h"
#include "task.h"
#include "r_sci_rx_if.h"
#include "spi_logic_probe.h"
#include "trace_spi_transport.h"

#ifndef SPI_LOGIC_PROBE_ENABLE
#define SPI_LOGIC_PROBE_ENABLE    (0)
#endif

/**********************************************************************************************************************
Typedef definitions
**********************************************************************************************************************/

/******************************************************************************
 External variables
 ******************************************************************************/

/******************************************************************************
 Private global variables
 ******************************************************************************/
char* txBuffer = NULL;


/******************************************************************************

 External functions
 ******************************************************************************/


void UserInitialization (void);
uint32_t TraceRxTraceTimerGetValue(void);
uint32_t TraceRxTraceTimerGetFrequency(void);

uint32_t TraceRxTraceTimerGetFrequency(void)
{
    return (uint32_t) (configPERIPHERAL_CLOCK_HZ / 8UL);
}

uint32_t TraceRxTraceTimerGetValue(void)
{
    const uint32_t period = ((uint32_t) CMT0.CMCOR) + 1UL;
    uint32_t tick_count_1 = (uint32_t) xTaskGetTickCountFromISR();
    uint32_t timer_count = (uint32_t) CMT0.CMCNT;
    uint32_t tick_count_2 = (uint32_t) xTaskGetTickCountFromISR();

    if (tick_count_2 != tick_count_1)
    {
        tick_count_1 = tick_count_2;
        timer_count = (uint32_t) CMT0.CMCNT;
    }

    if ((IR(CMT0, CMI0) != 0U) && (timer_count < (period / 2U)))
    {
        tick_count_1++;
    }

    return (tick_count_1 * period) + timer_count;
}

/******************************************************************************
 Function Name   : UserInitialization
 Description     : Initialize Smart Configurator pins
 Arguments       : none
 Return value    : none
 ******************************************************************************/
void UserInitialization(void)
{
    /* enable MCU pins */
    R_Pins_Create();

#if (SPI_LOGIC_PROBE_ENABLE == 1)
    SPI_LogicProbeRun();
#endif

    (void) TraceSpiTransport_Init();

    /* Buffer to contain the whole string of printf before sending to SCI */
    txBuffer = pvPortMalloc((size_t)SCI_CFG_CH5_TX_BUFSIZ * 5);
    if (NULL != txBuffer)
    {
        memset(txBuffer, 0, SCI_CFG_CH5_TX_BUFSIZ * 5);
    }
    else
    {
        /* txBuffer allocation failed */
    }
}
/******************************************************************************
 End of function UserInitialization()
 ******************************************************************************/


/******************************************************************************
 End  Of File
 ******************************************************************************/


/*
* Copyright (c) 2026 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/**********************************************************************************************************************
 * File Name    : user_init.c
 * Description  : User initialization for the EK-RX671 Wi-Fi project.
 *********************************************************************************************************************/

#include <stddef.h>
#include <string.h>

#include "FreeRTOS.h"
#include "r_sci_rx_if.h"

char * txBuffer = NULL;

void UserInitialization(void)
{
    if (NULL == txBuffer)
    {
        txBuffer = pvPortMalloc((size_t)SCI_CFG_CH6_TX_BUFSIZ * 5U);
        if (NULL != txBuffer)
        {
            memset(txBuffer, 0, (size_t)SCI_CFG_CH6_TX_BUFSIZ * 5U);
        }
    }
}

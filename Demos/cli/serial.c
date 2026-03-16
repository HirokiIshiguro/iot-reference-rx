/*
 * FreeRTOS V202211.00
 * Copyright (C) 2020 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
 * Modifications Copyright (C) 2023-2025 Renesas Electronics Corporation or its affiliates.
 *
 * SPDX-License-Identifier: MIT
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * https://www.FreeRTOS.org
 * https://github.com/FreeRTOS
 *
 */

/* Kernel includes. */
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

/* Demo program includes. */
#include "serial.h"

/* Renesas includes. */
#include "platform.h"
#include "r_sci_rx_if.h"
#include "r_byteq_if.h"
#include "r_sci_rx_pinset.h"

/* FreeRTOS CLI Command Console */
#if !defined(BSP_CFG_SCI_UART_TERMINAL_ENABLE)
#error "Error! Need to define MY_BSP_CFG_SERIAL_TERM_SCI in r_bsp_config.h"
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (0)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI0())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH0)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (1)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI1())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH1)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (2)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI2())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH2)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (3)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI3())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH3)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (4)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI4())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH4)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (5)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI5())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH5)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (6)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI6())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH6)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (7)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI7())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH7)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (8)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI8())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH8)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (9)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI9())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH9)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (10)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI10())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH10)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (11)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI11())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH11)
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (12)
/* U_SCI_UART_CLI_PINSET macro definition */
#define U_SCI_UART_CLI_PINSET()  (R_SCI_PinSet_SCI12())
#define U_SCI_UART_CLI_SCI_CH    (SCI_CH12)
#else
#error "Error! Invalid setting for MY_BSP_CFG_SERIAL_TERM_SCI in r_bsp_config.h"
#endif

/* Characters received from the UART are stored in this queue, ready to be
received by the application.  ***NOTE*** Using a queue in this way is very
convenient, but also very inefficient.  It can be used here because characters
will only arrive slowly.  In a higher bandwidth system a circular RAM buffer or
DMA should be used in place of this queue. */
QueueHandle_t xRxQueue = NULL;

/* Board Support Data Structures. */
sci_hdl_t xSerialSciHandle = 0;

extern char* txBuffer;

const TickType_t xMaxBlockTime = pdMS_TO_TICKS( 5000 );

static size_t txIndex = 0;

/* Used to guard access to the UART in case messages are sent to the UART from
more than one task. */
static SemaphoreHandle_t xTransmitMutex = NULL;
static SemaphoreHandle_t xOutCharMutex = NULL;

void CLI_Support_Settings (void);
void vSerialSciCallback ( void *pvArgs );
void CLI_Close (void);

/**********************************************************************************************************************
 * Function Name: CLI_Support_Settings
 * Description  : .
 * Return Value : .
 *********************************************************************************************************************/
void CLI_Support_Settings(void)
{

    /* FreeRTOS CLI Command Console */
    U_SCI_UART_CLI_PINSET();
    sci_cfg_t xSerialSciConfig;
    xSerialSciConfig.async.baud_rate    = BSP_CFG_SCI_UART_TERMINAL_BITRATE;
    xSerialSciConfig.async.clk_src      = SCI_CLK_INT;
    xSerialSciConfig.async.data_size    = SCI_DATA_8BIT;
    xSerialSciConfig.async.parity_en    = SCI_PARITY_OFF;
    xSerialSciConfig.async.parity_type  = SCI_EVEN_PARITY;
    xSerialSciConfig.async.stop_bits    = SCI_STOPBITS_1;
    xSerialSciConfig.async.int_priority = 1; /* lowest at first. */
    R_SCI_Open(U_SCI_UART_CLI_SCI_CH, SCI_MODE_ASYNC, &xSerialSciConfig, vSerialSciCallback, &xSerialSciHandle);

    /* Create the semaphore used to access the UART Tx. */
    xTransmitMutex = xSemaphoreCreateMutex();
    configASSERT( xTransmitMutex );

    /* Create the semaphore used to protect the transmit buffer */
    xOutCharMutex = xSemaphoreCreateMutex();
    configASSERT( xOutCharMutex );
}
/**********************************************************************************************************************
 End of function CLI_Support_Settings
 *********************************************************************************************************************/


/**********************************************************************************************************************
 * Function Name: CLI_Close
 * Description  : .
 * Return Value : .
 *********************************************************************************************************************/
void CLI_Close(void)
{
    R_SCI_Close(xSerialSciHandle);
}
/**********************************************************************************************************************
 End of function CLI_Close
 *********************************************************************************************************************/


/* Callback function which is called from Renesas API's interrupt service routine. */
/**********************************************************************************************************************
 * Function Name: vSerialSciCallback
 * Description  : .
 * Argument     : pvArgs
 * Return Value : .
 *********************************************************************************************************************/
void vSerialSciCallback( void *pvArgs )
{
sci_cb_args_t *pxArgs = (sci_cb_args_t *)pvArgs;

    /* Renesas API has a built-in queue but we will ignore it.  If the queue is not
    full, a received character is passed with SCI_EVT_RX_CHAR event.  If the queue
    is full, a received character is passed with SCI_EVT_RXBUF_OVFL event. */
    if ( (SCI_EVT_RX_CHAR == pxArgs->event) || (SCI_EVT_RXBUF_OVFL == pxArgs->event) )
    {
        BaseType_t xHigherPriorityTaskWoken = pdFALSE;

        configASSERT( xRxQueue );

        /* Characters received from the UART are stored in this queue, ready to be
        received by the application.  ***NOTE*** Using a queue in this way is very
        convenient, but also very inefficient.  It can be used here because
        characters will only arrive slowly.  In a higher bandwidth system a circular
        RAM buffer or DMA should be used in place of this queue. */
        xQueueSendFromISR( xRxQueue, &pxArgs->byte, &xHigherPriorityTaskWoken );

        /* See http://www.freertos.org/xQueueOverwriteFromISR.html for information
        on the semantics of this ISR. */
        portYIELD_FROM_ISR( xHigherPriorityTaskWoken );
    }
}
/**********************************************************************************************************************
 End of function vSerialSciCallback
 *********************************************************************************************************************/


/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
/**********************************************************************************************************************
 * Function Name: xSerialPortInitMinimal
 * Description  : .
 * Arguments    : ulWantedBaud
 *              : uxQueueLength
 * Return Value : .
 *********************************************************************************************************************/
xComPortHandle xSerialPortInitMinimal( unsigned long ulWantedBaud, unsigned portBASE_TYPE uxQueueLength )
{
    (void) ulWantedBaud;
    (void) uxQueueLength;

    /* Characters received from the UART are stored in this queue, ready to be
    received by the application.  ***NOTE*** Using a queue in this way is very
    convenient, but also very inefficient.  It can be used here because
    characters will only arrive slowly.  In a higher bandwidth system a circular
    RAM buffer or DMA should be used in place of this queue. */
    xRxQueue = xQueueCreate( uxQueueLength, sizeof( char ) );
    configASSERT( xRxQueue );

    /* Set interrupt priority. (Other UART settings had been initialized in the
    src/smc_gen/general/r_cg_hardware_setup.c.) */
    uint8_t ucInterruptPriority = configMAX_SYSCALL_INTERRUPT_PRIORITY-1;
    R_SCI_Control(xSerialSciHandle, SCI_CMD_SET_RXI_PRIORITY, (void *) &ucInterruptPriority);
    R_SCI_Control(xSerialSciHandle, SCI_CMD_SET_TXI_PRIORITY, (void *) &ucInterruptPriority);

    /* Only one UART is supported, so it doesn't matter what is returned
    here. */
    return 0;
}
/**********************************************************************************************************************
 End of function xSerialPortInitMinimal
 *********************************************************************************************************************/


/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
/**********************************************************************************************************************
 * Function Name: vSerialPutString
 * Description  : .
 * Arguments    : pcString
 *              : usStringLength
 * Return Value : .
 *********************************************************************************************************************/
void vSerialPutString(const signed char * pcString, unsigned short usStringLength )
{
    /* Don't send the string unless the previous string has been sent. */
    {
        /* Ensure the calling task's notification state is not already
        pending. */
        xTaskNotifyStateClear( NULL );

        uint32_t str_length = usStringLength;
        uint32_t transmit_length = 0;
        sci_err_t sci_err = SCI_SUCCESS;
        uint32_t retry = 0xFFFF;

        if ( xSemaphoreTake( xTransmitMutex, xMaxBlockTime ) == pdPASS )
        {
            while ((retry > 0) && (str_length > 0))
            {
                R_SCI_Control(xSerialSciHandle, SCI_CMD_TX_Q_BYTES_FREE, &transmit_length);

                if (transmit_length > str_length)
                {
                    transmit_length = str_length;
                }

                sci_err = R_SCI_Send(xSerialSciHandle, (uint8_t *) pcString,
                                     transmit_length);

                if ((SCI_ERR_XCVR_BUSY == sci_err) || (SCI_ERR_INSUFFICIENT_SPACE == sci_err))
                {
                    retry--; // retry if previous transmission still in progress or tx buffer is insufficient.
                    continue;
                }

                str_length -= transmit_length;
                pcString += transmit_length;
            }

            /* Must ensure to give the mutex back. */
            xSemaphoreGive( xTransmitMutex );
        }

        if (SCI_SUCCESS != sci_err)
        {
            R_BSP_NOP(); //TODO error handling code
        }
        /* A breakpoint can be set here for debugging. */
        R_BSP_NOP();
    }
}
/**********************************************************************************************************************
 End of function vSerialPutString
 *********************************************************************************************************************/


/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
/**********************************************************************************************************************
 * Function Name: xSerialGetChar
 * Description  : .
 * Arguments    : pxPort
 *              : pcRxedChar
 *              : xBlockTime
 * Return Value : .
 *********************************************************************************************************************/
signed portBASE_TYPE xSerialGetChar( xComPortHandle pxPort, signed char *pcRxedChar, TickType_t xBlockTime )
{
    /* Only one UART is supported. */
    (void) pxPort;

    /* Return a received character, if any are available.  Otherwise block to
    wait for a character. */
    return xQueueReceive( xRxQueue, pcRxedChar, xBlockTime );
}
/**********************************************************************************************************************
 End of function xSerialGetChar
 *********************************************************************************************************************/

/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
/**********************************************************************************************************************
 * Function Name: xSerialPutChar
 * Description  : .
 * Arguments    : pxPort
 *              : cOutChar
 *              : xBlockTime
 * Return Value : .
 *********************************************************************************************************************/
signed portBASE_TYPE xSerialPutChar( xComPortHandle pxPort, signed char cOutChar, TickType_t xBlockTime )
{
    /* Just mapped to vSerialPutString() so the block time is not used. */
    (void) xBlockTime;
    (void) pxPort;

    vSerialPutString( &cOutChar, sizeof( cOutChar ) );
    return pdPASS;
}
/**********************************************************************************************************************
 End of function xSerialPutChar
 *********************************************************************************************************************/


/******************************************************************************
 * Function Name: vOutputChar
 * Description  : Outputs a single character to the UART interface (custom BSP charput function).
 * Argument     : cOutChar
 * Return Value : None
 *****************************************************************************/
void vOutputChar(char cOutChar)
{
    if (xSemaphoreTake(xOutCharMutex, portMAX_DELAY) == pdPASS)
    {
        /* OVERFLOW GUARD: Check if the buffer is full (or near-full) */
        if (txIndex >= (SCI_CFG_CH5_TX_BUFSIZ * 5))
        {
            /* Force a flush now to free up the buffer space */
            vSerialPutString((signed char *)txBuffer, (unsigned short)txIndex);
            txIndex = 0;
        }

        /* Write the character (safe now that space is guaranteed) */
        txBuffer[txIndex++] = (char)cOutChar;

        if (('\r' == txBuffer[txIndex - 1]) || ('\n' == txBuffer[txIndex - 1]))
        {
            vSerialPutString((signed char *)txBuffer, (unsigned short)txIndex); /* Cast to match input arg of vSerialPutString */
            txIndex = 0;
        }

        xSemaphoreGive(xOutCharMutex);
    }
}
/******************************************************************************
 End of function vOutputChar
 *****************************************************************************/


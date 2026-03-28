/*
 * FreeRTOS V202211.00
 * Copyright (C) 2020 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
 * Modifications Copyright (C) 2023-2025 Renesas Electronics Corporation or its affiliates.
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
#include <string.h>

/* Demo program includes. */
#include "serial.h"

/* Renesas includes. */
#include "platform.h"
#include "Pin.h"
#include "r_sci_rx_if.h"
#include "r_byteq_if.h"

#define U_SCI_UART_CLI_PINSET()  R_Pins_Create()

#ifndef PHASE8B_DEBUG_POLLING_UART
    #define PHASE8B_DEBUG_POLLING_UART    ( 1 )
#endif

/* FreeRTOS CLI Command Console */
#if !defined(BSP_CFG_SCI_UART_TERMINAL_ENABLE)
#error "Error! Need to define MY_BSP_CFG_SERIAL_TERM_SCI in r_bsp_config.h"
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (0)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH0
#define U_SCI_UART_CLI_REG             SCI0
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (1)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH1
#define U_SCI_UART_CLI_REG             SCI1
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (2)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH2
#define U_SCI_UART_CLI_REG             SCI2
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (3)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH3
#define U_SCI_UART_CLI_REG             SCI3
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (4)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH4
#define U_SCI_UART_CLI_REG             SCI4
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (5)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH5
#define U_SCI_UART_CLI_REG             SCI5
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (6)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH6
#define U_SCI_UART_CLI_REG             SCI6
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (7)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH7
#define U_SCI_UART_CLI_REG             SCI7
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (8)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH8
#define U_SCI_UART_CLI_REG             SCI8
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (9)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH9
#define U_SCI_UART_CLI_REG             SCI9
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (10)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH10
#define U_SCI_UART_CLI_REG             SCI10
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (11)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH11
#define U_SCI_UART_CLI_REG             SCI11
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (12)
#define U_SCI_UART_CLI_SCI_CH          SCI_CH12
#define U_SCI_UART_CLI_REG             SCI12
#else
#error "Error! Invalid setting for MY_BSP_CFG_SERIAL_TERM_SCI in r_bsp_config.h"
#endif

/* Characters received from the UART are stored in this queue, ready to be
received by the application.  ***NOTE*** Using a queue in this way is very
convenient, but also very inefficient.  It can be used here because characters
will only arrive slowly.  In a higher bandwidth system a circular RAM buffer or
DMA should be used in place of this queue. */
QueueHandle_t xRxQueue = NULL;

/* When a task calls vSerialPutString() its handle is stored in xSendingTask,
before being placed into the Blocked state (so does not use any CPU time) to
wait for the transmission to end.  The task handle is then used from the UART
transmit end interrupt to remove the task from the Blocked state. */
static TaskHandle_t xSendingTask = NULL;

/* Board Support Data Structures. */
sci_hdl_t xSerialSciHandle = 0;
void CLI_Support_Settings(void);
void vSerialSciCallback( void *pvArgs );
void CLI_Close(void);

#define serialSTARTUP_TRACE_RETRY_LIMIT    ( 200000UL )

static char prvNibbleToHex( uint8_t ucNibble )
{
    ucNibble &= 0x0FU;
    return ( char ) ( ( ucNibble < 10U ) ? ( '0' + ucNibble ) : ( 'A' + ( ucNibble - 10U ) ) );
}

static sci_err_t prvEnsureSerialPortOpen( void )
{
    sci_cfg_t xSerialSciConfig;
    sci_err_t xOpenResult;

    if( 0 != xSerialSciHandle )
    {
        return SCI_SUCCESS;
    }

    U_SCI_UART_CLI_PINSET();
    memset( &xSerialSciConfig, 0, sizeof( xSerialSciConfig ) );
    xSerialSciConfig.async.baud_rate    = BSP_CFG_SCI_UART_TERMINAL_BITRATE;
    xSerialSciConfig.async.clk_src      = SCI_CLK_INT;
    xSerialSciConfig.async.data_size    = SCI_DATA_8BIT;
    xSerialSciConfig.async.parity_en    = SCI_PARITY_OFF;
    xSerialSciConfig.async.parity_type  = SCI_EVEN_PARITY;
    xSerialSciConfig.async.stop_bits    = SCI_STOPBITS_1;
    xSerialSciConfig.async.int_priority = 1;

    xOpenResult = R_SCI_Open( U_SCI_UART_CLI_SCI_CH,
                              SCI_MODE_ASYNC,
                              &xSerialSciConfig,
                              vSerialSciCallback,
                              &xSerialSciHandle );

#if ( PHASE8B_DEBUG_POLLING_UART == 1 ) && ( BSP_CFG_SCI_UART_TERMINAL_CHANNEL == ( 7 ) )
    if( SCI_SUCCESS == xOpenResult )
    {
        IEN( SCI7, TXI7 ) = 0;
        IR( SCI7, TXI7 ) = 0;
        /* Keep RXI/RIE enabled so the CLI can still receive commands on SCI7,
         * but force TX onto the polling path to avoid early boot TXI noise. */
        ICU.GENAL0.LONG &= ~( 1UL << 23 );
        U_SCI_UART_CLI_REG.SCR.BYTE &= ( uint8_t ) ~( 0x84U );
    }
#endif

    return xOpenResult;
}

void CLI_Support_Settings(void)
{
    ( void ) prvEnsureSerialPortOpen();
}

void CLI_Close(void)
{
    if( 0 != xSerialSciHandle )
    {
        R_SCI_Close( xSerialSciHandle );
        xSerialSciHandle = 0;
    }
}

/* Callback function which is called from Renesas API's interrupt service routine. */
void vSerialSciCallback( void *pvArgs )
{
sci_cb_args_t *pxArgs = (sci_cb_args_t *)pvArgs;

    /* Renesas API has a built-in queue but we will ignore it.  If the queue is not
    full, a received character is passed with SCI_EVT_RX_CHAR event.  If the queue
    is full, a received character is passed with SCI_EVT_RXBUF_OVFL event. */
    if( SCI_EVT_RX_CHAR == pxArgs->event || SCI_EVT_RXBUF_OVFL == pxArgs->event )
    {
        BaseType_t xHigherPriorityTaskWoken = pdFALSE;

        if( NULL == xRxQueue )
        {
            return;
        }

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

/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
xComPortHandle xSerialPortInitMinimal( unsigned long ulWantedBaud, unsigned portBASE_TYPE uxQueueLength )
{
    ( void ) ulWantedBaud;
    ( void ) uxQueueLength;

    /* Characters received from the UART are stored in this queue, ready to be
    received by the application.  ***NOTE*** Using a queue in this way is very
    convenient, but also very inefficient.  It can be used here because
    characters will only arrive slowly.  In a higher bandwidth system a circular
    RAM buffer or DMA should be used in place of this queue. */
    xRxQueue = xQueueCreate( uxQueueLength, sizeof( char ) );
    configASSERT( xRxQueue );

    /* Set interrupt priority. (Other UART settings had been initialized in the
    src/smc_gen/general/r_cg_hardware_setup.c.) */
    uint8_t ucInterruptPriority = configMAX_SYSCALL_INTERRUPT_PRIORITY - 1;
    R_SCI_Control( xSerialSciHandle, SCI_CMD_SET_RXI_PRIORITY, ( void * ) &ucInterruptPriority );
    R_SCI_Control( xSerialSciHandle, SCI_CMD_SET_TXI_PRIORITY, ( void * ) &ucInterruptPriority );

    /* Only one UART is supported, so it doesn't matter what is returned
    here. */
    return 0;
}

void vStartupTracePutString( const char * pcMessage )
{
    const uint8_t * pucMessage = ( const uint8_t * ) pcMessage;
    uint32_t ulRetry;

    if( ( NULL == pcMessage ) || ( '\0' == pcMessage[ 0 ] ) )
    {
        return;
    }

    if( SCI_SUCCESS != prvEnsureSerialPortOpen() )
    {
        return;
    }

    while( '\0' != *pucMessage )
    {
        ulRetry = serialSTARTUP_TRACE_RETRY_LIMIT;

        while( ( 0 == U_SCI_UART_CLI_REG.SSR.BIT.TDRE ) && ( ulRetry-- > 0 ) )
        {
            R_BSP_NOP();
        }

        if( 0 == ulRetry )
        {
            return;
        }

        U_SCI_UART_CLI_REG.TDR = *pucMessage++;
    }

    ulRetry = serialSTARTUP_TRACE_RETRY_LIMIT;
    while( ( 0 == U_SCI_UART_CLI_REG.SSR.BIT.TEND ) && ( ulRetry-- > 0 ) )
    {
        R_BSP_NOP();
    }
}

void vStartupTracePutHex32( uint32_t ulValue )
{
    char cHex[ 9 ];
    int32_t lIndex;

    for( lIndex = 0; lIndex < 8; lIndex++ )
    {
        cHex[ lIndex ] = prvNibbleToHex( ( uint8_t ) ( ulValue >> ( 28 - ( lIndex * 4 ) ) ) );
    }
    cHex[ 8 ] = '\0';

    vStartupTracePutString( cHex );
}

/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
void vSerialPutString(const signed char * pcString, unsigned short usStringLength )
{
const TickType_t xMaxBlockTime = pdMS_TO_TICKS( 5000 );

    /* Only one port is supported. */

#if ( PHASE8B_DEBUG_POLLING_UART == 1 ) && ( BSP_CFG_SCI_UART_TERMINAL_CHANNEL == ( 7 ) )
    {
        const uint8_t * pucMessage = ( const uint8_t * ) pcString;
        uint32_t ulRemaining = ( uint32_t ) usStringLength;
        uint32_t ulRetry;

        ( void ) xMaxBlockTime;

        if( ( NULL == pcString ) || ( 0U == usStringLength ) )
        {
            return;
        }

        if( SCI_SUCCESS != prvEnsureSerialPortOpen() )
        {
            return;
        }

        while( ulRemaining > 0U )
        {
            ulRetry = serialSTARTUP_TRACE_RETRY_LIMIT;

            while( ( 0 == U_SCI_UART_CLI_REG.SSR.BIT.TDRE ) && ( ulRetry-- > 0U ) )
            {
                R_BSP_NOP();
            }

            if( 0U == ulRetry )
            {
                return;
            }

            U_SCI_UART_CLI_REG.TDR = *pucMessage++;
            ulRemaining--;
        }

        ulRetry = serialSTARTUP_TRACE_RETRY_LIMIT;
        while( ( 0 == U_SCI_UART_CLI_REG.SSR.BIT.TEND ) && ( ulRetry-- > 0U ) )
        {
            R_BSP_NOP();
        }

        return;
    }
#endif


    /* Don't send the string unless the previous string has been sent. */
    {
        /* Ensure the calling task's notification state is not already
        pending. */
        xTaskNotifyStateClear( NULL );

        /* Store the handle of the transmitting task.  This is used to unblock
        the task when the transmission has completed. */
        xSendingTask = xTaskGetCurrentTaskHandle();
        uint32_t str_length = usStringLength;
        uint32_t transmit_length = 0;
        sci_err_t sci_err = SCI_SUCCESS;
        uint32_t retry = 0xFFFF;

        while ((retry > 0) && (str_length > 0))
        {

            R_SCI_Control(xSerialSciHandle, SCI_CMD_TX_Q_BYTES_FREE, &transmit_length);

            if(transmit_length > str_length)
            {
                transmit_length = str_length;
            }

            sci_err = R_SCI_Send(xSerialSciHandle, (uint8_t *) pcString,
                                 transmit_length);

            if ((sci_err == SCI_ERR_XCVR_BUSY) || (sci_err == SCI_ERR_INSUFFICIENT_SPACE))
            {
                retry--; // retry if previous transmission still in progress or tx buffer is insufficient.
                continue;
            }

            str_length -= transmit_length;
            pcString += transmit_length;

        }

        if (SCI_SUCCESS != sci_err)
        {
            R_BSP_NOP(); //TODO error handling code
        }
        /* A breakpoint can be set here for debugging. */
        R_BSP_NOP();
    }
}

/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
signed portBASE_TYPE xSerialGetChar( xComPortHandle pxPort, signed char *pcRxedChar, TickType_t xBlockTime )
{
    /* Only one UART is supported. */
    ( void ) pxPort;

    /* Return a received character, if any are available.  Otherwise block to
    wait for a character. */
    return xQueueReceive( xRxQueue, pcRxedChar, xBlockTime );
}

/* Function required in order to link UARTCommandConsole.c - which is used by
multiple different demo application. */
signed portBASE_TYPE xSerialPutChar( xComPortHandle pxPort, signed char cOutChar, TickType_t xBlockTime )
{
    /* Just mapped to vSerialPutString() so the block time is not used. */
    ( void ) xBlockTime;
    ( void ) pxPort;

    vSerialPutString( &cOutChar, sizeof( cOutChar ) );
    return pdPASS;
}

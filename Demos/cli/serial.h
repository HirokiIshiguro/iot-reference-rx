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

#ifndef SERIAL_COMMS_H
#define SERIAL_COMMS_H

typedef void * xComPortHandle;

typedef enum
{
    serCOM1,
    serCOM2,
    serCOM3,
    serCOM4,
    serCOM5,
    serCOM6,
    serCOM7,
    serCOM8
} eCOMPort;

typedef enum
{
    serNO_PARITY,
    serODD_PARITY,
    serEVEN_PARITY,
    serMARK_PARITY,
    serSPACE_PARITY
} eParity;

typedef enum
{
    serSTOP_1,
    serSTOP_2
} eStopBits;

typedef enum
{
    serBITS_5,
    serBITS_6,
    serBITS_7,
    serBITS_8
} eDataBits;

typedef enum
{
    ser50,
    ser75,
    ser110,
    ser134,
    ser150,
    ser200,
    ser300,
    ser600,
    ser1200,
    ser1800,
    ser2400,
    ser4800,
    ser9600,
    ser19200,
    ser38400,
    ser57600,
    ser115200
} eBaud;

/**********************************************************************************************************************
 * Function Name: xSerialPortInitMinimal
 * Description  : .
 * Arguments    : ulWantedBaud
 *              : uxQueueLength
 * Return Value : .
 *********************************************************************************************************************/
xComPortHandle xSerialPortInitMinimal ( unsigned long ulWantedBaud,
                                       unsigned portBASE_TYPE uxQueueLength );

/**********************************************************************************************************************
 * Function Name: xSerialPortInit
 * Description  : .
 * Arguments    : ePort
 *              : eWantedBaud
 *              : eWantedParity
 *              : eWantedDataBits
 *              : eWantedStopBits
 *              : uxBufferLength
 * Return Value : .
 *********************************************************************************************************************/
xComPortHandle xSerialPortInit ( eCOMPort ePort,
                                eBaud eWantedBaud,
                                eParity eWantedParity,
                                eDataBits eWantedDataBits,
                                eStopBits eWantedStopBits,
                                unsigned portBASE_TYPE uxBufferLength );

/**********************************************************************************************************************
 * Function Name: vSerialPutString
 * Description  : .
 * Arguments    : pcString
 *              : usStringLength
 * Return Value : .
 *********************************************************************************************************************/
void vSerialPutString ( const signed char * pcString,
                       unsigned short usStringLength );

/**********************************************************************************************************************
 * Function Name: xSerialGetChar
 * Description  : .
 * Arguments    : pxPort
 *              : pcRxedChar
 *              : xBlockTime
 * Return Value : .
 *********************************************************************************************************************/
signed portBASE_TYPE xSerialGetChar ( xComPortHandle pxPort,
                                     signed char * pcRxedChar,
                                     TickType_t xBlockTime );

/**********************************************************************************************************************
 * Function Name: xSerialPutChar
 * Description  : .
 * Arguments    : pxPort
 *              : cOutChar
 *              : xBlockTime
 * Return Value : .
 *********************************************************************************************************************/
signed portBASE_TYPE xSerialPutChar ( xComPortHandle pxPort,
                                     signed char cOutChar,
                                     TickType_t xBlockTime );

/**********************************************************************************************************************
 * Function Name: xSerialWaitForSemaphore
 * Description  : .
 * Argument     : xPort
 * Return Value : .
 *********************************************************************************************************************/
portBASE_TYPE xSerialWaitForSemaphore ( xComPortHandle xPort );

/**********************************************************************************************************************
 * Function Name: vSerialClose
 * Description  : .
 * Argument     : xPort
 * Return Value : .
 *********************************************************************************************************************/
void vSerialClose ( xComPortHandle xPort );

/**********************************************************************************************************************
 * Function Name: vOutputString
 * Description  : .
 * Argument     : pcMessage
 * Return Value : .
 *********************************************************************************************************************/
void vOutputString ( const char * pcMessage );

#endif /* ifndef SERIAL_COMMS_H */

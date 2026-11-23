/* SPDX-License-Identifier: MIT
 * Product implementation of Unity's public output hooks for the RX print task.
 * Unity drives one test task at a time; these hooks do not synchronize writers.
 */
#include <stddef.h>
#include "FreeRTOS.h"
#include "task.h"
#include "iot_logging_task.h"
#include "rx_idt_unity_output.h"

static char resultLine[ 1024 ];
static size_t lineLength;

static void prvPrintResult( const char * text )
{
    configPRINT_STRING( text );
    /* Keep the existing RX test port's print-task drain interval. */
    vTaskDelay( pdMS_TO_TICKS( 100U ) );
}

void RxIdt_UnityOutputFlush( void )
{
    if( lineLength != 0U )
    {
        resultLine[ lineLength ] = '\0';
        prvPrintResult( resultLine );
        lineLength = 0U;
    }
}

void RxIdt_UnityOutputChar( int character )
{
    /* Flush a full chunk before appending, retaining the incoming character. */
    if( lineLength == sizeof( resultLine ) - 1U )
    {
        RxIdt_UnityOutputFlush();
    }
    resultLine[ lineLength++ ] = ( char ) character;
    if( character == '\n' )
    {
        RxIdt_UnityOutputFlush();
    }
}

void RxIdt_UnityOutputStart( void )
{
    lineLength = 0U;
    prvPrintResult( "---------STARTING TESTS---------\n" );
}

void RxIdt_UnityOutputComplete( void )
{
    RxIdt_UnityOutputFlush();
    prvPrintResult( "-------ALL TESTS FINISHED-------\n" );
}

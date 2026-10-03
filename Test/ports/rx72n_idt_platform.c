/* SPDX-License-Identifier: MIT
 * FreeRTOS platform functions shared by the transport and PKCS11 IDT tests.
 */
#include <stdint.h>
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "rx_idt_config.h"
#include "platform_function.h"

#define IDT_TASK_STACK_WORDS       ( 8192U )

typedef struct IdtThread
{
    TaskHandle_t task;
    SemaphoreHandle_t completed;
    FRTestThreadFunction_t function;
    void * argument;
} IdtThread_t;

extern void get_random_number( uint8_t * data, uint32_t len );

static void prvThread( void * argument )
{
    IdtThread_t * thread = argument;
    thread->function( thread->argument );
    xSemaphoreGive( thread->completed );
    /* Do not dereference the descriptor after signalling the owning joiner. */
    vTaskSuspend( NULL );
}

FRTestThreadHandle_t FRTest_ThreadCreate( FRTestThreadFunction_t function,
                                        void * argument )
{
    IdtThread_t * thread;
    if( function == NULL )
    {
        return NULL;
    }
    thread = pvPortMalloc( sizeof( *thread ) );
    if( thread == NULL )
    {
        return NULL;
    }
    memset( thread, 0, sizeof( *thread ) );
    thread->completed = xSemaphoreCreateBinary();
    thread->function = function;
    thread->argument = argument;
    if( ( thread->completed == NULL ) ||
        ( xTaskCreate( prvThread, "IDT worker", IDT_TASK_STACK_WORDS, thread,
                       uxTaskPriorityGet( NULL ), &thread->task ) != pdPASS ) )
    {
        if( thread->completed != NULL )
        {
            vSemaphoreDelete( thread->completed );
        }
        vPortFree( thread );
        return NULL;
    }
    return thread;
}

int FRTest_ThreadTimedJoin( FRTestThreadHandle_t handle, uint32_t timeoutMs )
{
    IdtThread_t * thread = handle;
    BaseType_t completed;
    if( thread == NULL )
    {
        return -1;
    }
    completed = xSemaphoreTake( thread->completed, pdMS_TO_TICKS( timeoutMs ) );
    if( completed != pdTRUE )
    {
        /* The worker may own TLS/PKCS11 locks. Keep the caller and all worker
         * storage alive, and never enter test teardown before the host reset. */
        configPRINT_STRING( "IDT_PORT_FATAL: thread join timeout\r\n" );
        for( ;; )
        {
            vTaskSuspend( NULL );
        }
    }
    vTaskDelete( thread->task );
    vSemaphoreDelete( thread->completed );
    vPortFree( thread );
    return 0;
}

void FRTest_TimeDelay( uint32_t delayMs )
{
    vTaskDelay( pdMS_TO_TICKS( delayMs ) );
}

uint32_t FRTest_GetTimeMs( void )
{
    return ( uint32_t ) ( ( ( uint64_t ) xTaskGetTickCount() * 1000U ) /
                         ( uint64_t ) configTICK_RATE_HZ );
}

void * FRTest_MemoryAlloc( size_t size )
{
    return pvPortMalloc( size );
}

void FRTest_MemoryFree( void * pointer )
{
    vPortFree( pointer );
}

int FRTest_GenerateRandInt( void )
{
    uint32_t random = 0U;
    get_random_number( ( uint8_t * ) &random, sizeof( random ) );
    return ( int ) ( random & 0x7fffffffU );
}

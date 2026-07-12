/*
 * PSA mutex definitions for the TSIP-flavored Mbed TLS tree.
 *
 * Newer Mbed TLS provides these globals in library/threading.c. The
 * TSIP Mbed TLS tree staged under iot-reference-rx Middleware does not, so
 * define them in the application project and let the existing threading_alt
 * hooks initialize them from corePKCS11.
 */
#if defined(TSIP_RUNTIME_PROVISIONING_ENABLE)

#include <stdint.h>

#include "FreeRTOS.h"
#include "task.h"
#include "mbedtls/threading.h"
#include "platform.h"

#define TSIP_WAIT_LOOP_DELAY_INTERVAL    (256UL)
#define TSIP_MT_TRACKED_TASKS_MAX        (4UL)

static volatile uint32_t ulTsipWaitLoopCalls = 0UL;
static volatile uint32_t ulTsipWaitLoopDelays = 0UL;
static volatile uint32_t ulTsipMtLockCalls = 0UL;
static volatile uint32_t ulTsipMtUnlockCalls = 0UL;
static volatile uint32_t ulTsipMtOwnerErrors = 0UL;
static uint32_t ulTsipMtTaskCount = 0UL;
static TaskHandle_t xTsipMtTasks[TSIP_MT_TRACKED_TASKS_MAX];

/*
 * The TLS 1.3 0-RTT smoke build stages stock Mbed TLS 3.6.x into the TSIP
 * path. That tree already owns the PSA mutex globals in library/threading.c.
 */
#if defined(MBEDTLS_THREADING_C) && defined(MBEDTLS_PSA_CRYPTO_C) && \
    !defined(LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE) && \
    !defined(LANBENCH_TLS13_0RTT_TSIP_ENABLE)
mbedtls_threading_mutex_t mbedtls_threading_key_slot_mutex;
mbedtls_threading_mutex_t mbedtls_threading_psa_globaldata_mutex;
mbedtls_threading_mutex_t mbedtls_threading_psa_rngdata_mutex;
#endif

#if defined(MBEDTLS_THREADING_C)
mbedtls_threading_mutex_t mutexUseTsip;
/*
 * The TSIP-enabled Mbed TLS tree keeps certificate parsing and handshake
 * scratch state in process-wide globals.  Serialize TLS setup/handshake while
 * leaving established record traffic free to use mutexUseTsip independently.
 */
mbedtls_threading_mutex_t mutexTsipTlsHandshake;
#endif

#if defined(MBEDTLS_THREADING_C)
extern void mbedtls_platform_mutex_init( mbedtls_threading_mutex_t * pMutex );

static void prvTsipMultithreadingRecordTask( void )
{
    TaskHandle_t xCurrentTask;
    uint32_t ulIndex;

    if( taskSCHEDULER_NOT_STARTED == xTaskGetSchedulerState() )
    {
        return;
    }

    xCurrentTask = xTaskGetCurrentTaskHandle();
    for( ulIndex = 0UL; ulIndex < ulTsipMtTaskCount; ulIndex++ )
    {
        if( xTsipMtTasks[ulIndex] == xCurrentTask )
        {
            return;
        }
    }

    if( ulTsipMtTaskCount < TSIP_MT_TRACKED_TASKS_MAX )
    {
        xTsipMtTasks[ulTsipMtTaskCount] = xCurrentTask;
        ulTsipMtTaskCount++;
    }
}

void vTsipMbedtlsThreadingCompatInit( void )
{
    static int initialized = 0;

    if( 0 == initialized )
    {
    #if defined(MBEDTLS_PSA_CRYPTO_C) && \
        !defined(LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE) && \
        !defined(LANBENCH_TLS13_0RTT_TSIP_ENABLE)
        mbedtls_platform_mutex_init( &mbedtls_threading_key_slot_mutex );
        mbedtls_platform_mutex_init( &mbedtls_threading_psa_globaldata_mutex );
        mbedtls_platform_mutex_init( &mbedtls_threading_psa_rngdata_mutex );
    #endif
        mbedtls_platform_mutex_init( &mutexUseTsip );
        mbedtls_platform_mutex_init( &mutexTsipTlsHandshake );
        initialized = 1;
    }
}

/* The official FIT driver invokes these callbacks around each generated
 * private TSIP operation when TSIP_MULTI_THREADING is enabled. Reuse the
 * recursive mutex already held across public Init/Update/Final sequences so
 * both protection layers share one ownership domain. */
void user_lock_function( void )
{
    ( void ) mbedtls_platform_mutex_lock( &mutexUseTsip );
    ulTsipMtLockCalls++;
    prvTsipMultithreadingRecordTask();
}

void user_unlock_function( void )
{
    if( taskSCHEDULER_NOT_STARTED != xTaskGetSchedulerState() )
    {
        TaskHandle_t xCurrentTask = xTaskGetCurrentTaskHandle();
        TaskHandle_t xHolder = xSemaphoreGetMutexHolder( mutexUseTsip.mutexHandle );

        if( xHolder != xCurrentTask )
        {
            ulTsipMtOwnerErrors++;
        }
    }

    ulTsipMtUnlockCalls++;
    ( void ) mbedtls_platform_mutex_unlock( &mutexUseTsip );
}

void vTsipMultithreadingStatsReset( void )
{
    uint32_t ulIndex;

    ( void ) mbedtls_platform_mutex_lock( &mutexUseTsip );
    ulTsipMtLockCalls = 0UL;
    ulTsipMtUnlockCalls = 0UL;
    ulTsipMtOwnerErrors = 0UL;
    ulTsipMtTaskCount = 0UL;
    for( ulIndex = 0UL; ulIndex < TSIP_MT_TRACKED_TASKS_MAX; ulIndex++ )
    {
        xTsipMtTasks[ulIndex] = NULL;
    }
    ( void ) mbedtls_platform_mutex_unlock( &mutexUseTsip );
}

void vTsipMultithreadingGetStats( uint32_t * pulLockCalls,
                                  uint32_t * pulUnlockCalls,
                                  uint32_t * pulTaskCount,
                                  uint32_t * pulOwnerErrors )
{
    ( void ) mbedtls_platform_mutex_lock( &mutexUseTsip );

    if( NULL != pulLockCalls )
    {
        *pulLockCalls = ulTsipMtLockCalls;
    }

    if( NULL != pulUnlockCalls )
    {
        *pulUnlockCalls = ulTsipMtUnlockCalls;
    }

    if( NULL != pulTaskCount )
    {
        *pulTaskCount = ulTsipMtTaskCount;
    }

    if( NULL != pulOwnerErrors )
    {
        *pulOwnerErrors = ulTsipMtOwnerErrors;
    }

    ( void ) mbedtls_platform_mutex_unlock( &mutexUseTsip );
}
#endif

/*
 * Hybrid wait used by the RX72N FreeRTOS integration. Short TSIP operations
 * remain pure polling; a long REG_00H.B25 wait yields for one tick after every
 * 256 polls. Never call the scheduler from startup, an ISR, a critical
 * section, or the TSIP self-check path where global interrupts are disabled.
 */
void vTsipWaitLoopHook( void )
{
    uint32_t ulCalls = ++ulTsipWaitLoopCalls;

    if( ( 0UL == ( ulCalls & ( TSIP_WAIT_LOOP_DELAY_INTERVAL - 1UL ) ) ) &&
        ( taskSCHEDULER_RUNNING == xTaskGetSchedulerState() ) &&
        ( 0UL != ( R_BSP_GET_PSW() & 0x00010000UL ) ) &&
        ( 0UL == R_BSP_CpuInterruptLevelRead() ) )
    {
        ++ulTsipWaitLoopDelays;
        vTaskDelay( 1U );
    }
}

void vTsipWaitLoopGetStats( uint32_t * pulCalls,
                            uint32_t * pulDelays )
{
    if( NULL != pulCalls )
    {
        *pulCalls = ulTsipWaitLoopCalls;
    }

    if( NULL != pulDelays )
    {
        *pulDelays = ulTsipWaitLoopDelays;
    }
}

#endif /* TSIP_RUNTIME_PROVISIONING_ENABLE */

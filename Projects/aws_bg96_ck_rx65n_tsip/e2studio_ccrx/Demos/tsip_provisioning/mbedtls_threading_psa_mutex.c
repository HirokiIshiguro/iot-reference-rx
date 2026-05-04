/*
 * PSA mutex definitions for the TSIP-flavored Mbed TLS tree.
 *
 * Newer Mbed TLS provides these globals in library/threading.c. The
 * TSIP Mbed TLS tree staged under iot-reference-rx Middleware does not, so
 * define them in the application project and let the existing threading_alt
 * hooks initialize them from corePKCS11.
 */
#if defined(TSIP_RUNTIME_PROVISIONING_ENABLE)

#include "mbedtls/threading.h"

#if defined(MBEDTLS_THREADING_C) && defined(MBEDTLS_PSA_CRYPTO_C)
mbedtls_threading_mutex_t mbedtls_threading_key_slot_mutex;
mbedtls_threading_mutex_t mbedtls_threading_psa_globaldata_mutex;
mbedtls_threading_mutex_t mbedtls_threading_psa_rngdata_mutex;
#endif

#if defined(MBEDTLS_THREADING_C)
mbedtls_threading_mutex_t mutexUseTsip;
#endif

#if defined(MBEDTLS_THREADING_C)
extern void mbedtls_platform_mutex_init( mbedtls_threading_mutex_t * pMutex );

void vTsipMbedtlsThreadingCompatInit( void )
{
    static int initialized = 0;

    if( 0 == initialized )
    {
    #if defined(MBEDTLS_PSA_CRYPTO_C)
        mbedtls_platform_mutex_init( &mbedtls_threading_key_slot_mutex );
        mbedtls_platform_mutex_init( &mbedtls_threading_psa_globaldata_mutex );
        mbedtls_platform_mutex_init( &mbedtls_threading_psa_rngdata_mutex );
    #endif
        mbedtls_platform_mutex_init( &mutexUseTsip );
        initialized = 1;
    }
}
#endif

#endif /* TSIP_RUNTIME_PROVISIONING_ENABLE */

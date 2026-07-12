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
#endif

#endif /* TSIP_RUNTIME_PROVISIONING_ENABLE */

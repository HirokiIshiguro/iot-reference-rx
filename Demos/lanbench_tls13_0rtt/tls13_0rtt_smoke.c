/*
 * TLS 1.3 resumption and 0-RTT smoke task for Mbed TLS 3.6.x. The software
 * build proves upstream early-data behavior; the TSIP build keeps the same
 * flow and routes client CertificateVerify through the TSIP key index.
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifndef LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE
#define LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE    ( 0U )
#endif

#ifndef LANBENCH_TLS13_0RTT_TSIP_ENABLE
#define LANBENCH_TLS13_0RTT_TSIP_ENABLE        ( 0U )
#endif

#ifndef LANBENCH_TLS13_0RTT_ENABLE
#define LANBENCH_TLS13_0RTT_ENABLE             ( ( LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE != 0U ) || \
                                                  ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U ) )
#endif

#if ( LANBENCH_TLS13_0RTT_ENABLE != 0U )

#include "FreeRTOS.h"
#include "task.h"

#ifndef FreeRTOS_printf
    #define FreeRTOS_printf( X )    configPRINTF( X )
#endif

#include "tcp_sockets_wrapper.h"
#include "mbedtls_bio_tcp_sockets_wrapper.h"

#include "mbedtls/build_info.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"
#include "mbedtls/error.h"
#include "mbedtls/pk.h"
#include "mbedtls/platform_time.h"
#include "mbedtls/ssl.h"
#include "mbedtls/x509_crt.h"

#if defined( MBEDTLS_DEBUG_C )
    #include "mbedtls/debug.h"
#endif

#if defined( MBEDTLS_PSA_CRYPTO_C )
    #include "psa/crypto.h"
#endif

#include "tls13_0rtt_smoke.h"
#include "lanbench_tls13_0rtt_config.h"

#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
    #include "aws_clientcredential_keys.h"
    #include "tsip_provisioning_store.h"

    extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateAttempts;
    extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateCalls;
    extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateFailures;
    extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus;
    extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastScheme;
    extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastBytes;
#endif

#ifndef LANBENCH_TLS13_0RTT_HOST
#define LANBENCH_TLS13_0RTT_HOST              "192.168.10.103"
#endif

#ifndef LANBENCH_TLS13_0RTT_SERVER_NAME
#define LANBENCH_TLS13_0RTT_SERVER_NAME       "localhost"
#endif

#ifndef LANBENCH_TLS_PORT
#define LANBENCH_TLS_PORT                     ( 5443U )
#endif

#define TLS13_0RTT_TASK_STACK_WORDS           ( 8192U )
#define TLS13_0RTT_TASK_PRIORITY              ( tskIDLE_PRIORITY + 1 )
#define TLS13_0RTT_START_DELAY_MS             ( 40000U )
#define TLS13_0RTT_SOCKET_TIMEOUT_MS          ( 30000U )
#define TLS13_0RTT_READ_BUFFER_SIZE           ( 512U )
#define TLS13_0RTT_EARLY_REQUEST_TARGET_SIZE  ( 96U )

typedef struct Tls13ZeroRttContext
{
    Socket_t xSocket;
    mbedtls_ssl_context xSsl;
    mbedtls_ssl_config xConfig;
    mbedtls_ctr_drbg_context xCtrDrbg;
    mbedtls_entropy_context xEntropy;
#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
    mbedtls_x509_crt xClientCert;
    mbedtls_pk_context xClientKey;
#endif
} Tls13ZeroRttContext_t;

static void prvTls13ZeroRttTask( void * pvParameters );
static BaseType_t prvRunTls13ZeroRttSmoke( void );
static void prvContextInit( Tls13ZeroRttContext_t * pxContext );
static void prvContextFree( Tls13ZeroRttContext_t * pxContext );
static BaseType_t prvConfigureContext( Tls13ZeroRttContext_t * pxContext );
#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
static BaseType_t prvConfigureTsipClientCertificate( Tls13ZeroRttContext_t * pxContext );
static void prvPrintTsipCertificateVerifyStats( void );
#endif
static BaseType_t prvConnectSocket( Tls13ZeroRttContext_t * pxContext );
static BaseType_t prvSetupSslOnSocket( Tls13ZeroRttContext_t * pxContext );
static BaseType_t prvHandshake( Tls13ZeroRttContext_t * pxContext );
static BaseType_t prvSendRequest( Tls13ZeroRttContext_t * pxContext );
static BaseType_t prvReadUntilTicket( Tls13ZeroRttContext_t * pxContext,
                                      mbedtls_ssl_session * pxSession );
static BaseType_t prvReconnectWithEarlyData( const mbedtls_ssl_session * pxSession );
static BaseType_t prvWriteEarlyRequest( Tls13ZeroRttContext_t * pxContext,
                                        size_t * pxBytesWritten );
static void prvBuildEarlyRequest( unsigned char * pucBuffer,
                                  size_t xBufferSize,
                                  size_t * pxRequestSize );
#if defined( MBEDTLS_DEBUG_C )
static void prvMbedtlsDebug( void * pvContext,
                             int lLevel,
                             const char * pcFile,
                             int lLine,
                             const char * pcMessage );
#endif
static void prvPrintMbedtlsError( const char * pcWhere,
                                  int lError );
long tls13_0rtt_mbedtls_time( long * plTime );
mbedtls_ms_time_t mbedtls_ms_time( void );

static const int lTls13OnlyCipherSuites[] =
{
    MBEDTLS_TLS1_3_AES_128_GCM_SHA256,
    0
};

static const uint16_t usTls13OnlyGroups[] =
{
    23U, /* secp256r1 / prime256v1 */
    0U
};

#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
static const uint16_t usTls13TsipSignatureAlgorithms[] =
{
    MBEDTLS_TLS1_3_SIG_ECDSA_SECP256R1_SHA256,
    MBEDTLS_TLS1_3_SIG_RSA_PSS_RSAE_SHA256,
    MBEDTLS_TLS1_3_SIG_NONE
};
#endif

long tls13_0rtt_mbedtls_time( long * plTime )
{
    long lSeconds;

    lSeconds = ( long ) ( xTaskGetTickCount() / configTICK_RATE_HZ );

    if( NULL != plTime )
    {
        *plTime = lSeconds;
    }

    return lSeconds;
}

mbedtls_ms_time_t mbedtls_ms_time( void )
{
    return ( ( mbedtls_ms_time_t ) xTaskGetTickCount() * 1000 ) / configTICK_RATE_HZ;
}

void vStartTls13ZeroRttSmoke( void )
{
    ( void ) xTaskCreate( prvTls13ZeroRttTask,
                          "TLS13_0RTT",
                          TLS13_0RTT_TASK_STACK_WORDS,
                          NULL,
                          TLS13_0RTT_TASK_PRIORITY,
                          NULL );
}

static void prvTls13ZeroRttTask( void * pvParameters )
{
    BaseType_t xResult;

    ( void ) pvParameters;

    vTaskDelay( pdMS_TO_TICKS( TLS13_0RTT_START_DELAY_MS ) );

    FreeRTOS_printf( ( "[LANBENCH] TLS13 0RTT %s smoke start host=%s tls=%u\r\n",
#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
                       "TSIP",
#else
                       "software",
#endif
                       LANBENCH_TLS13_0RTT_HOST,
                       ( unsigned int ) LANBENCH_TLS_PORT ) );

    xResult = prvRunTls13ZeroRttSmoke();

    if( pdTRUE == xResult )
    {
        FreeRTOS_printf( ( "[LANBENCH] PASS\r\n" ) );
    }
    else
    {
        FreeRTOS_printf( ( "[LANBENCH] FAIL tls13_0rtt=0\r\n" ) );
    }

    vTaskDelete( NULL );
}

static BaseType_t prvRunTls13ZeroRttSmoke( void )
{
    Tls13ZeroRttContext_t * pxContext;
    mbedtls_ssl_session xSavedSession;
    BaseType_t xResult = pdFALSE;
    BaseType_t xTicketSaved = pdFALSE;

    pxContext = ( Tls13ZeroRttContext_t * ) pvPortMalloc( sizeof( *pxContext ) );
    if( NULL == pxContext )
    {
        FreeRTOS_printf( ( "[LANBENCH] TLS13 0RTT context alloc failed\r\n" ) );
        return pdFALSE;
    }

    mbedtls_ssl_session_init( &xSavedSession );
    prvContextInit( pxContext );

    if( ( pdTRUE == prvConfigureContext( pxContext ) ) &&
        ( pdTRUE == prvConnectSocket( pxContext ) ) &&
        ( pdTRUE == prvSetupSslOnSocket( pxContext ) ) &&
        ( pdTRUE == prvHandshake( pxContext ) ) )
    {
        FreeRTOS_printf( ( "[LANBENCH] TLS13 initial connected version=%s cipher=%s\r\n",
                           mbedtls_ssl_get_version( &pxContext->xSsl ),
                           mbedtls_ssl_get_ciphersuite( &pxContext->xSsl ) ) );

        if( ( pdTRUE == prvSendRequest( pxContext ) ) &&
            ( pdTRUE == prvReadUntilTicket( pxContext, &xSavedSession ) ) )
        {
            FreeRTOS_printf( ( "[LANBENCH] TLS13 session ticket saved\r\n" ) );
            xTicketSaved = pdTRUE;
        }
    }

    ( void ) mbedtls_ssl_close_notify( &pxContext->xSsl );
    prvContextFree( pxContext );
    vPortFree( pxContext );

    if( pdTRUE == xTicketSaved )
    {
        xResult = prvReconnectWithEarlyData( &xSavedSession );
    }

    mbedtls_ssl_session_free( &xSavedSession );

    return xResult;
}

static void prvContextInit( Tls13ZeroRttContext_t * pxContext )
{
    memset( pxContext, 0, sizeof( *pxContext ) );
    pxContext->xSocket = SOCKETS_INVALID_SOCKET;
    mbedtls_ssl_init( &pxContext->xSsl );
    mbedtls_ssl_config_init( &pxContext->xConfig );
    mbedtls_ctr_drbg_init( &pxContext->xCtrDrbg );
    mbedtls_entropy_init( &pxContext->xEntropy );
#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
    mbedtls_x509_crt_init( &pxContext->xClientCert );
    mbedtls_pk_init( &pxContext->xClientKey );
#endif
}

static void prvContextFree( Tls13ZeroRttContext_t * pxContext )
{
    if( SOCKETS_INVALID_SOCKET != pxContext->xSocket )
    {
        TCP_Sockets_Disconnect( pxContext->xSocket );
        pxContext->xSocket = SOCKETS_INVALID_SOCKET;
    }

    mbedtls_ssl_free( &pxContext->xSsl );
    mbedtls_ssl_config_free( &pxContext->xConfig );
    mbedtls_ctr_drbg_free( &pxContext->xCtrDrbg );
    mbedtls_entropy_free( &pxContext->xEntropy );
#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
    mbedtls_x509_crt_free( &pxContext->xClientCert );
    mbedtls_pk_free( &pxContext->xClientKey );
#endif
}

static BaseType_t prvConfigureContext( Tls13ZeroRttContext_t * pxContext )
{
    static const unsigned char ucPersonalization[] = "iotref-tls13-0rtt";
    int lMbedtlsError;

#if defined( MBEDTLS_PSA_CRYPTO_C )
    psa_status_t xPsaStatus;

    xPsaStatus = psa_crypto_init();
    if( PSA_SUCCESS != xPsaStatus )
    {
        FreeRTOS_printf( ( "[LANBENCH] PSA init failed status=%ld\r\n", ( long ) xPsaStatus ) );
        return pdFALSE;
    }
#endif

    lMbedtlsError = mbedtls_ctr_drbg_seed( &pxContext->xCtrDrbg,
                                           mbedtls_entropy_func,
                                           &pxContext->xEntropy,
                                           ucPersonalization,
                                           sizeof( ucPersonalization ) - 1U );
    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "ctr_drbg_seed", lMbedtlsError );
        return pdFALSE;
    }

    lMbedtlsError = mbedtls_ssl_config_defaults( &pxContext->xConfig,
                                                 MBEDTLS_SSL_IS_CLIENT,
                                                 MBEDTLS_SSL_TRANSPORT_STREAM,
                                                 MBEDTLS_SSL_PRESET_DEFAULT );
    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "ssl_config_defaults", lMbedtlsError );
        return pdFALSE;
    }

    mbedtls_ssl_conf_authmode( &pxContext->xConfig, MBEDTLS_SSL_VERIFY_NONE );
    mbedtls_ssl_conf_rng( &pxContext->xConfig,
                          mbedtls_ctr_drbg_random,
                          &pxContext->xCtrDrbg );
    mbedtls_ssl_conf_ciphersuites( &pxContext->xConfig, lTls13OnlyCipherSuites );
    mbedtls_ssl_conf_groups( &pxContext->xConfig, usTls13OnlyGroups );
#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
    mbedtls_ssl_conf_sig_algs( &pxContext->xConfig, usTls13TsipSignatureAlgorithms );
#endif

#if defined( MBEDTLS_DEBUG_C )
    mbedtls_ssl_conf_dbg( &pxContext->xConfig, prvMbedtlsDebug, NULL );
    mbedtls_debug_set_threshold( 2 );
#endif

#if defined( MBEDTLS_SSL_PROTO_TLS1_3 )
    mbedtls_ssl_conf_min_tls_version( &pxContext->xConfig, MBEDTLS_SSL_VERSION_TLS1_3 );
    mbedtls_ssl_conf_max_tls_version( &pxContext->xConfig, MBEDTLS_SSL_VERSION_TLS1_3 );
#endif

#if defined( MBEDTLS_SSL_SESSION_TICKETS )
    mbedtls_ssl_conf_session_tickets( &pxContext->xConfig, MBEDTLS_SSL_SESSION_TICKETS_ENABLED );
#endif

#if defined( MBEDTLS_SSL_PROTO_TLS1_3 ) && defined( MBEDTLS_SSL_SESSION_TICKETS )
    mbedtls_ssl_conf_tls13_enable_signal_new_session_tickets(
        &pxContext->xConfig,
        MBEDTLS_SSL_TLS1_3_SIGNAL_NEW_SESSION_TICKETS_ENABLED );
#endif

#if defined( MBEDTLS_SSL_EARLY_DATA )
    mbedtls_ssl_conf_early_data( &pxContext->xConfig, MBEDTLS_SSL_EARLY_DATA_ENABLED );
#else
    FreeRTOS_printf( ( "[LANBENCH] MBEDTLS_SSL_EARLY_DATA is not enabled\r\n" ) );
    return pdFALSE;
#endif

#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
    if( pdTRUE != xTsipProvisioningLoadClientRsa2048KeyPair() )
    {
        FreeRTOS_printf( ( "[LANBENCH] TSIP client RSA key index load failed\r\n" ) );
        return pdFALSE;
    }

    if( pdTRUE != prvConfigureTsipClientCertificate( pxContext ) )
    {
        return pdFALSE;
    }
#endif

    return pdTRUE;
}

#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
static void prvPrintTsipCertificateVerifyStats( void )
{
    FreeRTOS_printf( ( "[LANBENCH] TSIP CertificateVerify attempts=%lu calls=%lu failures=%lu status=0x%08lx scheme=0x%08lx bytes=%lu\r\n",
                       ( unsigned long ) gTsipTlsProbeTls13CertificateVerifyGenerateAttempts,
                       ( unsigned long ) gTsipTlsProbeTls13CertificateVerifyGenerateCalls,
                       ( unsigned long ) gTsipTlsProbeTls13CertificateVerifyGenerateFailures,
                       ( unsigned long ) gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus,
                       ( unsigned long ) gTsipTlsProbeTls13CertificateVerifyGenerateLastScheme,
                       ( unsigned long ) gTsipTlsProbeTls13CertificateVerifyGenerateLastBytes ) );
}

static BaseType_t prvConfigureTsipClientCertificate( Tls13ZeroRttContext_t * pxContext )
{
    int lMbedtlsError;
    const char * pcClientCertificate = keyCLIENT_CERTIFICATE_PEM;

    if( NULL == pcClientCertificate )
    {
        FreeRTOS_printf( ( "[LANBENCH] TSIP 0RTT client certificate is not configured\r\n" ) );
        return pdFALSE;
    }

    lMbedtlsError = mbedtls_x509_crt_parse( &pxContext->xClientCert,
                                            ( const unsigned char * ) pcClientCertificate,
                                            strlen( pcClientCertificate ) + 1U );
    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "x509_crt_parse_client", lMbedtlsError );
        return pdFALSE;
    }

    lMbedtlsError = mbedtls_pk_setup( &pxContext->xClientKey,
                                      mbedtls_pk_info_from_type( MBEDTLS_PK_RSA ) );
    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "pk_setup_tsip_client", lMbedtlsError );
        return pdFALSE;
    }

    lMbedtlsError = mbedtls_ssl_conf_own_cert( &pxContext->xConfig,
                                               &pxContext->xClientCert,
                                               &pxContext->xClientKey );
    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "ssl_conf_own_cert_tsip", lMbedtlsError );
        return pdFALSE;
    }

    FreeRTOS_printf( ( "[LANBENCH] TSIP client certificate configured for TLS13 0RTT smoke\r\n" ) );
    return pdTRUE;
}
#endif

static BaseType_t prvConnectSocket( Tls13ZeroRttContext_t * pxContext )
{
    BaseType_t xSocketStatus;

    xSocketStatus = TCP_Sockets_Connect( &pxContext->xSocket,
                                         LANBENCH_TLS13_0RTT_HOST,
                                         LANBENCH_TLS_PORT,
                                         TLS13_0RTT_SOCKET_TIMEOUT_MS,
                                         TLS13_0RTT_SOCKET_TIMEOUT_MS );
    if( 0 != xSocketStatus )
    {
        FreeRTOS_printf( ( "[LANBENCH] TLS13 socket connect failed status=%ld\r\n",
                           ( long ) xSocketStatus ) );
        return pdFALSE;
    }

    return pdTRUE;
}

static BaseType_t prvSetupSslOnSocket( Tls13ZeroRttContext_t * pxContext )
{
    int lMbedtlsError;

    lMbedtlsError = mbedtls_ssl_setup( &pxContext->xSsl, &pxContext->xConfig );
    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "ssl_setup", lMbedtlsError );
        return pdFALSE;
    }

    lMbedtlsError = mbedtls_ssl_set_hostname( &pxContext->xSsl, LANBENCH_TLS13_0RTT_SERVER_NAME );
    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "ssl_set_hostname", lMbedtlsError );
        return pdFALSE;
    }

    mbedtls_ssl_set_bio( &pxContext->xSsl,
                         ( void * ) pxContext->xSocket,
                         xMbedTLSBioTCPSocketsWrapperSend,
                         xMbedTLSBioTCPSocketsWrapperRecv,
                         NULL );

    return pdTRUE;
}

static BaseType_t prvHandshake( Tls13ZeroRttContext_t * pxContext )
{
    int lMbedtlsError;

    do
    {
        lMbedtlsError = mbedtls_ssl_handshake( &pxContext->xSsl );
    } while( ( MBEDTLS_ERR_SSL_WANT_READ == lMbedtlsError ) ||
             ( MBEDTLS_ERR_SSL_WANT_WRITE == lMbedtlsError ) ||
             ( MBEDTLS_ERR_SSL_RECEIVED_NEW_SESSION_TICKET == lMbedtlsError ) );

    if( 0 != lMbedtlsError )
    {
        prvPrintMbedtlsError( "ssl_handshake", lMbedtlsError );
#if ( LANBENCH_TLS13_0RTT_TSIP_ENABLE != 0U )
        prvPrintTsipCertificateVerifyStats();
#endif
        return pdFALSE;
    }

    return pdTRUE;
}

static BaseType_t prvSendRequest( Tls13ZeroRttContext_t * pxContext )
{
    static const unsigned char ucRequest[] =
        "GET /initial HTTP/1.0\r\n"
        "Host: lanbenchd.local\r\n"
        "\r\n";
    size_t xOffset = 0U;
    int lWritten;

    while( xOffset < ( sizeof( ucRequest ) - 1U ) )
    {
        lWritten = mbedtls_ssl_write( &pxContext->xSsl,
                                      &ucRequest[ xOffset ],
                                      ( sizeof( ucRequest ) - 1U ) - xOffset );
        if( lWritten > 0 )
        {
            xOffset += ( size_t ) lWritten;
        }
        else if( ( MBEDTLS_ERR_SSL_WANT_READ != lWritten ) &&
                 ( MBEDTLS_ERR_SSL_WANT_WRITE != lWritten ) )
        {
            prvPrintMbedtlsError( "ssl_write_initial", lWritten );
            return pdFALSE;
        }
    }

    return pdTRUE;
}

static BaseType_t prvReadUntilTicket( Tls13ZeroRttContext_t * pxContext,
                                      mbedtls_ssl_session * pxSession )
{
    unsigned char ucBuffer[ TLS13_0RTT_READ_BUFFER_SIZE ];
    TickType_t xDeadline = xTaskGetTickCount() + pdMS_TO_TICKS( TLS13_0RTT_SOCKET_TIMEOUT_MS );
    BaseType_t xTicketSaved = pdFALSE;
    BaseType_t xResponseSeen = pdFALSE;
    int lRead;

    while( xTaskGetTickCount() < xDeadline )
    {
        lRead = mbedtls_ssl_read( &pxContext->xSsl, ucBuffer, sizeof( ucBuffer ) - 1U );
        if( lRead > 0 )
        {
            ucBuffer[ lRead ] = '\0';
            xResponseSeen = pdTRUE;
            FreeRTOS_printf( ( "[LANBENCH] TLS13 initial read bytes=%ld\r\n", ( long ) lRead ) );
        }
        else if( MBEDTLS_ERR_SSL_RECEIVED_NEW_SESSION_TICKET == lRead )
        {
            lRead = mbedtls_ssl_get_session( &pxContext->xSsl, pxSession );
            if( 0 != lRead )
            {
                prvPrintMbedtlsError( "ssl_get_session", lRead );
                return pdFALSE;
            }
            xTicketSaved = pdTRUE;
            FreeRTOS_printf( ( "[LANBENCH] TLS13 new session ticket received\r\n" ) );
        }
        else if( ( MBEDTLS_ERR_SSL_WANT_READ == lRead ) ||
                 ( MBEDTLS_ERR_SSL_WANT_WRITE == lRead ) )
        {
            vTaskDelay( pdMS_TO_TICKS( 10U ) );
        }
        else if( MBEDTLS_ERR_SSL_PEER_CLOSE_NOTIFY == lRead )
        {
            break;
        }
        else
        {
            prvPrintMbedtlsError( "ssl_read_initial", lRead );
            return pdFALSE;
        }

        if( ( pdTRUE == xTicketSaved ) && ( pdTRUE == xResponseSeen ) )
        {
            return pdTRUE;
        }
    }

    FreeRTOS_printf( ( "[LANBENCH] TLS13 ticket wait timeout ticket=%ld response=%ld\r\n",
                       ( long ) xTicketSaved,
                       ( long ) xResponseSeen ) );
    return pdFALSE;
}

static BaseType_t prvReconnectWithEarlyData( const mbedtls_ssl_session * pxSession )
{
    Tls13ZeroRttContext_t * pxContext;
    BaseType_t xResult = pdFALSE;
    size_t xEarlyBytes = 0U;
    int lMbedtlsError;

    pxContext = ( Tls13ZeroRttContext_t * ) pvPortMalloc( sizeof( *pxContext ) );
    if( NULL == pxContext )
    {
        FreeRTOS_printf( ( "[LANBENCH] TLS13 reconnect context alloc failed\r\n" ) );
        return pdFALSE;
    }

    prvContextInit( pxContext );

    if( ( pdTRUE == prvConfigureContext( pxContext ) ) &&
        ( pdTRUE == prvConnectSocket( pxContext ) ) &&
        ( pdTRUE == prvSetupSslOnSocket( pxContext ) ) )
    {
        lMbedtlsError = mbedtls_ssl_set_session( &pxContext->xSsl, pxSession );
        if( 0 != lMbedtlsError )
        {
            prvPrintMbedtlsError( "ssl_set_session", lMbedtlsError );
        }
        else if( pdTRUE == prvWriteEarlyRequest( pxContext, &xEarlyBytes ) )
        {
            if( pdTRUE == prvHandshake( pxContext ) )
            {
#if defined( MBEDTLS_SSL_EARLY_DATA )
                mbedtls_ssl_early_data_status xEarlyStatus;

                xEarlyStatus = mbedtls_ssl_get_early_data_status( &pxContext->xSsl );
                FreeRTOS_printf( ( "[LANBENCH] TLS13 resumed connected version=%s cipher=%s early_bytes=%lu early_status=%ld\r\n",
                                   mbedtls_ssl_get_version( &pxContext->xSsl ),
                                   mbedtls_ssl_get_ciphersuite( &pxContext->xSsl ),
                                   ( unsigned long ) xEarlyBytes,
                                   ( long ) xEarlyStatus ) );

                xResult = ( ( xEarlyBytes > 0U ) &&
                            ( MBEDTLS_SSL_EARLY_DATA_STATUS_ACCEPTED == xEarlyStatus ) ) ? pdTRUE : pdFALSE;
#endif
            }
        }
    }

    ( void ) mbedtls_ssl_close_notify( &pxContext->xSsl );
    prvContextFree( pxContext );
    vPortFree( pxContext );

    return xResult;
}

static BaseType_t prvWriteEarlyRequest( Tls13ZeroRttContext_t * pxContext,
                                        size_t * pxBytesWritten )
{
    unsigned char ucRequest[ TLS13_0RTT_EARLY_REQUEST_TARGET_SIZE ];
    size_t xRequestSize = 0U;
    size_t xOffset = 0U;
    TickType_t xDeadline = xTaskGetTickCount() + pdMS_TO_TICKS( TLS13_0RTT_SOCKET_TIMEOUT_MS );
    int lWritten;

    prvBuildEarlyRequest( ucRequest, sizeof( ucRequest ), &xRequestSize );

    while( xOffset < xRequestSize )
    {
        lWritten = mbedtls_ssl_write_early_data( &pxContext->xSsl,
                                                 &ucRequest[ xOffset ],
                                                 xRequestSize - xOffset );
        if( lWritten > 0 )
        {
            xOffset += ( size_t ) lWritten;
        }
        else if( MBEDTLS_ERR_SSL_CANNOT_WRITE_EARLY_DATA == lWritten )
        {
            FreeRTOS_printf( ( "[LANBENCH] TLS13 cannot write more early data after %lu bytes\r\n",
                               ( unsigned long ) xOffset ) );
            break;
        }
        else if( ( MBEDTLS_ERR_SSL_WANT_READ != lWritten ) &&
                 ( MBEDTLS_ERR_SSL_WANT_WRITE != lWritten ) )
        {
            prvPrintMbedtlsError( "ssl_write_early_data", lWritten );
            return pdFALSE;
        }
        else
        {
            if( xTaskGetTickCount() >= xDeadline )
            {
                FreeRTOS_printf( ( "[LANBENCH] TLS13 early data write timeout after %lu bytes\r\n",
                                   ( unsigned long ) xOffset ) );
                return pdFALSE;
            }

            vTaskDelay( pdMS_TO_TICKS( 1U ) );
        }
    }

    *pxBytesWritten = xOffset;
    FreeRTOS_printf( ( "[LANBENCH] TLS13 early data written bytes=%lu\r\n",
                       ( unsigned long ) xOffset ) );

    return ( xOffset > 0U ) ? pdTRUE : pdFALSE;
}

static void prvBuildEarlyRequest( unsigned char * pucBuffer,
                                  size_t xBufferSize,
                                  size_t * pxRequestSize )
{
    static const char cPrefix[] =
        "GET /early HTTP/1.0\r\n"
        "Host: lanbenchd.local\r\n"
        "User-Agent: rx72n-0rtt\r\n"
        "\r\n";
    size_t xLength;

    xLength = strlen( cPrefix );
    if( xLength > xBufferSize )
    {
        xLength = xBufferSize;
    }

    memcpy( pucBuffer, cPrefix, xLength );
    while( xLength < xBufferSize )
    {
        pucBuffer[ xLength ] = 'A';
        xLength++;
    }

    *pxRequestSize = xLength;
}

#if defined( MBEDTLS_DEBUG_C )
static void prvMbedtlsDebug( void * pvContext,
                             int lLevel,
                             const char * pcFile,
                             int lLine,
                             const char * pcMessage )
{
    const char * pcBaseName;

    ( void ) pvContext;
    ( void ) lLevel;

    pcBaseName = strrchr( pcFile, '/' );
    if( NULL == pcBaseName )
    {
        pcBaseName = strrchr( pcFile, '\\' );
    }

    if( NULL != pcBaseName )
    {
        pcBaseName++;
    }
    else
    {
        pcBaseName = pcFile;
    }

    FreeRTOS_printf( ( "[MBEDTLS] %s:%d: %s", pcBaseName, lLine, pcMessage ) );
}
#endif

static void prvPrintMbedtlsError( const char * pcWhere,
                                  int lError )
{
#if defined( MBEDTLS_ERROR_C )
    char cError[ 96 ];

    mbedtls_strerror( lError, cError, sizeof( cError ) );
    FreeRTOS_printf( ( "[LANBENCH] %s failed ret=-0x%lx %s\r\n",
                       pcWhere,
                       ( unsigned long ) ( -lError ),
                       cError ) );
#else
    FreeRTOS_printf( ( "[LANBENCH] %s failed ret=%ld\r\n",
                       pcWhere,
                       ( long ) lError ) );
#endif
}

#endif /* LANBENCH_TLS13_0RTT_ENABLE */

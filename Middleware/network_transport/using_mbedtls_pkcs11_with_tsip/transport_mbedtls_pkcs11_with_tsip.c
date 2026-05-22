/*
 * FreeRTOS V202112.00
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

/**
 * @file transport_mbedtls_pkcs11_with_tsip.c
 * @brief TLS transport interface implementations. This implementation uses
 * mbedTLS.
 */

#include "logging_levels.h"

#define LIBRARY_LOG_NAME     "PkcsTlsTransport"
#define LIBRARY_LOG_LEVEL    LOG_INFO

#include "logging_stack.h"

#define MBEDTLS_ALLOW_PRIVATE_ACCESS

#include "mbedtls/private_access.h"
#include "mbedtls/debug.h"

/* Standard includes. */
#include <stdint.h>
#include <string.h>

/* FreeRTOS includes. */
#include "FreeRTOS.h"
#include "task.h"

/* MbedTLS Bio TCP sockets wrapper include. */
#include "mbedtls_bio_tcp_sockets_wrapper.h"

/* TLS transport header. */
#include "transport_mbedtls_pkcs11_with_tsip.h"
#include "mbedtls_pk_pkcs11.h"

/* PKCS #11 includes. */
#include "core_pkcs11_config_defaults.h"
#include "core_pkcs11_config.h"
#include "core_pkcs11.h"
#include "pkcs11.h"
#include "core_pki_utils.h"

/* Mbedtls with TSIP */
#include "key_write.h"

/* strnlen includes for CC-RX compiler. */
#if defined(__CCRX__)
#include "strnlen.h"
#endif

/*-----------------------------------------------------------*/

/**
 * @brief Each compilation unit that consumes the NetworkContext must define it.
 * It should contain a single pointer as seen below whenever the header file
 * of this transport implementation is included to your project.
 *
 * @note When using multiple transports in the same compilation unit,
 *       define this pointer as void *.
 */
struct NetworkContext
{
    TlsTransportParams_t * pParams;
};

/*-----------------------------------------------------------*/

/**
 * @brief Represents string to be logged when mbedTLS returned error
 * does not contain a high-level code.
 */
static const char * pNoHighLevelMbedTlsCodeStr = "<No-High-Level-Code>";

/**
 * @brief Represents string to be logged when mbedTLS returned error
 * does not contain a low-level code.
 */
static const char * pNoLowLevelMbedTlsCodeStr = "<No-Low-Level-Code>";

static void prvLogCurrentTaskStackHighWaterMark( const char * pcLabel )
{
    #if ( INCLUDE_uxTaskGetStackHighWaterMark == 1 )
        LogInfo( ( "TLS stack trace: %s highwater=%lu.",
                   pcLabel,
                   ( unsigned long ) uxTaskGetStackHighWaterMark( NULL ) ) );
    #else
        ( void ) pcLabel;
    #endif
}

/**
 * @brief Utility for converting the high-level code in an mbedTLS error to string,
 * if the code-contains a high-level code; otherwise, using a default string.
 */
#define mbedtlsHighLevelCodeOrDefault( mbedTlsCode )       \
    ( mbedtls_high_level_strerr( mbedTlsCode ) != NULL ) ? \
    mbedtls_high_level_strerr( mbedTlsCode ) : pNoHighLevelMbedTlsCodeStr

/**
 * @brief Utility for converting the level-level code in an mbedTLS error to string,
 * if the code-contains a level-level code; otherwise, using a default string.
 */
#define mbedtlsLowLevelCodeOrDefault( mbedTlsCode )       \
    ( mbedtls_low_level_strerr( mbedTlsCode ) != NULL ) ? \
    mbedtls_low_level_strerr( mbedTlsCode ) : pNoLowLevelMbedTlsCodeStr

#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    #define TSIP_ROOT_CA_SIGNATURE_SIZE    ( 256U )

    #ifndef TSIP_RUNTIME_ROOT_CA_VERIFY_REQUIRED
        #define TSIP_RUNTIME_ROOT_CA_VERIFY_REQUIRED    ( 0 )
    #endif

    #ifndef TSIP_RUNTIME_SERVER_CERT_VERIFY_REQUIRED
        #define TSIP_RUNTIME_SERVER_CERT_VERIFY_REQUIRED    ( 0 )
    #endif

    extern BaseType_t xTsipProvisioningReadRootCaSignature( uint8_t * pucBuffer,
                                                            uint32_t ulBufferSize,
                                                            uint32_t * pulActualSize );
    extern BaseType_t xTsipProvisioningPrepareTlsRootCaTrustAnchor( void );
    extern BaseType_t xTsipProvisioningLoadClientRsa2048KeyPair( void );
    static const unsigned char * gpTlsRootCaSignatureOverride = NULL;
    static size_t gxTlsRootCaSignatureOverrideSize = 0U;
#endif /* TSIP_TLS_API_ENABLE && TSIP_RUNTIME_PROVISIONING_ENABLE */
static int glTlsServerCertAuthModeOverride = -1;
static int glTlsDisableTsipTlsAccelOverride = 0;

/*-----------------------------------------------------------*/

/**
 * @brief Initialize the mbed TLS structures in a network connection.
 *
 * @param[in] pSslContext The SSL context to initialize.
 */
static void sslContextInit( SSLContext_t * pSslContext );

/**
 * @brief Free the mbed TLS structures in a network connection.
 *
 * @param[in] pSslContext The SSL context to free.
 */
static void sslContextFree( SSLContext_t * pSslContext );

/**
 * @brief Set up TLS on a TCP connection.
 *
 * @param[in] pNetworkContext Network context.
 * @param[in] pHostName Remote host name, used for server name indication.
 * @param[in] pNetworkCredentials TLS setup parameters.
 *
 * @return #TLS_TRANSPORT_SUCCESS, #TLS_TRANSPORT_INSUFFICIENT_MEMORY, #TLS_TRANSPORT_INVALID_CREDENTIALS,
 * #TLS_TRANSPORT_HANDSHAKE_FAILED, or #TLS_TRANSPORT_INTERNAL_ERROR.
 */
static TlsTransportStatus_t tlsSetup( NetworkContext_t * pNetworkContext,
                                      const char * pHostName,
                                      const NetworkCredentials_t * pNetworkCredentials );

/*-----------------------------------------------------------*/

/**
 * @brief Callback that wraps PKCS#11 for pseudo-random number generation.
 *
 * @param[in] pvCtx Caller context.
 * @param[in] pucRandom Byte array to fill with random data.
 * @param[in] xRandomLength Length of byte array.
 *
 * @return Zero on success.
 */
static int generateRandomBytes( void * pvCtx,
                                unsigned char * pucRandom,
                                size_t xRandomLength );

/**
 * @brief Helper for reading the specified certificate object, if present,
 * out of storage, into RAM, and then into an mbedTLS certificate context
 * object.
 *
 * @param[in] pSslContext Caller TLS context.
 * @param[in] pcLabelName PKCS #11 certificate object label.
 * @param[in] xClass PKCS #11 certificate object class.
 * @param[out] pxCertificateContext Certificate context.
 *
 * @return Zero on success.
 */
static CK_RV readCertificateIntoContext( SSLContext_t * pSslContext,
                                         const char * pcLabelName,
                                         CK_OBJECT_CLASS xClass,
                                         mbedtls_x509_crt * pxCertificateContext );
static void tlsDebugCallback( void * pvContext,
                              int level,
                              const char * pcFile,
                              int line,
                              const char * pcMessage );

/**
 * @brief Helper for setting up potentially hardware-based cryptographic context
 * for the client TLS certificate and private key.
 *
 * @param[in] Caller context.
 * @param[in] PKCS11 label which contains the desired private key.
 *
 * @return Zero on success.
 */
static CK_RV initializeClientKeys( SSLContext_t * pxCtx,
                                   const char * pcLabelName );

/**
 * @brief Stub function to satisfy mbedtls checks before sign operations
 *
 * @return 1.
 */
int canDoStub( mbedtls_pk_type_t type );

/**
 * @brief Sign a cryptographic hash with the private key.
 *
 * @param[in] pvContext Crypto context.
 * @param[in] xMdAlg Unused.
 * @param[in] pucHash Length in bytes of hash to be signed.
 * @param[in] uiHashLen Byte array of hash to be signed.
 * @param[out] pucSig RSA signature bytes.
 * @param[in] pxSigLen Length in bytes of signature buffer.
 * @param[in] piRng Unused.
 * @param[in] pvRng Unused.
 *
 * @return Zero on success.
 */
static int32_t privateKeySigningCallback( void * pvContext,
                                          mbedtls_md_type_t xMdAlg,
                                          const unsigned char * pucHash,
                                          size_t xHashLen,
                                          unsigned char * pucSig,
                                          size_t * pxSigLen,
                                          int32_t ( * piRng )( void *,
                                                               unsigned char *,
                                                               size_t ),
                                          void * pvRng );


/*-----------------------------------------------------------*/

void vTlsTransportSetRootCaSignatureOverride( const unsigned char * pucSignature,
                                              size_t xSignatureSize )
{
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    gpTlsRootCaSignatureOverride = pucSignature;
    gxTlsRootCaSignatureOverrideSize = xSignatureSize;
#else
    (void)pucSignature;
    (void)xSignatureSize;
#endif
}

void vTlsTransportClearRootCaSignatureOverride( void )
{
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    gpTlsRootCaSignatureOverride = NULL;
    gxTlsRootCaSignatureOverrideSize = 0U;
#endif
}

void vTlsTransportSetServerCertAuthModeOverride( int lAuthMode )
{
    glTlsServerCertAuthModeOverride = lAuthMode;
}

void vTlsTransportClearServerCertAuthModeOverride( void )
{
    glTlsServerCertAuthModeOverride = -1;
}

void vTlsTransportSetDisableTsipTlsAccelOverride( int lDisable )
{
    glTlsDisableTsipTlsAccelOverride = lDisable;
}

void vTlsTransportClearDisableTsipTlsAccelOverride( void )
{
    glTlsDisableTsipTlsAccelOverride = 0;
}

#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
static const unsigned char * prvGetRootCaSignatureForTsip( uint8_t * pucBuffer,
                                                           uint32_t * pulActualSize )
{
    if( ( NULL != gpTlsRootCaSignatureOverride ) &&
        ( TSIP_ROOT_CA_SIGNATURE_SIZE == gxTlsRootCaSignatureOverrideSize ) )
    {
        *pulActualSize = (uint32_t)gxTlsRootCaSignatureOverrideSize;
        return gpTlsRootCaSignatureOverride;
    }

    if( ( pdTRUE == xTsipProvisioningReadRootCaSignature( pucBuffer,
                                                          TSIP_ROOT_CA_SIGNATURE_SIZE,
                                                          pulActualSize ) ) &&
        ( TSIP_ROOT_CA_SIGNATURE_SIZE == *pulActualSize ) )
    {
        return pucBuffer;
    }

    return NULL;
}
#endif

static void sslContextInit( SSLContext_t * pSslContext )
{
    configASSERT( pSslContext != NULL );

    mbedtls_ssl_config_init( &( pSslContext->config ) );
    mbedtls_x509_crt_init( &( pSslContext->rootCa ) );
    mbedtls_x509_crt_init( &( pSslContext->clientCert ) );
    mbedtls_ssl_init( &( pSslContext->context ) );
#if defined(TSIP_TLS_API_ENABLE)
    pSslContext->context.tsip_cipher_suite = 0U;
    pSslContext->context.disable_tsip_tls_accel = 0U;
#endif

    xInitializePkcs11Session( &( pSslContext->xP11Session ) );
    C_GetFunctionList( &( pSslContext->pxP11FunctionList ) );
}
/*-----------------------------------------------------------*/

static void sslContextFree( SSLContext_t * pSslContext )
{
    configASSERT( pSslContext != NULL );

    mbedtls_ssl_free( &( pSslContext->context ) );
    mbedtls_x509_crt_free( &( pSslContext->rootCa ) );
    mbedtls_x509_crt_free( &( pSslContext->clientCert ) );
    mbedtls_ssl_config_free( &( pSslContext->config ) );

    mbedtls_pk_free( &( pSslContext->privKey ) );

    pSslContext->pxP11FunctionList->C_CloseSession( pSslContext->xP11Session );
}

/*-----------------------------------------------------------*/

static TlsTransportStatus_t tlsSetup( NetworkContext_t * pNetworkContext,
                                      const char * pHostName,
                                      const NetworkCredentials_t * pNetworkCredentials )
{
    TlsTransportParams_t * pTlsTransportParams = NULL;
    TlsTransportStatus_t returnStatus = TLS_TRANSPORT_SUCCESS;
    int32_t mbedtlsError = 0;
    CK_RV xResult = CKR_OK;
    long lTraceUseTsipKey = 0L;
    long lTraceDisableTsipAccel = 0L;

#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    BaseType_t xUseTsipRuntimeKey = pdFALSE;
    BaseType_t xDisableTsipTlsAccelForConnection = pdFALSE;
    BaseType_t xPrivateKeyLabelIsDevice = pdFALSE;
#endif

#if defined(TSIP_TLS_API_ENABLE)
    extern mbedtls_threading_mutex_t 						mutexUseTsip;
    extern tsip_tls_ca_certification_public_key_index_t		system_user_rsa2048_ne_key_index;
    extern uint8_t                                         tsip_rootca_rsa_pubkey_scnt;
    extern uint32_t                                        tsip_rootca_rsa_pubkey[5][140];
#if defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    uint8_t trust_ca_root_rsa_certificate_signature[ TSIP_ROOT_CA_SIGNATURE_SIZE ] = { 0 };
    uint32_t ulRootCaSignatureSize = 0;
    const unsigned char * pTsipRootCaSignature = NULL;
#else
	const char trust_ca_root_rsa_certificate_signature[] = {
		#include "AmazonRootCA1_sig_array.txt"
    };
#endif /* TSIP_RUNTIME_PROVISIONING_ENABLE */
#endif

    configPRINT_STRING( "TSET: entry direct\r\n" );
    LogInfo( ( "TSET: entry ctx=%p host=%p credentials=%p.",
               pNetworkContext,
               pHostName,
               pNetworkCredentials ) );

    configASSERT( pNetworkContext != NULL );
    configPRINT_STRING( "TSET: ctx ok direct\r\n" );
    LogInfo( ( "TSET: assert ctx ok." ) );
    configASSERT( pNetworkContext->pParams != NULL );
    configPRINT_STRING( "TSET: params ok direct\r\n" );
    LogInfo( ( "TSET: assert params ok." ) );
    configASSERT( pHostName != NULL );
    configPRINT_STRING( "TSET: host ok direct\r\n" );
    LogInfo( ( "TSET: assert host ok." ) );
    configASSERT( pNetworkCredentials != NULL );
    configPRINT_STRING( "TSET: credentials ok direct\r\n" );
    LogInfo( ( "TSET: assert credentials ok." ) );
    configASSERT( pNetworkCredentials->pRootCa != NULL );
    configPRINT_STRING( "TSET: root ok direct\r\n" );
    LogInfo( ( "TSET: assert root ok." ) );
    configASSERT( pNetworkCredentials->pClientCertLabel != NULL );
    configPRINT_STRING( "TSET: cert label ok direct\r\n" );
    LogInfo( ( "TSET: assert cert label ok." ) );
    configASSERT( pNetworkCredentials->pPrivateKeyLabel != NULL );
    configPRINT_STRING( "TSET: key label ok direct\r\n" );
    LogInfo( ( "TSET: assert key label ok." ) );

    pTlsTransportParams = pNetworkContext->pParams;

    LogInfo( ( "TSET: params=%p root=%p certLabel=%p keyLabel=%p.",
               pTlsTransportParams,
               pNetworkCredentials->pRootCa,
               pNetworkCredentials->pClientCertLabel,
               pNetworkCredentials->pPrivateKeyLabel ) );

    LogInfo( ( "TLS trace: setup enter host=%s cert=%s key=%s.",
               pHostName,
               pNetworkCredentials->pClientCertLabel,
               pNetworkCredentials->pPrivateKeyLabel ) );

    /* Initialize the mbed TLS context structures. */
    configPRINT_STRING( "TSET: ssl init direct\r\n" );
    sslContextInit( &( pTlsTransportParams->sslContext ) );

    configPRINT_STRING( "TSET: config defaults call direct\r\n" );
    mbedtlsError = mbedtls_ssl_config_defaults( &( pTlsTransportParams->sslContext.config ),
                                                MBEDTLS_SSL_IS_CLIENT,
                                                MBEDTLS_SSL_TRANSPORT_STREAM,
                                                MBEDTLS_SSL_PRESET_DEFAULT );
    configPRINT_STRING( "TSET: config defaults returned direct\r\n" );

    if( mbedtlsError != 0 )
    {
        LogError( ( "Failed to set default SSL configuration: mbedTLSError= %s : %s.",
                    mbedtlsHighLevelCodeOrDefault( mbedtlsError ),
                    mbedtlsLowLevelCodeOrDefault( mbedtlsError ) ) );

        /* Per mbed TLS docs, mbedtls_ssl_config_defaults only fails on memory allocation. */
        returnStatus = TLS_TRANSPORT_INSUFFICIENT_MEMORY;
    }

    if( returnStatus == TLS_TRANSPORT_SUCCESS )
    {
        /* Set up the certificate security profile, starting from the default value. */
        pTlsTransportParams->sslContext.certProfile = mbedtls_x509_crt_profile_default;

        /* test.mosquitto.org only provides a 1024-bit RSA certificate, which is
         * not acceptable by the default mbed TLS certificate security profile.
         * For the purposes of this demo, allow the use of 1024-bit RSA certificates.
         * This block should be removed otherwise. */
        if( strncmp( pHostName, "test.mosquitto.org", strlen( pHostName ) ) == 0 )
        {
            pTlsTransportParams->sslContext.certProfile.rsa_min_bitlen = 1024;
        }

        /* Set SSL authmode and the RNG context. */
        if( glTlsServerCertAuthModeOverride >= 0 )
        {
            mbedtls_ssl_conf_authmode( &( pTlsTransportParams->sslContext.config ),
                                       glTlsServerCertAuthModeOverride );
        }
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
        else if( TSIP_RUNTIME_SERVER_CERT_VERIFY_REQUIRED != 1 )
        {
            mbedtls_ssl_conf_authmode( &( pTlsTransportParams->sslContext.config ),
                                       MBEDTLS_SSL_VERIFY_OPTIONAL );
        }
#endif
        else
        {
            mbedtls_ssl_conf_authmode( &( pTlsTransportParams->sslContext.config ),
                                       MBEDTLS_SSL_VERIFY_REQUIRED );
        }
        mbedtls_ssl_conf_rng( &( pTlsTransportParams->sslContext.config ),
                              generateRandomBytes,
                              &pTlsTransportParams->sslContext );
        mbedtls_ssl_conf_cert_profile( &( pTlsTransportParams->sslContext.config ),
                                       &( pTlsTransportParams->sslContext.certProfile ) );
        if( pNetworkCredentials->pCipherSuites != NULL )
        {
            mbedtls_ssl_conf_ciphersuites( &( pTlsTransportParams->sslContext.config ),
                                           pNetworkCredentials->pCipherSuites );
        }
        if( pNetworkCredentials->pSigAlgs != NULL )
        {
            mbedtls_ssl_conf_sig_algs( &( pTlsTransportParams->sslContext.config ),
                                       pNetworkCredentials->pSigAlgs );
        }
        if( pNetworkCredentials->tlsDebugLevel > 0U )
        {
            mbedtls_debug_set_threshold( (int)pNetworkCredentials->tlsDebugLevel );
            mbedtls_ssl_conf_dbg( &( pTlsTransportParams->sslContext.config ),
                                  tlsDebugCallback,
                                  NULL );
        }

        /* Parse the server root CA certificate into the SSL context. */
        mbedtlsError = mbedtls_x509_crt_parse( &( pTlsTransportParams->sslContext.rootCa ),
                                               pNetworkCredentials->pRootCa,
                                               pNetworkCredentials->rootCaSize );

        if( mbedtlsError != 0 )
        {
            LogError( ( "Failed to parse server root CA certificate: mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( mbedtlsError ),
                        mbedtlsLowLevelCodeOrDefault( mbedtlsError ) ) );

            returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
        }
        else
        {
            mbedtls_ssl_conf_ca_chain( &( pTlsTransportParams->sslContext.config ),
                                       &( pTlsTransportParams->sslContext.rootCa ),
                                       NULL );
            LogInfo( ( "TLS trace: root CA parsed." ) );
        }
    }

    /* Configure the client certificate private key. TSIP runtime credentials
     * take precedence for the normal device key. Fleet provisioning claim and
     * generated keys remain PKCS #11 software keys in the TSIP-capable build. */
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    if( returnStatus == TLS_TRANSPORT_SUCCESS )
    {
        mbedtls_pk_init( &( pTlsTransportParams->sslContext.privKey ) );

        xPrivateKeyLabelIsDevice =
            ( 0 == strncmp( pNetworkCredentials->pPrivateKeyLabel,
                            pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS,
                            sizeof( pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS ) ) ) ? pdTRUE : pdFALSE;

        if( ( xPrivateKeyLabelIsDevice == pdTRUE ) &&
            ( pdTRUE == xTsipProvisioningLoadClientRsa2048KeyPair() ) )
        {
            xUseTsipRuntimeKey = pdTRUE;
            LogInfo( ( "TLS trace: TSIP runtime device key selected." ) );
            mbedtlsError = mbedtls_pk_setup( &( pTlsTransportParams->sslContext.privKey ),
                                             mbedtls_pk_info_from_type( MBEDTLS_PK_RSA ) );

            if( mbedtlsError != 0 )
            {
                LogError( ( "Failed to setup TSIP runtime private key." ) );
                returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
            }
        }

        if( ( returnStatus == TLS_TRANSPORT_SUCCESS ) &&
            ( xUseTsipRuntimeKey == pdFALSE ) )
        {
            LogInfo( ( "TLS trace: PKCS #11 key setup enter label=%s.",
                       pNetworkCredentials->pPrivateKeyLabel ) );
            xResult = initializeClientKeys( &( pTlsTransportParams->sslContext ),
                                            pNetworkCredentials->pPrivateKeyLabel );
            LogInfo( ( "TLS trace: PKCS #11 key setup exit ret=0x%08lx.",
                       ( unsigned long ) xResult ) );

            if( xResult != CKR_OK )
            {
                LogError( ( "Failed to setup PKCS #11 private key for label \"%s\": CK_RV=0x%08lx.",
                            pNetworkCredentials->pPrivateKeyLabel,
                            ( unsigned long ) xResult ) );
                returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
            }
            else
            {
                xDisableTsipTlsAccelForConnection = pdTRUE;
            }
        }

        if( returnStatus == TLS_TRANSPORT_SUCCESS )
        {
            LogInfo( ( "TLS trace: client certificate load enter label=%s.",
                       pNetworkCredentials->pClientCertLabel ) );
            xResult = readCertificateIntoContext( &( pTlsTransportParams->sslContext ),
                                                  pNetworkCredentials->pClientCertLabel,
                                                  CKO_CERTIFICATE,
                                                  &( pTlsTransportParams->sslContext.clientCert ) );
            LogInfo( ( "TLS trace: client certificate load exit ret=0x%08lx.",
                       ( unsigned long ) xResult ) );

            if( xResult != CKR_OK )
            {
                LogError( ( "Failed to get certificate from PKCS #11 module." ) );
                returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
            }
            else
            {
                ( void ) mbedtls_ssl_conf_own_cert( &( pTlsTransportParams->sslContext.config ),
                                                    &( pTlsTransportParams->sslContext.clientCert ),
                                                    &( pTlsTransportParams->sslContext.privKey ) );
            }
        }
    }
#else
    if (TLS_TRANSPORT_SUCCESS == returnStatus)
    {
        /* Configuring client certificate private key (RSA) */
        mbedtls_pk_init(&(pTlsTransportParams->sslContext.privKey));
        mbedtlsError = mbedtls_pk_setup(&(pTlsTransportParams->sslContext.privKey),
                                        mbedtls_pk_info_from_type(MBEDTLS_PK_RSA));
        if (0 != mbedtlsError)
        {
            LogError(("Failed to setup Private key"));
            returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
        }
        else
        {
            /* Setup the client certificate. */
            xResult = readCertificateIntoContext( &( pTlsTransportParams->sslContext ),
                                                  pNetworkCredentials->pClientCertLabel,
                                                  CKO_CERTIFICATE,
                                                  &( pTlsTransportParams->sslContext.clientCert ) );

            if( xResult != CKR_OK )
            {
                LogError( ( "Failed to get certificate from PKCS #11 module." ) );

                returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
            }
            else
            {
                ( void ) mbedtls_ssl_conf_own_cert( &( pTlsTransportParams->sslContext.config ),
                                                    &( pTlsTransportParams->sslContext.clientCert ),
                                                    &( pTlsTransportParams->sslContext.privKey ) );
            }
        }
    }
#endif /* TSIP_TLS_API_ENABLE && TSIP_RUNTIME_PROVISIONING_ENABLE */

    /* RootCA certificate verification */
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    if( ( returnStatus == TLS_TRANSPORT_SUCCESS ) &&
        ( xUseTsipRuntimeKey == pdTRUE ) )
    {
        if( pdTRUE != xTsipProvisioningPrepareTlsRootCaTrustAnchor() )
        {
            LogError( ( "Failed to load TSIP runtime Root CA trust anchor." ) );
            returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
        }
        else if( NULL == ( pTsipRootCaSignature = prvGetRootCaSignatureForTsip( trust_ca_root_rsa_certificate_signature,
                                                                                &ulRootCaSignatureSize ) ) )
        {
            LogError( ( "Failed to load Root CA signature for TSIP runtime provisioning." ) );
            returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
        }
        else
        {
            LogInfo( ( "TLS trace: TSIP Root CA trust anchor prepared." ) );
        }
    }
#endif /* TSIP_TLS_API_ENABLE && TSIP_RUNTIME_PROVISIONING_ENABLE */

    if( ( returnStatus == TLS_TRANSPORT_SUCCESS ) &&
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
        ( xUseTsipRuntimeKey == pdTRUE ) &&
#endif
        ( glTlsServerCertAuthModeOverride != MBEDTLS_SSL_VERIFY_NONE ) )
    {
    tsip_rootca_rsa_pubkey_scnt = 0U;
    mbedtls_rsa_context * p_tmprsa = mbedtls_pk_rsa(pTlsTransportParams->sslContext.rootCa.pk);
    mbedtlsError = R_TSIP_TlsRootCertificateVerification(
                    (uint32_t)R_TSIP_TLS_PUBLIC_KEY_TYPE_RSA2048, // 0 : RSA 2048bit
                    (uint8_t*)pTlsTransportParams->sslContext.rootCa.raw.p, //
                    (uint32_t)pTlsTransportParams->sslContext.rootCa.raw.len, //
                    (uint32_t)(p_tmprsa->pubkey_n_spos + 1) -   //
                        (uint32_t)(uint8_t *)pTlsTransportParams->sslContext.rootCa.raw.p, //
                    (uint32_t)(p_tmprsa->pubkey_n_spos -    //
                        (uint32_t)(uint8_t *)pTlsTransportParams->sslContext.rootCa.raw.p) +    //
                        (p_tmprsa->pubkey_n_epos - 1), //
                    (uint32_t)p_tmprsa->pubkey_e_spos - //
                        (uint32_t)(uint8_t *)pTlsTransportParams->sslContext.rootCa.raw.p,  //
                    (uint32_t)(p_tmprsa->pubkey_e_spos -    //
                        (uint32_t)(uint8_t *)pTlsTransportParams->sslContext.rootCa.raw.p) +    //
                        (p_tmprsa->pubkey_e_epos - 1), //
                    (uint8_t *)
#if defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
                    pTsipRootCaSignature,
#else
                    trust_ca_root_rsa_certificate_signature,
#endif
                    &tsip_rootca_rsa_pubkey[tsip_rootca_rsa_pubkey_scnt][0]);
    if (TSIP_SUCCESS != mbedtlsError)
    {
        #if ( TSIP_RUNTIME_ROOT_CA_VERIFY_REQUIRED == 1 )
            LogError(("Failed to RootCA certificate verification"));
            returnStatus = TLS_TRANSPORT_INVALID_CREDENTIALS;
        #else
            LogWarn(("Failed to RootCA certificate verification; continuing with mbed TLS CA verification."));
        #endif
    }
    else
    {
        tsip_rootca_rsa_pubkey_scnt = 1U;
    }
    }
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
    else if( ( xUseTsipRuntimeKey == pdFALSE ) ||
             ( glTlsServerCertAuthModeOverride == MBEDTLS_SSL_VERIFY_NONE ) )
#else
    else if( glTlsServerCertAuthModeOverride == MBEDTLS_SSL_VERIFY_NONE )
#endif
    {
        tsip_rootca_rsa_pubkey_scnt = 0U;
    }

    if( ( returnStatus == TLS_TRANSPORT_SUCCESS ) && ( pNetworkCredentials->pAlpnProtos != NULL ) )
    {
        /* Include an application protocol list in the TLS ClientHello
         * message. */
        mbedtlsError = mbedtls_ssl_conf_alpn_protocols( &( pTlsTransportParams->sslContext.config ),
                                                        pNetworkCredentials->pAlpnProtos );

        if( mbedtlsError != 0 )
        {
            LogError( ( "Failed to configure ALPN protocol in mbed TLS: mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( mbedtlsError ),
                        mbedtlsLowLevelCodeOrDefault( mbedtlsError ) ) );

            returnStatus = TLS_TRANSPORT_INTERNAL_ERROR;
        }
        else
        {
            LogInfo( ( "TLS trace: ALPN configured." ) );
        }
    }

    if( returnStatus == TLS_TRANSPORT_SUCCESS )
    {
        /* Initialize the mbed TLS secured connection context. */
#if defined(TSIP_TLS_API_ENABLE) && defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
        lTraceUseTsipKey = ( long ) xUseTsipRuntimeKey;
        lTraceDisableTsipAccel = ( long ) xDisableTsipTlsAccelForConnection;
#endif
        LogInfo( ( "TLS trace: ssl_setup enter use_tsip_key=%ld disable_tsip_accel=%ld.",
                   lTraceUseTsipKey,
                   lTraceDisableTsipAccel ) );
        mbedtlsError = mbedtls_ssl_setup( &( pTlsTransportParams->sslContext.context ),
                                          &( pTlsTransportParams->sslContext.config ) );
        LogInfo( ( "TLS trace: ssl_setup exit ret=%ld.",
                   ( long ) mbedtlsError ) );

        if( mbedtlsError != 0 )
        {
            LogError( ( "Failed to set up mbed TLS SSL context: mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( mbedtlsError ),
                        mbedtlsLowLevelCodeOrDefault( mbedtlsError ) ) );

            returnStatus = TLS_TRANSPORT_INTERNAL_ERROR;
        }
        else
        {
#if defined(TSIP_TLS_API_ENABLE)
            pTlsTransportParams->sslContext.context.disable_tsip_tls_accel =
                ( ( glTlsDisableTsipTlsAccelOverride != 0 )
#if defined(TSIP_RUNTIME_PROVISIONING_ENABLE)
                  || ( xDisableTsipTlsAccelForConnection != pdFALSE )
#endif
                  ) ? 1U : 0U;
            if( pNetworkCredentials->tlsDebugLevel > 0U )
            {
                LogInfo( ( "TSIP TLS accel override=%ld",
                           (long)pTlsTransportParams->sslContext.context.disable_tsip_tls_accel ) );
            }
#endif
            /* Set the underlying IO for the TLS connection. */

            /* MISRA Rule 11.2 flags the following line for casting the second
             * parameter to void *. This rule is suppressed because
             * #mbedtls_ssl_set_bio requires the second parameter as void *.
             */
            /* coverity[misra_c_2012_rule_11_2_violation] */
            mbedtls_ssl_set_bio( &( pTlsTransportParams->sslContext.context ),
                                 ( void * ) pTlsTransportParams->tcpSocket,
                                 xMbedTLSBioTCPSocketsWrapperSend,
                                 xMbedTLSBioTCPSocketsWrapperRecv,
                                 NULL );
        }
    }

    if( returnStatus == TLS_TRANSPORT_SUCCESS )
    {
        /* Enable SNI if requested. */
        if( pNetworkCredentials->disableSni == pdFALSE )
        {
            mbedtlsError = mbedtls_ssl_set_hostname( &( pTlsTransportParams->sslContext.context ),
                                                     pHostName );
        }
        /* MbedTLS-3.6.3 requires calling the mbedtls_ssl_set_hostname() before calling mbedtls_ssl_handshake(). */
        else
        {
            mbedtlsError = mbedtls_ssl_set_hostname( &( pTlsTransportParams->sslContext.context ),
                                                     NULL );
        }

        if( mbedtlsError != 0 )
        {
            LogError( ( "Failed to set server name: mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( mbedtlsError ),
                        mbedtlsLowLevelCodeOrDefault( mbedtlsError ) ) );

            returnStatus = TLS_TRANSPORT_INTERNAL_ERROR;
        }
        else
        {
            LogInfo( ( "TLS trace: hostname configured." ) );
        }
    }

    /* Set Maximum Fragment Length if enabled. */
    #ifdef MBEDTLS_SSL_MAX_FRAGMENT_LENGTH
        if( returnStatus == TLS_TRANSPORT_SUCCESS )
        {
            /* Enable the max fragment extension. 4096 bytes is currently the largest fragment size permitted.
             * See RFC 8449 https://tools.ietf.org/html/rfc8449 for more information.
             *
             * Smaller values can be found in "mbedtls/include/ssl.h".
             */
            mbedtlsError = mbedtls_ssl_conf_max_frag_len( &( pTlsTransportParams->sslContext.config ), MBEDTLS_SSL_MAX_FRAG_LEN_4096 );

            if( mbedtlsError != 0 )
            {
                LogError( ( "Failed to maximum fragment length extension: mbedTLSError= %s : %s.",
                            mbedtlsHighLevelCodeOrDefault( mbedtlsError ),
                            mbedtlsLowLevelCodeOrDefault( mbedtlsError ) ) );
                returnStatus = TLS_TRANSPORT_INTERNAL_ERROR;
            }
        }
    #endif /* ifdef MBEDTLS_SSL_MAX_FRAGMENT_LENGTH */

    if( returnStatus == TLS_TRANSPORT_SUCCESS )
    {
        uint32_t ulHandshakeAttempt = 0U;

        LogInfo( ( "TLS trace: handshake enter state=%ld.",
                   ( long ) pTlsTransportParams->sslContext.context.MBEDTLS_PRIVATE( state ) ) );
        prvLogCurrentTaskStackHighWaterMark( "before_handshake" );

        /* Perform the TLS handshake. */
        do
        {
            if( pNetworkCredentials->tlsDebugLevel > 0U )
            {
                LogInfo( ( "TLS handshake call begin: attempt=%lu state=%ld",
                           (unsigned long)ulHandshakeAttempt,
                           (long)pTlsTransportParams->sslContext.context.MBEDTLS_PRIVATE( state ) ) );
            }
            mbedtlsError = mbedtls_ssl_handshake( &( pTlsTransportParams->sslContext.context ) );
            if( pNetworkCredentials->tlsDebugLevel > 0U )
            {
                LogInfo( ( "TLS handshake call end: attempt=%lu state=%ld ret=%ld",
                           (unsigned long)ulHandshakeAttempt,
                           (long)pTlsTransportParams->sslContext.context.MBEDTLS_PRIVATE( state ),
                           (long)mbedtlsError ) );
            }
            ulHandshakeAttempt++;
        } while( ( mbedtlsError == MBEDTLS_ERR_SSL_WANT_READ ) ||
                 ( mbedtlsError == MBEDTLS_ERR_SSL_WANT_WRITE ) );

        LogInfo( ( "TLS trace: handshake exit attempts=%lu state=%ld ret=%ld.",
                   ( unsigned long ) ulHandshakeAttempt,
                   ( long ) pTlsTransportParams->sslContext.context.MBEDTLS_PRIVATE( state ),
                   ( long ) mbedtlsError ) );
        prvLogCurrentTaskStackHighWaterMark( "after_handshake" );

        if( mbedtlsError != 0 )
        {
            LogError( ( "Failed to perform TLS handshake: mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( mbedtlsError ),
                        mbedtlsLowLevelCodeOrDefault( mbedtlsError ) ) );

            returnStatus = TLS_TRANSPORT_HANDSHAKE_FAILED;
        }
    }

    if( returnStatus != TLS_TRANSPORT_SUCCESS )
    {
        sslContextFree( &( pTlsTransportParams->sslContext ) );
    }
    else
    {
        LogInfo( ( "(Network connection %p) TLS handshake successful.",
                   pNetworkContext ) );
    }

    return returnStatus;
}

/*-----------------------------------------------------------*/

static int generateRandomBytes( void * pvCtx,
                                unsigned char * pucRandom,
                                size_t xRandomLength )
{
    /* Must cast from void pointer to conform to mbed TLS API. */
    SSLContext_t * pxCtx = ( SSLContext_t * ) pvCtx;
    CK_RV xResult;

    LogInfo( ( "TLS trace: RNG enter len=%lu.",
               ( unsigned long ) xRandomLength ) );
    xResult = pxCtx->pxP11FunctionList->C_GenerateRandom( pxCtx->xP11Session, pucRandom, xRandomLength );
    LogInfo( ( "TLS trace: RNG exit ret=0x%08lx.",
               ( unsigned long ) xResult ) );

    if( xResult != CKR_OK )
    {
        LogError( ( "Failed to generate random bytes from the PKCS #11 module." ) );
    }

    return xResult;
}

static void tlsDebugCallback( void * pvContext,
                              int level,
                              const char * pcFile,
                              int line,
                              const char * pcMessage )
{
    (void)pvContext;

    if( pcMessage != NULL )
    {
        LogInfo( ( "mbedTLS[%d] %s:%d %s", level, pcFile, line, pcMessage ) );
    }
}

/*-----------------------------------------------------------*/

static CK_RV readCertificateIntoContext( SSLContext_t * pSslContext,
                                         const char * pcLabelName,
                                         CK_OBJECT_CLASS xClass,
                                         mbedtls_x509_crt * pxCertificateContext )
{
    CK_RV xResult = CKR_OK;
    CK_ATTRIBUTE xTemplate = { 0 };
    CK_OBJECT_HANDLE xCertObj = 0;

    /* Get the handle of the certificate. */
    xResult = xFindObjectWithLabelAndClass( pSslContext->xP11Session,
                                            pcLabelName,
                                            strnlen( pcLabelName,
                                                     pkcs11configMAX_LABEL_LENGTH ),
                                            xClass,
                                            &xCertObj );

    if( ( CKR_OK == xResult ) && ( xCertObj == CK_INVALID_HANDLE ) )
    {
        xResult = CKR_OBJECT_HANDLE_INVALID;
    }

    /* Query the certificate size. */
    if( CKR_OK == xResult )
    {
        xTemplate.type = CKA_VALUE;
        xTemplate.ulValueLen = 0;
        xTemplate.pValue = NULL;
        xResult = pSslContext->pxP11FunctionList->C_GetAttributeValue( pSslContext->xP11Session,
                                                                       xCertObj,
                                                                       &xTemplate,
                                                                       1 );
    }

    /* Create a buffer for the certificate. */
    if( CKR_OK == xResult )
    {
        xTemplate.pValue = pvPortMalloc( xTemplate.ulValueLen );

        if( NULL == xTemplate.pValue )
        {
            xResult = CKR_HOST_MEMORY;
        }
    }

    /* Export the certificate. */
    if( CKR_OK == xResult )
    {
        xResult = pSslContext->pxP11FunctionList->C_GetAttributeValue( pSslContext->xP11Session,
                                                                       xCertObj,
                                                                       &xTemplate,
                                                                       1 );
    }

    /* Decode the certificate. */
    if( CKR_OK == xResult )
    {
        xResult = mbedtls_x509_crt_parse( pxCertificateContext,
                                          ( const unsigned char * ) xTemplate.pValue,
                                          xTemplate.ulValueLen );
    }

    /* Free memory. */
    if( xTemplate.pValue != NULL )
    {
        vPortFree( xTemplate.pValue );
    }

    return xResult;
}

/*-----------------------------------------------------------*/

/**
 * @brief Helper for setting up potentially hardware-based cryptographic context
 * for the client TLS certificate and private key.
 *
 * @param[in] Caller context.
 * @param[in] PKCS11 label which contains the desired private key.
 *
 * @return Zero on success.
 */
static CK_RV initializeClientKeys( SSLContext_t * pxCtx,
                                   const char * pcLabelName )
{
    CK_RV xResult = CKR_OK;
    CK_SLOT_ID * pxSlotIds = NULL;
    CK_ULONG xCount = 0;
    CK_ATTRIBUTE xTemplate[ 2 ];
    mbedtls_pk_type_t xKeyAlgo = ( mbedtls_pk_type_t ) ~0;

    /* Get the PKCS #11 module/token slot count. */
    if( CKR_OK == xResult )
    {
        xResult = ( BaseType_t ) pxCtx->pxP11FunctionList->C_GetSlotList( CK_TRUE,
                                                                          NULL,
                                                                          &xCount );
    }

    /* Allocate memory to store the token slots. */
    if( CKR_OK == xResult )
    {
        pxSlotIds = ( CK_SLOT_ID * ) pvPortMalloc( sizeof( CK_SLOT_ID ) * xCount );

        if( NULL == pxSlotIds )
        {
            xResult = CKR_HOST_MEMORY;
        }
    }

    /* Get all of the available private key slot identities. */
    if( CKR_OK == xResult )
    {
        xResult = ( BaseType_t ) pxCtx->pxP11FunctionList->C_GetSlotList( CK_TRUE,
                                                                          pxSlotIds,
                                                                          &xCount );
    }

    /* Put the module in authenticated mode. */
    if( CKR_OK == xResult )
    {
        xResult = ( BaseType_t ) pxCtx->pxP11FunctionList->C_Login( pxCtx->xP11Session,
                                                                    CKU_USER,
                                                                    ( CK_UTF8CHAR_PTR ) pkcs11configPKCS11_DEFAULT_USER_PIN,
                                                                    sizeof( pkcs11configPKCS11_DEFAULT_USER_PIN ) - 1 );
    }

    if( CKR_OK == xResult )
    {
        /* Get the handle of the device private key. */
        xResult = xFindObjectWithLabelAndClass( pxCtx->xP11Session,
                                                pcLabelName,
                                                strnlen( pcLabelName,
                                                         pkcs11configMAX_LABEL_LENGTH ),
                                                CKO_PRIVATE_KEY,
                                                &pxCtx->xP11PrivateKey );
    }

    if( ( CKR_OK == xResult ) && ( pxCtx->xP11PrivateKey == CK_INVALID_HANDLE ) )
    {
        xResult = CK_INVALID_HANDLE;
        LogError( ( "Could not find private key." ) );
    }

    if( xResult == CKR_OK )
    {
        xResult = xPKCS11_initMbedtlsPkContext( &( pxCtx->privKey ),
                                                pxCtx->xP11Session,
                                                pxCtx->xP11PrivateKey );
    }

    /* Free memory. */
    if( pxSlotIds!= NULL )
    {
        vPortFree( pxSlotIds );
    }

    return xResult;
}

/*-----------------------------------------------------------*/

TlsTransportStatus_t TLS_FreeRTOS_Connect( NetworkContext_t * pNetworkContext,
                                           const char * pHostName,
                                           uint16_t port,
                                           const NetworkCredentials_t * pNetworkCredentials,
                                           uint32_t receiveTimeoutMs,
                                           uint32_t sendTimeoutMs )
{
    TlsTransportParams_t * pTlsTransportParams = NULL;
    TlsTransportStatus_t returnStatus = TLS_TRANSPORT_SUCCESS;
    BaseType_t socketStatus = 0;
    BaseType_t isSocketConnected = pdFALSE;

    if( ( pNetworkContext == NULL ) ||
        ( pNetworkContext->pParams == NULL ) ||
        ( pHostName == NULL ) ||
        ( pNetworkCredentials == NULL ) )
    {
        LogError( ( "Invalid input parameter(s): Arguments cannot be NULL. pNetworkContext=%p, "
                    "pHostName=%p, pNetworkCredentials=%p.",
                    pNetworkContext,
                    pHostName,
                    pNetworkCredentials ) );
        returnStatus = TLS_TRANSPORT_INVALID_PARAMETER;
    }
    else if( ( pNetworkCredentials->pRootCa == NULL ) )
    {
        LogError( ( "pRootCa cannot be NULL." ) );
        returnStatus = TLS_TRANSPORT_INVALID_PARAMETER;
    }
    else
    {
        /* Empty else for MISRA 15.7 compliance. */
    }

    /* Establish a TCP connection with the server. */
    if( returnStatus == TLS_TRANSPORT_SUCCESS )
    {
        pTlsTransportParams = pNetworkContext->pParams;

        /* Initialize tcpSocket so failure cleanup never touches a stale handle. */
        pTlsTransportParams->tcpSocket = NULL;

        configPRINT_STRING( "TLSC: tcp connect call\r\n" );
        socketStatus = TCP_Sockets_Connect( &( pTlsTransportParams->tcpSocket ),
                                            pHostName,
                                            port,
                                            receiveTimeoutMs,
                                            sendTimeoutMs );
        configPRINT_STRING( "TLSC: tcp connect returned\r\n" );

        if( socketStatus != 0 )
        {
            LogError( ( "Failed to connect to %s with error %d.",
                        pHostName,
                        socketStatus ) );
            returnStatus = TLS_TRANSPORT_CONNECT_FAILURE;
        }
    }

    /* Perform TLS handshake. */
    if( returnStatus == TLS_TRANSPORT_SUCCESS )
    {
        isSocketConnected = pdTRUE;

        configPRINT_STRING( "TLSC: setup call\r\n" );
        returnStatus = tlsSetup( pNetworkContext, pHostName, pNetworkCredentials );
        configPRINT_STRING( "TLSC: setup returned\r\n" );
    }

    /* Clean up on failure. */
    if( returnStatus != TLS_TRANSPORT_SUCCESS )
    {
        if( isSocketConnected == pdTRUE )
        {
            TCP_Sockets_Disconnect( pTlsTransportParams->tcpSocket );
            pTlsTransportParams->tcpSocket = NULL;
        }
    }
    else
    {
        LogInfo( ( "(Network connection %p) Connection to %s established.",
                   pNetworkContext,
                   pHostName ) );
    }

    return returnStatus;
}

/*-----------------------------------------------------------*/

void TLS_FreeRTOS_Disconnect( NetworkContext_t * pNetworkContext )
{
    TlsTransportParams_t * pTlsTransportParams = NULL;
    BaseType_t tlsStatus = 0;

    if( ( pNetworkContext != NULL ) && ( pNetworkContext->pParams != NULL ) )
    {
        pTlsTransportParams = pNetworkContext->pParams;
        /* Attempting to terminate TLS connection. */
        tlsStatus = ( BaseType_t ) mbedtls_ssl_close_notify( &( pTlsTransportParams->sslContext.context ) );

        /* Ignore the WANT_READ and WANT_WRITE return values. */
        if( ( tlsStatus != ( BaseType_t ) MBEDTLS_ERR_SSL_WANT_READ ) &&
            ( tlsStatus != ( BaseType_t ) MBEDTLS_ERR_SSL_WANT_WRITE ) )
        {
            if( tlsStatus == 0 )
            {
                LogInfo( ( "(Network connection %p) TLS close-notify sent.",
                           pNetworkContext ) );
            }
            else
            {
                LogError( ( "(Network connection %p) Failed to send TLS close-notify: mbedTLSError= %s : %s.",
                            pNetworkContext,
                            mbedtlsHighLevelCodeOrDefault( tlsStatus ),
                            mbedtlsLowLevelCodeOrDefault( tlsStatus ) ) );
            }
        }

        /* Call socket shutdown function to close connection. */
        TCP_Sockets_Disconnect( pTlsTransportParams->tcpSocket );
        pTlsTransportParams->tcpSocket = NULL;

        /* Free mbed TLS contexts. */
        sslContextFree( &( pTlsTransportParams->sslContext ) );
    }
}

/*-----------------------------------------------------------*/

int32_t TLS_FreeRTOS_recv( NetworkContext_t * pNetworkContext,
                           void * pBuffer,
                           size_t bytesToRecv )
{
    TlsTransportParams_t * pTlsTransportParams = NULL;
    int32_t tlsStatus = 0;

    if( ( pNetworkContext == NULL ) || ( pNetworkContext->pParams == NULL ) )
    {
        LogError( ( "invalid input, pNetworkContext=%p", pNetworkContext ) );
        tlsStatus = -1;
    }
    else if( pBuffer == NULL )
    {
        LogError( ( "invalid input, pBuffer == NULL" ) );
        tlsStatus = -1;
    }
    else if( bytesToRecv == 0 )
    {
        LogError( ( "invalid input, bytesToRecv == 0" ) );
        tlsStatus = -1;
    }
    else
    {
        pTlsTransportParams = pNetworkContext->pParams;

        tlsStatus = ( int32_t ) mbedtls_ssl_read( &( pTlsTransportParams->sslContext.context ),
                                                  pBuffer,
                                                  bytesToRecv );

        if( ( tlsStatus == MBEDTLS_ERR_SSL_TIMEOUT ) ||
            ( tlsStatus == MBEDTLS_ERR_SSL_WANT_READ ) ||
            ( tlsStatus == MBEDTLS_ERR_SSL_WANT_WRITE ) )
        {
            LogDebug( ( "Failed to read data. However, a read can be retried on this error. "
                        "mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( tlsStatus ),
                        mbedtlsLowLevelCodeOrDefault( tlsStatus ) ) );

            /* Mark these set of errors as a timeout. The libraries may retry read
             * on these errors. */
            tlsStatus = 0;
        }
        else if( tlsStatus < 0 )
        {
            LogError( ( "Failed to read data: mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( tlsStatus ),
                        mbedtlsLowLevelCodeOrDefault( tlsStatus ) ) );
        }
        else
        {
            /* Empty else marker. */
        }
    }

    return tlsStatus;
}

/*-----------------------------------------------------------*/

int32_t TLS_FreeRTOS_send( NetworkContext_t * pNetworkContext,
                           const void * pBuffer,
                           size_t bytesToSend )
{
    TlsTransportParams_t * pTlsTransportParams = NULL;
    int32_t tlsStatus = 0;

    if( ( pNetworkContext == NULL ) || ( pNetworkContext->pParams == NULL ) )
    {
        LogError( ( "invalid input, pNetworkContext=%p", pNetworkContext ) );
        tlsStatus = -1;
    }
    else if( pBuffer == NULL )
    {
        LogError( ( "invalid input, pBuffer == NULL" ) );
        tlsStatus = -1;
    }
    else if( bytesToSend == 0 )
    {
        LogError( ( "invalid input, bytesToSend == 0" ) );
        tlsStatus = -1;
    }
    else
    {
        pTlsTransportParams = pNetworkContext->pParams;
        tlsStatus = ( int32_t ) mbedtls_ssl_write( &( pTlsTransportParams->sslContext.context ),
                                                   pBuffer,
                                                   bytesToSend );

        if( ( tlsStatus == MBEDTLS_ERR_SSL_TIMEOUT ) ||
            ( tlsStatus == MBEDTLS_ERR_SSL_WANT_READ ) ||
            ( tlsStatus == MBEDTLS_ERR_SSL_WANT_WRITE ) )
        {
            LogDebug( ( "Failed to send data. However, send can be retried on this error. "
                        "mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( tlsStatus ),
                        mbedtlsLowLevelCodeOrDefault( tlsStatus ) ) );

            /* Mark these set of errors as a timeout. The libraries may retry send
             * on these errors. */
            tlsStatus = 0;
        }
        else if( tlsStatus < 0 )
        {
            LogError( ( "Failed to send data:  mbedTLSError= %s : %s.",
                        mbedtlsHighLevelCodeOrDefault( tlsStatus ),
                        mbedtlsLowLevelCodeOrDefault( tlsStatus ) ) );
        }
        else
        {
            /* Empty else marker. */
        }
    }

    return tlsStatus;
}
/*-----------------------------------------------------------*/

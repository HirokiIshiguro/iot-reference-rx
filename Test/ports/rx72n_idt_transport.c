/* SPDX-License-Identifier: MIT
 * RX72N Ethernet port for the upstream transport integration tests.
 * Built only by tools/build_rx72n_idt_transport.ps1. This does not adapt MQTT
 * qualification tests or claim IDT support for the 202604.00-LTS manifest.
 */
#include <stdint.h>
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "test_execution_config.h"
#include "test_param_config.h"
#include "platform_function.h"
#include "transport_interface_test.h"
#include "transport_mbedtls_pkcs11.h"
#include "core_pkcs11_config.h"
#include "core_pkcs11_config_defaults.h"
#include "store.h"
#include "rx72n_idt_transport.h"

#if ( TRANSPORT_INTERFACE_TEST_ENABLED != 1 ) || \
    ( MQTT_TEST_ENABLED == 1 ) || ( CORE_PKCS11_TEST_ENABLED == 1 ) || \
    ( DEVICE_ADVISOR_TEST_ENABLED == 1 ) || ( OTA_PAL_TEST_ENABLED == 1 ) || \
    ( OTA_E2E_TEST_ENABLED == 1 )
    #error "This build supports only the IDT TLS transport test group."
#endif

/* Preserve the 8192-word stack and 1000 ms socket timeout of the existing
 * Test/integration_test.c port while giving every connection its own state. */
#define IDT_TASK_STACK_WORDS       ( 8192U )
#define IDT_SOCKET_TIMEOUT_MS      ( 1000U )
#define IDT_START_DELAY_MS         ( 5000U )

struct NetworkContext
{
    TlsTransportParams_t * pParams;
};

static TlsTransportParams_t xTlsParameters[ 2 ];
static NetworkContext_t xNetworkContexts[ 2 ];
static NetworkCredentials_t xCredentials;
static TransportInterface_t xTransport;

static NetworkConnectStatus_t prvConnect( void * context,
                                         TestHostInfo_t * host,
                                         void * credentials )
{
    TlsTransportStatus_t status;

    if( ( context == NULL ) || ( host == NULL ) ||
        ( host->pHostName == NULL ) || ( credentials == NULL ) )
    {
        return NETWORK_CONNECT_INVALID_PARAMETER;
    }

    status = TLS_FreeRTOS_Connect( context, host->pHostName, host->port,
                                  credentials, IDT_SOCKET_TIMEOUT_MS,
                                  IDT_SOCKET_TIMEOUT_MS );
    /* A failed connection is a test result, not an assertion/reset. */
    switch( status )
    {
        case TLS_TRANSPORT_SUCCESS: return NETWORK_CONNECT_SUCCESS;
        case TLS_TRANSPORT_INVALID_PARAMETER: return NETWORK_CONNECT_INVALID_PARAMETER;
        case TLS_TRANSPORT_INSUFFICIENT_MEMORY: return NETWORK_CONNECT_INSUFFICIENT_MEMORY;
        case TLS_TRANSPORT_INVALID_CREDENTIALS: return NETWORK_CONNECT_INVALID_CREDENTIALS;
        case TLS_TRANSPORT_HANDSHAKE_FAILED: return NETWORK_CONNECT_HANDSHAKE_FAILED;
        case TLS_TRANSPORT_CONNECT_FAILURE: return NETWORK_CONNECT_FAILURE;
        default: return NETWORK_CONNECT_INTERNAL_ERROR;
    }
}

static void prvDisconnect( void * context )
{
    TLS_FreeRTOS_Disconnect( context );
}

void SetupTransportTestParam( TransportTestParam_t * parameters )
{
    memset( xTlsParameters, 0, sizeof( xTlsParameters ) );
    memset( &xCredentials, 0, sizeof( xCredentials ) );
    memset( &xTransport, 0, sizeof( xTransport ) );
    xNetworkContexts[ 0 ].pParams = &xTlsParameters[ 0 ];
    xNetworkContexts[ 1 ].pParams = &xTlsParameters[ 1 ];

    /* Exercise the production send/recv functions without wrapping results. */
    xTransport.send = TLS_FreeRTOS_send;
    xTransport.recv = TLS_FreeRTOS_recv;
    xTransport.writev = NULL;
    xCredentials.pRootCa = ( const unsigned char * ) ECHO_SERVER_ROOT_CA;
    xCredentials.rootCaSize = sizeof( ECHO_SERVER_ROOT_CA );
    xCredentials.pClientCertLabel = pkcs11configLABEL_DEVICE_CERTIFICATE_FOR_TLS;
    xCredentials.pPrivateKeyLabel = pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS;
    /* Same local-echo-server mode as Test/integration_test.c. */
    xCredentials.disableSni = pdTRUE;

    parameters->pTransport = &xTransport;
    parameters->pNetworkContext = &xNetworkContexts[ 0 ];
    parameters->pSecondNetworkContext = &xNetworkContexts[ 1 ];
    parameters->pNetworkConnect = prvConnect;
    parameters->pNetworkDisconnect = prvDisconnect;
    parameters->pNetworkCredentials = &xCredentials;
}

static BaseType_t prvProvisionEchoCredentials( void )
{
    const char * certificate = TRANSPORT_CLIENT_CERTIFICATE;
    const char * privateKey = TRANSPORT_CLIENT_PRIVATE_KEY;

    if( ( certificate == NULL ) || ( privateKey == NULL ) )
    {
        return pdFALSE;
    }
    /* Import only IDT's disposable echo-client credentials using the normal
     * KVS/PKCS11 path. Values must never be written to the UART log. */
    if( ( xprvWriteCacheEntry( strlen( "cert" ), "cert", strlen( certificate ),
                              ( char * ) certificate ) < 0 ) ||
        ( xprvWriteCacheEntry( strlen( "key" ), "key", strlen( privateKey ),
                              ( char * ) privateKey ) < 0 ) )
    {
        return pdFALSE;
    }
    return KVStore_xCommitChanges();
}

static void prvRunTransportTests( void * unused )
{
    int failures;
    ( void ) unused;

    if( prvProvisionEchoCredentials() != pdTRUE )
    {
        configPRINT_STRING( "IDT transport credential provisioning failed\r\n" );
        vTaskDelete( NULL );
        return;
    }
    FRTest_TimeDelay( IDT_START_DELAY_MS );
    failures = RunTransportInterfaceTest();
    configPRINTF( ( "IDT transport result: %d failures\r\n", failures ) );
    vTaskDelete( NULL );
}

BaseType_t xStartIdtTransportTest( void )
{
    return xTaskCreate( prvRunTransportTests, "IDT transport",
                        IDT_TASK_STACK_WORDS, NULL, tskIDLE_PRIORITY + 1, NULL );
}

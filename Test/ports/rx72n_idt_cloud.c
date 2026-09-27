/* SPDX-License-Identifier: MIT
 * Provision IDT's temporary parameters for the unchanged production MQTT
 * agent, SimplePubSub and (when selected) OTA tasks. Cloud-side IDT/Device
 * Advisor determines results; this file never emits a local PASS.
 */
#include <string.h>
#include "FreeRTOS.h"
#include "test_execution_config.h"
#include "test_param_config.h"
#include "demo_config.h"
#include "store.h"
#include "rx72n_idt_cloud.h"

#if ( ( DEVICE_ADVISOR_TEST_ENABLED + OTA_E2E_TEST_ENABLED ) != 1 ) || \
    ( TRANSPORT_INTERFACE_TEST_ENABLED == 1 ) || ( MQTT_TEST_ENABLED == 1 ) || \
    ( CORE_PKCS11_TEST_ENABLED == 1 ) || ( OTA_PAL_TEST_ENABLED == 1 )
    #error "Select exactly one cloud demo: Device Advisor or OTA E2E."
#endif

#if ( OTA_E2E_TEST_ENABLED == 1 )
    #include "idt_ota_signer.h"
#endif

static BaseType_t prvWriteIdtValue( char * key, const char * value )
{
    if( ( value == NULL ) || ( value[ 0 ] == '\0' ) )
    {
        return pdFALSE;
    }
    return ( xprvWriteCacheEntry( strlen( key ), key, strlen( value ),
                                  ( char * ) value ) < 0 ) ? pdFALSE : pdTRUE;
}

BaseType_t xProvisionIdtCloudCredentials( void )
{
    /* The production agent reads these entries from KVS, including the host
     * used for SNI. Never print credential values or use transport-echo mode. */
    if( ( prvWriteIdtValue( "thingname", IOT_THING_NAME ) != pdTRUE ) ||
        ( prvWriteIdtValue( "endpoint", MQTT_SERVER_ENDPOINT ) != pdTRUE ) ||
        ( prvWriteIdtValue( "cert", MQTT_CLIENT_CERTIFICATE ) != pdTRUE ) ||
        ( prvWriteIdtValue( "key", MQTT_CLIENT_PRIVATE_KEY ) != pdTRUE ) ||
        /* Device Advisor uses the Amazon Root CA 1 chain. The legacy demo
         * default is Starfield Class 2, which does not anchor that chain. */
        ( prvWriteIdtValue( "rootca", tlsATS1_ROOT_CERTIFICATE_PEM ) != pdTRUE ) )
    {
        return pdFALSE;
    }
#if ( OTA_E2E_TEST_ENABLED == 1 )
    if( prvWriteIdtValue( "codesigncert", IDT_OTA_SIGNER_CERTIFICATE ) != pdTRUE )
    {
        return pdFALSE;
    }
#endif
    return KVStore_xCommitChanges();
}

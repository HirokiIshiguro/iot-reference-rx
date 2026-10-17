/* SPDX-License-Identifier: MIT
 * IDT network parameters enter the production KVS and typed PDN paths. This file is
 * linked only for RX65N/BG96 and RX671/Type 1YN network test profiles.
 */
#include <string.h>
#include "FreeRTOS.h"
#include "rx_idt_config.h"
#include "rx_idt_network.h"
#include "idt_network_config.h"
#include "store.h"

#if ( IDT_TEST_ENABLED != 1 ) || \
    ( ( ENABLE_IDT_TRANSPORT_TEST + ENABLE_IDT_CLOUD_DEMO ) != 1 )
    #error "Network provisioning requires a selected IDT network profile."
#endif

#if ( IDT_TARGET_RX65N_BG96 == 1 )
    #include "bg96_network.h"
    #if !defined( IDT_CELLULAR_APN ) || !defined( IDT_CELLULAR_APN_USER ) || \
        !defined( IDT_CELLULAR_APN_PASSWORD ) || !defined( IDT_CELLULAR_APN_AUTH )
        #error "The runtime header must supply all four cellular parameters."
    #endif
#elif ( IDT_TARGET_RX671_WIFI == 1 )
    #if !defined( IDT_WIFI_SSID ) || !defined( IDT_WIFI_PASSPHRASE )
        #error "The runtime header must supply the Wi-Fi parameters."
    #endif
    #if ( RX671_WIFI_CREDENTIAL_KVS_ENABLE != 1 )
        #error "IDT Wi-Fi startup requires the production Wi-Fi credential KVS."
    #endif
#else
    #error "This network port supports only BG96 and Type 1YN targets."
#endif

static BaseType_t prvWriteNetworkValue( char * key, const char * value )
{
    size_t length = strlen( value );

    /* Explicit empty cellular user/password values clear stale credentials.
     * KVS represents those as a one-byte NUL string; Wi-Fi values are nonempty. */
    if( length == 0U )
    {
        length = 1U;
    }
    return ( xprvWriteCacheEntry( strlen( key ), key, length,
                                  ( char * ) value ) < 0 ) ? pdFALSE : pdTRUE;
}

BaseType_t xProvisionIdtNetworkCredentials( void )
{
#if ( IDT_TARGET_RX65N_BG96 == 1 )
    CellularPdnConfig_t pdn = { 0 };

    if( ( Bg96_GetHandle() != NULL ) ||
        ( strlen( IDT_CELLULAR_APN ) == 0U ) ||
        ( strlen( IDT_CELLULAR_APN ) >= sizeof( pdn.apnName ) ) ||
        ( strlen( IDT_CELLULAR_APN_USER ) >= sizeof( pdn.username ) ) ||
        ( strlen( IDT_CELLULAR_APN_PASSWORD ) >= sizeof( pdn.password ) ) ||
        ( strlen( IDT_CELLULAR_APN_AUTH ) != 1U ) ||
        ( IDT_CELLULAR_APN_AUTH[ 0 ] < '0' ) || ( IDT_CELLULAR_APN_AUTH[ 0 ] > '2' ) )
    {
        return pdFALSE;
    }
    pdn.pdnContextType = CELLULAR_PDN_CONTEXT_IPV4;
    switch( IDT_CELLULAR_APN_AUTH[ 0 ] )
    {
        case '0': pdn.pdnAuthType = CELLULAR_PDN_AUTH_NONE; break;
        case '1': pdn.pdnAuthType = CELLULAR_PDN_AUTH_PAP; break;
        default: pdn.pdnAuthType = CELLULAR_PDN_AUTH_CHAP; break;
    }
    strcpy( pdn.apnName, IDT_CELLULAR_APN );
    strcpy( pdn.username, IDT_CELLULAR_APN_USER );
    strcpy( pdn.password, IDT_CELLULAR_APN_PASSWORD );
    if( ( prvWriteNetworkValue( "apn", IDT_CELLULAR_APN ) != pdTRUE ) ||
        ( prvWriteNetworkValue( "apnuser", IDT_CELLULAR_APN_USER ) != pdTRUE ) ||
        ( prvWriteNetworkValue( "apnpass", IDT_CELLULAR_APN_PASSWORD ) != pdTRUE ) ||
        ( prvWriteNetworkValue( "apnauth", IDT_CELLULAR_APN_AUTH ) != pdTRUE ) )
#else
    if( ( strlen( IDT_WIFI_SSID ) == 0U ) || ( strlen( IDT_WIFI_SSID ) > 32U ) ||
        ( strlen( IDT_WIFI_PASSPHRASE ) < 8U ) ||
        ( strlen( IDT_WIFI_PASSPHRASE ) > 63U ) )
    {
        return pdFALSE;
    }
    if( ( prvWriteNetworkValue( "wifissid", IDT_WIFI_SSID ) != pdTRUE ) ||
        ( prvWriteNetworkValue( "wifipass", IDT_WIFI_PASSPHRASE ) != pdTRUE ) )
#endif
    {
        return pdFALSE;
    }
    if( KVStore_xCommitChanges() != pdTRUE )
    {
        return pdFALSE;
    }
#if ( IDT_TARGET_RX65N_BG96 == 1 )
    /* Install only a successfully committed profile. Connect2AP() uses this
     * copied public CellularPdnConfig_t instead of ignoring native inputs. */
    return Bg96_SetRuntimePdnConfig( &pdn ) ? pdTRUE : pdFALSE;
#else
    return pdTRUE;
#endif
}

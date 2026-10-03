/* SPDX-License-Identifier: MIT
 * Shared firmware profile guards. Historical rx72n_idt_* entry points are kept
 * so the RX72N builder and existing project startup remain compatible.
 */
#ifndef RX_IDT_CONFIG_H
#define RX_IDT_CONFIG_H

#include "platform.h"

#ifndef ENABLE_IDT_TRANSPORT_TEST
    #define ENABLE_IDT_TRANSPORT_TEST 0
#endif
#ifndef ENABLE_IDT_CLOUD_DEMO
    #define ENABLE_IDT_CLOUD_DEMO 0
#endif
#ifndef ENABLE_IDT_PKCS11_TEST
    #define ENABLE_IDT_PKCS11_TEST 0
#endif
#ifndef ENABLE_IDT_OTAPAL_TEST
    #define ENABLE_IDT_OTAPAL_TEST 0
#endif

#define IDT_TEST_ENABLED ( ENABLE_IDT_TRANSPORT_TEST + ENABLE_IDT_CLOUD_DEMO + \
                           ENABLE_IDT_PKCS11_TEST + ENABLE_IDT_OTAPAL_TEST )

#if ( ENABLE_IDT_TRANSPORT_TEST < 0 ) || ( ENABLE_IDT_TRANSPORT_TEST > 1 ) || \
    ( ENABLE_IDT_CLOUD_DEMO < 0 ) || ( ENABLE_IDT_CLOUD_DEMO > 1 ) || \
    ( ENABLE_IDT_PKCS11_TEST < 0 ) || ( ENABLE_IDT_PKCS11_TEST > 1 ) || \
    ( ENABLE_IDT_OTAPAL_TEST < 0 ) || ( ENABLE_IDT_OTAPAL_TEST > 1 ) || \
    ( IDT_TEST_ENABLED > 1 )
    #error "Select exactly one IDT firmware startup profile."
#endif

/* The original RX72N wrapper did not provide a target selector. Only that
 * board may use this compatibility default; new boards require an explicit
 * selector so a copied project cannot silently exercise a different MCU. */
#if !defined( IDT_TARGET_RX72N_ETHERNET ) && !defined( IDT_TARGET_RX65N_BG96 ) && \
    !defined( IDT_TARGET_RX671_WIFI ) && defined( BSP_MCU_RX72N )
    #define IDT_TARGET_RX72N_ETHERNET 1
#endif
#ifndef IDT_TARGET_RX72N_ETHERNET
    #define IDT_TARGET_RX72N_ETHERNET 0
#endif
#ifndef IDT_TARGET_RX65N_BG96
    #define IDT_TARGET_RX65N_BG96 0
#endif
#ifndef IDT_TARGET_RX671_WIFI
    #define IDT_TARGET_RX671_WIFI 0
#endif

#if ( IDT_TEST_ENABLED == 1 )
    #if ( IDT_TARGET_RX72N_ETHERNET < 0 ) || ( IDT_TARGET_RX72N_ETHERNET > 1 ) || \
        ( IDT_TARGET_RX65N_BG96 < 0 ) || ( IDT_TARGET_RX65N_BG96 > 1 ) || \
        ( IDT_TARGET_RX671_WIFI < 0 ) || ( IDT_TARGET_RX671_WIFI > 1 ) || \
        ( ( IDT_TARGET_RX72N_ETHERNET + IDT_TARGET_RX65N_BG96 + IDT_TARGET_RX671_WIFI ) != 1 )
        #error "Select exactly one supported IDT target."
    #endif
    #if ( IDT_TARGET_RX72N_ETHERNET == 1 ) && ( BSP_MCU_RX72N != 1 )
        #error "The Ethernet IDT target requires RX72N."
    #endif
    #if ( IDT_TARGET_RX65N_BG96 == 1 ) && ( BSP_MCU_RX65N != 1 )
        #error "The BG96 IDT target requires RX65N."
    #endif
    #if ( IDT_TARGET_RX671_WIFI == 1 ) && ( BSP_MCU_RX671 != 1 )
        #error "The Type 1YN IDT target requires RX671."
    #endif
#endif

#endif /* RX_IDT_CONFIG_H */

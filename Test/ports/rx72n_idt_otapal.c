/* SPDX-License-Identifier: MIT
 * Run the existing OTA PAL assertions against real RX inactive-bank flash.
 * No activation, bank swap or reset is requested by this test port. The host
 * must retain the board lock and reset/hold the MCU after the test run.
 */
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "platform.h"
#include "rx_idt_config.h"
#include "r_fwup_config.h"
#include "test_execution_config.h"
#include "test_param_config.h"
#include "ota_pal_test.h"
#include "MQTTFileDownloader_config.h"
#include "aws_test_ota_pal_ecdsa_sha256_signature.h"
#include "platform_function.h"
#include "store.h"
#include "rx72n_idt_otapal.h"

#if ( OTA_PAL_TEST_ENABLED != 1 ) || ( CORE_PKCS11_TEST_ENABLED == 1 ) || \
    ( TRANSPORT_INTERFACE_TEST_ENABLED == 1 ) || ( MQTT_TEST_ENABLED == 1 ) || \
    ( DEVICE_ADVISOR_TEST_ENABLED == 1 ) || ( OTA_E2E_TEST_ENABLED == 1 )
    #error "The OTA PAL build must select only OTA_PAL_TEST_ENABLED."
#endif
#if ( OTA_PAL_TEST_CERT_TYPE != OTA_ECDSA_SHA256 ) || ( OTA_PAL_USE_FILE_SYSTEM != 0 )
    #error "This RX PAL profile requires ECDSA-SHA256 and the direct-flash PAL."
#endif
#if ( FWUP_CFG_UPDATE_MODE != 0 ) || ( FWUP_CFG_FUNCTION_MODE != 1 ) || \
    ( FWUP_CFG_SIGNATURE_VERIFICATION != 0 ) || ( BSP_CFG_CODE_FLASH_BANK_MODE != 0 )
    #error "OTA PAL tests require the production ECDSA application dual-bank profile."
#endif
#if ( IDT_TARGET_RX72N_ETHERNET == 1 )
    #if ( FWUP_CFG_MAIN_AREA_ADDR_L != 0xFFE00000U ) || \
        ( FWUP_CFG_BUF_AREA_ADDR_L != 0xFFC00000U ) || ( FWUP_CFG_AREA_SIZE != 0x1C0000U )
        #error "OTA PAL tests require the reviewed RX72N inactive-bank layout."
    #endif
    #define IDT_PAL_INACTIVE_REGION "FFC00000-FFDBFFFF"
#elif ( IDT_TARGET_RX65N_BG96 == 1 )
    #if ( FWUP_CFG_MAIN_AREA_ADDR_L != 0xFFF00000U ) || \
        ( FWUP_CFG_BUF_AREA_ADDR_L != 0xFFE00000U ) || ( FWUP_CFG_AREA_SIZE != 0xF0000U )
        #error "OTA PAL tests require the reviewed RX65N inactive-bank layout."
    #endif
    #define IDT_PAL_INACTIVE_REGION "FFE00000-FFEEFFFF"
#elif ( IDT_TARGET_RX671_WIFI == 1 )
    #if ( FWUP_CFG_MAIN_AREA_ADDR_L != 0xFFF00000U ) || \
        ( FWUP_CFG_BUF_AREA_ADDR_L != 0xFFE00000U ) || ( FWUP_CFG_AREA_SIZE != 0xC0000U )
        #error "OTA PAL tests require the reviewed RX671 768-KiB OTA inactive-bank profile."
    #endif
    #define IDT_PAL_INACTIVE_REGION "FFE00000-FFEBFFFF"
#else
    #error "Unsupported IDT OTA PAL target."
#endif

void SetupOtaPalTestParam( OtaPalTestParam_t * parameters )
{
    /* Existing port contract: the 384-byte fixture fits within a transfer
     * page, and ten spaced writes remain inside the inactive image area. */
    parameters->pageSize = mqttFileDownloader_CONFIG_BLOCK_SIZE;
}

static void prvRunOtaPalTests( void * unused )
{
    const char * signer = OTA_PAL_CODE_SIGNING_CERTIFICATE;
    int failures;
    ( void ) unused;

    /* Use the certificate in the same header as ucValidSignature. The older
     * certificate under test_files does not verify this RX fixture. The
     * fixture/signature are unchanged on every target. */
    if( ( xprvWriteCacheEntry( strlen( "codesigncert" ), "codesigncert",
                              strlen( signer ), ( char * ) signer ) < 0 ) ||
        ( KVStore_xCommitChanges() != pdTRUE ) )
    {
        configPRINT_STRING( "IDT_PORT_FATAL: OTA PAL signer provisioning failed\r\n" );
        for( ;; )
        {
            vTaskSuspend( NULL );
        }
    }
    configPRINT_STRING( "IDT OTA PAL: inactive flash " IDT_PAL_INACTIVE_REGION "; no activation/reset\r\n" );
    configPRINT_STRING( "IDT OTA PAL coverage: 15 nominal, 14 assertion-capable, 1 filesystem-only not applicable\r\n" );
    FRTest_TimeDelay( 5000U );
    failures = RunOtaPalTest();
    configPRINTF( ( "IDT OTA PAL result: %d failures; host reset-hold required\r\n", failures ) );
    vTaskDelete( NULL );
}

BaseType_t xStartIdtOtaPalTest( void )
{
    return xTaskCreate( prvRunOtaPalTests, "IDT OTA PAL", 8192U, NULL,
                        tskIDLE_PRIORITY + 1, NULL );
}

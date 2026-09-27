/* SPDX-License-Identifier: MIT
 * Run the unchanged upstream PKCS11 tests against the software implementation
 * and the existing production provisioning helpers. Test keys are disposable.
 */
#include "FreeRTOS.h"
#include "task.h"
#include "test_execution_config.h"
#include "test_param_config.h"
#include "core_pkcs11_test.h"
#include "platform_function.h"
#include "rx72n_idt_pkcs11.h"

#if ( CORE_PKCS11_TEST_ENABLED != 1 ) || \
    ( TRANSPORT_INTERFACE_TEST_ENABLED == 1 ) || ( MQTT_TEST_ENABLED == 1 ) || \
    ( DEVICE_ADVISOR_TEST_ENABLED == 1 ) || ( OTA_PAL_TEST_ENABLED == 1 ) || \
    ( OTA_E2E_TEST_ENABLED == 1 )
    #error "The PKCS11 test build must select only CORE_PKCS11_TEST_ENABLED."
#endif

#if ( PKCS11_TEST_RSA_KEY_SUPPORT != 0 ) || ( PKCS11_TEST_EC_KEY_SUPPORT != 1 ) || \
    ( PKCS11_TEST_IMPORT_PRIVATE_KEY_SUPPORT != 1 ) || \
    ( PKCS11_TEST_GENERATE_KEYPAIR_SUPPORT != 0 ) || \
    ( PKCS11_TEST_PREPROVISIONED_SUPPORT != 0 )
    #error "This IDT profile is EC with KeyProvisioningImport."
#endif

static void prvRunPkcs11Tests( void * unused )
{
    int failures;
    ( void ) unused;
    FRTest_TimeDelay( 5000U );
    failures = RunPkcs11Test();
    configPRINTF( ( "IDT PKCS11 result: %d failures\r\n", failures ) );
    vTaskDelete( NULL );
}

BaseType_t xStartIdtPkcs11Test( void )
{
    return xTaskCreate( prvRunPkcs11Tests, "IDT PKCS11", 8192U, NULL,
                        tskIDLE_PRIORITY + 1, NULL );
}

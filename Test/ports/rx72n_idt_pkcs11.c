/* SPDX-License-Identifier: MIT
 * Run the unchanged upstream PKCS11 tests against the software implementation
 * and the existing production provisioning helpers. Test keys are disposable.
 */
#include "FreeRTOS.h"
#include "task.h"
#include "rx_idt_config.h"
#include "test_execution_config.h"
#include "test_param_config.h"
#include "unity_fixture.h"
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

/* The build callback selects a public group entry without editing its body.
 * StartFinish includes Capabilities, matching native FullPKCS11_Core's first
 * execution (six assertions); NoObject is its second (five assertions,
 * including Capabilities again). The two executions cover ten distinct cases.
 * Routing the SDK's request to this definition is checked separately.
 */
#ifndef RX_IDT_PKCS11_SELECTED_GROUP
    #error "Explicit product PKCS11 group selection is required."
#elif ( RX_IDT_PKCS11_SELECTED_GROUP != 1 ) && ( RX_IDT_PKCS11_SELECTED_GROUP != 2 )
    #error "This Core profile supports StartFinish (1) or NoObject (2) only."
#endif

static int prvRunSelectedPkcs11Group( void )
{
    UnityFixture.Verbose = 1;
    UnityFixture.Silent = 0;
    UnityFixture.GroupFilter = NULL;
    UnityFixture.NameFilter = NULL;
    UnityFixture.RepeatCount = 1;
    UNITY_BEGIN();
#if ( RX_IDT_PKCS11_SELECTED_GROUP == 1 )
    RUN_TEST_GROUP( Full_PKCS11_StartFinish );
    RUN_TEST_GROUP( Full_PKCS11_Capabilities );
#elif ( RX_IDT_PKCS11_SELECTED_GROUP == 2 )
    RUN_TEST_GROUP( Full_PKCS11_Capabilities );
    RUN_TEST_GROUP( Full_PKCS11_NoObject );
#endif
    return UNITY_END();
}

static void prvRunPkcs11Tests( void * unused )
{
    int failures;
    ( void ) unused;
    FRTest_TimeDelay( 5000U );
    failures = prvRunSelectedPkcs11Group();
    configPRINTF( ( "IDT PKCS11 result: %d failures\r\n", failures ) );
    vTaskDelete( NULL );
}

BaseType_t xStartIdtPkcs11Test( void )
{
    return xTaskCreate( prvRunPkcs11Tests, "IDT PKCS11", 8192U, NULL,
                        tskIDLE_PRIORITY + 1, NULL );
}

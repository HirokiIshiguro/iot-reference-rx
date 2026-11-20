/*
 * EK-RX671 + Type 1YN bootstrap for the existing Fleet Provisioning demo.
 *
 * The claim credentials are compiled from an ignored local header for the
 * focused CI image, then imported into the existing LittleFS/corePKCS11 PAL at
 * boot.  No credential contents are printed by this module.
 */
#include <stddef.h>
#include <string.h>

#include "FreeRTOS.h"
#include "task.h"
#include "lfs.h"

#include "debug_uart.h"
#include "lfs_common_data.h"
#include "mqtt_agent_task.h"
#include "rx671_fleet_bootstrap.h"
#include "rx671_fleet_config.h"
#include "store.h"

#define RX671_FLEET_BOOTSTRAP_STACK_WORDS    (6144U)
#define RX671_FLEET_BOOTSTRAP_PRIORITY       (tskIDLE_PRIORITY + 2U)
#define RX671_FLEET_NETWORK_WAIT_TICKS       pdMS_TO_TICKS(100U)

extern volatile uint32_t g_freertos_tcp_network_up;
extern void vStartFleetProvisioningDemo(void);

#if (RX671_FLEET_PROVISIONING_ENABLE == 1)

static BaseType_t fleet_write_cache_entry(const char * p_key,
                                          const char * p_value)
{
    int32_t result;

    result = xprvWriteCacheEntry(strlen(p_key),
                                 (char *)p_key,
                                 strlen(p_value),
                                 (char *)p_value);

    return (result >= 0) ? pdTRUE : pdFALSE;
}

static BaseType_t fleet_config_is_complete(void)
{
    return ((RX671_FLEET_ENDPOINT[0] != '\0') &&
            (RX671_FLEET_TEMPLATE_NAME[0] != '\0') &&
            (RX671_FLEET_CLAIM_CERTIFICATE_PEM[0] != '\0') &&
            (RX671_FLEET_CLAIM_PRIVATE_KEY_PEM[0] != '\0')) ? pdTRUE : pdFALSE;
}

static BaseType_t fleet_provision_claim_credentials(void)
{
    BaseType_t result = pdTRUE;

    if (pdTRUE == result)
    {
        result = fleet_write_cache_entry("endpoint", RX671_FLEET_ENDPOINT);
    }
    if (pdTRUE == result)
    {
        result = fleet_write_cache_entry("template", RX671_FLEET_TEMPLATE_NAME);
    }
    if (pdTRUE == result)
    {
        result = fleet_write_cache_entry("claimcert", RX671_FLEET_CLAIM_CERTIFICATE_PEM);
    }
    if (pdTRUE == result)
    {
        result = fleet_write_cache_entry("claimkey", RX671_FLEET_CLAIM_PRIVATE_KEY_PEM);
    }
    if (pdTRUE == result)
    {
        result = KVStore_xCommitChanges();
    }

    return result;
}

static void fleet_bootstrap_task(void * p_parameters)
{
    int32_t littlefs_result;
    int32_t cache_result;

    (void)p_parameters;

    while (0U == g_freertos_tcp_network_up)
    {
        vTaskDelay(RX671_FLEET_NETWORK_WAIT_TICKS);
    }
    debug_puts("RX671 Fleet: network ready\r\n");

    if (pdTRUE != fleet_config_is_complete())
    {
        debug_puts("RX671 Fleet: local configuration missing\r\n");
        vTaskDelete(NULL);
        return;
    }

    littlefs_result = littlFs_init();
    if (LFS_ERR_OK != littlefs_result)
    {
        debug_puts("RX671 Fleet: LittleFS init NG\r\n");
        vTaskDelete(NULL);
        return;
    }
    debug_puts("RX671 Fleet: LittleFS init OK\r\n");

    cache_result = vprvCacheInit();
    if (LFS_ERR_OK != cache_result)
    {
        debug_puts("RX671 Fleet: KVS cache init NG\r\n");
        vTaskDelete(NULL);
        return;
    }

    if (pdTRUE != fleet_provision_claim_credentials())
    {
        debug_puts("RX671 Fleet: claim provisioning NG\r\n");
        vTaskDelete(NULL);
        return;
    }
    debug_puts("RX671 Fleet: claim provisioning OK\r\n");

    if (pdPASS != xMQTTAgentInit())
    {
        debug_puts("RX671 Fleet: MQTT helper init NG\r\n");
        vTaskDelete(NULL);
        return;
    }

    debug_puts("RX671 Fleet: starting demo\r\n");
    vStartFleetProvisioningDemo();
    vTaskDelete(NULL);
}

#endif /* RX671_FLEET_PROVISIONING_ENABLE == 1 */

void rx671_fleet_bootstrap_start(void)
{
#if (RX671_FLEET_PROVISIONING_ENABLE == 1)
    BaseType_t result;

    result = xTaskCreate(fleet_bootstrap_task,
                         "RX671FLEET",
                         RX671_FLEET_BOOTSTRAP_STACK_WORDS,
                         NULL,
                         RX671_FLEET_BOOTSTRAP_PRIORITY,
                         NULL);
    debug_puts((pdPASS == result) ?
               "RX671 Fleet bootstrap task OK\r\n" :
               "RX671 Fleet bootstrap task NG\r\n");
#endif
}

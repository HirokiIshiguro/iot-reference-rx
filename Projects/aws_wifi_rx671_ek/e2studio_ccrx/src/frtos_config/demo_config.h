#ifndef DEMO_CONFIG_H
#define DEMO_CONFIG_H

#include "FreeRTOS.h"
#include "event_groups.h"
#include "aws_iot_config.h"
#include "rx671_fleet_config.h"
#include "core_mqtt.h"
#include "iot_default_root_certificates.h"
#include "logging_levels.h"

#ifndef LIBRARY_LOG_NAME
#define LIBRARY_LOG_NAME    "MQTTDemo"
#endif

#ifndef LIBRARY_LOG_LEVEL
#define LIBRARY_LOG_LEVEL   LOG_INFO
#endif

#include "iot_logging_task.h"
#include "logging_stack.h"

#define ENABLE_FLEET_PROVISIONING_DEMO      RX671_FLEET_PROVISIONING_ENABLE
#define ENABLE_OTA_UPDATE_DEMO              (0)
#define democonfigUSE_AWS_IOT_CORE_BROKER   (1)
#define democonfigDISABLE_SNI               (0)

#define democonfigFP_DEMO_ID                "RX671Type1YN"
#define democonfigCLIENT_IDENTIFIER         AWS_IOT_THING_NAME
#if (RX671_FLEET_PROVISIONING_ENABLE == 1)
#define democonfigMQTT_BROKER_ENDPOINT      RX671_FLEET_ENDPOINT
#define democonfigPROVISIONING_TEMPLATE_NAME RX671_FLEET_TEMPLATE_NAME
/*
 * The Fleet demo performs CSR generation and TLS operations from its task.
 * Keep enough stack for the crypto call chain instead of using the small
 * generic demo default (configMINIMAL_STACK_SIZE * 3).
 */
#define democonfigFLEET_PROVISIONING_DEMO_STACKSIZE (6144U)
#else
#define democonfigMQTT_BROKER_ENDPOINT      AWS_IOT_ENDPOINT
#define democonfigPROVISIONING_TEMPLATE_NAME "...insert here..."
#endif
#define democonfigMQTT_BROKER_PORT          (AWS_IOT_MQTT_PORT)
#define democonfigCSR_SUBJECT_NAME          "CN=" democonfigFP_DEMO_ID

#define democonfigDEMO_STACKSIZE            (configMINIMAL_STACK_SIZE * 3)
#define democonfigDEMO_TASK_PRIORITY        (tskIDLE_PRIORITY + 1)
#define democonfigNETWORK_BUFFER_SIZE       (configMINIMAL_STACK_SIZE * 3)

#define democonfigMQTT_LIB                  "core-mqtt@" MQTT_LIBRARY_VERSION
#define AWS_IOT_MQTT_ALPN                   "\x0ex-amzn-mqtt-ca"
#define AWS_IOT_CUSTOM_AUTH_ALPN            "\x04mqtt"
#define democonfigOS_NAME                   "FreeRTOS"
#define democonfigOS_VERSION                "V11.1.0"
#define democonfigHARDWARE_PLATFORM_NAME    "EK-RX671 Type 1YN"
#define AWS_IOT_METRICS_STRING              "?SDK=" democonfigOS_NAME "&Version=" democonfigOS_VERSION "&MQTTLib=" democonfigMQTT_LIB
#define AWS_IOT_METRICS_STRING_LENGTH       ((uint16_t)(sizeof(AWS_IOT_METRICS_STRING) - 1))

#define appmainPROVISIONING_MODE            (0)
#define otapalconfigCODE_SIGNING_CERTIFICATE "Insert code signing certificate..."
#define APP_VERSION_MAJOR                   (0)
#define APP_VERSION_MINOR                   (1)
#define APP_VERSION_BUILD                   (0)

#define democonfigROOT_CA_PEM               tlsATS1_ROOT_CERTIFICATE_PEM
#define MQTT_AGENT_COMMAND_QUEUE_LENGTH     (25)
#define MQTT_AGENT_NETWORK_BUFFER_SIZE      (32768)
#define MQTT_COMMAND_CONTEXTS_POOL_SIZE     (10)
#define ENABLE_CREDENTIAL_BY_CLI            (0)
#define SELF_TEST_PASSED                    ((EventBits_t)(1U))

#endif /* DEMO_CONFIG_H */

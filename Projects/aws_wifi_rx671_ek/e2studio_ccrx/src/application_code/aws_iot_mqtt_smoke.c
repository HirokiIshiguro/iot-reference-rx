/*
 * Minimal AWS IoT MQTT smoke test for EK-RX671 + Murata Type 1YN.
 *
 * SPDX-License-Identifier: MIT
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h"
#include "task.h"

#include "core_mqtt.h"
#include "debug_uart.h"
#include "iot_default_root_certificates.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"
#include "mbedtls/pk.h"
#include "mbedtls/private_access.h"
#include "mbedtls/ssl.h"
#include "mbedtls/threading.h"
#include "mbedtls/x509_crt.h"
#include "mbedtls_bio_tcp_sockets_wrapper.h"
#include "tcp_sockets_wrapper.h"
#include "threading_alt.h"

#include "aws_iot_config.h"
#include "aws_iot_mqtt_smoke.h"

#define AWS_IOT_MQTT_TASK_STACK_WORDS       (4096U)
#define AWS_IOT_MQTT_TASK_PRIORITY          (tskIDLE_PRIORITY + 2U)
#define AWS_IOT_MQTT_WAIT_NETWORK_TICKS     pdMS_TO_TICKS(1000U)
#define AWS_IOT_MQTT_TCP_RECV_TIMEOUT_MS    (1000U)
#define AWS_IOT_MQTT_TCP_SEND_TIMEOUT_MS    (5000U)
#define AWS_IOT_MQTT_CONNACK_TIMEOUT_MS     (10000U)
#define AWS_IOT_MQTT_KEEP_ALIVE_SECONDS     (60U)
#define AWS_IOT_MQTT_NETWORK_BUFFER_BYTES   (2048U)
#define AWS_IOT_MQTT_ENTROPY_MIN_BYTES      (32U)

struct NetworkContext
{
    mbedtls_ssl_context * p_ssl_context;
};

typedef struct AwsIotMqttTlsContext
{
    Socket_t socket;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;
    mbedtls_x509_crt ca_cert;
    mbedtls_x509_crt client_cert;
    mbedtls_pk_context client_key;
    mbedtls_ssl_config ssl_config;
    mbedtls_ssl_context ssl_context;
} AwsIotMqttTlsContext_t;

extern volatile uint32_t g_freertos_tcp_network_up;
extern int mbedtls_hardware_poll(void * data,
                                 unsigned char * output,
                                 size_t len,
                                 size_t * olen);

volatile uint32_t g_aws_iot_mqtt_enable_seen;
volatile uint32_t g_aws_iot_mqtt_task_create_result;
volatile uint32_t g_aws_iot_mqtt_task_enter_count;
volatile uint32_t g_aws_iot_mqtt_wait_network_count;
volatile uint32_t g_aws_iot_mqtt_tcp_connect_status;
volatile uint32_t g_aws_iot_mqtt_tls_step;
volatile int32_t g_aws_iot_mqtt_mbedtls_status;
volatile uint32_t g_aws_iot_mqtt_mqtt_status;
volatile uint32_t g_aws_iot_mqtt_connect_session_present;
volatile uint32_t g_aws_iot_mqtt_publish_count;
volatile uint32_t g_aws_iot_mqtt_task_done_count;
volatile int32_t g_aws_iot_mqtt_entropy_add_status;
volatile uint32_t g_aws_iot_mqtt_entropy_source_count_after_init;
volatile uint32_t g_aws_iot_mqtt_entropy_source_count_after_add;
volatile uint32_t g_aws_iot_mqtt_stack_high_water_entry;
volatile uint32_t g_aws_iot_mqtt_stack_high_water_after_tls;
volatile uint32_t g_aws_iot_mqtt_threading_alt_set_count;

static uint8_t s_mqtt_network_buffer[AWS_IOT_MQTT_NETWORK_BUFFER_BYTES];
static AwsIotMqttTlsContext_t s_tls_context;
static bool s_mbedtls_threading_alt_is_set;

static void log_step_status(const char * label, int32_t status)
{
    char line[96];
    char * p = line;

    p = append_text(p, label);
    p = append_text(p, "=");
    if (status < 0)
    {
        p = append_text(p, "-");
        p = append_hex32(p, (uint32_t)(-status));
    }
    else
    {
        p = append_dec32(p, (uint32_t)status);
    }
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static uint32_t mqtt_get_time_ms(void)
{
    return (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
}

static void ensure_mbedtls_threading_alt(void)
{
    if (!s_mbedtls_threading_alt_is_set)
    {
        mbedtls_threading_set_alt(mbedtls_platform_mutex_init,
                                  mbedtls_platform_mutex_free,
                                  mbedtls_platform_mutex_lock,
                                  mbedtls_platform_mutex_unlock);
        s_mbedtls_threading_alt_is_set = true;
        g_aws_iot_mqtt_threading_alt_set_count++;
    }
}

static bool mqtt_event_callback(MQTTContext_t * p_context,
                                MQTTPacketInfo_t * p_packet_info,
                                MQTTDeserializedInfo_t * p_deserialized_info,
                                MQTTSuccessFailReasonCode_t * p_reason_code,
                                MQTTPropBuilder_t * p_send_props_buffer,
                                MQTTPropBuilder_t * p_get_props_buffer)
{
    (void)p_context;
    (void)p_packet_info;
    (void)p_deserialized_info;
    (void)p_reason_code;
    (void)p_send_props_buffer;
    (void)p_get_props_buffer;

    return true;
}

static int32_t tls_transport_send(NetworkContext_t * p_network_context,
                                  const void * p_buffer,
                                  size_t bytes_to_send)
{
    int ret;

    configASSERT(NULL != p_network_context);
    configASSERT(NULL != p_network_context->p_ssl_context);
    configASSERT(NULL != p_buffer);

    ret = mbedtls_ssl_write(p_network_context->p_ssl_context,
                            (const unsigned char *)p_buffer,
                            bytes_to_send);
    if ((MBEDTLS_ERR_SSL_WANT_READ == ret) || (MBEDTLS_ERR_SSL_WANT_WRITE == ret))
    {
        ret = 0;
    }

    return (int32_t)ret;
}

static int32_t tls_transport_recv(NetworkContext_t * p_network_context,
                                  void * p_buffer,
                                  size_t bytes_to_recv)
{
    int ret;

    configASSERT(NULL != p_network_context);
    configASSERT(NULL != p_network_context->p_ssl_context);
    configASSERT(NULL != p_buffer);

    ret = mbedtls_ssl_read(p_network_context->p_ssl_context,
                           (unsigned char *)p_buffer,
                           bytes_to_recv);
    if ((MBEDTLS_ERR_SSL_WANT_READ == ret) ||
        (MBEDTLS_ERR_SSL_WANT_WRITE == ret) ||
        (MBEDTLS_ERR_SSL_TIMEOUT == ret))
    {
        ret = 0;
    }

    return (int32_t)ret;
}

static void tls_context_init(AwsIotMqttTlsContext_t * p_tls)
{
    (void)memset(p_tls, 0, sizeof(*p_tls));
    p_tls->socket = SOCKETS_INVALID_SOCKET;
    mbedtls_entropy_init(&p_tls->entropy);
    mbedtls_ctr_drbg_init(&p_tls->ctr_drbg);
    mbedtls_x509_crt_init(&p_tls->ca_cert);
    mbedtls_x509_crt_init(&p_tls->client_cert);
    mbedtls_pk_init(&p_tls->client_key);
    mbedtls_ssl_config_init(&p_tls->ssl_config);
    mbedtls_ssl_init(&p_tls->ssl_context);
}

static void tls_context_free(AwsIotMqttTlsContext_t * p_tls)
{
    if (SOCKETS_INVALID_SOCKET != p_tls->socket)
    {
        TCP_Sockets_Disconnect(p_tls->socket);
        p_tls->socket = SOCKETS_INVALID_SOCKET;
    }

    mbedtls_ssl_free(&p_tls->ssl_context);
    mbedtls_ssl_config_free(&p_tls->ssl_config);
    mbedtls_pk_free(&p_tls->client_key);
    mbedtls_x509_crt_free(&p_tls->client_cert);
    mbedtls_x509_crt_free(&p_tls->ca_cert);
    mbedtls_ctr_drbg_free(&p_tls->ctr_drbg);
    mbedtls_entropy_free(&p_tls->entropy);
}

static int tls_connect(AwsIotMqttTlsContext_t * p_tls)
{
    static const char personalisation[] = "rx671-1yn-aws-iot";
    int ret;

    g_aws_iot_mqtt_tls_step = 1U;
    g_aws_iot_mqtt_entropy_source_count_after_init =
        (uint32_t)p_tls->entropy.MBEDTLS_PRIVATE(source_count);
    ret = mbedtls_entropy_add_source(&p_tls->entropy,
                                     mbedtls_hardware_poll,
                                     NULL,
                                     AWS_IOT_MQTT_ENTROPY_MIN_BYTES,
                                     MBEDTLS_ENTROPY_SOURCE_STRONG);
    g_aws_iot_mqtt_entropy_add_status = (int32_t)ret;
    g_aws_iot_mqtt_entropy_source_count_after_add =
        (uint32_t)p_tls->entropy.MBEDTLS_PRIVATE(source_count);
    if (0 != ret)
    {
        return ret;
    }

    ret = mbedtls_ctr_drbg_seed(&p_tls->ctr_drbg,
                                mbedtls_entropy_func,
                                &p_tls->entropy,
                                (const unsigned char *)personalisation,
                                strlen(personalisation));
    if (0 != ret)
    {
        return ret;
    }

    g_aws_iot_mqtt_tls_step = 2U;
    ret = mbedtls_x509_crt_parse(&p_tls->ca_cert,
                                 (const unsigned char *)tlsATS1_ROOT_CERTIFICATE_PEM,
                                 (size_t)tlsATS1_ROOT_CERTIFICATE_LENGTH);
    if (0 != ret)
    {
        return ret;
    }

    g_aws_iot_mqtt_tls_step = 3U;
    ret = mbedtls_x509_crt_parse(&p_tls->client_cert,
                                 (const unsigned char *)AWS_IOT_CLIENT_CERT_PEM,
                                 strlen(AWS_IOT_CLIENT_CERT_PEM) + 1U);
    if (0 != ret)
    {
        return ret;
    }

    g_aws_iot_mqtt_tls_step = 4U;
    ret = mbedtls_pk_parse_key(&p_tls->client_key,
                               (const unsigned char *)AWS_IOT_CLIENT_PRIVATE_KEY_PEM,
                               strlen(AWS_IOT_CLIENT_PRIVATE_KEY_PEM) + 1U,
                               NULL,
                               0,
                               mbedtls_ctr_drbg_random,
                               &p_tls->ctr_drbg);
    if (0 != ret)
    {
        return ret;
    }

    g_aws_iot_mqtt_tls_step = 5U;
    ret = mbedtls_ssl_config_defaults(&p_tls->ssl_config,
                                      MBEDTLS_SSL_IS_CLIENT,
                                      MBEDTLS_SSL_TRANSPORT_STREAM,
                                      MBEDTLS_SSL_PRESET_DEFAULT);
    if (0 != ret)
    {
        return ret;
    }

#if AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3
  #if !defined(MBEDTLS_SSL_PROTO_TLS1_3)
    #error "AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3 requires MBEDTLS_SSL_PROTO_TLS1_3"
  #endif
    mbedtls_ssl_conf_min_tls_version(&p_tls->ssl_config, MBEDTLS_SSL_VERSION_TLS1_3);
    mbedtls_ssl_conf_max_tls_version(&p_tls->ssl_config, MBEDTLS_SSL_VERSION_TLS1_3);
#endif

    mbedtls_ssl_conf_authmode(&p_tls->ssl_config, MBEDTLS_SSL_VERIFY_REQUIRED);
    mbedtls_ssl_conf_rng(&p_tls->ssl_config, mbedtls_ctr_drbg_random, &p_tls->ctr_drbg);
    mbedtls_ssl_conf_ca_chain(&p_tls->ssl_config, &p_tls->ca_cert, NULL);

    g_aws_iot_mqtt_tls_step = 6U;
    ret = mbedtls_ssl_conf_own_cert(&p_tls->ssl_config, &p_tls->client_cert, &p_tls->client_key);
    if (0 != ret)
    {
        return ret;
    }

    g_aws_iot_mqtt_tls_step = 7U;
    ret = mbedtls_ssl_setup(&p_tls->ssl_context, &p_tls->ssl_config);
    if (0 != ret)
    {
        return ret;
    }

    g_aws_iot_mqtt_tls_step = 8U;
    ret = mbedtls_ssl_set_hostname(&p_tls->ssl_context, AWS_IOT_ENDPOINT);
    if (0 != ret)
    {
        return ret;
    }

    g_aws_iot_mqtt_tls_step = 9U;
    g_aws_iot_mqtt_tcp_connect_status =
        (uint32_t)TCP_Sockets_Connect(&p_tls->socket,
                                      AWS_IOT_ENDPOINT,
                                      (uint16_t)AWS_IOT_MQTT_PORT,
                                      AWS_IOT_MQTT_TCP_RECV_TIMEOUT_MS,
                                      AWS_IOT_MQTT_TCP_SEND_TIMEOUT_MS);
    if (0U != g_aws_iot_mqtt_tcp_connect_status)
    {
        return -1;
    }

    mbedtls_ssl_set_bio(&p_tls->ssl_context,
                        (void *)p_tls->socket,
                        xMbedTLSBioTCPSocketsWrapperSend,
                        xMbedTLSBioTCPSocketsWrapperRecv,
                        NULL);

    g_aws_iot_mqtt_tls_step = 10U;
    do
    {
        ret = mbedtls_ssl_handshake(&p_tls->ssl_context);
        if ((MBEDTLS_ERR_SSL_WANT_READ == ret) || (MBEDTLS_ERR_SSL_WANT_WRITE == ret))
        {
            vTaskDelay(pdMS_TO_TICKS(1U));
        }
    } while ((MBEDTLS_ERR_SSL_WANT_READ == ret) || (MBEDTLS_ERR_SSL_WANT_WRITE == ret));

    if (0 == ret)
    {
        debug_puts("AWS TLS version=");
        debug_puts(mbedtls_ssl_get_version(&p_tls->ssl_context));
        debug_puts("\r\n");

#if AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3
        if (MBEDTLS_SSL_VERSION_TLS1_3 != mbedtls_ssl_get_version_number(&p_tls->ssl_context))
        {
            ret = MBEDTLS_ERR_SSL_BAD_PROTOCOL_VERSION;
        }
#endif
    }

    return ret;
}

static MQTTStatus_t mqtt_connect_publish(AwsIotMqttTlsContext_t * p_tls)
{
    NetworkContext_t network_context;
    TransportInterface_t transport;
    MQTTFixedBuffer_t fixed_buffer;
    MQTTContext_t mqtt_context;
    MQTTConnectInfo_t connect_info;
    MQTTPublishInfo_t publish_info;
    bool session_present = false;
    MQTTStatus_t mqtt_status;
    const char payload[] = "{\"source\":\"rx671-ek-type1yn\",\"message\":\"hello\"}";

    (void)memset(&network_context, 0, sizeof(network_context));
    (void)memset(&transport, 0, sizeof(transport));
    (void)memset(&fixed_buffer, 0, sizeof(fixed_buffer));
    (void)memset(&mqtt_context, 0, sizeof(mqtt_context));
    (void)memset(&connect_info, 0, sizeof(connect_info));
    (void)memset(&publish_info, 0, sizeof(publish_info));

    network_context.p_ssl_context = &p_tls->ssl_context;
    transport.recv = tls_transport_recv;
    transport.send = tls_transport_send;
    transport.writev = NULL;
    transport.pNetworkContext = &network_context;

    fixed_buffer.pBuffer = s_mqtt_network_buffer;
    fixed_buffer.size = sizeof(s_mqtt_network_buffer);

    mqtt_status = MQTT_Init(&mqtt_context,
                            &transport,
                            mqtt_get_time_ms,
                            mqtt_event_callback,
                            &fixed_buffer);
    if (MQTTSuccess != mqtt_status)
    {
        return mqtt_status;
    }

    connect_info.cleanSession = true;
    connect_info.pClientIdentifier = AWS_IOT_THING_NAME;
    connect_info.clientIdentifierLength = strlen(AWS_IOT_THING_NAME);
    connect_info.keepAliveSeconds = AWS_IOT_MQTT_KEEP_ALIVE_SECONDS;

    mqtt_status = MQTT_Connect(&mqtt_context,
                               &connect_info,
                               NULL,
                               AWS_IOT_MQTT_CONNACK_TIMEOUT_MS,
                               &session_present,
                               NULL,
                               NULL);
    g_aws_iot_mqtt_connect_session_present = session_present ? 1U : 0U;
    if (MQTTSuccess != mqtt_status)
    {
        return mqtt_status;
    }

    publish_info.qos = MQTTQoS0;
    publish_info.retain = false;
    publish_info.dup = false;
    publish_info.pTopicName = AWS_IOT_PUBLISH_TOPIC;
    publish_info.topicNameLength = strlen(AWS_IOT_PUBLISH_TOPIC);
    publish_info.pPayload = payload;
    publish_info.payloadLength = strlen(payload);

    mqtt_status = MQTT_Publish(&mqtt_context, &publish_info, 0U, NULL);
    if (MQTTSuccess == mqtt_status)
    {
        g_aws_iot_mqtt_publish_count++;
    }

    (void)MQTT_Disconnect(&mqtt_context, NULL, NULL);
    return mqtt_status;
}

static void aws_iot_mqtt_task(void * p_parameters)
{
    AwsIotMqttTlsContext_t * p_tls = &s_tls_context;
    int tls_status;
    MQTTStatus_t mqtt_status;

    (void)p_parameters;
    g_aws_iot_mqtt_task_enter_count++;
    g_aws_iot_mqtt_stack_high_water_entry = (uint32_t)uxTaskGetStackHighWaterMark(NULL);

    while (0U == g_freertos_tcp_network_up)
    {
        g_aws_iot_mqtt_wait_network_count++;
        vTaskDelay(AWS_IOT_MQTT_WAIT_NETWORK_TICKS);
    }

    debug_puts("AWS MQTT smoke: network ready\r\n");

    ensure_mbedtls_threading_alt();
    tls_context_init(p_tls);
    tls_status = tls_connect(p_tls);
    g_aws_iot_mqtt_stack_high_water_after_tls = (uint32_t)uxTaskGetStackHighWaterMark(NULL);
    g_aws_iot_mqtt_mbedtls_status = (int32_t)tls_status;
    log_step_status("AWS TLS", (int32_t)tls_status);

    if (0 == tls_status)
    {
        mqtt_status = mqtt_connect_publish(p_tls);
        g_aws_iot_mqtt_mqtt_status = (uint32_t)mqtt_status;
        log_step_status("AWS MQTT", (int32_t)mqtt_status);
    }

    tls_context_free(p_tls);
    g_aws_iot_mqtt_task_done_count++;
    vTaskDelete(NULL);
}

void aws_iot_mqtt_smoke_start(void)
{
#if AWS_IOT_MQTT_ENABLE
    BaseType_t result;

    g_aws_iot_mqtt_enable_seen = 1U;
    if ((0U == strlen(AWS_IOT_ENDPOINT)) ||
        (0U == strlen(AWS_IOT_CLIENT_CERT_PEM)) ||
        (0U == strlen(AWS_IOT_CLIENT_PRIVATE_KEY_PEM)))
    {
        debug_puts("AWS MQTT smoke skipped: config missing\r\n");
        return;
    }

    result = xTaskCreate(aws_iot_mqtt_task,
                         "AWSMQTT",
                         AWS_IOT_MQTT_TASK_STACK_WORDS,
                         NULL,
                         AWS_IOT_MQTT_TASK_PRIORITY,
                         NULL);
    g_aws_iot_mqtt_task_create_result = (uint32_t)result;
    debug_puts((pdPASS == result) ? "AWS MQTT smoke task OK\r\n" : "AWS MQTT smoke task NG\r\n");
#else
    g_aws_iot_mqtt_enable_seen = 0U;
#endif
}

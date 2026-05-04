#include "bg96_probe.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"
#include "demo_config.h"
#include "platform.h"
#include "r_cellular_if.h"
#include "r_sci_rx_if.h"
#include "r_sci_rx_pinset.h"

#define BG96_UART_BAUDRATE             (115200U)
#define BG96_RX_QUEUE_LENGTH           (512U)
#define BG96_RESPONSE_BUFFER_SIZE      (768U)
#define BG96_PWKEY_PULSE_MS            (700U)
#define BG96_RESET_PULSE_MS            (200U)
#define BG96_BOOT_WAIT_MS              (5000U)
#define BG96_FIRST_BYTE_TIMEOUT_MS     (2000U)
#define BG96_INTERBYTE_TIMEOUT_MS      (200U)
#define BG96_TX_CHUNK_SIZE             (64U)
#define BG96_NETWORK_POLL_INTERVAL_MS  (5000U)
#define BG96_NETWORK_REG_TIMEOUT_MS    (120000U)
#define BG96_NETWORK_CMD_TIMEOUT_MS    (30000U)
#define BG96_MQTT_CMD_TIMEOUT_MS       (30000U)

#define BG96_APN_NAME                  "linksmate.jp"
#define BG96_APN_USER                  "user"
#define BG96_APN_PASSWORD              "mate"
#define BG96_APN_AUTH_TYPE             (2)

#define BG96_TEST_BROKER_HOST          "54.36.178.49"
#define BG96_TEST_BROKER_PORT          (1883U)
#define BG96_TEST_SOCKET_ID            (3U)
#define BG96_RCELLULAR_PROTOCOL_TCP    (6U)
#define BG96_RCELLULAR_IPV4            (4U)

/* CK-RX65N V1 PMOD1 GPIO mapping from CK-RX65N_V1.03.bdf:
 *   PMOD1-GPIO1 -> P55  (user wired to BG96 RESET_N)
 *   PMOD1-GPIO2 -> PB7  (user wired to BG96 PWRKEY)
 * The AE-LTE-CATM1-BG96-BO board drives RESET/PWRKEY through Q2/Q3, so an
 * active-high output on CK asserts the line toward BG96. */
#define BG96_RESET_ASSERT()            do { PORT5.PODR.BIT.B5 = 1U; } while (0)
#define BG96_RESET_RELEASE()           do { PORT5.PODR.BIT.B5 = 0U; } while (0)
#define BG96_PWRKEY_ASSERT()           do { PORTB.PODR.BIT.B7 = 1U; } while (0)
#define BG96_PWRKEY_RELEASE()          do { PORTB.PODR.BIT.B7 = 0U; } while (0)

static QueueHandle_t s_bg96_rx_queue = NULL;
static sci_hdl_t s_bg96_uart = NULL;
static char s_bg96_text_response[BG96_RESPONSE_BUFFER_SIZE];
static char s_bg96_hex_line[256];
extern st_cellular_ctrl_t cellular_ctrl;

static void bg96_uart_callback(void *p_args)
{
    sci_cb_args_t *args = (sci_cb_args_t *) p_args;
    BaseType_t higher_priority_task_woken = pdFALSE;
    uint8_t byte;

    if ((args->event != SCI_EVT_RX_CHAR) && (args->event != SCI_EVT_RXBUF_OVFL))
    {
        return;
    }

    if (NULL == s_bg96_rx_queue)
    {
        return;
    }

    byte = args->byte;
    (void) xQueueSendFromISR(s_bg96_rx_queue, &byte, &higher_priority_task_woken);
    portYIELD_FROM_ISR(higher_priority_task_woken);
}

static void bg96_control_pins_init(void)
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);

    MPC.P55PFS.BYTE = 0x00U;
    PORT5.PMR.BIT.B5 = 0U;
    PORT5.PDR.BIT.B5 = 1U;
    BG96_RESET_RELEASE();

    MPC.PB7PFS.BYTE = 0x00U;
    PORTB.PMR.BIT.B7 = 0U;
    PORTB.PDR.BIT.B7 = 1U;
    BG96_PWRKEY_RELEASE();

    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}

static bool bg96_uart_open(void)
{
    sci_cfg_t cfg;

    if (NULL == s_bg96_rx_queue)
    {
        s_bg96_rx_queue = xQueueCreate(BG96_RX_QUEUE_LENGTH, sizeof(uint8_t));
    }

    if (NULL == s_bg96_rx_queue)
    {
        configPRINTF(("BG96: failed to allocate RX queue\r\n"));
        return false;
    }

    R_SCI_PinSet_SCI6();

    cfg.async.baud_rate = BG96_UART_BAUDRATE;
    cfg.async.clk_src = SCI_CLK_INT;
    cfg.async.data_size = SCI_DATA_8BIT;
    cfg.async.parity_en = SCI_PARITY_OFF;
    cfg.async.parity_type = SCI_EVEN_PARITY;
    cfg.async.stop_bits = SCI_STOPBITS_1;
    cfg.async.int_priority = 3;

    if (SCI_SUCCESS != R_SCI_Open(SCI_CH6, SCI_MODE_ASYNC, &cfg, bg96_uart_callback, &s_bg96_uart))
    {
        configPRINTF(("BG96: R_SCI_Open(SCI6) failed\r\n"));
        return false;
    }

    return true;
}

static void bg96_uart_flush(void)
{
    uint8_t byte;

    if (NULL == s_bg96_rx_queue)
    {
        return;
    }

    while (pdPASS == xQueueReceive(s_bg96_rx_queue, &byte, 0))
    {
        /* drop */
    }
}

static bool bg96_uart_send(const char *text)
{
    sci_err_t err;
    const uint8_t *cursor = (const uint8_t *) text;
    uint16_t remaining = (uint16_t) strlen(text);

    while (remaining > 0U)
    {
        uint16_t chunk = (remaining > BG96_TX_CHUNK_SIZE) ? BG96_TX_CHUNK_SIZE : remaining;

        do
        {
            err = R_SCI_Send(s_bg96_uart, cursor, chunk);

            if ((err == SCI_ERR_XCVR_BUSY) || (err == SCI_ERR_INSUFFICIENT_SPACE))
            {
                vTaskDelay(pdMS_TO_TICKS(1));
            }
        } while ((err == SCI_ERR_XCVR_BUSY) || (err == SCI_ERR_INSUFFICIENT_SPACE));

        if (SCI_SUCCESS != err)
        {
            configPRINTF(("BG96: R_SCI_Send failed (%d)\r\n", (int) err));
            return false;
        }

        cursor += chunk;
        remaining = (uint16_t) (remaining - chunk);
    }

    return true;
}

static size_t bg96_read_response(char *buffer,
                                 size_t buffer_size,
                                 uint32_t first_byte_timeout_ms,
                                 uint32_t interbyte_timeout_ms)
{
    uint8_t byte;
    TickType_t wait_ticks;
    size_t length = 0U;
    bool received_anything = false;

    if ((NULL == buffer) || (0U == buffer_size))
    {
        return 0U;
    }

    wait_ticks = pdMS_TO_TICKS(first_byte_timeout_ms);

    while (pdPASS == xQueueReceive(s_bg96_rx_queue, &byte, wait_ticks))
    {
        received_anything = true;

        if (length + 1U < buffer_size)
        {
            buffer[length++] = (char) byte;
        }

        wait_ticks = pdMS_TO_TICKS(interbyte_timeout_ms);
    }

    buffer[length] = '\0';

    if (!received_anything)
    {
        return 0U;
    }

    return length;
}

static void bg96_log_response(const char *label, const char *buffer, size_t length)
{
    if ((NULL == buffer) || (0U == length))
    {
        configPRINTF(("BG96 %s: <no response>\r\n", label));
        return;
    }

    configPRINTF(("BG96 %s (%u bytes):\r\n%.*s\r\n",
                  label,
                  (unsigned int) length,
                  (int) length,
                  buffer));
}

static bool bg96_command_capture(const char *command,
                                 const char *expected_token,
                                 uint32_t first_byte_timeout_ms,
                                 uint32_t interbyte_timeout_ms,
                                 char *response,
                                 size_t response_size)
{
    size_t length;

    configPRINTF(("BG96 >> %s", command));
    bg96_uart_flush();

    if (!bg96_uart_send(command))
    {
        return false;
    }

    length = bg96_read_response(response,
                                response_size,
                                first_byte_timeout_ms,
                                interbyte_timeout_ms);
    bg96_log_response("<<", response, length);

    if (0U == length)
    {
        return false;
    }

    if (NULL != strstr(response, "ERROR"))
    {
        return false;
    }

    if ((NULL != expected_token) && (NULL == strstr(response, expected_token)))
    {
        return false;
    }

    return true;
}

static bool bg96_command(const char *command, const char *expected_token)
{
    return bg96_command_capture(command,
                                expected_token,
                                BG96_FIRST_BYTE_TIMEOUT_MS,
                                BG96_INTERBYTE_TIMEOUT_MS,
                                s_bg96_text_response,
                                sizeof(s_bg96_text_response));
}

static bool bg96_command_timed(const char *command,
                               const char *expected_token,
                               uint32_t first_byte_timeout_ms)
{
    return bg96_command_capture(command,
                                expected_token,
                                first_byte_timeout_ms,
                                BG96_INTERBYTE_TIMEOUT_MS,
                                s_bg96_text_response,
                                sizeof(s_bg96_text_response));
}

static bool bg96_command_wait_async(const char *command,
                                    const char *expected_token,
                                    uint32_t total_timeout_ms)
{
    char chunk[256];
    size_t total_length = 0U;
    TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(total_timeout_ms);
    bool sent = false;

    memset(s_bg96_text_response, 0, sizeof(s_bg96_text_response));

    configPRINTF(("BG96 >> %s", command));
    bg96_uart_flush();
    if (!bg96_uart_send(command))
    {
        return false;
    }
    sent = true;

    while ((sent) && (xTaskGetTickCount() < deadline))
    {
        size_t chunk_length = bg96_read_response(chunk,
                                                 sizeof(chunk),
                                                 500U,
                                                 BG96_INTERBYTE_TIMEOUT_MS);

        if (chunk_length > 0U)
        {
            if ((total_length + chunk_length) >= sizeof(s_bg96_text_response))
            {
                chunk_length = sizeof(s_bg96_text_response) - total_length - 1U;
            }

            memcpy(&s_bg96_text_response[total_length], chunk, chunk_length);
            total_length += chunk_length;
            s_bg96_text_response[total_length] = '\0';

            if ((NULL != expected_token) && (NULL != strstr(s_bg96_text_response, expected_token)))
            {
                bg96_log_response("<<", s_bg96_text_response, total_length);
                return true;
            }

            if (NULL != strstr(s_bg96_text_response, "ERROR"))
            {
                bg96_log_response("<<", s_bg96_text_response, total_length);
                return false;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(200U));
    }

    bg96_log_response("<<", s_bg96_text_response, total_length);
    return false;
}

static void bg96_log_hex(const char *label, const uint8_t *data, size_t length)
{
    size_t offset = 0U;
    size_t i;

    if ((NULL == data) || (0U == length))
    {
        configPRINTF(("BG96 %s: <empty>\r\n", label));
        return;
    }

    for (i = 0; (i < length) && ((offset + 2U) < sizeof(s_bg96_hex_line)); i++)
    {
        offset += (size_t) snprintf(&s_bg96_hex_line[offset],
                                    sizeof(s_bg96_hex_line) - offset,
                                    "%02X",
                                    data[i]);
    }
    s_bg96_hex_line[offset] = '\0';

    configPRINTF(("BG96 %s HEX (%u bytes): %s\r\n",
                  label,
                  (unsigned int) length,
                  s_bg96_hex_line));
}

static bool bg96_socket_unread_bytes(uint32_t *p_unread_length)
{
    char response[192];
    const char *prefix = "+QIRD:";
    const char *cursor = NULL;
    long total = 0;
    long already_read = 0;
    long unread = 0;

    if ((NULL == p_unread_length) ||
        !bg96_command_capture("AT+QIRD=1,0\r",
                              "+QIRD:",
                              BG96_MQTT_CMD_TIMEOUT_MS,
                              BG96_INTERBYTE_TIMEOUT_MS,
                              response,
                              sizeof(response)))
    {
        return false;
    }

    cursor = strstr(response, prefix);
    if (NULL == cursor)
    {
        return false;
    }

    if (3 == sscanf(cursor + strlen(prefix), " %ld,%ld,%ld", &total, &already_read, &unread))
    {
        *p_unread_length = (uint32_t) unread;
        return true;
    }

    return false;
}

static bool bg96_socket_read_raw(uint32_t read_length, uint8_t *buffer, size_t buffer_size, size_t *p_out_length)
{
    char command[32];
    char response[BG96_RESPONSE_BUFFER_SIZE];
    size_t response_length;
    char *prefix;
    char *data_start;
    long actual_length = 0;

    if ((NULL == buffer) || (NULL == p_out_length) || (0U == buffer_size))
    {
        return false;
    }

    (void) snprintf(command, sizeof(command), "AT+QIRD=%u,%u\r",
                    (unsigned int) BG96_TEST_SOCKET_ID,
                    (unsigned int) read_length);

    configPRINTF(("BG96 >> %s", command));
    bg96_uart_flush();
    if (!bg96_uart_send(command))
    {
        return false;
    }

    response_length = bg96_read_response(response,
                                         sizeof(response),
                                         BG96_MQTT_CMD_TIMEOUT_MS,
                                         BG96_INTERBYTE_TIMEOUT_MS);

    if (0U == response_length)
    {
        configPRINTF(("BG96 <<: <no response>\r\n"));
        return false;
    }

    prefix = strstr(response, "+QIRD:");
    if (NULL == prefix)
    {
        bg96_log_response("<<", response, response_length);
        return false;
    }

    if (1 != sscanf(prefix + strlen("+QIRD:"), " %ld", &actual_length))
    {
        bg96_log_response("<<", response, response_length);
        return false;
    }

    data_start = strstr(prefix, "\r\n");
    if (NULL == data_start)
    {
        bg96_log_response("<<", response, response_length);
        return false;
    }
    data_start += 2;

    if ((actual_length < 0) || ((size_t) actual_length > buffer_size))
    {
        return false;
    }

    memcpy(buffer, data_start, (size_t) actual_length);
    *p_out_length = (size_t) actual_length;
    bg96_log_hex("QIRD", buffer, *p_out_length);
    return true;
}

static void bg96_hex_encode(const uint8_t *input, size_t input_length, char *output, size_t output_size)
{
    size_t i;
    size_t offset = 0U;

    if ((NULL == input) || (NULL == output) || (0U == output_size))
    {
        return;
    }

    for (i = 0; (i < input_length) && ((offset + 2U) < output_size); i++)
    {
        offset += (size_t) snprintf(&output[offset], output_size - offset, "%02X", input[i]);
    }
    output[offset] = '\0';
}

static bool bg96_socket_send_hex(const uint8_t *data, size_t data_length)
{
    char command[256];
    char hex_payload[192];

    if ((NULL == data) || (0U == data_length))
    {
        return false;
    }

    bg96_hex_encode(data, data_length, hex_payload, sizeof(hex_payload));
    (void) snprintf(command, sizeof(command), "AT+QISENDEX=%u,\"%s\"\r",
                    (unsigned int) BG96_TEST_SOCKET_ID,
                    hex_payload);

    return bg96_command_timed(command, "SEND OK", BG96_MQTT_CMD_TIMEOUT_MS);
}

static bool bg96_socket_open_tcp(const char *host, uint32_t port)
{
    char command[128];
    char response[192];
    char state_command[32];
    long connect_id = 0;
    long remote_port = 0;
    long local_port = 0;
    long socket_state = 0;
    long context_id = 0;
    long server_id = 0;
    long access_mode = 0;
    char service_type[16];
    char ip_addr[64];
    char at_port[16];
    uint32_t poll = 0U;

    (void) snprintf(command, sizeof(command), "AT+QIOPEN=1,%u,\"TCP\",\"%s\",%u,0,0\r",
                    (unsigned int) BG96_TEST_SOCKET_ID,
                    host,
                    (unsigned int) port);

    if (!bg96_command_timed(command, "OK", BG96_MQTT_CMD_TIMEOUT_MS))
    {
        return false;
    }

    (void) snprintf(state_command, sizeof(state_command), "AT+QISTATE=1,%u\r",
                    (unsigned int) BG96_TEST_SOCKET_ID);

    while (poll < 40U)
    {
        char *state_line = NULL;

        if (!bg96_command_capture(state_command,
                                  "+QISTATE:",
                                  BG96_MQTT_CMD_TIMEOUT_MS,
                                  BG96_INTERBYTE_TIMEOUT_MS,
                                  response,
                                  sizeof(response)))
        {
            vTaskDelay(pdMS_TO_TICKS(500U));
            poll++;
            continue;
        }

        state_line = strstr(response, "+QISTATE:");
        if ((NULL != state_line) &&
            (10 == sscanf(state_line,
                          "+QISTATE: %ld,\"%15[^\"]\",\"%63[^\"]\",%ld,%ld,%ld,%ld,%ld,%ld,\"%15[^\"]\"",
                          &connect_id,
                          service_type,
                          ip_addr,
                          &remote_port,
                          &local_port,
                          &socket_state,
                          &context_id,
                          &server_id,
                          &access_mode,
                          at_port)))
        {
            if ((connect_id == (long) BG96_TEST_SOCKET_ID) && (socket_state == 2))
            {
                configPRINTF(("BG96 MQTT: socket connected (%s:%ld)\r\n", ip_addr, remote_port));
                return true;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(500U));
        poll++;
    }

    configPRINTF(("BG96 MQTT: socket did not reach connected state\r\n"));
    return false;
}

static void bg96_socket_close(void)
{
    char command[32];

    (void) snprintf(command, sizeof(command), "AT+QICLOSE=%u\r", (unsigned int) BG96_TEST_SOCKET_ID);
    (void) bg96_command_timed(command, "OK", BG96_MQTT_CMD_TIMEOUT_MS);
}

static size_t bg96_build_mqtt_connect(uint8_t *buffer, size_t buffer_size)
{
    char client_id[24];
    size_t client_id_length;
    size_t remaining_length;
    size_t idx = 0U;

    if ((NULL == buffer) || (buffer_size < 32U))
    {
        return 0U;
    }

    (void) snprintf(client_id, sizeof(client_id), "ckrx65n-bg96-%lu",
                    (unsigned long) (xTaskGetTickCount() % 100000UL));
    client_id_length = strlen(client_id);
    remaining_length = 10U + 2U + client_id_length;

    buffer[idx++] = 0x10U;
    buffer[idx++] = (uint8_t) remaining_length;
    buffer[idx++] = 0x00U;
    buffer[idx++] = 0x04U;
    buffer[idx++] = 'M';
    buffer[idx++] = 'Q';
    buffer[idx++] = 'T';
    buffer[idx++] = 'T';
    buffer[idx++] = 0x04U;
    buffer[idx++] = 0x02U;
    buffer[idx++] = 0x00U;
    buffer[idx++] = 0x3CU;
    buffer[idx++] = (uint8_t) ((client_id_length >> 8) & 0xFFU);
    buffer[idx++] = (uint8_t) (client_id_length & 0xFFU);
    memcpy(&buffer[idx], client_id, client_id_length);
    idx += client_id_length;

    return idx;
}

static void bg96_mqtt_plain_probe(void)
{
    uint8_t connect_packet[64];
    uint8_t rx_buffer[32];
    uint32_t unread_length = 0U;
    size_t connect_length;
    size_t rx_length = 0U;
    uint32_t poll_count = 0U;

    configPRINTF(("BG96 MQTT: opening TCP socket to %s:%u\r\n",
                  BG96_TEST_BROKER_HOST,
                  (unsigned int) BG96_TEST_BROKER_PORT));

    if (!bg96_socket_open_tcp(BG96_TEST_BROKER_HOST, BG96_TEST_BROKER_PORT))
    {
        configPRINTF(("BG96 MQTT: socket open failed\r\n"));
        return;
    }

    connect_length = bg96_build_mqtt_connect(connect_packet, sizeof(connect_packet));
    bg96_log_hex("MQTT CONNECT", connect_packet, connect_length);

    if (!bg96_socket_send_hex(connect_packet, connect_length))
    {
        configPRINTF(("BG96 MQTT: CONNECT send failed\r\n"));
        bg96_socket_close();
        return;
    }

    while (poll_count < 20U)
    {
        if (bg96_socket_unread_bytes(&unread_length) && (unread_length >= 4U))
        {
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(500U));
        poll_count++;
    }

    if ((unread_length >= 4U) &&
        bg96_socket_read_raw(4U, rx_buffer, sizeof(rx_buffer), &rx_length) &&
        (4U == rx_length) &&
        (0x20U == rx_buffer[0]) &&
        (0x02U == rx_buffer[1]) &&
        (0x00U == rx_buffer[2]) &&
        (0x00U == rx_buffer[3]))
    {
        static const uint8_t pingreq[2] = { 0xC0U, 0x00U };

        configPRINTF(("BG96 MQTT: CONNACK accepted\r\n"));
        if (bg96_socket_send_hex(pingreq, sizeof(pingreq)))
        {
            unread_length = 0U;
            poll_count = 0U;
            while (poll_count < 20U)
            {
                if (bg96_socket_unread_bytes(&unread_length) && (unread_length >= 2U))
                {
                    break;
                }
                vTaskDelay(pdMS_TO_TICKS(500U));
                poll_count++;
            }

            if ((unread_length >= 2U) &&
                bg96_socket_read_raw(2U, rx_buffer, sizeof(rx_buffer), &rx_length) &&
                (2U == rx_length) &&
                (0xD0U == rx_buffer[0]) &&
                (0x00U == rx_buffer[1]))
            {
                configPRINTF(("BG96 MQTT: PINGRESP received\r\n"));
            }
            else
            {
                configPRINTF(("BG96 MQTT: PINGRESP not confirmed\r\n"));
            }
        }
    }
    else
    {
        configPRINTF(("BG96 MQTT: CONNACK not confirmed\r\n"));
    }

    (void) bg96_socket_send_hex((const uint8_t *) "\xE0\x00", 2U);
    bg96_socket_close();
}

static void bg96_mqtt_at_probe(void)
{
    char command[160];
    char client_id[24];

    (void) bg96_command_timed("AT+QMTCFG=\"pdpcid\",0,1\r", "OK", BG96_MQTT_CMD_TIMEOUT_MS);

    (void) snprintf(command, sizeof(command), "AT+QMTOPEN=0,\"%s\",%u\r",
                    BG96_TEST_BROKER_HOST,
                    (unsigned int) BG96_TEST_BROKER_PORT);
    if (!bg96_command_wait_async(command, "+QMTOPEN: 0,0", BG96_MQTT_CMD_TIMEOUT_MS))
    {
        configPRINTF(("BG96 MQTT(AT): QMTOPEN failed\r\n"));
        return;
    }

    (void) snprintf(client_id, sizeof(client_id), "ckrx65n-bg96-%lu",
                    (unsigned long) (xTaskGetTickCount() % 100000UL));
    (void) snprintf(command, sizeof(command), "AT+QMTCONN=0,\"%s\"\r", client_id);
    if (!bg96_command_wait_async(command, "+QMTCONN: 0,0,0", BG96_MQTT_CMD_TIMEOUT_MS))
    {
        configPRINTF(("BG96 MQTT(AT): QMTCONN failed\r\n"));
        (void) bg96_command_wait_async("AT+QMTCLOSE=0\r", "+QMTCLOSE: 0,0", BG96_MQTT_CMD_TIMEOUT_MS);
        return;
    }

    if (!bg96_command_wait_async("AT+QMTPUBEX=0,0,0,0,\"openai/codex/test\",\"hello-from-bg96\"\r",
                                 "+QMTPUB: 0,0,0",
                                 BG96_MQTT_CMD_TIMEOUT_MS))
    {
        configPRINTF(("BG96 MQTT(AT): QMTPUBEX failed\r\n"));
    }
    else
    {
        configPRINTF(("BG96 MQTT(AT): publish succeeded\r\n"));
    }

    (void) bg96_command_wait_async("AT+QMTDISC=0\r", "+QMTDISC: 0,0", BG96_MQTT_CMD_TIMEOUT_MS);
    (void) bg96_command_wait_async("AT+QMTCLOSE=0\r", "+QMTCLOSE: 0,0", BG96_MQTT_CMD_TIMEOUT_MS);
}

static void bg96_r_cellular_smoke_test(void)
{
    int32_t socket_no = 0;
    e_cellular_err_t ret = CELLULAR_SUCCESS;
    static const uint8_t broker_ip[] = BG96_TEST_BROKER_HOST;

    if (NULL != s_bg96_uart)
    {
        R_SCI_Close(s_bg96_uart);
        s_bg96_uart = NULL;
    }

    configPRINTF(("BG96 r_cellular: opening driver\r\n"));
    ret = R_CELLULAR_Open(&cellular_ctrl, NULL);
    configPRINTF(("BG96 r_cellular: R_CELLULAR_Open -> %d\r\n", (int)ret));
    if (CELLULAR_SUCCESS != ret)
    {
        return;
    }

    ret = R_CELLULAR_APConnect(&cellular_ctrl, NULL);
    configPRINTF(("BG96 r_cellular: R_CELLULAR_APConnect -> %d\r\n", (int)ret));
    if (CELLULAR_SUCCESS != ret)
    {
        (void)R_CELLULAR_Close(&cellular_ctrl);
        return;
    }

    socket_no = R_CELLULAR_CreateSocket(&cellular_ctrl,
                                        BG96_RCELLULAR_PROTOCOL_TCP,
                                        BG96_RCELLULAR_IPV4);
    configPRINTF(("BG96 r_cellular: R_CELLULAR_CreateSocket -> %ld\r\n", (long)socket_no));
    if (socket_no <= 0)
    {
        (void)R_CELLULAR_Close(&cellular_ctrl);
        return;
    }

    ret = R_CELLULAR_ConnectSocket(&cellular_ctrl,
                                   (uint8_t)socket_no,
                                   broker_ip,
                                   (uint16_t)BG96_TEST_BROKER_PORT);
    configPRINTF(("BG96 r_cellular: R_CELLULAR_ConnectSocket -> %d\r\n", (int)ret));

    if (CELLULAR_SUCCESS == ret)
    {
        (void)R_CELLULAR_CloseSocket(&cellular_ctrl, (uint8_t)socket_no);
    }

    (void)R_CELLULAR_Close(&cellular_ctrl);
}

static bool bg96_configure_apn(void)
{
    char command[96];

    (void) snprintf(command,
                    sizeof(command),
                    "AT+QICSGP=1,1,\"%s\",\"%s\",\"%s\",%u\r",
                    BG96_APN_NAME,
                    BG96_APN_USER,
                    BG96_APN_PASSWORD,
                    (unsigned int) BG96_APN_AUTH_TYPE);

    return bg96_command(command, "OK");
}

static void bg96_dump_radio_diagnostics(void)
{
    (void) bg96_command("AT+CFUN?\r", "+CFUN:");
    (void) bg96_command("AT+QCFG=\"nwscanmode\"\r", "+QCFG:");
    (void) bg96_command("AT+QCFG=\"iotopmode\"\r", "+QCFG:");
    (void) bg96_command("AT+QCFG=\"nwscanseq\"\r", "+QCFG:");
    (void) bg96_command("AT+QCFG=\"band\"\r", "+QCFG:");
    (void) bg96_command("AT+QNWINFO\r", "+QNWINFO:");
    (void) bg96_command("AT+QCSQ\r", "+QCSQ:");
    (void) bg96_command("AT+QENG=\"servingcell\"\r", "+QENG:");
    (void) bg96_command("AT+QENG=\"neighbourcell\"\r", "OK");
}

static void bg96_apply_catm_profile(void)
{
    (void) bg96_command("AT+QCFG=\"nwscanmode\",3,1\r", "OK");
    (void) bg96_command("AT+QCFG=\"iotopmode\",0,1\r", "OK");
    (void) bg96_command("AT+QCFG=\"nwscanseq\",02,1\r", "OK");
}

static void bg96_dump_sim_diagnostics(void)
{
    (void) bg96_command("AT+CMEE=2\r", "OK");
    (void) bg96_command("AT+QCCID\r", "+QCCID:");
    (void) bg96_command("AT+QINISTAT\r", "+QINISTAT:");
    (void) bg96_command("AT+QSIMDET?\r", "+QSIMDET:");
    (void) bg96_command("AT+QSIMSTAT?\r", "+QSIMSTAT:");
    (void) bg96_command("AT+QPINC?\r", "+QPINC:");
    (void) bg96_command("AT+CPIN?\r", "+CPIN:");
    (void) bg96_command("AT+CIMI\r", "OK");
}

static bool bg96_is_registered(const char *response)
{
    return ((NULL != strstr(response, "+CEREG: 0,1")) ||
            (NULL != strstr(response, "+CEREG: 0,5")) ||
            (NULL != strstr(response, "+CEREG: 1,1")) ||
            (NULL != strstr(response, "+CEREG: 1,5")) ||
            (NULL != strstr(response, "+CEREG: 2,1")) ||
            (NULL != strstr(response, "+CEREG: 2,5")));
}

static bool bg96_wait_for_registration(uint32_t timeout_ms)
{
    char response[BG96_RESPONSE_BUFFER_SIZE];
    TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);

    while (xTaskGetTickCount() < deadline)
    {
        if (!bg96_command_capture("AT+CEREG?\r",
                                  "+CEREG:",
                                  BG96_FIRST_BYTE_TIMEOUT_MS,
                                  BG96_INTERBYTE_TIMEOUT_MS,
                                  response,
                                  sizeof(response)))
        {
            vTaskDelay(pdMS_TO_TICKS(BG96_NETWORK_POLL_INTERVAL_MS));
            continue;
        }

        if (bg96_is_registered(response))
        {
            configPRINTF(("BG96: network registration complete\r\n"));
            return true;
        }

        vTaskDelay(pdMS_TO_TICKS(BG96_NETWORK_POLL_INTERVAL_MS));
    }

    configPRINTF(("BG96: network registration timeout\r\n"));
    return false;
}

static void bg96_capture_boot_urc(const char *stage)
{
    char response[BG96_RESPONSE_BUFFER_SIZE];
    size_t length;

    length = bg96_read_response(response,
                                sizeof(response),
                                BG96_BOOT_WAIT_MS,
                                BG96_INTERBYTE_TIMEOUT_MS);

    if (length > 0U)
    {
        bg96_log_response(stage, response, length);
    }
    else
    {
        configPRINTF(("BG96 %s: <silent>\r\n", stage));
    }
}

static void bg96_pwrkey_pulse(void)
{
    configPRINTF(("BG96: assert PWRKEY for %u ms\r\n", BG96_PWKEY_PULSE_MS));
    BG96_PWRKEY_ASSERT();
    vTaskDelay(pdMS_TO_TICKS(BG96_PWKEY_PULSE_MS));
    BG96_PWRKEY_RELEASE();
}

static void bg96_reset_pulse(void)
{
    configPRINTF(("BG96: assert RESET_N for %u ms\r\n", BG96_RESET_PULSE_MS));
    BG96_RESET_ASSERT();
    vTaskDelay(pdMS_TO_TICKS(BG96_RESET_PULSE_MS));
    BG96_RESET_RELEASE();
}

void bg96_probe_run(void)
{
    configPRINTF(("\r\nBG96 probe: start\r\n"));
    configPRINTF(("BG96 probe: PMOD1 UART uses SCI6 (P00/P01/PJ3)\r\n"));
    configPRINTF(("BG96 probe: RESET_N=P55, PWRKEY=PB7\r\n"));

    bg96_control_pins_init();

    if (!bg96_uart_open())
    {
        return;
    }

    bg96_capture_boot_urc("initial");

    if (!bg96_command("AT\r", "OK"))
    {
        bg96_pwrkey_pulse();
        bg96_capture_boot_urc("after PWRKEY");
    }

    if (!bg96_command("AT\r", "OK"))
    {
        bg96_reset_pulse();
        bg96_capture_boot_urc("after RESET_N");
    }

    if (!bg96_command("AT\r", "OK"))
    {
        configPRINTF(("BG96 probe: no AT response after PWRKEY/RESET_N\r\n"));
        return;
    }

    (void) bg96_command("ATE0\r", "OK");
    (void) bg96_command("ATI1\r", "OK");
    (void) bg96_command("AT+CGMM\r", "OK");
    bg96_dump_sim_diagnostics();
    (void) bg96_command("AT+COPS?\r", "+COPS:");
    (void) bg96_command("AT+CSQ\r", "+CSQ:");
    (void) bg96_configure_apn();
    bg96_apply_catm_profile();
    bg96_dump_radio_diagnostics();

    if (bg96_wait_for_registration(BG96_NETWORK_REG_TIMEOUT_MS))
    {
        (void) bg96_command("AT+CGATT?\r", "+CGATT:");
        (void) bg96_command_timed("AT+CGATT=1\r", "OK", BG96_NETWORK_CMD_TIMEOUT_MS);
        (void) bg96_command("AT+CGATT?\r", "+CGATT:");
        (void) bg96_command("AT+CGACT?\r", "+CGACT:");
        (void) bg96_command_timed("AT+CGACT=1,1\r", "OK", BG96_NETWORK_CMD_TIMEOUT_MS);
        (void) bg96_command("AT+CGACT?\r", "+CGACT:");
        (void) bg96_command_timed("AT+QIACT=1\r", "OK", BG96_NETWORK_CMD_TIMEOUT_MS);
        (void) bg96_command("AT+QIACT?\r", "OK");
        (void) bg96_command("AT+CGPADDR=1\r", "+CGPADDR:");
        bg96_r_cellular_smoke_test();
        bg96_mqtt_at_probe();
    }
    else
    {
        bg96_dump_sim_diagnostics();
        bg96_dump_radio_diagnostics();
        (void) bg96_command_timed("AT+COPS=?\r", "+COPS:", BG96_NETWORK_CMD_TIMEOUT_MS);
    }

    configPRINTF(("BG96 probe: complete\r\n"));
}

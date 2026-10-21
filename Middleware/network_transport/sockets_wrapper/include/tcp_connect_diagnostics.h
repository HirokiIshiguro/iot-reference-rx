/* Common TCP-wrapper diagnostics. SPDX-License-Identifier: MIT */
#ifndef TCP_CONNECT_DIAGNOSTICS_H
#define TCP_CONNECT_DIAGNOSTICS_H

#include <stddef.h>
#include <stdint.h>

#define TCP_CONNECT_BACKEND_FREERTOS_TCP       (1U)
#define TCP_CONNECT_BACKEND_CELLULAR            (2U)
#define TCP_CONNECT_BACKEND_WIFI_DA16600        (3U)

#define TCP_CONNECT_STAGE_NONE                 (0U)
#define TCP_CONNECT_STAGE_SOCKET_CREATION      (1U)
#define TCP_CONNECT_STAGE_SOCKET_CONFIGURATION (2U)
#define TCP_CONNECT_STAGE_ADDRESS_RESOLUTION   (3U)
#define TCP_CONNECT_STAGE_INITIAL_CONNECT      (4U)
#define TCP_CONNECT_STAGE_EXPLICIT_CONNECT_WAIT (5U)

typedef void (*TCPConnectDiagnosticWriter_t)(const char *line);

static char *tcp_sockets_diag_append_text(char *out, const char *text)
{
    while ('\0' != *text)
    {
        *out++ = *text++;
    }
    return out;
}

static char *tcp_sockets_diag_append_decimal(char *out, uint32_t value)
{
    char digits[10];
    size_t count = 0U;
    do
    {
        digits[count++] = (char)('0' + (value % 10U));
        value /= 10U;
    } while (0U != value);
    while (0U != count)
    {
        *out++ = digits[--count];
    }
    return out;
}

static char *tcp_sockets_diag_append_hex(char *out, uint32_t value)
{
    uint32_t index;
    uint32_t digit;
    for (index = 0U; index < 8U; index++)
    {
        digit = (value >> ((7U - index) * 4U)) & 0xFU;
        *out++ = (char)((digit < 10U) ? ('0' + digit) : ('A' + digit - 10U));
    }
    return out;
}

/* Passive DNS-path capability. No DNS payload, identity or packet bytes are
 * accepted by this public formatter. Counters are cumulative since boot, not
 * query/window IDs or a coherent transaction. cap=0 is UNSUPPORTED: no counter
 * values are written or reported. An opted-in application owns the provider.
 * TX handoff is not wire-send success; RX/IP-queue counts are not DNS validity.
 */
#ifndef TCP_SOCKETS_ENABLE_DNS_PATH_DIAGNOSTICS
#define TCP_SOCKETS_ENABLE_DNS_PATH_DIAGNOSTICS (0)
#endif

#define TCP_DNS_PATH_UNSUPPORTED              (0U)
#define TCP_DNS_PATH_COUNTERS_AVAILABLE       (1U)

typedef struct TCPDNSPathCounters
{
    uint32_t tx_handoff;
    uint32_t rx_ingress;
    uint32_t rx_ipqueue;
    uint32_t rx_drop;
    uint32_t saturated;
} TCPDNSPathCounters_t;

#if (TCP_SOCKETS_ENABLE_DNS_PATH_DIAGNOSTICS == 1)
uint32_t TCP_Sockets_GetDNSPathCounters(uint32_t backend,
                                      TCPDNSPathCounters_t *counters);
#else
static uint32_t TCP_Sockets_GetDNSPathCounters(uint32_t backend,
                                              TCPDNSPathCounters_t *counters)
{
    (void)backend;
    (void)counters;
    return TCP_DNS_PATH_UNSUPPORTED;
}
#endif

/* Caller-selected task writer only. No UART from the adapter/IP task. This
 * fixed row is emitted only by the existing explicit failure formatter below.
 * Reads are reported cumulatively; concurrent progress and delivery loss mean
 * absence, zero or relationships between fields do not establish a cause.
 */
static void tcp_sockets_report_dns_path(uint32_t backend,
                                         char line[96],
                                         TCPConnectDiagnosticWriter_t writer)
{
    TCPDNSPathCounters_t counters;
    uint32_t capability;
    char *out = line;

    if ((NULL == writer) ||
        (backend < TCP_CONNECT_BACKEND_FREERTOS_TCP) ||
        (backend > TCP_CONNECT_BACKEND_WIFI_DA16600))
    {
        return;
    }
    capability = TCP_Sockets_GetDNSPathCounters(backend, &counters);
    out = tcp_sockets_diag_append_text(out, "TCP DNS path backend=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " cap=");
    out = tcp_sockets_diag_append_decimal(out,
             (TCP_DNS_PATH_COUNTERS_AVAILABLE == capability) ? 1U : 0U);
    if (TCP_DNS_PATH_COUNTERS_AVAILABLE == capability)
    {
        out = tcp_sockets_diag_append_text(out, " tx=");
        out = tcp_sockets_diag_append_decimal(out, counters.tx_handoff);
        out = tcp_sockets_diag_append_text(out, " rx=");
        out = tcp_sockets_diag_append_decimal(out, counters.rx_ingress);
        out = tcp_sockets_diag_append_text(out, " ip=");
        out = tcp_sockets_diag_append_decimal(out, counters.rx_ipqueue);
        out = tcp_sockets_diag_append_text(out, " drop=");
        out = tcp_sockets_diag_append_decimal(out, counters.rx_drop);
        out = tcp_sockets_diag_append_text(out, " sat=");
        out = tcp_sockets_diag_append_decimal(out,
                  (0U != counters.saturated) ? 1U : 0U);
    }
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
}

/* The numeric backend distinguishes status domains; status bits are not a
 * universal errno. Stage describes the public operation visible in this
 * wrapper, not an opaque vendor driver's internal state. No network identity
 * or arbitrary error text is accepted. The writer must consume the row before
 * returning. Physical reception is not guaranteed; absence is not evidence.
 */
static void tcp_sockets_report_connect_failure(uint32_t backend,
                                               uint32_t stage,
                                               uint32_t status,
                                               TCPConnectDiagnosticWriter_t writer)
{
    char line[96];
    char *out = line;

    if ((0U == status) || (NULL == writer))
    {
        return;
    }
    out = tcp_sockets_diag_append_text(out, "TCP connect failure context backend=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " stage=");
    out = tcp_sockets_diag_append_decimal(out, stage);
    out = tcp_sockets_diag_append_text(out, " status=");
    out = tcp_sockets_diag_append_hex(out, status);
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
    tcp_sockets_report_dns_path(backend, line, writer);
}

/* Optional observation contract. Disabled by default in every backend.
 * The hook is task context and must not block, alter task notifications, call
 * network/RNG/PKCS APIs, or print secrets. The application owns any delivery.
 * backend1 status is a PKCS#11 CK_RV. Opaque cellular/DA internal RNG state is
 * not observable through their current API: they emit no synthetic event.
 */
#ifndef TCP_SOCKETS_ENABLE_RANDOM_DIAGNOSTICS
#define TCP_SOCKETS_ENABLE_RANDOM_DIAGNOSTICS   (0)
#endif

#define TCP_RANDOM_OP_UNSPECIFIED              (0U)
#define TCP_RANDOM_OP_GET_FUNCTION_LIST        (1U)
#define TCP_RANDOM_OP_TOKEN_INITIALIZE         (2U)
#define TCP_RANDOM_OP_SLOT_COUNT               (3U)
#define TCP_RANDOM_OP_SLOT_ALLOCATE            (4U)
#define TCP_RANDOM_OP_SLOT_LIST                (5U)
#define TCP_RANDOM_OP_SESSION_OPEN             (6U)
#define TCP_RANDOM_OP_GENERATE_RANDOM          (7U)

#if (TCP_SOCKETS_ENABLE_RANDOM_DIAGNOSTICS == 1)
/* Opt-in application definitions are required before enabling this feature.
 * No UART route or mutable observer state is provided by this header.
 */
void TCP_Sockets_OnRandomFailure(uint32_t backend,
                                 uint32_t operation,
                                 uint32_t status);
void TCP_Sockets_OnDNSSendAttempt(uint32_t backend);
#endif

/* Fixed numeric failure row only; callers choose an appropriate task-owned
 * writer. A hook must not use a blocking writer directly in the IP task.
 */
static void tcp_sockets_report_random_failure(uint32_t backend,
                                              uint32_t operation,
                                              uint32_t status,
                                              uint32_t match,
                                              TCPConnectDiagnosticWriter_t writer)
{
    char line[96];
    char *out = line;

    if ((0U == status) || (NULL == writer))
    {
        return;
    }
    out = tcp_sockets_diag_append_text(out, "TCP RNG failure context backend=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " op=");
    out = tcp_sockets_diag_append_decimal(out, operation);
    out = tcp_sockets_diag_append_text(out, " status=");
    out = tcp_sockets_diag_append_hex(out, status);
    out = tcp_sockets_diag_append_text(out, " match=");
    out = tcp_sockets_diag_append_decimal(out, (0U != match) ? 1U : 0U);
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
}

#endif

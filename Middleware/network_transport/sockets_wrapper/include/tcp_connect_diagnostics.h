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

/* Optional legacy adapter context, sharing the existing RX671 opt-in.
 * Modulo-uint32 counters retain their existing reset/increment behavior; there
 * is no saturation witness. nr includes invalid descriptor/buffer/length as
 * well as not-ready. ARP tx/rx are EtherType-only, not validity/identity.
 * ipall/qdall cover ALL protocols, not ARP-specific queue acceptance/drop.
 * No per-query, coherent snapshot, field relationship or wire claim. */
typedef struct TCPAdapterPathCounters
{
    uint32_t tx_handoff;
    uint32_t tx_reject;
    uint32_t tx_no_buffer;
    uint32_t tx_no_data;
    uint32_t arp_tx;
    uint32_t arp_rx;
    uint32_t rx_ipqueue_all;
    uint32_t rx_queue_drop_all;
} TCPAdapterPathCounters_t;

#if (TCP_SOCKETS_ENABLE_DNS_PATH_DIAGNOSTICS == 1)
uint32_t TCP_Sockets_GetAdapterPathCounters(uint32_t backend,
                                           TCPAdapterPathCounters_t *counters);
#else
static uint32_t TCP_Sockets_GetAdapterPathCounters(uint32_t backend,
                                                  TCPAdapterPathCounters_t *counters)
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

/* Existing failure task only; reuse its 96-byte line and legacy scalars.
 * Each maximum row, including CRLF and NUL, fits that buffer. */
static void tcp_sockets_report_adapter_path(uint32_t backend,
                                             char line[96],
                                             TCPConnectDiagnosticWriter_t writer)
{
    TCPAdapterPathCounters_t counters;
    uint32_t capability;
    char *out;

    if ((NULL == writer) ||
        (backend < TCP_CONNECT_BACKEND_FREERTOS_TCP) ||
        (backend > TCP_CONNECT_BACKEND_WIFI_DA16600))
    {
        return;
    }
    capability = TCP_Sockets_GetAdapterPathCounters(backend, &counters);
    out = tcp_sockets_diag_append_text(line, "TCP adapter gates backend=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " cap=");
    out = tcp_sockets_diag_append_decimal(out,
             (TCP_DNS_PATH_COUNTERS_AVAILABLE == capability) ? 1U : 0U);
    if (TCP_DNS_PATH_COUNTERS_AVAILABLE == capability)
    {
        out = tcp_sockets_diag_append_text(out, " tx=");
        out = tcp_sockets_diag_append_decimal(out, counters.tx_handoff);
        out = tcp_sockets_diag_append_text(out, " nr=");
        out = tcp_sockets_diag_append_decimal(out, counters.tx_reject);
        out = tcp_sockets_diag_append_text(out, " nb=");
        out = tcp_sockets_diag_append_decimal(out, counters.tx_no_buffer);
        out = tcp_sockets_diag_append_text(out, " nd=");
        out = tcp_sockets_diag_append_decimal(out, counters.tx_no_data);
    }
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);

    out = tcp_sockets_diag_append_text(line, "TCP ARP path backend=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " cap=");
    out = tcp_sockets_diag_append_decimal(out,
             (TCP_DNS_PATH_COUNTERS_AVAILABLE == capability) ? 1U : 0U);
    if (TCP_DNS_PATH_COUNTERS_AVAILABLE == capability)
    {
        out = tcp_sockets_diag_append_text(out, " tx=");
        out = tcp_sockets_diag_append_decimal(out, counters.arp_tx);
        out = tcp_sockets_diag_append_text(out, " rx=");
        out = tcp_sockets_diag_append_decimal(out, counters.arp_rx);
        out = tcp_sockets_diag_append_text(out, " ipall=");
        out = tcp_sockets_diag_append_decimal(out, counters.rx_ipqueue_all);
        out = tcp_sockets_diag_append_text(out, " qdall=");
        out = tcp_sockets_diag_append_decimal(out, counters.rx_queue_drop_all);
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
    tcp_sockets_report_adapter_path(backend, line, writer);
}

/* Optional before/after SAMPLED network state, not actual DNS-attempt state.
 * Default off; no producer logs. Opaque transports remain cap=0. No address,
 * MAC, endpoint pointer or identifier is accepted by these output structs. */
#ifndef TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS
/* Explicit EPOCH setting wins. Otherwise follow the already explicit RANDOM
 * opt-in, without relying on its later default definition in this header. */
#if defined(TCP_SOCKETS_ENABLE_RANDOM_DIAGNOSTICS) &&     (TCP_SOCKETS_ENABLE_RANDOM_DIAGNOSTICS == 1)
#define TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS (1)
#else
#define TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS (0)
#endif
#endif

#define TCP_SAMPLE_UNSUPPORTED                 (0U)
#define TCP_SAMPLE_AVAILABLE                   (1U)
#define TCP_ROUTE_SAMPLE_INVALID               (0U)
#define TCP_ROUTE_SAMPLE_NO_DNS                (1U)
#define TCP_ROUTE_SAMPLE_DNS_INDEX_INVALID     (2U)
#define TCP_ROUTE_SAMPLE_ENDPOINT_LIMIT        (3U)
#define TCP_ROUTE_SAMPLE_READY                 (4U)
#define TCP_ROUTE_SAMPLE_NO_ROUTE              (0U)
#define TCP_ROUTE_SAMPLE_DIRECT                (1U)
#define TCP_ROUTE_SAMPLE_GATEWAY               (2U)
#define TCP_ROUTE_SAMPLE_MAX_ENDPOINTS         (4U)

typedef struct TCPRxEpochSample
{
    uint32_t capability;
    uint32_t initialise_count;
    uint32_t ready_count;
    uint32_t link_up;
} TCPRxEpochSample_t;

typedef struct TCPRouteCacheSample
{
    uint32_t capability;
    uint32_t state;
    uint32_t dns_endpoint_up;
    uint32_t route_kind;
    uint32_t route_endpoint_up;
    uint32_t cache_valid;
} TCPRouteCacheSample_t;

typedef struct TCPConnectNetworkSample
{
    TCPRxEpochSample_t epoch;
    TCPRouteCacheSample_t route;
} TCPConnectNetworkSample_t;

typedef void (*TCPRxEpochSampleReader_t)(uint32_t backend,
                                         TCPRxEpochSample_t *sample);

static void tcp_sockets_clear_epoch_sample(TCPRxEpochSample_t *sample)
{
    if (NULL != sample)
    {
        sample->capability = TCP_SAMPLE_UNSUPPORTED;
        sample->initialise_count = 0U;
        sample->ready_count = 0U;
        sample->link_up = 0U;
    }
}

static void tcp_sockets_clear_route_sample(TCPRouteCacheSample_t *sample)
{
    if (NULL != sample)
    {
        sample->capability = TCP_SAMPLE_UNSUPPORTED;
        sample->state = TCP_ROUTE_SAMPLE_INVALID;
        sample->dns_endpoint_up = 0U;
        sample->route_kind = TCP_ROUTE_SAMPLE_NO_ROUTE;
        sample->route_endpoint_up = 0U;
        sample->cache_valid = 0U;
    }
}

/* All ports implement this API: FreeRTOS+TCP may sample; opaque ports cannot.
 * Task context only; opt-in implementation performs bounded reads, no sends. */
void TCP_Sockets_GetRouteCacheSample(uint32_t backend,
                                     TCPRouteCacheSample_t *sample);

/* Application owns before/after storage and may supply an epoch reader. RX72
 * can use this same route API with NULL epoch reader. These are independent
 * samples; no coherent pair, actual DNS-server selection or cause is claimed. */
static void tcp_sockets_capture_network_sample(uint32_t backend,
                                                 TCPConnectNetworkSample_t *sample,
                                                 TCPRxEpochSampleReader_t reader)
{
    if (NULL == sample)
    {
        return;
    }
    tcp_sockets_clear_epoch_sample(&sample->epoch);
    tcp_sockets_clear_route_sample(&sample->route);
#if (TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS == 1)
    TCP_Sockets_GetRouteCacheSample(backend, &sample->route);
    if ((backend == TCP_CONNECT_BACKEND_FREERTOS_TCP) && (NULL != reader))
    {
        reader(backend, &sample->epoch);
    }
#else
    (void)backend;
    (void)reader;
#endif
}

#if (TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS == 1)
static void tcp_sockets_report_epoch_sample(uint32_t backend, uint32_t phase,
                                             const TCPRxEpochSample_t *sample,
                                             char line[96],
                                             TCPConnectDiagnosticWriter_t writer)
{
    char *out = line;
    out = tcp_sockets_diag_append_text(out, "TCP sampled epoch b=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " p=");
    out = tcp_sockets_diag_append_decimal(out, phase);
    out = tcp_sockets_diag_append_text(out, " cap=");
    if ((backend == TCP_CONNECT_BACKEND_FREERTOS_TCP) &&
        (TCP_SAMPLE_AVAILABLE == sample->capability))
    {
        out = tcp_sockets_diag_append_text(out, "1 init=");
        out = tcp_sockets_diag_append_hex(out, sample->initialise_count);
        out = tcp_sockets_diag_append_text(out, " ready=");
        out = tcp_sockets_diag_append_hex(out, sample->ready_count);
        out = tcp_sockets_diag_append_text(out, " link=");
        out = tcp_sockets_diag_append_decimal(out, (0U != sample->link_up) ? 1U : 0U);
    }
    else
    {
        out = tcp_sockets_diag_append_text(out, "0");
    }
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
}

static void tcp_sockets_report_route_sample(uint32_t backend, uint32_t phase,
                                             const TCPRouteCacheSample_t *sample,
                                             char line[96],
                                             TCPConnectDiagnosticWriter_t writer)
{
    char *out = line;
    uint32_t state = sample->state;
    out = tcp_sockets_diag_append_text(out, "TCP sampled route b=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " p=");
    out = tcp_sockets_diag_append_decimal(out, phase);
    out = tcp_sockets_diag_append_text(out, " cap=");
    if ((backend == TCP_CONNECT_BACKEND_FREERTOS_TCP) &&
        (TCP_SAMPLE_AVAILABLE == sample->capability))
    {
        if ((state > TCP_ROUTE_SAMPLE_READY) ||
            (sample->route_kind > TCP_ROUTE_SAMPLE_GATEWAY))
        {
            state = TCP_ROUTE_SAMPLE_INVALID;
        }
        out = tcp_sockets_diag_append_text(out, "1 state=");
        out = tcp_sockets_diag_append_decimal(out, state);
        if (TCP_ROUTE_SAMPLE_READY == state)
        {
            out = tcp_sockets_diag_append_text(out, " dnsup=");
            out = tcp_sockets_diag_append_decimal(out,
                     (0U != sample->dns_endpoint_up) ? 1U : 0U);
            out = tcp_sockets_diag_append_text(out, " route=");
            out = tcp_sockets_diag_append_decimal(out, sample->route_kind);
            if (TCP_ROUTE_SAMPLE_NO_ROUTE != sample->route_kind)
            {
                out = tcp_sockets_diag_append_text(out, " up=");
                out = tcp_sockets_diag_append_decimal(out,
                         (0U != sample->route_endpoint_up) ? 1U : 0U);
                out = tcp_sockets_diag_append_text(out, " cache=");
                out = tcp_sockets_diag_append_decimal(out,
                         (0U != sample->cache_valid) ? 1U : 0U);
            }
        }
    }
    else
    {
        out = tcp_sockets_diag_append_text(out, "0");
    }
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
}
#endif

/* Explicit failure-task call only. Reuses the caller's existing 96-byte row.
 * phase0/1 mean before/after CONNECT, not per-request or per-packet snapshots.
 * No subtraction is performed: existing epoch counts retain modulo semantics.
 * No new row appears for success, feature-off, invalid backend or NULL writer. */
static void tcp_sockets_report_sampled_network_failure(uint32_t backend,
                                     const TCPConnectNetworkSample_t *before,
                                     const TCPConnectNetworkSample_t *after,
                                     uint32_t valid, uint32_t status,
                                     char line[96],
                                     TCPConnectDiagnosticWriter_t writer)
{
#if (TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS == 1)
    char *out;
    if ((0U == status) || (NULL == writer) || (NULL == line) ||
        (backend < TCP_CONNECT_BACKEND_FREERTOS_TCP) ||
        (backend > TCP_CONNECT_BACKEND_WIFI_DA16600))
    {
        return;
    }
    out = tcp_sockets_diag_append_text(line, "TCP sampled window b=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " valid=");
    valid = ((1U == valid) && (NULL != before) && (NULL != after)) ? 1U : 0U;
    out = tcp_sockets_diag_append_decimal(out, valid);
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
    if (0U != valid)
    {
        tcp_sockets_report_epoch_sample(backend, 0U, &before->epoch, line, writer);
        tcp_sockets_report_route_sample(backend, 0U, &before->route, line, writer);
        tcp_sockets_report_epoch_sample(backend, 1U, &after->epoch, line, writer);
        tcp_sockets_report_route_sample(backend, 1U, &after->route, line, writer);
    }
#else
    (void)backend; (void)before; (void)after; (void)valid;
    (void)status; (void)line; (void)writer;
#endif
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

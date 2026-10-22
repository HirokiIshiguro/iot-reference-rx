/* RX671 application observer adapter; contains no credentials or network data. */
#ifndef TCP_RNG_DNS_OBSERVATION_H
#define TCP_RNG_DNS_OBSERVATION_H
#include "FreeRTOS.h"
#include "task.h"
#include "tcp_connect_diagnostics.h"

#if (TCP_SOCKETS_ENABLE_RANDOM_DIAGNOSTICS == 1)
typedef struct TcpRngDnsConnectWindow
{
    TaskHandle_t caller;
    TickType_t started_at;
    TickType_t finished_at;
    BaseType_t complete;
#if (TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS == 1)
    TCPConnectNetworkSample_t network_before;
    TCPConnectNetworkSample_t network_after;
#endif
} TcpRngDnsConnectWindow_t;

#if (TCP_SOCKETS_ENABLE_EPOCH_ROUTE_DIAGNOSTICS == 1)
/* RX671-owned read-only epoch provider; RX72 can pass NULL to common capture. */
void tcp_rng_dns_observation_get_rx_epoch(uint32_t backend,
                                           TCPRxEpochSample_t *sample);
#endif

/* One static queue; call before FreeRTOS_IPInit. Repeated calls never reset it. */
void tcp_rng_dns_observation_init(void);
void tcp_rng_dns_observation_connect_begin(TcpRngDnsConnectWindow_t *window);
void tcp_rng_dns_observation_connect_end(TcpRngDnsConnectWindow_t *window);
/* Status0 is silent and never drains. Writer must consume each line on return. */
void tcp_rng_dns_observation_report_failure(const TcpRngDnsConnectWindow_t *window,
                                           BaseType_t status,
                                           TCPConnectDiagnosticWriter_t writer);
#endif
#endif

/*
 * Application hooks required by FreeRTOS+TCP.
 */
#include <stdint.h>

#include "FreeRTOS.h"
#include "FreeRTOS_IP.h"
#include "FreeRTOS_DHCP.h"

#include "debug_uart.h"

extern volatile uint32_t g_tcp_random_requests;
extern volatile uint32_t g_tcp_random_successes;
extern volatile uint32_t g_tcp_random_session_failures;
extern volatile uint32_t g_tcp_random_generate_failures;
extern volatile uint32_t g_tcp_random_last_ck_rv;
extern volatile uint32_t g_whd_network_rx_frames;
extern volatile uint32_t g_whd_network_rx_to_ip;
extern volatile uint32_t g_whd_network_rx_no_buffer;
extern volatile uint32_t g_whd_network_rx_drop_not_ready;
extern volatile uint32_t g_whd_network_rx_drop_filter;
extern volatile uint32_t g_whd_network_rx_drop_no_endpoint;
extern volatile uint32_t g_whd_network_rx_drop_queue;
extern volatile uint32_t g_whd_network_tx_frames;
extern volatile uint32_t g_whd_network_tx_no_buffer;
extern volatile uint32_t g_whd_network_tx_drop_not_ready;
extern volatile uint32_t g_whd_network_tx_drop_no_data;

volatile uint32_t g_freertos_tcp_network_up;
volatile uint32_t g_freertos_tcp_ip_address;
volatile uint32_t g_freertos_tcp_netmask;
volatile uint32_t g_freertos_tcp_gateway;
volatile uint32_t g_freertos_tcp_dns;
volatile uint32_t g_freertos_tcp_ping_status;
volatile uint32_t g_freertos_tcp_ping_identifier;
volatile uint32_t g_freertos_tcp_dhcp_hook_count;
volatile uint32_t g_freertos_tcp_dhcp_phase;
volatile uint32_t g_freertos_tcp_dhcp_ip;
volatile uint32_t g_freertos_tcp_dhcp_lease_acquired;
volatile uint32_t g_freertos_tcp_dhcp_static_fallback;
volatile uint32_t g_iptrace_network_event_count;
volatile uint32_t g_iptrace_network_rx_event_count;
volatile uint32_t g_iptrace_network_tx_event_count;
volatile uint32_t g_iptrace_network_last_event;
volatile uint32_t g_iptrace_network_input_count;
volatile uint32_t g_iptrace_network_input_arp;
volatile uint32_t g_iptrace_network_input_ipv4;
volatile uint32_t g_iptrace_network_input_icmp;
volatile uint32_t g_iptrace_network_input_udp;
volatile uint32_t g_iptrace_network_input_tcp;
volatile uint32_t g_iptrace_network_input_last_length;
volatile uint32_t g_iptrace_network_input_last_ethertype;
volatile uint32_t g_iptrace_network_input_last_protocol;
volatile uint32_t g_iptrace_icmp_packet_received_count;
volatile uint32_t g_iptrace_sending_ping_reply_count;
volatile uint32_t g_iptrace_sending_ping_reply_last_ip;
volatile uint32_t g_iptrace_network_output_count;
volatile uint32_t g_iptrace_network_output_arp;
volatile uint32_t g_iptrace_network_output_ipv4;
volatile uint32_t g_iptrace_network_output_icmp;
volatile uint32_t g_iptrace_network_output_udp;
volatile uint32_t g_iptrace_network_output_tcp;
volatile uint32_t g_iptrace_network_output_last_length;
volatile uint32_t g_iptrace_network_output_last_ethertype;
volatile uint32_t g_iptrace_network_output_last_protocol;

static uint32_t pack_be16(const uint8_t * p)
{
    return (((uint32_t)p[0] << 8) | (uint32_t)p[1]);
}

static void count_trace_protocol(const uint8_t * buffer, uint32_t length,
                                 volatile uint32_t * arp_count,
                                 volatile uint32_t * ipv4_count,
                                 volatile uint32_t * icmp_count,
                                 volatile uint32_t * udp_count,
                                 volatile uint32_t * tcp_count,
                                 volatile uint32_t * last_ethertype,
                                 volatile uint32_t * last_protocol)
{
    if ((NULL != buffer) && (length >= 14U))
    {
        uint32_t ethertype = pack_be16(&buffer[12]);

        *last_ethertype = ethertype;
        *last_protocol = 0U;

        if (0x0806U == ethertype)
        {
            (*arp_count)++;
        }
        else if (0x0800U == ethertype)
        {
            (*ipv4_count)++;
            if (length >= 24U)
            {
                uint32_t protocol = (uint32_t)buffer[23];

                *last_protocol = protocol;
                if (1U == protocol)
                {
                    (*icmp_count)++;
                }
                else if (6U == protocol)
                {
                    (*tcp_count)++;
                }
                else if (17U == protocol)
                {
                    (*udp_count)++;
                }
            }
        }
    }
}

void vWifiRx671IpTraceNetworkEventReceived(uint32_t event)
{
    g_iptrace_network_event_count++;
    g_iptrace_network_last_event = event;

    if (1U == event)
    {
        g_iptrace_network_rx_event_count++;
    }
    else if (2U == event)
    {
        g_iptrace_network_tx_event_count++;
    }
}

void vWifiRx671IpTraceNetworkInterfaceInput(uint32_t length, const uint8_t * buffer)
{
    g_iptrace_network_input_count++;
    g_iptrace_network_input_last_length = length;
    count_trace_protocol(buffer, length,
                         &g_iptrace_network_input_arp,
                         &g_iptrace_network_input_ipv4,
                         &g_iptrace_network_input_icmp,
                         &g_iptrace_network_input_udp,
                         &g_iptrace_network_input_tcp,
                         &g_iptrace_network_input_last_ethertype,
                         &g_iptrace_network_input_last_protocol);
}

void vWifiRx671IpTraceNetworkInterfaceOutput(uint32_t length, const uint8_t * buffer)
{
    g_iptrace_network_output_count++;
    g_iptrace_network_output_last_length = length;
    count_trace_protocol(buffer, length,
                         &g_iptrace_network_output_arp,
                         &g_iptrace_network_output_ipv4,
                         &g_iptrace_network_output_icmp,
                         &g_iptrace_network_output_udp,
                         &g_iptrace_network_output_tcp,
                         &g_iptrace_network_output_last_ethertype,
                         &g_iptrace_network_output_last_protocol);
}

void vWifiRx671IpTraceIcmpPacketReceived(void)
{
    g_iptrace_icmp_packet_received_count++;
}

void vWifiRx671IpTraceSendingPingReply(uint32_t ip_address)
{
    g_iptrace_sending_ping_reply_count++;
    g_iptrace_sending_ping_reply_last_ip = ip_address;
}

void vWifiRx671IpTraceDhcpSucceeded(uint32_t ip_address)
{
    g_freertos_tcp_dhcp_ip = ip_address;
    g_freertos_tcp_dhcp_static_fallback = 0U;
    g_freertos_tcp_dhcp_lease_acquired = 1U;
    debug_puts("FreeRTOS+TCP DHCP lease acquired\r\n");
}

void vWifiRx671IpTraceDhcpStaticFallback(uint32_t ip_address)
{
    g_freertos_tcp_dhcp_ip = ip_address;
    g_freertos_tcp_dhcp_lease_acquired = 0U;
    g_freertos_tcp_dhcp_static_fallback = 1U;
}

static void log_dhcp_path_counts(void)
{
    /* Called only by the IP task; avoid adding 192 bytes to its stack. */
    static char line[192];
    char * p = append_text(line, "RX671 DHCP RNG: req=");

    /* These are task-context status snapshots, not an atomic event ledger.
     * Do not include random bytes, packet headers, addresses or credentials. */
    p = append_dec32(p, g_tcp_random_requests);
    p = append_text(p, " ok=");
    p = append_dec32(p, g_tcp_random_successes);
    p = append_text(p, " session_fail=");
    p = append_dec32(p, g_tcp_random_session_failures);
    p = append_text(p, " generate_fail=");
    p = append_dec32(p, g_tcp_random_generate_failures);
    p = append_text(p, " ck=");
    p = append_hex32(p, g_tcp_random_last_ck_rv);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);

    p = append_text(line, "RX671 DHCP IP: rx=");
    p = append_dec32(p, g_iptrace_network_input_count);
    p = append_text(p, " tx=");
    p = append_dec32(p, g_iptrace_network_output_count);
    p = append_text(p, " rx_udp=");
    p = append_dec32(p, g_iptrace_network_input_udp);
    p = append_text(p, " tx_udp=");
    p = append_dec32(p, g_iptrace_network_output_udp);
    p = append_text(p, " hook=");
    p = append_dec32(p, g_freertos_tcp_dhcp_hook_count);
    p = append_text(p, " phase=");
    p = append_dec32(p, g_freertos_tcp_dhcp_phase);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);

    p = append_text(line, "RX671 DHCP WHD RX: frames=");
    p = append_dec32(p, g_whd_network_rx_frames);
    p = append_text(p, " to_ip=");
    p = append_dec32(p, g_whd_network_rx_to_ip);
    p = append_text(p, " no_buf=");
    p = append_dec32(p, g_whd_network_rx_no_buffer);
    p = append_text(p, " not_ready=");
    p = append_dec32(p, g_whd_network_rx_drop_not_ready);
    p = append_text(p, " filter=");
    p = append_dec32(p, g_whd_network_rx_drop_filter);
    p = append_text(p, " no_ep=");
    p = append_dec32(p, g_whd_network_rx_drop_no_endpoint);
    p = append_text(p, " queue=");
    p = append_dec32(p, g_whd_network_rx_drop_queue);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);

    p = append_text(line, "RX671 DHCP WHD TX: frames=");
    p = append_dec32(p, g_whd_network_tx_frames);
    p = append_text(p, " no_buf=");
    p = append_dec32(p, g_whd_network_tx_no_buffer);
    p = append_text(p, " not_ready=");
    p = append_dec32(p, g_whd_network_tx_drop_not_ready);
    p = append_text(p, " no_data=");
    p = append_dec32(p, g_whd_network_tx_drop_no_data);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

void vApplicationIPNetworkEventHook(eIPCallbackEvent_t event)
{
    if (eNetworkUp == event)
    {
        FreeRTOS_GetAddressConfiguration((uint32_t *)&g_freertos_tcp_ip_address,
                                         (uint32_t *)&g_freertos_tcp_netmask,
                                         (uint32_t *)&g_freertos_tcp_gateway,
                                         (uint32_t *)&g_freertos_tcp_dns);
        g_freertos_tcp_network_up = 1U;
        /* The DHCP fallback trace runs inside taskENTER_CRITICAL(), where
         * debug_uart deliberately drops TX. Report the state from this same
         * task's network-up callback after that critical section has ended. */
        if (0U != g_freertos_tcp_dhcp_static_fallback)
        {
            debug_puts("FreeRTOS+TCP DHCP static fallback\r\n");
        }
        debug_puts("FreeRTOS+TCP network up\r\n");
        log_dhcp_path_counts();
    }
    else
    {
        g_freertos_tcp_network_up = 0U;
        debug_puts("FreeRTOS+TCP network down\r\n");
    }
}

const char * pcApplicationHostnameHook(void)
{
    return "rx671-1yn";
}

eDHCPCallbackAnswer_t xApplicationDHCPHook(eDHCPCallbackPhase_t phase, uint32_t ip_address)
{
    g_freertos_tcp_dhcp_hook_count++;
    g_freertos_tcp_dhcp_phase = (uint32_t)phase;
    g_freertos_tcp_dhcp_ip = ip_address;

    return eDHCPContinue;
}

void vApplicationPingReplyHook(ePingReplyStatus_t status, uint16_t identifier)
{
    g_freertos_tcp_ping_status = (uint32_t)status;
    g_freertos_tcp_ping_identifier = (uint32_t)identifier;
}

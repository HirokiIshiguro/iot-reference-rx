/*
 * Application hooks required by FreeRTOS+TCP.
 */
#include <stdint.h>

#include "FreeRTOS.h"
#include "task.h"
#include "FreeRTOS_IP.h"
#include "FreeRTOS_DHCP.h"

#include "debug_uart.h"

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

static uint32_t g_random_state = 0x6711a9afUL;

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

void vApplicationIPNetworkEventHook(eIPCallbackEvent_t event)
{
    if (eNetworkUp == event)
    {
        FreeRTOS_GetAddressConfiguration((uint32_t *)&g_freertos_tcp_ip_address,
                                         (uint32_t *)&g_freertos_tcp_netmask,
                                         (uint32_t *)&g_freertos_tcp_gateway,
                                         (uint32_t *)&g_freertos_tcp_dns);
        g_freertos_tcp_network_up = 1U;
        debug_puts("FreeRTOS+TCP network up\r\n");
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

BaseType_t xApplicationGetRandomNumber(uint32_t * pul_number)
{
    uint32_t x = g_random_state;

    x ^= (x << 13);
    x ^= (x >> 17);
    x ^= (x << 5);
    x += (uint32_t)xTaskGetTickCount();
    g_random_state = x;

    if (NULL != pul_number)
    {
        *pul_number = x;
    }

    return pdTRUE;
}

eDHCPCallbackAnswer_t xApplicationDHCPHook(eDHCPCallbackPhase_t phase, uint32_t ip_address)
{
    g_freertos_tcp_dhcp_hook_count++;
    g_freertos_tcp_dhcp_phase = (uint32_t)phase;
    g_freertos_tcp_dhcp_ip = ip_address;

    return eDHCPContinue;
}

uint32_t ulApplicationGetNextSequenceNumber(uint32_t source_address,
                                            uint16_t source_port,
                                            uint32_t destination_address,
                                            uint16_t destination_port)
{
    uint32_t rnd;

    (void)xApplicationGetRandomNumber(&rnd);
    return rnd ^ source_address ^ destination_address ^
           ((uint32_t)source_port << 16) ^ (uint32_t)destination_port;
}

void vApplicationPingReplyHook(ePingReplyStatus_t status, uint16_t identifier)
{
    g_freertos_tcp_ping_status = (uint32_t)status;
    g_freertos_tcp_ping_identifier = (uint32_t)identifier;
}

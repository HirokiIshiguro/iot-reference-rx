/*
 * FreeRTOS+TCP configuration for EK-RX671 + Murata Type 1YN WHD bring-up.
 */
#ifndef FREERTOS_IP_CONFIG_H
#define FREERTOS_IP_CONFIG_H

#include "FreeRTOS.h"

#define ipconfigBYTE_ORDER                         pdFREERTOS_LITTLE_ENDIAN

#define ipconfigHAS_DEBUG_PRINTF                  0
#define ipconfigHAS_PRINTF                        1

#define ipconfigUSE_NETWORK_EVENT_HOOK            1
#define ipconfigUSE_DHCP                          1
#define ipconfigUSE_DHCP_HOOK                     1
#define ipconfigDHCP_REGISTER_HOSTNAME            1

#define ipconfigUSE_IPv4                          1
#define ipconfigUSE_IPv6                          0
#define ipconfigIPv4_BACKWARD_COMPATIBLE          1

#define ipconfigUSE_TCP                           1
#define ipconfigUSE_TCP_WIN                       1
#define ipconfigTCP_MSS                           ( ipconfigNETWORK_MTU - 40 )
#define ipconfigTCP_RX_BUFFER_LENGTH              ( 16 * ipconfigTCP_MSS )
#define ipconfigTCP_TX_BUFFER_LENGTH              ( 16 * ipconfigTCP_MSS )
#ifndef RX671_TCP_WIN_SEG_COUNT
#define RX671_TCP_WIN_SEG_COUNT                   128
#endif
#define ipconfigTCP_WIN_SEG_COUNT                 RX671_TCP_WIN_SEG_COUNT
#define ipconfigUSE_DNS                           1
#define ipconfigUSE_DNS_CACHE                     1
#define ipconfigUSE_LLMNR                         0
#define ipconfigUSE_NBNS                          0
#define ipconfigUSE_MDNS                          0

#define ipconfigNETWORK_MTU                       1500
#ifndef RX671_NETWORK_BUFFER_DESCRIPTORS
#define RX671_NETWORK_BUFFER_DESCRIPTORS          48
#endif
#define ipconfigNUM_NETWORK_BUFFER_DESCRIPTORS    RX671_NETWORK_BUFFER_DESCRIPTORS
#define ipconfigEVENT_QUEUE_LENGTH                ( ipconfigNUM_NETWORK_BUFFER_DESCRIPTORS + 8 )
#define ipconfigIP_TASK_PRIORITY                  3
#define ipconfigIP_TASK_STACK_SIZE_WORDS          1536

#define ipconfigARP_CACHE_ENTRIES                 6
#define ipconfigMAX_ARP_RETRANSMISSIONS           5
#define ipconfigMAX_ARP_AGE                       150

#define ipconfigDRIVER_INCLUDED_RX_IP_CHECKSUM    0
#define ipconfigDRIVER_INCLUDED_TX_IP_CHECKSUM    0
#define ipconfigETHERNET_DRIVER_FILTERS_PACKETS   0
#define ipconfigETHERNET_DRIVER_FILTERS_FRAME_TYPES 1
#define ipconfigZERO_COPY_RX_DRIVER               0
#define ipconfigZERO_COPY_TX_DRIVER               0

#define ipconfigSUPPORT_OUTGOING_PINGS            1
#define ipconfigREPLY_TO_INCOMING_PINGS           1
#define ipconfigSOCKET_HAS_USER_WAKE_CALLBACK     0
#define ipconfigCHECK_IP_QUEUE_SPACE              1

void vWifiRx671IpTraceNetworkEventReceived(uint32_t event);
void vWifiRx671IpTraceNetworkInterfaceInput(uint32_t length, const uint8_t * buffer);
void vWifiRx671IpTraceNetworkInterfaceOutput(uint32_t length, const uint8_t * buffer);
void vWifiRx671IpTraceIcmpPacketReceived(void);
void vWifiRx671IpTraceSendingPingReply(uint32_t ip_address);
void vWifiRx671IpTraceDhcpSucceeded(uint32_t ip_address);
void vWifiRx671IpTraceDhcpStaticFallback(uint32_t ip_address);

#define iptraceNETWORK_EVENT_RECEIVED(eEvent) \
    vWifiRx671IpTraceNetworkEventReceived((uint32_t)(eEvent))
#define iptraceNETWORK_INTERFACE_INPUT(uxDataLength, pucEthernetBuffer) \
    vWifiRx671IpTraceNetworkInterfaceInput((uint32_t)(uxDataLength), (const uint8_t *)(pucEthernetBuffer))
#define iptraceNETWORK_INTERFACE_OUTPUT(uxDataLength, pucEthernetBuffer) \
    vWifiRx671IpTraceNetworkInterfaceOutput((uint32_t)(uxDataLength), (const uint8_t *)(pucEthernetBuffer))
#define iptraceICMP_PACKET_RECEIVED() \
    vWifiRx671IpTraceIcmpPacketReceived()
#define iptraceSENDING_PING_REPLY(ulIPAddress) \
    vWifiRx671IpTraceSendingPingReply((uint32_t)(ulIPAddress))
#define iptraceDHCP_SUCCEEDED(ulOfferedIPAddress) \
    vWifiRx671IpTraceDhcpSucceeded((uint32_t)(ulOfferedIPAddress))
#define iptraceDHCP_REQUESTS_FAILED_USING_DEFAULT_IP_ADDRESS(ulIPAddress) \
    vWifiRx671IpTraceDhcpStaticFallback((uint32_t)(ulIPAddress))

#endif /* FREERTOS_IP_CONFIG_H */

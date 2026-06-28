/*
 * WHD <-> FreeRTOS+TCP network glue.
 *
 * This first bridge deliberately uses copy RX/TX. It keeps WHD buffers and
 * FreeRTOS+TCP network buffers independent while the SDIO path is still being
 * tuned; later DTC/DMAC work can reduce or remove these copies.
 */
#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h"
#include "task.h"
#include "FreeRTOS_IP.h"
#include "FreeRTOS_IP_Private.h"
#include "FreeRTOS_Routing.h"
#include "NetworkBufferManagement.h"
#include "NetworkInterface.h"

#include "whd.h"
#include "whd_network_types.h"
#include "whd_port.h"
#include "whd_bringup.h"
#include "whd_wifi_api.h"

#define WHD_NETWORK_DEBUG_HEAD_BYTES    (64U)

#ifndef WHD_NETWORK_PROTOCOL_DIAG
#define WHD_NETWORK_PROTOCOL_DIAG       (1)
#endif

#ifndef WHD_NETWORK_READY_CHECK_EACH_TX
#define WHD_NETWORK_READY_CHECK_EACH_TX (1)
#endif

volatile uint32_t g_whd_network_rx_frames;
volatile uint32_t g_whd_network_rx_to_ip;
volatile uint32_t g_whd_network_rx_dropped;
volatile uint32_t g_whd_network_rx_no_buffer;
volatile uint32_t g_whd_network_rx_drop_not_ready;
volatile uint32_t g_whd_network_rx_drop_filter;
volatile uint32_t g_whd_network_rx_drop_no_endpoint;
volatile uint32_t g_whd_network_rx_drop_queue;
volatile uint32_t g_whd_network_rx_last_length;
volatile uint32_t g_whd_network_rx_last_filter;
volatile uint32_t g_whd_network_rx_last_ethertype;
volatile uint32_t g_whd_network_rx_last_dst_0_3;
volatile uint32_t g_whd_network_rx_last_dst_4_5;
volatile uint32_t g_whd_network_rx_last_src_0_3;
volatile uint32_t g_whd_network_rx_last_src_4_5;
volatile uint32_t g_whd_network_rx_last_ifp;
volatile uint32_t g_whd_network_rx_last_whd_buffer;
volatile uint32_t g_whd_network_rx_last_p_data;
volatile uint32_t g_whd_network_rx_last_network_buffer;
volatile uint32_t g_whd_network_rx_last_network_puc;
volatile uint32_t g_whd_network_rx_last_event_type;
volatile uint32_t g_whd_network_rx_last_event_pvdata;
volatile uint32_t g_whd_network_rx_last_send_result;
volatile uint32_t g_whd_network_rx_last_frame_head_length;
volatile uint8_t  g_whd_network_rx_last_frame_head[WHD_NETWORK_DEBUG_HEAD_BYTES];
volatile uint32_t g_whd_network_rx_last_network_head_length;
volatile uint8_t  g_whd_network_rx_last_network_head[WHD_NETWORK_DEBUG_HEAD_BYTES];
volatile uint32_t g_whd_network_rx_arp;
volatile uint32_t g_whd_network_rx_ipv4;
volatile uint32_t g_whd_network_rx_ipv6;
volatile uint32_t g_whd_network_rx_icmp;
volatile uint32_t g_whd_network_rx_udp;
volatile uint32_t g_whd_network_rx_tcp;
volatile uint32_t g_whd_network_tx_frames;
volatile uint32_t g_whd_network_tx_no_buffer;
volatile uint32_t g_whd_network_tx_drop_not_ready;
volatile uint32_t g_whd_network_tx_drop_no_data;
volatile uint32_t g_whd_network_tx_arp;
volatile uint32_t g_whd_network_tx_ipv4;
volatile uint32_t g_whd_network_tx_ipv6;
volatile uint32_t g_whd_network_tx_icmp;
volatile uint32_t g_whd_network_tx_udp;
volatile uint32_t g_whd_network_tx_tcp;
volatile uint32_t g_whd_network_tx_last_length;
volatile uint32_t g_whd_network_tx_last_ethertype;
volatile uint32_t g_whd_network_tx_last_dst_0_3;
volatile uint32_t g_whd_network_tx_last_dst_4_5;
volatile uint32_t g_whd_network_tx_last_src_0_3;
volatile uint32_t g_whd_network_tx_last_src_4_5;
volatile uint32_t g_whd_network_link_up;
volatile uint32_t g_whd_network_initialise_count;
volatile uint32_t g_whd_network_initialise_ready_count;
volatile uint32_t g_whd_network_initialise_last_ifp;
volatile uint32_t g_whd_network_initialise_last_result;
volatile uint32_t g_whd_network_phy_count;
volatile uint32_t g_whd_network_phy_ready_count;
volatile uint32_t g_whd_network_phy_last_result;
volatile uint32_t g_whd_network_fill_count;

static NetworkInterface_t * g_whd_network_interface;

static void capture_head(volatile uint8_t * p_dst, volatile uint32_t * p_captured,
                         const uint8_t * p_src, uint16_t length)
{
#if (WHD_NETWORK_PROTOCOL_DIAG != 0)
    uint32_t i;
    uint32_t captured = ((uint32_t)length > WHD_NETWORK_DEBUG_HEAD_BYTES) ?
                        WHD_NETWORK_DEBUG_HEAD_BYTES : (uint32_t)length;

    *p_captured = captured;
    for (i = 0U; i < captured; i++)
    {
        p_dst[i] = p_src[i];
    }
#else
    (void)p_dst;
    (void)p_src;
    (void)length;
    *p_captured = 0U;
#endif
}

static void clear_rx_debug_observation(void)
{
    uint32_t i;

    g_whd_network_rx_frames = 0U;
    g_whd_network_rx_to_ip = 0U;
    g_whd_network_rx_dropped = 0U;
    g_whd_network_rx_no_buffer = 0U;
    g_whd_network_rx_drop_not_ready = 0U;
    g_whd_network_rx_drop_filter = 0U;
    g_whd_network_rx_drop_no_endpoint = 0U;
    g_whd_network_rx_drop_queue = 0U;
    g_whd_network_rx_last_length = 0U;
    g_whd_network_rx_last_filter = 0U;
    g_whd_network_rx_last_ethertype = 0U;
    g_whd_network_rx_last_dst_0_3 = 0U;
    g_whd_network_rx_last_dst_4_5 = 0U;
    g_whd_network_rx_last_src_0_3 = 0U;
    g_whd_network_rx_last_src_4_5 = 0U;
    g_whd_network_rx_last_ifp = 0U;
    g_whd_network_rx_last_whd_buffer = 0U;
    g_whd_network_rx_last_p_data = 0U;
    g_whd_network_rx_last_network_buffer = 0U;
    g_whd_network_rx_last_network_puc = 0U;
    g_whd_network_rx_last_event_type = 0U;
    g_whd_network_rx_last_event_pvdata = 0U;
    g_whd_network_rx_last_send_result = 0U;
    g_whd_network_rx_last_frame_head_length = 0U;
    g_whd_network_rx_last_network_head_length = 0U;
    g_whd_network_rx_arp = 0U;
    g_whd_network_rx_ipv4 = 0U;
    g_whd_network_rx_ipv6 = 0U;
    g_whd_network_rx_icmp = 0U;
    g_whd_network_rx_udp = 0U;
    g_whd_network_rx_tcp = 0U;

    for (i = 0U; i < WHD_NETWORK_DEBUG_HEAD_BYTES; i++)
    {
        g_whd_network_rx_last_frame_head[i] = 0U;
        g_whd_network_rx_last_network_head[i] = 0U;
    }
}

static uint32_t pack_be32(const uint8_t * p)
{
    return (((uint32_t)p[0] << 24) |
            ((uint32_t)p[1] << 16) |
            ((uint32_t)p[2] << 8) |
            (uint32_t)p[3]);
}

static uint32_t pack_be16(const uint8_t * p)
{
    return (((uint32_t)p[0] << 8) | (uint32_t)p[1]);
}

static void count_protocol(const uint8_t * p_data, uint16_t length,
                           volatile uint32_t * p_arp,
                           volatile uint32_t * p_ipv4,
                           volatile uint32_t * p_ipv6,
                           volatile uint32_t * p_icmp,
                           volatile uint32_t * p_udp,
                           volatile uint32_t * p_tcp)
{
#if (WHD_NETWORK_PROTOCOL_DIAG != 0)
    if ((NULL != p_data) && (length >= 14U))
    {
        uint32_t ethertype = pack_be16(&p_data[12]);

        if (0x0806U == ethertype)
        {
            (*p_arp)++;
        }
        else if (0x0800U == ethertype)
        {
            (*p_ipv4)++;
            if (length >= 24U)
            {
                uint8_t protocol = p_data[23];

                if (1U == protocol)
                {
                    (*p_icmp)++;
                }
                else if (6U == protocol)
                {
                    (*p_tcp)++;
                }
                else if (17U == protocol)
                {
                    (*p_udp)++;
                }
            }
        }
        else if (0x86DDU == ethertype)
        {
            (*p_ipv6)++;
        }
    }
#else
    (void)p_data;
    (void)length;
    (void)p_arp;
    (void)p_ipv4;
    (void)p_ipv6;
    (void)p_icmp;
    (void)p_udp;
    (void)p_tcp;
#endif
}

static BaseType_t whd_network_is_ready(whd_interface_t ifp)
{
    return ((NULL != ifp) && (WHD_SUCCESS == whd_wifi_is_ready_to_transceive(ifp))) ? pdTRUE : pdFALSE;
}

static BaseType_t whd_network_is_ready_for_tx(whd_interface_t ifp)
{
#if (WHD_NETWORK_READY_CHECK_EACH_TX != 0)
    return whd_network_is_ready(ifp);
#else
    return ((NULL != ifp) && (0U != g_whd_network_link_up)) ? pdTRUE : pdFALSE;
#endif
}

static void whd_port_network_process_ethernet_data(whd_interface_t ifp, whd_buffer_t buffer)
{
    uint8_t * p_data;
    uint16_t length;
    NetworkBufferDescriptor_t * p_network_buffer;

    g_whd_network_rx_frames++;
    g_whd_network_rx_last_ifp = (uint32_t)(uintptr_t)ifp;
    g_whd_network_rx_last_whd_buffer = (uint32_t)(uintptr_t)buffer;

    p_data = g_whd_port_buffer_funcs.whd_buffer_get_current_piece_data_pointer(buffer);
    length = g_whd_port_buffer_funcs.whd_buffer_get_current_piece_size(buffer);
    g_whd_network_rx_last_p_data = (uint32_t)(uintptr_t)p_data;
    g_whd_network_rx_last_length = (uint32_t)length;
    if ((NULL != p_data) && (0U != length))
    {
        capture_head(g_whd_network_rx_last_frame_head,
                     &g_whd_network_rx_last_frame_head_length,
                     p_data, length);
    }

    if ((WHD_NETWORK_PROTOCOL_DIAG != 0) && (NULL != p_data) && (length >= 14U))
    {
        g_whd_network_rx_last_dst_0_3 = pack_be32(&p_data[0]);
        g_whd_network_rx_last_dst_4_5 = pack_be16(&p_data[4]);
        g_whd_network_rx_last_src_0_3 = pack_be32(&p_data[6]);
        g_whd_network_rx_last_src_4_5 = pack_be16(&p_data[10]);
        g_whd_network_rx_last_ethertype = pack_be16(&p_data[12]);
    }
    count_protocol(p_data, length,
                   &g_whd_network_rx_arp,
                   &g_whd_network_rx_ipv4,
                   &g_whd_network_rx_ipv6,
                   &g_whd_network_rx_icmp,
                   &g_whd_network_rx_udp,
                   &g_whd_network_rx_tcp);

    if ((NULL == p_data) || (0U == length) || (NULL == g_whd_network_interface))
    {
        g_whd_network_rx_drop_not_ready++;
        g_whd_network_rx_dropped++;
        whd_port_buffer_release_from_network(buffer);
        return;
    }

    g_whd_network_rx_last_filter = (uint32_t)eConsiderFrameForProcessing(p_data);
    if (g_whd_network_rx_last_filter != (uint32_t)eProcessBuffer)
    {
        g_whd_network_rx_drop_filter++;
        g_whd_network_rx_dropped++;
        whd_port_buffer_release_from_network(buffer);
        return;
    }

    p_network_buffer = pxGetNetworkBufferWithDescriptor((size_t)length, 0U);
    g_whd_network_rx_last_network_buffer = (uint32_t)(uintptr_t)p_network_buffer;
    if (NULL == p_network_buffer)
    {
        g_whd_network_rx_no_buffer++;
        whd_port_buffer_release_from_network(buffer);
        return;
    }

    g_whd_network_rx_last_network_puc = (uint32_t)(uintptr_t)p_network_buffer->pucEthernetBuffer;
    memcpy(p_network_buffer->pucEthernetBuffer, p_data, (size_t)length);
    capture_head(g_whd_network_rx_last_network_head,
                 &g_whd_network_rx_last_network_head_length,
                 p_network_buffer->pucEthernetBuffer, length);
    p_network_buffer->xDataLength = (size_t)length;
    p_network_buffer->pxInterface = g_whd_network_interface;
    p_network_buffer->pxEndPoint = FreeRTOS_MatchingEndpoint(g_whd_network_interface,
                                                             p_network_buffer->pucEthernetBuffer);

    whd_port_buffer_release_from_network(buffer);

    if (NULL == p_network_buffer->pxEndPoint)
    {
        g_whd_network_rx_drop_no_endpoint++;
        g_whd_network_rx_dropped++;
        vReleaseNetworkBufferAndDescriptor(p_network_buffer);
        return;
    }

    {
        IPStackEvent_t rx_event;
        BaseType_t send_result;

        rx_event.eEventType = eNetworkRxEvent;
        rx_event.pvData = (void *)p_network_buffer;
        g_whd_network_rx_last_event_type = (uint32_t)rx_event.eEventType;
        g_whd_network_rx_last_event_pvdata = (uint32_t)(uintptr_t)rx_event.pvData;

        send_result = xSendEventStructToIPTask(&rx_event, 0U);
        g_whd_network_rx_last_send_result = (uint32_t)send_result;
        if (send_result != pdPASS)
        {
            g_whd_network_rx_drop_queue++;
            g_whd_network_rx_dropped++;
            vReleaseNetworkBufferAndDescriptor(p_network_buffer);
            iptraceETHERNET_RX_EVENT_LOST();
        }
        else
        {
            g_whd_network_rx_to_ip++;
            iptraceNETWORK_INTERFACE_RECEIVE();
        }
    }
}

static BaseType_t whd_freertos_network_initialise(NetworkInterface_t * px_interface)
{
    whd_interface_t ifp = whd_bringup_get_interface();

    g_whd_network_initialise_count++;
    g_whd_network_initialise_last_ifp = (uint32_t)(uintptr_t)ifp;
    g_whd_network_interface = px_interface;
    clear_rx_debug_observation();
    g_whd_network_link_up = (uint32_t)whd_network_is_ready(ifp);
    if (0U != g_whd_network_link_up)
    {
        g_whd_network_initialise_ready_count++;
    }
    g_whd_network_initialise_last_result = (0U != g_whd_network_link_up) ? (uint32_t)pdPASS : (uint32_t)pdFAIL;

    return (0U != g_whd_network_link_up) ? pdPASS : pdFAIL;
}

static BaseType_t whd_freertos_network_output(NetworkInterface_t * px_interface,
                                              NetworkBufferDescriptor_t * const px_descriptor,
                                              BaseType_t x_release_after_send)
{
    BaseType_t result = pdFALSE;
    whd_interface_t ifp = whd_bringup_get_interface();
    whd_buffer_t whd_buffer = NULL;

    (void)px_interface;

    if ((NULL != px_descriptor) &&
        (NULL != px_descriptor->pucEthernetBuffer) &&
        (0U != px_descriptor->xDataLength) &&
        (pdTRUE == whd_network_is_ready_for_tx(ifp)))
    {
        whd_result_t whd_result;

        whd_result = g_whd_port_buffer_funcs.whd_host_buffer_get(&whd_buffer,
                                                                 WHD_NETWORK_TX,
                                                                 (unsigned short)px_descriptor->xDataLength,
                                                                 0UL);
        if ((WHD_SUCCESS == whd_result) && (NULL != whd_buffer))
        {
            uint8_t * p_data = g_whd_port_buffer_funcs.whd_buffer_get_current_piece_data_pointer(whd_buffer);

            if (NULL != p_data)
            {
                const uint8_t * p_tx = px_descriptor->pucEthernetBuffer;
                uint16_t tx_length = (uint16_t)px_descriptor->xDataLength;

                g_whd_network_tx_last_length = (uint32_t)tx_length;
                if ((WHD_NETWORK_PROTOCOL_DIAG != 0) && (tx_length >= 14U))
                {
                    g_whd_network_tx_last_dst_0_3 = pack_be32(&p_tx[0]);
                    g_whd_network_tx_last_dst_4_5 = pack_be16(&p_tx[4]);
                    g_whd_network_tx_last_src_0_3 = pack_be32(&p_tx[6]);
                    g_whd_network_tx_last_src_4_5 = pack_be16(&p_tx[10]);
                    g_whd_network_tx_last_ethertype = pack_be16(&p_tx[12]);
                }
                count_protocol(p_tx, tx_length,
                               &g_whd_network_tx_arp,
                               &g_whd_network_tx_ipv4,
                               &g_whd_network_tx_ipv6,
                               &g_whd_network_tx_icmp,
                               &g_whd_network_tx_udp,
                               &g_whd_network_tx_tcp);

                memcpy(p_data, px_descriptor->pucEthernetBuffer, px_descriptor->xDataLength);
                (void)g_whd_port_buffer_funcs.whd_buffer_set_size(whd_buffer,
                                                                  (unsigned short)px_descriptor->xDataLength);
                whd_network_send_ethernet_data(ifp, whd_buffer);
                g_whd_network_tx_frames++;
                result = pdTRUE;
                iptraceNETWORK_INTERFACE_TRANSMIT();
                whd_buffer = NULL;
            }
            else
            {
                g_whd_network_tx_drop_no_data++;
            }
        }
        else
        {
            g_whd_network_tx_no_buffer++;
        }
    }
    else
    {
        g_whd_network_tx_drop_not_ready++;
    }

    if (NULL != whd_buffer)
    {
        g_whd_port_buffer_funcs.whd_buffer_release(whd_buffer, WHD_NETWORK_TX);
    }

    if ((pdFALSE != x_release_after_send) && (NULL != px_descriptor))
    {
        vReleaseNetworkBufferAndDescriptor(px_descriptor);
    }

    return result;
}

BaseType_t xGetPhyLinkStatus(NetworkInterface_t * px_interface)
{
    (void)px_interface;

    g_whd_network_phy_count++;
    g_whd_network_link_up = (uint32_t)whd_network_is_ready(whd_bringup_get_interface());
    if (0U != g_whd_network_link_up)
    {
        g_whd_network_phy_ready_count++;
    }
    g_whd_network_phy_last_result = (0U != g_whd_network_link_up) ? (uint32_t)pdTRUE : (uint32_t)pdFALSE;
    return (0U != g_whd_network_link_up) ? pdTRUE : pdFALSE;
}

NetworkInterface_t * pxFillInterfaceDescriptor(BaseType_t x_emac_index, NetworkInterface_t * px_interface)
{
    (void)x_emac_index;

    g_whd_network_fill_count++;
    memset(px_interface, 0, sizeof(*px_interface));
    px_interface->pcName = "wlan0";
    px_interface->pvArgument = (void *)0;
    px_interface->pfInitialise = whd_freertos_network_initialise;
    px_interface->pfOutput = whd_freertos_network_output;
    px_interface->pfGetPhyLinkStatus = xGetPhyLinkStatus;

    g_whd_network_interface = px_interface;

    return FreeRTOS_AddNetworkInterface(px_interface);
}

whd_netif_funcs_t g_whd_port_netif_funcs =
{
    whd_port_network_process_ethernet_data,
};

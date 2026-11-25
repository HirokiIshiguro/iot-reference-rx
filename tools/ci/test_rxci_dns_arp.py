"""Exercise the socket wrapper DNS path with controlled DNS and ARP stubs."""
from pathlib import Path
import unittest

from tools.ci.tests import test_product_oss_api as host


WRAPPER = Path("Middleware/network_transport/sockets_wrapper/ports/freertos_plus_tcp/tcp_sockets_wrapper.c")


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required")
class DnsArpTests(unittest.TestCase):
    def test_primes_selected_dns_without_changing_resolver_fallback(self):
        source = (host.ROOT / WRAPPER).read_text(encoding="utf-8")
        resolver = source.split("    return socketStatus;\n}\n", 1)[1].split("\n/**", 1)[0]
        host.ProductApiTests().compile_run(
            r"""
#include <assert.h>
#include <stddef.h>
#include <stdint.h>

typedef unsigned int TickType_t;
#define ipconfigUSE_IPv6 0
#define ipconfigUSE_MDNS 0
#define ipconfigUSE_LLMNR 0
#define ipconfigUSE_DNS_CACHE 1
#define ipconfigENDPOINT_DNS_ADDRESS_COUNT 2
#define FREERTOS_INADDR_BROADCAST UINT32_MAX
#define pdFALSE 0
#define pdMS_TO_TICKS(value) (value)
#define pdTICKS_TO_MS(value) (value)
#define LogInfo(message) ((void)0)

typedef struct NetworkEndPoint
{
    struct
    {
        uint8_t ucDNSIndex;
        uint32_t ulDNSServerAddresses[2];
    } ipv4_settings;
    int up;
    struct NetworkEndPoint *next;
} NetworkEndPoint_t;
#define ENDPOINT_IS_IPv4(endpoint) ((endpoint) != NULL)

static NetworkEndPoint_t first = {{0, {0, 0}}, 1, NULL};
static NetworkEndPoint_t selected = {{1, {2, 3}}, 1, NULL};
static uint32_t numeric_address;
static uint32_t cached_address;
static unsigned int arp_calls;
static unsigned int dns_calls;

static NetworkEndPoint_t *FreeRTOS_FirstEndPoint(void *interface)
{
    (void)interface;
    return &first;
}

static NetworkEndPoint_t *FreeRTOS_NextEndPoint(void *interface, NetworkEndPoint_t *endpoint)
{
    (void)interface;
    return endpoint->next;
}

static int FreeRTOS_IsEndPointUp(NetworkEndPoint_t *endpoint) { return endpoint->up; }
static TickType_t xTaskGetTickCount(void) { return 0; }
static uint32_t FreeRTOS_inet_addr(const char *host) { (void)host; return numeric_address; }
static uint32_t FreeRTOS_dnslookup(const char *host) { (void)host; return cached_address; }
static uint32_t FreeRTOS_gethostbyname(const char *host) { (void)host; dns_calls++; return 7; }

static int xARPWaitResolution(uint32_t server, TickType_t timeout)
{
    assert(dns_calls == 0);
    assert(server == 3); /* Use the active DNS index, not the first server. */
    assert(timeout == 1000);
    arp_calls++;
    return -1; /* Continue normal DNS even when the ARP wait fails. */
}
"""
            + resolver
            + r"""
int main(void)
{
    first.next = &selected;

    numeric_address = 8;
    assert(prvResolveIPv4Address("192.0.2.1") == 8);
    assert(arp_calls == 0 && dns_calls == 0);

    numeric_address = 0;
    assert(prvResolveIPv4Address("broker.example") == 7);
    assert(arp_calls == 1 && dns_calls == 1);

    cached_address = 7;
    assert(prvResolveIPv4Address("broker.example") == 7);
    assert(arp_calls == 1 && dns_calls == 2);

    cached_address = 0;
    selected.up = 0;
    assert(prvResolveIPv4Address("broker.example") == 7);
    assert(arp_calls == 1 && dns_calls == 3);

    selected.up = 1;
    selected.ipv4_settings.ulDNSServerAddresses[1] = FREERTOS_INADDR_BROADCAST;
    assert(prvResolveIPv4Address("broker.example") == 7);
    assert(arp_calls == 1 && dns_calls == 4);
    return 0;
}
"""
        )

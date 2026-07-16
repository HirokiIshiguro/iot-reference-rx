/*
 * The RX72N RAM is split into two non-contiguous 512 KiB blocks. Keep the
 * existing 320 KiB heap region in lower RAM and use the otherwise empty gap
 * between upper-RAM networking data and the framebuffer as a second region.
 * heap_5 combines both regions without moving the fixed Ethernet/framebuffer
 * sections.
 */

#include <stdint.h>

#include "FreeRTOS.h"

#define RX72N_UPPER_HEAP_SIZE    (248U * 1024U)

#pragma section _FREERTOS_HEAP
uint8_t ucHeap[configTOTAL_HEAP_SIZE];
#pragma section

#pragma section _MULTI_TLS_HEAP
static uint8_t ucUpperHeap[RX72N_UPPER_HEAP_SIZE];
#pragma section

void vConfigureHeapRegions(void)
{
    static const HeapRegion_t xHeapRegions[] =
    {
        { ucHeap, sizeof(ucHeap) },
        { ucUpperHeap, sizeof(ucUpperHeap) },
        { NULL, 0U }
    };

    vPortDefineHeapRegions(xHeapRegions);
}

/*
 * The RX72N RAM is split into two non-contiguous 512 KiB blocks.  The TSIP
 * image needs more static RAM than the software-TLS image, so grow the lower
 * heap only into its verified linker gap and add a conservative second region
 * before the fixed framebuffer in upper RAM.
 */

#include <stdint.h>

#include "FreeRTOS.h"

#define RX72N_TSIP_UPPER_HEAP_SIZE    ( 148U * 1024U )

#pragma section _FREERTOS_HEAP
uint8_t ucHeap[configTOTAL_HEAP_SIZE];
#pragma section

#pragma section _MULTI_TLS_HEAP
static uint8_t ucUpperHeap[ RX72N_TSIP_UPPER_HEAP_SIZE ];
#pragma section

void vConfigureHeapRegions( void )
{
    static const HeapRegion_t xHeapRegions[] =
    {
        { ucHeap, sizeof( ucHeap ) },
        { ucUpperHeap, sizeof( ucUpperHeap ) },
        { NULL, 0U }
    };

    vPortDefineHeapRegions( xHeapRegions );
}

/*
* Copyright (c) 2026 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/**********************************************************************************************************************
 * File Name    : freertos_heap.c
 * Description  : Hands the FreeRTOS heap regions to heap_5.c. This file is shared by every project; the per-project
 *                values (region sizes) live in freertos_heap_config.h.
 *
 *                The first region is always present and is placed in section _FREERTOS_HEAP. The optional second
 *                region (FREERTOS_HEAP_UPPER_REGION_SIZE > 0) is placed in section _MULTI_TLS_HEAP. The section names
 *                are fixed here because #pragma section does not expand macros; the linker -start list of each
 *                project decides which RAM block each section lands in.
 *********************************************************************************************************************/

#include <stddef.h>
#include <stdint.h>

#include "FreeRTOS.h"
#include "freertos_heap_config.h"

#pragma section _FREERTOS_HEAP
uint8_t ucHeap[configTOTAL_HEAP_SIZE];
#pragma section

#if (FREERTOS_HEAP_UPPER_REGION_SIZE > 0U)
#pragma section _MULTI_TLS_HEAP
static uint8_t ucUpperHeap[FREERTOS_HEAP_UPPER_REGION_SIZE];
#pragma section
#endif

/* heap_5 requires this to be called once, before the first pvPortMalloc(). The regions must be listed in order of
 * ascending address and the list must end with { NULL, 0 }. */
void vConfigureHeapRegions(void)
{
    static const HeapRegion_t xHeapRegions[] =
    {
        { ucHeap, sizeof(ucHeap) },
#if (FREERTOS_HEAP_UPPER_REGION_SIZE > 0U)
        { ucUpperHeap, sizeof(ucUpperHeap) },
#endif
        { NULL, 0U }
    };

    vPortDefineHeapRegions(xHeapRegions);
}

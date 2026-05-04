/*
 * Place the FreeRTOS heap in the lower RX72N RAM block. The upper RAM block is
 * shared with Ethernet buffers and the framebuffer, so keeping the heap out of
 * it leaves headroom for network tuning.
 */

#include <stdint.h>

#include "FreeRTOS.h"

#pragma section _FREERTOS_HEAP
uint8_t ucHeap[configTOTAL_HEAP_SIZE];
#pragma section

/*
 * FreeRTOS heap storage for the RX72N Envision Kit.
 *
 * heap_4 manages one contiguous region, so the heap is this single
 * 320 KiB array (configTOTAL_HEAP_SIZE) in lower RAM.
 * configAPPLICATION_ALLOCATED_HEAP is 1, so heap_4.c declares
 * "extern uint8_t ucHeap[configTOTAL_HEAP_SIZE]" and uses the array defined
 * here. The array sits in the _FREERTOS_HEAP section, which the linker places
 * as B_FREERTOS_HEAP* before the fixed Ethernet buffers and framebuffer.
 */

#include <stdint.h>

#include "FreeRTOS.h"

#pragma section _FREERTOS_HEAP
uint8_t ucHeap[configTOTAL_HEAP_SIZE];
#pragma section

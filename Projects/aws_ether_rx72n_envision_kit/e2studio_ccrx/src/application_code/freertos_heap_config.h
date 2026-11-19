/*
* Copyright (c) 2026 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/**********************************************************************************************************************
 * File Name    : freertos_heap_config.h
 * Description  : Per-project values for the shared Common/FreeRTOS_common/freertos_heap.c.
 *                The size of the first heap region is configTOTAL_HEAP_SIZE (FreeRTOSConfig.h).
 *********************************************************************************************************************/

#ifndef FREERTOS_HEAP_CONFIG_H_
#define FREERTOS_HEAP_CONFIG_H_

/* The RX72N RAM is two separate 512 KiB blocks. The second region sits in upper RAM between the networking data and the frame buffer. */
/* Size in bytes of the second heap region. 0 means a single region. */
#define FREERTOS_HEAP_UPPER_REGION_SIZE    (248U * 1024U)

#endif /* FREERTOS_HEAP_CONFIG_H_ */

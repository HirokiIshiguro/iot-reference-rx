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

/* Size in bytes of the second heap region. 0 means a single region. */
#define FREERTOS_HEAP_UPPER_REGION_SIZE    (0U)

#endif /* FREERTOS_HEAP_CONFIG_H_ */

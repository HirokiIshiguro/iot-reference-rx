/*
 * Project-local FreeRTOS.h wrapper for TraceRecorderSource.
 *
 * FreeRTOSConfig.h is included before the RX port defines BaseType_t,
 * UBaseType_t, and TickType_t.  Including trcRecorder.h from FreeRTOSConfig.h
 * therefore breaks CC-RX builds with FreeRTOS V11.3.0.  Keep the upstream
 * FreeRTOS and TraceRecorder submodules untouched: include the real FreeRTOS.h
 * first, then install the Tracealyzer hooks after the port types exist.
 */
#ifndef AWS_WIFI_RX671_EK_FREERTOS_TRACE_WRAPPER_H
#define AWS_WIFI_RX671_EK_FREERTOS_TRACE_WRAPPER_H

#include "../../../../../Middleware/FreeRTOS/FreeRTOS-Kernel/include/FreeRTOS.h"

#if ( defined( CONFIG_USE_PERCEPIO_TRACE_RECORDER ) && ( CONFIG_USE_PERCEPIO_TRACE_RECORDER == 1 ) )
#include "trcRecorder.h"
#endif

#endif /* AWS_WIFI_RX671_EK_FREERTOS_TRACE_WRAPPER_H */

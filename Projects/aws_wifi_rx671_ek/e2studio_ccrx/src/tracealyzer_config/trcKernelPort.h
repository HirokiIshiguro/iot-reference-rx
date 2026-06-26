/*
 * Project-local wrapper for TraceRecorderSource's FreeRTOS kernel port.
 *
 * CC-RX cannot evaluate FreeRTOS queue type macros with casts inside #if
 * expressions, for example "((uint8_t)0U) != ((uint8_t)5U)".
 * TraceRecorderSource v4.11.0 performs such a preprocessor comparison while
 * installing traceQUEUE_* hooks.  Keep the upstream submodule untouched and
 * provide plain constants only while that header is parsed.
 */
#ifndef TRACE_RECORDER_RX671_TRC_KERNEL_PORT_WRAPPER_H
#define TRACE_RECORDER_RX671_TRC_KERNEL_PORT_WRAPPER_H

#if defined(__CCRX__)
#if defined(queueQUEUE_TYPE_BASE)
#define TRACE_RECORDER_RX671_QUEUE_TYPE_BASE_WAS_DEFINED
#undef queueQUEUE_TYPE_BASE
#endif

#if defined(queueQUEUE_TYPE_SET)
#define TRACE_RECORDER_RX671_QUEUE_TYPE_SET_WAS_DEFINED
#undef queueQUEUE_TYPE_SET
#endif

#define TRACE_RECORDER_RX671_QUEUE_TYPE_BASE_SHIM
#define TRACE_RECORDER_RX671_QUEUE_TYPE_SET_SHIM
#define queueQUEUE_TYPE_BASE 0U
#define queueQUEUE_TYPE_SET 5U
#endif

#include "../../../external/TraceRecorderSource/kernelports/FreeRTOS/include/trcKernelPort.h"

#if defined(TRACE_RECORDER_RX671_QUEUE_TYPE_SET_SHIM)
#undef queueQUEUE_TYPE_SET
#undef TRACE_RECORDER_RX671_QUEUE_TYPE_SET_SHIM
#endif
#if defined(TRACE_RECORDER_RX671_QUEUE_TYPE_SET_WAS_DEFINED)
#define queueQUEUE_TYPE_SET ((uint8_t)5U)
#undef TRACE_RECORDER_RX671_QUEUE_TYPE_SET_WAS_DEFINED
#endif

#if defined(TRACE_RECORDER_RX671_QUEUE_TYPE_BASE_SHIM)
#undef queueQUEUE_TYPE_BASE
#undef TRACE_RECORDER_RX671_QUEUE_TYPE_BASE_SHIM
#endif
#if defined(TRACE_RECORDER_RX671_QUEUE_TYPE_BASE_WAS_DEFINED)
#define queueQUEUE_TYPE_BASE ((uint8_t)0U)
#undef TRACE_RECORDER_RX671_QUEUE_TYPE_BASE_WAS_DEFINED
#endif

#endif /* TRACE_RECORDER_RX671_TRC_KERNEL_PORT_WRAPPER_H */

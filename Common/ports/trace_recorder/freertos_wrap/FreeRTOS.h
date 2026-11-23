/* Product include facade: original Kernel types first, then public Trace hooks.
 * No Kernel or recorder body is copied or modified. */
#ifndef PRODUCT_FREERTOS_TRACE_WRAPPER_H
#define PRODUCT_FREERTOS_TRACE_WRAPPER_H
#include "../../../../Middleware/FreeRTOS/FreeRTOS-Kernel/include/FreeRTOS.h"
#if ( CONFIG_USE_PERCEPIO_TRACE_RECORDER == 1 )
#include "trcRecorder.h"
#endif
#endif

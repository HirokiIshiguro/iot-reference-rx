/*
 * Trace Recorder stream port for RX SCI simple-SPI.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TRC_STREAM_PORT_H
#define TRC_STREAM_PORT_H

#include <stdint.h>

#include <trcTypes.h>
#include <trcStreamPortConfig.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct TraceStreamPortBuffer
{
    TraceUnsignedBaseType_t dummy;
} TraceStreamPortBuffer_t;

traceResult xTraceStreamPortInitialize(TraceStreamPortBuffer_t * pxBuffer);
int32_t prvTraceSpiWrite(void * pvData, uint32_t uiSize, uint32_t uiChannel, int32_t * piBytesWritten);
int32_t prvTraceSpiRead(void * pvData, uint32_t uiSize, int32_t * piBytesRead);

#define xTraceStreamPortWriteData(pvData, uiSize, uiChannel, piBytesWritten) \
    (prvTraceSpiWrite((pvData), (uiSize), (uiChannel), (piBytesWritten)) == 0 ? TRC_SUCCESS : TRC_FAIL)

#define xTraceStreamPortReadData(pvData, uiSize, piBytesRead) \
    (prvTraceSpiRead((pvData), (uiSize), (piBytesRead)) == 0 ? TRC_SUCCESS : TRC_FAIL)

#define xTraceStreamPortOnEnable(uiStartOption) ((void)(uiStartOption), TRC_SUCCESS)
#define xTraceStreamPortOnDisable() (TRC_SUCCESS)
#define xTraceStreamPortOnTraceBegin() (TRC_SUCCESS)
#define xTraceStreamPortOnTraceEnd() (TRC_SUCCESS)

#ifdef __cplusplus
}
#endif

#endif /* TRC_STREAM_PORT_H */

/*
 * Trace Recorder stream port for RX SCI simple-SPI.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <trcRecorder.h>

#if (TRC_USE_TRACEALYZER_RECORDER == 1)

#include "trace_spi_transport.h"

#if (TRC_CFG_STREAM_PORT_USE_INTERNAL_BUFFER == 0)
#error This StreamPort requires TRC_CFG_STREAM_PORT_USE_INTERNAL_BUFFER to be enabled.
#endif

static TraceStreamPortBuffer_t * pxStreamPortSpi;

traceResult xTraceStreamPortInitialize(TraceStreamPortBuffer_t * pxBuffer)
{
    if (pxBuffer == (void *) 0)
    {
        return TRC_FAIL;
    }

    pxStreamPortSpi = pxBuffer;
    return TRC_SUCCESS;
}

int32_t prvTraceSpiWrite(void * pvData, uint32_t uiSize, uint32_t uiChannel, int32_t * piBytesWritten)
{
    size_t bytes_written = 0u;

    (void) pxStreamPortSpi;
    (void) uiChannel;

    if (piBytesWritten == (void *) 0)
    {
        return -1;
    }

    *piBytesWritten = 0;
    if (TraceSpiTransport_Write(pvData, (size_t) uiSize, &bytes_written) != 0)
    {
        *piBytesWritten = (int32_t) bytes_written;
        return -1;
    }

    *piBytesWritten = (int32_t) bytes_written;
    return 0;
}

int32_t prvTraceSpiRead(void * pvData, uint32_t uiSize, int32_t * piBytesRead)
{
    size_t bytes_read = 0u;

    if (piBytesRead != (void *) 0)
    {
        *piBytesRead = 0;
    }

    if (TraceSpiTransport_Read(pvData, (size_t) uiSize, &bytes_read) != 0)
    {
        if (piBytesRead != (void *) 0)
        {
            *piBytesRead = (int32_t) bytes_read;
        }
        return -1;
    }

    if (piBytesRead != (void *) 0)
    {
        *piBytesRead = (int32_t) bytes_read;
    }

    return 0;
}

#endif /* (TRC_USE_TRACEALYZER_RECORDER == 1) */

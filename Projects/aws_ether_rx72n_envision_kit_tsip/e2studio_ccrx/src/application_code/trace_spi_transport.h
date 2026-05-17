/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#ifndef TRACE_SPI_TRANSPORT_H
#define TRACE_SPI_TRANSPORT_H

#include <stddef.h>
#include <stdint.h>

#define TRACE_SPI_TRANSPORT_FRAME_BYTES   (256u)
#define TRACE_SPI_TRANSPORT_PAYLOAD_BYTES (252u)
#define TRACE_SPI_TRANSPORT_MAGIC0        (0x54u)
#define TRACE_SPI_TRANSPORT_MAGIC1        (0x5Au)
#define TRACE_SPI_TRANSPORT_CONTROL_MAGIC0 (0x43u)
#define TRACE_SPI_TRANSPORT_CONTROL_MAGIC1 (0x54u)
#define TRACE_SPI_TRANSPORT_CONTROL_BUFFER_BYTES (128u)

extern volatile uint32_t g_trace_spi_initialized;
extern volatile uint32_t g_trace_spi_frame_count;
extern volatile uint32_t g_trace_spi_payload_byte_count;
extern volatile uint32_t g_trace_spi_error_count;
extern volatile uint32_t g_trace_spi_timeout_count;
extern volatile uint32_t g_trace_spi_last_error;
extern volatile uint32_t g_trace_spi_control_frame_count;
extern volatile uint32_t g_trace_spi_control_byte_count;
extern volatile uint32_t g_trace_spi_control_read_count;
extern volatile uint32_t g_trace_spi_control_drop_count;

int TraceSpiTransport_Init(void);
int TraceSpiTransport_Write(const void * p_data, size_t length, size_t * p_bytes_written);
int TraceSpiTransport_Read(void * p_data, size_t length, size_t * p_bytes_read);

#endif /* TRACE_SPI_TRANSPORT_H */

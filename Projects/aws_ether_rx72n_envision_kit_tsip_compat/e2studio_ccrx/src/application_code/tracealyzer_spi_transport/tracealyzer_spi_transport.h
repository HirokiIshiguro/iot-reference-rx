#ifndef TRACEALYZER_SPI_TRANSPORT_H
#define TRACEALYZER_SPI_TRANSPORT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRACE_SPI_MAGIC0 ((uint8_t)'T')
#define TRACE_SPI_MAGIC1 ((uint8_t)'Z')
#define TRACE_SPI_MAGIC2 ((uint8_t)'S')
#define TRACE_SPI_MAGIC3 ((uint8_t)'P')
#define TRACE_SPI_VERSION 1u
#define TRACE_SPI_MAX_PAYLOAD 512u

typedef enum trace_spi_channel
{
    TRACE_SPI_CHANNEL_TRACE_UP = 0u,
    TRACE_SPI_CHANNEL_COMMAND_DOWN = 1u,
    TRACE_SPI_CHANNEL_CONTROL = 2u
} trace_spi_channel_t;

typedef struct trace_spi_header
{
    uint8_t magic[4];
    uint8_t version;
    uint8_t channel;
    uint16_t sequence;
    uint16_t payload_length;
    uint16_t header_crc;
} trace_spi_header_t;

uint16_t TraceSpi_Crc16Ccitt(const uint8_t *data, size_t length);

void TraceSpi_InitHeader(trace_spi_header_t *header,
                         trace_spi_channel_t channel,
                         uint16_t sequence,
                         uint16_t payload_length);

int TraceSpi_IsHeaderValid(const trace_spi_header_t *header);

#ifdef __cplusplus
}
#endif

#endif

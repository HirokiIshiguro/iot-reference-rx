#include "tracealyzer_spi_transport.h"

uint16_t TraceSpi_Crc16Ccitt(const uint8_t *data, size_t length)
{
    uint16_t crc = 0xFFFFu;
    size_t index;

    if (data == NULL)
    {
        return 0u;
    }

    for (index = 0u; index < length; index++)
    {
        uint8_t bit;
        crc ^= (uint16_t)data[index] << 8;
        for (bit = 0u; bit < 8u; bit++)
        {
            if ((crc & 0x8000u) != 0u)
            {
                crc = (uint16_t)((crc << 1) ^ 0x1021u);
            }
            else
            {
                crc = (uint16_t)(crc << 1);
            }
        }
    }

    return crc;
}

void TraceSpi_InitHeader(trace_spi_header_t *header,
                         trace_spi_channel_t channel,
                         uint16_t sequence,
                         uint16_t payload_length)
{
    if (header == NULL)
    {
        return;
    }

    header->magic[0] = TRACE_SPI_MAGIC0;
    header->magic[1] = TRACE_SPI_MAGIC1;
    header->magic[2] = TRACE_SPI_MAGIC2;
    header->magic[3] = TRACE_SPI_MAGIC3;
    header->version = TRACE_SPI_VERSION;
    header->channel = (uint8_t)channel;
    header->sequence = sequence;
    header->payload_length = payload_length;
    header->header_crc = 0u;
    header->header_crc = TraceSpi_Crc16Ccitt((const uint8_t *)header,
                                             offsetof(trace_spi_header_t, header_crc));
}

int TraceSpi_IsHeaderValid(const trace_spi_header_t *header)
{
    uint16_t crc;

    if (header == NULL)
    {
        return 0;
    }

    if ((header->magic[0] != TRACE_SPI_MAGIC0) ||
        (header->magic[1] != TRACE_SPI_MAGIC1) ||
        (header->magic[2] != TRACE_SPI_MAGIC2) ||
        (header->magic[3] != TRACE_SPI_MAGIC3))
    {
        return 0;
    }

    if (header->version != TRACE_SPI_VERSION)
    {
        return 0;
    }

    if (header->payload_length > TRACE_SPI_MAX_PAYLOAD)
    {
        return 0;
    }

    crc = TraceSpi_Crc16Ccitt((const uint8_t *)header,
                              offsetof(trace_spi_header_t, header_crc));
    return crc == header->header_crc;
}

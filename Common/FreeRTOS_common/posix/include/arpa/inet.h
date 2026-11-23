/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef RX_POSIX_ARPA_INET_H
#define RX_POSIX_ARPA_INET_H

#include <stdint.h>

/* Product POSIX byte-order port; independent of the selected TCP/IP backend.
 * Reading an object's representation through unsigned char is defined by C.
 * The compiler can fold this constant endian probe for the target CPU. */
static inline int rx_posix_is_little_endian(void)
{
    const uint16_t value = 1U;
    return *(const unsigned char *)&value == 1U;
}

static inline uint16_t htons(uint16_t value)
{
    return rx_posix_is_little_endian() ?
        (uint16_t)((value << 8) | (value >> 8)) : value;
}

static inline uint16_t ntohs(uint16_t value)
{
    return htons(value);
}

static inline uint32_t htonl(uint32_t value)
{
    return rx_posix_is_little_endian() ?
        ((value & 0x000000FFUL) << 24) | ((value & 0x0000FF00UL) << 8) |
        ((value & 0x00FF0000UL) >> 8) | ((value & 0xFF000000UL) >> 24) : value;
}

static inline uint32_t ntohl(uint32_t value)
{
    return htonl(value);
}

#endif

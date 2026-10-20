/* Common TCP-wrapper diagnostics. SPDX-License-Identifier: MIT */
#ifndef TCP_CONNECT_DIAGNOSTICS_H
#define TCP_CONNECT_DIAGNOSTICS_H

#include <stddef.h>
#include <stdint.h>

#define TCP_CONNECT_BACKEND_FREERTOS_TCP       (1U)
#define TCP_CONNECT_BACKEND_CELLULAR            (2U)
#define TCP_CONNECT_BACKEND_WIFI_DA16600        (3U)

#define TCP_CONNECT_STAGE_NONE                 (0U)
#define TCP_CONNECT_STAGE_SOCKET_CREATION      (1U)
#define TCP_CONNECT_STAGE_SOCKET_CONFIGURATION (2U)
#define TCP_CONNECT_STAGE_ADDRESS_RESOLUTION   (3U)
#define TCP_CONNECT_STAGE_INITIAL_CONNECT      (4U)
#define TCP_CONNECT_STAGE_EXPLICIT_CONNECT_WAIT (5U)

typedef void (*TCPConnectDiagnosticWriter_t)(const char *line);

static char *tcp_sockets_diag_append_text(char *out, const char *text)
{
    while ('\0' != *text)
    {
        *out++ = *text++;
    }
    return out;
}

static char *tcp_sockets_diag_append_decimal(char *out, uint32_t value)
{
    char digits[10];
    size_t count = 0U;
    do
    {
        digits[count++] = (char)('0' + (value % 10U));
        value /= 10U;
    } while (0U != value);
    while (0U != count)
    {
        *out++ = digits[--count];
    }
    return out;
}

static char *tcp_sockets_diag_append_hex(char *out, uint32_t value)
{
    uint32_t index;
    uint32_t digit;
    for (index = 0U; index < 8U; index++)
    {
        digit = (value >> ((7U - index) * 4U)) & 0xFU;
        *out++ = (char)((digit < 10U) ? ('0' + digit) : ('A' + digit - 10U));
    }
    return out;
}

/* The numeric backend distinguishes status domains; status bits are not a
 * universal errno. Stage describes the public operation visible in this
 * wrapper, not an opaque vendor driver's internal state. No network identity
 * or arbitrary error text is accepted. The writer must consume the row before
 * returning. Physical reception is not guaranteed; absence is not evidence.
 */
static void tcp_sockets_report_connect_failure(uint32_t backend,
                                               uint32_t stage,
                                               uint32_t status,
                                               TCPConnectDiagnosticWriter_t writer)
{
    char line[96];
    char *out = line;

    if ((0U == status) || (NULL == writer))
    {
        return;
    }
    out = tcp_sockets_diag_append_text(out, "TCP connect failure context backend=");
    out = tcp_sockets_diag_append_decimal(out, backend);
    out = tcp_sockets_diag_append_text(out, " stage=");
    out = tcp_sockets_diag_append_decimal(out, stage);
    out = tcp_sockets_diag_append_text(out, " status=");
    out = tcp_sockets_diag_append_hex(out, status);
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
}

#endif

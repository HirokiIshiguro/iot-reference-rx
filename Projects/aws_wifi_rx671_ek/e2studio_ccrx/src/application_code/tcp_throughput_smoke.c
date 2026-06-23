/*
 * Plain TCP throughput smoke test for EK-RX671 + Type 1YN.
 */
#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h"
#include "task.h"
#include "FreeRTOS_IP.h"
#include "FreeRTOS_Sockets.h"
#include "NetworkBufferManagement.h"

#include "debug_uart.h"
#include "sdio_host.h"
#include "tcp_throughput_config.h"
#include "tcp_throughput_smoke.h"

extern volatile uint32_t g_freertos_tcp_network_up;

volatile uint32_t g_tcp_throughput_enable_seen;
volatile uint32_t g_tcp_throughput_task_create_result;
volatile uint32_t g_tcp_throughput_task_enter_count;
volatile uint32_t g_tcp_throughput_wait_network_count;
volatile uint32_t g_tcp_throughput_sink_status;
volatile uint32_t g_tcp_throughput_source_status;
volatile uint32_t g_tcp_throughput_last_mode;
volatile uint32_t g_tcp_throughput_last_bytes;
volatile uint32_t g_tcp_throughput_last_ms;
volatile uint32_t g_tcp_throughput_last_mbps_x1000;
volatile uint32_t g_tcp_throughput_win_status;

extern volatile uint32_t g_whd_network_rx_frames;
extern volatile uint32_t g_whd_network_rx_to_ip;
extern volatile uint32_t g_whd_network_rx_dropped;
extern volatile uint32_t g_whd_network_rx_no_buffer;
extern volatile uint32_t g_whd_network_rx_drop_queue;
extern volatile uint32_t g_whd_network_rx_tcp;
extern volatile uint32_t g_whd_network_tx_frames;
extern volatile uint32_t g_whd_network_tx_no_buffer;
extern volatile uint32_t g_whd_network_tx_drop_not_ready;
extern volatile uint32_t g_whd_network_tx_drop_no_data;
extern volatile uint32_t g_whd_network_tx_tcp;
extern volatile uint32_t g_whd_port_buffer_current_in_use;
extern volatile uint32_t g_whd_port_buffer_max_in_use;
extern volatile uint32_t g_whd_port_buffer_alloc_temp_fail_count;
extern volatile uint32_t g_whd_port_buffer_alloc_perm_fail_count;
extern volatile uint32_t g_whd_port_buffer_wait_loop_count;
extern volatile uint32_t g_whd_port_buffer_last_request_size;
extern volatile uint32_t g_whd_port_buffer_last_request_direction;

#if TCP_THROUGHPUT_ENABLE

#define TCP_THROUGHPUT_BUFFER_BYTES \
    (((TCP_THROUGHPUT_TX_CHUNK_BYTES) > (TCP_THROUGHPUT_RX_CHUNK_BYTES)) ? \
     (TCP_THROUGHPUT_TX_CHUNK_BYTES) : (TCP_THROUGHPUT_RX_CHUNK_BYTES))

static union
{
    uint32_t align;
    uint8_t  bytes[TCP_THROUGHPUT_BUFFER_BYTES];
} s_tcp_buffer_storage;

#define s_tcp_buffer (s_tcp_buffer_storage.bytes)

static char * append_dec64(char * dst, uint64_t value)
{
    char tmp[20];
    uint8_t digits = 0U;

    do
    {
        tmp[digits] = (char)('0' + (value % 10ULL));
        digits++;
        value /= 10ULL;
    } while ((0ULL != value) && (digits < sizeof(tmp)));

    while (digits > 0U)
    {
        digits--;
        *dst = tmp[digits];
        dst++;
    }

    return dst;
}

static void log_status(const char * label, int32_t status)
{
    char line[96];
    char * p = line;

    p = append_text(p, "[TCPTHR] ");
    p = append_text(p, label);
    p = append_text(p, "=");
    if (status < 0)
    {
        p = append_text(p, "-");
        p = append_dec32(p, (uint32_t)(-status));
    }
    else
    {
        p = append_dec32(p, (uint32_t)status);
    }
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void log_socket_window_status(BaseType_t status)
{
    char line[200];
    char * p = line;

    g_tcp_throughput_win_status = (uint32_t)status;
    p = append_text(p, "[TCPTHR] win status=");
    if (status < 0)
    {
        p = append_text(p, "-");
        p = append_dec32(p, (uint32_t)(-status));
    }
    else
    {
        p = append_dec32(p, (uint32_t)status);
    }
    p = append_text(p, " txbuf=");
    p = append_dec32(p, (uint32_t)TCP_THROUGHPUT_TX_BUFFER_BYTES);
    p = append_text(p, " txwin=");
    p = append_dec32(p, (uint32_t)TCP_THROUGHPUT_TX_WINDOW_MSS);
    p = append_text(p, " txchunk=");
    p = append_dec32(p, (uint32_t)TCP_THROUGHPUT_TX_CHUNK_BYTES);
    p = append_text(p, " rxbuf=");
    p = append_dec32(p, (uint32_t)TCP_THROUGHPUT_RX_BUFFER_BYTES);
    p = append_text(p, " rxwin=");
    p = append_dec32(p, (uint32_t)TCP_THROUGHPUT_RX_WINDOW_MSS);
    p = append_text(p, " rxchunk=");
    p = append_dec32(p, (uint32_t)TCP_THROUGHPUT_RX_CHUNK_BYTES);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void log_resource_diag(const char * label)
{
    char line[320];
    char * p = line;

    p = append_text(p, "[TCPTHR] res ");
    p = append_text(p, label);
    p = append_text(p, " heap=");
    p = append_dec32(p, (uint32_t)xPortGetFreeHeapSize());
    p = append_text(p, " minheap=");
    p = append_dec32(p, (uint32_t)xPortGetMinimumEverFreeHeapSize());
    p = append_text(p, " nbuf=");
    p = append_dec32(p, (uint32_t)uxGetNumberOfFreeNetworkBuffers());
    p = append_text(p, " minnbuf=");
    p = append_dec32(p, (uint32_t)uxGetMinimumFreeNetworkBuffers());
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void log_network_diag(const char * label)
{
    char line[360];
    char * p = line;

    p = append_text(p, "[TCPTHR] net ");
    p = append_text(p, label);
    p = append_text(p, " rx=");
    p = append_dec32(p, g_whd_network_rx_frames);
    p = append_text(p, " rxip=");
    p = append_dec32(p, g_whd_network_rx_to_ip);
    p = append_text(p, " rxdrop=");
    p = append_dec32(p, g_whd_network_rx_dropped);
    p = append_text(p, " rxnb=");
    p = append_dec32(p, g_whd_network_rx_no_buffer);
    p = append_text(p, " rxq=");
    p = append_dec32(p, g_whd_network_rx_drop_queue);
    p = append_text(p, " rxtcp=");
    p = append_dec32(p, g_whd_network_rx_tcp);
    p = append_text(p, " tx=");
    p = append_dec32(p, g_whd_network_tx_frames);
    p = append_text(p, " txnb=");
    p = append_dec32(p, g_whd_network_tx_no_buffer);
    p = append_text(p, " txnr=");
    p = append_dec32(p, g_whd_network_tx_drop_not_ready);
    p = append_text(p, " txnd=");
    p = append_dec32(p, g_whd_network_tx_drop_no_data);
    p = append_text(p, " txtcp=");
    p = append_dec32(p, g_whd_network_tx_tcp);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void log_whd_buffer_diag(const char * label)
{
    char line[240];
    char * p = line;

    p = append_text(p, "[TCPTHR] whdbuf ");
    p = append_text(p, label);
    p = append_text(p, " cur=");
    p = append_dec32(p, g_whd_port_buffer_current_in_use);
    p = append_text(p, " max=");
    p = append_dec32(p, g_whd_port_buffer_max_in_use);
    p = append_text(p, " tempfail=");
    p = append_dec32(p, g_whd_port_buffer_alloc_temp_fail_count);
    p = append_text(p, " permfail=");
    p = append_dec32(p, g_whd_port_buffer_alloc_perm_fail_count);
    p = append_text(p, " waitloop=");
    p = append_dec32(p, g_whd_port_buffer_wait_loop_count);
    p = append_text(p, " lastsz=");
    p = append_dec32(p, g_whd_port_buffer_last_request_size);
    p = append_text(p, " lastdir=");
    p = append_dec32(p, g_whd_port_buffer_last_request_direction);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void log_perf_diag(const char * label)
{
    log_resource_diag(label);
    log_network_diag(label);
    log_whd_buffer_diag(label);
}

static void log_result(const char * label, uint32_t bytes, uint32_t elapsed_ms)
{
    char line[160];
    char * p = line;
    uint64_t bps = 0ULL;
    uint64_t mbps_x1000 = 0ULL;

    if (0U != elapsed_ms)
    {
        bps = (((uint64_t)bytes) * 8000ULL) / (uint64_t)elapsed_ms;
        mbps_x1000 = bps / 1000ULL;
    }

    g_tcp_throughput_last_bytes = bytes;
    g_tcp_throughput_last_ms = elapsed_ms;
    g_tcp_throughput_last_mbps_x1000 = (uint32_t)mbps_x1000;

    p = append_text(p, "[TCPTHR] ");
    p = append_text(p, label);
    p = append_text(p, " bytes=");
    p = append_dec32(p, bytes);
    p = append_text(p, " ms=");
    p = append_dec32(p, elapsed_ms);
    p = append_text(p, " bps=");
    p = append_dec64(p, bps);
    p = append_text(p, " Mbps=");
    p = append_dec64(p, mbps_x1000 / 1000ULL);
    p = append_text(p, ".");
    if ((mbps_x1000 % 1000ULL) < 100ULL)
    {
        p = append_text(p, "0");
    }
    if ((mbps_x1000 % 1000ULL) < 10ULL)
    {
        p = append_text(p, "0");
    }
    p = append_dec64(p, mbps_x1000 % 1000ULL);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void log_sdio_xfer_diag(const char * label)
{
    char line[240];
    char * p = line;
    uint32_t engine = 0U;
    uint32_t done = 0U;
    uint32_t ok = 0U;
    uint32_t fail = 0U;
    uint32_t fallback = 0U;
    uint32_t error = 0U;
    uint32_t fb_function = 0U;
    uint32_t fb_disabled = 0U;
    uint32_t fb_small = 0U;
    uint32_t fb_ineligible = 0U;
    uint32_t fb_prepare = 0U;

    sdio_host_cmd53_xfer_diag(&engine, &done, &ok, &fail, &fallback, &error);
    sdio_host_cmd53_xfer_fallback_diag(&fb_function, &fb_disabled, &fb_small, &fb_ineligible, &fb_prepare);

    p = append_text(p, "[TCPTHR] sdio ");
    p = append_text(p, label);
    p = append_text(p, " eng=");
    p = append_dec32(p, engine);
    p = append_text(p, " done=");
    p = append_dec32(p, done);
    p = append_text(p, " ok=");
    p = append_dec32(p, ok);
    p = append_text(p, " fail=");
    p = append_dec32(p, fail);
    p = append_text(p, " fb=");
    p = append_dec32(p, fallback);
    p = append_text(p, " err=");
    p = append_hex32(p, error);
    p = append_text(p, " ff=");
    p = append_dec32(p, fb_function);
    p = append_text(p, " fd=");
    p = append_dec32(p, fb_disabled);
    p = append_text(p, " fs=");
    p = append_dec32(p, fb_small);
    p = append_text(p, " fi=");
    p = append_dec32(p, fb_ineligible);
    p = append_text(p, " fp=");
    p = append_dec32(p, fb_prepare);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static Socket_t open_connected_socket(int32_t * p_status)
{
    Socket_t socket;
    struct freertos_sockaddr address = {0};
    TickType_t timeout_ticks = pdMS_TO_TICKS(TCP_THROUGHPUT_TIMEOUT_MS);
    BaseType_t status;

    socket = FreeRTOS_socket(FREERTOS_AF_INET, FREERTOS_SOCK_STREAM, FREERTOS_IPPROTO_TCP);
    if (FREERTOS_INVALID_SOCKET == socket)
    {
        *p_status = -1;
        return socket;
    }

    (void)FreeRTOS_setsockopt(socket, 0, FREERTOS_SO_RCVTIMEO, &timeout_ticks, sizeof(timeout_ticks));
    (void)FreeRTOS_setsockopt(socket, 0, FREERTOS_SO_SNDTIMEO, &timeout_ticks, sizeof(timeout_ticks));
#if (ipconfigUSE_TCP_WIN == 1)
    {
        WinProperties_t win_props;

        win_props.lTxBufSize = (int32_t)TCP_THROUGHPUT_TX_BUFFER_BYTES;
        win_props.lTxWinSize = (int32_t)TCP_THROUGHPUT_TX_WINDOW_MSS;
        win_props.lRxBufSize = (int32_t)TCP_THROUGHPUT_RX_BUFFER_BYTES;
        win_props.lRxWinSize = (int32_t)TCP_THROUGHPUT_RX_WINDOW_MSS;
        status = FreeRTOS_setsockopt(socket, 0, FREERTOS_SO_WIN_PROPERTIES,
                                     (void *)&win_props, sizeof(win_props));
        log_socket_window_status(status);
        log_perf_diag("win");
    }
#endif

    address.sin_len = sizeof(address);
    address.sin_family = FREERTOS_AF_INET;
    address.sin_port = FreeRTOS_htons((uint16_t)TCP_THROUGHPUT_PORT);
    address.sin_addr = FreeRTOS_inet_addr_quick(TCP_THROUGHPUT_HOST_IP0,
                                                TCP_THROUGHPUT_HOST_IP1,
                                                TCP_THROUGHPUT_HOST_IP2,
                                                TCP_THROUGHPUT_HOST_IP3);

    status = FreeRTOS_connect(socket, &address, sizeof(address));
    if (0 != status)
    {
        *p_status = (int32_t)status;
        (void)FreeRTOS_closesocket(socket);
        return FREERTOS_INVALID_SOCKET;
    }

    log_perf_diag("connected");
    *p_status = 0;
    return socket;
}

static int32_t run_sink_once(uint32_t iteration)
{
    Socket_t socket;
    int32_t status;
    uint32_t sent = 0U;
    TickType_t start_ticks;
    TickType_t end_ticks;
#if (TCP_THROUGHPUT_PROGRESS_BYTES > 0UL)
    uint32_t next_progress = (uint32_t)TCP_THROUGHPUT_PROGRESS_BYTES;
#endif

    (void)iteration;
    log_perf_diag("sink_begin");
    socket = open_connected_socket(&status);
    if (FREERTOS_INVALID_SOCKET == socket)
    {
        return status;
    }

    memset(s_tcp_buffer, 0xa5, (size_t)TCP_THROUGHPUT_TX_CHUNK_BYTES);
    start_ticks = xTaskGetTickCount();
    while (sent < (uint32_t)TCP_THROUGHPUT_TOTAL_BYTES)
    {
        uint32_t remaining = (uint32_t)TCP_THROUGHPUT_TOTAL_BYTES - sent;
        uint32_t request = (remaining < (uint32_t)TCP_THROUGHPUT_TX_CHUNK_BYTES) ?
                           remaining : (uint32_t)TCP_THROUGHPUT_TX_CHUNK_BYTES;
        BaseType_t n = FreeRTOS_send(socket, s_tcp_buffer, request, 0);

        if (0 >= n)
        {
            status = (int32_t)n;
            break;
        }
        sent += (uint32_t)n;
#if (TCP_THROUGHPUT_PROGRESS_BYTES > 0UL)
        if ((0U != next_progress) && (sent >= next_progress))
        {
            log_perf_diag("sink_progress");
            next_progress += (uint32_t)TCP_THROUGHPUT_PROGRESS_BYTES;
        }
#endif
    }
    end_ticks = xTaskGetTickCount();

    (void)FreeRTOS_shutdown(socket, FREERTOS_SHUT_RDWR);
    (void)FreeRTOS_closesocket(socket);

    log_result("sink", sent, (uint32_t)((end_ticks - start_ticks) * portTICK_PERIOD_MS));
    log_sdio_xfer_diag("sink");
    log_perf_diag("sink_end");
    return status;
}

static int32_t run_source_once(uint32_t iteration)
{
    Socket_t socket;
    int32_t status;
    uint32_t received = 0U;
    TickType_t start_ticks;
    TickType_t end_ticks;
#if (TCP_THROUGHPUT_PROGRESS_BYTES > 0UL)
    uint32_t next_progress = (uint32_t)TCP_THROUGHPUT_PROGRESS_BYTES;
#endif

    (void)iteration;
    log_perf_diag("source_begin");
    socket = open_connected_socket(&status);
    if (FREERTOS_INVALID_SOCKET == socket)
    {
        return status;
    }

    start_ticks = xTaskGetTickCount();
    while (received < (uint32_t)TCP_THROUGHPUT_TOTAL_BYTES)
    {
        uint32_t remaining = (uint32_t)TCP_THROUGHPUT_TOTAL_BYTES - received;
        uint32_t request = (remaining < (uint32_t)TCP_THROUGHPUT_RX_CHUNK_BYTES) ?
                           remaining : (uint32_t)TCP_THROUGHPUT_RX_CHUNK_BYTES;
        BaseType_t n = FreeRTOS_recv(socket, s_tcp_buffer, request, 0);

        if (0 >= n)
        {
            status = (int32_t)n;
            break;
        }
        received += (uint32_t)n;
#if (TCP_THROUGHPUT_PROGRESS_BYTES > 0UL)
        if ((0U != next_progress) && (received >= next_progress))
        {
            log_perf_diag("source_progress");
            next_progress += (uint32_t)TCP_THROUGHPUT_PROGRESS_BYTES;
        }
#endif
    }
    end_ticks = xTaskGetTickCount();

    (void)FreeRTOS_shutdown(socket, FREERTOS_SHUT_RDWR);
    (void)FreeRTOS_closesocket(socket);

    log_result("source", received, (uint32_t)((end_ticks - start_ticks) * portTICK_PERIOD_MS));
    log_sdio_xfer_diag("source");
    log_perf_diag("source_end");
    return status;
}

static void tcp_throughput_task(void * p_parameters)
{
    uint32_t i;

    (void)p_parameters;
    g_tcp_throughput_task_enter_count++;

    while (0U == g_freertos_tcp_network_up)
    {
        g_tcp_throughput_wait_network_count++;
        vTaskDelay(pdMS_TO_TICKS(500U));
    }

    debug_puts("[TCPTHR] network ready\r\n");
    log_perf_diag("task_begin");

    for (i = 0U; i < (uint32_t)TCP_THROUGHPUT_ITERATIONS; i++)
    {
        if ((TCP_THROUGHPUT_MODE_SINK == TCP_THROUGHPUT_MODE) ||
            (TCP_THROUGHPUT_MODE_BOTH == TCP_THROUGHPUT_MODE))
        {
            g_tcp_throughput_last_mode = TCP_THROUGHPUT_MODE_SINK;
            g_tcp_throughput_sink_status = (uint32_t)run_sink_once(i);
            log_status("sink_status", (int32_t)g_tcp_throughput_sink_status);
            vTaskDelay(pdMS_TO_TICKS(1000U));
        }

        if ((TCP_THROUGHPUT_MODE_SOURCE == TCP_THROUGHPUT_MODE) ||
            (TCP_THROUGHPUT_MODE_BOTH == TCP_THROUGHPUT_MODE))
        {
            g_tcp_throughput_last_mode = TCP_THROUGHPUT_MODE_SOURCE;
            g_tcp_throughput_source_status = (uint32_t)run_source_once(i);
            log_status("source_status", (int32_t)g_tcp_throughput_source_status);
            vTaskDelay(pdMS_TO_TICKS(1000U));
        }
    }

    debug_puts("[TCPTHR] done\r\n");
    log_perf_diag("task_done");
    vTaskDelete(NULL);
}

#endif /* TCP_THROUGHPUT_ENABLE */

void tcp_throughput_smoke_start(void)
{
#if TCP_THROUGHPUT_ENABLE
    BaseType_t result;

    g_tcp_throughput_enable_seen = 1U;
    result = xTaskCreate(tcp_throughput_task,
                         "TCPTHR",
                         TCP_THROUGHPUT_TASK_STACK_WORDS,
                         NULL,
                         TCP_THROUGHPUT_TASK_PRIORITY,
                         NULL);
    g_tcp_throughput_task_create_result = (uint32_t)result;
    debug_puts((pdPASS == result) ? "[TCPTHR] task OK\r\n" : "[TCPTHR] task NG\r\n");
#else
    g_tcp_throughput_enable_seen = 0U;
#endif
}

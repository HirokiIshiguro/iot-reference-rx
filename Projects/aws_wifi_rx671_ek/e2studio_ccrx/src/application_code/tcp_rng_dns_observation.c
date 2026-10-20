/* Application-only bounded observation. No AWS/credential header dependencies.
 * Both hooks are defined whenever the common feature is enabled, including a
 * maintenance build with the AWS application disabled. No producer emits UART.
 */
#include <stdint.h>
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "tcp_rng_dns_observation.h"

#if (TCP_SOCKETS_ENABLE_RANDOM_DIAGNOSTICS == 1)
#define OBS_QUEUE_LENGTH (8U)
#define OBS_EVENT_RNG    (1U)
#define OBS_EVENT_DNS    (2U)

typedef struct ObsEvent
{
    uint32_t kind;
    uint32_t backend;
    uint32_t operation;
    uint32_t status;
    TaskHandle_t caller; /* Private RAM only. Never formatted or retained. */
    TickType_t tick;     /* Private RAM only. Never formatted or retained. */
} ObsEvent_t;

typedef struct ObsCounters
{
    uint32_t rng;
    uint32_t dns;
    uint32_t lost;
    uint32_t uninitialized;
    uint32_t saturated;
} ObsCounters_t;

static StaticQueue_t g_queue_control;
static uint8_t g_queue_storage[OBS_QUEUE_LENGTH * sizeof(ObsEvent_t)];
static QueueHandle_t g_queue;
static BaseType_t g_init_started;
static ObsCounters_t g_counts;

/* Caller holds the bounded application critical section. Never wrap. */
static void prvIncrement(uint32_t *value)
{
    if ((uint32_t)0xFFFFFFFFUL == *value)
    {
        g_counts.saturated = 1U;
    }
    else
    {
        *value += 1U;
    }
}

void tcp_rng_dns_observation_init(void)
{
    QueueHandle_t created;
    BaseType_t create = pdFALSE;

    taskENTER_CRITICAL();
    if (pdFALSE == g_init_started)
    {
        g_init_started = pdTRUE;
        create = pdTRUE;
    }
    taskEXIT_CRITICAL();
    if (pdFALSE != create)
    {
        created = xQueueCreateStatic(OBS_QUEUE_LENGTH, sizeof(ObsEvent_t),
                                     g_queue_storage, &g_queue_control);
        taskENTER_CRITICAL();
        g_queue = created;
        taskEXIT_CRITICAL();
    }
}

/* Task context only. No log/UART/heap/notification/PKCS/RNG/network calls.
 * xQueueSend(...,0) may copy and enter kernel critical sections; observer cost
 * is not zero. A null/initializing queue is explicitly counted, not invented.
 */
static void prvRecord(uint32_t kind, uint32_t backend,
                      uint32_t operation, uint32_t status)
{
    ObsEvent_t event;
    QueueHandle_t queue;

    event.kind = kind;
    event.backend = backend;
    event.operation = operation;
    event.status = status;
    event.caller = xTaskGetCurrentTaskHandle();
    event.tick = xTaskGetTickCount();
    taskENTER_CRITICAL();
    queue = g_queue;
    if (OBS_EVENT_RNG == kind)
    {
        prvIncrement(&g_counts.rng);
    }
    else
    {
        prvIncrement(&g_counts.dns);
    }
    if (NULL == queue)
    {
        prvIncrement(&g_counts.uninitialized);
    }
    taskEXIT_CRITICAL();
    if (NULL != queue)
    {
        if (pdPASS != xQueueSend(queue, &event, 0U))
        {
            taskENTER_CRITICAL();
            prvIncrement(&g_counts.lost);
            taskEXIT_CRITICAL();
        }
    }
}

void TCP_Sockets_OnRandomFailure(uint32_t backend,
                                 uint32_t operation, uint32_t status)
{
    prvRecord(OBS_EVENT_RNG, backend, operation, status);
}

void TCP_Sockets_OnDNSSendAttempt(uint32_t backend)
{
    prvRecord(OBS_EVENT_DNS, backend, 0U, 0U);
}

void tcp_rng_dns_observation_connect_begin(TcpRngDnsConnectWindow_t *window)
{
    if (NULL != window)
    {
        window->caller = xTaskGetCurrentTaskHandle();
        window->started_at = xTaskGetTickCount();
        window->finished_at = window->started_at;
        window->complete = pdFALSE;
    }
}

void tcp_rng_dns_observation_connect_end(TcpRngDnsConnectWindow_t *window)
{
    if (NULL != window)
    {
        window->finished_at = xTaskGetTickCount();
        window->complete = pdTRUE;
    }
}

void tcp_rng_dns_observation_report_failure(const TcpRngDnsConnectWindow_t *window,
                                           BaseType_t status,
                                           TCPConnectDiagnosticWriter_t writer)
{
    ObsEvent_t event;
    ObsCounters_t counts;
    QueueHandle_t queue;
    uint32_t drained = 0U;
    uint32_t match_rng = 0U;
    uint32_t match_dns = 0U;
    uint32_t uncorrelated = 0U;
    uint32_t pending = 0U;
    uint32_t valid = 0U;
    uint32_t match;
    TickType_t elapsed = 0U;
    char line[96];
    char *out;

    if ((0 == status) || (NULL == writer))
    {
        return;
    }
    if ((NULL != window) && (pdFALSE != window->complete) &&
        (NULL != window->caller) &&
        (window->caller == xTaskGetCurrentTaskHandle()))
    {
        valid = 1U;
        elapsed = (TickType_t)(window->finished_at - window->started_at);
    }
    taskENTER_CRITICAL();
    queue = g_queue;
    taskEXIT_CRITICAL();
    while ((NULL != queue) && (drained < OBS_QUEUE_LENGTH))
    {
        if (pdPASS != xQueueReceive(queue, &event, 0U))
        {
            break;
        }
        drained++;
        match = 0U;
        if ((0U != valid) && (event.caller == window->caller) &&
            ((TickType_t)(event.tick - window->started_at) <= elapsed))
        {
            match = 1U;
        }
        if (0U == match)
        {
            uncorrelated++;
        }
        if (OBS_EVENT_RNG == event.kind)
        {
            match_rng += match;
            tcp_sockets_report_random_failure(event.backend, event.operation,
                                               event.status, match, writer);
        }
        else
        {
            match_dns += match;
        }
    }
    if (NULL != queue)
    {
        pending = (uint32_t)uxQueueMessagesWaiting(queue);
    }
    taskENTER_CRITICAL();
    counts = g_counts;
    taskEXIT_CRITICAL();

    out = line;
    out = tcp_sockets_diag_append_text(out, "TCP RNG queue lost=");
    out = tcp_sockets_diag_append_hex(out, counts.lost);
    out = tcp_sockets_diag_append_text(out, " uninit=");
    out = tcp_sockets_diag_append_hex(out, counts.uninitialized);
    out = tcp_sockets_diag_append_text(out, " pending=");
    out = tcp_sockets_diag_append_hex(out, pending);
    out = tcp_sockets_diag_append_text(out, " drained=");
    out = tcp_sockets_diag_append_hex(out, drained);
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);

    out = line;
    out = tcp_sockets_diag_append_text(out, "TCP RNG events rng=");
    out = tcp_sockets_diag_append_hex(out, counts.rng);
    out = tcp_sockets_diag_append_text(out, " dns=");
    out = tcp_sockets_diag_append_hex(out, counts.dns);
    out = tcp_sockets_diag_append_text(out, " match_rng=");
    out = tcp_sockets_diag_append_hex(out, match_rng);
    out = tcp_sockets_diag_append_text(out, " match_dns=");
    out = tcp_sockets_diag_append_hex(out, match_dns);
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);

    out = line;
    out = tcp_sockets_diag_append_text(out, "TCP RNG window uncorrelated=");
    out = tcp_sockets_diag_append_hex(out, uncorrelated);
    out = tcp_sockets_diag_append_text(out, " saturated=");
    out = tcp_sockets_diag_append_decimal(out, counts.saturated);
    out = tcp_sockets_diag_append_text(out, " valid=");
    out = tcp_sockets_diag_append_decimal(out, valid);
    out = tcp_sockets_diag_append_text(out, "\r\n");
    *out = '\0';
    writer(line);
}
#endif

/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#include <string.h>
#include <limits.h>
#include "FreeRTOS.h"
#include "task.h"
#include "event_groups.h"
#include "tcp_sockets_wrapper.h"
#include "bg96_network.h"

#define SOCKET_OPEN_OK 1U
#define SOCKET_OPEN_FAILED 2U
#define SOCKET_DATA_READY 4U
#define SOCKET_CLOSED 8U

/* Static contexts prevent a delayed URC callback from dereferencing freed
 * product memory. The official library owns each opaque socket handle. */
struct xSOCKET
{
    CellularSocketHandle_t handle;
    EventGroupHandle_t events;
    StaticEventGroup_t eventStorage;
    uint32_t recvTimeout;
    bool used;
    bool draining;
};
static struct xSOCKET sockets[CELLULAR_NUM_SOCKET_MAX];

static void socketOpened(CellularUrcEvent_t event, CellularSocketHandle_t handle, void * context)
{
    struct xSOCKET * socket = context;
    if ((socket->used) && (handle == socket->handle))
    { xEventGroupSetBits(socket->events, event == CELLULAR_URC_SOCKET_OPENED ? SOCKET_OPEN_OK : SOCKET_OPEN_FAILED); }
}
static void dataReady(CellularSocketHandle_t handle, void * context)
{
    struct xSOCKET * socket = context;
    if ((socket->used) && (handle == socket->handle)) { xEventGroupSetBits(socket->events, SOCKET_DATA_READY); }
}
static void socketClosed(CellularSocketHandle_t handle, void * context)
{
    struct xSOCKET * socket = context;
    if ((socket->used) && (handle == socket->handle)) { xEventGroupSetBits(socket->events, SOCKET_CLOSED); }
}

void TCP_Sockets_Disconnect(Socket_t socket)
{
    if ((socket == NULL) || (socket == SOCKETS_INVALID_SOCKET) || !socket->used) { return; }
    if (socket->handle != NULL)
    {
        CellularHandle_t module = Bg96_GetHandle();
        (void)Cellular_SocketRegisterSocketOpenCallback(module, socket->handle, NULL, NULL);
        (void)Cellular_SocketRegisterDataReadyCallback(module, socket->handle, NULL, NULL);
        (void)Cellular_SocketRegisterClosedCallback(module, socket->handle, NULL, NULL);
        (void)Cellular_SocketClose(module, socket->handle);
    }
    taskENTER_CRITICAL();
    socket->handle = NULL; socket->used = false;
    taskEXIT_CRITICAL();
}

BaseType_t TCP_Sockets_Connect(Socket_t * result, const char * hostname, uint16_t port,
                              uint32_t recvTimeoutMs, uint32_t sendTimeoutMs)
{
    unsigned int index;
    struct xSOCKET * socket = NULL;
    CellularSocketAddress_t address = {0};
    CellularHandle_t module = Bg96_GetHandle();
    CellularError_t status;
    EventBits_t events;
    if ((result == NULL) || (hostname == NULL) || (module == NULL)) { return TCP_SOCKETS_ERRNO_EINVAL; }
    *result = NULL;
    taskENTER_CRITICAL();
    for (index = 0; index < CELLULAR_NUM_SOCKET_MAX; index++)
    { if (!sockets[index].used) { socket = &sockets[index]; socket->used = true; break; } }
    taskEXIT_CRITICAL();
    if (socket == NULL) { return TCP_SOCKETS_ERRNO_ENOSPC; }
    if (socket->events == NULL) { socket->events = xEventGroupCreateStatic(&socket->eventStorage); }
    if (socket->events == NULL) { socket->used = false; return TCP_SOCKETS_ERRNO_ENOMEM; }
    xEventGroupClearBits(socket->events, SOCKET_OPEN_OK|SOCKET_OPEN_FAILED|SOCKET_DATA_READY|SOCKET_CLOSED);
    socket->handle = NULL; socket->draining = false; socket->recvTimeout = recvTimeoutMs;
    status = Cellular_GetHostByName(module, CELLULAR_PDN_CONTEXT_ID, hostname, address.ipAddress.ipAddress);
    address.ipAddress.ipAddressType = CELLULAR_IP_ADDRESS_V4; address.port = port;
    if (status == CELLULAR_SUCCESS)
    { status = Cellular_CreateSocket(module, CELLULAR_PDN_CONTEXT_ID, CELLULAR_SOCKET_DOMAIN_AF_INET,
              CELLULAR_SOCKET_TYPE_STREAM, CELLULAR_SOCKET_PROTOCOL_TCP, &socket->handle); }
    if (status == CELLULAR_SUCCESS)
    { status = Cellular_SocketRegisterSocketOpenCallback(module, socket->handle, socketOpened, socket); }
    if (status == CELLULAR_SUCCESS)
    { status = Cellular_SocketRegisterDataReadyCallback(module, socket->handle, dataReady, socket); }
    if (status == CELLULAR_SUCCESS)
    { status = Cellular_SocketRegisterClosedCallback(module, socket->handle, socketClosed, socket); }
    if (status == CELLULAR_SUCCESS)
    { status = Cellular_SocketSetSockOpt(module, socket->handle, CELLULAR_SOCKET_OPTION_LEVEL_TRANSPORT,
               CELLULAR_SOCKET_OPTION_SEND_TIMEOUT, (const uint8_t *)&sendTimeoutMs, sizeof(sendTimeoutMs)); }
    if (status == CELLULAR_SUCCESS)
    { status = Cellular_SocketSetSockOpt(module, socket->handle, CELLULAR_SOCKET_OPTION_LEVEL_TRANSPORT,
               CELLULAR_SOCKET_OPTION_RECV_TIMEOUT, (const uint8_t *)&recvTimeoutMs, sizeof(recvTimeoutMs)); }
    if (status == CELLULAR_SUCCESS)
    { status = Cellular_SocketConnect(module, socket->handle, CELLULAR_ACCESSMODE_BUFFER, &address); }
    if (status == CELLULAR_SUCCESS)
    {
        events = xEventGroupWaitBits(socket->events, SOCKET_OPEN_OK|SOCKET_OPEN_FAILED|SOCKET_CLOSED,
                                     pdFALSE, pdFALSE, pdMS_TO_TICKS(60000U));
        if (((events & SOCKET_OPEN_OK) != 0U) && ((events & (SOCKET_OPEN_FAILED|SOCKET_CLOSED)) == 0U))
        { *result = socket; return TCP_SOCKETS_ERRNO_NONE; }
    }
    TCP_Sockets_Disconnect(socket);
    return TCP_SOCKETS_ERRNO_ENOTCONN;
}

int32_t TCP_Sockets_Send(Socket_t socket, const void * data, size_t length)
{
    uint32_t sent = 0;
    CellularError_t status;
    if ((socket == NULL) || (socket == SOCKETS_INVALID_SOCKET) || !socket->used || (data == NULL) || (length > INT32_MAX))
    { return TCP_SOCKETS_ERRNO_EINVAL; }
    if ((xEventGroupGetBits(socket->events) & SOCKET_CLOSED) != 0U) { return TCP_SOCKETS_ERRNO_ECLOSED; }
    if (length == 0U) { return 0; }
    status = Cellular_SocketSend(Bg96_GetHandle(), socket->handle, data, (uint32_t)length, &sent);
    if (sent > 0U) { return (int32_t)sent; }
    if ((status == CELLULAR_SOCKET_CLOSED) || (status == CELLULAR_SOCKET_NOT_CONNECTED)) { return TCP_SOCKETS_ERRNO_ECLOSED; }
    return status == CELLULAR_TIMEOUT ? 0 : TCP_SOCKETS_ERRNO_ERROR;
}

int32_t TCP_Sockets_Recv(Socket_t socket, void * data, size_t capacity)
{
    TickType_t began = xTaskGetTickCount();
    uint32_t received = 0;
    CellularError_t status;
    EventBits_t events;
    if ((socket == NULL) || (socket == SOCKETS_INVALID_SOCKET) || !socket->used || (data == NULL) || (capacity > INT32_MAX))
    { return TCP_SOCKETS_ERRNO_EINVAL; }
    if (capacity == 0U) { return 0; }
    for (;;)
    {
        events = xEventGroupGetBits(socket->events);
        if ((events & SOCKET_CLOSED) != 0U) { return TCP_SOCKETS_ERRNO_ECLOSED; }
        if (!socket->draining)
        {
            TickType_t wait = portMAX_DELAY;
            if (socket->recvTimeout != 0U)
            {
                TickType_t elapsed = xTaskGetTickCount() - began;
                TickType_t total = pdMS_TO_TICKS(socket->recvTimeout);
                if (elapsed >= total) { return 0; }
                wait = total - elapsed;
            }
            events = xEventGroupWaitBits(socket->events, SOCKET_DATA_READY|SOCKET_CLOSED, pdFALSE, pdFALSE, wait);
            if ((events & SOCKET_CLOSED) != 0U) { return TCP_SOCKETS_ERRNO_ECLOSED; }
            if ((events & SOCKET_DATA_READY) == 0U) { return 0; }
            /* Clear before QIRD: a new URC arriving during the drain must stay
             * pending. Continue QIRD until it reports zero, without requiring
             * an additional URC for the same buffered payload. */
            xEventGroupClearBits(socket->events, SOCKET_DATA_READY);
        }
        status = Cellular_SocketRecv(Bg96_GetHandle(), socket->handle, data, (uint32_t)capacity, &received);
        if (received > 0U) { socket->draining = true; return (int32_t)received; }
        socket->draining = false;
        if ((status == CELLULAR_SOCKET_CLOSED) || (status == CELLULAR_SOCKET_NOT_CONNECTED)) { return TCP_SOCKETS_ERRNO_ECLOSED; }
        if ((status != CELLULAR_SUCCESS) && (status != CELLULAR_TIMEOUT)) { return TCP_SOCKETS_ERRNO_ERROR; }
        /* Do not spin on stale indications while no payload is available. */
        if (socket->recvTimeout == 0U) { vTaskDelay(pdMS_TO_TICKS(1U)); }
    }
}

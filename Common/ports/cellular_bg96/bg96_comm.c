/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "platform.h"
#include "r_sci_rx_if.h"
#include "r_sci_rx_pinset.h"
#include "bg96_network.h"

struct CellularCommInterfaceContext
{
    sci_hdl_t uart;
    QueueHandle_t rx;
    CellularCommInterfaceReceiveCallback_t receive;
    void * user;
    volatile bool overflow;
    bool flowPending;
    bool flowEnabled;
    char responseLine[8];
    unsigned int lineLength;
};
static struct CellularCommInterfaceContext comm;

/* AE-LTE-CATM1-BG96-BO uses transistor inversion on RESET_N/PWRKEY.
 * Preserve CK-RX65N's P55/PB7/PB6 wiring, PJ3 CTS and P02 RTS. */
static void configurePins(void)
{
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_MPC);
    MPC.P55PFS.BYTE = 0U; PORT5.PMR.BIT.B5 = 0U;
    PORT5.PODR.BIT.B5 = 0U; PORT5.PDR.BIT.B5 = 1U;
    MPC.PB7PFS.BYTE = 0U; PORTB.PMR.BIT.B7 = 0U;
    PORTB.PODR.BIT.B7 = 0U; PORTB.PDR.BIT.B7 = 1U;
    MPC.PB6PFS.BYTE = 0U; PORTB.PMR.BIT.B6 = 0U; PORTB.PDR.BIT.B6 = 0U;
    MPC.P02PFS.BYTE = 0U; PORT0.PMR.BIT.B2 = 0U;
    PORT0.PODR.BIT.B2 = 0U; PORT0.PDR.BIT.B2 = 1U;
    /* CTS6#/RTS6# must remain input until AT+IFC has been accepted. */
    PORTJ.PMR.BIT.B3 = 0U; PORTJ.PDR.BIT.B3 = 0U;
    R_BSP_RegisterProtectEnable(BSP_REG_PROTECT_MPC);
}

static void uartCallback(void * argument)
{
    sci_cb_args_t * args = argument;
    BaseType_t wake = pdFALSE;
    if ((args->event == SCI_EVT_RX_CHAR) || (args->event == SCI_EVT_RXBUF_OVFL))
    {
        if ((comm.rx == NULL) || (xQueueSendFromISR(comm.rx, &args->byte, &wake) != pdPASS))
        { comm.overflow = true; }
        if ((comm.receive != NULL) &&
            (comm.receive(comm.user, &comm) == IOT_COMM_INTERFACE_SUCCESS)) { wake = pdTRUE; }
        portYIELD_FROM_ISR(wake);
    }
}

static bool openUart(uint32_t baud)
{
    sci_cfg_t config = {0};
    R_SCI_PinSet_SCI6();
    /* PinSet selects the shared CTS/RTS peripheral: immediately undo that
     * selection before enabling the SCI so it cannot drive the modem CTS net. */
    PORTJ.PMR.BIT.B3 = 0U; PORTJ.PDR.BIT.B3 = 0U;
    config.async.baud_rate = baud;
    config.async.clk_src = SCI_CLK_INT;
    config.async.data_size = SCI_DATA_8BIT;
    config.async.parity_en = SCI_PARITY_OFF;
    config.async.parity_type = SCI_EVEN_PARITY;
    config.async.stop_bits = SCI_STOPBITS_1;
    config.async.int_priority = configMAX_SYSCALL_INTERRUPT_PRIORITY;
    return R_SCI_Open(SCI_CH6, SCI_MODE_ASYNC, &config, uartCallback, &comm.uart) == SCI_SUCCESS;
}

static bool probeUart(void)
{
    static const uint32_t rates[] = {115200U, 460800U, 921600U};
    unsigned int index;
    uint8_t byte;
    for (index = 0; index < sizeof(rates)/sizeof(rates[0]); index++)
    {
        char reply[64] = {0};
        size_t used = 0;
        TickType_t began;
        if (!openUart(rates[index])) { return false; }
        while (xQueueReceive(comm.rx, &byte, 0U) == pdPASS) { }
        if (R_SCI_Send(comm.uart, (uint8_t *)"AT\r", 3U) == SCI_SUCCESS)
        {
            began = xTaskGetTickCount();
            while ((xTaskGetTickCount() - began) < pdMS_TO_TICKS(1000U))
            {
                if ((xQueueReceive(comm.rx, &byte, pdMS_TO_TICKS(20U)) == pdPASS) && (used < sizeof(reply)-1U))
                { reply[used++] = (char)byte; reply[used] = 0; }
                if (strstr(reply, "\r\nOK\r\n") != NULL) { return true; }
            }
        }
        (void)R_SCI_Close(comm.uart); comm.uart = NULL;
    }
    return false;
}

static CellularCommInterfaceError_t closeComm(CellularCommInterfaceHandle_t handle)
{
    if (handle != &comm) { return IOT_COMM_INTERFACE_BAD_PARAMETER; }
    comm.receive = NULL;
    if (comm.uart != NULL) { (void)R_SCI_Close(comm.uart); comm.uart = NULL; }
    if (comm.rx != NULL) { vQueueDelete(comm.rx); comm.rx = NULL; }
    comm.flowEnabled = false;
    PORTJ.PMR.BIT.B3 = 0U; PORTJ.PDR.BIT.B3 = 0U;
    return IOT_COMM_INTERFACE_SUCCESS;
}

static CellularCommInterfaceError_t openComm(CellularCommInterfaceReceiveCallback_t receive,
                                            void * user, CellularCommInterfaceHandle_t * result)
{
    TickType_t began;
    if ((receive == NULL) || (result == NULL)) { return IOT_COMM_INTERFACE_BAD_PARAMETER; }
    *result = NULL;
    if (comm.uart != NULL) { return IOT_COMM_INTERFACE_BUSY; }
    memset(&comm, 0, sizeof(comm));
    comm.rx = xQueueCreate(8192U, sizeof(uint8_t));
    if (comm.rx == NULL) { return IOT_COMM_INTERFACE_NO_MEMORY; }
    configurePins();
    if (PORTB.PIDR.BIT.B6 == 0U)
    {
        PORTB.PODR.BIT.B7 = 1U; vTaskDelay(pdMS_TO_TICKS(700U)); PORTB.PODR.BIT.B7 = 0U;
        began = xTaskGetTickCount();
        while ((PORTB.PIDR.BIT.B6 == 0U) && ((xTaskGetTickCount()-began) < pdMS_TO_TICKS(15000U)))
        { vTaskDelay(pdMS_TO_TICKS(50U)); }
    }
    if ((PORTB.PIDR.BIT.B6 == 0U) || !probeUart())
    {
        /* One defined recovery from stale modem/UART state; never claim ready
         * unless the subsequent AT exchange succeeds. */
        PORT5.PODR.BIT.B5 = 1U; vTaskDelay(pdMS_TO_TICKS(200U)); PORT5.PODR.BIT.B5 = 0U;
        vTaskDelay(pdMS_TO_TICKS(5000U));
        if (!probeUart()) { (void)closeComm(&comm); return IOT_COMM_INTERFACE_DRIVER_ERROR; }
    }
    comm.overflow = false;
    comm.receive = receive; comm.user = user; *result = &comm;
    return IOT_COMM_INTERFACE_SUCCESS;
}

static CellularCommInterfaceError_t sendComm(CellularCommInterfaceHandle_t handle,
                                            const uint8_t * data, uint32_t length,
                                            uint32_t timeoutMs, uint32_t * sent)
{
    TickType_t began = xTaskGetTickCount();
    if ((handle != &comm) || (comm.uart == NULL) || (data == NULL) || (sent == NULL))
    { return IOT_COMM_INTERFACE_BAD_PARAMETER; }
    *sent = 0U;
    if ((length >= 10U) && (memcmp(data, "AT+IFC=2,2", 10U) == 0))
    { comm.flowPending = true; comm.lineLength = 0U; }
    while (*sent < length)
    {
        uint16_t chunk = (uint16_t)((length-*sent > 64U) ? 64U : length-*sent);
        sci_err_t status = R_SCI_Send(comm.uart, (uint8_t *)(data+*sent), chunk);
        if (status == SCI_SUCCESS) { *sent += chunk; }
        else if ((status == SCI_ERR_INSUFFICIENT_SPACE) || (status == SCI_ERR_XCVR_BUSY))
        {
            if ((timeoutMs != 0U) && ((xTaskGetTickCount()-began) >= pdMS_TO_TICKS(timeoutMs)))
            { return IOT_COMM_INTERFACE_TIMEOUT; }
            vTaskDelay(pdMS_TO_TICKS(1U));
        }
        else { return IOT_COMM_INTERFACE_DRIVER_ERROR; }
    }
    return IOT_COMM_INTERFACE_SUCCESS;
}

static bool handleFlowAcknowledgement(uint8_t byte)
{
    if (!comm.flowPending) { return true; }
    if (byte == '\n')
    {
        comm.responseLine[comm.lineLength] = 0;
        if (strcmp(comm.responseLine, "OK") == 0)
        {
            if (R_SCI_Control(comm.uart, SCI_CMD_EN_CTS_IN, NULL) != SCI_SUCCESS) { return false; }
            PORTJ.PDR.BIT.B3 = 0U; PORTJ.PMR.BIT.B3 = 1U;
            comm.flowPending = false; comm.flowEnabled = true;
        }
        else if (strcmp(comm.responseLine, "ERROR") == 0) { comm.flowPending = false; }
        comm.lineLength = 0U;
    }
    else if ((byte != '\r') && (comm.lineLength < sizeof(comm.responseLine)-1U))
    { comm.responseLine[comm.lineLength++] = (char)byte; }
    return true;
}

static CellularCommInterfaceError_t recvComm(CellularCommInterfaceHandle_t handle,
                                            uint8_t * data, uint32_t capacity,
                                            uint32_t timeoutMs, uint32_t * received)
{
    uint8_t byte;
    if ((handle != &comm) || (data == NULL) || (capacity == 0U) || (received == NULL))
    { return IOT_COMM_INTERFACE_BAD_PARAMETER; }
    *received = 0U;
    if (comm.overflow) { return IOT_COMM_INTERFACE_DRIVER_ERROR; }
    if (xQueueReceive(comm.rx, &byte, pdMS_TO_TICKS(timeoutMs)) != pdPASS)
    { return IOT_COMM_INTERFACE_TIMEOUT; }
    do
    {
        if (!handleFlowAcknowledgement(byte)) { return IOT_COMM_INTERFACE_DRIVER_ERROR; }
        data[(*received)++] = byte;
    } while ((*received < capacity) && (xQueueReceive(comm.rx, &byte, 0U) == pdPASS));
    return IOT_COMM_INTERFACE_SUCCESS;
}

bool Bg96_CommSetRuntimeBaud(void)
{
    sci_baud_t baud = {BSP_PCLKB_HZ, 460800U};
    return (comm.uart != NULL) && comm.flowEnabled &&
           (R_SCI_Control(comm.uart, SCI_CMD_CHANGE_BAUD, &baud) == SCI_SUCCESS);
}

const CellularCommInterface_t Bg96_CommInterface = {openComm, sendComm, recvComm, closeComm};

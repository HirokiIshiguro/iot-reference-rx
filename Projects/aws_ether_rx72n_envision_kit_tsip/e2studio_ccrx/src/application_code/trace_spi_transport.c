/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

/**********************************************************************************************************************
 * File Name    : trace_spi_transport.c
 * Description  : Tracealyzer PSF byte stream transport over SCI2 simple-SPI.
 *********************************************************************************************************************/

#include "trace_spi_transport.h"

#include <stdbool.h>
#include <string.h>

#include "platform.h"
#include "r_sci_rx_if.h"
#include "r_pinset.h"
#include "FreeRTOS.h"
#include "task.h"

void R_SCI_PinSet_SCI2(void);

#define TRACE_SPI_CHANNEL          (SCI_CH2)
#ifndef TRACE_SPI_BIT_RATE
#define TRACE_SPI_BIT_RATE         (2000000UL)
#endif
#ifndef TRACE_SPI_INTER_FRAME_DELAY_TICKS
#define TRACE_SPI_INTER_FRAME_DELAY_TICKS (0U)
#endif
#ifndef TRACE_SPI_FRAMES_PER_BURST
#define TRACE_SPI_FRAMES_PER_BURST (1U)
#endif
#ifndef TRACE_SPI_INTER_BURST_DELAY_TICKS
#define TRACE_SPI_INTER_BURST_DELAY_TICKS (1U)
#endif
#ifndef TRACE_SPI_CS_SETUP_DELAY_US
#define TRACE_SPI_CS_SETUP_DELAY_US (2U)
#endif
#ifndef TRACE_SPI_CS_HOLD_DELAY_US
#define TRACE_SPI_CS_HOLD_DELAY_US (10U)
#endif
#define TRACE_SPI_INT_PRIORITY     ((uint8_t) configMAX_SYSCALL_INTERRUPT_PRIORITY)
#define TRACE_SPI_TRANSFER_NOTIFICATION_INDEX (3U)
#define TRACE_SPI_SEND_TIMEOUT_MS  (100U)
#define TRACE_SPI_FALLBACK_SPIN_TIMEOUT (2000000UL)

volatile uint32_t g_trace_spi_initialized;
volatile uint32_t g_trace_spi_frame_count;
volatile uint32_t g_trace_spi_payload_byte_count;
volatile uint32_t g_trace_spi_error_count;
volatile uint32_t g_trace_spi_timeout_count;
volatile uint32_t g_trace_spi_last_error;
volatile uint32_t g_trace_spi_control_frame_count;
volatile uint32_t g_trace_spi_control_byte_count;
volatile uint32_t g_trace_spi_control_read_count;
volatile uint32_t g_trace_spi_control_drop_count;

static sci_hdl_t s_sci_handle = FIT_NO_PTR;
static volatile bool s_transfer_done;
static volatile TaskHandle_t s_transfer_task_handle;
static uint8_t s_sequence;
static uint16_t s_burst_frame_count;
static uint8_t s_control_buffer[TRACE_SPI_TRANSPORT_CONTROL_BUFFER_BYTES];
static size_t s_control_head;
static size_t s_control_tail;
static size_t s_control_count;

static void trace_spi_callback(void * p_args);
static void trace_spi_configure_cs_pin(void);
static void trace_spi_cs_low(void);
static void trace_spi_cs_high(void);
static int trace_spi_exchange_frame(const uint8_t * p_frame, uint8_t * p_rx_frame);
static bool trace_spi_wait_for_transfer_done(void);
static void trace_spi_apply_pacing(void);
static void trace_spi_process_control_frame(const uint8_t * p_frame);
static size_t trace_spi_pop_control(uint8_t * p_buffer, size_t max_bytes);

int TraceSpiTransport_Init(void)
{
    sci_cfg_t cfg;
    sci_err_t sci_error;

    if (FIT_NO_PTR != s_sci_handle)
    {
        g_trace_spi_initialized = 1u;
        return 0;
    }

    cfg.sspi.spi_mode = SCI_SPI_MODE_1;
    cfg.sspi.bit_rate = TRACE_SPI_BIT_RATE;
    cfg.sspi.msb_first = true;
    cfg.sspi.invert_data = false;
    cfg.sspi.int_priority = TRACE_SPI_INT_PRIORITY;

    sci_error = R_SCI_Open(TRACE_SPI_CHANNEL, SCI_MODE_SSPI, &cfg, trace_spi_callback, &s_sci_handle);
    if (SCI_SUCCESS != sci_error)
    {
        s_sci_handle = FIT_NO_PTR;
        g_trace_spi_last_error = (uint32_t) sci_error;
        g_trace_spi_error_count++;
        return -1;
    }

    R_SCI_PinSet_SCI2();
    trace_spi_configure_cs_pin();
    trace_spi_cs_high();

    g_trace_spi_initialized = 1u;
    return 0;
}

int TraceSpiTransport_Write(const void * p_data, size_t length, size_t * p_bytes_written)
{
    const uint8_t * p_source = (const uint8_t *) p_data;
    size_t offset = 0u;

    if (p_bytes_written != NULL)
    {
        *p_bytes_written = 0u;
    }

    if ((p_source == NULL) && (length != 0u))
    {
        g_trace_spi_error_count++;
        g_trace_spi_last_error = 0xBAD00001u;
        return -1;
    }

    if (TraceSpiTransport_Init() != 0)
    {
        return -1;
    }

    while (offset < length)
    {
        uint8_t frame[TRACE_SPI_TRANSPORT_FRAME_BYTES];
        size_t payload_length = length - offset;

        if (payload_length > TRACE_SPI_TRANSPORT_PAYLOAD_BYTES)
        {
            payload_length = TRACE_SPI_TRANSPORT_PAYLOAD_BYTES;
        }

        (void) memset(frame, 0, sizeof(frame));
        frame[0] = TRACE_SPI_TRANSPORT_MAGIC0;
        frame[1] = TRACE_SPI_TRANSPORT_MAGIC1;
        frame[2] = (uint8_t) payload_length;
        frame[3] = s_sequence++;
        (void) memcpy(&frame[4], &p_source[offset], payload_length);

        {
            uint8_t rx_frame[TRACE_SPI_TRANSPORT_FRAME_BYTES];

            if (trace_spi_exchange_frame(frame, rx_frame) != 0)
            {
                return -1;
            }
            trace_spi_process_control_frame(rx_frame);
            trace_spi_apply_pacing();
        }

#if (TRACE_SPI_INTER_FRAME_DELAY_TICKS > 0U)
        vTaskDelay((TickType_t) TRACE_SPI_INTER_FRAME_DELAY_TICKS);
#endif

        offset += payload_length;
        if (p_bytes_written != NULL)
        {
            *p_bytes_written = offset;
        }
        g_trace_spi_payload_byte_count += (uint32_t) payload_length;
    }

    return 0;
}

int TraceSpiTransport_Read(void * p_data, size_t length, size_t * p_bytes_read)
{
    uint8_t * p_destination = (uint8_t *) p_data;
    size_t copied;

    if (p_bytes_read != NULL)
    {
        *p_bytes_read = 0u;
    }

    if ((p_destination == NULL) && (length != 0u))
    {
        g_trace_spi_error_count++;
        g_trace_spi_last_error = 0xBAD00005u;
        return -1;
    }

    if (TraceSpiTransport_Init() != 0)
    {
        return -1;
    }

    copied = trace_spi_pop_control(p_destination, length);
    if ((copied == 0u) && (length > 0u))
    {
        uint8_t tx_frame[TRACE_SPI_TRANSPORT_FRAME_BYTES];
        uint8_t rx_frame[TRACE_SPI_TRANSPORT_FRAME_BYTES];

        (void) memset(tx_frame, 0, sizeof(tx_frame));
        tx_frame[0] = TRACE_SPI_TRANSPORT_MAGIC0;
        tx_frame[1] = TRACE_SPI_TRANSPORT_MAGIC1;
        tx_frame[2] = 0u;
        tx_frame[3] = s_sequence++;

        if (trace_spi_exchange_frame(tx_frame, rx_frame) != 0)
        {
            return -1;
        }

        trace_spi_process_control_frame(rx_frame);
        trace_spi_apply_pacing();
        copied = trace_spi_pop_control(p_destination, length);
    }

    if (p_bytes_read != NULL)
    {
        *p_bytes_read = copied;
    }
    g_trace_spi_control_read_count += (uint32_t) copied;

    return 0;
}

static void trace_spi_callback(void * p_args)
{
    sci_cb_args_t * p_sci_args = (sci_cb_args_t *) p_args;
    BaseType_t higher_priority_task_woken = pdFALSE;

    if ((FIT_NO_PTR != p_sci_args) && (SCI_EVT_XFER_DONE == p_sci_args->event))
    {
        TaskHandle_t task_to_notify;

        s_transfer_done = true;
        task_to_notify = s_transfer_task_handle;
        if (task_to_notify != NULL)
        {
            vTaskNotifyGiveIndexedFromISR(task_to_notify,
                                          TRACE_SPI_TRANSFER_NOTIFICATION_INDEX,
                                          &higher_priority_task_woken);
            portYIELD_FROM_ISR(higher_priority_task_woken);
        }
    }
}

static void trace_spi_configure_cs_pin(void)
{
    PORT5.PMR.BIT.B4 = 0U;
    PORT5.PODR.BIT.B4 = 1U;
    PORT5.PDR.BIT.B4 = 1U;
}

static void trace_spi_cs_low(void)
{
    PORT5.PODR.BIT.B4 = 0U;
}

static void trace_spi_cs_high(void)
{
    PORT5.PODR.BIT.B4 = 1U;
}

static int trace_spi_exchange_frame(const uint8_t * p_frame, uint8_t * p_rx_frame)
{
    if ((FIT_NO_PTR == s_sci_handle) || (p_frame == NULL) || (p_rx_frame == NULL))
    {
        g_trace_spi_error_count++;
        g_trace_spi_last_error = 0xBAD00002u;
        return -1;
    }

    s_transfer_done = false;
    s_transfer_task_handle = NULL;
    if (xTaskGetSchedulerState() == taskSCHEDULER_RUNNING)
    {
        (void) ulTaskNotifyTakeIndexed(TRACE_SPI_TRANSFER_NOTIFICATION_INDEX, pdTRUE, 0);
        s_transfer_task_handle = xTaskGetCurrentTaskHandle();
    }

    trace_spi_cs_low();
#if (TRACE_SPI_CS_SETUP_DELAY_US > 0U)
    (void) R_BSP_SoftwareDelay((uint32_t) TRACE_SPI_CS_SETUP_DELAY_US, BSP_DELAY_MICROSECS);
#endif

    if (SCI_SUCCESS != R_SCI_SendReceive(s_sci_handle,
                                         (uint8_t *) p_frame,
                                         p_rx_frame,
                                         (uint16_t) TRACE_SPI_TRANSPORT_FRAME_BYTES))
    {
        s_transfer_task_handle = NULL;
        trace_spi_cs_high();
        g_trace_spi_error_count++;
        g_trace_spi_last_error = 0xBAD00003u;
        return -1;
    }

    if (!trace_spi_wait_for_transfer_done())
    {
        s_transfer_task_handle = NULL;
        (void) R_SCI_Control(s_sci_handle, SCI_CMD_ABORT_XFER, FIT_NO_PTR);
        trace_spi_cs_high();
        g_trace_spi_timeout_count++;
        g_trace_spi_last_error = 0xBAD00004u;
        return -1;
    }

    s_transfer_task_handle = NULL;
#if (TRACE_SPI_CS_HOLD_DELAY_US > 0U)
    (void) R_BSP_SoftwareDelay((uint32_t) TRACE_SPI_CS_HOLD_DELAY_US, BSP_DELAY_MICROSECS);
#endif
    trace_spi_cs_high();

    g_trace_spi_frame_count++;
    return 0;
}

static bool trace_spi_wait_for_transfer_done(void)
{
    if (xTaskGetSchedulerState() == taskSCHEDULER_RUNNING)
    {
        TickType_t timeout_ticks = pdMS_TO_TICKS(TRACE_SPI_SEND_TIMEOUT_MS);

        if (timeout_ticks == 0u)
        {
            timeout_ticks = 1u;
        }

        (void) ulTaskNotifyTakeIndexed(TRACE_SPI_TRANSFER_NOTIFICATION_INDEX, pdTRUE, timeout_ticks);
        return s_transfer_done;
    }
    else
    {
        uint32_t timeout = TRACE_SPI_FALLBACK_SPIN_TIMEOUT;

        while ((false == s_transfer_done) && (timeout > 0UL))
        {
            timeout--;
        }

        return (timeout != 0UL);
    }
}

static void trace_spi_apply_pacing(void)
{
#if (TRACE_SPI_FRAMES_PER_BURST > 0U) && (TRACE_SPI_INTER_BURST_DELAY_TICKS > 0U)
    s_burst_frame_count++;
    if (s_burst_frame_count >= TRACE_SPI_FRAMES_PER_BURST)
    {
        s_burst_frame_count = 0u;
        if (xTaskGetSchedulerState() == taskSCHEDULER_RUNNING)
        {
            vTaskDelay((TickType_t) TRACE_SPI_INTER_BURST_DELAY_TICKS);
        }
    }
#endif
}

static void trace_spi_process_control_frame(const uint8_t * p_frame)
{
    uint8_t payload_length;
    uint32_t index;

    if (p_frame == NULL)
    {
        return;
    }

    if ((p_frame[0] != TRACE_SPI_TRANSPORT_CONTROL_MAGIC0) ||
        (p_frame[1] != TRACE_SPI_TRANSPORT_CONTROL_MAGIC1))
    {
        return;
    }

    payload_length = p_frame[2];
    if (payload_length > TRACE_SPI_TRANSPORT_PAYLOAD_BYTES)
    {
        return;
    }

    taskENTER_CRITICAL();
    for (index = 0u; index < payload_length; index++)
    {
        if (s_control_count < sizeof(s_control_buffer))
        {
            s_control_buffer[s_control_head] = p_frame[4u + index];
            s_control_head++;
            if (s_control_head >= sizeof(s_control_buffer))
            {
                s_control_head = 0u;
            }
            s_control_count++;
            g_trace_spi_control_byte_count++;
        }
        else
        {
            g_trace_spi_control_drop_count++;
        }
    }
    taskEXIT_CRITICAL();

    g_trace_spi_control_frame_count++;
}

static size_t trace_spi_pop_control(uint8_t * p_buffer, size_t max_bytes)
{
    size_t copied = 0u;

    if ((p_buffer == NULL) || (max_bytes == 0u))
    {
        return 0u;
    }

    taskENTER_CRITICAL();
    while ((copied < max_bytes) && (s_control_count > 0u))
    {
        p_buffer[copied] = s_control_buffer[s_control_tail];
        s_control_tail++;
        if (s_control_tail >= sizeof(s_control_buffer))
        {
            s_control_tail = 0u;
        }
        s_control_count--;
        copied++;
    }
    taskEXIT_CRITICAL();

    return copied;
}

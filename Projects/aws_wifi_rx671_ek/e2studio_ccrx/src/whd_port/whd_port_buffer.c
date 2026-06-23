/*
 * Static WHD packet buffer pool.
 *
 * This is deliberately simple for bring-up: enough headroom for WHD's internal
 * headers and enough payload for an Ethernet MTU plus bus framing.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include "FreeRTOS.h"
#include "task.h"

#include "whd.h"
#include "whd_network_types.h"
#include "whd_port.h"

#define WHD_PORT_BUFFER_COUNT           (16U)
#define WHD_PORT_BUFFER_HEADROOM        (128U)
#define WHD_PORT_BUFFER_TX_ALIGN_BIAS   (2U)
#define WHD_PORT_BUFFER_PAYLOAD         (2048U)
#define WHD_PORT_BUFFER_STORAGE         (WHD_PORT_BUFFER_HEADROOM + WHD_PORT_BUFFER_TX_ALIGN_BIAS + WHD_PORT_BUFFER_PAYLOAD)
#define WHD_PORT_BUFFER_WORDS           ((WHD_PORT_BUFFER_STORAGE + sizeof(uint32_t) - 1U) / sizeof(uint32_t))

typedef struct st_whd_port_buffer
{
    bool     in_use;
    uint8_t * p_current;
    uint16_t  current_size;
    uint32_t  storage[WHD_PORT_BUFFER_WORDS];
} whd_port_buffer_t;

static whd_port_buffer_t g_whd_port_buffers[WHD_PORT_BUFFER_COUNT];

static uint8_t * whd_port_buffer_start(whd_port_buffer_t * p_slot)
{
    return (uint8_t *)p_slot->storage;
}

static uint8_t * whd_port_buffer_end(whd_port_buffer_t * p_slot)
{
    return &whd_port_buffer_start(p_slot)[WHD_PORT_BUFFER_STORAGE];
}

static whd_port_buffer_t * whd_port_buffer_from_handle(whd_buffer_t buffer)
{
    uint32_t i;

    for (i = 0U; i < WHD_PORT_BUFFER_COUNT; i++)
    {
        if ((whd_buffer_t)&g_whd_port_buffers[i] == buffer)
        {
            return &g_whd_port_buffers[i];
        }
    }

    return NULL;
}

static whd_result_t whd_port_host_buffer_get(whd_buffer_t * buffer, whd_buffer_dir_t direction,
                                             unsigned short size, unsigned long wait)
{
    if (NULL == buffer)
    {
        return WHD_BADARG;
    }

    if (size > WHD_PORT_BUFFER_PAYLOAD)
    {
        *buffer = NULL;
        return WHD_BUFFER_UNAVAILABLE_PERMANENT;
    }

    do
    {
        uint32_t i;

        taskENTER_CRITICAL();
        for (i = 0U; i < WHD_PORT_BUFFER_COUNT; i++)
        {
            whd_port_buffer_t * p_slot = &g_whd_port_buffers[i];

            if (!p_slot->in_use)
            {
                uint32_t headroom = WHD_PORT_BUFFER_HEADROOM;

                if (WHD_NETWORK_TX == direction)
                {
                    headroom += WHD_PORT_BUFFER_TX_ALIGN_BIAS;
                }

                p_slot->in_use      = true;
                p_slot->p_current   = &whd_port_buffer_start(p_slot)[headroom];
                p_slot->current_size = (uint16_t)size;
                *buffer = (whd_buffer_t)p_slot;
                taskEXIT_CRITICAL();
                return WHD_SUCCESS;
            }
        }
        taskEXIT_CRITICAL();

        if (0UL == wait)
        {
            *buffer = NULL;
            return WHD_BUFFER_UNAVAILABLE_TEMPORARY;
        }

        vTaskDelay(pdMS_TO_TICKS(1U));
    } while (true);
}

static void whd_port_buffer_release(whd_buffer_t buffer, whd_buffer_dir_t direction)
{
    whd_port_buffer_t * p_slot;

    (void)direction;

    p_slot = whd_port_buffer_from_handle(buffer);
    if (NULL == p_slot)
    {
        return;
    }

    taskENTER_CRITICAL();
    p_slot->in_use = false;
    p_slot->p_current = NULL;
    p_slot->current_size = 0U;
    taskEXIT_CRITICAL();
}

void whd_port_buffer_release_from_network(whd_buffer_t buffer)
{
    whd_port_buffer_release(buffer, WHD_NETWORK_RX);
}

static uint8_t * whd_port_buffer_get_current_piece_data_pointer(whd_buffer_t buffer)
{
    whd_port_buffer_t * p_slot = whd_port_buffer_from_handle(buffer);

    return (NULL == p_slot) ? NULL : p_slot->p_current;
}

static uint16_t whd_port_buffer_get_current_piece_size(whd_buffer_t buffer)
{
    whd_port_buffer_t * p_slot = whd_port_buffer_from_handle(buffer);

    return (NULL == p_slot) ? 0U : p_slot->current_size;
}

static whd_result_t whd_port_buffer_set_size(whd_buffer_t buffer, unsigned short size)
{
    whd_port_buffer_t * p_slot = whd_port_buffer_from_handle(buffer);

    if ((NULL == p_slot) || (NULL == p_slot->p_current))
    {
        return WHD_BADARG;
    }
    if (&p_slot->p_current[size] > whd_port_buffer_end(p_slot))
    {
        return WHD_BUFFER_SIZE_SET_ERROR;
    }

    p_slot->current_size = (uint16_t)size;
    return WHD_SUCCESS;
}

static whd_result_t whd_port_buffer_add_remove_at_front(whd_buffer_t * buffer, int32_t add_remove_amount)
{
    whd_port_buffer_t * p_slot;
    uint8_t * p_start;

    if ((NULL == buffer) || (NULL == *buffer))
    {
        return WHD_BADARG;
    }

    p_slot = whd_port_buffer_from_handle(*buffer);
    if ((NULL == p_slot) || (NULL == p_slot->p_current))
    {
        return WHD_BADARG;
    }

    p_start = whd_port_buffer_start(p_slot);

    if (add_remove_amount < 0)
    {
        uint32_t amount = (uint32_t)(-add_remove_amount);

        if ((uint32_t)(p_slot->p_current - p_start) < amount)
        {
            return WHD_BUFFER_POINTER_MOVE_ERROR;
        }
        p_slot->p_current -= amount;
        p_slot->current_size = (uint16_t)(p_slot->current_size + amount);
    }
    else
    {
        uint32_t amount = (uint32_t)add_remove_amount;

        if (amount > p_slot->current_size)
        {
            return WHD_BUFFER_POINTER_MOVE_ERROR;
        }
        p_slot->p_current += amount;
        p_slot->current_size = (uint16_t)(p_slot->current_size - amount);
    }

    return WHD_SUCCESS;
}

whd_buffer_funcs_t g_whd_port_buffer_funcs =
{
    whd_port_host_buffer_get,
    whd_port_buffer_release,
    whd_port_buffer_get_current_piece_data_pointer,
    whd_port_buffer_get_current_piece_size,
    whd_port_buffer_set_size,
    whd_port_buffer_add_remove_at_front,
};

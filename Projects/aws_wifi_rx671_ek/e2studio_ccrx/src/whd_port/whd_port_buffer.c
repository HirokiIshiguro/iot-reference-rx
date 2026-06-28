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

#ifndef WHD_PORT_BUFFER_COUNT
#define WHD_PORT_BUFFER_COUNT           (4U)
#endif
#ifndef WHD_PORT_BUFFER_HEADROOM
#define WHD_PORT_BUFFER_HEADROOM        (128U)
#endif
#ifndef WHD_PORT_BUFFER_TX_ALIGN_BIAS
#define WHD_PORT_BUFFER_TX_ALIGN_BIAS   (2U)
#endif
#ifndef WHD_PORT_BUFFER_PAYLOAD
#define WHD_PORT_BUFFER_PAYLOAD         (2048U)
#endif

#if WHD_PORT_BUFFER_COUNT < 1
#error "WHD_PORT_BUFFER_COUNT must be at least 1."
#endif

#if WHD_PORT_BUFFER_PAYLOAD < 1536
#error "WHD_PORT_BUFFER_PAYLOAD must hold a full Ethernet frame."
#endif

#if WHD_PORT_BUFFER_HEADROOM < 64
#error "WHD_PORT_BUFFER_HEADROOM is too small for WHD SDPCM/BDC header movement."
#endif

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
static uint16_t g_whd_port_buffer_free_stack[WHD_PORT_BUFFER_COUNT];
static uint16_t g_whd_port_buffer_free_top;
static bool g_whd_port_buffer_free_initialized;

volatile uint32_t g_whd_port_buffer_get_count;
volatile uint32_t g_whd_port_buffer_release_count;
volatile uint32_t g_whd_port_buffer_current_in_use;
volatile uint32_t g_whd_port_buffer_max_in_use;
volatile uint32_t g_whd_port_buffer_alloc_temp_fail_count;
volatile uint32_t g_whd_port_buffer_alloc_perm_fail_count;
volatile uint32_t g_whd_port_buffer_wait_count;
volatile uint32_t g_whd_port_buffer_wait_loop_count;
volatile uint32_t g_whd_port_buffer_bad_release_count;
volatile uint32_t g_whd_port_buffer_double_release_count;
volatile uint32_t g_whd_port_buffer_last_request_size;
volatile uint32_t g_whd_port_buffer_last_request_direction;
volatile uint32_t g_whd_port_buffer_last_wait_ms;
volatile uint32_t g_whd_port_buffer_last_slot;

static uint8_t * whd_port_buffer_start(whd_port_buffer_t * p_slot)
{
    return (uint8_t *)p_slot->storage;
}

static uint8_t * whd_port_buffer_end(whd_port_buffer_t * p_slot)
{
    return &whd_port_buffer_start(p_slot)[WHD_PORT_BUFFER_STORAGE];
}

static void whd_port_buffer_init_free_stack_locked(void)
{
    uint16_t i;

    if (g_whd_port_buffer_free_initialized)
    {
        return;
    }

    for (i = 0U; i < WHD_PORT_BUFFER_COUNT; i++)
    {
        g_whd_port_buffer_free_stack[i] = (uint16_t)(WHD_PORT_BUFFER_COUNT - 1U - i);
        g_whd_port_buffers[i].in_use = false;
        g_whd_port_buffers[i].p_current = NULL;
        g_whd_port_buffers[i].current_size = 0U;
    }
    g_whd_port_buffer_free_top = WHD_PORT_BUFFER_COUNT;
    g_whd_port_buffer_current_in_use = 0U;
    g_whd_port_buffer_max_in_use = 0U;
    g_whd_port_buffer_free_initialized = true;
}

static whd_port_buffer_t * whd_port_buffer_from_handle(whd_buffer_t buffer)
{
    whd_port_buffer_t * p_slot = (whd_port_buffer_t *)buffer;

    if ((p_slot >= &g_whd_port_buffers[0]) &&
        (p_slot < &g_whd_port_buffers[WHD_PORT_BUFFER_COUNT]))
    {
        return p_slot;
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

    g_whd_port_buffer_get_count++;
    g_whd_port_buffer_last_request_size = (uint32_t)size;
    g_whd_port_buffer_last_request_direction = (uint32_t)direction;
    g_whd_port_buffer_last_wait_ms = (uint32_t)wait;

    if (size > WHD_PORT_BUFFER_PAYLOAD)
    {
        g_whd_port_buffer_alloc_perm_fail_count++;
        *buffer = NULL;
        return WHD_BUFFER_UNAVAILABLE_PERMANENT;
    }

    do
    {
        taskENTER_CRITICAL();
        whd_port_buffer_init_free_stack_locked();
        if (g_whd_port_buffer_free_top > 0U)
        {
            uint16_t index = g_whd_port_buffer_free_stack[--g_whd_port_buffer_free_top];
            whd_port_buffer_t * p_slot = &g_whd_port_buffers[index];
            uint32_t headroom = WHD_PORT_BUFFER_HEADROOM;

            if (WHD_NETWORK_TX == direction)
            {
                headroom += WHD_PORT_BUFFER_TX_ALIGN_BIAS;
            }

            p_slot->in_use      = true;
            p_slot->p_current   = &whd_port_buffer_start(p_slot)[headroom];
            p_slot->current_size = (uint16_t)size;
            g_whd_port_buffer_current_in_use++;
            if (g_whd_port_buffer_current_in_use > g_whd_port_buffer_max_in_use)
            {
                g_whd_port_buffer_max_in_use = g_whd_port_buffer_current_in_use;
            }
            g_whd_port_buffer_last_slot = (uint32_t)index;
            *buffer = (whd_buffer_t)p_slot;
            taskEXIT_CRITICAL();
            return WHD_SUCCESS;
        }
        taskEXIT_CRITICAL();

        if (0UL == wait)
        {
            g_whd_port_buffer_alloc_temp_fail_count++;
            *buffer = NULL;
            return WHD_BUFFER_UNAVAILABLE_TEMPORARY;
        }

        g_whd_port_buffer_wait_count++;
        g_whd_port_buffer_wait_loop_count++;
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
        g_whd_port_buffer_bad_release_count++;
        return;
    }

    taskENTER_CRITICAL();
    whd_port_buffer_init_free_stack_locked();
    if (!p_slot->in_use)
    {
        g_whd_port_buffer_double_release_count++;
        taskEXIT_CRITICAL();
        return;
    }

    p_slot->in_use = false;
    p_slot->p_current = NULL;
    p_slot->current_size = 0U;
    g_whd_port_buffer_release_count++;
    if (g_whd_port_buffer_current_in_use > 0U)
    {
        g_whd_port_buffer_current_in_use--;
    }
    if (g_whd_port_buffer_free_top < WHD_PORT_BUFFER_COUNT)
    {
        g_whd_port_buffer_free_stack[g_whd_port_buffer_free_top++] =
            (uint16_t)(p_slot - &g_whd_port_buffers[0]);
    }
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

/*
 * cyhal_gpio - minimal WHD GPIO abstraction for the EK-RX671 / Type 1YN.
 *
 * WHD's SDIO bus driver references cyhal_gpio for the out-of-band host-wake line.
 * This board runs WHD in polled mode (no OOB interrupt - the in-band IRQ topology
 * livelocks), and the SDHI pins plus the WLAN enable are set up by the board pin
 * configuration, so these entry points are no-ops / success stubs.
 */
#include <stdint.h>
#include <stdbool.h>

#include "cy_result.h"
#include "cyhal_gpio.h"

cy_rslt_t cyhal_gpio_init(cyhal_gpio_t pin, cyhal_gpio_direction_t direction,
                          cyhal_gpio_drive_mode_t drvMode, bool initVal)
{
    (void)pin;
    (void)direction;
    (void)drvMode;
    (void)initVal;
    return CY_RSLT_SUCCESS;
}

void cyhal_gpio_free(cyhal_gpio_t pin)
{
    (void)pin;
}

void cyhal_gpio_write(cyhal_gpio_t pin, bool value)
{
    (void)pin;
    (void)value;
}

bool cyhal_gpio_read(cyhal_gpio_t pin)
{
    (void)pin;
    return false;
}

void cyhal_gpio_register_irq(cyhal_gpio_t pin, uint8_t intrPriority,
                             cyhal_gpio_irq_handler_t handler, void *handler_arg)
{
    (void)pin;
    (void)intrPriority;
    (void)handler;
    (void)handler_arg;
}

void cyhal_gpio_irq_enable(cyhal_gpio_t pin, cyhal_gpio_irq_event_t event, bool enable)
{
    (void)pin;
    (void)event;
    (void)enable;
}

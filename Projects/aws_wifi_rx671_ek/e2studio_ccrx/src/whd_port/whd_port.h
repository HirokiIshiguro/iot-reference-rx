/*
 * Minimal WHD port glue shared by the EK-RX671 bring-up files.
 */
#ifndef WHD_PORT_H_
#define WHD_PORT_H_

#include <stdbool.h>

#include "whd.h"
#include "whd_network_types.h"
#include "whd_resource_api.h"

extern whd_resource_source_t g_whd_port_resource_source;
extern whd_buffer_funcs_t    g_whd_port_buffer_funcs;
extern whd_netif_funcs_t     g_whd_port_netif_funcs;

void whd_port_buffer_release_from_network(whd_buffer_t buffer);
void whd_port_rtos_set_thread_context_irq(bool enabled);

#endif /* WHD_PORT_H_ */

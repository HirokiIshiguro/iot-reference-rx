/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef PRODUCT_R_CELLULAR_NETWORK_H
#define PRODUCT_R_CELLULAR_NETWORK_H
#include <stdbool.h>
#include "r_cellular_if.h"
extern st_cellular_ctrl_t cellular_ctrl;
bool Connect2AP(void);
bool RCellular_IsOpen(void);
/* Native IDT installs a copied profile only after its KVS commit succeeds. */
bool RCellular_SetRuntimeApConfig(const st_cellular_ap_cfg_t * config);
void RCellular_NetworkCleanup(void);
#endif

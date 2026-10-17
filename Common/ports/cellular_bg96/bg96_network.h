/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#ifndef PRODUCT_BG96_NETWORK_H
#define PRODUCT_BG96_NETWORK_H
#include <stdbool.h>
#include "cellular_config.h"
#include "cellular_config_defaults.h"
#include "cellular_api.h"
extern const CellularCommInterface_t Bg96_CommInterface;
CellularHandle_t Bg96_GetHandle(void);
/* Supply a copied IPv4 PDN profile before the first Connect2AP(). An active
 * modem session rejects changes. Otherwise use persisted PDN fields when the
 * BG96 KVS is selected, retaining board defaults for fields not stored. */
bool Bg96_SetRuntimePdnConfig(const CellularPdnConfig_t * config);
bool Connect2AP(void);
void Bg96_NetworkCleanup(void);
bool Bg96_CommSetRuntimeBaud(void);
#endif

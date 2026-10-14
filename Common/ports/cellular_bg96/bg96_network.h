/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#ifndef PRODUCT_BG96_NETWORK_H
#define PRODUCT_BG96_NETWORK_H
#include <stdbool.h>
#include "cellular_config.h"
#include "cellular_config_defaults.h"
#include "cellular_api.h"
extern const CellularCommInterface_t Bg96_CommInterface;
CellularHandle_t Bg96_GetHandle(void);
bool Connect2AP(void);
void Bg96_NetworkCleanup(void);
bool Bg96_CommSetRuntimeBaud(void);
#endif

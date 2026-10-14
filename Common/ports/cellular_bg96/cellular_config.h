/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#ifndef PRODUCT_CELLULAR_CONFIG_H
#define PRODUCT_CELLULAR_CONFIG_H
#include "FreeRTOS.h"
#include "bg96_board_config.h"
#if defined(__CCRX__)
#include "strtok_r.h"
#endif
#define CELLULAR_NUM_SOCKET_MAX 6U
#define CELLULAR_PDN_CONTEXT_ID 1U
#define CELLULAR_CONFIG_DEFAULT_RAT CELLULAR_RAT_CATM1
#define CELLULAR_BG96_SUPPPORT_DIRECT_PUSH_SOCKET 0
/* The host uses BG96 buffer mode and the official URC/QIRD decoder. */
/* Existing BG96 operation leaves band selection to the SIM/operator. */
#define CELLULAR_BG96_ENABLE_BAND_CONFIGURATION 0
#endif

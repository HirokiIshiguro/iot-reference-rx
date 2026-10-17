/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#ifndef PRODUCT_BG96_BOARD_CONFIG_H
#define PRODUCT_BG96_BOARD_CONFIG_H
/* CK-RX65N / BG96 carrier profile. Override these public configuration values
 * in the product configuration, rather than changing the cellular libraries. */
#ifndef BG96_APN_NAME
#define BG96_APN_NAME "iot.truphone.com"
#endif
#ifndef BG96_APN_USER
#define BG96_APN_USER ""
#endif
#ifndef BG96_APN_PASSWORD
#define BG96_APN_PASSWORD ""
#endif
#ifndef BG96_PDN_AUTH_TYPE
#define BG96_PDN_AUTH_TYPE 2
#endif
#endif

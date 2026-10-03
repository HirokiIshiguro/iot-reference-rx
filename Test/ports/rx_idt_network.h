/* SPDX-License-Identifier: MIT */
#ifndef RX_IDT_NETWORK_H
#define RX_IDT_NETWORK_H

#include "FreeRTOS.h"

/* Seed the production network KVS after LittleFS/cache initialization and
 * before Connect2AP()/WHD join. The host supplies a private runtime header. */
BaseType_t xProvisionIdtNetworkCredentials( void );

#endif

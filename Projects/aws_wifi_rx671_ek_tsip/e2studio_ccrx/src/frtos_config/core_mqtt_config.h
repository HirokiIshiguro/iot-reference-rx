/*
 * coreMQTT v5.0.2
 * Copyright (C) 2022 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
 * Modifications Copyright (C) 2026 Renesas Electronics Corporation or its affiliates.
 *
 * SPDX-License-Identifier: MIT
 */

#ifndef CORE_MQTT_CONFIG_H_
#define CORE_MQTT_CONFIG_H_

#ifdef __cplusplus
extern "C" {
#endif

#include "logging_levels.h"

#ifndef LIBRARY_LOG_NAME
    #define LIBRARY_LOG_NAME    "MQTT"
#endif

#ifndef LIBRARY_LOG_LEVEL
    #define LIBRARY_LOG_LEVEL    LOG_INFO
#endif

#include "logging_stack.h"

#define MQTT_RECV_POLLING_TIMEOUT_MS    (1000U)

#ifdef __cplusplus
}
#endif

#endif /* CORE_MQTT_CONFIG_H_ */

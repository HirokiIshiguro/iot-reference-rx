/*
 * Copyright (C) 2026 OpenAI.
 * SPDX-License-Identifier: MIT
 */

#ifndef MULTI_TLS_DEMO_H
#define MULTI_TLS_DEMO_H

/**
 * @brief Start the two-session MQTT/TLS coexistence demo.
 *
 * Session 1 is the existing MQTT Agent connection shared by PubSub and OTA.
 * Session 2 is an independent coreMQTT client with its own NetworkContext,
 * TLS context, TCP socket, MQTT context, client identifier, and task.
 */
void vStartMultiTlsDemo(void);

#endif /* MULTI_TLS_DEMO_H */

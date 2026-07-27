/*
 * Copyright (c) 2026 Renesas Electronics Corporation and/or its affiliates
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include "demo_config.h"
#include "ota_image_identity.h"

#define RX671_OTA_STRINGIFY_INNER(value)    #value
#define RX671_OTA_STRINGIFY(value)          RX671_OTA_STRINGIFY_INNER(value)

/*
 * volatile prevents compiler-side removal.  The build helper temporarily adds
 * CC-RX -symbol_forbid for this external symbol, then verifies that the linker
 * retained its exact bytes in the final Motorola S-record.
 */
const volatile char g_rx671_ota_image_version_marker[] =
    "RX671_OTA_IMAGE_VERSION="
    RX671_OTA_STRINGIFY(APP_VERSION_MAJOR) "."
    RX671_OTA_STRINGIFY(APP_VERSION_MINOR) "."
    RX671_OTA_STRINGIFY(APP_VERSION_BUILD);

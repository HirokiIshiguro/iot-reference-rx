/*
 * Copyright (c) 2026 Renesas Electronics Corporation and/or its affiliates
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#ifndef OTA_IMAGE_IDENTITY_H_
#define OTA_IMAGE_IDENTITY_H_

/*
 * Human-readable build identity retained in the loadable image.  OTA tooling
 * checks the matching bytes in the generated Motorola S-record before signing.
 */
extern const volatile char g_rx671_ota_image_version_marker[];

#endif /* OTA_IMAGE_IDENTITY_H_ */

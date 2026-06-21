/*
 * corePKCS11 v3.6.0
 * Copyright (C) 2020 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
 * Modifications Copyright (C) 2026 Renesas Electronics Corporation or its affiliates.
 *
 * SPDX-License-Identifier: MIT
 */

#ifndef CORE_PKCS11_CONFIG_H_
#define CORE_PKCS11_CONFIG_H_

#ifdef __cplusplus
extern "C" {
#endif

#include "logging_levels.h"

#ifndef LIBRARY_LOG_NAME
    #define LIBRARY_LOG_NAME    "PKCS11"
#endif

#ifndef LIBRARY_LOG_LEVEL
    #define LIBRARY_LOG_LEVEL    LOG_ERROR
#endif

#include "logging_stack.h"

#define pkcs11configMAX_NUM_OBJECTS          8
#define pkcs11configPAL_DESTROY_SUPPORTED    1
#define pkcs11configOTA_SUPPORTED            1
#define pkcs11configPKCS11_MALLOC            pvPortMalloc
#define pkcs11configPKCS11_FREE              vPortFree

#ifdef __cplusplus
}
#endif

#endif /* CORE_PKCS11_CONFIG_H_ */

/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/***********************************************************************************************************************
 * File Name    : lfs_util_config.h
 * Description  : Configuration header for LittleFS functions.
 *                This file defines macros and settings for LittleFS such as memory allocation, assertions, tracing,
 *                and thread safety.
 **********************************************************************************************************************/

#include "lfs_util.h"

/* generated configuration header file - do not edit */
#ifndef LFS_UTIL_H_
#define LFS_UTIL_H_

#ifdef __cplusplus
        extern "C" {
        #endif

#if (0)
        #define LFS_NO_MALLOC
        #endif

#ifdef LFS_NO_MALLOC
#error "LFS no malloc operation is not implemented yet."
#endif

#if (0)
        #define LFS_NO_ASSERT
        #endif

#if (1)
        #define LFS_YES_TRACE
        #endif

#if (1)
#define LFS_NO_DEBUG
#endif

#if (1)
#define LFS_NO_WARN
#endif

#if (1)
#define LFS_NO_ERROR
#endif

#if (1)
        #define LFS_NO_INTRINSICS
        #endif

#ifdef LFS_NO_INTRINSICS
#else
#error "CTZ or CLZ instructions are not implemented on RXv2 core."
#endif

#define LFS_THREAD_SAFE (1)
/* Public application storage operations are locked in lfs_common_data.c. */

/* Defines the LittleFS instance control block to be the stdio wrapper. */
/* Obtain the initialized instance via LfsCommon_GetLfs(). */

#ifdef __cplusplus
        }
        #endif
#endif /* LFS_UTIL_H_ */

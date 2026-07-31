/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/
/***********************************************************************************************************************
* File Name    : base64_decode.h
* Description  : BASE64 decode function
***********************************************************************************************************************/
/**********************************************************************************************************************
* History : DD.MM.YYYY Version Description
*         : 01.09.2014 1.00    First Release
*         : 01.06.2015 1.01    Added RX231.
*         : 15.05.2017 1.02    Clean up source file
***********************************************************************************************************************/

#ifndef BASE64_DECODE_H_
#define BASE64_DECODE_H_

#include "platform.h"

#if defined(__CCRX__)
#define BASE64_FAR
#define STRCHR          ( strchr )
 #if !defined(STRSTR)
 #define STRSTR          ( strstr )
 #endif
#elif defined(__GNUC__)
#define BASE64_FAR
#define STRCHR          ( strchr )
 #if !defined(STRSTR)
 #define STRSTR          ( strstr )
 #endif
#elif defined(__ICCRX__)
#define BASE64_FAR
#define STRCHR          ( strchr )
 #if !defined(STRSTR)
 #define STRSTR          ( strstr )
 #endif
#elif defined(__CCRL__)
#define BASE64_FAR      __far
#define STRCHR          ( _COM_strchr_f )
 #if !defined(STRSTR)
 #define STRSTR          ( _COM_strstr_ff )
 #endif
#elif defined(__ICCRL78__)
#define BASE64_FAR      __far
#define STRCHR          ( strchr )
 #if !defined(STRSTR)
 #define STRSTR          ( strstr )
 #endif
#endif

uint32_t base64_decode(uint8_t BASE64_FAR *source, uint8_t BASE64_FAR *result, uint32_t size);

#endif /* BASE64_DECODE_H_ */

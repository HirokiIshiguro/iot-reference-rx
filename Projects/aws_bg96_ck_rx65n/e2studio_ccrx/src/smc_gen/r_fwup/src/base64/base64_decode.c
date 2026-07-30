/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/
/***********************************************************************************************************************
* File Name    : base64_decode.c
* Description  : base64 decode function.
***********************************************************************************************************************/
/***********************************************************************************************************************
* History : DD.MM.YYYY Version Description
*         : 27.06.2015 1.00    First Release
*         : 15.05.2017 1.01    Clean up source file
***********************************************************************************************************************/
#include <string.h>
#include "base64_decode.h"

/* base64 table */
const static char BASE64_FAR base64[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/=";

const char BASE64_FAR s2[] = "==";

/***********************************************************************************************************************
* Function Name: base64_decode
* Description  : http://apis.jpn.ph/fswiki/wiki.cgi?page=ScrapCode%2FC%2FBASE64
* Arguments    : *source
*                *result
*                size
* Return Value : j
***********************************************************************************************************************/
uint32_t base64_decode(uint8_t BASE64_FAR *source, uint8_t BASE64_FAR *result, uint32_t size)
{
    uint8_t ind1;
    uint8_t ind2;
    uint8_t ind3;
    uint8_t ind4;
    uint32_t i;
    uint32_t j;
    uint8_t tmp[3];
    uint8_t *ptr;

    for( i = 0, j = 0 ; i < size; i += 4 )
    {
        /* get the character code */
        ind1 = ('=' == (*((source + i) + 0))) ? 0 : (STRCHR(base64, *((source + i) + 0)) - base64);
        ind2 = ('=' == (*((source + i) + 1))) ? 0 : (STRCHR(base64, *((source + i) + 1)) - base64);
        ind3 = ('=' == (*((source + i) + 2))) ? 0 : (STRCHR(base64, *((source + i) + 2)) - base64);
        ind4 = ('=' == (*((source + i) + 3))) ? 0 : (STRCHR(base64, *((source + i) + 3)) - base64);

        /* decode */
        tmp[0] = (uint8_t)( ((ind1 & 0x3f) << 2) | ((ind2 & 0x30) >> 4) );
        tmp[1] = (uint8_t)( ((ind2 & 0x0f) << 4) | ((ind3 & 0x3c) >> 2) );
        tmp[2] = (uint8_t)( ((ind3 & 0x03) << 6) | ((ind4 & 0x3f) >> 0) );

        ptr = (uint8_t *)STRSTR((const char BASE64_FAR *)source, s2);
        if(ptr == (source + i))
        {
            ;/* nothing to do */
        }
        else if(ptr == (source + i) + 2)
        {
            result[j+0] = tmp[0];
            j += 1;
        }
        else if(ptr == (source + i) + 3)
        {
            result[j+0] = tmp[0];
            result[j+1] = tmp[1];
            j += 2;
        }
        else
        {
            result[j+0] = tmp[0];
            result[j+1] = tmp[1];
            result[j+2] = tmp[2];
            j += 3;
        }
    }

    return j;
}

/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#include <stddef.h>
#include <string.h>
#include "strtok_r.h"

char * strtok_r(char *string, const char *delimiters, char **save_ptr)
{
    char *end;
    if (NULL == string)
    {
        string = *save_ptr;
    }
    if (NULL == string)
    {
        return NULL;
    }
    string += strspn(string, delimiters);
    if ('\0' == *string)
    {
        *save_ptr = string;
        return NULL;
    }
    end = string + strcspn(string, delimiters);
    if ('\0' != *end)
    {
        *end++ = '\0';
    }
    *save_ptr = end;
    return string;
}

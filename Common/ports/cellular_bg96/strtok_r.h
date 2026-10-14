/* Copyright (c) 2026 SAFFTI. SPDX-License-Identifier: BSD-3-Clause */
#ifndef PRODUCT_CELLULAR_STRTOK_R_H
#define PRODUCT_CELLULAR_STRTOK_R_H
#ifdef __cplusplus
extern "C" {
#endif
/* POSIX string tokenization expected by the pristine Cellular library. */
char * strtok_r(char *string, const char *delimiters, char **save_ptr);
#ifdef __cplusplus
}
#endif
#endif

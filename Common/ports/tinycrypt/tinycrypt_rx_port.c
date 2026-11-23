/*
 * Copyright (c) 2026 SAFFTI and contributors
 * SPDX-License-Identifier: MIT
 */
#include <stdint.h>
#include <tinycrypt/ecc_platform_specific.h>

/* Boot uses public-signature verification, which does not require an RNG.
 * Reject requests for secret-key operations until a board entropy provider is
 * explicitly supplied through Tinycrypt's public platform interface. */
int default_CSPRNG(uint8_t *dest, unsigned int size)
{
    (void)dest;
    (void)size;
    return 0;
}

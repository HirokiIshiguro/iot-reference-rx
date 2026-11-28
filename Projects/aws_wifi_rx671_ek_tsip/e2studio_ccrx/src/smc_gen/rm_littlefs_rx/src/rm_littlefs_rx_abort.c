/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
#include <stdlib.h>

#include "rm_littlefs_rx_config.h"

#if (RM_LITTLEFS_CFG_PROVIDE_ABORT)
void abort(void)
{
    for (;;)
    {
        /* Trap here if an upstream littlefs assert fires. */
    }
}
#endif

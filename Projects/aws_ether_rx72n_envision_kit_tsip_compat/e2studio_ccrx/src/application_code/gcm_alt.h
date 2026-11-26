#ifndef RX72N_TSIP_COMPAT_GCM_ALT_H
#define RX72N_TSIP_COMPAT_GCM_ALT_H

#include "r_tsip_rx_if.h"

typedef struct mbedtls_gcm_context
{
    tsip_aes_key_index_t key_index;
    int key_ready;
} mbedtls_gcm_context;

#endif

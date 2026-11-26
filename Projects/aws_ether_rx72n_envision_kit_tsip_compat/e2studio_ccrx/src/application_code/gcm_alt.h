#ifndef RX72N_TSIP_COMPAT_GCM_ALT_H
#define RX72N_TSIP_COMPAT_GCM_ALT_H

/* Keep FIT and its BSP headers out of Mbed TLS library translation units. */
struct tsip_aes_key_index;

typedef struct mbedtls_gcm_context
{
    struct tsip_aes_key_index *key_index;
} mbedtls_gcm_context;

#endif

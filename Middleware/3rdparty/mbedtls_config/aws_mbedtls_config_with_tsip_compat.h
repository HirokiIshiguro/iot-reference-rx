#ifndef AWS_MBEDTLS_CONFIG_WITH_TSIP_COMPAT_H
#define AWS_MBEDTLS_CONFIG_WITH_TSIP_COMPAT_H

#include "aws_mbedtls_config.h"

/* Experimental RX72N TLS 1.2 client: only the record cipher uses TSIP. */
#undef MBEDTLS_SSL_PROTO_TLS1_3
#define MBEDTLS_GCM_ALT
#define MBEDTLS_SSL_CIPHERSUITES MBEDTLS_TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256, \
                                 MBEDTLS_TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256

#endif

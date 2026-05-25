/*
 * mbed TLS configuration overlay for TSIP-backed TLS 1.3 validation.
 *
 * Keep the normal TSIP profile on aws_mbedtls_config_with_tsip.h so the
 * established TLS 1.2 path remains unchanged.  CI selects this overlay only
 * when a TLS 1.3 TSIP job is explicitly requested.
 */

#ifndef AWS_MBEDTLS_CONFIG_WITH_TSIP13_H
#define AWS_MBEDTLS_CONFIG_WITH_TSIP13_H

#define MBEDTLS_SSL_PROTO_TLS1_3
#define MBEDTLS_SSL_TLS1_3_COMPATIBILITY_MODE
#define TSIP_TLS13_CERTVERIFY_TRACE_ENABLE
#define TSIP_TLS13_CERTVERIFY_PREFER_TSIP_SHA256
#define TSIP_TLS13_CERTVERIFY_ONLY

#include "aws_mbedtls_config_with_tsip.h"

/* Force TLS 1.3 in smoke/regression jobs and avoid TLS 1.2-only extensions. */
#undef MBEDTLS_SSL_PROTO_TLS1_2
#undef MBEDTLS_SSL_ENCRYPT_THEN_MAC
#undef MBEDTLS_SSL_EXTENDED_MASTER_SECRET
#undef MBEDTLS_SSL_MAX_FRAGMENT_LENGTH

#endif /* AWS_MBEDTLS_CONFIG_WITH_TSIP13_H */

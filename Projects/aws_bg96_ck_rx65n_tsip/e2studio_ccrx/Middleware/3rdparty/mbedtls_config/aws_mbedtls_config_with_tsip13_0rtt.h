/*
 * Mbed TLS 3.6.x TLS 1.3 resumption / 0-RTT configuration with the RX TSIP
 * client CertificateVerify hook enabled.
 *
 * This intentionally keeps the 3.6.x record/key-schedule path in software and
 * only routes client-auth signature generation through TSIP. Full TLS 1.3
 * record offload is outside this smoke test.
 */
#ifndef AWS_MBEDTLS_CONFIG_WITH_TSIP13_0RTT_H
#define AWS_MBEDTLS_CONFIG_WITH_TSIP13_0RTT_H

#define TSIP_TLS_API_ENABLE
#define TSIP_TLS13_CERTVERIFY_TRACE_ENABLE
#define TSIP_TLS13_CERTVERIFY_PREFER_TSIP_SHA256
#define TSIP_TLS13_CERTVERIFY_ONLY

#include "aws_mbedtls_config_tls13_0rtt.h"

#endif /* AWS_MBEDTLS_CONFIG_WITH_TSIP13_0RTT_H */

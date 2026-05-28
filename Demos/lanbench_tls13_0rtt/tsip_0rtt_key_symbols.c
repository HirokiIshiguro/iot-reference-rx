/*
 * TLS 1.3 0-RTT smoke builds stage stock Mbed TLS 3.6.x. Keep the TSIP key
 * index symbols linkable so the software path can bypass TSIP and the TSIP
 * path can still provision real key indices for CertificateVerify.
 */
#include <stddef.h>
#include <stdint.h>

#include <platform.h>
#include "r_tsip_rx_if.h"

#if defined(LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE) || defined(LANBENCH_TLS13_0RTT_TSIP_ENABLE)

tsip_rsa2048_private_key_index_t rsa2048_private_key;
tsip_rsa2048_public_key_index_t rsa2048_public_key;
tsip_ecc_private_key_index_t eccp256_private_key;
tsip_ecc_public_key_index_t eccp256_public_key;

volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateAttempts = 0U;
volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateCalls = 0U;
volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateFailures = 0U;
volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = 0U;
volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastScheme = 0U;
volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastBytes = 0U;

#endif /* LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE || LANBENCH_TLS13_0RTT_TSIP_ENABLE */

#if defined(LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE)

void vTlsTransportSetRootCaSignatureOverride(const unsigned char * pucSignature,
                                             size_t xSignatureSize)
{
    (void)pucSignature;
    (void)xSignatureSize;
}

void vTlsTransportClearRootCaSignatureOverride(void)
{
}

void vTlsTransportSetServerCertAuthModeOverride(int lAuthMode)
{
    (void)lAuthMode;
}

void vTlsTransportClearServerCertAuthModeOverride(void)
{
}

void vTlsTransportSetDisableTsipTlsAccelOverride(int lDisable)
{
    (void)lDisable;
}

void vTlsTransportClearDisableTsipTlsAccelOverride(void)
{
}

#endif /* LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE */

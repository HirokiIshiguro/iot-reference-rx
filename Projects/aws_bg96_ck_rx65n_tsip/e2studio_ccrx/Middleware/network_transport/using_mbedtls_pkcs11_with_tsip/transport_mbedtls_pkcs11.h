/*
 * Compatibility include for TSIP builds.
 *
 * The demos include "transport_mbedtls_pkcs11.h" for both software and TSIP
 * profiles. Put the TSIP include directory before the software transport
 * directory in TSIP projects so this wrapper selects the matching ABI.
 */

#ifndef TRANSPORT_MBEDTLS_PKCS11_TSIP_COMPAT_H
#define TRANSPORT_MBEDTLS_PKCS11_TSIP_COMPAT_H

#include "transport_mbedtls_pkcs11_with_tsip.h"

#endif /* TRANSPORT_MBEDTLS_PKCS11_TSIP_COMPAT_H */

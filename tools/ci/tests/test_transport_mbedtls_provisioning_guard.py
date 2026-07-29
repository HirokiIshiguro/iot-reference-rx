#!/usr/bin/env python3
"""Contract tests for the software PKCS #11 transport provisioning guard."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
TRANSPORT_HEADER = (
    ROOT
    / "Middleware"
    / "network_transport"
    / "using_mbedtls_pkcs11"
    / "transport_mbedtls_pkcs11.h"
)


class TransportMbedtlsProvisioningGuardTests(unittest.TestCase):
    def test_runtime_provisioning_allows_only_explicit_zero_rtt_profiles(self) -> None:
        header = TRANSPORT_HEADER.read_text(encoding="utf-8")
        guard = header.split(
            "#if defined( TSIP_RUNTIME_PROVISIONING_ENABLE )", maxsplit=1
        )[1].split("#endif", maxsplit=1)[0]

        self.assertIn("!defined( LANBENCH_TLS13_0RTT_TSIP_ENABLE )", guard)
        self.assertIn("!defined( LANBENCH_TLS13_0RTT_SOFTWARE_ENABLE )", guard)
        self.assertIn("#error", guard)


if __name__ == "__main__":
    unittest.main()

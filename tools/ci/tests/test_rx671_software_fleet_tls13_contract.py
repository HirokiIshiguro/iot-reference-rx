from __future__ import annotations

import unittest
from pathlib import Path

from tools import test_fleet_rx72n


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


class Rx671SoftwareFleetTls13ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        cls.transport = (
            ROOT
            / "Middleware"
            / "network_transport"
            / "using_mbedtls_pkcs11"
            / "transport_mbedtls_pkcs11.c"
        ).read_text(encoding="utf-8")
        cls.build = (ROOT / "tools" / "build_headless_rx671_wifi.ps1").read_text(
            encoding="utf-8"
        )

    def test_transport_pins_all_pkcs11_mqtt_sessions_to_tls13(self) -> None:
        self.assertIn("AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3", self.transport)
        self.assertIn("MBEDTLS_SSL_PROTO_TLS1_3", self.transport)
        self.assertIn("mbedtls_ssl_conf_min_tls_version", self.transport)
        self.assertIn("mbedtls_ssl_conf_max_tls_version", self.transport)
        self.assertIn("mbedtls_ssl_get_version_number", self.transport)
        self.assertGreaterEqual(
            self.transport.count("MBEDTLS_SSL_VERSION_TLS1_3"),
            3,
        )

    def test_build_helper_exposes_the_existing_opt_in_define(self) -> None:
        self.assertIn("[string]$RequireTlsVersion", self.build)
        self.assertIn("RX671_WIFI_REQUIRE_TLS_VERSION", self.build)
        self.assertIn("AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3=1", self.build)

    def test_fleet_build_passes_and_records_the_tls_requirement(self) -> None:
        job = job_block(
            self.ci,
            "build_rx671_wifi_fleet",
            "build_rx671_bootloader",
        )

        self.assertIn(
            "$buildArgs.RequireTlsVersion = $env:RX671_WIFI_REQUIRE_TLS_VERSION",
            job,
        )
        self.assertIn(
            "required_tls_version = $env:RX671_WIFI_REQUIRE_TLS_VERSION",
            job,
        )

    def test_nightly_tls13_row_inherits_the_fleet_safety_gate(self) -> None:
        job = job_block(
            self.ci,
            "matrix_rx671_wifi_fleet_tls13",
            ".matrix_rx671_software_lanbench",
        )

        self.assertIn("extends: matrix_rx671_wifi_fleet", job)
        self.assertIn('RX671_WIFI_TEST_SCOPE: "fleet"', job)
        self.assertIn('RX671_WIFI_REQUIRE_TLS_VERSION: "TLSv1.3"', job)

    def test_hardware_job_requires_two_tls13_handshakes(self) -> None:
        job = job_block(
            self.ci,
            "test_rx671_wifi_fleet",
            "cleanup_rx671_wifi_fleet",
        )

        self.assertIn(
            '--require-tls-version "$RX671_WIFI_REQUIRE_TLS_VERSION"',
            job,
        )
        self.assertIn("--minimum-tls-handshakes 2", job)
        self.assertIn('"${tls_version_args[@]}"', job)

    def test_tls13_requirement_rejects_missing_or_mixed_handshakes(self) -> None:
        self.assertTrue(
            test_fleet_rx72n.tls_requirement_ok("TLSv1.3", ["TLSv1.3"], 2, 2)
        )
        self.assertFalse(
            test_fleet_rx72n.tls_requirement_ok("TLSv1.3", ["TLSv1.3"], 1, 2)
        )
        self.assertFalse(
            test_fleet_rx72n.tls_requirement_ok(
                "TLSv1.3", ["TLSv1.3", "TLSv1.2"], 2, 2
            )
        )
        self.assertFalse(test_fleet_rx72n.tls_requirement_ok("TLSv1.3", [], 0, 2))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class Rx671SoftwareMqttTls13ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        cls.source = (
            ROOT
            / "Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/application_code"
            / "aws_iot_mqtt_smoke.c"
        ).read_text(encoding="utf-8")
        cls.build = (ROOT / "tools/build_headless_rx671_wifi.ps1").read_text(
            encoding="utf-8"
        )

    def test_tls13_build_is_pinned_and_runtime_verified(self) -> None:
        self.assertIn("mbedtls_ssl_conf_min_tls_version", self.source)
        self.assertIn("mbedtls_ssl_conf_max_tls_version", self.source)
        self.assertIn("mbedtls_ssl_get_version(&p_tls->ssl_context)", self.source)
        self.assertIn("mbedtls_ssl_get_version_number", self.source)
        self.assertIn("MBEDTLS_ERR_SSL_BAD_PROTOCOL_VERSION", self.source)

    def test_build_helper_rejects_unknown_version(self) -> None:
        self.assertIn("[string]$RequireTlsVersion", self.build)
        self.assertIn("expected TLSv1.3", self.build)
        self.assertIn("AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_3=1", self.build)

    def test_nightly_has_a_dedicated_tls13_mqtt_row(self) -> None:
        start = self.ci.index("matrix_rx671_wifi_mqtt_tls13:")
        end = self.ci.index("\n.matrix_rx671_software_lanbench:", start)
        job = self.ci[start:end]
        self.assertIn('RX671_WIFI_TEST_SCOPE: "mqtt"', job)
        self.assertIn('RX671_WIFI_REQUIRE_TLS_VERSION: "TLSv1.3"', job)
        self.assertIn("RX671_EK_AWS_IOT_PRIVATE_KEY_PEM", job)


if __name__ == "__main__":
    unittest.main()

import unittest

from tools import test_fleet_rx72n


class FleetStartupRetryTests(unittest.TestCase):
    def setUp(self):
        self.empty_results = {
            name: False for name, _ in test_fleet_rx72n.MARKERS
        }

    def test_nonzero_whd_pre_network_result_is_failure(self):
        self.assertTrue(
            test_fleet_rx72n.whd_pre_network_result_failed("whd_wifi_on=060E0000")
        )
        self.assertTrue(
            test_fleet_rx72n.whd_pre_network_result_failed("whd_wifi_join=060E0000")
        )
        self.assertTrue(
            test_fleet_rx72n.whd_pre_network_result_failed(
                "whd_wifi_is_ready_to_transceive=060E0000"
            )
        )
        self.assertFalse(
            test_fleet_rx72n.whd_pre_network_result_failed("whd_wifi_on=00000000")
        )
        self.assertFalse(
            test_fleet_rx72n.whd_pre_network_result_failed("whd_wifi_join=00000000")
        )
        self.assertFalse(
            test_fleet_rx72n.whd_pre_network_result_failed("whd_wifi_on diag irq=0")
        )

    def test_preclaim_whd_failure_is_retryable(self):
        self.assertTrue(
            test_fleet_rx72n.retryable_startup_failure(
                ["WHD startup failed: whd_wifi_on=060E0000"],
                self.empty_results,
                None,
                None,
            )
        )

    def test_retry_is_blocked_after_claim_connection(self):
        results = dict(self.empty_results)
        results["claim_mqtt"] = True
        self.assertFalse(
            test_fleet_rx72n.retryable_startup_failure(
                ["WHD startup failed: whd_wifi_on=060E0000"],
                results,
                None,
                None,
            )
        )

    def test_retry_is_blocked_after_resource_identifier(self):
        self.assertFalse(
            test_fleet_rx72n.retryable_startup_failure(
                ["Cellular init failed"],
                self.empty_results,
                "provisioned-thing",
                None,
            )
        )
        self.assertFalse(
            test_fleet_rx72n.retryable_startup_failure(
                ["Cellular Open Failed"],
                self.empty_results,
                None,
                "certificate-id",
            )
        )

    def test_unrelated_error_is_not_retryable(self):
        self.assertFalse(
            test_fleet_rx72n.retryable_startup_failure(
                ["Failed to establish MQTT session"],
                self.empty_results,
                None,
                None,
            )
        )


if __name__ == "__main__":
    unittest.main()

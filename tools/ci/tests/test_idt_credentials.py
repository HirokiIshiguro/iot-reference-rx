"""AWS read boundary: only the current IDT thing's active matching certificate."""
import unittest
from unittest.mock import Mock, patch

from tools.idt.prepare_transport_key import matching_iot_certificate


class IdtCredentialTests(unittest.TestCase):
    def setUp(self):
        self.account, self.region = "123456789012", "ap-northeast-1"
        self.arn = f"arn:aws:iot:{self.region}:{self.account}:cert/" + "a" * 64
        self.second = self.arn[:-64] + "b" * 64
        self.client = Mock()
        self.client.list_thing_principals.return_value = {"principals": [self.arn]}
        self.client.describe_certificate.return_value = {"certificateDescription": {
            "certificateArn": self.arn, "status": "ACTIVE", "certificatePem": "matching-public-key"}}
        parser = patch("tools.idt.prepare_transport_key.certificate_public_key", side_effect=lambda pem: pem.encode())
        parser.start()
        self.addCleanup(parser.stop)

    def fetch(self):
        return matching_iot_certificate(self.client, self.account, self.region,
                                        "IDT-Test-Thing", b"matching-public-key")

    def test_reads_all_pages_and_returns_matching_active_certificate(self):
        self.client.list_thing_principals.side_effect = [
            {"principals": [], "nextToken": "page2"}, {"principals": [self.arn]}]
        self.assertEqual("matching-public-key", self.fetch())
        self.client.list_thing_principals.assert_any_call(thingName="IDT-Test-Thing", nextToken="page2")
        self.client.describe_certificate.assert_called_once_with(certificateId="a" * 64)

    def test_foreign_account_or_region_is_rejected_before_reading_certificate(self):
        for arn in (self.arn.replace(self.account, "999999999999"),
                    self.arn.replace(self.region, "us-east-1")):
            with self.subTest(arn=arn):
                self.client.list_thing_principals.return_value = {"principals": [arn]}
                with self.assertRaises(RuntimeError):
                    self.fetch()
        self.client.describe_certificate.assert_not_called()

    def test_wrong_key_or_inactive_certificate_cannot_be_used(self):
        for status, pem in (("INACTIVE", "matching-public-key"), ("ACTIVE", "other-key")):
            self.client.describe_certificate.return_value["certificateDescription"].update(status=status, certificatePem=pem)
            with self.subTest(status=status, pem=pem), self.assertRaises(RuntimeError):
                self.fetch()

    def test_multiple_matching_certificates_are_ambiguous(self):
        self.client.list_thing_principals.return_value = {"principals": [self.arn, self.second]}
        self.client.describe_certificate.side_effect = [
            {"certificateDescription": {"certificateArn": arn, "status": "ACTIVE",
                                        "certificatePem": "matching-public-key"}}
            for arn in (self.arn, self.second)]
        with self.assertRaises(RuntimeError):
            self.fetch()

    def test_empty_thing_and_nonadvancing_pagination_fail(self):
        with self.assertRaises(RuntimeError):
            matching_iot_certificate(self.client, self.account, self.region, "", b"key")
        self.client.list_thing_principals.return_value = {"principals": [], "nextToken": "same"}
        with self.assertRaises(RuntimeError):
            self.fetch()
        self.assertEqual(2, self.client.list_thing_principals.call_count)


if __name__ == "__main__":
    unittest.main()

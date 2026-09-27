import unittest

from tools.idt.test_selection import parse_test_ids


class CaseSelectionTests(unittest.TestCase):
    def test_absent_means_full_group_but_blank_or_unknown_never_does(self):
        self.assertEqual((), parse_test_ids(None))
        for value in ("", " ", "OTAE2EGreaterVersion,", "not-a-test", "FullCloudIoT"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_test_ids(value)

    def test_explicit_subset_is_preserved_and_duplicates_rejected(self):
        self.assertEqual(("OTAE2ESameVersion", "OTAE2EPreviousVersion", "OTAE2EUntrustedCertificate"),
                         parse_test_ids("OTAE2ESameVersion, OTAE2EPreviousVersion,OTAE2EUntrustedCertificate"))
        with self.assertRaises(ValueError):
            parse_test_ids("OTAE2EGreaterVersion,OTAE2EGreaterVersion")


if __name__ == "__main__":
    unittest.main()

"""Source contracts for client metadata writes; no credentials or compiler used."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
APPS = (
    "aws_ether_rx72n_envision_kit", "aws_ether_rx72n_envision_kit_tsip",
    "aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip",
)
CLI = ROOT / "Demos/tsip_provisioning/tsip_provisioning_cli.c"
WRITES = re.compile(r'xprvWriteCacheEntry\(strlen\("([^"]+)"\),\s*"([^"]+)"')


def function(text, name):
    match = re.search(r"^(?:static\s+)?(?:BaseType_t|void)\s+" + name +
                      r"\([^;]*?\)\s*\{", text, re.M)
    if match is None:
        raise AssertionError("Missing product definition: " + name)
    opening = text.index("{", match.start())
    depth = 1
    for end in range(opening + 1, len(text)):
        depth += (text[end] == "{") - (text[end] == "}")
        if depth == 0:
            return text[match.start():end + 1]
    raise AssertionError("Unclosed product definition: " + name)


def bodies():
    for app in APPS:
        path = ROOT / "Projects" / app / "e2studio_ccrx/src/application_code/main.c"
        yield app, function(path.read_text(encoding="utf-8"), "vAssignCredentials")
    yield "shared_tsip_refresh", function(CLI.read_text(encoding="utf-8"),
                                          "prvRefreshAwsCredentialMetadata")


class SigningTrustPreservationTests(unittest.TestCase):
    def test_exact_client_write_set_excludes_both_signing_keys(self):
        for role, body in bodies():
            with self.subTest(role=role):
                pairs = WRITES.findall(body)
                self.assertTrue(all(length_key == key for length_key, key in pairs))
                keys = [key for _, key in pairs]
                expected = ["thingname", "endpoint", "cert"]
                if role != "shared_tsip_refresh":
                    expected.append("key")  # Existing conditional TSIP branch retained.
                expected.append("rootca")
                self.assertEqual(expected, keys)
                self.assertEqual(len(pairs), body.count("xprvWriteCacheEntry("))
                self.assertNotIn("otapalconfigCODE_SIGNING_CERTIFICATE", body)
                self.assertNotIn("codesigncert", body)
                self.assertNotIn("codesignpubkey", body)
                self.assertEqual(1, body.count("KVStore_xCommitChanges()"))
                self.assertGreater(body.index("KVStore_xCommitChanges()"),
                                   body.rindex("xprvWriteCacheEntry("))

    def test_client_sources_and_returned_errors_are_retained(self):
        for role, body in bodies():
            with self.subTest(role=role):
                for source in ("democonfigCLIENT_IDENTIFIER", "democonfigMQTT_BROKER_ENDPOINT",
                               "keyCLIENT_CERTIFICATE_PEM", "democonfigROOT_CA_PEM"):
                    self.assertIn(source, body)
                if role.endswith("_tsip"):
                    self.assertIn("#if !defined(TSIP_RUNTIME_PROVISIONING_ENABLE)", body)
                if role.startswith("aws_ether") or role == "shared_tsip_refresh":
                    checks = re.findall(r"if\s*\(\s*(?:xStoreResult|lStoreResult)\s*<\s*0\s*\)\s*"
                                        r"\{\s*return pdFALSE;\s*\}", body)
                    self.assertEqual(len(WRITES.findall(body)), len(checks))
                    self.assertIn("return xCommitResult;", body)

    def test_rx671_startup_has_no_automatic_signer_writer(self):
        startup = ROOT / "Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/aws_wifi_rx671_ek.c"
        body = startup.read_text(encoding="utf-8")
        self.assertNotIn('"codesigncert"', body)
        self.assertNotIn('"codesignpubkey"', body)

    def test_explicit_signer_cli_and_refresh_protocol_remain_available(self):
        commands = (ROOT / "Demos/cli/CLIcommands.c").read_text(encoding="utf-8")
        self.assertIn("conf get/set codesigncert/codesignpubkey", commands)
        provisioning = (ROOT / "tools/idt/public_signer_provision.py").read_text(encoding="utf-8")
        self.assertIn('"codesigncert", "codesignpubkey"', provisioning)
        cli = CLI.read_text(encoding="utf-8")
        for protocol in ('"credentials"', "OK: AWS credential metadata refreshed.",
                         "Error: AWS credential metadata refresh failed."):
            self.assertIn(protocol, cli)


if __name__ == "__main__":
    unittest.main()

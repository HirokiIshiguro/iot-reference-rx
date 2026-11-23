"""Every test of tools/ci/tests.json connects to the endpoint of its TLS version and must see that version.

The board side builds one observing command per test. These tests run all 36 flows with a board that only records
its commands, and check that the command of the observing tool names the TLS version of the test.
"""
import collections
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.platform == "win32":
    sys.modules.setdefault("fcntl", mock.MagicMock())
import rxci  # noqa: E402
import rxci_aws  # noqa: E402
import rxci_board  # noqa: E402
import rxci_build  # noqa: E402

# Number of build outputs each flow receives (rxci.py hands them over in this order).
BUILDS = {rxci_board.mqtt_rx72n: 2, rxci_board.fleet_rx72n: 2, rxci_board.ota_rx72n: 3,
          rxci_board.mqtt_rx65n: 2, rxci_board.fleet_rx65n: 2, rxci_board.ota_rx65n: 3,
          rxci_board.mqtt_rx671: 2, rxci_board.fleet_rx671: 2, rxci_board.ota_rx671: 1}


class VariableNames(collections.defaultdict):
    """Board settings: any setting that is looked up names a CI variable that exists in this test."""

    def __init__(self):
        super().__init__(lambda: "RXCI_TEST_VARIABLE")


def commands_of(test: dict, registry: dict) -> list[list[str]]:
    board = mock.Mock()
    board.uart, board.baud, board.name = "uart", 115200, test["board"]
    board.config = VariableNames()
    board.reset_command.return_value = "reset"
    board.rfp.common_command.return_value = []
    recipe = rxci_board.RECIPES[(test["board"], test["feature"])]
    builds = [Path(f"build{index}") for index in range(BUILDS[recipe])]
    if recipe is rxci_board.mqtt_rx671 and test["backend"] == "tsip":
        builds = builds[:1]
    thing = {"certificate": "certificate", "private_key": "key"}
    with tempfile.TemporaryDirectory() as folder, \
         mock.patch.dict(os.environ, {"RXCI_TEST_VARIABLE": "value", "AWS_IOT_ENDPOINT": "tls12.example.test"}), \
         mock.patch.object(rxci_board, "required_file", return_value="file"), \
         mock.patch.object(rxci_board, "install_rx671"), mock.patch.object(rxci_board, "erase_application"), \
         mock.patch.object(rxci_board, "cleanup_ota"), mock.patch.object(rxci_board, "provision_tsip_keys"), \
         mock.patch.object(rxci_board, "rx671_programmer", return_value=[]), \
         mock.patch.object(rxci, "aws_session", return_value=object()), \
         mock.patch.object(rxci_aws, "create_thing", return_value=thing), \
         mock.patch.object(rxci_aws, "delete_fleet_resources"), mock.patch.object(rxci_aws, "sweep"), \
         mock.patch.object(rxci_aws, "environment", return_value={}), \
         mock.patch("sys.stdout", new_callable=io.StringIO):
        recipe(registry, board, test, builds, Path(folder))
    return [[str(part) for part in call.args[0]] for call in board.run.call_args_list]


class ObservedVersionTests(unittest.TestCase):
    def test_all_36_tests_ask_their_observing_tool_for_the_version_in_their_name(self):
        registry = rxci.load_registry()
        self.assertEqual(len(registry["tests"]), 36)
        for test in registry["tests"]:
            with self.subTest(test=test["name"]):
                wanted = {"tls12": "TLSv1.2", "tls13": "TLSv1.3"}[test["tls"]]
                versions = [command[command.index("--require-tls-version") + 1]
                            for command in commands_of(test, registry) if "--require-tls-version" in command]
                self.assertEqual(versions, [wanted])

    def test_rx671_fleet_needs_the_claim_and_the_provisioned_connection_in_both_versions(self):
        registry = rxci.load_registry()
        for test in registry["tests"]:
            if test["board"] == "rx671" and test["feature"] == "fleet":
                with self.subTest(test=test["name"]):
                    observing = [command for command in commands_of(test, registry)
                                 if "--require-tls-version" in command]
                    self.assertEqual(observing[0][observing[0].index("--minimum-tls-handshakes") + 1], "2")

    def test_the_version_names_are_the_ones_the_firmware_logs(self):
        self.assertEqual(rxci.tls_version("tls12"), "TLSv1.2")
        self.assertEqual(rxci.tls_version("tls13"), "TLSv1.3")


class EndpointTests(unittest.TestCase):
    REGISTRY = {"endpoints": {"tls12": {"variable": "AWS_IOT_ENDPOINT"}, "tls13": {"value": "tls13.example.test"}}}

    def test_each_version_has_its_own_endpoint(self):
        with mock.patch.dict(os.environ, {"AWS_IOT_ENDPOINT": "tls12.example.test"}):
            self.assertEqual(rxci.endpoint(self.REGISTRY, "tls12"), "tls12.example.test")
            self.assertEqual(rxci.endpoint(self.REGISTRY, "tls13"), "tls13.example.test")
            self.assertEqual(rxci_board.endpoint(self.REGISTRY, "tls12"), "tls12.example.test")

    def test_a_missing_variable_stops_the_job(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(SystemExit):
            rxci.endpoint(self.REGISTRY, "tls12")

    def test_rx671_builds_ignore_the_variable_of_the_other_version(self):
        for tls, expected in (("tls12", "tls12.example.test"), ("tls13", "tls13.example.test")):
            for kind in ("app", "fleet"):
                with self.subTest(tls=tls, kind=kind), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    board = {"fleet_template_variable": "UNIT_TEMPLATE", "claim_certificate_variable": "UNIT_CERT",
                             "claim_private_key_variable": "UNIT_KEY"}
                    data = {"boards": {"rx671": board}, "endpoints": self.REGISTRY["endpoints"],
                            "e2studio_cli": "e2studio-cli"}
                    env = {"RX671_EK_WIFI_SSID": "test", "RX671_EK_WIFI_PASSPHRASE": "test",
                           "RX671_EK_AWS_IOT_THING_NAME": "test", "RX671_EK_AWS_IOT_CERT_PEM": "test",
                           "RX671_EK_AWS_IOT_PRIVATE_KEY_PEM": "test", "UNIT_TEMPLATE": "test",
                           "UNIT_CERT": "test", "UNIT_KEY": "test", "AWS_IOT_ENDPOINT": "tls12.example.test",
                           # The variable that used to win over the endpoint of the version.
                           "RX671_EK_AWS_IOT_ENDPOINT": "tls13.example.test"}
                    commands = []

                    def run(command, *, timeout, env=None):
                        commands.append((command, env))
                        if "tools/build_rx671_fwup_v2_rsu.py" in command:
                            (root / "rx671_app.rsu").write_bytes(b"test")
                    with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(rxci_build, "ROOT", root), \
                         mock.patch.object(rxci_build, "workspace", return_value=root / "work"), \
                         mock.patch.object(rxci_build, "image_key", return_value=b"key"), \
                         mock.patch.object(rxci_build, "run", side_effect=run), \
                         mock.patch.object(rxci_build, "encrypt_file"), mock.patch.object(rxci_build.subprocess, "run"), \
                         mock.patch("sys.stdout", new_callable=io.StringIO):
                        rxci_build.build_rx671_app(data, "software", tls, kind, root / "out")
                    command, build_env = commands[0]
                    if kind == "app":
                        self.assertEqual(command[command.index("-AwsIotEndpoint") + 1], expected)
                    else:
                        self.assertEqual(build_env["RX671_EK_FLEET_ENDPOINT"], expected)

    def test_no_ci_tool_reads_the_variable_that_overrode_the_endpoint(self):
        for path in Path(__file__).resolve().parent.glob("rxci*.py"):
            self.assertNotIn("RX671_EK_AWS_IOT_ENDPOINT", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rxci
import rxci_build


class Rx671TsipFleetTests(unittest.TestCase):
    def test_generated_local_credentials_are_ignored_for_both_projects(self):
        root = Path(__file__).resolve().parents[2]
        relative = ("src/whd_join_config_local.h", "src/frtos_config/aws_iot_config_local.h",
                    "src/frtos_config/tcp_throughput_config_local.h", "src/frtos_config/rx671_fleet_config_local.h")
        for project in ("aws_wifi_rx671_ek", "aws_wifi_rx671_ek_tsip"):
            for suffix in relative:
                with self.subTest(project=project, filename=suffix):
                    result = subprocess.run(["git", "check-ignore", "-q", f"Projects/{project}/e2studio_ccrx/{suffix}"],
                                            cwd=root, check=False)
                    self.assertEqual(result.returncode, 0)

    def test_qualification_runs_only_explicit_pair_without_marking_ready(self):
        registry = rxci.load_registry()
        names = [f"rx671:tsip:tls{version}:fleet" for version in (12, 13)]
        self.assertTrue(all(not t["ready"] for t in registry["tests"] if t["name"] in names))
        jobs, summary = rxci.child_pipeline(registry, "full", r"^rx671:tsip:tls1[23]:fleet$", 1)
        self.assertEqual(summary["tests"], names)
        self.assertEqual(summary["builds"], ["rx671/common", "rx671/tsip-tls12/fleet", "rx671/tsip-tls13/fleet"])
        for name in names:
            self.assertEqual(jobs[name]["resource_group"], registry["boards"]["rx671"]["resource_group"])
        _, full = rxci.child_pipeline(registry, "full", "", 1)
        self.assertTrue(set(names).isdisjoint(full["tests"]))

    def test_dispatch_allows_only_fleet_tsip(self):
        data = rxci.load_registry()
        with mock.patch.object(rxci_build, "build_rx671_app") as build:
            for version in ("tls12", "tls13"):
                rxci_build.build_from_source(data, f"rx671/tsip-{version}/fleet", Path("out"))
                build.assert_called_with(data, "tsip", version, "fleet", Path("out"))
            with self.assertRaises(SystemExit):
                rxci_build.build_from_source(data, "rx671/tsip-tls12/app", Path("out"))

    def test_board_fleet_uses_same_cleanup_and_changes_only_label(self):
        if sys.platform == "win32":
            sys.modules.setdefault("fcntl", mock.MagicMock())
        import rxci_board
        import rxci_aws
        board = mock.Mock()
        board.uart = "test-port"
        board.baud = 115200
        board.reset_command.return_value = "test-reset"
        with mock.patch.object(rxci_board, "install_rx671") as install, \
             mock.patch.object(rxci_board, "erase_application") as erase, \
             mock.patch.object(rxci_board, "provision_tsip_keys") as provision, \
             mock.patch.object(rxci, "aws_session", return_value=object()), \
             mock.patch.object(rxci_aws, "delete_fleet_resources") as cleanup:
            rxci_board.fleet_rx671({}, board, {"backend": "tsip", "tls": "tls13"},
                                   [Path("common"), Path("app")], Path("logs"))
        install.assert_called_once()
        erase.assert_called_once_with(board)
        provision.assert_not_called()
        cleanup.assert_called_once()
        command = board.run.call_args.args[0]
        self.assertIn("RX671/Type 1YN TSIP", command)
        self.assertIn("--require-tls-version", command)
        self.assertIn("--minimum-tls-handshakes", command)

    def test_fleet_build_uses_selected_project_and_keeps_claim_out_of_command(self):
        for backend in ("software", "tsip"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                board = {"fleet_template_variable": "UNIT_TEMPLATE", "claim_certificate_variable": "UNIT_CERT",
                         "claim_private_key_variable": "UNIT_KEY"}
                data = {"boards": {"rx671": board}, "endpoints": {"tls13": {"value": "test.invalid"}},
                        "e2studio_cli": "e2studio-cli"}
                env = {"RX671_EK_WIFI_SSID": "test", "RX671_EK_WIFI_PASSPHRASE": "test",
                       "UNIT_TEMPLATE": "test-template", "UNIT_CERT": "test-certificate", "UNIT_KEY": "test-key"}
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
                    rxci_build.build_rx671_app(data, backend, "tls13", "fleet", root / "out")
                command, build_env = commands[0]
                self.assertEqual("-TlsBackend" in command, backend == "tsip")
                self.assertIn("-RequireTlsVersion", command)
                self.assertNotIn("test-key", command)
                self.assertNotIn("test-certificate", command)
                self.assertEqual(build_env["RX671_EK_FLEET_CLAIM_PRIVATE_KEY_PEM"], "test-key")
                expected = "aws_wifi_rx671_ek_tsip" if backend == "tsip" else "aws_wifi_rx671_ek"
                self.assertEqual(commands[1][0][commands[1][0].index("--mot") + 1].name, expected + ".mot")


if __name__ == "__main__":
    unittest.main()

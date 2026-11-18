"""Tests of the RX671 TSIP MQTT and OTA path: wrapped keys through tsipprov, the fixed thing, the OTA bundle."""
import argparse
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rxci
import rxci_build

# Fake value only. The tests never read a CI variable.
THING = "unit-test-thing"


def fake_board(registry):
    board = mock.Mock()
    board.config = registry["boards"]["rx671"]
    board.uart = "test-port"
    board.baud = 921600
    board.name = "rx671"
    board.reset_command.return_value = "test-reset"
    board.rfp.executable = "rfp-cli"
    board.rfp.device = "RX671"
    board.rfp.tool = "e2l:test"
    board.rfp.interface = "fine"
    board.rfp.speed = "500K"
    board.rfp.auth_id = "F" * 32
    board.rfp.common_command.return_value = ["rfp-cli"]
    return board


def board_module():
    if sys.platform == "win32":
        sys.modules.setdefault("fcntl", mock.MagicMock())
    import rxci_board
    return rxci_board


class PlanTests(unittest.TestCase):
    def test_tsip_mqtt_and_ota_share_one_bundle_per_tls_version(self):
        registry = rxci.load_registry()
        names = [f"rx671:tsip:tls{version}:{feature}" for version in (12, 13) for feature in ("mqtt", "ota")]
        tests = {t["name"]: t for t in registry["tests"]}
        for name in names:
            self.assertTrue(tests[name]["ready"], name)
            self.assertEqual(rxci.build_variants(tests[name], registry), [f"rx671/tsip-{name.split(':')[2]}/ota"])
        _, summary = rxci.child_pipeline(registry, "full", r"^rx671:tsip:tls1[23]:(mqtt|ota)$", 1)
        self.assertEqual(sorted(summary["tests"]), sorted(names))
        self.assertEqual(summary["builds"], ["rx671/tsip-tls12/ota", "rx671/tsip-tls13/ota"])

    def test_other_plans_are_unchanged(self):
        registry = rxci.load_registry()
        tests = {t["name"]: t for t in registry["tests"]}
        self.assertEqual(rxci.build_variants(tests["rx671:sw:tls12:mqtt"], registry),
                         ["rx671/common", "rx671/software-tls12/app"])
        self.assertEqual(rxci.build_variants(tests["rx671:sw:tls13:ota"], registry), ["rx671/software-tls13/ota"])
        self.assertEqual(rxci.build_variants(tests["rx671:tsip:tls12:fleet"], registry),
                         ["rx671/common", "rx671/tsip-tls12/fleet"])
        self.assertEqual(rxci.build_variants(tests["rx72n:tsip:tls12:mqtt"], registry),
                         ["rx72n/common", "rx72n/tsip-tls12/app"])

    def test_ota_build_dispatch_passes_the_backend(self):
        registry = rxci.load_registry()
        with mock.patch.object(rxci_build, "build_rx671_ota") as build:
            rxci_build.build_from_source(registry, "rx671/software-tls12/ota", Path("out"))
            build.assert_called_with(registry, "tls12", Path("out"), "software")
            rxci_build.build_from_source(registry, "rx671/tsip-tls13/ota", Path("out"))
            build.assert_called_with(registry, "tls13", Path("out"), "tsip")

    def test_ota_build_uses_the_selected_project_and_backend(self):
        registry = rxci.load_registry()
        for backend, project in (("software", "aws_wifi_rx671_ek"), ("tsip", "aws_wifi_rx671_ek_tsip")):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as tmp:
                commands, published = [], []
                with mock.patch.object(rxci_build, "ROOT", Path(tmp)), \
                     mock.patch.object(rxci_build, "workspace", return_value=Path(tmp) / "work"), \
                     mock.patch.object(rxci_build, "build_rx671_bootloader"), \
                     mock.patch.object(rxci_build, "keep_logs"), \
                     mock.patch.object(rxci_build, "run", side_effect=lambda command, **_: commands.append(command)), \
                     mock.patch.object(rxci_build, "publish", side_effect=lambda out, files: published.append(files)):
                    rxci_build.build_rx671_ota(registry, "tls12", Path(tmp) / "out", backend)
                command = [str(part) for part in commands[0]]
                self.assertEqual(command[command.index("--tls-backend") + 1], backend)
                self.assertEqual(published[0]["provisioner.mot"].name, project + ".mot")
                self.assertEqual(published[0]["baseline.rsu"].name, "aws_wifi_rx671_ek.rsu")


class BoardTests(unittest.TestCase):
    def environment(self, registry):
        board = registry["boards"]["rx671"]
        return {board["ota_service_role_variable"]: "unit-role", board["ota_bucket_variable"]: "unit-bucket",
                board["tsip_thing_variable"]: THING, "CI_PIPELINE_ID": "1", "CI_JOB_ID": "2"}

    def run_ota(self, backend):
        import rxci_aws
        rxci_board = board_module()
        registry = rxci.load_registry()
        board = fake_board(registry)
        test = {"backend": backend, "tls": "tls13", "name": f"rx671:{backend}:tls13:ota"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, self.environment(registry)), \
             mock.patch.object(rxci, "aws_session", return_value=object()), \
             mock.patch.object(rxci_aws, "environment", return_value={}), \
             mock.patch.object(rxci_aws, "create_thing",
                               return_value={"certificate": "c", "private_key": "k"}) as create, \
             mock.patch.object(rxci_aws, "delete_thing") as delete, \
             mock.patch.object(rxci_aws, "sweep"), \
             mock.patch.object(rxci_board, "cleanup_ota") as cleanup, \
             mock.patch.object(rxci_board, "required_file", return_value="certificate-file"):
            rxci_board.ota_rx671(registry, board, test, [Path("bundle")], Path(tmp))
        return board, create, delete, cleanup

    def test_tsip_ota_uses_the_fixed_thing_and_sends_no_plaintext_key(self):
        board, create, delete, cleanup = self.run_ota("tsip")
        create.assert_not_called()
        delete.assert_not_called()
        cleanup.assert_called_once()
        calls = board.run.call_args_list
        ota = next(call for call in calls if call.kwargs.get("label") == "create the OTA update")
        self.assertIn(THING, [str(part) for part in ota.args[0]])
        self.assertEqual(ota.kwargs["hide"], (THING,))
        provision = next(call for call in calls if "provision_rx671_ota.py" in str(call.args[0][1]))
        command = [str(part) for part in provision.args[0]]
        self.assertIn("--tsip", command)
        self.assertIn("--thing-name-env", command)
        self.assertNotIn("--private-key", command)
        self.assertNotIn("--thing-name", command)
        self.assertNotIn(THING, command)
        erases = [call for call in calls if "-erase-chip" in call.args[0]]
        self.assertEqual(len(erases), 2)        # before the provisioner, and again at the end

    def test_software_ota_still_creates_its_own_thing_and_key(self):
        board, create, delete, cleanup = self.run_ota("sw")
        create.assert_called_once()
        calls = board.run.call_args_list
        provision = next(call for call in calls if "provision_rx671_ota.py" in str(call.args[0][1]))
        command = [str(part) for part in provision.args[0]]
        self.assertIn("--private-key", command)
        self.assertIn("--thing-name", command)
        self.assertNotIn("--tsip", command)
        self.assertNotIn("--thing-name-env", command)
        self.assertTrue(all("hide" not in call.kwargs or call.kwargs["hide"] == () for call in calls))

    def test_cleanup_without_a_thing_meta_does_not_touch_things(self):
        rxci_board = board_module()
        import rxci_aws
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "ota"
            folder.mkdir()
            (folder / "ota_job_meta.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(rxci_aws, "environment", return_value={}), \
                 mock.patch.object(rxci_board.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
                rxci_board.cleanup_ota(Path(tmp), lambda: object())
            steps = [Path(str(call.args[0][1])).name for call in run.call_args_list]
            self.assertEqual(steps, ["verify_ota_aws_state.py"])

    def test_tsip_mqtt_installs_the_baseline_and_erases_the_chip_at_the_end(self):
        rxci_board = board_module()
        registry = rxci.load_registry()
        board = fake_board(registry)
        test = {"backend": "tsip", "tls": "tls12", "name": "rx671:tsip:tls12:mqtt"}
        order = []
        board.run.side_effect = lambda command, **kw: order.append(kw.get("label"))
        board.download.side_effect = lambda *_: order.append("download")
        with mock.patch.object(rxci_board, "provision_rx671_tsip", side_effect=lambda *_: order.append("provision")):
            rxci_board.mqtt_rx671(registry, board, test, [Path("bundle")], Path("logs"))
        self.assertEqual(order, ["erase chip", "provision", "download", "observe Wi-Fi and MQTT on the UART",
                                 "erase chip (it holds credentials)"])
        board.download.assert_called_once_with(Path("bundle") / "baseline.rsu", Path("logs"))
        observe = board.run.call_args_list[1].args[0]
        self.assertEqual(observe[observe.index("--mode") + 1], "mqtt-agent")
        self.assertEqual(observe[observe.index("--require-tls-version") + 1], "TLSv1.2")

    def test_tsip_mqtt_erases_the_chip_when_the_observation_fails(self):
        rxci_board = board_module()
        registry = rxci.load_registry()
        board = fake_board(registry)
        test = {"backend": "tsip", "tls": "tls13", "name": "rx671:tsip:tls13:mqtt"}
        labels = []

        def run(command, **kw):
            labels.append(kw.get("label"))
            if kw.get("label", "").startswith("observe"):
                raise subprocess.CalledProcessError(1, command)

        board.run.side_effect = run
        with mock.patch.object(rxci_board, "provision_rx671_tsip"):
            with self.assertRaises(subprocess.CalledProcessError):
                rxci_board.mqtt_rx671(registry, board, test, [Path("bundle")], Path("logs"))
        self.assertEqual(labels[-1], "erase chip (it holds credentials)")

    def test_download_command_is_the_one_install_always_used(self):
        rxci_board = board_module()
        board = rxci_board.Board.__new__(rxci_board.Board)
        board.name, board.uart, board.baud = "rx671", "test-port", 921600
        board.rfp = mock.Mock()
        board.rfp.run_command.return_value = ["rfp-cli", "-run"]
        board.run = mock.Mock()
        board.download(Path("app.rsu"), Path("logs"))
        command = [str(part) for part in board.run.call_args.args[0]]
        self.assertEqual(command[2:4], ["--rsu", "app.rsu"])
        self.assertEqual(command[command.index("--ready-timeout") + 1], "90")
        self.assertEqual(command[command.index("--send-chunk-size") + 1], "32768")
        self.assertEqual(command[command.index("--ready-message") + 1], 'send "userprog.rsu" via UART.')

    def test_run_hides_only_the_given_values_from_the_echo(self):
        rxci_board = board_module()
        board = rxci_board.Board.__new__(rxci_board.Board)
        with mock.patch.object(rxci_board.subprocess, "run"), mock.patch("builtins.print") as printed:
            board.run(["tool", "--name", THING], label="step", hide=(THING,))
            board.run(["tool", "--name", THING], label="step")
        self.assertNotIn(THING, printed.call_args_list[0].args[0])
        self.assertIn(THING, printed.call_args_list[1].args[0])


class ProvisionerTests(unittest.TestCase):
    def arguments(self, root, *, tsip):
        files = {}
        for name in ("provisioner.mot", "bootloader.mot", "device.crt", "device.key", "signer.crt", "signer.pub"):
            files[name] = root / name
            files[name].write_text("-----BEGIN TEST-----\nX\n-----END TEST-----\n", encoding="ascii")
        return argparse.Namespace(
            artifact_dir=root / "artifacts", rfp_cli="rfp-cli", rfp_device="RX671", rfp_tool="e2l:test",
            rfp_interface="fine", rfp_speed="500K", rfp_auth_id="F" * 32, rfp_timeout=1,
            provisioner_mot=files["provisioner.mot"], bootloader_mot=files["bootloader.mot"], port="test-port",
            baud=921600, boot_timeout=1, char_delay=0, command_timeout=1, commit_timeout=1, endpoint="example.invalid",
            thing_name=None, thing_name_env="UNIT_THING", certificate=files["device.crt"],
            private_key=None if tsip else files["device.key"], tsip=tsip, tsip_chunk_size=128,
            codesigner_certificate=files["signer.crt"], codesigner_public_key=files["signer.pub"],
            wifi_ssid_env="UNIT_SSID", wifi_passphrase_env="UNIT_PASS")

    def provision(self, tsip):
        import provision_rx671_ota as provision
        import provision_tsip_over_uart as tsip_tool
        payloads = [(slot, bytes([index]) * length, "unit") for index, (slot, length) in enumerate(
            (("rootca-sig", 256), ("root-signer", 348), ("client-pub", 348), ("client-pri", 588)))]
        names, sent = [], []
        with tempfile.TemporaryDirectory() as tmp:
            args = self.arguments(Path(tmp), tsip=tsip)
            with mock.patch.dict(os.environ, {"UNIT_SSID": "unit-ssid", "UNIT_PASS": "unit-passphrase",
                                              "UNIT_THING": THING}), \
                 mock.patch.object(provision, "run_checked"), mock.patch.object(provision, "open_serial"), \
                 mock.patch.object(provision, "enter_cli"), mock.patch.object(provision, "_commit"), \
                 mock.patch.object(provision, "send_ascii_bytes_command"), \
                 mock.patch.object(provision, "send_ascii_command",
                                   side_effect=lambda _s, command, **_k: names.append(command.split(" ")[:3])), \
                 mock.patch.object(tsip_tool, "load_payloads", return_value=payloads), \
                 mock.patch.object(tsip_tool, "send_command",
                                   side_effect=lambda _s, command, *_a, **_k: sent.append(command) or "OK\r\n"):
                summary = provision.provision(args)
        return summary, names, sent

    def test_wrapped_keys_are_sent_in_the_fixed_order_and_no_plaintext_key(self):
        summary, names, sent = self.provision(tsip=True)
        self.assertTrue(summary["success"])
        self.assertTrue(summary["tsip"])
        steps = summary["completed_steps"]
        self.assertLess(steps.index("commit"), steps.index("tsip_keys"))
        self.assertEqual([command.split(" ")[2] for command in sent if command.startswith("tsipprov begin")],
                         ["rootca-sig", "root-signer", "client-pub", "client-pri"])
        self.assertEqual([command for command in sent if not command.startswith("tsipprov write")][-2:],
                         ["tsipprov status", "tsipprov prepare"])
        self.assertEqual(sum(command.startswith("tsipprov write") for command in sent), 2 + 3 + 3 + 5)
        stored = [name[2] for name in names if name[:2] == ["conf", "set"]]
        self.assertIn("cert", stored)
        self.assertNotIn("key", stored)
        self.assertIn(["conf", "set", "thingname"], names)

    def test_commit_keeps_the_board_answer_when_no_success_line_comes(self):
        import provision_rx671_ota as provision

        class Serial:
            def __init__(self): self.chunks = [b"conf commit\r\nsomething odd\r\n"]
            in_waiting = 0
            def reset_input_buffer(self): pass
            def write(self, _b): pass
            def flush(self): pass
            def read(self, _n): return self.chunks.pop(0) if self.chunks else b""

        class Log:
            def __init__(self): self.lines = []
            def write(self, text): self.lines.append(text)

        log = Log()
        args = argparse.Namespace(char_delay=0, commit_timeout=0.2)
        with self.assertRaises(TimeoutError):
            provision._commit(Serial(), args, log)
        self.assertIn("something odd", "".join(log.lines))

    def test_software_path_still_stores_the_key_and_sends_no_tsip_command(self):
        summary, names, sent = self.provision(tsip=False)
        self.assertFalse(summary["tsip"])
        self.assertEqual(sent, [])
        self.assertIn("key", [name[2] for name in names if name[:2] == ["conf", "set"]])

    def test_rx671_root_ca_signature_falls_back_to_the_rx72n_variable(self):
        import provision_tsip_over_uart as tool
        table = tool.TARGET_ENV_NAMES["rx671"]
        names = table["rootca-sig"]
        self.assertEqual(len(names), 2)
        self.assertIn("RX671", names[0])
        self.assertIn("RX72N", names[1])
        arguments = argparse.Namespace(only=None, target="rx671", rootca_sig_hex_env=None, rootca_der_hex_env=None,
                                       root_signer_hex_env=None, client_pub_hex_env=None, client_pri_hex_env=None)
        fake = {table[slot][0]: "00" * 4 for slot in ("root-signer", "client-pub", "client-pri")}
        with mock.patch.dict(os.environ, {**fake, names[1]: "11" * 4}, clear=True):
            payloads = tool.load_payloads(arguments)
        self.assertEqual([(slot, source) for slot, _, source in payloads],
                         [("rootca-sig", names[1]), ("root-signer", table["root-signer"][0]),
                          ("client-pub", table["client-pub"][0]), ("client-pri", table["client-pri"][0])])
        with mock.patch.dict(os.environ, {**fake, names[0]: "22" * 4, names[1]: "11" * 4}, clear=True):
            self.assertEqual(tool.load_payloads(arguments)[0][2], names[0])


class AgentObserverTests(unittest.TestCase):
    LOG = "\n".join(["whd_wifi_join=00000000", "WHD bring-up done", "FreeRTOS+TCP network up",
                     "[MQTT] [INFO] (Network connection 1) TLS handshake successful: version TLSv1.2",
                     "[MQTT] [INFO] Successfully connected to MQTT broker.",
                     "[OTA_Agent] [INFO] Request Job Document event Received "])

    def test_agent_mode_needs_the_connection_and_the_job_request(self):
        import test_rx671_wifi_uart as observer
        self.assertEqual(observer.evaluate_log(self.LOG, "mqtt-agent", "TLSv1.2"), ([], []))
        missing, _ = observer.evaluate_log(self.LOG.replace("Successfully connected", "x"), "mqtt-agent")
        self.assertEqual(missing, ["Successfully connected to MQTT broker."])

    def test_agent_mode_rejects_another_tls_version(self):
        import test_rx671_wifi_uart as observer
        missing, failures = observer.evaluate_log(self.LOG, "mqtt-agent", "TLSv1.3")
        self.assertEqual(missing, ["TLS handshake successful: version TLSv1.3"])
        self.assertEqual(failures, ["TLS handshake used TLSv1.2, not TLSv1.3"])

    def test_the_smoke_mode_is_unchanged(self):
        import test_rx671_wifi_uart as observer
        with self.assertRaises(ValueError):
            observer.required_markers("mqtt", "TLSv1.2")
        self.assertIn("AWS TLS=0", observer.required_markers("mqtt", "TLSv1.3"))


if __name__ == "__main__":
    unittest.main()

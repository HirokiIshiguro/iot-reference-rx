"""Normal signed-install validation and failure/ownership boundaries; no hardware."""
import json
from contextlib import ExitStack
import itertools
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from tools import normal_boot, install_normal_boot as installer
from tools.ci.tests.test_idt_public_signer_provision import Fixture, ROOT, SOURCE_SHA
from tools.idt.targets import get_target


class NormalBootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bundle(self, target_id="rx671-wifi", backend="software"):
        fixture = Fixture(self.root/(target_id+"-inputs"), target_id)
        inputs = {name: fixture.files[name] for name in normal_boot.FILES
                  if name not in {"normal_app.rsu", "public_signer_bootloader_config.h", "public_signer_target.h"}}
        inputs["normal_app.rsu"] = fixture.files["idt_transport.rsu"]
        output = self.root/(target_id+"-bundle")
        with patch("tools.idt.prepare_public_signer._source_state", return_value=SOURCE_SHA):
            manifest = normal_boot.prepare(ROOT, target_id, output, inputs, tls_backend=backend)
        return output, fixture, manifest

    def reset_only_transaction(self, *, return_code=0, uart_bytes=b""):
        """Mock programmer/UART and Linux syscalls, retaining actual owner files."""
        target = {**get_target("rx671-wifi"), "bench_lock": str(self.root/"bench.lock"),
                  "rfp_lock": str(self.root/"rfp"/"global.lock"),
                  "owner_file": str(self.root/"canonical-owner.json")}
        events = self.root/"events"
        events.mkdir()
        clock = itertools.count(step=0.1)
        observer = MagicMock()
        observer.in_waiting = 0
        observer.read.return_value = uart_bytes
        serial = MagicMock()
        serial.return_value.__enter__.return_value = observer
        commands, owners = [], []
        def guarded(command, **_):
            commands.append(list(command))
            owners.append(json.loads(Path(target["owner_file"]).read_text()))
            return subprocess.CompletedProcess(command, return_code)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.dict(sys.modules, {"fcntl": SimpleNamespace(
            LOCK_EX=2, LOCK_NB=4, flock=Mock())}))
        stack.enter_context(patch.object(os, "O_NOFOLLOW", getattr(os, "O_NOFOLLOW", 0), create=True))
        stack.enter_context(patch.object(os, "fchmod", Mock(), create=True))
        stack.enter_context(patch.object(normal_boot, "validate", return_value={"tls_backend": "software"}))
        stack.enter_context(patch.object(installer, "check_ci_identity"))
        stack.enter_context(patch.object(installer, "check_bench_lease"))
        stack.enter_context(patch.object(installer, "check_devices"))
        stack.enter_context(patch.object(installer.tempfile, "mkdtemp", return_value=str(events)))
        stack.enter_context(patch.object(installer.time, "monotonic", side_effect=lambda: next(clock)))
        stack.enter_context(patch.object(installer.rfp_process, "run_guarded", side_effect=guarded))
        stack.enter_context(patch("serial.Serial", serial))
        prepare = stack.enter_context(patch.object(installer.trust, "provision_boot_trust"))
        download = stack.enter_context(patch.object(installer, "download_command"))
        return target, commands, owners, observer, serial, prepare, download

    def test_reset_only_issues_only_reset_and_reports_no_image_replacement(self):
        target, commands, owners, observer, _, prepare, download = self.reset_only_transaction()
        receipt = installer.install(self.root, target, SOURCE_SHA, reset_only=True)
        self.assertEqual([[*installer.rfp_command(target), "-sig", "-reset", "-noquery"]], commands)
        prepare.assert_not_called()
        download.assert_not_called()
        observer.reset_input_buffer.assert_called_once()
        self.assertTrue(observer.read.called, "A fresh quiet interval must actually be observed")
        self.assertFalse(Path(target["owner_file"]).exists())
        self.assertEqual(installer.RESET_ONLY_PROFILE, owners[0]["profile"])
        self.assertEqual(SOURCE_SHA, owners[0]["validated_bundle_source_sha"])
        self.assertNotIn("source_sha", owners[0])
        self.assertEqual(installer.RESET_ONLY_PROFILE, receipt["profile"])
        self.assertEqual(SOURCE_SHA, receipt["validated_bundle_source_sha"])
        self.assertEqual("offline_reference_only", receipt["bundle_validation"])
        self.assertEqual("not_reverified", receipt["current_image_signature"])
        for field in ("code_flash_written", "data_flash_written", "image_replaced"):
            self.assertIs(False, receipt[field])
        self.assertNotIn("signed_install_and_bootloader_handoff", receipt)
        self.assertNotIn("source_sha", receipt)
        self.assertTrue(receipt["end_state"]["reset_command_exit_zero"])
        self.assertTrue(receipt["end_state"]["fresh_uart_quiet_1s"])

    def test_reset_only_retains_owner_when_reset_fails_without_opening_uart(self):
        target, commands, _, _, serial, prepare, download = self.reset_only_transaction(return_code=7)
        with self.assertRaisesRegex(RuntimeError, "did not return success"):
            installer.install(self.root, target, SOURCE_SHA, reset_only=True)
        self.assertEqual(1, len(commands))
        self.assertTrue(Path(target["owner_file"]).exists())
        serial.assert_not_called()
        prepare.assert_not_called()
        download.assert_not_called()

    def test_reset_only_retains_owner_when_uart_is_not_quiet(self):
        target, commands, _, observer, _, prepare, download = self.reset_only_transaction(uart_bytes=b"x")
        with self.assertRaisesRegex(RuntimeError, "UART remained active"):
            installer.install(self.root, target, SOURCE_SHA, reset_only=True)
        self.assertEqual(1, len(commands))
        self.assertTrue(observer.read.called)
        self.assertTrue(Path(target["owner_file"]).exists())
        prepare.assert_not_called()
        download.assert_not_called()

    def test_reset_only_still_rejects_tampered_signed_bundle_before_hardware_io(self):
        root, fixture, _ = self.bundle()
        app = root/"normal_app.rsu"
        image = app.read_bytes()
        app.write_bytes(image[:-1] + bytes([image[-1] ^ 1]))
        with patch.object(installer, "check_bench_lease") as lease, \
                patch.object(installer, "check_devices") as devices, \
                patch.object(installer.rfp_process, "run_guarded") as programmer, \
                patch("serial.Serial") as serial:
            with self.assertRaises(RuntimeError):
                installer.install(root, fixture.target, SOURCE_SHA, reset_only=True)
            lease.assert_not_called()
            devices.assert_not_called()
            programmer.assert_not_called()
            serial.assert_not_called()

    def test_reset_only_cli_forwards_the_option_without_a_different_entrypoint(self):
        with patch.object(installer.sys, "platform", "linux"), \
                patch.object(installer.signal, "signal"), \
                patch.object(installer, "install", return_value={"profile": installer.RESET_ONLY_PROFILE}) as install:
            self.assertEqual(0, installer.main(["--bundle", str(self.root), "--target", "rx671-wifi",
                                               "--source-sha", SOURCE_SHA, "--reset-only"]))
            self.assertTrue(install.call_args.kwargs["reset_only"])

    def test_real_signed_bundles_and_exact_mirrors_for_all_three_targets(self):
        for target_id in normal_boot.trust.LAYOUTS:
            with self.subTest(target=target_id):
                root, fixture, manifest = self.bundle(target_id)
                self.assertEqual(manifest, normal_boot.validate(root, fixture.target, SOURCE_SHA))
                self.assertEqual(normal_boot.PROFILE, manifest["profile"])
                self.assertTrue(manifest["application"]["code_flash_only"])
                self.assertEqual(normal_boot.FILES | {"normal_install_manifest.json"}, {path.name for path in root.iterdir()})
                self.assertFalse(any(b"PRIVATE KEY" in path.read_bytes() for path in root.iterdir()))

    def test_rx671_tsip_app_keeps_real_signed_bytes_and_software_public_maintenance(self):
        root, fixture, manifest = self.bundle("rx671-wifi", backend="tsip")
        self.assertEqual("tsip", manifest["tls_backend"])
        self.assertEqual(manifest, normal_boot.validate(root, fixture.target, SOURCE_SHA))
        public_manifest = root/"public_signer_provisioner_manifest.json"
        maintenance = json.loads(public_manifest.read_text(encoding="utf-8"))
        self.assertEqual("software", maintenance["tls_backend"])
        # App backend support must not permit a TSIP public-maintenance image.
        public_manifest.write_text(json.dumps({**maintenance, "tls_backend": "tsip"}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "formal manifest/source/target/profile"):
            normal_boot.validate(root, fixture.target, SOURCE_SHA)

    def test_prepare_rejects_unsupported_backend_without_publishing_a_bundle(self):
        root, fixture, _ = self.bundle()
        inputs = {name: root/name for name in normal_boot.FILES
                  if name not in {"public_signer_bootloader_config.h", "public_signer_target.h"}}
        for index, backend in enumerate(("unsupported", "", None)):
            output = self.root/("unsupported-backend-"+str(index))
            with self.subTest(backend=backend), \
                    patch("tools.idt.prepare_public_signer._source_state", return_value=SOURCE_SHA):
                with self.assertRaisesRegex(RuntimeError, "Unsupported normal application backend"):
                    normal_boot.prepare(ROOT, fixture.target["id"], output, inputs, tls_backend=backend)
                self.assertFalse(output.exists())

    def test_direct_cli_prepares_real_synthetic_bundles_for_all_three_targets(self):
        # Execute the actual script from outside the checkout. Only Git state is
        # synthetic: no module preloading masks the script/package import path,
        # and every firmware, public-PEM, manifest and signature check is real.
        startup = self.root/"synthetic-python-startup"
        startup.mkdir()
        (startup/"sitecustomize.py").write_text(
            "import subprocess\n"
            "def synthetic_git(arguments, *args, **kwargs):\n"
            "    if arguments[0] == 'git' and arguments[-2:] == ['rev-parse', 'HEAD']:\n"
            f"        return subprocess.CompletedProcess(arguments, 0, {SOURCE_SHA!r} + '\\n', '')\n"
            "    if arguments[0] == 'git' and arguments[-3:] == ['status', '--porcelain=v1', '--untracked-files=all']:\n"
            "        return subprocess.CompletedProcess(arguments, 0, '', '')\n"
            "    raise AssertionError('Unexpected subprocess: no build or hardware is permitted')\n"
            "subprocess.run = synthetic_git\n", encoding="utf-8")
        environment = {**os.environ, "PYTHONPATH": str(startup), "PYTHONDONTWRITEBYTECODE": "1"}
        options = {"--rsu": "normal_app.rsu", "--bootloader": "bootloader.mot",
                   "--bootloader-bank1": "bootloader_bank1.mot", "--provisioner-mot": "public_signer_provisioner.mot",
                   "--provisioner-manifest": "public_signer_provisioner_manifest.json",
                   "--signer-cert": "signer.crt.pem", "--signer-public-key": "signer.pub.pem"}
        for target_id in normal_boot.trust.LAYOUTS:
            with self.subTest(target=target_id):
                original, fixture, expected = self.bundle(target_id)
                output = self.root/(target_id+"-direct-cli")
                command = [sys.executable, str(ROOT/"tools/prepare_normal_boot.py"),
                           "--source", str(ROOT), "--target", target_id, "--output", str(output)]
                for option, name in options.items():
                    command.extend((option, str(original/name)))
                completed = subprocess.run(command, cwd=self.root, env=environment, capture_output=True,
                                           text=True, encoding="utf-8", timeout=30)
                self.assertEqual(0, completed.returncode, completed.stderr)
                self.assertEqual({name: expected[name] for name in ("profile", "source_sha", "target_id", "tls_backend")},
                                 json.loads(completed.stdout))
                self.assertEqual(expected, normal_boot.validate(output, fixture.target, SOURCE_SHA))
                self.assertEqual({path.name: normal_boot.file_hash(path) for path in original.iterdir()},
                                 {path.name: normal_boot.file_hash(path) for path in output.iterdir()})

    def test_wrong_source_target_app_bytes_mirror_and_private_pem_fail_before_device_checks(self):
        root, fixture, _ = self.bundle()
        cases = [("normal_app.rsu", lambda raw: raw[:-1]+bytes([raw[-1]^1])),
                 ("bootloader_bank1.mot", lambda raw: raw.replace(b"424F4F54", b"454F4F54")),
                 ("signer.pub.pem", lambda raw: b"-----BEGIN PRIVATE KEY-----\nSYNTHETIC\n")]
        for name, change in cases:
            with self.subTest(input=name):
                path = root/name; previous = path.read_bytes(); path.write_bytes(change(previous))
                with patch.object(installer, "check_bench_lease") as lease, patch.object(installer, "check_devices") as devices:
                    with self.assertRaises((RuntimeError, ValueError)): installer.install(root, fixture.target, SOURCE_SHA)
                    lease.assert_not_called(); devices.assert_not_called()
                path.write_bytes(previous)
        for target, sha in ((fixture.target, "b"*40), (get_target("rx65n-bg96"), SOURCE_SHA)):
            with self.assertRaises(RuntimeError): normal_boot.validate(root, target, sha)

    def test_normal_sequence_is_bound_without_weakening_native_idt_initial_sequence(self):
        root, fixture, _ = self.bundle("rx72n-ethernet")
        image = bytearray((root/"normal_app.rsu").read_bytes())
        import struct
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        struct.pack_into("<I", image, 0x200, 2)
        r, s = utils.decode_dss_signature(fixture.key.sign(bytes(image[0x200:]), ec.ECDSA(hashes.SHA256())))
        image[0x2C:0x6C] = r.to_bytes(32,"big")+s.to_bytes(32,"big")
        files = {name: root/name for name in normal_boot.FILES}
        (root/"normal_app.rsu").write_bytes(image)
        self.assertEqual(2, normal_boot.signed_application(files, fixture.target)["sequence"])
        fixture.files["idt_transport.rsu"].write_bytes(image)
        with self.assertRaisesRegex(RuntimeError,"descriptor"):
            normal_boot.trust.validate_initial_rsu(fixture.files, fixture.target)

    def test_manifest_backend_hash_and_claim_substitution_is_rejected(self):
        root, fixture, manifest = self.bundle()
        path = root/"normal_install_manifest.json"
        mutations = [("tls_backend", "unsupported"), ("files", {}), ("application", {"sequence": 2}),
                     ("bootloader_policy_sha256", {}), ("public_signer_spki_sha256", "0"*64)]
        for field, value in mutations:
            with self.subTest(field=field):
                path.write_text(json.dumps({**manifest, field: value}))
                with self.assertRaises(RuntimeError): normal_boot.validate(root, fixture.target, SOURCE_SHA)

    def test_physical_ci_overrides_are_checked_instead_of_ignored(self):
        for target_id, prefix in (("rx72n-ethernet","RX72N_LINUX_"),
                                  ("rx65n-bg96","RX65N_BG96_"), ("rx671-wifi","RX671_WIFI_")):
            target = get_target(target_id)
            installer.check_ci_identity(target,{})
            installer.check_ci_identity(target,{prefix+"UART_PORT":target["uart"],
                                               prefix+"RFP_TOOL":"e2l:"+target["e2lite"]})
            for variable, value in ((prefix+"UART_PORT","/dev/other-board"),
                                    (prefix+"RFP_TOOL","e2l:OTHER"), (prefix+"UART_BAUD_RATE","115200")):
                with self.subTest(target=target_id,variable=variable), self.assertRaisesRegex(RuntimeError,variable):
                    installer.check_ci_identity(target,{variable:value})

    def test_source_changes_never_leave_a_usable_normal_manifest(self):
        _, fixture, _ = self.bundle()
        inputs = {name: fixture.files[name] for name in normal_boot.FILES
                  if name not in {"normal_app.rsu", "public_signer_bootloader_config.h", "public_signer_target.h"}}
        inputs["normal_app.rsu"] = fixture.files["idt_transport.rsu"]
        for index, states in enumerate(((SOURCE_SHA, RuntimeError("source dirty")),
                                        (SOURCE_SHA, SOURCE_SHA, RuntimeError("source dirty")))):
            output = self.root/("changed-source-"+str(index))
            with patch("tools.idt.prepare_public_signer._source_state",side_effect=states):
                with self.assertRaisesRegex(RuntimeError,"source dirty"):
                    normal_boot.prepare(ROOT,fixture.target["id"],output,inputs)
            self.assertFalse((output/"normal_install_manifest.json").exists())

    def test_event_storage_failure_precedes_the_first_programmer_command(self):
        root, fixture, _ = self.bundle()
        blocked = self.root/"not-a-directory"; blocked.write_text("preserve")
        call = Mock()
        with self.assertRaises(FileExistsError):
            normal_boot.trust.provision_boot_trust(root,fixture.target,SOURCE_SHA,call,Mock(),artifact_dir=blocked)
        call.assert_not_called()
        self.assertEqual("preserve",blocked.read_text())

    def test_failed_reset_cannot_claim_zero_exit_or_open_uart_observer(self):
        with patch("serial.Serial") as observer:
            with self.assertRaisesRegex(RuntimeError,"did not return success"):
                installer.reset_and_quiet(get_target("rx671-wifi"),
                    Mock(return_value=subprocess.CompletedProcess([],7)),Mock())
        observer.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Real inherited flock evidence requires Linux")
    def test_real_fdinfo_distinguishes_owned_descriptor_from_same_inode_without_lock(self):
        import fcntl
        path = self.root/"bench.lock"; path.touch()
        target = {**get_target("rx671-wifi"), "bench_lock": str(path), "owner_file": str(self.root/"no-owner")}
        held = os.open(path, os.O_RDWR); other = os.open(path, os.O_RDWR)
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(installer.socket, "gethostname", return_value=target["hostname"]), \
                    patch.object(installer.rfp_process, "raise_if_rfp_unsafe"):
                installer.check_bench_lease(target, held)
                with self.assertRaisesRegex(RuntimeError,"own an exclusive flock"):
                    installer.check_bench_lease(target, other)
                owner = {"profile":normal_boot.PROFILE,"pid":os.getpid(),"token":"synthetic-normal-owner"}
                Path(target["owner_file"]).write_text(json.dumps(owner))
                with self.assertRaisesRegex(RuntimeError,"retained or different"):
                    installer.check_bench_lease(target,held)
                installer.check_bench_lease(target,held,owner=owner)
                # Existing native bridge must reject this canonical record too.
                import importlib
                with patch.object(sys,"path",[str(ROOT/"tools/idt"),*sys.path]):
                    bridge=importlib.import_module("rpi_uart_bridge")
                    with self.assertRaises(FileExistsError):
                        bridge.persist_owner({"token":"native-owner"},Path(target["owner_file"]),initial=True)
        finally:
            os.close(other); os.close(held)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Transaction locking requires Linux")
    def test_transaction_keeps_lock_through_final_reset_and_retains_owner_on_unproved_cleanup(self):
        root, fixture, _ = self.bundle()
        target = {**fixture.target, "bench_lock": str(self.root/"bench.lock"),
                  "rfp_lock": str(self.root/"rfp"/"global.lock"), "owner_file": str(self.root/"canonical-owner.json")}
        owner = Path(target["owner_file"])
        def reset(*_):
            self.assertTrue(owner.exists())
            return {"fresh_uart_quiet_1s": True}
        # Offline target validation is tested above; this test varies only the
        # transaction's callbacks and cleanup outcome, with no programmer/serial.
        with patch.object(normal_boot,"validate",return_value={"tls_backend":"software"}), \
                patch.object(installer,"check_bench_lease"), patch.object(installer,"check_devices"), \
                patch.object(installer.trust,"provision_boot_trust") as prepare, \
                patch.object(installer.rfp_process,"run_guarded",return_value=subprocess.CompletedProcess([],0)), \
                patch.object(installer,"reset_and_quiet",side_effect=reset):
            receipt = installer.install(root,target,SOURCE_SHA)
            self.assertTrue(receipt["signed_install_and_bootloader_handoff"])
            prepare.assert_called_once(); self.assertFalse(owner.exists())
        with patch.object(normal_boot,"validate",return_value={"tls_backend":"software"}), \
                patch.object(installer,"check_bench_lease"), patch.object(installer,"check_devices"), \
                patch.object(installer.trust,"provision_boot_trust"), \
                patch.object(installer.rfp_process,"run_guarded",return_value=subprocess.CompletedProcess([],7)), \
                patch.object(installer,"reset_and_quiet",side_effect=reset):
            with self.assertRaisesRegex(RuntimeError,"did not return success"):
                installer.install(root,target,SOURCE_SHA)
            self.assertFalse(owner.exists())
        with patch.object(normal_boot,"validate",return_value={"tls_backend":"software"}), \
                patch.object(installer,"check_bench_lease"), patch.object(installer,"check_devices"), \
                patch.object(installer.trust,"provision_boot_trust",side_effect=RuntimeError("write failure")), \
                patch.object(installer,"reset_and_quiet",side_effect=RuntimeError("quiet unproved")):
            with self.assertRaisesRegex(RuntimeError,"quiet unproved"):
                installer.install(root,target,SOURCE_SHA)
            self.assertTrue(owner.exists())


if __name__ == "__main__": unittest.main()

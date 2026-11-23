"""Synthetic public signer validation and locked protocol tests; no device I/O."""
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import shlex
import struct
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from tools.idt import public_signer_provision as controller
from tools.idt.targets import get_target, target_fingerprint

ROOT = Path(__file__).resolve().parents[3]
SOURCE_SHA = "a"*40


def srecord(address, data):
    payload = bytes([len(data)+5])+address.to_bytes(4, "big")+data
    return "S3"+(payload+bytes([(~sum(payload)) & 0xFF])).hex().upper()+"\n"


class Fixture:
    def __init__(self, root, target_id):
        self.root, self.target = root, get_target(target_id)
        root.mkdir(parents=True, exist_ok=True)
        self.files = {name: root/name for name in controller.PUBLIC_SIGNER_INPUTS |
                      {"bootloader.mot", "bootloader_bank1.mot", "idt_transport.rsu"}}
        helpers = {"public_signer_provision.py": "tools/idt/public_signer_provision.py",
                   "public_signer_material.py": "tools/idt/public_signer_material.py",
                   "provision_rx671_ota.py": "tools/provision_rx671_ota.py",
                   "rx671_ota_host.py": "tools/rx671_ota_host.py",
                   "build_rx671_fwup_v2_rsu.py": "tools/build_rx671_fwup_v2_rsu.py"}
        for name, source in helpers.items():
            shutil.copyfile(ROOT/source, self.files[name])
        policy = (ROOT/self.target["bootloader_project"]/"src/rx_bootloader_config.h").read_bytes()
        self.files["public_signer_bootloader_config.h"].write_bytes(policy)
        chip = controller.CHIP_HEADERS[target_id]
        self.files["public_signer_target.h"].write_bytes(
            (ROOT/self.target["bootloader_project"]/"lib/rx_bootloader/config"/chip).read_bytes())
        self.key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.now(timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-public-signer")])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(self.key.public_key())
                .serial_number(1).not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
                .sign(self.key, hashes.SHA256()))
        self.files["signer.crt.pem"].write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self.files["signer.pub.pem"].write_bytes(self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        start, shift = controller.LAYOUTS[target_id]
        vector = start+0x300
        marker = b"PUBLIC_SIGNER_PROVISIONER source_sha="+SOURCE_SHA.encode("ascii")+b"\r\n"
        self.records = [(vector, b"CODE"), (vector+0x100, marker),
                        (0xFFFFFFFC, vector.to_bytes(4, "little")),
                        (0xFE7F5D00, bytes.fromhex("8FFFFFFF")), (0xFE7F5D20, bytes.fromhex("FFFFFFFF"))]
        self.files["public_signer_provisioner.mot"].write_text("".join(srecord(*entry) for entry in self.records))
        boot = [(0xFFFC0000, b"BOOT"), (0xFFFFFF80, bytes(range(128))),
                (0xFE7F5D00, bytes.fromhex("8FFFFFFF")), (0xFE7F5D20, bytes.fromhex("FFFFFFFF"))]
        self.files["bootloader.mot"].write_text("".join(srecord(*entry) for entry in boot))
        self.files["bootloader_bank1.mot"].write_text("".join(srecord(address-shift, data)
                            for address, data in boot if address >= 0xFFFC0000))
        self.metadata = {"schema_version": 1, "profile": controller.PROFILE, "target_id": target_id,
            "target_sha256": target_fingerprint(self.target), "source_sha": SOURCE_SHA, "source_tree_dirty": False,
            "formal": True, "tls_backend": "software", "bank_mode": "bank.dual", "cli_scope": "public_signer_only",
            "reset_vector_kind": "standalone_hardware_vector", "credentials_embedded": False,
            "credential_injection_requested": False,
            "credential_verification": {"client_and_wifi_headers_empty": True, "local_overrides_absent": True,
                "injection_environment_removed": True, "private_pem_payloads_absent": True,
                "private_pem_scan_policy": controller.material.PRIVATE_PEM_SCAN_POLICY,
                "scope": "embedded_client_claim_private_and_wifi_credentials"},
            "effective_command_validation": {"maintenance_compiler_defines_verified": True,
                "standalone_vectors_verified": True, "flash_ram_mapping_verified": True},
            "image_validation": {"reset_vector": f"0x{vector:08X}", "mde": "0xFFFFFF8F", "initial_bank": 0,
                "compiled_source_identity_verified": True, "code_flash_and_options_only": True},
            "effective_input_sha256": {name: "0"*64 for name in
                (self.target["application_project"]+"/.cproject", "Demos/include/aws_clientcredential.h",
                 "Demos/include/aws_clientcredential_keys.h")}}
        basename = Path(self.target["application_project"]).parent.name
        self.metadata["sha256"] = {basename+".mot": hashlib.sha256(self.files["public_signer_provisioner.mot"].read_bytes()).hexdigest(),
                                  basename+".map": "0"*64, basename+".abs": "1"*64}
        self.write_metadata()
        self.rsu(self.key)

    def write_metadata(self):
        self.files["public_signer_provisioner_manifest.json"].write_text(json.dumps(self.metadata))

    def change_records(self, records):
        self.files["public_signer_provisioner.mot"].write_text("".join(srecord(*entry) for entry in records))
        basename = Path(self.target["application_project"]).parent.name
        self.metadata["sha256"][basename+".mot"] = hashlib.sha256(self.files["public_signer_provisioner.mot"].read_bytes()).hexdigest()
        self.write_metadata()

    def rsu(self, key):
        target_id = self.target["id"]
        start, _ = controller.LAYOUTS[target_id]
        payload = bytearray(b"\xff"*(0xFFFC0000-start-0x300))
        payload[:4] = b"CODE"; payload[-4:] = (start+0x300).to_bytes(4, "little")
        if target_id == "rx671-wifi":
            image = controller._tools_module("build_rx671_fwup_v2_rsu").build_image(bytes(payload), key)
            self.files["idt_transport.rsu"].write_bytes(image)
        else:
            # The only private file belongs to this synthetic fixture. The
            # controller's input set never contains it or reads it.
            synthetic_key = self.root/"synthetic-unit-only-private-key.pem"
            synthetic_key.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            try:
                with redirect_stdout(io.StringIO()):
                    if target_id == "rx72n-ethernet":
                        image = controller._tools_module("build_fwup_v2_rsu").build_rsu(payload, synthetic_key, 1)
                        self.files["idt_transport.rsu"].write_bytes(image)
                    else:
                        mot = self.root/"synthetic-app.mot"
                        mot.write_text(srecord(start+0x300,b"CODE") + srecord(0xFFFBFFFC,(start+0x300).to_bytes(4,"little")))
                        packager = controller._tools_module("create_bg96_rsu")
                        with patch.object(packager.sys if hasattr(packager,"sys") else __import__("sys"), "argv",
                                ["create_bg96_rsu.py", "--mot", str(mot), "--key", str(synthetic_key),
                                 "--output", str(self.files["idt_transport.rsu"])]):
                            packager.main()
            finally:
                synthetic_key.unlink()

    def plan(self):
        return controller.validate_bundle(self.files, self.target, SOURCE_SHA)

    def download(self):
        reset = ["sudo","-n","/usr/local/bin/rfp-cli","-device",self.target["rfp_device"],"-tool",
                 "e2l:"+self.target["e2lite"],"-if","fine","-speed",self.target["rfp_speed"],
                 "-auth","id","F"*32,"-sig","-run","-noquery"]
        return ["python3", str(self.root/"test_uart_download_rx72n.py"), "--rsu",str(self.files["idt_transport.rsu"]),
                "--port",self.target["uart"],"--baud",str(self.target["baud"]),"--strict-success","--wait-for-ready",
                "--success-message","swap bank" if self.target["id"]=="rx65n-bg96" else "jump to user program",
                "--ready-message",'send "userprog.rsu" via UART.',"--reset-cmd",shlex.join(reset)]


class FakeSerial:
    timeout, write_timeout = .1, 10
    def __init__(self):
        self.responses = bytearray(); self.closed = False
    @property
    def in_waiting(self):
        return len(self.responses)
    def read(self, size):
        result = bytes(self.responses[:size]); del self.responses[:size]; return result
    def write(self, data):
        return len(data)
    def flush(self):
        pass
    def reset_input_buffer(self):
        self.responses.clear()
    def reset_output_buffer(self):
        pass
    def close(self):
        self.closed = True


class PublicSignerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def fixture(self, target="rx671-wifi"):
        return Fixture(self.root/target, target)

    def test_actual_packagers_and_all_three_bank_mirrors_are_accepted_offline(self):
        for target in controller.LAYOUTS:
            with self.subTest(target=target):
                fixture = self.fixture(target); plan=fixture.plan()
                self.assertEqual("not_established",plan["runtime_trust"])
                self.assertEqual("not_run",plan["status"])
                self.assertEqual(target_fingerprint(fixture.target),plan["target_sha256"])
                self.assertFalse(plan["private_credentials_used"])

    def test_validly_signed_segmented_v2_is_rejected_for_every_target(self):
        from cryptography.hazmat.primitives.asymmetric import utils
        from tools import normal_boot
        for target_id in controller.LAYOUTS:
            with self.subTest(target=target_id):
                fixture = self.fixture(target_id)
                start, _ = controller.LAYOUTS[target_id]
                image = bytearray(fixture.files["idt_transport.rsu"].read_bytes())
                image[0x200:0x300] = b"\xff" * 256
                struct.pack_into("<III", image, 0x200, 1, start + 0x300, 0xFFFC0000 - start - 0x300)
                r, s = utils.decode_dss_signature(fixture.key.sign(
                    bytes(image[0x200:]), ec.ECDSA(hashes.SHA256())))
                image[0x2c:0x6c] = r.to_bytes(32, "big") + s.to_bytes(32, "big")
                fixture.files["idt_transport.rsu"].write_bytes(image)
                with self.assertRaisesRegex(RuntimeError, "legacy RSU descriptor"):
                    controller.validate_initial_rsu(fixture.files, fixture.target)
                with self.assertRaisesRegex(RuntimeError, "descriptor"):
                    normal_boot.signed_application(
                        {**fixture.files, "normal_app.rsu": fixture.files["idt_transport.rsu"]},
                        fixture.target)

    def test_formal_source_target_and_isolation_claims_are_mandatory(self):
        fixture=self.fixture(); baseline=json.loads(json.dumps(fixture.metadata))
        mutations=[("source_sha","b"*40),("target_id","rx65n-bg96"),("target_sha256","0"*64),
                   ("formal",False),("formal",1),("source_tree_dirty",True),("credentials_embedded",True),
                   ("credential_injection_requested",True),("bank_mode","bank.single"),("cli_scope","full_credentials"),
                   ("effective_command_validation",{}),("credential_verification",{}),("effective_input_sha256",{})]
        for field,value in mutations:
            with self.subTest(field=field,value=value):
                fixture.metadata=json.loads(json.dumps(baseline)); fixture.metadata[field]=value; fixture.write_metadata()
                with self.assertRaises(RuntimeError):fixture.plan()

    def test_actual_mot_options_vectors_marker_and_ranges_override_manifest_claims(self):
        fixture=self.fixture(); original=fixture.records
        variants=[[(a,b"\x87\xff\xff\xff" if a==0xFE7F5D00 else data) for a,data in original],
                  [(a,b"\xf8\xff\xff\xff" if a==0xFE7F5D20 else data) for a,data in original],
                  [(a,(0xFFF01000).to_bytes(4,"little") if a==0xFFFFFFFC else data) for a,data in original],
                  [(a,data.replace(SOURCE_SHA.encode(),b"b"*40)) for a,data in original],
                  original+[(0x00100000,b"DF")], original+[(0xFFF03000,b"-----BEGIN PRIVATE KEY-----")]]
        for records in variants:
            with self.subTest(records=len(records)):
                fixture.change_records(records)
                with self.assertRaises(RuntimeError):fixture.plan()

    def test_pem_header_constants_do_not_hide_private_payloads_or_old_manifest_claims(self):
        fixture=self.fixture(); original=fixture.records
        header=b'-----BEGIN EC PRIVATE KEY-----'
        for suffix in (b'\0',b'\n\0',b'\r\n\0',b'\nU1lOVEhFVElD\n-----END EC PRIVATE KEY-----\0',b''):
            fixture.change_records(original+[(0xFFF03000,header+suffix)])
            if suffix in (b'\0',b'\n\0',b'\r\n\0'):
                fixture.plan()
            else:
                with self.assertRaisesRegex(RuntimeError,'Private PEM'):fixture.plan()
        fixture.change_records(original)
        for invalid in ({'private_pem_scan_policy':'any_header_allowed'},
                        {'private_pem_payloads_absent':False},
                        {'private_pem_payloads_absent':None,'private_pem_markers_absent':True}):
            saved=fixture.metadata['credential_verification'].copy()
            fixture.metadata['credential_verification'].update(invalid);fixture.write_metadata()
            with self.assertRaisesRegex(RuntimeError,'credential isolation'):fixture.plan()
            fixture.metadata['credential_verification']=saved
        fixture.write_metadata()

    def test_mirror_substitution_and_rsu_signature_or_df_are_rejected(self):
        fixture=self.fixture()
        mirror=fixture.files["bootloader_bank1.mot"]; original=mirror.read_bytes()
        mirror.write_text(srecord(0xFFEC0000,b"EVIL")+srecord(0xFFEFFF80,bytes(range(128))))
        with self.assertRaisesRegex(RuntimeError,"exact reviewed bank0 shift"):fixture.plan()
        mirror.write_bytes(original)
        rsu=fixture.files["idt_transport.rsu"]; original=rsu.read_bytes()
        changed=bytearray(original);changed[-8]^=1;rsu.write_bytes(changed)
        with self.assertRaisesRegex(RuntimeError,"does not match"):fixture.plan()
        changed=bytearray(original);struct.pack_into("<I",changed,0x12C,1);rsu.write_bytes(changed)
        with self.assertRaisesRegex(RuntimeError,"raw Data Flash"):fixture.plan()
        rsu.write_bytes(original+b"\xff"*32768)
        with self.assertRaisesRegex(RuntimeError,"RSU size"):fixture.plan()

    def test_policy_override_duplicates_and_other_target_are_rejected(self):
        fixture=self.fixture();path=fixture.files["public_signer_bootloader_config.h"];baseline=path.read_bytes()
        for name in ("RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE","RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE",
                     "RX_BOOTLOADER_USE_DUAL_BANK"):
            path.write_bytes(baseline+("\n#define "+name+" (0)\n").encode())
            with self.assertRaisesRegex(RuntimeError,"Unsafe or ambiguous"):fixture.plan()
        path.write_bytes(baseline)
        target=dict(fixture.target);target["e2lite"]="other"
        with self.assertRaisesRegex(RuntimeError,"hardware identity"):
            controller.validate_bundle(fixture.files,target,SOURCE_SHA)

    def test_private_pem_header_and_second_body_are_never_prefetched(self):
        fixture=self.fixture();path=fixture.files["signer.crt.pem"];public=path.read_bytes()
        for prefix, boundary in [(b"-----BEGIN PRIVATE KEY-----\n",None),
                                 (public+b"-----BEGIN PRIVATE KEY-----\n",len(public)+1)]:
            path.write_bytes(prefix+b"SYNTHETIC-DO-NOT-READ-BODY\n")
            limit=len(prefix) if boundary is None else boundary
            original_open=Path.open;positions=[]
            class Guard:
                def __init__(self,stream):self.stream=stream
                def __enter__(self):return self
                def __exit__(self,*args):positions.append(self.stream.tell());self.stream.close()
                def readline(self,count=-1):
                    result=self.stream.readline(count);self.assert_bound();return result
                def read(self,count=-1):
                    if count<0 or self.stream.tell()+count>limit:raise AssertionError("private body read")
                    result=self.stream.read(count);self.assert_bound();return result
                def assert_bound(self):
                    if self.stream.tell()>limit:raise AssertionError("private body prefetched")
            def opened(candidate,mode="r",buffering=-1,**kwargs):
                stream=original_open(candidate,mode,buffering=buffering,**kwargs)
                return Guard(stream) if candidate==path else stream
            with patch.object(Path,"open",opened), self.assertRaisesRegex(RuntimeError,"exactly one public PEM"):
                controller.validate_public_signer_material(path,fixture.files["signer.pub.pem"])
            self.assertLessEqual(positions[0],limit)

    def test_all_environment_inputs_and_private_runtime_scope_are_required(self):
        fixture=self.fixture();runtime=self.root/"execution";runtime.mkdir()
        with self.assertRaisesRegex(RuntimeError,"inputs are required"):
            controller.source_inputs(ROOT,runtime,fixture.target,SOURCE_SHA,environ={})
        environment={variable:str(fixture.files[name]) for name,variable in controller.ENVIRONMENT_INPUTS.items()}
        with self.assertRaisesRegex(RuntimeError,"private IDT runtime"):
            controller.source_inputs(ROOT,runtime,fixture.target,SOURCE_SHA,environ=environment)
        inputs=self.root/"inputs"/"public-signer";inputs.mkdir(parents=True)
        for name,variable in controller.ENVIRONMENT_INPUTS.items():
            shutil.copyfile(fixture.files[name],inputs/name);environment[variable]=str(inputs/name)
        files=controller.source_inputs(ROOT,runtime,fixture.target,SOURCE_SHA,environ=environment)
        self.assertEqual(controller.PUBLIC_SIGNER_INPUTS,set(files))
        self.assertEqual("not_established",controller.validate_prepared_signer(ROOT,runtime,fixture.target,SOURCE_SHA,environment)["runtime_trust"])

    def _execute(self,fixture, *, witness=SOURCE_SHA, call_error_at=None, owner=None):
        host=controller._tools_module("rx671_ota_host");provisioner=controller._tools_module("provision_rx671_ota")
        serial=FakeSerial();commands=[];cli=[]
        def runner(command,**kwargs):
            commands.append(command)
            if call_error_at==len(commands):raise RuntimeError("synthetic guarded failure")
            if "-sig" in command and "-run" in command:
                serial.responses.extend(b"PUBLIC_SIGNER_PROVISIONER source_sha="+witness.encode()+b"\r\n")
            return subprocess.CompletedProcess(command,0)
        def send(_serial,command,**kwargs):cli.append(command);return b"OK"
        real_read=provisioner.read_until
        def bounded_read(port,**kwargs):kwargs["timeout"]=.02;return real_read(port,**kwargs)
        with patch.object(host,"open_serial",return_value=serial), patch.object(provisioner,"enter_cli"), \
                patch.object(provisioner,"send_ascii_command",side_effect=send), \
                patch.object(provisioner,"read_until",side_effect=bounded_read), \
                patch.object(provisioner,"_wifi_credentials_from_environment",side_effect=AssertionError("no private credentials")), \
                patch.object(provisioner,"_set_wifi_credentials",side_effect=AssertionError("no private credentials")):
            result=controller.provision_and_install(fixture.root,fixture.target,SOURCE_SHA,runner,fixture.download(),
                                                   check_owner=owner or Mock())
        return result,commands,cli,serial

    def test_all_three_guarded_flows_use_actual_cli_and_preserve_df_after_initial_erase(self):
        for target in controller.LAYOUTS:
            with self.subTest(target=target):
                fixture=self.fixture(target);owner=Mock();result,commands,cli,serial=self._execute(fixture,owner=owner)
                self.assertEqual(7,len(commands));self.assertEqual(["-erase-chip","-reset","-noquery"],commands[0][-3:])
                self.assertTrue(all("-erase-chip" not in command for command in commands[1:]))
                start,shift=controller.LAYOUTS[target]
                self.assertEqual([f"{start-shift:08X},{0xFFFBFFFF-shift:08X}",f"{start:08X},FFFBFFFF"],
                    [commands[3][i+1] for i,value in enumerate(commands[3]) if value=="-range"])
                self.assertEqual(["format","conf commit"],[cli[0],cli[-1]])
                self.assertTrue(cli[1].startswith("conf set codesigncert "))
                self.assertTrue(cli[2].startswith("conf set codesignpubkey "))
                self.assertEqual(4,len(cli));self.assertTrue(serial.closed);self.assertGreater(owner.call_count,14)
                self.assertEqual("signature_checked_by_bootloader_on_initial_install",result["runtime_trust"])
                log=(fixture.root/"public-signer-events/provision-events.log").read_text()
                self.assertNotIn("-----BEGIN",log);self.assertNotIn("conf set",log)

    def test_missing_witness_failed_commit_or_download_never_establishes_trust(self):
        fixture=self.fixture()
        with self.assertRaises(TimeoutError):self._execute(fixture,witness="b"*40)
        with self.assertRaisesRegex(RuntimeError,"synthetic guarded failure"):
            self._execute(fixture,call_error_at=7)
        provisioner=controller._tools_module("provision_rx671_ota")
        with patch.object(provisioner,"provision",return_value={"success":True,"signer_only":True}), \
                self.assertRaisesRegex(RuntimeError,"actual reviewed transaction"):
            controller.provision_and_install(fixture.root,fixture.target,SOURCE_SHA,
                Mock(return_value=subprocess.CompletedProcess([],0)),fixture.download(),check_owner=Mock())

    def test_failed_commit_stops_before_install_area_erase_and_closes_owned_uart(self):
        fixture=self.fixture();host=controller._tools_module("rx671_ota_host")
        provisioner=controller._tools_module("provision_rx671_ota");serial=FakeSerial();commands=[]
        def runner(command,**kwargs):
            commands.append(command)
            if "-sig" in command and "-run" in command:
                serial.responses.extend(b"PUBLIC_SIGNER_PROVISIONER source_sha="+SOURCE_SHA.encode()+b"\r\n")
            return subprocess.CompletedProcess(command,0)
        def send(_serial,command,**kwargs):
            if command=="conf commit":raise RuntimeError("synthetic commit failure")
            return b"OK"
        with patch.object(host,"open_serial",return_value=serial),patch.object(provisioner,"enter_cli"), \
                patch.object(provisioner,"send_ascii_command",side_effect=send), \
                self.assertRaisesRegex(RuntimeError,"synthetic commit failure"):
            controller.provision_and_install(fixture.root,fixture.target,SOURCE_SHA,runner,fixture.download(),check_owner=Mock())
        self.assertEqual(3,len(commands));self.assertTrue(serial.closed)
        self.assertFalse(any("-erase" in command for command in commands))

    def test_no_owner_invalid_download_or_dirty_image_refuses_initial_chip_erase(self):
        fixture=self.fixture();runner=Mock()
        with self.assertRaisesRegex(RuntimeError,"ownership checks"):
            controller.provision_and_install(fixture.root,fixture.target,SOURCE_SHA,runner,fixture.download())
        command=fixture.download();command.remove("--strict-success")
        with self.assertRaises(RuntimeError):controller.provision_and_install(
            fixture.root,fixture.target,SOURCE_SHA,runner,command,check_owner=Mock())
        with self.assertRaisesRegex(RuntimeError,"Unexpected strict UART downloader option"):
            controller.provision_and_install(fixture.root,fixture.target,SOURCE_SHA,runner,
                                             fixture.download()+["--diag"],check_owner=Mock())
        fixture.metadata["source_tree_dirty"]=True;fixture.write_metadata()
        with self.assertRaises(RuntimeError):controller.provision_and_install(
            fixture.root,fixture.target,SOURCE_SHA,runner,fixture.download(),check_owner=Mock())
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()

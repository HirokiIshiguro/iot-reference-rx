"""Local credential/payload contract tests; never invoke AWS or hardware."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
try:
    from . import ota_support
except ImportError:
    import ota_support

from tools.idt.targets import get_target, target_fingerprint, target_ids
from tools.build_rx671_fwup_v2_rsu import APPLICATION_SIZE, build_image

ROOT = Path(__file__).resolve().parents[2]


def stack_source_fixture(source):
    """Model project-local BG96 and linked shared MQTT sources without Gitlinks.

    The source-only CI job intentionally initializes no production submodules.
    Actual project metadata is independently checked by the builder/plans; this
    fixture exercises source selection, source hashes and protocol observations.
    """
    def write(relative, text):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    write("manifest.yml", 'name: "unit reference"\nversion: "202604.00-LTS"\n')
    write("tools/idt/bundle-manifest.json", json.dumps({"idt_version": "4.9.0", "suite": "FRQ_2.5.0"}))
    for target_id in target_ids():
        project = get_target(target_id)["application_project"]
        shared = target_id != "rx65n-bg96"
        links = ("<linkedResources><link><name>Middleware</name><type>2</type>"
                 "<locationURI>AWS_IOT_MCU_ROOT/Middleware</locationURI></link></linkedResources>"
                 "<variableList><variable><name>AWS_IOT_MCU_ROOT</name>"
                 "<value>$%7BPARENT-3-PROJECT_LOC%7D</value></variable></variableList>" if shared else "")
        write(project + "/.project", "<projectDescription>" + links + "</projectDescription>")
        if not shared:
            mqtt = project + "/Middleware/FreeRTOS/coreMQTT/source"
            write(mqtt + "/include/core_mqtt.h", '#define MQTT_LIBRARY_VERSION "v2.3.1"\n')
            write(mqtt + "/core_mqtt_serializer.c", "#define MQTT_VERSION_3_1_1 ((uint8_t) 4U)\n"
                  "void serializeConnectPacket(void) { *pIndexLocal = MQTT_VERSION_3_1_1; }\n")
    mqtt = "Middleware/FreeRTOS/coreMQTT/source"
    write(mqtt + "/include/core_mqtt.h", '#define MQTT_LIBRARY_VERSION "v5.0.2"\n')
    write(mqtt + "/core_mqtt_serializer.c", "/* MQTT 5 CONNECT uses the private serializer. */\n")
    write(mqtt + "/core_mqtt_serializer_private.c", "#define MQTT_VERSION_5 (5U)\n"
          "void serializeConnectFixedHeader(void) { *pIndexLocal = MQTT_VERSION_5; }\n")
    return source


class StackMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="idt-stack-unit-")
        self.addCleanup(temporary.cleanup)
        self.source = stack_source_fixture(Path(temporary.name))

    def test_selected_project_stack_and_distinct_idt_compatibility_observations(self):
        for target_id in target_ids():
            with self.subTest(target=target_id):
                metadata = ota_support.source_stack_metadata(self.source, target_id)
                mqtt = metadata["core_mqtt"]
                bg96 = target_id == "rx65n-bg96"
                self.assertEqual(mqtt["version"], "v2.3.1" if bg96 else "v5.0.2")
                self.assertEqual(mqtt["protocol"], "3.1.1" if bg96 else "5.0")
                self.assertEqual(mqtt["wire_level"], 4 if bg96 else 5)
                self.assertEqual(metadata["source_manifest_version"], "202604.00-LTS")
                self.assertEqual(metadata["idt"]["freertos_version_check"]["status"], "unsupported")
                self.assertEqual(metadata["idt"]["mqtt_protocol_check"]["status"],
                                 "protocol-match-only" if bg96 else "protocol-mismatch")
                self.assertEqual(metadata["qualification"], "not-established")
                for field in ("header", "connect_serializer"):
                    evidence = mqtt[field]
                    self.assertEqual(evidence["sha256"],
                                     hashlib.sha256((self.source / evidence["path"]).read_bytes()).hexdigest())
                self.assertTrue(mqtt["header"]["path"].startswith(
                    get_target(target_id)["application_project"] + "/Middleware/" if bg96 else "Middleware/"))

    def test_changed_connect_serializer_cannot_reuse_a_protocol_assessment(self):
        target = get_target("rx65n-bg96")
        metadata = ota_support.source_stack_metadata(self.source, target)
        serializer = self.source / metadata["core_mqtt"]["connect_serializer"]["path"]
        serializer.write_text(serializer.read_text(encoding="utf-8").replace(
            "*pIndexLocal = MQTT_VERSION_3_1_1;", "*pIndexLocal = 5U;"), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unreviewed protocol level"):
            ota_support.source_stack_metadata(self.source, target)

    def test_changed_shared_project_mapping_cannot_assess_unreviewed_sources(self):
        for target_id in ("rx72n-ethernet", "rx671-wifi"):
            with self.subTest(target=target_id):
                project = self.source / get_target(target_id)["application_project"] / ".project"
                project.write_text(project.read_text(encoding="utf-8").replace(
                    "$%7BPARENT-3-PROJECT_LOC%7D", "$%7BPARENT-2-PROJECT_LOC%7D"), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "unreviewed Middleware source mapping"):
                    ota_support.source_stack_metadata(self.source, target_id)


class OtaSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="idt-ota-unit-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source, self.inputs, self.runtime = root / "checkout", root / "run/inputs", root / "run/execution"
        self.runtime.mkdir(parents=True)
        (self.source / "sample_keys").mkdir(parents=True)
        self.key = ec.generate_private_key(ec.SECP256R1())
        private = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption())
        (self.source / "sample_keys/secp256r1.privatekey").write_bytes(private)
        public = self.key.public_key().public_bytes(serialization.Encoding.PEM,
                                                    serialization.PublicFormat.SubjectPublicKeyInfo)
        header = self.source / "Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/src/key/code_signer_public_key.h"
        header.parent.mkdir(parents=True)
        header.write_text("#define CODE_SIGNER_PUBLIC_KEY_PEM " + json.dumps(public.decode()) + "\n")
        self.config = ota_support.make_ota_config(self.inputs, self.source, str)
        self.environment = ota_support.ota_environment(self.inputs, str)
        self.environment.update(IDT_RUNTIME_DIR=str(self.runtime), IDT_SOURCE_PATH=str(self.source))
        self.env_patch = patch.dict(os.environ, self.environment)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_certificate_matches_bootloader_key_and_wrong_certificate_fails(self):
        cert = x509.load_pem_x509_certificate((self.inputs / ota_support.TRUSTED_CERT).read_bytes())
        self.assertEqual(cert.public_key().public_numbers(), self.key.public_key().public_numbers())
        with self.assertRaisesRegex(RuntimeError, "differ"):
            ota_support.load_signer(self.inputs / ota_support.SIGNING_KEY,
                                    self.inputs / ota_support.UNTRUSTED_CERT)

    def test_bg96_uses_its_own_bootloader_signer_before_writing_credentials(self):
        target = get_target("rx65n-bg96")
        header = self.source / target["bootloader_project"] / "src/key/code_signer_public_key.h"
        header.parent.mkdir(parents=True)
        wrong_key = ec.generate_private_key(ec.SECP256R1())
        def public(key):
            return key.public_key().public_bytes(serialization.Encoding.PEM,
                                                 serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        header.write_text("#define CODE_SIGNER_PUBLIC_KEY_PEM " + json.dumps(public(wrong_key)) + "\n")
        inputs = self.inputs.parent / "bg96-inputs"
        with self.assertRaisesRegex(ValueError, "does not match"):
            ota_support.make_ota_config(inputs, self.source, str, target=target)
        self.assertFalse((inputs / ota_support.SIGNING_KEY).exists())
        header.write_text("#define CODE_SIGNER_PUBLIC_KEY_PEM " + json.dumps(public(self.key)) + "\n")
        config = ota_support.make_ota_config(inputs, self.source, str, target=target)
        self.assertTrue((inputs / ota_support.SIGNING_KEY).is_file())
        self.assertEqual(config["otaE2EFirmwarePath"], "{{testData.sourcePath}}/" +
                         ota_support.payload_relative_path(target))

    def test_payload_paths_keep_rx72n_compatibility_and_selected_target_contract(self):
        self.assertEqual(ota_support.payload_relative_path(get_target("rx72n-ethernet")),
                         ota_support.PAYLOAD)
        self.assertEqual(self.config["otaE2EFirmwarePath"], "{{testData.sourcePath}}/" +
                         ota_support.PAYLOAD)
        for target_id in ("rx65n-bg96", "rx671-wifi"):
            target = get_target(target_id)
            self.assertEqual(ota_support.payload_relative_path(target),
                             "artifacts/idt/build_transport/" + target["artifact_basename"] +
                             "_ota_payload.bin")

    def test_rx671_runtime_trust_is_required_before_writing_credentials(self):
        inputs = self.inputs.parent / "rx671-inputs"
        with self.assertRaisesRegex(ValueError, "verified LittleFS code_signer_public_key"):
            ota_support.make_ota_config(inputs, self.source, str, target="rx671-wifi")
        self.assertFalse((inputs / ota_support.SIGNING_KEY).exists())

    def rx671_public_bootstrap(self, key=None):
        target = get_target("rx671-wifi")
        root = self.runtime / "bootstrap"
        root.mkdir()
        key = self.key if key is None else key
        certificate, public = root / "signer.crt.pem", root / "signer.pub.pem"
        certificate.write_bytes(ota_support._certificate(key, "ephemeral unit bootstrap signer"))
        public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                        serialization.PublicFormat.SubjectPublicKeyInfo))
        def record(address, data):
            encoded = bytes([len(data) + 5]) + address.to_bytes(4, "big") + data
            return "S3" + (encoded + bytes([(~sum(encoded)) & 0xFF])).hex().upper() + "\n"
        mot = root / "provisioner.mot"
        mot.write_text(record(0xFFE00000, b"ephemeral-linear-fixture") +
                       record(0xFFFFFFFC, b"\x00\x00\xe0\xff"), encoding="ascii")
        source_sha = "a" * 40
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"schema_version": 1,
            "profile": "rx671-bank-single-ota-provisioner-v1", "bank_mode": "bank.single",
            "credentials_embedded": False, "source_sha": source_sha,
            "sha256": {"aws_wifi_rx671_ek.mot": hashlib.sha256(mot.read_bytes()).hexdigest()}}))
        policy_dir = self.source / target["bootloader_project"] / "src"
        policy_dir.mkdir(parents=True)
        (policy_dir / "rx_bootloader_config.h").write_text(
            "#define RX_BOOTLOADER_USE_LITTLEFS_KEY_STORE (1)\n"
            "#define RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE (0)\n"
            "#define RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK (0)\n"
            "#define RX_BOOTLOADER_REQUIRE_ECDSA_SIGNATURE (1)\n")
        (policy_dir / "rx671.h").write_text("#define RX_BOOTLOADER_INSTALL_DATA_FLASH (0)\n")
        return target, source_sha, {
            "IDT_RX671_PROVISIONER_MOT_FILE": str(mot),
            "IDT_RX671_PROVISIONER_MANIFEST_FILE": str(manifest),
            "IDT_RX671_SIGNER_CERT_FILE": str(certificate),
            "IDT_RX671_SIGNER_PUBLIC_KEY_FILE": str(public)}

    def test_rx671_prepared_public_signer_is_bound_to_custom_signer_and_rechecked_at_build(self):
        target, source_sha, bootstrap = self.rx671_public_bootstrap()
        inputs = self.runtime / "rx671-ota-inputs"
        config = ota_support.make_ota_config(inputs, self.source, str, target=target,
                                             bootstrap_environment=bootstrap, source_sha=source_sha)
        self.assertEqual((inputs / ota_support.TRUSTED_CERT).read_bytes(),
                         Path(bootstrap["IDT_RX671_SIGNER_CERT_FILE"]).read_bytes())
        self.assertEqual(config["otaE2EFirmwarePath"], "{{testData.sourcePath}}/" +
                         ota_support.payload_relative_path(target))
        source = self.runtime / "rx671-123456"
        shutil.copytree(self.source, source)
        (source / "Test/include").mkdir(parents=True)
        (source / "Test/include/test_execution_config.h").write_text("#define OTA_E2E_TEST_ENABLED 1\n")
        (source / "Test/include/test_param_config.h").write_text("#define OTA_APP_VERSION_MAJOR 0\n"
            "#define OTA_APP_VERSION_MINOR 9\n#define OTA_APP_VERSION_BUILD 3\n")
        environment = {**bootstrap, **ota_support.ota_environment(inputs, str), "IDT_SOURCE_SHA": source_sha}
        with patch.dict(os.environ, environment), contextlib.redirect_stdout(io.StringIO()):
            ota_support.prepare_source(source, target)
        self.assertTrue((source / "Test/include/idt_ota_signer.h").is_file())
        Path(bootstrap["IDT_RX671_PROVISIONER_MANIFEST_FILE"]).write_text("{}")
        with patch.dict(os.environ, environment):
            with self.assertRaisesRegex(RuntimeError, "manifest/hash/source mismatch"):
                ota_support.prepare_source(source, target)

    def test_rx671_prepared_wrong_signer_or_source_cannot_write_private_credentials(self):
        target, source_sha, bootstrap = self.rx671_public_bootstrap(ec.generate_private_key(ec.SECP256R1()))
        inputs = self.inputs.parent / "rx671-inputs"
        with self.assertRaisesRegex(ValueError, "does not match the prepared RX671 public signer"):
            ota_support.make_ota_config(inputs, self.source, str, target=target,
                                         bootstrap_environment=bootstrap, source_sha=source_sha)
        self.assertFalse((inputs / ota_support.SIGNING_KEY).exists())
        with self.assertRaisesRegex(RuntimeError, "manifest/hash/source mismatch"):
            ota_support.make_ota_config(inputs, self.source, str, target=target,
                                         bootstrap_environment=bootstrap, source_sha="b" * 40)
        self.assertFalse((inputs / ota_support.SIGNING_KEY).exists())

    def test_manifest_identity_and_fingerprint_reject_other_target_and_stale_config(self):
        for target_id in target_ids():
            target = get_target(target_id)
            manifest = {"target_id": target_id, "target_sha256": target_fingerprint(target)}
            ota_support.validate_target_manifest(manifest, target)
            with self.assertRaisesRegex(RuntimeError, "different IDT target"):
                ota_support.validate_target_manifest({**manifest, "target_sha256": "0" * 64}, target)
            for other_id in target_ids():
                if other_id != target_id:
                    with self.assertRaisesRegex(RuntimeError, "different IDT target"):
                        ota_support.validate_target_manifest(manifest, get_target(other_id))
        ota_support.validate_target_manifest({}, get_target("rx72n-ethernet"), allow_legacy=True)
        with self.assertRaises(RuntimeError):
            ota_support.validate_target_manifest({}, get_target("rx65n-bg96"), allow_legacy=True)

    def test_rx671_transfer_uses_exact_production_bytes_and_verified_signature(self):
        rsu = build_image(b"\xff" * APPLICATION_SIZE, self.key)
        transfer = ota_support.rx671_transfer_payload(rsu, self.key)
        self.assertEqual(transfer, rsu[0x200:])
        self.assertEqual(len(transfer), 0xBFE00)
        modified = bytearray(rsu)
        modified[-1] ^= 1
        with self.assertRaises(InvalidSignature):
            ota_support.rx671_transfer_payload(bytes(modified), self.key)
        modified = bytearray(rsu)
        struct.pack_into("<I", modified, 0x12C, 1)
        with self.assertRaisesRegex(RuntimeError, "Data Flash"):
            ota_support.rx671_transfer_payload(bytes(modified), self.key)

    def test_bg96_uart_trailer_and_flash_hashes_cover_actual_staged_files(self):
        target = get_target("rx65n-bg96")
        source = self.runtime / "abc-123456"
        (source / "Test/include").mkdir(parents=True)
        (source / "Test/include/test_param_config.h").write_text("/* source validation fixture */\n")
        output = source / "artifacts/idt/build_transport"
        output.mkdir(parents=True)
        def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
        mot, bootloader = output / "rx72n_idt_transport.mot", output / "bootloader.mot"
        mot.write_bytes(b"application MOT fixture")
        bootloader.write_bytes(b"bootloader MOT fixture")
        bank1 = output / "bootloader_bank1.mot"
        bank1.write_bytes(b"shifted bootloader fixture")
        rsu = output / "rx72n_idt_transport.rsu"
        rsu.write_bytes(b"R" * 0xC0000)
        (output / "build_manifest.json").write_text(json.dumps({
            "target_id": target["id"], "target_sha256": target_fingerprint(target),
            "outputs": {"mot": {"sha256": sha(mot)}, "bootloader": {"sha256": sha(bootloader)}}}))
        ota_support.record_packaging(source, target)
        self.assertEqual(rsu.read_bytes(), b"R" * 0xC0000 + b"\xff" * 32768)
        manifest = json.loads((output / "build_manifest.json").read_text())
        self.assertEqual(manifest["outputs"]["rsu"]["sha256"], sha(rsu))
        self.assertEqual(manifest["outputs"]["bootloader_bank1"]["sha256"], sha(bank1))
        ota_support.record_packaging(source, target)
        self.assertEqual(rsu.stat().st_size, 0xC8000)

    def test_detached_der_signature_rejects_modified_payload(self):
        image, signature = self.runtime / "payload.bin", self.runtime / "payload.sig"
        image.write_bytes(b"IDT test payload\x00\r\n")
        subprocess.run([sys.executable, str(Path(ota_support.__file__).with_name("ota_sign.py")),
                        str(image), str(signature), "--key", self.environment["IDT_OTA_SIGNING_KEY_FILE"],
                        "--certificate", self.environment["IDT_OTA_SIGNER_CERT_FILE"]],
                       check=True, stdout=subprocess.DEVNULL)
        self.key.public_key().verify(signature.read_bytes(), image.read_bytes(), ec.ECDSA(hashes.SHA256()))
        with self.assertRaises(InvalidSignature):
            self.key.public_key().verify(signature.read_bytes(), image.read_bytes() + b"changed", ec.ECDSA(hashes.SHA256()))

    def test_signing_outside_runtime_is_rejected(self):
        image = self.source / "outside.bin"
        image.write_bytes(b"outside")
        result = subprocess.run([sys.executable, str(Path(ota_support.__file__).with_name("ota_sign.py")),
                                 str(image), str(self.runtime / "signature"), "--key", self.environment["IDT_OTA_SIGNING_KEY_FILE"],
                                 "--certificate", self.environment["IDT_OTA_SIGNER_CERT_FILE"]],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.runtime / "signature").exists())

    def test_stale_mot_rejected_before_payload_tool(self):
        source = self.runtime / "abc-123456"
        (source / "Test/include").mkdir(parents=True)
        (source / "Test/include/test_param_config.h").write_text("#define OTA_APP_VERSION_MAJOR 0\n#define OTA_APP_VERSION_MINOR 9\n#define OTA_APP_VERSION_BUILD 3\n")
        output = source / "artifacts/idt/build_transport"
        output.mkdir(parents=True)
        (output / "rx72n_idt_transport.mot").write_text("modified image")
        for target_id in target_ids():
            with self.subTest(target=target_id):
                target = get_target(target_id)
                (output / "build_manifest.json").write_text(json.dumps({
                    "target_id": target_id, "target_sha256": target_fingerprint(target),
                    "outputs": {"mot": {"sha256": "0" * 64}}}))
                with patch.object(ota_support.subprocess, "run") as execute:
                    with self.assertRaisesRegex(RuntimeError, "MOT differs"):
                        ota_support.build_payload(source, target)
                    execute.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "runtime ledger uses Linux flock; execute this case in WSL")
    def test_all_target_real_packagers_produce_selected_payload_and_ledger(self):
        def srecord(address, data):
            record = bytes([len(data) + 5]) + address.to_bytes(4, "big") + data
            return "S3" + (record + bytes([(~sum(record)) & 0xFF])).hex().upper() + "\n"
        def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
        execute = subprocess.run
        stack_source = stack_source_fixture(self.runtime / "stack-source")
        for index, target_id in enumerate(target_ids()):
            with self.subTest(target=target_id):
                target = get_target(target_id)
                source = self.runtime / (target_id + "-123456")
                include = source / "Test/include"
                include.mkdir(parents=True)
                parameter = include / "test_param_config.h"
                parameter.write_text("#define OTA_APP_VERSION_MAJOR 0\n#define OTA_APP_VERSION_MINOR 9\n"
                                     "#define OTA_APP_VERSION_BUILD 3\n")
                image_id = f"{index + 1:032x}"
                signer_header = include / "idt_ota_signer.h"
                signer_header.write_text('#define IDT_OTA_IMAGE_ID "' + image_id + '"\n')
                output = source / "artifacts/idt/build_transport"
                output.mkdir(parents=True)
                mot = output / (target["artifact_basename"] + ".mot")
                app_start = 0xFFE00300 if target_id == "rx72n-ethernet" else 0xFFF00300
                reset_vector = app_start.to_bytes(4, "little")
                mot.write_text(srecord(app_start, b"\x12\x34\x56\x78") +
                               srecord(0xFFFBFFFC, reset_vector), encoding="ascii")
                for relative in (target["packager"], target["prm"]):
                    if relative:
                        destination = source / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(ROOT / relative, destination)
                stack = ota_support.source_stack_metadata(stack_source, target)
                (output / "build_manifest.json").write_text(json.dumps({
                    "target_id": target_id, "target_sha256": target_fingerprint(target),
                    "outputs": {"mot": {"sha256": sha(mot)}},
                    "parameter_config_sha256": sha(parameter),
                    "image_id": image_id, "signer_header_sha256": sha(signer_header),
                    "application_version": {"MAJOR": 0, "MINOR": 9, "BUILD": 3},
                    "production_stack": stack}))
                def convert(command, **kwargs):
                    return execute(command, **kwargs, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                with patch.object(ota_support.subprocess, "run", side_effect=convert), \
                        contextlib.redirect_stdout(io.StringIO()):
                    ota_support.build_payload(source, target)
                payload = source / ota_support.payload_relative_path(target)
                image = payload.read_bytes()
                app_size = 0xFFFC0000 - app_start
                self.assertEqual(struct.unpack_from("<III", image), (1, app_start, app_size))
                self.assertEqual(len(image), 0x100 + app_size)
                self.assertEqual(image[0x100:0x104], b"\x12\x34\x56\x78")
                self.assertEqual(image[-4:], reset_vector)
                if target_id == "rx671-wifi":
                    signed_rsu = output / (target["artifact_basename"] + "_ota_signed.rsu")
                    self.assertEqual(image, ota_support.rx671_transfer_payload(signed_rsu.read_bytes(), self.key))
        records = [json.loads(line) for line in (self.runtime / "ota-build-ledger.jsonl").read_text().splitlines()]
        self.assertEqual([item["target_id"] for item in records], list(target_ids()))
        for record in records:
            self.assertEqual(record["target_sha256"], target_fingerprint(get_target(record["target_id"])))
            self.assertEqual(record["production_stack"], ota_support.source_stack_metadata(stack_source, record["target_id"]))
            source = self.runtime / record["source_runtime_path"]
            self.assertEqual(record["payload_sha256"], sha(source / ota_support.payload_relative_path(get_target(record["target_id"]))))

    @unittest.skipUnless(os.name == "posix", "runtime ledger uses Linux flock; execute this case in WSL")
    def test_ledger_preserves_each_variant_without_credentials(self):
        source = self.runtime / "abc-123456"
        (source / "Test/include").mkdir(parents=True)
        parameter = source / "Test/include/test_param_config.h"
        output = source / "artifacts/idt/build_transport"
        output.mkdir(parents=True)
        mot = output / "rx72n_idt_transport.mot"
        mot.write_bytes(b"synthetic MOT fixture")
        def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
        for version in (3, 4):
            parameter.write_text(f"#define OTA_APP_VERSION_MAJOR 0U\n#define OTA_APP_VERSION_MINOR 9U\n#define OTA_APP_VERSION_BUILD {version}U\n")
            image_id = f"{version:032x}"
            header = source / "Test/include/idt_ota_signer.h"
            header.write_text('#define IDT_OTA_IMAGE_ID "' + image_id + '"\n')
            (output / "build_manifest.json").write_text(json.dumps({
                "outputs": {"mot": {"sha256": sha(mot)}}, "parameter_config_sha256": sha(parameter),
                "image_id": image_id, "signer_header_sha256": sha(header),
                "application_version": {"MAJOR": 0, "MINOR": 9, "BUILD": version}}))
            def generate(command, **_kwargs):
                Path(command[command.index("--output") + 1]).write_bytes(bytes([version]))
            with patch.object(ota_support.subprocess, "run", side_effect=generate), contextlib.redirect_stdout(io.StringIO()):
                ota_support.build_payload(source)
        raw = (self.runtime / "ota-build-ledger.jsonl").read_text()
        records = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual([item["ota_version"] for item in records], ["0.9.3", "0.9.4"])
        self.assertEqual(records[0]["payload_sha256"], hashlib.sha256(b"\x03").hexdigest())
        self.assertNotEqual(records[0]["payload_sha256"], records[1]["payload_sha256"])
        self.assertNotEqual(records[0]["image_id"], records[1]["image_id"])
        self.assertNotIn("PRIVATE KEY", raw)
        self.assertNotIn("CERTIFICATE", raw)

    def test_changed_image_identity_header_is_rejected_before_payload_tool(self):
        source = self.runtime / "abc-123456"
        (source / "Test/include").mkdir(parents=True)
        parameter = source / "Test/include/test_param_config.h"
        parameter.write_text("#define OTA_APP_VERSION_MAJOR 1\n#define OTA_APP_VERSION_MINOR 9\n#define OTA_APP_VERSION_BUILD 2\n")
        header = source / "Test/include/idt_ota_signer.h"
        header.write_text('#define IDT_OTA_IMAGE_ID "' + "a" * 32 + '"\n')
        header_hash = hashlib.sha256(header.read_bytes()).hexdigest()
        output = source / "artifacts/idt/build_transport"
        output.mkdir(parents=True)
        mot = output / "rx72n_idt_transport.mot"
        mot.write_bytes(b"synthetic compiled image")
        (output / "build_manifest.json").write_text(json.dumps({
            "outputs": {"mot": {"sha256": hashlib.sha256(mot.read_bytes()).hexdigest()}},
            "parameter_config_sha256": hashlib.sha256(parameter.read_bytes()).hexdigest(),
            "application_version": {"MAJOR": 1, "MINOR": 9, "BUILD": 2},
            "image_id": "a" * 32, "signer_header_sha256": header_hash}))
        header.write_text('#define IDT_OTA_IMAGE_ID "' + "b" * 32 + '"\n')
        with patch.object(ota_support.subprocess, "run") as execute:
            with self.assertRaisesRegex(RuntimeError, "identity header changed"):
                ota_support.build_payload(source)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()

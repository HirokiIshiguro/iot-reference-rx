"""Validate real staged files before mocked bench/SSH boundaries for all RX targets."""
import builtins
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import contextmanager, redirect_stdout
import io
from unittest.mock import Mock, patch

from tools.ci.tests import test_idt_public_signer_provision as signer_tests

ROOT = signer_tests.ROOT
sys.path.insert(0, str(ROOT/"tools/idt"))
sys.path.insert(0, str(ROOT/"tools"))
import public_signer_provision as controller
import flash_transport
import rpi_flash


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FlashFixture:
    """Use actual producer-shaped inputs and real host/remote validators."""
    def __init__(self, root, target_id):
        self.root=root;self.runtime=root/"runtime";self.runtime.mkdir(parents=True)
        self.signer=signer_tests.Fixture(self.runtime/"inputs/public-signer",target_id)
        self.target=self.signer.target
        self.source=self.runtime/"source/worktree";self.source.mkdir(parents=True)
        boot=self.source/self.target["bootloader_project"]
        (boot/"src").mkdir(parents=True)
        (boot/"src/rx_bootloader_config.h").write_bytes(self.signer.files["public_signer_bootloader_config.h"].read_bytes())
        chip=controller.CHIP_HEADERS[target_id]
        chip_dir=boot/"lib/rx_bootloader/config";chip_dir.mkdir(parents=True)
        (chip_dir/chip).write_bytes(self.signer.files["public_signer_target.h"].read_bytes())
        sample_public=(self.source/self.target["signing_key"]).with_suffix(".publickey")
        sample_public.parent.mkdir(parents=True)
        sample_public.write_bytes(self.signer.files["signer.pub.pem"].read_bytes())
        tools=self.source/"tools";tools.mkdir()
        for name in ("rx671_ota_host.py","provision_rx671_ota.py","build_rx671_fwup_v2_rsu.py","test_uart_download_rx72n.py"):
            shutil.copyfile(ROOT/"tools"/name,tools/name)
        params=self.source/"Test/include/test_param_config.h";params.parent.mkdir(parents=True)
        params.write_text("/* synthetic native scope: no embedded TLS material */\n")
        self.environment={variable:str(self.signer.files[name]) for name,variable in controller.ENVIRONMENT_INPUTS.items()}
        self.environment["IDT_RUNTIME_DIR"]=str(self.runtime)
        self.out=self.source/"artifacts/idt/build_transport";self.out.mkdir(parents=True)
        self.outputs={"mot":self.out/(self.target["artifact_basename"]+".mot"),
                      "rsu":self.out/(self.target["artifact_basename"]+".rsu"),
                      "bootloader":self.out/"bootloader.mot","bootloader_bank1":self.out/"bootloader_bank1.mot"}
        start,_=controller.LAYOUTS[target_id]
        self.outputs["mot"].write_text(signer_tests.srecord(start+0x300,b"CODE")+
                                     signer_tests.srecord(0xFFFBFFFC,(start+0x300).to_bytes(4,"little")))
        for field,name in (("rsu","idt_transport.rsu"),("bootloader","bootloader.mot"),("bootloader_bank1","bootloader_bank1.mot")):
            shutil.copyfile(self.signer.files[name],self.outputs[field])
        self.build_manifest={"schema_version":1,"target_id":target_id,
            "target_sha256":controller.target_fingerprint(self.target),"source_sha":signer_tests.SOURCE_SHA,
            "outputs":{name:{"sha256":digest(path)} for name,path in self.outputs.items()},
            "parameter_config_sha256":digest(params),
            "bootloader_policy_sha256":controller.policy_hashes(self.signer.files,self.target)}
        self.write_build_manifest()
        self.staged=root/"remote-staged";self.staged.mkdir()

    def write_build_manifest(self):
        (self.out/"build_manifest.json").write_text(json.dumps(self.build_manifest))

    def host_inputs(self):
        with patch.dict(os.environ,self.environment,clear=True):
            return flash_transport.validated_inputs(self.source,self.target)

    def stage(self):
        files,manifest=self.host_inputs()
        for name,path in files.items():shutil.copyfile(path,self.staged/name)
        self.flash_manifest=manifest
        self.manifest_sha=self.write_flash_manifest()
        return manifest

    def write_flash_manifest(self):
        path=self.staged/"flash_manifest.json";path.write_text(json.dumps(self.flash_manifest))
        return digest(path)

    def pkcs11_view(self):
        from tools.idt import pkcs11_source_view as view
        # The resolver is exercised with a real original SDK body and a separate
        # product facade. Native source/provenance qualification has its own tests.
        for relative in view.CONFIG_FILES:
            path=self.source/relative;path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists():
                path.write_text('version: "202604.00-LTS"\n' if relative=="manifest.yml" else
                                "#define PRODUCT_TEST_SETTING 0\n")
        native=self.runtime/"source/native-facade"
        view.create_source_view(self.source,native)
        facade=view.FACADE
        for name in view.GROUPS:
            if name not in {"Full_PKCS11_Capabilities","Full_PKCS11_NoObject"}:
                facade=facade.replace("    RUN_TEST_GROUP( "+name,"\t\t//RUN_TEST_GROUP( "+name)
        (native/view.FACADE_FILE).write_text(facade)
        built=view.build_directory(native,self.runtime)
        shutil.copytree(self.source,built)
        runner=built/view.PKCS11_RUNNER_FILE;runner.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/view.PKCS11_RUNNER_FILE,runner)
        for relative in view.CONFIG_FILES:(built/relative).write_bytes((native/relative).read_bytes())
        binding={"schema_version":1,"target_id":self.target["id"],"source_sha":signer_tests.SOURCE_SHA,
                 "selection":view.selected_group(native),"source_view_sha256":view._hashes(native),
                 "original_test_runner_sha256":digest(runner)}
        (built/view.BINDING_FILE).write_text(json.dumps(binding))
        self.source=built;self.out=built/"artifacts/idt/build_transport"
        self.outputs={field:self.out/path.name for field,path in self.outputs.items()}
        self.environment["IDT_SOURCE_PATH"]=str(native)
        return native


@contextmanager
def public_read_boundary(path, limit):
    """Fail if a generic read or BufferedReader prefetch reaches dummy private data."""
    original_open=Path.open;positions=[]
    class Guard:
        def __init__(self,stream):self.stream=stream;self.raw=getattr(stream,"raw",stream)
        def check(self):
            if self.raw.tell()>limit:raise AssertionError("dummy private body was read or prefetched")
        def __enter__(self):return self
        def __exit__(self,*args):positions.append(self.raw.tell());self.stream.close()
        def read(self,count=-1):
            if count<0 or self.raw.tell()+count>limit:raise AssertionError("generic read entered private body")
            value=self.stream.read(count);self.check();return value
        def readline(self,count=-1):
            value=self.stream.readline(count);self.check();return value
    def opened(candidate,mode="r",buffering=-1,**kwargs):
        stream=original_open(candidate,mode,buffering=buffering,**kwargs)
        return Guard(stream) if candidate==path else stream
    with patch.object(Path,"open",opened):yield positions


class PublicSignerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def fixture(self,target):return FlashFixture(self.root/target,target)

    def test_all_three_host_to_remote_manifests_validate_real_input_sets_and_policy(self):
        for target in controller.LAYOUTS:
            with self.subTest(target=target):
                fixture=self.fixture(target);manifest=fixture.stage()
                expected=rpi_flash.FLASH_INPUTS|controller.PUBLIC_SIGNER_INPUTS
                self.assertEqual(expected,set(manifest["files"]))
                validated=rpi_flash.validate_flash_manifest(fixture.staged,fixture.target,fixture.manifest_sha)
                self.assertEqual(manifest,validated)
                self.assertEqual("not_established",validated["public_signer_provision_plan"]["runtime_trust"])
                self.assertEqual(controller.policy_hashes(fixture.signer.files,fixture.target),validated["bootloader_policy_sha256"])

    def test_all_scope_callbacks_require_public_inputs_before_any_board_operation(self):
        for target in controller.LAYOUTS:
            for scope in ("transport","mqtt","ota-mqtt","pkcs11","ota-pal"):
                with self.subTest(target=target,scope=scope), \
                        patch.object(rpi_flash,"open_rfp_lock") as lock,patch.object(rpi_flash,"run_guarded") as rfp:
                    with self.assertRaisesRegex(RuntimeError,"provisioning inputs are required"):
                        rpi_flash.flash(self.root,controller.get_target(target),"c"*32)
                    lock.assert_not_called();rfp.assert_not_called()

    def test_rpi_locked_route_calls_real_generic_flow_for_all_three(self):
        for target in controller.LAYOUTS:
            with self.subTest(target=target):
                fixture=self.fixture(target);manifest=fixture.stage()
                rpi_flash.validate_flash_manifest(fixture.staged,fixture.target,fixture.manifest_sha)
                host=controller._tools_module("rx671_ota_host");provisioner=controller._tools_module("provision_rx671_ota")
                serial=signer_tests.FakeSerial();commands=[];cli=[];events=[]
                def run(command,**kwargs):
                    commands.append(command);events.append("command")
                    if "-sig" in command and "-run" in command and len(commands)==3:
                        serial.responses.extend(b"PUBLIC_SIGNER_PROVISIONER source_sha="+signer_tests.SOURCE_SHA.encode()+b"\r\n")
                    return subprocess.CompletedProcess(command,0)
                def send(port,command,**kwargs):cli.append(command);return b"OK"
                lock_module=SimpleNamespace(LOCK_EX=1,LOCK_NB=2,flock=Mock(side_effect=lambda *args:events.append("flock")))
                with patch.dict(sys.modules,{"fcntl":lock_module}), \
                        patch.object(rpi_flash,"open_rfp_lock",side_effect=lambda *args:events.append("lock") or 42), \
                        patch.object(rpi_flash,"validate_owner",return_value={"target_id":target}), \
                        patch.object(rpi_flash,"control",side_effect=lambda _target,_token,action:events.append(action)), \
                        patch.object(rpi_flash,"run_guarded",side_effect=run),patch.object(rpi_flash.os,"close") as close, \
                        patch.object(host,"open_serial",return_value=serial),patch.object(provisioner,"enter_cli"), \
                        patch.object(provisioner,"send_ascii_command",side_effect=send),redirect_stdout(io.StringIO()) as output:
                    rpi_flash.flash(fixture.staged,fixture.target,"c"*32,manifest)
                self.assertEqual(["lock","flock","pause","mark-flashed"],events[:4])
                self.assertEqual(9,len(commands));self.assertIn("-erase-chip",commands[0])
                self.assertFalse(any("-erase-chip" in command for command in commands[1:]))
                self.assertIn("--strict-success",commands[6]);self.assertIn("-reset",commands[7]);self.assertIn("-run",commands[8])
                self.assertEqual("conf commit",cli[-1]);self.assertEqual(4,len(cli));self.assertTrue(serial.closed)
                self.assertIn("resume",events);close.assert_called_once_with(42)
                self.assertEqual("IDT_FLASH_COMPLETE",output.getvalue().strip())

    def test_all_three_native_missing_bootstrap_inputs_stop_before_install(self):
        from tools.idt import run_idt
        for target in controller.LAYOUTS:
            with self.subTest(target=target):
                fixture=self.fixture(target)
                execution=fixture.root/"new-native-execution";execution.mkdir()
                with patch.object(run_idt,"HOST",{"windows_powershell":str(fixture.signer.files["signer.crt.pem"])}), \
                        patch.object(run_idt,"SOURCE",fixture.source), \
                        patch.object(run_idt.subprocess,"check_output",return_value="7"), \
                        patch.object(run_idt,"install_idt") as install,patch.dict(os.environ,{},clear=True):
                    with self.assertRaisesRegex(RuntimeError,"requires reviewed public bootstrap input"):
                        run_idt.transport(execution,"unit-region",Mock(),{"source_sha":signer_tests.SOURCE_SHA},
                                          "pkcs11",target=fixture.target)
                install.assert_not_called()

    def test_native_private_pem_boundary_precedes_bootstrap_copy_for_all_three(self):
        from tools.idt import run_idt
        for target in controller.LAYOUTS:
            with self.subTest(target=target):
                fixture=self.fixture(target);path=fixture.signer.files["signer.crt.pem"]
                header=b"-----BEGIN PRIVATE KEY-----\n";path.write_bytes(header+b"SYNTHETIC-PRIVATE-BODY\n")
                inputs=fixture.runtime/"inputs"
                with patch.object(run_idt,"SOURCE",fixture.source),public_read_boundary(path,len(header)), \
                        self.assertRaisesRegex(RuntimeError,"exactly one public PEM"):
                    run_idt.public_signer_bootstrap_environment(inputs,signer_tests.SOURCE_SHA,fixture.target,
                                                               environ=fixture.environment)
                self.assertFalse((inputs/"public-signer-bootstrap").exists())

    def test_native_failed_formal_validation_removes_only_its_new_copies(self):
        from tools.idt import run_idt
        for target in controller.LAYOUTS:
            with self.subTest(target=target):
                fixture=self.fixture(target);inputs=fixture.runtime/"inputs"
                unrelated=inputs/"preserved.txt";unrelated.write_text("preserved")
                fixture.signer.metadata["bank_mode"]="bank.single";fixture.signer.write_metadata()
                with patch.object(run_idt,"SOURCE",fixture.source), \
                        self.assertRaisesRegex(RuntimeError,"formal manifest/source/target/profile mismatch"):
                    run_idt.public_signer_bootstrap_environment(inputs,signer_tests.SOURCE_SHA,fixture.target,
                                                               environ=fixture.environment)
                self.assertFalse((inputs/"public-signer-bootstrap").exists())
                self.assertEqual("preserved",unrelated.read_text())

    def test_staged_boot_policy_requires_effective_build_input_hashes_for_all_three(self):
        for target in controller.LAYOUTS:
            fixture=self.fixture(target);manifest=fixture.stage()
            rpi_flash.validate_public_signer_policy_binding(fixture.staged,fixture.target,manifest)
            with self.assertRaisesRegex(RuntimeError,"effective build inputs"):
                rpi_flash.validate_public_signer_policy_binding(fixture.staged,fixture.target,{"bootloader_policy_sha256":{}})

    def test_private_header_or_appended_private_body_is_rejected_before_host_and_remote_hashing(self):
        for target in controller.LAYOUTS:
            fixture=self.fixture(target);fixture.stage()
            for remote in (False,True):
                path=(fixture.staged if remote else fixture.signer.root)/"signer.crt.pem"
                original=path.read_bytes()
                for prefix,limit in ((b"-----BEGIN PRIVATE KEY-----\n",len(b"-----BEGIN PRIVATE KEY-----\n")),
                                     (original+b"-----BEGIN PRIVATE KEY-----\n",len(original)+1)):
                    with self.subTest(target=target,remote=remote,appended=limit>30):
                        path.write_bytes(prefix+b"SYNTHETIC-PRIVATE-BODY-DO-NOT-READ\n")
                        with public_read_boundary(path,limit) as positions, \
                                self.assertRaisesRegex(RuntimeError,"exactly one public PEM"):
                            if remote:rpi_flash.validate_flash_manifest(fixture.staged,fixture.target,fixture.manifest_sha)
                            else:fixture.host_inputs()
                        self.assertLessEqual(positions[0],limit)
                path.write_bytes(original)

    def test_actual_image_source_policy_and_manifest_tampering_stops_before_fcntl_uart_and_rfp(self):
        for target in controller.LAYOUTS:
            fixture=self.fixture(target);fixture.stage()
            baseline={name:(fixture.staged/name).read_bytes() for name in fixture.flash_manifest["files"]}
            manifest_original=json.loads(json.dumps(fixture.flash_manifest))
            for case in ("source","unsigned_rsu","missing_mot","compiled_marker","policy","wrong_target","mirror","plan"):
                with self.subTest(target=target,case=case):
                    for name,body in baseline.items():(fixture.staged/name).write_bytes(body)
                    manifest=json.loads(json.dumps(manifest_original))
                    if case=="source":manifest["source_sha"]="b"*40
                    elif case=="unsigned_rsu":
                        path=fixture.staged/"idt_transport.rsu";image=bytearray(path.read_bytes());image[0x2C:0x6C]=b"\0"*64;path.write_bytes(image)
                    elif case=="missing_mot":(fixture.staged/"public_signer_provisioner.mot").unlink()
                    elif case=="compiled_marker":
                        path=fixture.staged/"public_signer_provisioner.mot"
                        records=[(a,data.replace(signer_tests.SOURCE_SHA.encode(),b"b"*40)) for a,data in fixture.signer.records]
                        path.write_text("".join(signer_tests.srecord(*entry) for entry in records))
                        meta_path=fixture.staged/"public_signer_provisioner_manifest.json";meta=json.loads(meta_path.read_bytes())
                        basename=Path(fixture.target["application_project"]).parent.name
                        meta["sha256"][basename+".mot"]=digest(path);meta_path.write_text(json.dumps(meta))
                    elif case=="policy":
                        path=fixture.staged/"public_signer_bootloader_config.h"
                        path.write_bytes(path.read_bytes()+b"\n#define RX_BOOTLOADER_ALLOW_BUILTIN_PUBLIC_KEY_FALLBACK (1)\n")
                        manifest["bootloader_policy_sha256"]=controller.policy_hashes(
                            {name:fixture.staged/name for name in controller.PUBLIC_SIGNER_INPUTS},fixture.target)
                    elif case=="wrong_target":
                        meta_path=fixture.staged/"public_signer_provisioner_manifest.json";meta=json.loads(meta_path.read_bytes())
                        meta["target_id"]="rx65n-bg96" if target!="rx65n-bg96" else "rx72n-ethernet";meta_path.write_text(json.dumps(meta))
                    elif case=="mirror":
                        path=fixture.staged/"bootloader_bank1.mot";_,shift=controller.LAYOUTS[target]
                        path.write_text(signer_tests.srecord(0xFFFC0000-shift,b"EVIL")+
                                        signer_tests.srecord(0xFFFFFF80-shift,bytes(range(128))))
                    elif case=="plan":manifest["public_signer_provision_plan"]["runtime_trust"]="self-attested"
                    original_import=builtins.__import__;fcntl_attempts=[]
                    def imported(name,*args,**kwargs):
                        if name=="fcntl":fcntl_attempts.append(name);raise AssertionError("fcntl imported before validation")
                        return original_import(name,*args,**kwargs)
                    with patch.object(builtins,"__import__",side_effect=imported), \
                            patch.object(rpi_flash,"open_rfp_lock") as lock,patch.object(rpi_flash,"run_guarded") as rfp, \
                            patch.object(rpi_flash,"control") as uart, self.assertRaises(RuntimeError):
                        rpi_flash.flash(fixture.staged,fixture.target,"c"*32,manifest)
                    self.assertFalse(fcntl_attempts);lock.assert_not_called();rfp.assert_not_called();uart.assert_not_called()

    def test_remote_strict_manifest_rejects_input_set_and_helper_hash_tampering(self):
        fixture=self.fixture("rx671-wifi");fixture.stage();original=json.loads(json.dumps(fixture.flash_manifest))
        for extra in (True,False):
            fixture.flash_manifest=json.loads(json.dumps(original))
            if extra:fixture.flash_manifest["files"]["unexpected.py"]={"sha256":"0"*64,"size_bytes":1}
            else:fixture.flash_manifest["files"].pop("public_signer_material.py")
            sha=fixture.write_flash_manifest()
            with self.assertRaisesRegex(RuntimeError,"Unexpected flash input set"):
                rpi_flash.validate_flash_manifest(fixture.staged,fixture.target,sha)
        fixture.flash_manifest=original;sha=fixture.write_flash_manifest()
        path=fixture.staged/"rx671_ota_host.py";path.write_bytes(path.read_bytes()+b"\n# substituted helper\n")
        with self.assertRaisesRegex(RuntimeError,"Flash input hash mismatch"):
            rpi_flash.validate_flash_manifest(fixture.staged,fixture.target,sha)

    def test_host_firmware_and_effective_policy_tampering_fails_before_any_ssh(self):
        for target in controller.LAYOUTS:
            fixture=self.fixture(target)
            with self.subTest(target=target):
                fixture.build_manifest["bootloader_policy_sha256"]={};fixture.write_build_manifest()
                with patch.object(flash_transport.subprocess,"run") as network, \
                        self.assertRaisesRegex(RuntimeError,"effective build inputs"):
                    fixture.host_inputs()
                network.assert_not_called()
                fixture.build_manifest["bootloader_policy_sha256"]=controller.policy_hashes(fixture.signer.files,fixture.target)
                fixture.write_build_manifest();fixture.outputs["rsu"].write_bytes(b"substituted")
                with patch.object(flash_transport.subprocess,"run") as network, \
                        self.assertRaisesRegex(RuntimeError,"Firmware hash mismatch"):
                    fixture.host_inputs()
                network.assert_not_called()

    def test_pkcs11_ssh_timeout_preserves_remote_staging_after_real_bound_input_validation(self):
        fixture=self.fixture("rx72n-ethernet");native=fixture.pkcs11_view();calls=[]
        def execute(command,**kwargs):
            calls.append(command)
            if "rpi_flash.py" in command[-1]:
                raise subprocess.TimeoutExpired(["synthetic-ssh"],kwargs["timeout"])
            return subprocess.CompletedProcess(command,0)
        environment={**fixture.environment,"IDT_BENCH_TOKEN":"c"*32,"IDT_TARGET":fixture.target["id"],"IDT_SCOPE":"pkcs11"}
        with patch.dict(os.environ,environment,clear=True), \
                patch.object(sys,"argv",["synthetic-flash",str(native)]), \
                patch.object(flash_transport.subprocess,"check_output",return_value="synthetic-path"), \
                patch.object(flash_transport.subprocess,"run",side_effect=execute), \
                self.assertRaises(subprocess.TimeoutExpired):
            flash_transport.main()
        self.assertTrue(any("rpi_flash.py" in command[-1] for command in calls))
        self.assertFalse(any("shutil.rmtree" in command[-1] for command in calls))


if __name__=="__main__":unittest.main()

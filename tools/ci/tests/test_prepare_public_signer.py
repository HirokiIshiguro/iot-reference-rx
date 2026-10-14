"""Prepare actual public inputs with compiler/certificate processes mocked only."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization

from tools.idt import prepare_public_signer as helper
from tools.ci.tests import test_idt_public_signer_integration as integration
from tools.ci.tests import test_idt_public_signer_provision as signer_tests
from tools.ci.tests import test_idt_source_manifest as git_fixture


@unittest.skipUnless(git_fixture.GIT,"Read-only source verification needs isolated local Git fixture objects")
class PreparePublicSignerTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.real_run=subprocess.run
        self.fixture_count=0

    def fixture(self,target_id="rx671-wifi"):
        self.fixture_count+=1
        fixture=integration.FlashFixture(self.root/(target_id+"-"+str(self.fixture_count)),target_id)
        source=fixture.source
        project=source/fixture.target["application_project"];project.mkdir(parents=True)
        name=Path(fixture.target["application_project"]).parent.name
        (project/".project").write_text("<projectDescription><name>"+name+"</name></projectDescription>")
        (project/".cproject").write_text("<cproject />")
        shutil.copyfile(signer_tests.ROOT/"tools/generate_signer_cert.py",source/"tools/generate_signer_cert.py")
        key=source/fixture.target["signing_key"]
        key.write_bytes(fixture.signer.key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        git_fixture.git(source,"init","--quiet","--template=")
        git_fixture.git(source,"add","--all")
        sha=git_fixture.commit_fixture_tree(source)
        fixture.signer.metadata["source_sha"]=sha
        records=[(address,data.replace(signer_tests.SOURCE_SHA.encode(),sha.encode()))
                 for address,data in fixture.signer.records]
        fixture.signer.change_records(records)
        fixture.output=fixture.root/"prepared-public-inputs"
        fixture.workspace=fixture.root/"e2-workspace"
        fixture.source_sha=sha
        return fixture

    def production_mocks(self,fixture,*,missing=None,formal=True,certificate=None):
        def build(source,target_id,output,workspace,python):
            self.assertEqual(fixture.source,source);self.assertEqual(fixture.target["id"],target_id)
            self.assertEqual(fixture.workspace,workspace);self.assertEqual("fixture-python",python)
            output.mkdir()
            print("SYNTHETIC PRIVATE COMPILER DIAGNOSTIC")
            name=Path(fixture.target["application_project"]).parent.name
            if missing!="mot":shutil.copyfile(fixture.signer.files["public_signer_provisioner.mot"],output/(name+".mot"))
            metadata=json.loads(json.dumps(fixture.signer.metadata))
            if not formal:metadata["formal"]=False;metadata["source_tree_dirty"]=True
            if missing!="manifest":(output/"provisioner-manifest.json").write_text(json.dumps(metadata))
            return metadata
        def run(command,**kwargs):
            if command[0]=="git":return self.real_run(command,**kwargs)
            self.assertEqual("fixture-python",command[0])
            self.assertEqual(fixture.source/"tools/generate_signer_cert.py",Path(command[1]))
            self.assertEqual(fixture.source/fixture.target["signing_key"],Path(command[command.index("--key")+1]))
            output=Path(command[command.index("--out")+1])
            kwargs["stdout"].write(b"SYNTHETIC PRIVATE CERTIFICATE TOOL DIAGNOSTIC\n")
            if missing!="certificate":
                output.write_bytes((certificate or fixture.signer.files["signer.crt.pem"]).read_bytes())
            return subprocess.CompletedProcess(command,0)
        return build,run

    def test_all_three_prepare_producer_and_real_matching_public_parts_without_stdout_leaks(self):
        for target in helper.controller.LAYOUTS:
            with self.subTest(target=target):
                fixture=self.fixture(target);build,run=self.production_mocks(fixture)
                stdout,stderr=io.StringIO(),io.StringIO()
                with patch.object(helper.producer,"build",side_effect=build) as compiler, \
                        patch.object(helper.subprocess,"run",side_effect=run) as child, \
                        patch.dict(os.environ,{variable:"" for variable in helper.controller.ENVIRONMENT_INPUTS.values()}),redirect_stdout(stdout),redirect_stderr(stderr):
                    status=helper.main(["--source",str(fixture.source),"--target",target,"--output",str(fixture.output),
                                        "--workspace",str(fixture.workspace),"--python","fixture-python"])
                self.assertEqual(0,status,stderr.getvalue());self.assertFalse(stderr.getvalue())
                paths=json.loads(stdout.getvalue());self.assertEqual(set(helper.controller.ENVIRONMENT_INPUTS.values()),set(paths))
                self.assertNotIn("DIAGNOSTIC",stdout.getvalue());self.assertNotIn("-----BEGIN",stdout.getvalue())
                for path in paths.values():self.assertTrue(Path(path).is_file());self.assertTrue(Path(path).is_relative_to(fixture.output))
                checked=helper.controller.validate_prepared_signer(fixture.source,fixture.output,fixture.target,
                                                                 fixture.source_sha,environ=paths)
                self.assertEqual("not_established",checked["runtime_trust"])
                self.assertEqual(fixture.signer.files["signer.pub.pem"].read_bytes(),Path(paths["IDT_PUBLIC_SIGNER_PUBLIC_KEY_FILE"]).read_bytes())
                compiler.assert_called_once();self.assertEqual(5,child.call_count) # four readonly Git calls + certificate tool
                self.assertIn("COMPILER DIAGNOSTIC",(fixture.output/"producer-private.log").read_text())
                self.assertIn("CERTIFICATE TOOL DIAGNOSTIC",(fixture.output/"signer-tool-private.log").read_text())

    def test_dirty_source_partial_overrides_and_existing_output_refuse_producer_and_preserve_inputs(self):
        fixture=self.fixture();source_marker=fixture.source/"unexpected.txt";source_marker.write_text("uncommitted")
        with patch.object(helper.producer,"build") as compiler,self.assertRaisesRegex(RuntimeError,"clean committed"):
            helper.prepare(fixture.source,fixture.target["id"],fixture.output,fixture.workspace,"fixture-python",environ={})
        compiler.assert_not_called();self.assertFalse(fixture.output.exists());source_marker.unlink()
        with patch.object(helper.producer,"build") as compiler,self.assertRaisesRegex(RuntimeError,"all four"):
            helper.prepare(fixture.source,fixture.target["id"],fixture.output,fixture.workspace,"fixture-python",
                           environ={"IDT_PUBLIC_SIGNER_CERT_FILE":str(fixture.signer.files["signer.crt.pem"])})
        compiler.assert_not_called();self.assertFalse(fixture.output.exists())
        fixture.output.mkdir();preserved=fixture.output/"preserved.txt";preserved.write_text("preserved")
        with patch.object(helper.producer,"build") as compiler,self.assertRaises(FileExistsError):
            helper.prepare(fixture.source,fixture.target["id"],fixture.output,fixture.workspace,"fixture-python",environ={})
        compiler.assert_not_called();self.assertEqual("preserved",preserved.read_text())

    def test_formal_false_missing_artifacts_and_certificate_mismatch_leave_no_public_input_set(self):
        for case in ("formal","mot","manifest","certificate","certificate_mismatch"):
            with self.subTest(case=case):
                fixture=self.fixture("rx671-wifi" if case=="formal" else "rx65n-bg96")
                if case=="certificate_mismatch":
                    other=signer_tests.Fixture(fixture.root/"other-public-signer","rx671-wifi")
                    certificate=other.files["signer.crt.pem"]
                else:certificate=None
                build,run=self.production_mocks(fixture,missing=case,formal=case!="formal",certificate=certificate)
                sibling=fixture.root/"preserved.txt";sibling.write_text("preserved")
                with patch.object(helper.producer,"build",side_effect=build),patch.object(helper.subprocess,"run",side_effect=run), \
                        self.assertRaises(RuntimeError):
                    helper.prepare(fixture.source,fixture.target["id"],fixture.output,fixture.workspace,"fixture-python",environ={})
                self.assertFalse((fixture.output/"build").exists())
                for name in helper.controller.ENVIRONMENT_INPUTS:self.assertFalse((fixture.output/name).exists())
                self.assertEqual("preserved",sibling.read_text())
                self.assertTrue((fixture.source/fixture.target["signing_key"]).is_file())
                self.assertTrue((fixture.output/"producer-private.log").is_file())

    def test_complete_or_private_overrides_are_rejected_without_copying_or_reading(self):
        fixture=self.fixture()
        environment={variable:str(fixture.signer.files[name]) for name,variable in helper.controller.ENVIRONMENT_INPUTS.items()}
        for private in (False,True):
            if private:
                fixture.signer.files["signer.crt.pem"].write_bytes(b"-----BEGIN PRIVATE KEY-----\nSYNTHETIC\n")
            with patch.object(helper.producer,"build") as compiler, \
                    self.assertRaisesRegex(RuntimeError,"generation-only"):
                helper.prepare(fixture.source,fixture.target["id"],fixture.output,fixture.workspace,"fixture-python",environ=environment)
            compiler.assert_not_called();self.assertFalse(fixture.output.exists())

    def test_certificate_tool_failure_and_producer_exception_do_not_publish_partial_paths(self):
        for case in ("compiler","certificate_tool"):
            with self.subTest(case=case):
                fixture=self.fixture();build,run=self.production_mocks(fixture)
                def failing_build(*args,**kwargs):
                    result=build(*args,**kwargs)
                    if case=="compiler":raise RuntimeError("synthetic compiler failure")
                    return result
                def failing_run(command,**kwargs):
                    if command[0]!="git" and case=="certificate_tool":
                        kwargs["stdout"].write(b"SYNTHETIC PRIVATE TOOL ERROR\n")
                        return subprocess.CompletedProcess(command,1)
                    return run(command,**kwargs)
                stdout,stderr=io.StringIO(),io.StringIO()
                with patch.object(helper.producer,"build",side_effect=failing_build), \
                        patch.object(helper.subprocess,"run",side_effect=failing_run), \
                        patch.dict(os.environ,{variable:"" for variable in helper.controller.ENVIRONMENT_INPUTS.values()}), \
                        redirect_stdout(stdout),redirect_stderr(stderr):
                    status=helper.main(["--source",str(fixture.source),"--target",fixture.target["id"],
                        "--output",str(fixture.output),"--workspace",str(fixture.workspace),"--python","fixture-python"])
                self.assertEqual(1,status);self.assertFalse(stdout.getvalue());self.assertNotIn("PRIVATE TOOL",stderr.getvalue())
                self.assertFalse((fixture.output/"build").exists())
                for name in helper.controller.ENVIRONMENT_INPUTS:self.assertFalse((fixture.output/name).exists())


if __name__=="__main__":unittest.main()

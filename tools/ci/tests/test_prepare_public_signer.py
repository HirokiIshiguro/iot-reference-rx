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

    def production_mocks(self,fixture,*,missing=None,formal=True,certificate=None,signing_key=None):
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
            self.assertEqual(signing_key or fixture.source/fixture.target["signing_key"],Path(command[command.index("--key")+1]))
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

    def test_explicit_normal_signer_selects_only_that_key_and_exports_public_files(self):
        fixture=self.fixture()
        selected=fixture.root/"explicit-normal-signing-key.pem"
        shutil.copyfile(fixture.source/fixture.target["signing_key"],selected)
        build,run=self.production_mocks(fixture,signing_key=selected)
        with patch.object(helper.producer,"build",side_effect=build),patch.object(helper.subprocess,"run",side_effect=run):
            paths=helper.prepare(fixture.source,fixture.target["id"],fixture.output,fixture.workspace,
                                 "fixture-python",environ={},signing_key=selected)
        self.assertNotIn(str(selected),paths.values())
        self.assertEqual(set(helper.controller.ENVIRONMENT_INPUTS.values()),set(paths))
        self.assertTrue(selected.is_file())

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

    def test_post_build_validation_failure_retains_private_diagnostic_without_local_values(self):
        fixture=self.fixture();build,run=self.production_mocks(fixture)
        def failed_validation(*args,**kwargs):
            build(*args,**kwargs)
            directory=args[2]
            (directory/"build-private.log").write_text("SYNTHETIC BUILD LOG")
            (directory/"launcher-private.log").write_text("SYNTHETIC LAUNCHER LOG")
            local_value="SYNTHETIC_VALUE_THAT_MUST_NOT_BE_CAPTURED"
            raise RuntimeError("synthetic post-build image validation failed")
        stdout,stderr=io.StringIO(),io.StringIO()
        with patch.object(helper.producer,"build",side_effect=failed_validation), \
                patch.object(helper.subprocess,"run",side_effect=run), \
                patch.dict(os.environ,{variable:"" for variable in helper.controller.ENVIRONMENT_INPUTS.values()}), \
                redirect_stdout(stdout),redirect_stderr(stderr):
            status=helper.main(["--source",str(fixture.source),"--target",fixture.target["id"],
                "--output",str(fixture.output),"--workspace",str(fixture.workspace),"--python","fixture-python"])
        self.assertEqual(1,status);self.assertFalse(stdout.getvalue())
        self.assertNotIn("synthetic post-build",stderr.getvalue())
        diagnostic=(fixture.output/"failure-private.log").read_text()
        self.assertIn("RuntimeError: synthetic post-build image validation failed",diagnostic)
        self.assertNotIn("SYNTHETIC_VALUE_THAT_MUST_NOT_BE_CAPTURED",diagnostic)
        self.assertEqual("SYNTHETIC BUILD LOG",(fixture.output/"failed-build-private.log").read_text())
        self.assertEqual("SYNTHETIC LAUNCHER LOG",(fixture.output/"failed-launcher-private.log").read_text())
        self.assertFalse((fixture.output/"build").exists())
        for name in helper.controller.ENVIRONMENT_INPUTS:self.assertFalse((fixture.output/name).exists())


class PublicFailureDiagnosticTests(unittest.TestCase):
    """Focused diagnostic-only cases; no campaign/native/credential fixture."""
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {}, clear=True).start()
        for name in ("run", "check_output", "Popen"):
            patch.object(subprocess, name, side_effect=AssertionError("Native boundary forbidden")).start()

    def record(self, error, stage="PREPARE_PRODUCER", **kwargs):
        helper.producer.remember_public_failure(error, stage, **kwargs)
        out = io.StringIO()
        helper.producer.emit_public_failure(error, out)
        prefix, payload = out.getvalue().split(" ", 1)
        self.assertEqual("PUBLIC_SIGNER_FAILURE", prefix)
        record = json.loads(payload)
        self.assertEqual({"schema", "stage", "exception_category", "failure_condition",
                          "native_child_failed", "compiler_diagnostic_code_presence"}, set(record))
        self.assertEqual("public-signer-failure-v2", record["schema"])
        self.assertEqual(set(helper.producer.PUBLIC_COMPILER_CODES), set(record["compiler_diagnostic_code_presence"]))
        self.assertTrue(all(type(value) is bool for value in record["compiler_diagnostic_code_presence"].values()))
        return record, out.getvalue()

    def test_known_unknown_and_prefix_conditions_retain_no_dynamic_text(self):
        secret = "SYNTHETIC_SECRET /synthetic/owner/private.pem endpoint.invalid include-local.h"
        cases = (
            (RuntimeError("Maintenance image has no matching compiled source identity"), "IMAGE_SOURCE_IDENTITY_MISMATCH"),
            (RuntimeError("Missing effective maintenance compiler defines"), "MAINTENANCE_DEFINES_MISSING"),
            (RuntimeError("Maintenance build returned a stale artifact: " + secret), "STALE_PROVISIONER_ARTIFACT"),
            (RuntimeError(secret + " Missing effective maintenance compiler defines"), "UNKNOWN"),
            (PermissionError(secret), "UNKNOWN"),
        )
        for error, expected in cases:
            with self.subTest(condition=expected):
                record, output = self.record(error)
                self.assertEqual(expected, record["failure_condition"])
                for token in ("SYNTHETIC_SECRET", "private.pem", "endpoint.invalid", "include-local.h"):
                    self.assertNotIn(token, output)

    def test_native_exit_and_timeout_use_only_fixed_captured_code_presence(self):
        secret = b"SYNTHETIC_SECRET /synthetic/private.pem endpoint.invalid"
        error = RuntimeError("Public signer provisioner build failed; inspect private build logs")
        record, output = self.record(error, "PRODUCER_NATIVE_CHILD", native_child_failed=True,
            captured=(b"F0520005 " + secret, b"E9999999 E0520020"))
        self.assertEqual("NATIVE_CHILD_EXIT", record["failure_condition"])
        self.assertTrue(record["compiler_diagnostic_code_presence"]["F0520005"])
        self.assertTrue(record["compiler_diagnostic_code_presence"]["E0520020"])
        self.assertNotIn("E9999999", output)
        timeout = subprocess.TimeoutExpired(["synthetic-child", secret.decode()], 1800,
                                            output=b"E0562310 " + secret, stderr=b"E0520065")
        record, output = self.record(timeout, "PRODUCER_NATIVE_CHILD", native_child_failed=True,
                                     captured=(timeout.output, timeout.stderr))
        self.assertEqual("NATIVE_CHILD_TIMEOUT", record["failure_condition"])
        self.assertTrue(record["compiler_diagnostic_code_presence"]["E0562310"])
        self.assertTrue(record["compiler_diagnostic_code_presence"]["E0520065"])
        self.assertNotIn("SYNTHETIC_SECRET", output)
        self.assertNotIn("private.pem", output)

    def test_stage_annotation_and_log_cleanup_replacement_preserve_exception_identity(self):
        original = RuntimeError("Maintenance image has no matching compiled source identity")
        log_error = PermissionError("SYNTHETIC_SECRET")
        cleanup_error = RuntimeError("Public signer build ownership changed during preparation")
        for replacement, expected_stage, expected_condition in (
            (None, "PREPARE_PRODUCER", "IMAGE_SOURCE_IDENTITY_MISMATCH"),
            (log_error, "PREPARE_FAILURE_LOG", "UNKNOWN"),
            (cleanup_error, "PREPARE_CLEANUP", "BUILD_OWNERSHIP_CHANGED"),
        ):
            with self.subTest(stage=expected_stage):
                try:
                    try:
                        with helper.producer.public_failure_stage("PREPARE_PRODUCER"):
                            raise original
                    finally:
                        if replacement is not None:
                            with helper.producer.public_failure_stage(expected_stage):
                                raise replacement
                except BaseException as escaped:
                    self.assertIs(replacement or original, escaped)
                    record, _ = self.record(escaped)
                    self.assertEqual(expected_stage, record["stage"])
                    self.assertEqual(expected_condition, record["failure_condition"])

    def test_prepare_manifest_failure_log_and_cleanup_precedence(self):
        for mode in ("manifest", "failure_log", "cleanup"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                project = source / "synthetic_project"
                project.mkdir(parents=True)
                (project / ".project").write_text(
                    "<projectDescription><name>synthetic</name></projectDescription>",
                    encoding="utf-8",
                )
                output, workspace = root / "output", root / "workspace"
                log_error = PermissionError("SYNTHETIC_SECRET")
                cleanup_error = RuntimeError("Public signer build ownership changed during preparation")
                calls = []

                def fake_build(repo, target_id, build, selected_workspace, python):
                    self.assertEqual(source, repo)
                    build.mkdir()
                    metadata = {"formal": False}
                    (build / "provisioner-manifest.json").write_text(json.dumps(metadata), encoding="utf-8")
                    return metadata

                def fake_cleanup(selected_output, build):
                    calls.append((selected_output, build, (output / "failure-private.log").exists()))
                    if mode == "cleanup":
                        raise cleanup_error

                with patch.object(helper, "get_target", return_value={"application_project": "synthetic_project"}), \
                        patch.object(helper, "_source_state", return_value="b" * 40), \
                        patch.object(helper.producer, "build", side_effect=fake_build), \
                        patch.object(helper, "_cleanup_public_outputs", side_effect=fake_cleanup):
                    try:
                        if mode == "failure_log":
                            with patch.object(helper.os, "open", side_effect=log_error):
                                helper.prepare(source, "synthetic-target", output, workspace, "synthetic-python", environ={})
                        else:
                            helper.prepare(source, "synthetic-target", output, workspace, "synthetic-python", environ={})
                    except BaseException as error:
                        escaped = error
                    else:
                        self.fail("Synthetic manifest failure did not escape")

                self.assertEqual([(output, output / "build", mode != "failure_log")], calls)
                if mode == "failure_log":
                    self.assertIs(log_error, escaped)
                    expected_stage, expected_condition = "PREPARE_FAILURE_LOG", "UNKNOWN"
                elif mode == "cleanup":
                    self.assertIs(cleanup_error, escaped)
                    expected_stage, expected_condition = "PREPARE_CLEANUP", "BUILD_OWNERSHIP_CHANGED"
                else:
                    self.assertEqual("Public signer producer did not return a formal matching source manifest", str(escaped))
                    expected_stage, expected_condition = "PREPARE_MANIFEST", "PRODUCER_MANIFEST_MISMATCH"
                record, public_text = self.record(escaped)
                self.assertEqual(expected_stage, record["stage"])
                self.assertEqual(expected_condition, record["failure_condition"])
                self.assertNotIn("SYNTHETIC_SECRET", public_text)
                self.assertNotIn(str(root), public_text)

    def test_failure_cli_emits_only_fixed_record_and_generic_message(self):
        error = RuntimeError("SYNTHETIC_SECRET endpoint.invalid /synthetic/private.pem")
        original_args = error.args
        out, err = io.StringIO(), io.StringIO()
        target = next(iter(helper.controller.LAYOUTS))
        with patch.object(helper, "prepare", side_effect=error), redirect_stdout(out), redirect_stderr(err):
            status = helper.main(["--source", "synthetic-source", "--target", target,
                "--output", "synthetic-output", "--workspace", "synthetic-workspace"])
        self.assertEqual(1, status)
        self.assertEqual("", out.getvalue())
        lines = err.getvalue().splitlines()
        self.assertEqual(2, len(lines))
        self.assertTrue(lines[0].startswith("PUBLIC_SIGNER_FAILURE "))
        self.assertEqual("UNKNOWN", json.loads(lines[0].split(" ", 1)[1])["failure_condition"])
        self.assertEqual("Public signer preparation failed; inspect the requested private output directory.", lines[1])
        self.assertEqual(original_args, error.args)
        for token in ("SYNTHETIC_SECRET", "endpoint.invalid", "private.pem"):
            self.assertNotIn(token, err.getvalue())

    def test_failure_emission_cannot_replace_original_exception(self):
        error = RuntimeError("Missing effective maintenance compiler defines")
        stream = Mock(); stream.write.side_effect = OSError("SYNTHETIC_SECRET")
        with self.assertRaises(RuntimeError) as caught:
            try:
                raise error
            except RuntimeError as original:
                helper.producer.emit_public_failure(original, stream)
                raise
        self.assertIs(error, caught.exception)

    def test_success_cli_stdout_and_stderr_unchanged(self):
        paths = {"MOCK_PUBLIC_INPUT": "synthetic-public-output"}
        out, err = io.StringIO(), io.StringIO()
        target = next(iter(helper.controller.LAYOUTS))
        with patch.object(helper, "prepare", return_value=paths) as prepared, \
                redirect_stdout(out), redirect_stderr(err):
            status = helper.main(["--source", "synthetic-source", "--target", target,
                "--output", "synthetic-output", "--workspace", "synthetic-workspace"])
        self.assertEqual(0, status)
        self.assertEqual(json.dumps(paths, sort_keys=True) + "\n", out.getvalue())
        self.assertEqual("", err.getvalue())
        prepared.assert_called_once()


if __name__=="__main__":unittest.main()

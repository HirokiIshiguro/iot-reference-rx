"""Exercise the real PowerShell lifecycle against a local AWS CLI stub only."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[3]
PWSH = shutil.which("pwsh")
STUB = r'''
$ErrorActionPreference = 'Stop'
$values = @($args | ForEach-Object { [string]$_ })
$file = $env:LANBENCH_STUB_STATE
$state = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json -AsHashtable
$state.calls += ,$values
$operation = ($values | Select-Object -First 2) -join ' '
if ($values[1] -eq 'wait') { $operation = ($values | Select-Object -First 3) -join ' ' }
function Save { $state | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $file }
function Owner-Tags {
    $owner = (Get-Content -LiteralPath $state.journal -Raw | ConvertFrom-Json).owner
    return @(@{ Key='Project';Value='iot-reference-rx' }, @{Key='Purpose';Value='lanbench-tls13-0rtt'},
        @{Key='GitLabProjectId';Value=[string]$owner.project_id}, @{Key='GitLabPipelineId';Value=[string]$owner.pipeline_id},
        @{Key='GitLabJobId';Value=[string]$owner.job_id}, @{Key='RunId';Value=[string]$owner.run_id})
}
function Stub-Instance {
    $owner = (Get-Content -LiteralPath $state.journal -Raw | ConvertFrom-Json).owner
    $tags = Owner-Tags
    if ($state.wrong_instance_tags) { $tags[-1].Value = 'different-run' }
    return @{ InstanceId='i-11111111';ClientToken=[string]$owner.run_id;Tags=$tags;
        State=@{Name=$state.instance_state};PublicIpAddress='127.0.0.1';PublicDnsName='fixture.invalid';InstanceType='fixture';
        Placement=@{AvailabilityZone='fixture-zone'};BlockDeviceMappings=@(@{Ebs=@{VolumeId='vol-55555555';DeleteOnTermination=$true}}) }
}
function Stub-Group {
    $meta = Get-Content -LiteralPath $state.journal -Raw | ConvertFrom-Json
    $tags = if ($state.owned_group) { Owner-Tags } else { @(@{Key='Project';Value='iot-reference-rx'}) }
    if ($state.wrong_group_tags) { $tags[0].Value = 'other-project' }
    return @{GroupId='sg-22222222';GroupName=$meta.security_group.name;VpcId='vpc-33333333';Tags=$tags;
        IpPermissions=@(@{IpProtocol='tcp';FromPort=1;ToPort=65535;IpRanges=@(@{CidrIp='0.0.0.0/0'})})}
}
if ($state.delay_operation -eq $operation) { Start-Sleep -Milliseconds 3200 }
if ($state.malformed_operation -eq $operation) {
    Save; $global:LASTEXITCODE = 0
    Write-Output 'fixture-private-diagnostic is not JSON'
    return
}
if ($state.fail_operation -eq $operation) {
    Save; $global:LASTEXITCODE = 255
    Write-Output 'An error occurred (SyntheticFailure) when calling the operation: fixture-private-diagnostic'
    return
}
$global:LASTEXITCODE = 0
$body = switch ($operation) {
    'ec2 describe-vpcs' { @{Vpcs=@(@{VpcId='vpc-33333333'})};break }
    'ec2 describe-subnets' { @{Subnets=@(@{SubnetId='subnet-66666666';VpcId='vpc-33333333';State='available'})};break }
    'ec2 describe-security-groups' {
        if ($state.group_exists) {
            $g=Stub-Group
            if ($values -contains '--filters' -and -not $state.owned_group) { $g.GroupName='fixture-sg' }
            @{SecurityGroups=@($g)}
        } elseif ($values -contains '--group-ids') {
            Save;$global:LASTEXITCODE=255
            Write-Output 'An error occurred (InvalidGroup.NotFound) when calling DescribeSecurityGroups: fixture-private-diagnostic'
            return
        } else { @{SecurityGroups=@()} }
        break
    }
    'ec2 create-security-group' { $state.group_exists=$true;$state.owned_group=$true;@{GroupId='sg-22222222'};break }
    'ec2 authorize-security-group-ingress' { @{};break }
    'ssm get-parameter' { 'ami-44444444';break }
    'ec2 describe-images' { @{Images=@(@{ImageId='ami-44444444';BlockDeviceMappings=@(@{DeviceName='/dev/xvda';Ebs=@{}})})};break }
    'ec2 run-instances' { $state.instance_exists=$true;$state.instance_state='running';@{Instances=@(@{InstanceId='i-11111111'})};break }
    'ec2 wait instance-running' { '';break }
    'ec2 describe-instances' {
        if ($state.instance_exists) { @{Reservations=@(@{Instances=@((Stub-Instance))})} }
        elseif ($values -contains '--instance-ids') {
            Save;$global:LASTEXITCODE=255
            Write-Output 'An error occurred (InvalidInstanceID.NotFound) when calling DescribeInstances: fixture-private-diagnostic'
            return
        } else { @{Reservations=@()} }
        break
    }
    'ec2 describe-volumes' {
        $tags=Owner-Tags
        if ($state.wrong_volume_tags) { $tags[-1].Value='foreign-volume' }
        @{Volumes=@(@{VolumeId='vol-55555555';Tags=$tags})};break
    }
    'ec2 terminate-instances' { $state.instance_state='shutting-down';@{};break }
    'ec2 wait instance-terminated' { $state.instance_state='terminated';'';break }
    'ec2 wait volume-deleted' { '';break }
    'ec2 delete-security-group' { $state.group_exists=$false;@{};break }
    default { Save;throw 'Unexpected AWS stub operation.' }
}
Save
if ($body -is [string]) { Write-Output $body } else { $body | ConvertTo-Json -Depth 20 -Compress }
'''


@unittest.skipUnless(PWSH, "PowerShell 7 is required for the offline AWS CLI fixture")
class LanbenchOwnedCleanupTests(unittest.TestCase):
    def setUp(self):
        # Keep all new fixture files inside the authorized workspace.
        base = Path("C:/ai/codex/tmp") if os.name == "nt" else Path(tempfile.gettempdir())
        self.temp = tempfile.TemporaryDirectory(prefix="lanbench-owned-", dir=base)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.journal = self.folder / "creation.json"
        self.result = self.folder / "cleanup.json"
        self.stub = self.folder / "aws-fixture.ps1"
        self.stub.write_text(STUB, encoding="utf-8")
        self.state_file = self.folder / "state.json"
        self.state = {"journal": str(self.journal), "calls": [], "group_exists": True,
                      "owned_group": False, "instance_exists": True, "instance_state": "running",
                      "wrong_instance_tags": False, "wrong_volume_tags": False, "wrong_group_tags": False,
                      "fail_operation": "", "delay_operation": "", "malformed_operation": ""}
        self.save_state()

    def save_state(self):
        self.state_file.write_text(json.dumps(self.state), encoding="utf-8")

    def read_state(self):
        return json.loads(self.state_file.read_text(encoding="utf-8-sig"))

    def metadata(self, *, owned_group=False, requested=True, instance_id="i-11111111"):
        run = "a" * 32
        value = {"schema_version": 2, "resource_kind": "lanbench-ec2", "state": "ready",
                 "region": "ap-northeast-1", "instance_name": "fixture-instance",
                 "instance_id": instance_id, "instance_requested": requested, "client_token": run,
                 "owner": {"project_id": "71", "pipeline_id": "99", "job_id": "31", "run_id": run},
                 "volume_ids": ["vol-55555555"] if instance_id else [],
                 "security_group": {"id": "sg-22222222", "name": "fixture-sg-" + run if owned_group else "fixture-sg",
                                    "vpc_id": "vpc-33333333", "created_by_run": owned_group, "requested": owned_group}}
        self.journal.write_text(json.dumps(value), encoding="utf-8")
        self.state["owned_group"] = owned_group
        self.save_state()
        return value

    def run_script(self, name, extra=()):
        allowed = ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT", "COMSPEC", "USERPROFILE",
                   "HOME", "LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "ProgramW6432", "PSModulePath")
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        env.update(LANBENCH_STUB_STATE=str(self.state_file), CI_JOB_ID="999",
                   AWS_EC2_METADATA_DISABLED="true", AWS_PROFILE="fixture-no-profile")
        command = [PWSH, "-NoProfile", "-File", str(ROOT / "tools/aws" / name), "-Region", "ap-northeast-1",
                   "-InstanceName", "fixture-instance", "-ProjectId", "71", "-PipelineId", "99",
                   "-OutputJson", str(self.result if name.startswith("terminate") else self.journal),
                   "-AwsCli", str(self.stub), *extra]
        return subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)

    def cleanup(self):
        return self.run_script("terminate_lanbench_tls13_0rtt_ec2.ps1", ["-MetadataJson", str(self.journal)])

    def mutations(self):
        return [row[1] for row in self.read_state()["calls"]
                if row[1] in {"terminate-instances", "delete-security-group", "start-instances", "run-instances",
                              "create-security-group", "authorize-security-group-ingress", "create-tags"}]

    def test_cleanup_requires_journal_and_current_pipeline_before_any_aws_call(self):
        missing = self.cleanup()
        self.assertNotEqual(0, missing.returncode)
        self.assertEqual([], self.read_state()["calls"])
        self.assertFalse(json.loads(self.result.read_text())["passed"])
        value = self.metadata()
        value["owner"]["pipeline_id"] = "100"
        self.journal.write_text(json.dumps(value), encoding="utf-8")
        wrong = self.cleanup()
        self.assertNotEqual(0, wrong.returncode)
        self.assertEqual([], self.read_state()["calls"])

    def test_cleanup_job_id_may_differ_and_shared_group_is_not_mutated(self):
        self.metadata()
        result = self.cleanup()
        self.assertEqual(0, result.returncode, result.stderr)
        summary = json.loads(self.result.read_text())
        self.assertTrue(summary["passed"])
        self.assertEqual("retained_shared", summary["security_group_state"])
        self.assertEqual(["terminate-instances"], self.mutations())
        self.assertNotIn("fixture-private-diagnostic", result.stdout)

    def test_instance_or_volume_owner_mismatch_stops_before_termination(self):
        self.metadata()
        for flag in ("wrong_instance_tags", "wrong_volume_tags"):
            with self.subTest(flag=flag):
                self.state["calls"] = []
                self.state["wrong_instance_tags"] = flag == "wrong_instance_tags"
                self.state["wrong_volume_tags"] = flag == "wrong_volume_tags"
                self.save_state()
                result = self.cleanup()
                self.assertNotEqual(0, result.returncode)
                self.assertEqual([], self.mutations())

    def test_cli_failure_and_failed_wait_cannot_report_terminated(self):
        self.metadata()
        for operation in ("ec2 terminate-instances", "ec2 wait instance-terminated"):
            with self.subTest(operation=operation):
                self.state.update(calls=[], instance_state="running", fail_operation=operation)
                self.save_state()
                result = self.cleanup()
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(json.loads(self.result.read_text())["passed"])
                self.assertNotIn("fixture-private-diagnostic", result.stdout + result.stderr)

    def test_owned_security_group_is_deleted_only_after_owner_and_instance_end(self):
        self.metadata(owned_group=True)
        result = self.cleanup()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["terminate-instances", "delete-security-group"], self.mutations())
        self.assertEqual("absent", json.loads(self.result.read_text())["security_group_state"])
        calls = self.read_state()["calls"]
        self.assertLess(next(i for i, a in enumerate(calls) if a[:3] == ["ec2", "wait", "instance-terminated"]),
                        next(i for i, a in enumerate(calls) if a[1] == "delete-security-group"))

    def test_other_security_group_owner_is_preserved(self):
        self.metadata(owned_group=True)
        self.state["wrong_group_tags"] = True
        self.save_state()
        result = self.cleanup()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(["terminate-instances"], self.mutations())

    def test_unknown_launch_uses_only_client_token_and_owner_tags(self):
        self.metadata(instance_id="")
        result = self.cleanup()
        self.assertEqual(0, result.returncode, result.stderr)
        filters = self.read_state()["calls"][0]
        self.assertIn("Name=client-token,Values=" + "a" * 32, filters)
        for key in ("GitLabProjectId", "GitLabPipelineId", "GitLabJobId", "RunId"):
            self.assertTrue(any(value.startswith("Name=tag:" + key + ",Values=") for value in filters))
        self.assertFalse(any(value.startswith("Name=tag:Name,") for value in filters))

    def test_unresolved_launch_is_held_and_known_absence_is_idempotent(self):
        self.metadata(instance_id="")
        self.state["instance_exists"] = False
        self.save_state()
        unknown = self.cleanup()
        self.assertNotEqual(0, unknown.returncode)
        self.assertEqual([], self.mutations())
        self.metadata()
        known = self.cleanup()
        self.assertEqual(0, known.returncode, known.stderr)
        self.assertEqual("already_absent", json.loads(self.result.read_text())["instance_state"])
        self.assertEqual([], self.mutations())

    def test_creation_has_no_instance_name_reuse_and_journals_before_launch(self):
        self.state["instance_exists"] = False
        self.save_state()
        with contextlib.closing(socket.socket()) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.settimeout(60)
            accepted = []
            def accept():
                try:
                    connection, _ = listener.accept()
                except OSError:
                    return
                connection.close()
                accepted.append(True)
            thread = threading.Thread(target=accept, daemon=True)
            thread.start()
            result = self.run_script("create_lanbench_tls13_0rtt_ec2.ps1", ["-JobId", "31", "-SecurityGroupName", "fixture-sg",
                    "-Port", str(listener.getsockname()[1]), "-ServerReadyTimeoutSeconds", "5"])
            thread.join(timeout=2)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(accepted)
        meta = json.loads(self.journal.read_text())
        self.assertEqual("ready", meta["state"])
        self.assertEqual(meta["owner"]["run_id"], meta["client_token"])
        calls = self.read_state()["calls"]
        self.assertFalse(any(row[1] == "start-instances" for row in calls))
        self.assertFalse(any(row[1] == "describe-instances" and "--filters" in row for row in calls))
        launch = next(row for row in calls if row[1] == "run-instances")
        self.assertIn("--client-token", launch)
        self.assertIn("DeleteOnTermination=true", " ".join(launch))
        self.assertEqual(["run-instances"], self.mutations())
        self.assertNotIn("127.0.0.1", result.stdout + result.stderr)

    def test_creation_failure_preserves_exact_instance_for_later_cleanup(self):
        self.state.update(instance_exists=False, fail_operation="ec2 wait instance-running")
        self.save_state()
        result = self.run_script("create_lanbench_tls13_0rtt_ec2.ps1", ["-JobId", "31", "-SecurityGroupName", "fixture-sg"])
        self.assertNotEqual(0, result.returncode)
        meta = json.loads(self.journal.read_text())
        self.assertEqual("prepare_failed", meta["state"])
        self.assertEqual("i-11111111", meta["instance_id"])
        self.assertNotIn("fixture-private-diagnostic", result.stdout + result.stderr)

    def test_invalid_shared_group_is_not_changed_to_make_creation_pass(self):
        self.state.update(instance_exists=False, wrong_group_tags=True)
        self.save_state()
        result = self.run_script("create_lanbench_tls13_0rtt_ec2.ps1", ["-JobId", "31", "-SecurityGroupName", "fixture-sg"])
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], self.mutations())
        self.assertFalse(json.loads(self.journal.read_text())["instance_requested"])

    def test_creation_owns_new_group_and_cleanup_deletes_only_that_group(self):
        self.state.update(instance_exists=False, group_exists=False)
        self.save_state()
        with contextlib.closing(socket.socket()) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.settimeout(60)
            def accept():
                try:
                    connection, _ = listener.accept()
                except OSError:
                    return
                connection.close()
            thread = threading.Thread(target=accept, daemon=True)
            thread.start()
            created = self.run_script("create_lanbench_tls13_0rtt_ec2.ps1", ["-JobId", "31", "-SecurityGroupName", "fixture-sg",
                    "-Port", str(listener.getsockname()[1]), "-ServerReadyTimeoutSeconds", "5"])
            thread.join(timeout=2)
        self.assertEqual(0, created.returncode, created.stderr)
        meta = json.loads(self.journal.read_text())
        self.assertTrue(meta["security_group"]["created_by_run"])
        self.assertTrue(meta["security_group"]["name"].endswith(meta["owner"]["run_id"]))
        closed = self.cleanup()
        self.assertEqual(0, closed.returncode, closed.stderr)
        self.assertEqual(["create-security-group", "authorize-security-group-ingress", "run-instances",
                          "terminate-instances", "delete-security-group"], self.mutations())

    def test_delayed_cli_wait_emits_generic_status_without_raw_diagnostics(self):
        self.metadata()
        self.state["delay_operation"] = "ec2 wait instance-terminated"
        self.save_state()
        result = self.cleanup()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("LANBENCH AWS operation active: ec2 wait", result.stdout)
        self.assertNotIn("fixture-private-diagnostic", result.stdout + result.stderr)

    def test_invalid_cli_json_is_rejected_without_leaking_its_body(self):
        self.metadata()
        self.state["malformed_operation"] = "ec2 describe-instances"
        self.save_state()
        result = self.cleanup()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], self.mutations())
        self.assertNotIn("fixture-private-diagnostic", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

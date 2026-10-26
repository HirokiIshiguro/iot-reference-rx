"""The RX72N preflight must only list; existing executions belong to other runs."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import cleanup_iot_jobs as jobs


ROOT = Path(__file__).resolve().parents[3]


def process(payload, returncode=0):
    child = mock.Mock()
    child.returncode = returncode
    child.poll.return_value = returncode
    child.communicate.return_value = (json.dumps(payload), "PRIVATE_AWS_STDERR")
    return child


def execution(status, job_id="AFR_OTA-PRIVATE_JOB_ID"):
    return {"jobId": job_id, "jobExecutionSummary": {"status": status}}


class ReadOnlyJobSnapshotTests(unittest.TestCase):
    def run_check(self, children):
        with tempfile.TemporaryDirectory(prefix="job-check-", dir=ROOT) as folder:
            output = Path(folder) / "summary.json"
            stream = io.StringIO()
            with mock.patch.object(jobs, "aws_command_prefix", return_value=["aws"]), \
                 mock.patch.object(jobs.subprocess, "Popen", side_effect=children) as popen, \
                 mock.patch.object(jobs, "run_aws", side_effect=AssertionError("legacy AWS path")), \
                 mock.patch.object(jobs, "run_command", side_effect=AssertionError("legacy command path")), \
                 mock.patch.object(jobs.time, "sleep", side_effect=AssertionError("polling")), \
                 mock.patch.object(jobs.sys, "argv", ["cleanup_iot_jobs.py", "--check-empty",
                     "--thing-name", "PRIVATE_THING", "--region", "test-region",
                     "--output-json", str(output)]), redirect_stdout(stream):
                code = jobs.main()
            text = stream.getvalue()
            summary = json.loads(output.read_text())
            self.assertNotIn("PRIVATE_", text + output.read_text())
            for call in popen.call_args_list:
                command = call.args[0]
                self.assertEqual(command[1:3], ["iot", "list-job-executions-for-thing"])
                self.assertIn("--no-paginate", command)
                self.assertEqual(command[command.index("--max-results") + 1], "250")
                self.assertEqual(call.kwargs["env"]["AWS_MAX_ATTEMPTS"], "1")
                self.assertFalse(call.kwargs.get("shell", False))
            return code, summary, popen.call_args_list

    def test_empty_snapshot_passes_with_exactly_two_read_only_calls(self):
        code, summary, calls = self.run_check([
            process({"executionSummaries": []}), process({"executionSummaries": []})])
        self.assertEqual(code, 0)
        self.assertEqual(summary["status"], "empty")
        self.assertEqual(summary["active_count"], 0)
        self.assertEqual(summary["mutation_count"], 0)
        self.assertTrue(summary["snapshot_complete"])
        self.assertEqual([call.args[0][call.args[0].index("--status") + 1] for call in calls],
                         ["QUEUED", "IN_PROGRESS"])

    def test_active_execution_fails_without_cancelling_or_waiting(self):
        code, summary, calls = self.run_check([
            process({"executionSummaries": [execution("QUEUED")]}),
            process({"executionSummaries": [execution("IN_PROGRESS"),
                                             execution("IN_PROGRESS", "unrelated-prefix") ]})])
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "active")
        self.assertEqual(summary["active_count"], 2)
        self.assertEqual(summary["status_counts"], {"QUEUED": 1, "IN_PROGRESS": 1})
        self.assertEqual(summary["mutation_count"], 0)
        self.assertEqual(len(calls), 2)

    def test_pagination_is_terminal_and_does_not_read_another_page(self):
        code, summary, calls = self.run_check([
            process({"executionSummaries": [], "nextToken": "PRIVATE_TOKEN"})])
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "incomplete_snapshot")
        self.assertFalse(summary["snapshot_complete"])
        self.assertEqual(len(calls), 1)

    def test_cli_failure_is_terminal_and_redacts_raw_output(self):
        code, summary, calls = self.run_check([
            process({"PRIVATE_RESULT": "PRIVATE_JOB_ID"}, returncode=1)])
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "lookup_failed")
        self.assertIsNone(summary["active_count"])
        self.assertEqual(len(calls), 1)

    def test_interruption_stops_the_owned_cli_and_emits_no_raw_output(self):
        child = process({"executionSummaries": []})
        child.poll.return_value = None
        child.communicate.side_effect = [KeyboardInterrupt, ("", "PRIVATE_AWS_STDERR")]
        code, summary, calls = self.run_check([child])
        self.assertEqual(code, 130)
        self.assertEqual(summary["status"], "interrupted")
        self.assertEqual(len(calls), 1)
        child.kill.assert_called_once_with()

    def test_waiting_uses_heartbeat_without_repeating_the_api_call(self):
        child = process({"executionSummaries": []})
        child.communicate.side_effect = [subprocess.TimeoutExpired("PRIVATE_COMMAND", 3),
                                        (json.dumps({"executionSummaries": []}), "")]
        code, summary, calls = self.run_check([child, process({"executionSummaries": []})])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(child.communicate.call_args_list[0].kwargs["timeout"], 3)
        self.assertEqual(summary["active_count"], 0)

    def test_deadline_stops_the_owned_cli_without_retrying(self):
        child = process({"executionSummaries": []})
        child.poll.return_value = None
        child.communicate.side_effect = [subprocess.TimeoutExpired("PRIVATE_COMMAND", 3), ("", "")]
        with mock.patch.object(jobs.time, "monotonic", side_effect=[0, 0, 28]):
            code, summary, calls = self.run_check([child])
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "lookup_failed")
        self.assertEqual(len(calls), 1)
        child.kill.assert_called_once_with()

    def test_rx72n_preparation_job_explicitly_selects_the_read_only_mode(self):
        ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        job = ci.split("\ncleanup_rx72n_ether_ota_jobs:\n", 1)[1].split("\ntest_rx671_wifi:", 1)[0]
        self.assertIn("--check-empty", job)
        self.assertIn("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }", job)
        self.assertNotIn("allow_failure: true", job)


if __name__ == "__main__":
    unittest.main()
